"""Provider-free tests of independent Paper run storage, admission and control."""

from __future__ import annotations

import asyncio
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, cast
from unittest import TestCase, main
from unittest.mock import patch
from uuid import uuid4

from sigma import papers
from sigma.projects import ProjectError


def present(value: dict[str, Any] | None) -> dict[str, Any]:
    if value is None:
        raise AssertionError("Expected persisted Paper state")
    return value


class PaperRunIsolationTests(TestCase):
    def setUp(self) -> None:
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.project = Path(temporary.name) / "research.sigma"
        self.project.mkdir()
        self.path = str(self.project)
        self.first = uuid4().hex
        self.second = uuid4().hex

    @staticmethod
    def saved_work(model: str) -> dict:
        return papers._new_work("a" * 64, "test-project", "b" * 64, model, "high")

    def test_independent_checkpoints_and_legacy_recovery(self) -> None:
        papers._save_work(self.path, self.saved_work("legacy"))
        legacy_file = papers._work_file(self.path, create=False)
        self.assertTrue(legacy_file.is_file())

        for run_id, model in ((self.first, "first"), (self.second, "second")):
            with papers.paper_run_scope(run_id):
                self.assertIsNone(papers._load_work(self.path))
                self.assertIsNone(papers._read_queue_status(self.path))
                papers._save_work(self.path, self.saved_work(model))
                papers._write_queue_status(self.path, "queued", papers._now())
                self.assertEqual(present(papers._load_work(self.path))["model"], model)
                self.assertEqual(present(papers._read_queue_status(self.path))["status"], "queued")
                self.assertEqual(papers._work_file(self.path, create=False).parent.name, run_id)

        # Reopening a scope after all task state is gone recovers the same work.
        with papers.paper_run_scope(self.first):
            self.assertEqual(present(papers._load_work(self.path))["model"], "first")
            papers._clear_work(self.path)
            papers._clear_queue_status(self.path)
        with papers.paper_run_scope(self.second):
            self.assertEqual(present(papers._load_work(self.path))["model"], "second")
            self.assertEqual(present(papers._read_queue_status(self.path))["status"], "queued")
        self.assertEqual(present(papers._load_work(self.path))["model"], "legacy")
        self.assertEqual(papers._work_file(self.path, create=False), legacy_file)
        self.assertTrue(legacy_file.is_file())

    def test_resumed_collaborator_keeps_original_creator(self) -> None:
        with (
            papers.paper_run_scope(self.first, number=12),
            patch.object(
                papers.project_collaboration, "execution_run",
                return_value={"number": 12, "creator_email": "original@example.test"},
            ),
            patch.object(
                papers.project_collaboration, "collaborator_identity",
                return_value="executor@example.test",
            ),
        ):
            self.assertEqual(papers._paper_original_creator(self.path), "original@example.test")

    def test_published_checkpoint_returns_scoring_as_resume_stage(self) -> None:
        paper_id = uuid4().hex
        work = self.saved_work("fixture")
        work["published_paper_id"] = paper_id
        self.assertEqual(papers._unfinished_resume_stage(work), "scoring")

    def test_published_creator_recovery_preserves_pdf_and_rejects_wrong_run(self) -> None:
        paper_id = uuid4().hex
        creator = "original@example.test"
        executor = "executor@example.test"
        pdf = b"%PDF-1.4\nfixture\n"
        with papers.paper_run_scope(self.first, number=12):
            papers._save(
                self.path,
                {
                    "paper_id": paper_id,
                    "paper_version": 12,
                    "created_by": executor,
                    "generation": {"progress_run_id": self.first},
                },
                pdf,
            )
            saved = papers._read_one(self.path, paper_id)
            reservation = {"number": 12, "creator_email": creator}
            with self.assertRaisesRegex(ProjectError, "saved execution"):
                papers._align_published_creator(self.path, saved, reservation, self.second)
            with self.assertRaisesRegex(ProjectError, "saved execution"):
                papers._align_published_creator(
                    self.path, saved, {"number": 13, "creator_email": creator}, self.first,
                )
            self.assertEqual(
                papers._read_one(self.path, paper_id)["created_by"], executor
            )
            aligned = papers._align_published_creator(self.path, saved, reservation, self.first)
            self.assertEqual(aligned["created_by"], creator)
            self.assertEqual(papers._read_one(self.path, paper_id)["created_by"], creator)
            self.assertEqual(
                (papers._paper_dir(self.path) / f"{paper_id}.pdf").read_bytes(), pdf
            )
            papers._align_published_creator(self.path, aligned, reservation, self.first)

    def test_cancelled_queue_does_not_erase_earlier_progress(self) -> None:
        """The next queued attempt is not the progress history of the Paper."""
        with papers.paper_run_scope(self.first):
            started = papers._now()
            papers._write_progress_status(
                self.path,
                {
                    "run_id": self.first,
                    "status": "paused",
                    "stage": "proofreading",
                    "current": None,
                    "total": None,
                    "started_at": started,
                    "updated_at": started,
                    "elapsed_seconds": 72,
                },
            )
            papers._write_queue_status(self.path, "cancelled", started)
            progress = present(papers.progress_status(self.path))
            self.assertEqual(progress["stage"], "proofreading")
            self.assertEqual(progress["status"], "cancelled")
            self.assertEqual(progress["elapsed_seconds"], 72)
        with papers.paper_run_scope(self.second):
            started = papers._now()
            papers._write_queue_status(self.path, "cancelled", started)
            progress = present(papers.progress_status(self.path))
            self.assertEqual(progress["stage"], "queued")
            self.assertEqual(progress["status"], "cancelled")

    def test_stopping_one_submitted_paper_does_not_cancel_the_other(self) -> None:
        """Two admitted Papers retain distinct tasks across a creator Stop."""

        async def exercise() -> None:
            entered_first = asyncio.Event()
            entered_second = asyncio.Event()
            hold_first = asyncio.Event()
            release_second = asyncio.Event()

            async def generation(entered: asyncio.Event, release: asyncio.Event) -> dict[str, Any]:
                async with papers._paper_operation(self.path, generating=True):
                    entered.set()
                    await release.wait()
                    return {"paper_id": uuid4().hex}

            with papers.paper_run_scope(self.first):
                first = asyncio.create_task(generation(entered_first, hold_first))
                papers.register_submission(self.path, first)
            await asyncio.wait_for(entered_first.wait(), timeout=5)
            with papers.paper_run_scope(self.second):
                second = asyncio.create_task(generation(entered_second, release_second))
                papers.register_submission(self.path, second)
            try:
                with papers.paper_run_scope(self.second):
                    for _ in range(100):
                        queued = papers.progress_status(self.path)
                        if queued is not None and queued.get("status") == "queued":
                            break
                        await asyncio.sleep(0)
                    else:
                        self.fail("Second Paper never received its own queue receipt")
                self.assertFalse(entered_second.is_set())
                with papers.paper_run_scope(self.first):
                    self.assertTrue(await papers.cancel_generation(self.path))
                await asyncio.wait_for(entered_second.wait(), timeout=5)
                self.assertFalse(second.done(), "Stopping A incorrectly cancelled B")
                with papers.paper_run_scope(self.first):
                    self.assertFalse(await papers.cancel_generation(self.path))
                release_second.set()
                result = await asyncio.wait_for(second, timeout=5)
                self.assertIn("paper_id", result)
            finally:
                hold_first.set()
                release_second.set()
                await asyncio.gather(first, second, return_exceptions=True)

        with patch("sigma.memory_guard.require_capacity"):
            asyncio.run(exercise())

    def test_fresh_process_reads_two_independent_paper_sidecars(self) -> None:
        """A new interpreter can read both scoped sidecars; worker restart is separate."""
        for run_id, model in ((self.first, "N"), (self.second, "Z")):
            with papers.paper_run_scope(run_id):
                papers._save_work(self.path, self.saved_work(model))
                papers._write_queue_status(self.path, "queued", papers._now())

        script = """
import sys
from sigma import papers

path, first, second = sys.argv[1:]
for run_id, expected in ((first, "N"), (second, "Z")):
    with papers.paper_run_scope(run_id):
        saved = papers._load_work(path)
        receipt = papers._read_queue_status(path)
        assert saved and saved["model"] == expected
        assert receipt and receipt["status"] == "queued"
"""
        child = subprocess.run(
            [sys.executable, "-c", script, self.path, self.first, self.second],
            cwd=Path(__file__).resolve().parents[1],
            check=False,
            capture_output=True,
            text=True,
            timeout=15,
        )
        self.assertEqual(child.returncode, 0, child.stderr)

    def test_real_process_kill_preserves_scoped_paper_work(self) -> None:
        from paper_process_restart import test_real_paper_process_crash

        test_real_paper_process_crash()

    def test_invalid_or_symlinked_run_directory_is_rejected(self) -> None:
        for bad in ("../escape", "a" * 31, "A" * 32, "", None):
            with (
                self.subTest(run_id=bad),
                self.assertRaises(ValueError),
                papers.paper_run_scope(cast(str, bad)),
            ):
                pass

        work_root = papers._paper_dir(self.path) / ".long-paper-work"
        work_root.mkdir()
        external = self.project.parent / "escape"
        external.mkdir()
        (work_root / "runs").symlink_to(external, target_is_directory=True)
        with papers.paper_run_scope(self.first), self.assertRaises(ProjectError):
            papers._work_file(self.path, create=True)
        (work_root / "runs").unlink()

        (work_root / "runs").mkdir()
        (work_root / "runs" / self.first).symlink_to(external, target_is_directory=True)
        with papers.paper_run_scope(self.first), self.assertRaises(ProjectError):
            papers._work_file(self.path, create=True)
        self.assertFalse((external / "checkpoint.json").exists())

    def test_two_runs_queue_separately_without_running_simultaneously(self) -> None:
        async def exercise() -> None:
            first_entered = asyncio.Event()
            release_first = asyncio.Event()
            second_entered = asyncio.Event()

            async def job(
                run_id: str, entered: asyncio.Event, release: asyncio.Event | None
            ) -> None:
                with papers.paper_run_scope(run_id):
                    async with papers._paper_operation(self.path, generating=True):
                        entered.set()
                        if release is not None:
                            await release.wait()

            first_task = asyncio.create_task(job(self.first, first_entered, release_first))
            await asyncio.wait_for(first_entered.wait(), timeout=5)
            second_task = asyncio.create_task(job(self.second, second_entered, None))
            try:
                for _ in range(100):
                    with papers.paper_run_scope(self.second):
                        state = papers.progress_status(self.path)
                    if state is not None and state["status"] == "queued":
                        break
                    await asyncio.sleep(0)
                else:
                    self.fail("Second Paper did not enter its independent queue")
                self.assertFalse(second_entered.is_set())
                with papers.paper_run_scope(self.first):
                    self.assertIsNone(papers._read_queue_status(self.path))
                with papers.paper_run_scope(self.second):
                    self.assertEqual(
                        present(papers._read_queue_status(self.path))["status"],
                        "queued",
                    )
            finally:
                release_first.set()
                await asyncio.wait_for(first_task, timeout=5)
                await asyncio.wait_for(second_task, timeout=5)
            self.assertTrue(second_entered.is_set())

        with patch("sigma.memory_guard.require_capacity"):
            asyncio.run(exercise())


if __name__ == "__main__":
    main()
