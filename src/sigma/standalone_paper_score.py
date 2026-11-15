"""Score an existing PDF without creating or changing a SIGMA project."""

from __future__ import annotations

import asyncio
import hashlib
import sys
from pathlib import Path

from sigma import memory_guard, paper_scores, papers
from sigma.openai_connection import auth_context
from sigma.projects import ProjectError
from sigma.proposals import configuration

MAX_PDF_BYTES = 32 * 1024 * 1024


def read_pdf(path: str) -> bytes:
    target = Path(path).expanduser()
    if not target.is_file() or target.is_symlink():
        raise ProjectError("Expected an existing, regular PDF file (not a symlink).")
    if target.suffix.lower() != ".pdf":
        raise ProjectError("The input must be a .pdf file.")
    try:
        with target.open("rb") as source:
            pdf = source.read(MAX_PDF_BYTES + 1)
    except OSError as exc:
        raise ProjectError(f"Could not read PDF: {exc}") from exc
    if len(pdf) > MAX_PDF_BYTES:
        raise ProjectError("PDF exceeds the 32 MiB standalone scoring limit.")
    if not pdf.startswith(b"%PDF-"):
        raise ProjectError("The input is not a PDF document.")
    return pdf


def format_score(score: dict, *, filename: str, model: str, effort: str) -> str:
    lines = [
        f"SIGMA paper score — {filename}",
        f"Rubric: {score['rubric_id']} v{score['rubric_version']}",
        f"Model / Thinking: {model} / {effort}",
        "",
        f"{'Category':<39} {'Score':>7} {'Weight':>8} {'Weighted':>9}",
        "-" * 67,
    ]
    for key, weight in paper_scores.WEIGHTS.items():
        row = score["categories"][key]
        earned = row["earned"]
        lines.append(
            f"{paper_scores.DESCRIPTION[key]:<39} "
            f"{earned:>3}/100 {weight:>7}% {earned * weight / 100:>8.2f}"
        )
        lines.append(f"  {row['explanation']}")
    lines.extend(
        [
            "-" * 67,
            f"Weighted total: {score['total']}/100",
            "",
            "Provisional AI assessment of PDF excerpts, not peer review.",
            "No SIGMA research archive or external reference verification was available.",
        ]
    )
    return "\n".join(lines)


async def score_file(path: str) -> tuple[dict, str, str]:
    pdf = read_pdf(path)
    memory_guard.require_capacity()
    binding = await auth_context()
    config = await configuration(context=binding)
    if not config["available"]:
        raise ProjectError(config["message"])
    # The existing PDF geometry/excerpt inspector and scoring prompt are reused.
    # Empty archival context is intentional: do not fabricate a research history.
    context = paper_scores._context({}, pdf)
    judgment, _ = await papers._provider_structured(
        context,
        binding,
        config,
        instructions=paper_scores.INSTRUCTIONS,
        schema_name="sigma_paper_score_v3",
        response_model=paper_scores.PaperJudgment,
        max_input_bytes=180000,
    )
    score = paper_scores._make_score(
        paper_scores.PaperJudgment.model_validate(judgment), hashlib.sha256(pdf).hexdigest()
    )
    return score, config["model"], config["reasoning_effort"]


def run(path: str) -> int:
    from sigma.local_config import load_local_config

    try:
        load_local_config()
        score, model, effort = asyncio.run(score_file(path))
        print(format_score(score, filename=Path(path).name, model=model, effort=effort))
        return 0
    except (ProjectError, OSError, RuntimeError, ValueError) as exc:
        print(f"sigma score_paper: {exc}", file=sys.stderr)
        return 2
