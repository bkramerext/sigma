"""Provider-free checks for immutable Paper restart from saved publication boundaries."""

from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, main
from uuid import uuid4

from sigma import paper_rewind, papers
from sigma.projects import ProjectError, initialize_project


class SavedPaperRewindTests(TestCase):
    def setUp(self) -> None:
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.path = str(Path(temporary.name) / "rewind.sigma")
        self.view = initialize_project(
            self.path, "Checkpoint test", "What can an immutable manuscript prove?"
        )
        package, digest = papers._snapshot(self.path)
        self.paper_id = uuid4().hex
        ref = package["sources"][0]["id"]
        draft = papers.PaperDraft.model_validate(
            {
                "title": "A published test manuscript",
                "abstract": "This paper reports a bounded test.",
                "abstract_claim_ids": ["C1"],
                "problem_framing": ["The question is bounded."],
                "problem_framing_claim_ids": ["C1"],
                "methods": ["Inspect the frozen evidence."],
                "methods_claim_ids": ["C1"],
                "claims": [
                    {
                        "id": "C1",
                        "statement": "The source has a research question.",
                        "status": "established",
                        "evidence_refs": [ref],
                        "reasoning": "The question is in the evidence.",
                    }
                ],
                "sections": [
                    {"heading": "Finding", "paragraphs": ["Test output"], "claim_ids": ["C1"]}
                ],
                "limitations": ["This is only a fixture."],
                "open_obligations": [],
                "conclusions": ["The source is saved."],
                "conclusion_claim_ids": ["C1"],
                "validation_warnings": [],
            }
        )
        original = {
            "schema_version": 1,
            "paper_id": self.paper_id,
            "project_id": self.view.project.id,
            "created_at": papers._now(),
            "snapshot_sha256": digest,
            "snapshot": package,
            "draft": draft.model_dump(),
            "validation_warnings": [],
            "generation": {"long_form": True, "include_diagrams": False},
        }
        pdf = (Path(__file__).parent / "fixtures/sigma-valid-sample-paper.pdf").read_bytes()
        papers._save(self.path, original, pdf)
        self.pdf = pdf
        self.record_bytes = (
            Path(self.path) / "artifacts/papers" / f"{self.paper_id}.json"
        ).read_bytes()
        self.binding = {"identity": "fixture-account", "mode": "api_key"}
        self.config = {
            "available": True,
            "model": "gpt-6-luna",
            "reasoning_effort": "medium",
        }

    def _new(self, stage: str, *, source_hash: str | None = None) -> dict:
        return asyncio.run(
            paper_rewind.create(
                self.path,
                self.paper_id,
                self.view.project.id,
                source_hash or hashlib.sha256(self.pdf).hexdigest(),
                stage,
                auth=self.binding,
                config=self.config,
            )
        )

    def test_typesetting_uses_frozen_evidence_and_validated_manuscript(self) -> None:
        options = paper_rewind.describe(self.path, self.paper_id, self.view.project.id)
        self.assertEqual([option["id"] for option in options["stages"]], ["typesetting", "writing"])
        with papers.paper_run_scope(uuid4().hex):
            first = self._new("typesetting")
            self.assertTrue(first["created"])
            saved = papers._load_work(self.path)
            self.assertIsNotNone(saved)
            assert saved is not None
            self.assertIn("validated_draft", saved)
            self.assertEqual(saved["provider_calls"], 0)
            self.assertEqual(saved["snapshot_sha256"], options["snapshot_sha256"])
            self.assertEqual(saved["rewind_origin"]["paper_id"], self.paper_id)
            self.assertFalse(saved["include_diagrams"])
            second = self._new("typesetting")
            self.assertFalse(second["created"])
            self.assertEqual(papers._load_work(self.path)["validated_draft"], saved["validated_draft"])
        self.assertEqual(
            (Path(self.path) / "artifacts/papers" / f"{self.paper_id}.json").read_bytes(),
            self.record_bytes,
        )
        self.assertEqual(papers.get_pdf(self.path, self.paper_id), self.pdf)

    def test_writing_restart_cannot_mutate_published_paper(self) -> None:
        with papers.paper_run_scope(uuid4().hex):
            self._new("writing")
            work = papers._load_work(self.path)
            self.assertIsNotNone(work)
            assert work is not None
            self.assertNotIn("validated_draft", work)
            self.assertEqual(work["rewind_origin"]["stage"], "writing")
            with self.assertRaisesRegex(ProjectError, "already has unfinished"):
                self._new("typesetting")
        self.assertEqual(
            (Path(self.path) / "artifacts/papers" / f"{self.paper_id}.json").read_bytes(),
            self.record_bytes,
        )

    def test_stale_source_and_invalid_stage_fail_without_new_work(self) -> None:
        with papers.paper_run_scope(uuid4().hex):
            with self.assertRaisesRegex(ProjectError, "changed"):
                self._new("typesetting", source_hash="f" * 64)
            with self.assertRaisesRegex(ProjectError, "Unknown"):
                self._new("not-a-stage")
            self.assertIsNone(papers._load_work(self.path))

    def test_rewind_runs_are_isolated(self) -> None:
        first = uuid4().hex
        second = uuid4().hex
        with papers.paper_run_scope(first):
            self._new("typesetting")
        with papers.paper_run_scope(second):
            self._new("writing")
            self.assertEqual(papers._load_work(self.path)["rewind_origin"]["stage"], "writing")
        with papers.paper_run_scope(first):
            self.assertEqual(papers._load_work(self.path)["rewind_origin"]["stage"], "typesetting")


if __name__ == "__main__":
    main()
