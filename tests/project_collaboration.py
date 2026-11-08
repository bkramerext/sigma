"""Adversarial shared-project lease, revision, and membership tests (no provider calls)."""

from __future__ import annotations

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase, main
from unittest.mock import patch

from sigma import project_collaboration as shared
from sigma.cloud_auth import Principal
from sigma.cloud_workspaces import Workspace
from sigma.projects import ProjectError


class CollaborationTests(TestCase):
    def setUp(self) -> None:
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = str(self.root / "shared.json")
        self.owner = Principal(subject="google-owner", email="owner@example.org", role="member")
        self.other = Principal(subject="google-other", email="other@example.org", role="member")
        self.outsider = Principal(
            subject="google-outsider", email="outsider@example.org", role="member"
        )
        self.workspace = Workspace(
            workspace_id="owner-workspace",
            subject_hash="owner-hash",
            path=self.root,
            email=self.owner.email,
            verified_subject=self.owner.subject,
        )
        self.clock = [1000.0]

        def connect(root: Path) -> sqlite3.Connection:
            connection = sqlite3.connect(
                root / "collaboration.sqlite3", timeout=10, isolation_level=None
            )
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA busy_timeout=10000")
            return connection

        for target, value in (
            ("sigma.project_collaboration.cloud_workspaces.storage_root", self.root),
            ("sigma.project_collaboration.cloud_workspaces._connect", connect),
            ("sigma.project_collaboration.cloud_workspaces.current", self.workspace),
            ("sigma.project_collaboration.cloud_auth.current_principal", self.owner),
            ("sigma.project_collaboration.time.time", lambda: self.clock[0]),
            (
                "sigma.projects.inspect_project",
                lambda path: SimpleNamespace(
                    path=str(path), project=SimpleNamespace(id="saved-project")
                ),
            ),
        ):
            patcher = patch(target, value) if callable(value) else patch(target, return_value=value)
            patcher.start()
            self.addCleanup(patcher.stop)
        with shared._db() as db:
            db.execute(
                """INSERT INTO shared_projects
                (path,project_id,owner_hash,owner_email,model,thinking,last_writer,updated_at)
                VALUES (?,?,?,?,?,?,?,?)""",
                (
                    self.path,
                    "saved-project",
                    "owner-hash",
                    self.owner.email,
                    "gpt-6.1-sol",
                    "high",
                    self.owner.email,
                    self.clock[0],
                ),
            )
            db.execute(
                "INSERT INTO shared_collaborators(path,email) VALUES (?,?)",
                (self.path, self.other.email),
            )

    def revision(self) -> int:
        with shared._db() as db:
            return int(
                db.execute(
                    "SELECT revision FROM shared_projects WHERE path=?", (self.path,)
                ).fetchone()["revision"]
            )

    def test_fence_prevents_stale_worker_and_foreign_writes(self) -> None:
        first = shared.acquire_lease(self.path, "Research session")
        self.assertIsNotNone(first)
        self.assertEqual(self.revision(), 1)
        with self.assertRaisesRegex(ProjectError, "being used"):
            shared.acquire_lease(self.path, "Paper generation")
        with shared.bind_lease(self.path, first), shared.write_guard(
            self.path, expected_revision=1
        ):
            pass
        self.assertEqual(self.revision(), 2)
        self.clock[0] += shared.LEASE_SECONDS + 1
        next_token = shared.acquire_lease(self.path, "Paper generation")
        self.assertNotEqual(first, next_token)
        before = self.revision()
        with (
            shared.bind_lease(self.path, first),
            self.assertRaisesRegex(ProjectError, "lease was lost"),
            shared.write_guard(self.path),
        ):
            self.fail("Stale worker entered the persistence boundary")
        self.assertEqual(self.revision(), before)
        with shared.bind_lease(self.path, next_token), shared.write_guard(self.path):
            pass
        self.assertEqual(self.revision(), before + 1)

    def test_nested_write_commits_one_revision_and_rolls_back_metadata(self) -> None:
        with shared.write_guard(self.path, expected_revision=0):
            with shared.write_guard(self.path):
                with shared._db() as check:
                    # The outer SQLite transaction is still uncommitted.
                    self.assertEqual(
                        check.execute(
                            "SELECT revision FROM shared_projects WHERE path=?", (self.path,)
                        ).fetchone()["revision"],
                        0,
                    )
        self.assertEqual(self.revision(), 1)
        with self.assertRaisesRegex(RuntimeError, "deliberate failure"):
            with shared.write_guard(self.path, expected_revision=1) as db:
                assert db is not None
                db.execute(
                    "UPDATE shared_projects SET thinking=? WHERE path=?",
                    ("medium", self.path),
                )
                raise RuntimeError("deliberate failure")
        with shared._db() as db:
            row = db.execute(
                "SELECT thinking,revision FROM shared_projects WHERE path=?", (self.path,)
            ).fetchone()
            self.assertEqual((row["thinking"], row["revision"]), ("high", 1))

    def test_compare_and_swap_rejects_stale_settings(self) -> None:
        with shared.write_guard(self.path, expected_revision=0):
            pass
        with self.assertRaisesRegex(ProjectError, "saved by owner@example.org"), shared.write_guard(
            self.path, expected_revision=0
        ):
            self.fail("Stale editor was allowed to persist")
        self.assertEqual(self.revision(), 1)

    def test_membership_changes_are_transactional_and_owner_immutable(self) -> None:
        with self.assertRaisesRegex(ProjectError, "owner"):
            shared.save_settings(self.path, 0, [self.owner.email], "gpt-6.1-sol", "high", "Study")
        self.assertEqual(self.revision(), 0)
        result = shared.save_settings(
            self.path, 0, ["new@example.net"], "gpt-6.1-sol", "medium", "Study"
        )
        self.assertTrue(result["changed"])
        self.assertEqual(result["revision"], 1)
        with shared._db() as db:
            members = [
                row["email"]
                for row in db.execute(
                    "SELECT email FROM shared_collaborators WHERE path=?", (self.path,)
                )
            ]
            queued = [
                row["event"]
                for row in db.execute("SELECT event FROM shared_email_outbox ORDER BY event")
            ]
        self.assertEqual(members, ["new@example.net"])
        self.assertEqual(queued, ["added", "removed"])
        with self.assertRaisesRegex(ProjectError, "saved by"):
            shared.save_settings(self.path, 0, ["new@example.net"], "gpt-6.1-sol", "high", "Study")

    def test_gmail_validation_and_acl(self) -> None:
        self.assertEqual(
            shared.normalize_collaborator(" SCARKRA01@TAMU.EDU "), "scarkra01@tamu.edu"
        )
        for address in ("a@gmail.com", "a..b@gmail.com", "bad@@gmail.com", "foo@-evil.org"):
            with self.subTest(address=address), self.assertRaises(ValueError):
                shared.normalize_collaborator(address)
        self.assertTrue(shared.authorized_shared_path(Path(self.path)))
        with patch(
            "sigma.project_collaboration.cloud_auth.current_principal", return_value=self.outsider
        ):
            self.assertFalse(shared.authorized_shared_path(Path(self.path)))

    def test_concurrent_expected_revision_has_one_winner(self) -> None:
        def save() -> bool:
            try:
                with shared.write_guard(self.path, expected_revision=0):
                    pass
                return True
            except ProjectError:
                return False

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: save(), range(2)))
        self.assertEqual(sorted(results), [False, True])
        self.assertEqual(self.revision(), 1)


if __name__ == "__main__":
    main()
