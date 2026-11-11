"""Restart an immutable published Paper from an actual saved authoring boundary.

A published paper is never reopened for mutation. Its verified frozen research
snapshot (and optionally validated manuscript) seeds a distinct durable attempt.
No provider call is made by this module; Play must be explicit.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any
from uuid import uuid4

from sigma.openai_connection import AuthContext

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
                "id": "typesetting",
                "label": "Validated manuscript",
                "description": "Keep the saved manuscript; rerun validation, TeX, proofreading and PDF generation.",
            },
            {
                "id": "writing",
                "label": "Writing",
                "description": "Reuse the original research evidence; write a new manuscript and rebuild the PDF.",
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
    auth: AuthContext,
    config: dict[str, Any],
) -> dict[str, Any]:
    """Seed the current (newly reserved) run; source publication stays immutable."""
    if stage not in {"typesetting", "writing"}:
        raise ProjectError("Unknown Paper restart checkpoint.")
    if not config.get("available"):
        raise ProjectError(config.get("message") or "AI provider unavailable.")
    async with papers._paper_operation(path, generating=False):
        source = source_checkpoint(path, paper_id, project_id)
        paper = source["paper"]
        if paper["pdf_sha256"] != source_pdf_sha256:
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
            raise ProjectError("This project has reached the saved Paper version limit.")
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
        if stage == "typesetting":
            work["validated_draft"] = source["draft"].model_dump()
            work["validated_warnings"] = list(paper.get("validation_warnings", []))
        now = papers._now()
        work["progress"] = {
            "run_id": papers._paper_run_id.get() or uuid4().hex,
            "status": "paused",
            "stage": "validation" if stage == "typesetting" else "writing",
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
            raise ProjectError("Restart checkpoint was not durably saved.")
        return {
            "created": True,
            "snapshot_sha256": work["snapshot_sha256"],
            "source_paper_id": paper_id,
            "stage": stage,
        }
