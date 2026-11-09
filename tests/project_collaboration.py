"""Adversarial shared-project lease, revision, and membership tests (no provider calls)."""

from __future__ import annotations

import asyncio
import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from typing import cast
from unittest import TestCase, main
from unittest.mock import AsyncMock, patch

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
        with (
            shared.bind_lease(self.path, first),
            shared.write_guard(self.path, expected_revision=1),
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
        with (
            shared.write_guard(self.path, expected_revision=0),
            shared.write_guard(self.path),
            shared._db() as check,
        ):
            # The outer SQLite transaction is still uncommitted.
            self.assertEqual(
                check.execute(
                    "SELECT revision FROM shared_projects WHERE path=?", (self.path,)
                ).fetchone()["revision"],
                0,
            )
        self.assertEqual(self.revision(), 1)
        with (
            self.assertRaisesRegex(RuntimeError, "deliberate failure"),
            shared.write_guard(self.path, expected_revision=1) as db,
        ):
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
        with (
            self.assertRaisesRegex(ProjectError, "saved by owner@example.org"),
            shared.write_guard(self.path, expected_revision=0),
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

    def test_collaboration_email_uses_shared_transport_and_retries_failures(self) -> None:
        shared.save_settings(self.path, 0, ["new@example.net"], "gpt-6.1-sol", "high", "Study")
        messages: list[tuple[str, str]] = []

        def deliver(message, *, recipients):
            messages.append((recipients[0], message.get_content()))

        with (
            patch("sigma.project_collaboration.cloud_workspaces.enabled", return_value=True),
            patch(
                "sigma.project_collaboration.cloud_auth.config",
                return_value=SimpleNamespace(origin="https://sigma.example.org"),
            ),
            patch(
                "sigma.mail_transport.send_message", side_effect=RuntimeError("temporary")
            ) as mail,
        ):
            self.assertTrue(shared.drain_notifications())
            # A failed email must not prevent the next queued notice.
            self.assertEqual(mail.call_count, 2)
        self.clock[0] += 61
        with (
            patch("sigma.project_collaboration.cloud_workspaces.enabled", return_value=True),
            patch(
                "sigma.project_collaboration.cloud_auth.config",
                return_value=SimpleNamespace(origin="https://sigma.example.org"),
            ),
            patch("sigma.mail_transport.send_message", side_effect=deliver),
        ):
            self.assertEqual(shared.drain_notifications(), [])
            self.assertEqual(shared.drain_notifications(), [])
        self.assertEqual(
            {recipient for recipient, _ in messages}, {"new@example.net", "other@example.org"}
        )
        self.assertIn(
            "/project?path=", next(body for email, body in messages if email == "new@example.net")
        )
        with shared._db() as db:
            self.assertEqual(
                db.execute("SELECT count(*) FROM shared_email_outbox WHERE sent_at>0").fetchone()[
                    0
                ],
                2,
            )

    def test_project_deletion_fences_execution_and_revokes_membership(self) -> None:
        with shared._db() as db:
            db.execute(
                """INSERT INTO shared_email_outbox
                (id,recipient,project_path,project_title,event,created_at)
                VALUES (?,?,?,?,?,?)""",
                ("pending-add", self.other.email, self.path, "Study", "added", self.clock[0]),
            )
        token = shared.acquire_lease(self.path, "Project deletion")
        self.assertIsNotNone(token)
        with self.assertRaisesRegex(ProjectError, "being used"):
            shared.acquire_lease(self.path, "Research session")
        with shared.bind_lease(self.path, token):
            shared.forget_project(self.path, "Study")
        shared.release_lease(self.path, token)
        with shared._db() as db:
            self.assertIsNone(
                db.execute("SELECT * FROM shared_projects WHERE path=?", (self.path,)).fetchone()
            )
            self.assertIsNone(
                db.execute("SELECT * FROM shared_leases WHERE path=?", (self.path,)).fetchone()
            )
            records = list(
                db.execute("SELECT recipient,project_title,event FROM shared_email_outbox")
            )
            self.assertEqual(
                [(row["recipient"], row["project_title"], row["event"]) for row in records],
                [(self.other.email, "Study", "removed")],
            )

    def test_notification_claim_is_single_dispatch_across_workers(self) -> None:
        import time

        with shared._db() as db:
            db.execute(
                """INSERT INTO shared_email_outbox
                (id,recipient,project_path,project_title,event,created_at)
                VALUES (?,?,?,?,?,?)""",
                ("single-notice", self.other.email, self.path, "Study", "added", self.clock[0]),
            )
        calls: list[str] = []

        def deliver(_message, *, recipients):
            calls.append(recipients[0])
            time.sleep(0.04)

        with (
            patch("sigma.project_collaboration.cloud_workspaces.enabled", return_value=True),
            patch(
                "sigma.project_collaboration.cloud_auth.config",
                return_value=SimpleNamespace(origin="https://sigma.example.org"),
            ),
            patch("sigma.mail_transport.send_message", side_effect=deliver),
            ThreadPoolExecutor(max_workers=2) as pool,
        ):
            list(pool.map(lambda _: shared.drain_notifications(), range(2)))
        self.assertEqual(calls, [self.other.email])

    def test_deleted_project_rejects_stale_worker_even_without_workspace(self) -> None:
        token = shared.acquire_lease(self.path, "Project deletion")
        self.assertIsNotNone(token)
        with shared.bind_lease(self.path, token), shared.finalize_deletion(self.path, "Study"):
            pass
        with (
            shared.bind_lease(self.path, token),
            self.assertRaisesRegex(ProjectError, "deleted or its execution lease was lost"),
            shared.write_guard(self.path),
        ):
            self.fail("A removed collaboration catalog allowed a stale worker")
        with (
            patch("sigma.project_collaboration.cloud_workspaces.current", return_value=None),
            shared.bind_lease(self.path, token),
            self.assertRaisesRegex(ProjectError, "execution context was lost"),
            shared.write_guard(self.path),
        ):
            self.fail("An unbound worker bypassed lease fencing")

    def test_deletion_is_authorized_before_acquiring_lease(self) -> None:
        collaborator_workspace = replace(
            self.workspace,
            subject_hash="other-hash",
            path=self.root / "other-account",
            verified_subject=self.other.subject,
            email=self.other.email,
        )
        with (
            patch(
                "sigma.project_collaboration.cloud_workspaces.current",
                return_value=collaborator_workspace,
            ),
            patch(
                "sigma.project_collaboration.cloud_auth.current_principal",
                return_value=self.other,
            ),
            self.assertRaisesRegex(ProjectError, "Only the project owner"),
        ):
            shared.acquire_lease(self.path, "Project deletion")
        self.assertEqual(self.revision(), 0)

    def test_deletion_publication_rolls_back_metadata_if_file_removal_fails(self) -> None:
        token = shared.acquire_lease(self.path, "Project deletion")
        self.assertIsNotNone(token)
        with (
            shared.bind_lease(self.path, token),
            self.assertRaisesRegex(OSError, "simulated unlink"),
            shared.finalize_deletion(self.path, "Study"),
        ):
            raise OSError("simulated unlink")
        with shared._db() as db:
            self.assertIsNotNone(
                db.execute("SELECT 1 FROM shared_projects WHERE path=?", (self.path,)).fetchone()
            )
            self.assertIsNotNone(
                db.execute("SELECT 1 FROM shared_leases WHERE path=?", (self.path,)).fetchone()
            )
        shared.release_lease(self.path, token)

    def test_expired_deletion_lease_blocks_destructive_publication(self) -> None:
        token = shared.acquire_lease(self.path, "Project deletion")
        self.assertIsNotNone(token)
        self.clock[0] += shared.LEASE_SECONDS + 1
        with (
            shared.bind_lease(self.path, token),
            self.assertRaisesRegex(ProjectError, "lease was lost"),
            shared.finalize_deletion(self.path, "Study"),
        ):
            self.fail("A stale deletion lease published removal")
        with shared._db() as db:
            self.assertIsNotNone(
                db.execute("SELECT 1 FROM shared_projects WHERE path=?", (self.path,)).fetchone()
            )

    def test_deletion_heartbeat_renews_independent_of_event_loop(self) -> None:
        with (
            patch("sigma.project_collaboration.LEASE_SECONDS", 0.09),
            patch("sigma.project_collaboration.renew_lease", return_value=True) as renew,
            shared.keep_lease(self.path, "deletion-token"),
        ):
            time.sleep(0.11)
        self.assertGreaterEqual(renew.call_count, 1)

    def test_failed_invitation_backoff_does_not_block_others(self) -> None:
        with shared._db() as db:
            db.executemany(
                """INSERT INTO shared_email_outbox
                (id,recipient,project_path,project_title,event,created_at)
                VALUES (?,?,?,?,?,?)""",
                [
                    ("a-poison", "poison@example.net", self.path, "Study", "added", 900),
                    ("b-good", "good@example.net", self.path, "Study", "added", 901),
                ],
            )
        delivered: list[str] = []

        def transport(_message, *, recipients):
            if recipients[0] == "poison@example.net":
                raise RuntimeError("refused")
            delivered.append(recipients[0])

        with (
            patch("sigma.project_collaboration.cloud_workspaces.enabled", return_value=True),
            patch(
                "sigma.project_collaboration.cloud_auth.config",
                return_value=SimpleNamespace(origin="https://sigma.example.org"),
            ),
            patch("sigma.mail_transport.send_message", side_effect=transport),
        ):
            self.assertTrue(shared.drain_notifications())
            self.assertEqual(delivered, ["good@example.net"])
            with shared._db() as db:
                poison = db.execute(
                    "SELECT attempts,retry_after,failed_at "
                    "FROM shared_email_outbox WHERE id='a-poison'"
                ).fetchone()
                self.assertEqual(poison["attempts"], 1)
                self.assertGreater(poison["retry_after"], self.clock[0])
                self.assertIsNone(poison["failed_at"])
            self.clock[0] += 61
            self.assertTrue(shared.drain_notifications())
            self.clock[0] += 121
            self.assertTrue(shared.drain_notifications())
            self.clock[0] += 10000
            self.assertEqual(shared.drain_notifications(), [])
        with shared._db() as db:
            poison = db.execute(
                "SELECT attempts,failed_at FROM shared_email_outbox WHERE id='a-poison'"
            ).fetchone()
            self.assertEqual(poison["attempts"], shared.MAX_NOTIFICATION_ATTEMPTS)
            self.assertIsNotNone(poison["failed_at"])
        self.assertEqual(delivered, ["good@example.net"])

    def test_legacy_collaboration_outbox_is_upgraded_in_place(self) -> None:
        with shared._db() as db:
            db.execute("DROP TABLE shared_email_outbox")
            db.execute(
                """CREATE TABLE shared_email_outbox (
                    id TEXT PRIMARY KEY,
                    recipient TEXT NOT NULL,
                    project_path TEXT NOT NULL,
                    project_title TEXT NOT NULL,
                    event TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    sent_at REAL
                )"""
            )
            db.execute(
                """INSERT INTO shared_email_outbox
                (id,recipient,project_path,project_title,event,created_at)
                VALUES ('old','old@example.org',?,'Study','added',?)""",
                (self.path, self.clock[0]),
            )
        with shared._db() as db:
            record = db.execute(
                "SELECT attempts,retry_after,failed_at FROM shared_email_outbox WHERE id='old'"
            ).fetchone()
            self.assertEqual(record["attempts"], 0)
            self.assertEqual(record["retry_after"], 0)
            self.assertIsNone(record["failed_at"])

    def test_successful_api_save_and_delete_do_not_send_mail_inline(self) -> None:
        from sigma import api

        view = SimpleNamespace(project=SimpleNamespace(investigation_type="default"))
        request = SimpleNamespace(
            path=self.path,
            investigation_type="default",
            title="Study",
            problem="Research problem",
            ai_model="gpt-6.1-sol",
            reasoning_effort="high",
            expected=SimpleNamespace(model_dump=lambda **_kw: {}),
            difficulty=None,
            show_advanced_outcome_details=None,
            desired_outcomes=None,
            paper_requirements=None,
            expected_revision=0,
            collaborators=[self.other.email],
        )
        with (
            patch("sigma.api.inspect_project", return_value=view),
            patch("sigma.api.update_project", return_value=view),
            patch("sigma.project_collaboration.register_owner", return_value=None),
            patch("sigma.api.asdict", return_value={"saved": True}),
            patch(
                "sigma.project_collaboration.drain_notifications",
                side_effect=AssertionError(),
            ),
        ):
            self.assertEqual(
                api.update_project_view(cast(api.UpdateProjectRequest, request)), {"saved": True}
            )

        deletion = SimpleNamespace(path=self.path, expected_project_id="saved-project")
        with (
            patch("sigma.projects.project_path", return_value=Path(self.path)),
            patch("sigma.projects.projects_root", return_value=self.root),
            patch("sigma.project_collaboration.acquire_lease", return_value=None),
            patch("sigma.api._delete_project_unleased", new_callable=AsyncMock) as delete,
            patch(
                "sigma.project_collaboration.drain_notifications",
                side_effect=AssertionError(),
            ),
        ):
            delete.return_value = {"deleted": True}
            self.assertEqual(
                asyncio.run(api.delete_project_view(cast(api.DeleteProjectRequest, deletion))),
                {"deleted": True},
            )

    def test_global_research_limits_save_does_not_take_project_lease(self) -> None:
        from sigma import research_sessions

        token = shared.acquire_lease(self.path, "Research session")
        self.assertIsNotNone(token)
        before = self.revision()
        with patch(
            "sigma.global_research_settings.save",
            return_value={"research_rounds": 3},
        ) as save:
            saved = research_sessions.save_limits(self.path, {"research_rounds": 3})
        self.assertEqual(saved["research_rounds"], 3)
        save.assert_called_once_with({"research_rounds": 3})
        self.assertEqual(self.revision(), before)
        shared.release_lease(self.path, token)

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
