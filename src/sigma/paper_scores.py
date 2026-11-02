"""Versioned, research-aware editorial scoring of saved paper PDFs.

Scores are provisional evaluations of the rendered PDF, not peer review.
The overall score is always normalized to 100.
"""
from __future__ import annotations

import asyncio
import fcntl
import hashlib
import json
import os
from typing import Any

import pypdfium2
from pydantic import BaseModel, ConfigDict, Field

from sigma.projects import ProjectError, _stage, inspect_project, project_path

RUBRIC_ID = "sigma-paper-quality"
RUBRIC_VERSION = 2
WEIGHTS = {
    "tex_correctness": 5,
    "readability": 25,
    "sustained_answer": 20,
    "research_rigor": 30,
    "evidence": 15,
    "visuals": 5,
}
assert sum(WEIGHTS.values()) == 100

DESCRIPTION = {
    "tex_correctness": "TeX correctness",
    "readability": "Human readability, including layout",
    "sustained_answer": "Clear question and sustained answer",
    "research_rigor": "Research rigor and correctness",
    "evidence": "Evidence and verification",
    "visuals": "Useful visuals",
}

class CategoryJudgment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    earned: int = Field(ge=0, le=100)
    explanation: str = Field(min_length=8, max_length=1500)

class PaperJudgment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tex_correctness: CategoryJudgment
    readability: CategoryJudgment
    sustained_answer: CategoryJudgment
    research_rigor: CategoryJudgment
    evidence: CategoryJudgment
    visuals: CategoryJudgment

def validate_score(score: Any, pdf_sha: str) -> dict[str, Any] | None:
    """Reject stale or malformed stored scores, including incorrect totals."""
    if not isinstance(score, dict):
        return None
    if (score.get("rubric_id"), score.get("rubric_version"), score.get("pdf_sha256")) != (
        RUBRIC_ID, RUBRIC_VERSION, pdf_sha
    ):
        return None
    rows = score.get("categories")
    if not isinstance(rows, dict) or set(rows) != set(WEIGHTS):
        return None
    total = 0
    for key, maximum in WEIGHTS.items():
        row = rows[key]
        if not isinstance(row, dict) or set(row) != {"earned", "max", "explanation"}:
            return None
        earned = row["earned"]
        if type(earned) is not int or not 0 <= earned <= maximum or row["max"] != maximum:
            return None
        if not isinstance(row["explanation"], str) or not row["explanation"].strip():
            return None
        total += earned
    if type(score.get("total")) is not int or score["total"] != total:
        return None
    return score

def cached_score(record: dict[str, Any]) -> dict[str, Any] | None:
    sha = record.get("pdf_sha256")
    if not isinstance(sha, str) or len(sha) != 64:
        return None
    return validate_score(record.get("score"), sha)

def best_score(summaries: list[dict[str, Any]]) -> int | None:
    scores = [
        item["score"]["total"]
        for item in summaries
        if item.get("pdf_available") and isinstance(item.get("score"), dict)
        and validate_score(item["score"], item.get("pdf_sha256", ""))
    ]
    return max(scores, default=None)

def _pdf_excerpts(pdf: bytes) -> dict[str, Any]:
    """Inspect actual compiled PDF text and page geometry, not TeX source."""
    from sigma import papers
    page_count, warnings = papers._pdf_text_bounds_diagnostics(pdf)
    pages: list[dict[str, Any]] = []
    document = pypdfium2.PdfDocument(pdf)
    try:
        for number in range(min(page_count, 24)):
            page = document[number]
            try:
                textpage = page.get_textpage()
                try:
                    text = textpage.get_text_range()
                finally:
                    textpage.close()
                pages.append({
                    "page": number + 1,
                    "text": text[:2400],
                    "truncated": len(text) > 2400,
                    "width": round(page.get_width()),
                    "height": round(page.get_height()),
                })
            finally:
                page.close()
    finally:
        document.close()
    return {"page_count": page_count, "geometry_warnings": warnings[:20],
            "pages": pages, "additional_pages_omitted": max(0, page_count - len(pages))}

def _context(record: dict[str, Any], pdf: bytes) -> dict[str, Any]:
    draft = record.get("draft") or {}
    snapshot = record.get("snapshot") or {}
    sources = snapshot.get("sources") if isinstance(snapshot, dict) else None
    claim_list = draft.get("claims") if isinstance(draft, dict) else None
    return {
        "pdf": _pdf_excerpts(pdf),
        "recorded_validation_warnings": (record.get("validation_warnings") or [])[:20],
        "recorded_author_review_warnings": (record.get("author_review_warnings") or [])[:20],
        "claim_register": [
            {"statement": str(item.get("statement", ""))[:400],
             "status": str(item.get("status", ""))[:80],
             "evidence_refs": item.get("evidence_refs", [])[:15],
             "reasoning": str(item.get("reasoning", ""))[:350]}
            for item in (claim_list or [])[:40] if isinstance(item, dict)
        ],
        "saved_research_source_inventory": [
            {"id": str(item.get("id", ""))[:100], "kind": str(item.get("kind", ""))[:80]}
            for item in (sources or [])[:100] if isinstance(item, dict)
        ],
        "evidence_limit": "Only source IDs and the saved paper claim register are supplied. "
        "Do not claim the original research archive or external references were independently verified.",
    }

INSTRUCTIONS = """Score a scientific paper as a provisional, critical research AND editorial reviewer.
Evaluate the compiled PDF page text and geometry observations, not TeX source alone.
Do not reward polished unsupported science. Examine derivations and claimed results, alternative
explanations, counterexamples, citations, research limitations and reproducibility. Judge actual
support; do not infer scientific validity from author confidence or agreement of AI agents.
Evidence inventories and citations are pointers, not proof their underlying content was verified.
Give conservative credit when PDF excerpts are truncated or external material is unavailable,
and explicitly mention such limitations. Never claim a human cold read happened; reserve
full readability credit for validated cold reading.
Exactly six categories and maxima: tex_correctness 5, readability 25, sustained_answer 20,
research_rigor 30, evidence 15, visuals 5. Return integer earned scores, concrete
explanations that identify weaknesses as well as strengths, and no invented observations.
Scores reflect what is substantiated, not the ambition of the topic."""

def _make_score(judgment: PaperJudgment, sha: str) -> dict[str, Any]:
    categories: dict[str, dict[str, Any]] = {}
    for key, maximum in WEIGHTS.items():
        value = getattr(judgment, key)
        if type(value.earned) is not int or not 0 <= value.earned <= maximum:
            raise ProjectError(f"Paper score for {key} is outside its rubric maximum")
        categories[key] = {
            "earned": value.earned, "max": maximum,
            "explanation": value.explanation.strip(),
        }
    score = {
        "rubric_id": RUBRIC_ID, "rubric_version": RUBRIC_VERSION,
        "pdf_sha256": sha, "categories": categories,
        "total": sum(row["earned"] for row in categories.values()),
        "provisional": True,
    }
    assert validate_score(score, sha) is not None
    return score

def _save_score(path: str, paper_id: str, score: dict[str, Any]) -> dict[str, Any]:
    """Atomic update of the paper record with its immutable PDF unchanged."""
    from sigma import papers
    descriptor = papers._paper_version_lock(path)
    try:
        record = papers._read_one(path, paper_id)
        if record.get("project_id") != inspect_project(path).project.id:
            raise ProjectError("Paper belongs to a different project")
        if record.get("pdf_sha256") != score["pdf_sha256"] or not papers._valid_pdf_file(path, record):
            raise ProjectError("Paper PDF changed while scoring. Retry against the current version.")
        record["score"] = score
        payload = papers._json(record)
        if len(payload) > papers.MAX_PAPER_BYTES:
            raise ProjectError("Paper score exceeds the record storage limit")
        target = project_path(path)
        if target.suffix == ".json":
            from sigma.projects import save_project_artifacts
            save_project_artifacts(target, {
                f"artifacts/papers/{papers._paper_id(paper_id)}.json": payload
            })
        else:
            directory = papers._paper_dir(path, create=False)
            destination = directory / f"{papers._paper_id(paper_id)}.json"
            staged = _stage(directory, payload)
            try:
                os.replace(staged, destination)
            finally:
                staged.unlink(missing_ok=True)
        return score
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)

_tasks: dict[tuple[str, str, str, int], asyncio.Task[dict[str, Any]]] = {}
_lock = asyncio.Lock()

async def score_paper(path: str, paper_id: str, expected_binding: str,
                      expected_project_id: str) -> dict[str, Any]:
    from sigma import papers
    from sigma.openai_connection import auth_context
    from sigma.proposals import configuration

    record = papers.get_paper(path, paper_id)
    if inspect_project(path).project.id != expected_project_id:
        raise ProjectError("Project identity changed; reopen and retry")
    if not record["pdf_available"]:
        raise ProjectError("The saved paper PDF is missing or unsafe")
    previous = cached_score(record)
    if previous is not None:
        return previous

    auth = await auth_context()
    if auth["identity"] != expected_binding:
        raise ProjectError("AI connection changed; review the connection and retry")
    config = await configuration(view=inspect_project(path), context=auth)
    if not config["available"]:
        raise ProjectError(config["message"])
    sha = record["pdf_sha256"]
    key = (str(project_path(path).resolve()), paper_id, sha, RUBRIC_VERSION)
    async with _lock:
        task = _tasks.get(key)
        if task is None or task.done():
            async def evaluate() -> dict[str, Any]:
                payload = _context(record, papers.get_pdf(path, paper_id))
                result, _ = await papers._provider_structured(
                    payload, auth, config, instructions=INSTRUCTIONS,
                    schema_name="sigma_paper_score_v2", response_model=PaperJudgment,
                    max_input_bytes=180000, project_id=expected_project_id,
                    project_path_value=path,
                )
                judgment = PaperJudgment.model_validate(result)
                return _save_score(path, paper_id, _make_score(judgment, sha))
            task = asyncio.create_task(evaluate())
            _tasks[key] = task
    try:
        return await asyncio.shield(task)
    finally:
        if task.done():
            async with _lock:
                if _tasks.get(key) is task:
                    _tasks.pop(key, None)
