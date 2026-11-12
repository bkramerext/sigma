"""Provider-free checks for immutable Paper restart from saved publication boundaries."""

from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, main
from unittest.mock import patch
from uuid import uuid4

from sigma import api, paper_rewind, papers
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
                "abstract": "This paper records a bounded, fixture-only investigation of the saved evidence, avoiding any assertion that its conclusions constitute independent verification.",
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
            "generation": {
                "long_form": True,
                "include_diagrams": False,
                "writing_sources": [
                    {
                        "url": "https://example.org/publication-standards",
                        "excerpt": "Fixture editorial standards.",
                        "sha256": "a" * 64,
                        "title": "Fixture standards",
                    }
                ],
                "writing_source_selection": "saved-publication",
            },
        }
        pdf = (Path(__file__).parent / "fixtures/sigma-valid-sample-paper.pdf").read_bytes()
        papers._save(self.path, original, pdf)
        self.pdf = pdf
        self.record_bytes = (
            papers._paper_dir(self.path, create=False) / f"{self.paper_id}.json"
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

    def test_api_accepts_real_validation_restart_stage(self) -> None:
        request = api.PaperRewindRequest(
            path=self.path,
            expected_project_id=self.view.project.id,
            expected_binding=self.binding["identity"],
            source_pdf_sha256=hashlib.sha256(self.pdf).hexdigest(),
            expected_snapshot_sha256=papers._snapshot(self.path)[1],
            stage="validation",
            confirm_restart=True,
            run_id=uuid4().hex,
        )
        self.assertEqual(request.stage, "validation")

    def test_typesetting_uses_frozen_evidence_and_validated_manuscript(self) -> None:
        options = paper_rewind.describe(self.path, self.paper_id, self.view.project.id)
        self.assertEqual(
            [option["id"] for option in options["stages"]],
            ["started", "writing", "validation", "typesetting"],
        )
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
            self.assertEqual(saved["writing_source_selection"], "saved-publication")
            self.assertEqual(saved["writing_sources"][0]["excerpt"], "Fixture editorial standards.")
            self.assertEqual(saved["progress"]["status"], "paused")
            self.assertIn("ready to resume", saved["progress"]["detail"])
            self.assertEqual(saved["progress"]["stage"], "proofreading")
            progress = papers.progress_status(self.path)
            self.assertIsNotNone(progress)
            assert progress is not None
            self.assertEqual(progress["status"], "interrupted")
            second = self._new("typesetting")
            self.assertFalse(second["created"])
            next_work = papers._load_work(self.path)
            self.assertIsNotNone(next_work)
            assert next_work is not None
            self.assertEqual(next_work["validated_draft"], saved["validated_draft"])
        self.assertEqual(
            (papers._paper_dir(self.path, create=False) / f"{self.paper_id}.json").read_bytes(),
            self.record_bytes,
        )
        self.assertEqual(papers.get_pdf(self.path, self.paper_id), self.pdf)

    def test_started_restart_reuses_frozen_evidence_without_downstream_work(self) -> None:
        with papers.paper_run_scope(uuid4().hex):
            result = self._new("started")
            self.assertTrue(result["created"])
            work = papers._load_work(self.path)
            self.assertIsNotNone(work)
            assert work is not None
            self.assertEqual(work["rewind_origin"]["stage"], "started")
            self.assertEqual(work["snapshot_sha256"], papers._snapshot(self.path)[1])
            self.assertIn("frozen_package", work)
            self.assertEqual(work["progress"]["stage"], "queued")
            self.assertEqual(work["progress"]["status"], "paused")
            admitted = papers.preflight(
                self.path,
                expected_project_id=self.view.project.id,
                expected_binding=self.binding["identity"],
                mode=self.binding["mode"],
                model=self.config["model"],
                reasoning_effort=self.config["reasoning_effort"],
            )
            self.assertTrue(admitted["resume_available"], admitted)
            self.assertNotIn("validated_draft", work)
            self.assertNotIn("plan", work)
            self.assertEqual(work["evidence_notes"], [])
            self.assertEqual(work["provider_calls"], 0)
        self.assertEqual(
            (papers._paper_dir(self.path, create=False) / f"{self.paper_id}.json").read_bytes(),
            self.record_bytes,
        )
        self.assertEqual(papers.get_pdf(self.path, self.paper_id), self.pdf)

    def test_validation_restart_rechecks_draft_without_ai_dispatch(self) -> None:
        with papers.paper_run_scope(uuid4().hex):
            result = self._new("validation")
            self.assertTrue(result["created"])
            work = papers._load_work(self.path)
            self.assertIsNotNone(work)
            assert work is not None
            self.assertEqual(work["progress"]["stage"], "validation")
            self.assertFalse(work["rewind_validation_done"])
            self.assertEqual(work["provider_calls"], 0)
            self.assertNotIn("proofread_ready", work)
            original = work["validated_draft"]
            checked, warnings = papers._revalidate_rewind_manuscript(work, work["frozen_package"])
            self.assertTrue(work["rewind_validation_done"])
            self.assertEqual(checked.model_dump(), original)
            self.assertEqual(work["validated_warnings"], warnings)
            self.assertEqual(work["provider_calls"], 0)
            self.assertNotIn("proofread_ready", work)
            papers._save_work(self.path, work)
            recovered = papers._load_work(self.path)
            self.assertIsNotNone(recovered)
            assert recovered is not None
            self.assertTrue(recovered["rewind_validation_done"])
            with self.assertRaisesRegex(ProjectError, "unavailable"):
                papers._revalidate_rewind_manuscript(work, work["frozen_package"])
        self.assertEqual(
            (papers._paper_dir(self.path, create=False) / f"{self.paper_id}.json").read_bytes(),
            self.record_bytes,
        )

    def test_invalid_restart_validation_marker_is_rejected(self) -> None:
        with papers.paper_run_scope(uuid4().hex):
            self._new("validation")
            work = papers._load_work(self.path)
            self.assertIsNotNone(work)
            assert work is not None
            work["rewind_validation_done"] = "true"
            papers._save_work(self.path, work)
            with self.assertRaisesRegex(ProjectError, "validation marker"):
                papers._load_work(self.path)

    def test_writing_restart_cannot_mutate_published_paper(self) -> None:
        with papers.paper_run_scope(uuid4().hex):
            self._new("writing")
            work = papers._load_work(self.path)
            self.assertIsNotNone(work)
            assert work is not None
            self.assertNotIn("validated_draft", work)
            self.assertEqual(work["rewind_origin"]["stage"], "writing")
            admitted = papers.preflight(
                self.path,
                expected_project_id=self.view.project.id,
                expected_binding=self.binding["identity"],
                mode=self.binding["mode"],
                model=self.config["model"],
                reasoning_effort=self.config["reasoning_effort"],
            )
            self.assertTrue(admitted["resume_available"], admitted)
            self.assertTrue(admitted["checkpoint_exists"], admitted)
            with self.assertRaisesRegex(ProjectError, "already has unfinished"):
                self._new("typesetting")
        self.assertEqual(
            (papers._paper_dir(self.path, create=False) / f"{self.paper_id}.json").read_bytes(),
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
            loaded = papers._load_work(self.path)
            self.assertIsNotNone(loaded)
            assert loaded is not None
            self.assertEqual(loaded["rewind_origin"]["stage"], "writing")
        with papers.paper_run_scope(first):
            loaded = papers._load_work(self.path)
            self.assertIsNotNone(loaded)
            assert loaded is not None
            self.assertEqual(loaded["rewind_origin"]["stage"], "typesetting")

    def _stopped_long_form(self, run_id: str) -> tuple[dict, dict]:
        paper = papers.get_paper(self.path, self.paper_id, include_tex=False)
        package, digest = papers._snapshot(self.path)
        ref = package["sources"][0]["id"]
        plan = {
            **paper["draft"],
            "sections": [
                {
                    "heading": "Finding",
                    "purpose": "Explain the frozen source and its bounded result.",
                    "evidence_refs": [ref],
                    "claim_ids": ["C1"],
                }
            ],
        }
        papers.LongPaperPlan.model_validate(plan)
        work = papers._new_work(
            digest,
            self.view.project.id,
            "f" * 64,
            self.config["model"],
            self.config["reasoning_effort"],
            kind="long_form",
            provider_calls_total=4,
        )
        work.update(
            {
                "frozen_package": package,
                "writing_sources": [],
                "evidence_indexed": True,
                "evidence_strategy": "structured_v1",
                "plan": plan,
                "validated_draft": paper["draft"],
                "validated_warnings": [],
                "provider_calls": 4,
                "progress": {
                    "run_id": run_id,
                    "status": "paused",
                    "stage": "proofreading",
                    "current": None,
                    "total": None,
                    "started_at": papers._now(),
                    "updated_at": papers._now(),
                    "elapsed_seconds": 100,
                    "detail": "Stopped before proofreading",
                },
            }
        )
        papers._save_work(self.path, work)
        return package, work

    def test_unfinished_stages_are_gated_by_real_checkpoints(self) -> None:
        run_id = uuid4().hex
        with papers.paper_run_scope(run_id):
            _package, work = self._stopped_long_form(run_id)
            options = papers.unfinished_restart_options(self.path)
            self.assertEqual(
                options["stages"],
                [
                    "started",
                    "review",
                    "evidence",
                    "planning",
                    "writing",
                    "validation",
                    "typesetting",
                ],
            )
            self.assertEqual(options["resume_stage"], "proofreading")
            self.assertNotIn("pdf", options["stages"])
            with self.assertRaisesRegex(ProjectError, "verified checkpoint"):
                asyncio.run(
                    papers.restart_unfinished_step(
                        self.path,
                        self.view.project.id,
                        work["snapshot_sha256"],
                        "pdf",
                    )
                )
            persisted = papers._load_work(self.path)
            assert persisted is not None
            self.assertEqual(persisted["provider_calls"], 4)

    def test_active_checkpoint_inspection_is_read_only(self) -> None:
        run_id = uuid4().hex
        with papers.paper_run_scope(run_id):
            _package, work = self._stopped_long_form(run_id)
            before = papers._load_work(self.path)
            with patch.object(
                papers,
                "progress_status",
                return_value={"status": "active", "stage": "proofreading"},
            ):
                with self.assertRaisesRegex(ProjectError, "Stop this Paper"):
                    papers.unfinished_restart_options(self.path)
                available = papers.unfinished_restart_options(self.path, allow_active=True)
                self.assertIn("validation", available["stages"])
                with self.assertRaisesRegex(ProjectError, "Stop this Paper"):
                    asyncio.run(
                        papers.restart_unfinished_step(
                            self.path, self.view.project.id, work["snapshot_sha256"], "validation"
                        )
                    )
            self.assertEqual(papers._load_work(self.path), before)

    def test_unfinished_writing_restart_preserves_plan_and_paid_call_history(self) -> None:
        run_id = uuid4().hex
        with papers.paper_run_scope(run_id):
            _package, work = self._stopped_long_form(run_id)
            result = asyncio.run(
                papers.restart_unfinished_step(
                    self.path, self.view.project.id, work["snapshot_sha256"], "writing"
                )
            )
            self.assertEqual(result["stage"], "writing")
            next_work = papers._load_work(self.path)
            self.assertIsNotNone(next_work)
            assert next_work is not None
            self.assertEqual(next_work["plan"], work["plan"])
            self.assertNotIn("validated_draft", next_work)
            self.assertNotIn("proofread_ready", next_work)
            self.assertEqual(next_work["provider_calls"], 0)
            self.assertEqual(next_work["provider_calls_total"], 4)
            self.assertEqual(next_work["prior_runs"][-1]["provider_calls_attempted"], 4)
            self.assertEqual(result["progress"]["stage"], "writing")
            self.assertEqual(result["progress"]["status"], "interrupted")
        self.assertEqual(papers.get_pdf(self.path, self.paper_id), self.pdf)

    def test_unfinished_validation_restart_rechecks_without_paid_call(self) -> None:
        run_id = uuid4().hex
        with papers.paper_run_scope(run_id):
            package, work = self._stopped_long_form(run_id)
            result = asyncio.run(
                papers.restart_unfinished_step(
                    self.path, self.view.project.id, work["snapshot_sha256"], "validation"
                )
            )
            self.assertEqual(result["stage"], "validation")
            next_work = papers._load_work(self.path)
            self.assertIsNotNone(next_work)
            assert next_work is not None
            self.assertTrue(next_work["checkpoint_revalidate_pending"])
            self.assertIn("validated_draft", next_work)
            checked, warnings = papers._revalidate_rewind_manuscript(next_work, package)
            self.assertFalse(next_work["checkpoint_revalidate_pending"])
            self.assertEqual(next_work["provider_calls"], 0)
            self.assertEqual(next_work["validated_warnings"], warnings)
            self.assertEqual(checked.model_dump(), next_work["validated_draft"])

    def test_unfinished_restart_replayed_request_is_idempotent(self) -> None:
        run_id = uuid4().hex
        request_id = uuid4().hex
        with papers.paper_run_scope(run_id):
            _package, work = self._stopped_long_form(run_id)
            first = asyncio.run(
                papers.restart_unfinished_step(
                    self.path,
                    self.view.project.id,
                    work["snapshot_sha256"],
                    "writing",
                    request_id=request_id,
                )
            )
            restored = papers._load_work(self.path)
            self.assertIsNotNone(restored)
            assert restored is not None
            second = asyncio.run(
                papers.restart_unfinished_step(
                    self.path,
                    self.view.project.id,
                    work["snapshot_sha256"],
                    "writing",
                    request_id=request_id,
                )
            )
            self.assertFalse(second["created"])
            with self.assertRaisesRegex(ProjectError, "different step"):
                asyncio.run(
                    papers.restart_unfinished_step(
                        self.path,
                        self.view.project.id,
                        work["snapshot_sha256"],
                        "validation",
                        request_id=request_id,
                    )
                )
            self.assertEqual(first["snapshot_sha256"], second["snapshot_sha256"])
            persisted = papers._load_work(self.path)
            assert persisted is not None
            self.assertEqual(persisted["prior_runs"], restored["prior_runs"])

    def test_restart_history_remains_bounded_after_many_attempts(self) -> None:
        run_id = uuid4().hex
        with papers.paper_run_scope(run_id):
            _, work = self._stopped_long_form(run_id)
            work["prior_runs"] = [
                {
                    "provider_calls_attempted": 1,
                    "snapshot_sha256": work["snapshot_sha256"],
                    "model": work["model"],
                    "reset_at": papers._now(),
                }
                for _ in range(100)
            ]
            papers._save_work(self.path, work)
            result = asyncio.run(
                papers.restart_unfinished_step(
                    self.path, self.view.project.id, work["snapshot_sha256"], "writing"
                )
            )
            self.assertEqual(result["stage"], "writing")
            saved = papers._load_work(self.path)
            assert saved is not None
            self.assertEqual(len(saved["prior_runs"]), 100)
            self.assertEqual(saved["prior_runs"][-1]["provider_calls_attempted"], 4)
            self.assertEqual(saved["provider_calls_total"], 4)

    def test_unfinished_proofreading_restart_clears_later_outputs(self) -> None:
        run_id = uuid4().hex
        with papers.paper_run_scope(run_id):
            _package, work = self._stopped_long_form(run_id)
            with self.assertRaisesRegex(ProjectError, "changed"):
                asyncio.run(
                    papers.restart_unfinished_step(
                        self.path, self.view.project.id, "a" * 64, "typesetting"
                    )
                )
            result = asyncio.run(
                papers.restart_unfinished_step(
                    self.path, self.view.project.id, work["snapshot_sha256"], "typesetting"
                )
            )
            next_work = papers._load_work(self.path)
            assert next_work is not None
            self.assertIn("validated_draft", next_work)
            self.assertNotIn("checkpoint_revalidate_pending", next_work)
            self.assertNotIn("proofread_ready", next_work)
            self.assertEqual(result["progress"]["stage"], "proofreading")
            self.assertEqual(papers.get_pdf(self.path, self.paper_id), self.pdf)


if __name__ == "__main__":
    main()
