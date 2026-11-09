"""Adversarial shared-project lease, revision, and membership tests (no provider calls)."""

from __future__ import annotations

import asyncio
import hashlib
import json
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

from sigma import project_bundle
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
                    path=str(path),
                    project=SimpleNamespace(
                        id="saved-project",
                        ai_model="gpt-6.1-sol",
                        reasoning_effort="high",
                    ),
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

    def test_collaborator_alone_sees_shared_project_in_saved(self) -> None:
        """An invitation is durable and does not depend on owner's login session."""
        from contextlib import contextmanager
        from uuid import uuid4

        from sigma import recents

        project_id = str(uuid4())
        with shared._db() as db:
            db.execute(
                "UPDATE shared_projects SET project_id=? WHERE path=?",
                (project_id, self.path),
            )
            db.execute("DELETE FROM shared_collaborators WHERE path=?", (self.path,))

        # Z saves N as collaborator; afterward no owner session is present.
        shared.save_settings(
            self.path,
            self.revision(),
            [self.other.email],
            "gpt-6.1-sol",
            "high",
            "Xenopus Tadpoles",
        )

        @contextmanager
        def empty_saved_index():
            yield {"version": 2, "entries": [], "pins": {}, "bootstrapped_roots": {}}

        colleague = Workspace(
            workspace_id="collaborator-workspace",
            subject_hash="collaborator-hash",
            path=self.root / "colleague",
            email=self.other.email,
            verified_subject=self.other.subject,
        )
        project = SimpleNamespace(
            id=project_id,
            title="Xenopus Tadpoles",
            investigation_type="biology",
            project_type_snapshot=None,
            active_order=(),
            difficulty="hard",
        )
        with (
            patch("sigma.project_collaboration.cloud_workspaces.current", return_value=colleague),
            patch(
                "sigma.project_collaboration.cloud_auth.current_principal", return_value=self.other
            ),
            patch("sigma.recents._index", empty_saved_index),
            patch(
                "sigma.recents.inspect_project",
                return_value=SimpleNamespace(path=self.path, project=project),
            ),
        ):
            invited, visible = shared.shared_listing()
            self.assertEqual(invited, [{"path": self.path, "id": project_id}])
            self.assertIn(self.path, visible)
            self.assertTrue(shared.authorized_shared_path(Path(self.path)))
            result = recents.recent_projects(lightweight=True)["projects"]
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["title"], "Xenopus Tadpoles")
        self.assertTrue(result[0]["available"])
        self.assertTrue(result[0]["shared"])

    def test_saved_listing_uses_single_db_snapshot_for_owner_and_collaborator(self) -> None:
        with patch.object(shared, "_db", wraps=shared._db) as db_calls:
            invited, shared_paths = shared.shared_listing()
        self.assertEqual(invited, [])
        self.assertEqual(shared_paths, {self.path})
        self.assertEqual(db_calls.call_count, 1)
        colleague = Workspace(
            workspace_id="collaborator-workspace",
            subject_hash="collaborator-hash",
            path=self.root,
            email=self.other.email,
            verified_subject=self.other.subject,
        )
        with (
            patch("sigma.project_collaboration.cloud_workspaces.current", return_value=colleague),
            patch(
                "sigma.project_collaboration.cloud_auth.current_principal", return_value=self.other
            ),
        ):
            invited, shared_paths = shared.shared_listing()
        self.assertEqual(invited, [{"path": self.path, "id": "saved-project"}])
        self.assertEqual(shared_paths, {self.path})

    def test_artifact_attribution_tracks_authenticated_actor_without_replacing_creator(
        self,
    ) -> None:
        shared.note_artifact_author(self.path, "strategy", "strategy-one")
        shared.note_artifact_author(self.path, "paper", "paper-one", created_only=True)
        self.assertEqual(
            shared.summary(self.path)["artifact_authors"]["strategy"]["strategy-one"],
            self.owner.email,
        )
        colleague = Workspace(
            workspace_id="collaborator-workspace",
            subject_hash="collaborator-hash",
            path=self.root,
            email=self.other.email,
            verified_subject=self.other.subject,
        )
        with (
            patch("sigma.project_collaboration.cloud_workspaces.current", return_value=colleague),
            patch(
                "sigma.project_collaboration.cloud_auth.current_principal",
                return_value=self.other,
            ),
        ):
            shared.note_artifact_author(self.path, "strategy", "strategy-one")
            shared.note_artifact_author(self.path, "paper", "paper-one", created_only=True)
            attribution = shared.summary(self.path)["artifact_authors"]
            self.assertEqual(attribution["strategy"]["strategy-one"], self.other.email)
            self.assertEqual(attribution["paper"]["paper-one"], self.owner.email)

        with shared._db() as db:
            db.execute("DELETE FROM shared_collaborators WHERE path=?", (self.path,))
        self.assertFalse(shared.summary(self.path)["shared"])
        self.assertEqual(shared.summary(self.path)["artifact_authors"], {})

    def revision(self) -> int:
        with shared._db() as db:
            return int(
                db.execute(
                    "SELECT revision FROM shared_projects WHERE path=?", (self.path,)
                ).fetchone()["revision"]
            )

    def test_owner_reopen_is_read_only_and_rejects_identity_drift(self) -> None:
        view = SimpleNamespace(
            path=self.path,
            project=SimpleNamespace(
                id="saved-project",
                ai_model="gpt-6.1-sol",
                reasoning_effort="high",
            ),
        )
        # Project polling/opening should never hash the project or write the
        # shared SQLite row when ownership has already been established.
        with patch.object(
            shared, "_project_digest", side_effect=AssertionError("unneeded bundle scan")
        ):
            shared.register_owner(view)
        with self.assertRaisesRegex(ValueError, "identity has changed"):
            shared.register_owner(
                SimpleNamespace(
                    path=self.path,
                    project=SimpleNamespace(id="different-project"),
                )
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

    def test_only_owner_or_original_inviter_can_remove_collaborator(self) -> None:
        owner_invited = "owner-invited@example.org"
        other_invited = "other-invited@example.org"
        # Legacy collaborator has no verified inviter, so only owner may remove.
        with shared._db() as db:
            legacy = db.execute(
                "SELECT added_by FROM shared_collaborators WHERE path=? AND email=?",
                (self.path, self.other.email),
            ).fetchone()
            self.assertIsNone(legacy["added_by"])

        shared.save_settings(
            self.path, self.revision(), [self.other.email, owner_invited],
            "gpt-6.1-sol", "high", "Study",
        )
        self.assertEqual(
            shared.summary(self.path)["removable_collaborators"],
            [self.other.email, owner_invited],
        )

        workspace = Workspace(
            workspace_id="other-workspace",
            subject_hash="other-hash",
            path=self.root,
            email=self.other.email,
            verified_subject=self.other.subject,
        )
        with (
            patch("sigma.project_collaboration.cloud_workspaces.current", return_value=workspace),
            patch(
                "sigma.project_collaboration.cloud_auth.current_principal",
                return_value=self.other,
            ),
        ):
            # A collaborator may invite someone and subsequently remove that invitee.
            shared.save_settings(
                self.path, self.revision(),
                [self.other.email, owner_invited, other_invited],
                "gpt-6.1-sol", "high", "Study",
            )
            self.assertEqual(shared.summary(self.path)["removable_collaborators"], [other_invited])
            revision = self.revision()
            with self.assertRaisesRegex(ProjectError, "Only the project owner"):
                shared.save_settings(
                    self.path, revision,
                    [self.other.email, other_invited, "unrelated@example.org"],
                    "gpt-6.1-sol", "high", "Study",
                )
            self.assertEqual(self.revision(), revision)
            with shared._db() as db:
                self.assertIsNone(
                    db.execute(
                        "SELECT 1 FROM shared_collaborators WHERE path=? AND email=?",
                        (self.path, "unrelated@example.org"),
                    ).fetchone()
                )
            # Editing model/thinking must not silently replace inviter provenance.
            shared.save_settings(
                self.path, revision,
                [self.other.email, owner_invited, other_invited],
                "gpt-6.1-sol", "medium", "Study",
            )
            with shared._db() as db:
                inviter = db.execute(
                    "SELECT added_by FROM shared_collaborators WHERE path=? AND email=?",
                    (self.path, other_invited),
                ).fetchone()
                self.assertEqual(inviter["added_by"], self.other.email)
            shared.save_settings(
                self.path, self.revision(), [self.other.email, owner_invited],
                "gpt-6.1-sol", "medium", "Study",
            )

        # Owner can override an inviter's choice and remove any invitee.
        with shared._db() as db:
            members = {
                record["email"]: record["added_by"]
                for record in db.execute(
                    "SELECT email,added_by FROM shared_collaborators WHERE path=?", (self.path,)
                )
            }
        self.assertEqual(members, {self.other.email: None, owner_invited: self.owner.email})
        shared.save_settings(
            self.path, self.revision(), [], "gpt-6.1-sol", "medium", "Study"
        )
        self.assertEqual(shared.summary(self.path)["collaborators"], [])

    def test_owner_can_remove_invitee_added_by_another_collaborator(self) -> None:
        inviter = Workspace(
            workspace_id="other-workspace",
            subject_hash="other-hash",
            path=self.root,
            email=self.other.email,
            verified_subject=self.other.subject,
        )
        with (
            patch("sigma.project_collaboration.cloud_workspaces.current", return_value=inviter),
            patch(
                "sigma.project_collaboration.cloud_auth.current_principal",
                return_value=self.other,
            ),
        ):
            shared.save_settings(
                self.path, self.revision(), ["invitee@example.org", self.other.email],
                "gpt-6.1-sol", "high", "Study",
            )
        self.assertEqual(
            shared.summary(self.path)["removable_collaborators"],
            [self.other.email, "invitee@example.org"],
        )
        shared.save_settings(
            self.path, self.revision(), [self.other.email], "gpt-6.1-sol", "high", "Study"
        )
        self.assertEqual(shared.summary(self.path)["collaborators"], [self.other.email])

    def test_collaboration_email_uses_shared_transport_and_retries_failures(self) -> None:
        shared.save_settings(self.path, 0, ["new@example.net"], "gpt-6.1-sol", "high", "Study")
        messages: list[tuple[str, str, str | None]] = []

        def deliver(message, *, recipients):
            html_part = message.get_body(preferencelist=("html",))
            messages.append(
                (
                    recipients[0],
                    message.get_body(preferencelist=("plain",)).get_content(),
                    html_part.get_content() if html_part is not None else None,
                )
            )

        with (
            patch(
                "sigma.project_collaboration.cloud_workspaces.account_scoping_enabled",
                return_value=True,
            ),
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
            patch(
                "sigma.project_collaboration.cloud_workspaces.account_scoping_enabled",
                return_value=True,
            ),
            patch(
                "sigma.project_collaboration.cloud_auth.config",
                return_value=SimpleNamespace(origin="https://sigma.example.org"),
            ),
            patch("sigma.mail_transport.send_message", side_effect=deliver),
        ):
            self.assertEqual(shared.drain_notifications(), [])
            self.assertEqual(shared.drain_notifications(), [])
        self.assertEqual(
            {recipient for recipient, _, _ in messages},
            {"new@example.net", "other@example.org"},
        )
        added = next((plain, html) for email, plain, html in messages if email == "new@example.net")
        removed = next(
            (plain, html) for email, plain, html in messages if email == "other@example.org"
        )
        self.assertIn("/project?path=", added[0])
        self.assertIn(">Study</a>", added[1])
        self.assertIn('href="https://sigma.example.org/project?path=', added[1])
        self.assertNotIn("“Study”", added[0])
        self.assertNotIn("“Study”", added[1])
        self.assertIn("“Study”", removed[0])
        self.assertIsNone(removed[1])
        with shared._db() as db:
            self.assertEqual(
                db.execute("SELECT count(*) FROM shared_email_outbox WHERE sent_at>0").fetchone()[
                    0
                ],
                2,
            )

    def test_added_collaborator_email_links_title_from_local_loopback(self) -> None:
        title = "Why Do Xenopus Tadpoles Temporarily Lose Tail Regeneration? v10"
        shared.save_settings(self.path, 0, ["new@example.net"], "gpt-6.1-sol", "high", title)
        delivered = []

        def capture(message, *, recipients):
            delivered.append((recipients[0], message))

        with (
            patch(
                "sigma.project_collaboration.cloud_workspaces.account_scoping_enabled",
                return_value=True,
            ),
            patch(
                "sigma.project_collaboration.cloud_auth.config",
                return_value=SimpleNamespace(origin="http://127.0.0.1:8844"),
            ),
            patch("sigma.mail_transport.send_message", side_effect=capture),
        ):
            self.assertEqual(shared.drain_notifications(), [])

        message = next(message for recipient, message in delivered if recipient == "new@example.net")
        plain = message.get_body(preferencelist=("plain",)).get_content()
        html = message.get_body(preferencelist=("html",)).get_content()
        self.assertIn(f"SIGMA project {title}.", plain)
        self.assertIn("Open project: http://127.0.0.1:8844/project?path=", plain)
        self.assertIn('href="http://127.0.0.1:8844/project?path=', html)
        self.assertIn(f">{title}</a>", html)
        self.assertNotIn(f"“{title}”", html)
        self.assertNotIn("Sign in to SIGMA with this Google account", plain)

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
            patch(
                "sigma.project_collaboration.cloud_workspaces.account_scoping_enabled",
                return_value=True,
            ),
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
            patch(
                "sigma.project_collaboration.cloud_workspaces.account_scoping_enabled",
                return_value=True,
            ),
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

    def test_revision_recovers_file_publication_after_sqlite_rollback(self) -> None:
        original = b'{"schema_version":8,"id":"before"}'
        updated = b'{"schema_version":8,"id":"after"}'
        Path(self.path).write_text(
            json.dumps(project_bundle.portable_bundle({"project.json": original})),
            encoding="utf-8",
        )
        initial_digest = shared._project_digest(self.path)
        self.assertIsNotNone(initial_digest)
        with shared._db() as db:
            db.execute(
                "UPDATE shared_projects SET project_sha256=? WHERE path=?",
                (initial_digest, self.path),
            )
        # A crash after os.replace but before SQLite COMMIT leaves the new
        # file behind. This represents precisely that interrupted publication.
        Path(self.path).write_text(
            json.dumps(project_bundle.portable_bundle({"project.json": updated})),
            encoding="utf-8",
        )
        with (
            self.assertRaisesRegex(ProjectError, "saved by recovered project file update"),
            shared.write_guard(self.path, expected_revision=0),
        ):
            pass
        # A later authenticated read establishes the new revision durably.
        recovered = shared.summary(self.path, verify_revision=True)
        self.assertEqual(recovered["revision"], 1)
        self.assertEqual(self.revision(), 1)
        with shared._db() as db:
            digest = db.execute(
                "SELECT project_sha256 FROM shared_projects WHERE path=?", (self.path,)
            ).fetchone()["project_sha256"]
        self.assertEqual(digest, hashlib.sha256(b'{"id":"after","schema_version":8}').hexdigest())
        self.assertEqual(
            json.loads(project_bundle.read_file(self.path, "project.json")),
            json.loads(updated),
        )

    def test_publication_records_project_digest_in_same_write(self) -> None:
        contents = b'{"schema_version":8,"id":"committed"}'
        with shared.write_guard(self.path, expected_revision=0):
            Path(self.path).write_text(
                json.dumps(project_bundle.portable_bundle({"project.json": contents})),
                encoding="utf-8",
            )
            shared.note_project_published(self.path, contents)
        self.assertEqual(self.revision(), 1)
        with shared._db() as db:
            digest = db.execute(
                "SELECT project_sha256 FROM shared_projects WHERE path=?", (self.path,)
            ).fetchone()["project_sha256"]
        self.assertEqual(
            digest, hashlib.sha256(b'{"id":"committed","schema_version":8}').hexdigest()
        )
        self.assertEqual(shared.summary(self.path, verify_revision=True)["revision"], 1)
        # Session and paper sidecars share the .json bundle but must not
        # invalidate the project's settings revision.
        project_bundle.write_file(
            self.path, "research-sessions/finished.json", b'{"status":"ended"}'
        )
        project_bundle.write_file(self.path, "papers/finished.json", b'{"status":"ready"}')
        self.assertEqual(shared.summary(self.path, verify_revision=True)["revision"], 1)

    def test_two_verified_accounts_share_access_and_handoff_after_expiry(self) -> None:
        other_workspace = replace(
            self.workspace,
            path=self.root / "other-account",
            subject_hash="other-hash",
            verified_subject=self.other.subject,
            email=self.other.email,
        )
        token = shared.acquire_lease(self.path, "Research session")
        self.assertIsNotNone(token)
        with (
            patch(
                "sigma.project_collaboration.cloud_workspaces.current",
                return_value=other_workspace,
            ),
            patch(
                "sigma.project_collaboration.cloud_auth.current_principal",
                return_value=self.other,
            ),
        ):
            self.assertTrue(shared.authorized_shared_path(Path(self.path)))
            self.assertIn(self.path, [item["path"] for item in shared.shared_with_me()])
            with self.assertRaisesRegex(ProjectError, "being used"):
                shared.acquire_lease(self.path, "Paper generation")
            self.clock[0] += shared.LEASE_SECONDS + 1
            next_token = shared.acquire_lease(self.path, "Paper generation")
            self.assertIsNotNone(next_token)
            with shared.bind_lease(self.path, next_token), shared.write_guard(self.path):
                pass
        with (
            shared.bind_lease(self.path, token),
            self.assertRaisesRegex(ProjectError, "lease was lost"),
            shared.write_guard(self.path),
        ):
            pass
        shared.release_lease(self.path, next_token)

    def test_failed_notification_is_visible_and_retry_requires_membership(self) -> None:
        with shared._db() as db:
            db.execute(
                """INSERT INTO shared_email_outbox
                (id,recipient,project_path,project_title,event,created_at,attempts,failed_at)
                VALUES (?,?,?,?,?,?,?,?)""",
                ("failed-notice", "other@example.org", self.path, "Study", "added", 1, 3, 999),
            )
        self.assertEqual(shared.summary(self.path)["failed_notifications"], 1)
        outsider_workspace = replace(
            self.workspace,
            subject_hash="outsider-hash",
            verified_subject=self.outsider.subject,
            email=self.outsider.email,
        )
        with (
            patch(
                "sigma.project_collaboration.cloud_workspaces.current",
                return_value=outsider_workspace,
            ),
            patch(
                "sigma.project_collaboration.cloud_auth.current_principal",
                return_value=self.outsider,
            ),
            self.assertRaisesRegex(ValueError, "access denied"),
        ):
            shared.retry_failed_notifications(self.path)
        self.assertEqual(shared.retry_failed_notifications(self.path), 1)
        self.assertEqual(shared.summary(self.path)["failed_notifications"], 0)
        with shared._db() as db:
            row = db.execute(
                "SELECT attempts,failed_at FROM shared_email_outbox WHERE id='failed-notice'"
            ).fetchone()
        self.assertEqual(row["attempts"], 0)
        self.assertIsNone(row["failed_at"])

    def test_local_summary_explicitly_has_no_collaborator_or_failed_mail(self) -> None:
        with patch("sigma.project_collaboration.cloud_workspaces.current", return_value=None):
            data = shared.summary(self.path)
        self.assertIsNone(data["owner"])
        self.assertEqual(data["collaborators"], [])
        self.assertEqual(data["failed_notifications"], 0)

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
        self.assertEqual(shared.normalize_collaborator("brian@gmail.com"), "brian@gmail.com")
        for address in ("a..b@gmail.com", "bad@@gmail.com", "foo@-evil.org"):
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
