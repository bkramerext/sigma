"""Provider-free published-paper rollback: immutable source, durable rewind, strict auth binding."""

from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, main
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from sigma import papers
from sigma.projects import ProjectError, initialize_project, inspect_project


def saved_draft() -> dict:
    return {
        "title": "A preserved manuscript",
        "abstract": "A saved manuscript is recovered from its previously accepted version and only its typesetting is repeated. The publication is preserved.",
        "abstract_claim_ids": ["C1"],
        "problem_framing": ["The original investigation is saved as a frozen snapshot."],
        "problem_framing_claim_ids": ["C1"],
        "methods": ["We reuse the accepted draft and frozen research source."],
        "methods_claim_ids": ["C1"],
        "claims": [
            {"id": "C1", "statement": "Saved research is retained unchanged.",
             "status": "established", "evidence_refs": ["project:placeholder"],
             "reasoning": "This unit test asserts a saved artifact remains intact."}
        ],
        "sections": [{"heading": "Saved evidence", "paragraphs": ["The draft is unchanged."], "claim_ids": ["C1"]}],
        "limitations": ["Further independent review is required."],
        "open_obligations": [],
        "conclusions": ["The saved publication is not edited."],
        "conclusion_claim_ids": ["C1"],
        "validation_warnings": [],
    }


class PaperRollbackTests(TestCase):
    def setUp(self) -> None:
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path = str(Path(temp.name) / "topic.sigma")
        initialize_project(Path(self.path), "Source paper", "What was preserved?")
        self.project_id = inspect_project(self.path).project.id
        self.snapshot, self.digest = papers._snapshot(self.path)
        self.source_id = uuid4().hex
        self.pdf_sha = hashlib.sha256(b"%PDF-1.4 verified publication").hexdigest()
        self.draft = papers.PaperDraft.model_validate(saved_draft()).model_dump()
        self.record = {
            "paper_id": self.source_id,
            "paper_version": 1,
            "project_id": self.project_id,
            "pdf_available": True,
            "pdf_sha256": self.pdf_sha,
            "snapshot_sha256": self.digest,
            "snapshot": self.snapshot,
            "draft": self.draft,
            "validation_warnings": [],
            "generation": {"long_form": False, "include_diagrams": False},
        }
        self.auth = {"mode": "api_key", "identity": "test-binding"}
        self.config = {"available": True, "model": "gpt-6-luna", "reasoning_effort": "medium"}

    def run_rollback(self, stage: str = "proofreading", pdf: str | None = None):
        return asyncio.run(
            papers.stage_saved_paper_rollback(
                self.path, self.source_id, self.project_id,
                self.auth["identity"], pdf or self.pdf_sha, stage=stage,
            )
        )

    def patched_sources(self):
        from contextlib import ExitStack

        stack = ExitStack()
        stack.enter_context(patch.object(papers, "get_paper", return_value=self.record))
        stack.enter_context(patch.object(papers, "get_pdf", return_value=b"%PDF-1.4 verified publication"))
        stack.enter_context(patch.object(papers, "auth_context", new=AsyncMock(return_value=self.auth)))
        stack.enter_context(patch.object(papers, "configuration", new=AsyncMock(return_value=self.config)))
        return stack

    def test_staged_proofreading_is_durable_and_source_immutable(self) -> None:
        original = json.dumps(self.record, sort_keys=True)
        with self.patched_sources(), papers.paper_run_scope(uuid4().hex, number=2):
            preview = papers.rollback_available(self.path, self.source_id)
            self.assertEqual(preview["stages"], ["proofreading"])
            result = self.run_rollback()
            self.assertTrue(result["staged"])
            self.assertEqual(result["paper_version"], 2)
            checkpoint = papers._load_work(self.path)
            self.assertIsNotNone(checkpoint)
            assert checkpoint is not None
            self.assertEqual(checkpoint["validated_draft"], self.draft)
            self.assertEqual(checkpoint["snapshot_sha256"], self.digest)
            self.assertEqual(checkpoint["rollback_origin"]["paper_id"], self.source_id)
            self.assertNotIn("proofread_ready", checkpoint)
            self.assertEqual(checkpoint["provider_calls"], 0)
            self.assertEqual(checkpoint["kind"], "one_shot")
            self.assertEqual(checkpoint["include_diagrams"], False)
        self.assertEqual(json.dumps(self.record, sort_keys=True), original)

    def test_stale_pdf_and_missing_boundary_fail_closed(self) -> None:
        with self.patched_sources():
            for action in (
                lambda: self.run_rollback(pdf="0" * 64),
                lambda: self.run_rollback(stage="writing"),
            ):
                with self.assertRaises(ProjectError):
                    action()
            self.assertIsNone(papers._load_work(self.path))

    def test_existing_draft_not_overwritten_and_runs_are_isolated(self) -> None:
        run_a, run_b = uuid4().hex, uuid4().hex
        with self.patched_sources():
            with papers.paper_run_scope(run_a):
                self.run_rollback()
                checkpoint = papers._load_work(self.path)
                self.assertTrue(self.run_rollback()["staged"])  # idempotent retried request
                with self.assertRaisesRegex(ProjectError, "unfinished paper"):
                    self.run_rollback(pdf="f" * 64)
            with papers.paper_run_scope(run_b):
                self.assertIsNone(papers._load_work(self.path))
                self.run_rollback()
                self.assertIsNotNone(papers._load_work(self.path))
            with papers.paper_run_scope(run_a):
                self.assertEqual(papers._load_work(self.path), checkpoint)

    def test_invalid_frozen_evidence_is_not_offered(self) -> None:
        with self.patched_sources():
            self.record["snapshot_sha256"] = "0" * 64
            self.assertEqual(papers.rollback_available(self.path, self.source_id)["stages"], [])
            with self.assertRaises(ProjectError):
                self.run_rollback()


if __name__ == "__main__":
    main()
