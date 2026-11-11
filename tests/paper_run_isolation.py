"""Provider-free tests of opt-in Paper run isolation and serial capacity queuing.

API admission is still project-scoped. These tests protect the storage/task
boundary before enabling independent collaborator starts.
"""

from __future__ import annotations

import asyncio
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
                self.assertEqual(
                    present(papers._read_queue_status(self.path))["status"], "queued"
                )
                self.assertEqual(
                    papers._work_file(self.path, create=False).parent.name, run_id
                )

        # Reopening a scope after all task state is gone recovers the same work.
        with papers.paper_run_scope(self.first):
            self.assertEqual(present(papers._load_work(self.path))["model"], "first")
            papers._clear_work(self.path)
            papers._clear_queue_status(self.path)
        with papers.paper_run_scope(self.second):
            self.assertEqual(present(papers._load_work(self.path))["model"], "second")
            self.assertEqual(
                present(papers._read_queue_status(self.path))["status"], "queued"
            )
        self.assertEqual(present(papers._load_work(self.path))["model"], "legacy")
        self.assertEqual(papers._work_file(self.path, create=False), legacy_file)
        self.assertTrue(legacy_file.is_file())

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

            first_task = asyncio.create_task(
                job(self.first, first_entered, release_first)
            )
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
