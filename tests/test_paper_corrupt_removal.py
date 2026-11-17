"""Corrupted saved-paper deletion must be exact, authorized and PDF-safe."""

from __future__ import annotations

import fcntl
import os
from tempfile import TemporaryDirectory
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from sigma import papers
from sigma.projects import ProjectError


class CorruptPaperRemovalTests(TestCase):
    def setUp(self) -> None:
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.directory = self.root / "papers"
        self.directory.mkdir()
        self.paper_id = "a" * 32
        self.other_id = "b" * 32
        self.run_id = "c" * 32
        self.project_path = self.root / "project"

    def acquire_lock(self, _path: str) -> int:
        fd = os.open(self.root / "paper.lock", os.O_CREAT | os.O_RDWR, 0o600)
        fcntl.flock(fd, fcntl.LOCK_EX)
        return fd

    def test_unreadable_paper_is_removed_without_touching_other_papers(self) -> None:
        for ext in (".json", ".pdf", ".tex"):
            (self.directory / f"{self.paper_id}{ext}").write_bytes(b"corrupt metadata")
            (self.directory / f"{self.other_id}{ext}").write_bytes(b"preserve this paper")
        with (
            patch.object(papers, "_paper_version_lock", side_effect=self.acquire_lock),
            patch.object(papers, "project_path", return_value=self.project_path),
            patch.object(papers, "_paper_dir", return_value=self.directory),
            patch.object(
                papers,
                "get_paper",
                side_effect=ProjectError("Paper record is unreadable"),
            ),
            patch.object(papers, "progress_status", return_value={"status": "complete"}),
            patch.object(papers, "_clear_published_paper_progress") as clear,
        ):
            papers.delete_unreadable_paper(str(self.project_path), self.paper_id, self.run_id)
        for ext in (".json", ".pdf", ".tex"):
            self.assertFalse((self.directory / f"{self.paper_id}{ext}").exists())
            self.assertEqual(
                (self.directory / f"{self.other_id}{ext}").read_bytes(),
                b"preserve this paper",
            )
        clear.assert_called_once()

    def test_healthy_record_and_live_worker_are_not_deleted(self) -> None:
        target = self.directory / f"{self.paper_id}.json"
        target.write_text("saved", encoding="utf-8")
        common = (
            patch.object(papers, "_paper_version_lock", side_effect=self.acquire_lock),
            patch.object(papers, "project_path", return_value=self.project_path),
            patch.object(papers, "_paper_dir", return_value=self.directory),
        )
        with (*common, patch.object(papers, "get_paper", return_value={"paper_id": self.paper_id})):
            with self.assertRaisesRegex(ProjectError, "readable"):
                papers.delete_unreadable_paper(str(self.project_path), self.paper_id, self.run_id)
        self.assertTrue(target.exists())

        with (
            *common,
            patch.object(
                papers, "get_paper", side_effect=ProjectError("Paper record is unreadable")
            ),
            patch.object(papers, "progress_status", return_value={"status": "active"}),
        ):
            with self.assertRaisesRegex(ProjectError, "Stop this paper"):
                papers.delete_unreadable_paper(str(self.project_path), self.paper_id, self.run_id)
        self.assertTrue(target.exists())
