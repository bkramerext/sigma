"""Restart an immutable published Paper from an actual saved authoring boundary.

A published paper is never reopened for mutation. Its verified frozen research
snapshot (and optionally validated manuscript) seeds a distinct durable attempt.
No provider call is made by this module; Play must be explicit.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from typing import Any
from uuid import uuid4

from sigma import papers
from sigma.projects import ProjectError, inspect_project


def source_checkpoint(path: str, paper_id: str, project_id: str) -> dict[str, Any]:
    """Fail closed on missing/altered evidence, PDF, or unusable manuscript."""
    view = inspect_project(path)
    if view.project.id != project_id:
        raise ProjectError("Project changed; reopen the Paper before restarting.")
    paper = papers.get_paper(path, paper_id, include_tex=False)
    if paper.get("project_id") != project_id:
        raise ProjectError("Paper belongs to a different project.")
    if not re.fullmatch(r"[0-9a-f]{64}", str(paper.get("snapshot_sha256", ""))):
        raise ProjectError("Published Paper has no verified evidence fingerprint.")
    if not paper.get("pdf_available"):
        raise ProjectError("Published Paper PDF is unavailable.")
    pdf = papers.get_pdf(path, paper_id)
    if hashlib.sha256(pdf).hexdigest() != paper["pdf_sha256"]:
        raise ProjectError("Published Paper PDF checksum changed.")
    frozen = paper.get("snapshot")
    if not isinstance(frozen, dict):
        raise ProjectError(
            "This Paper predates frozen evidence archives and cannot be restarted safely."
        )
    frozen, digest = papers._validate_frozen_snapshot(frozen, project_id)
    if digest != paper["snapshot_sha256"]:
        raise ProjectError("Published Paper evidence checksum changed.")
    manuscript = papers.PaperDraft.model_validate(paper["draft"])
    generation = paper.get("generation")
    if not isinstance(generation, dict):
        raise ProjectError("Published Paper generation history is missing.")
    return {
        "paper": paper,
        "snapshot": frozen,
        "draft": manuscript,
        "generation": generation,
    }


def describe(path: str, paper_id: str, project_id: str) -> dict[str, Any]:
    source = source_checkpoint(path, paper_id, project_id)
    paper = source["paper"]
    return {
        "paper_id": paper_id,
        "paper_version": paper["paper_version"],
        "source_pdf_sha256": paper["pdf_sha256"],
        "snapshot_sha256": paper["snapshot_sha256"],
        "stages": [
            {
                "id": "started",
                "label": "Started",
                "description": "Restart from the beginning using the verified frozen evidence; rerun review, evidence extraction, writing and publication.",
            },
            {
                "id": "writing",
                "label": "Write sections",
                "description": "Reuse frozen evidence to author a new manuscript and rebuild the PDF.",
            },
            {
                "id": "validation",
                "label": "Validate",
                "description": "Recheck the archived manuscript against frozen evidence, then proofread and rebuild the PDF.",
            },
            {
                "id": "typesetting",
                "label": "Proofread",
                "description": "Keep the validated manuscript and redo proofreading, PDF generation and scoring.",
            },
        ],
        "include_diagrams": source["generation"].get("include_diagrams", True),
    }


async def create(
    path: str,
    paper_id: str,
    project_id: str,
    source_pdf_sha256: str,
    stage: str,
    *,
    auth: Mapping[str, Any],
    config: dict[str, Any],
    expected_snapshot_sha256: str | None = None,
) -> dict[str, Any]:
    """Seed the current (newly reserved) run; source publication stays immutable."""
    if stage not in {"started", "writing", "validation", "typesetting"}:
        raise ProjectError("Unknown Paper restart checkpoint.")
    if not config.get("available"):
        raise ProjectError(config.get("message") or "AI provider unavailable.")
    async with papers._paper_operation(path, generating=False):
        source = source_checkpoint(path, paper_id, project_id)
        paper = source["paper"]
        if paper["pdf_sha256"] != source_pdf_sha256 or (
            expected_snapshot_sha256 is not None
            and paper["snapshot_sha256"] != expected_snapshot_sha256
        ):
            raise ProjectError("Published Paper changed; reopen before restarting.")
        origin = {
            "paper_id": paper_id,
            "paper_version": paper["paper_version"],
            "stage": stage,
            "pdf_sha256": source_pdf_sha256,
        }
        existing = papers._load_work(path)
        if existing is not None:
            if existing.get("rewind_origin") == origin:
                return {
                    "created": False,
                    "snapshot_sha256": existing["snapshot_sha256"],
                    "source_paper_id": paper_id,
                    "stage": stage,
                }
            raise ProjectError(
                "This run already has unfinished Paper work; use Resume or Start over."
            )
        if papers._read_reset_ledger(path) is not None:
            raise ProjectError("An unfinished Paper reset must be resolved before restarting.")
        if papers._read_queue_status(path) is not None:
            raise ProjectError("A Paper is queued or interrupted; resolve it before restarting.")
        if len(papers.list_papers(path)) >= papers.MAX_PAPERS:
            raise ProjectError("This project has reached the Paper version limit.")
        fingerprint = hashlib.sha256((auth["mode"] + "\0" + auth["identity"]).encode()).hexdigest()
        long_form = source["generation"].get("long_form") is True
        work = papers._new_work(
            paper["snapshot_sha256"],
            project_id,
            fingerprint,
            config["model"],
            config["reasoning_effort"],
            kind="long_form" if long_form else "one_shot",
        )
        work["frozen_package"] = source["snapshot"]
        work["include_diagrams"] = bool(source["generation"].get("include_diagrams", True))
        work["rewind_origin"] = origin
        if stage != "started":
            # Earlier editorial work belongs to this immutable publication.
            # Reuse its actual saved guidance/checklist when still valid.
            # Otherwise the compiler's normal fingerprint check fails closed.
            previous_guidance = source["generation"].get("writing_sources")
            if (
                isinstance(previous_guidance, list)
                and len(previous_guidance) <= 3
                and all(
                    isinstance(item, dict)
                    and all(isinstance(item.get(key), str) for key in ("url", "excerpt", "sha256"))
                    for item in previous_guidance
                )
            ):
                work["writing_sources"] = previous_guidance
                choice = source["generation"].get("writing_source_selection")
                if isinstance(choice, str):
                    work["writing_source_selection"] = choice
            previous_compilation = source["generation"].get("publication_compilation")
            if (
                isinstance(previous_compilation, dict)
                and isinstance(previous_compilation.get("fingerprint"), str)
                and papers.publication_reference_compiler.validate(
                    previous_compilation, previous_compilation["fingerprint"]
                )
            ):
                work["publication_compilation"] = previous_compilation
        if stage in {"validation", "typesetting"}:
            # This is an archived, checksum-verified manuscript, not an AI
            # dispatch replay. Validation may be repeated deterministically.
            work["validated_draft"] = source["draft"].model_dump()
            work["validated_warnings"] = list(paper.get("validation_warnings", []))
        if stage == "validation":
            work["rewind_validation_done"] = False
        now = papers._now()
        work["progress"] = {
            "run_id": papers._paper_run_id.get() or uuid4().hex,
            "status": "paused",
            "stage": {
                "started": "queued",
                "writing": "writing",
                "validation": "validation",
                "typesetting": "proofreading",
            }[stage],
            "current": None,
            "total": None,
            "started_at": now,
            "updated_at": now,
            "elapsed_seconds": 0,
            "detail": f"Restored from Paper {paper['paper_version']} · ready to resume",
        }
        papers._save_work(path, work)
        # Re-read the durable checkpoint so a request cannot claim success with
        # a truncated or non-resumable manuscript.
        checked = papers._load_work(path)
        if checked is None or checked.get("rewind_origin") != origin:
            raise ProjectError("Restart checkpoint is unavailable.")
        return {
            "created": True,
            "snapshot_sha256": work["snapshot_sha256"],
            "source_paper_id": paper_id,
            "stage": stage,
        }
