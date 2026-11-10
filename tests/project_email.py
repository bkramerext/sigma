"""Provider-free tests for project email attachment and SMTP behavior."""

from __future__ import annotations

import json
import smtplib
import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from email.message import EmailMessage
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from sigma import cloud_auth, project_email, research_sessions
from sigma.project_bundle import import_bundle, list_files, portable_bundle, read_file
from sigma.projects import ProjectError


class ProjectEmailTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        patcher = patch.object(
            project_email,
            "_delivery_database_path",
            return_value=Path(directory.name) / "mail.sqlite3",
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_parse_recipients_and_reject_bad_input(self):
        self.assertEqual(
            project_email.parse_recipients(
                "First@Example.com,\nsecond@example.com first@example.com"
            ),
            ["first@example.com", "second@example.com"],
        )
        for invalid in ("", "bad@example.com;other@example.com", "not-an-email"):
            with self.subTest(invalid=invalid), self.assertRaises(ProjectError):
                project_email.parse_recipients(invalid)
        with self.assertRaises(ProjectError):
            project_email.parse_recipients(" ".join(f"user{i}@example.com" for i in range(11)))

    def test_mail_bundle_import_retains_stopped_sessions_but_no_papers(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.json"
            target = root / "recipient.sigma"
            project_id = str(uuid4())
            session_id = str(uuid4())
            members = {
                "project.json": json.dumps(
                    {"schema_version": 11, "id": project_id, "title": "Shared Test"}
                ).encode(),
                f"research-sessions/{session_id}.json": json.dumps(
                    {
                        "id": session_id,
                        "project_id": project_id,
                        "project_path": "/sender/old-project.json",
                        "session_number": 2,
                        "status": "stopped",
                    }
                ).encode(),
                "artifacts/evidence.bin": b"\x00real\xff",
                "artifacts/papers/old.json": b'{"paper_id":"old"}',
                "artifacts/papers/old.pdf": b"%PDF-1.4",
            }
            source.write_text(json.dumps(portable_bundle(members)), encoding="utf-8")
            view = SimpleNamespace(project=SimpleNamespace(title="Shared Test"))
            with (
                patch.object(project_email, "project_path", return_value=source),
                patch.object(project_email, "inspect_project", return_value=view),
            ):
                raw, filename = project_email.email_project_bundle(str(source))
            payload = json.loads(raw)
            self.assertEqual(filename, "sigma-Shared-Test.json")
            self.assertNotIn("artifacts/papers/old.json", payload["files"])
            self.assertNotIn("artifacts/papers/old.pdf", payload["files"])
            self.assertIn(f"research-sessions/{session_id}.json", payload["files"])
            from sigma.project_transfer import import_project

            import_project(payload, target)
            session_paths = [
                name
                for name in list_files(target)
                if name.startswith("research-sessions/")
                and name.endswith(".json")
                and name not in {"research-sessions/sequence.json", "research-sessions/limits.json"}
            ]
            self.assertEqual(len(session_paths), 1)
            imported = json.loads(read_file(target, session_paths[0]))
            self.assertNotEqual(imported["id"], session_id)
            self.assertEqual(imported["source_session_id"], session_id)
            self.assertEqual(imported["status"], "stopped")
            self.assertTrue(imported["imported_via_bundle"])
            self.assertNotEqual(imported["project_id"], project_id)
            self.assertEqual(
                imported["project_id"], json.loads(read_file(target, "project.json"))["id"]
            )
            self.assertEqual(imported["project_path"], str(target.resolve()))
            self.assertEqual(read_file(target, "artifacts/evidence.bin"), b"\x00real\xff")

    @patch.object(project_email.cloud_auth, "send_smtp_message")
    @patch.object(
        project_email, "email_project_bundle", return_value=(b'{"files":{}}', "shared.json")
    )
    @patch.object(project_email, "inspect_project")
    def test_attachments_and_privacy(self, inspect, bundle, smtp):
        inspect.return_value.project.title = "Subject"
        with (
            patch.object(
                project_email.papers,
                "list_papers",
                return_value=[
                    {"paper_id": "p1", "pdf_available": True},
                ],
            ),
            patch.object(project_email.papers, "paper_download_basename", return_value="paper-v1"),
            patch.object(project_email.papers, "get_pdf", return_value=b"%PDF"),
            patch.object(project_email.papers, "paper_tex", return_value=r"\begin{document}"),
        ):
            count = project_email.send_project_email(
                "/project.json", "one@example.com two@example.com", "Hello", "pdf_tex", "p1"
            )
        self.assertEqual(count, 2)
        self.assertTrue(bundle.called)
        message, recipients = smtp.call_args.args
        self.assertEqual(recipients, ["one@example.com", "two@example.com"])
        self.assertEqual(message["Subject"], "SIGMA project: Subject")
        self.assertIn("Hello", message.get_body(preferencelist=("plain",)).get_content())
        attachments = list(message.iter_attachments())
        self.assertEqual(
            [attachment.get_filename() for attachment in attachments],
            ["shared.json", "paper-v1.pdf", "paper-v1.tex"],
        )
        self.assertEqual(attachments[1].get_payload(decode=True), b"%PDF")
        self.assertEqual(attachments[2].get_payload(decode=True), b"\\begin{document}")

    @patch.object(project_email.cloud_auth, "send_smtp_message")
    @patch.object(project_email, "email_project_bundle", return_value=(b"{}", "project.json"))
    @patch.object(project_email, "inspect_project")
    def test_missing_paper_is_never_emailed(self, inspect, _bundle, smtp):
        inspect.return_value.project.title = "Sample"
        with (
            patch.object(project_email.papers, "list_papers", return_value=[]),
            self.assertRaisesRegex(ProjectError, "no longer available"),
        ):
            project_email.send_project_email(
                "/project.json", "one@example.com", "", "pdf", "missing"
            )
        smtp.assert_not_called()

    @patch.object(project_email.cloud_auth, "send_smtp_message")
    @patch.object(project_email, "email_project_bundle")
    @patch.object(project_email, "inspect_project")
    def test_size_limit_does_not_send(self, inspect, bundle, smtp):
        inspect.return_value.project.title = "Sample"
        bundle.return_value = (b"X" * (project_email.MAX_ATTACHMENT_BYTES + 1), "project.json")
        with self.assertRaisesRegex(ProjectError, "size limit"):
            project_email.send_project_email(
                "/project.json", "one@example.com", "", "project", None
            )
        smtp.assert_not_called()

    def test_concurrent_reservation_and_idempotent_completion(self):
        identity = str(uuid4())

        def reserve():
            try:
                return project_email._reserve_delivery("subject:alice", identity, "digest", 1)
            except project_email.MailDispatchConflict:
                return "duplicate"

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _index: reserve(), range(2)))
        self.assertCountEqual(results, [None, "duplicate"])
        project_email._finish_delivery("subject:alice", identity, "sent", 1)
        self.assertEqual(
            project_email._reserve_delivery("subject:alice", identity, "digest", 1),
            1,
        )
        with self.assertRaises(project_email.MailDispatchConflict):
            project_email._reserve_delivery("subject:alice", identity, "changed", 1)

    def test_per_sender_and_global_quotas_survive_new_requests(self):
        for index in range(project_email.HOURLY_SEND_LIMIT):
            request_id = str(uuid4())
            project_email._reserve_delivery("subject:a", request_id, str(index), 2)
            project_email._finish_delivery("subject:a", request_id, "sent", 2)
        with self.assertRaises(project_email.MailRateLimit):
            project_email._reserve_delivery("subject:a", str(uuid4()), "more", 1)
        self.assertIsNone(project_email._reserve_delivery("subject:b", str(uuid4()), "other", 1))
        with (
            patch.object(project_email, "DAILY_GLOBAL_LIMIT", 6),
            self.assertRaises(project_email.MailRateLimit),
        ):
            project_email._reserve_delivery("subject:c", str(uuid4()), "global", 1)

    def test_partial_and_unknown_smtp_are_not_replayed(self):
        for outcome in ("partial", "unknown"):
            with self.subTest(outcome=outcome):
                identity = str(uuid4())
                with (
                    patch.object(project_email, "inspect_project") as inspect,
                    patch.object(
                        project_email,
                        "email_project_bundle",
                        return_value=(b"{}", "example.json"),
                    ),
                    patch.object(project_email.cloud_auth, "current_principal") as principal,
                    patch.object(cloud_auth, "secret_value", return_value="secret"),
                    patch.dict(
                        "os.environ",
                        {"SIGMA_INVITATION_SMTP_USERNAME": "sender@example.com"},
                    ),
                    patch.object(cloud_auth.smtplib, "SMTP") as smtp,
                ):
                    inspect.return_value.project.title = "Project"
                    principal.return_value = SimpleNamespace(
                        subject="alice", email="alice@example.com"
                    )
                    sending = smtp.return_value.__enter__.return_value.send_message
                    if outcome == "partial":
                        sending.return_value = {"second@example.com": (550, b"no")}
                    else:
                        sending.side_effect = smtplib.SMTPServerDisconnected("after DATA")
                    initial_error = None
                    for attempt in range(2):
                        with self.assertRaises(project_email.MailDispatchConflict) as caught:
                            project_email.send_project_email(
                                "/project.json",
                                "first@example.com second@example.com",
                                "hello",
                                "project",
                                None,
                                identity,
                            )
                        if attempt == 0:
                            initial_error = str(caught.exception)
                    sending.assert_called_once()
                    if outcome == "partial":
                        self.assertIn("second@example.com", initial_error or "")
                    with sqlite3.connect(project_email._delivery_database_path()) as db:
                        self.assertEqual(
                            db.execute(
                                "SELECT state,accepted FROM project_email_dispatches "
                                "WHERE request_id=?",
                                (identity,),
                            ).fetchone(),
                            (outcome, 1 if outcome == "partial" else 0),
                        )

    @patch.object(project_email.cloud_auth, "send_smtp_message")
    @patch.object(project_email, "email_project_bundle", return_value=(b"{}", "project.json"))
    @patch.object(project_email, "inspect_project")
    def test_repeated_send_returns_original_without_sending_twice(self, inspect, _bundle, smtp):
        inspect.return_value.project.title = "Title"
        identity = str(uuid4())
        for _ in range(2):
            self.assertEqual(
                project_email.send_project_email(
                    "/project.json", "first@example.com", "Hi", "project", None, identity
                ),
                1,
            )
        smtp.assert_called_once()

    @patch.object(project_email.cloud_auth, "send_smtp_message")
    @patch.object(project_email, "email_project_bundle", return_value=(b"{}", "project.json"))
    @patch.object(project_email, "inspect_project")
    def test_verified_sender_reply_to(self, inspect, _bundle, smtp):
        inspect.return_value.project.title = "Title"
        with patch.object(
            cloud_auth,
            "current_principal",
            return_value=SimpleNamespace(subject="alice", email="alice@example.org"),
        ):
            project_email.send_project_email(
                "/project.json", "bob@example.org", "", "project", None
            )
        self.assertEqual(smtp.call_args.kwargs["reply_to"], "alice@example.org")

    def test_imported_session_transport_handoff_preserves_history(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sender = root / "sender.json"
            receiver = root / "receiver.json"
            project_id = str(uuid4())
            session_id = str(uuid4())
            initial = {
                "id": session_id,
                "project_id": project_id,
                "project_path": str(sender),
                "session_number": 1,
                "status": "stopped",
                "mode": "chatgpt",
                "model": "gpt-5",
                "reasoning_effort": "high",
                "identity_hash": "old-identity",
                "steps": [{"id": str(uuid4()), "status": "completed"}],
                "events": [],
                "estimated_cost_usd": None,
                "hard_budget_ledger": None,
            }
            sender.write_text(
                json.dumps(
                    portable_bundle(
                        {
                            "project.json": json.dumps(
                                {"schema_version": 11, "id": project_id, "title": "Shared"}
                            ).encode(),
                            f"research-sessions/{session_id}.json": json.dumps(initial).encode(),
                        }
                    )
                )
            )
            import_bundle(json.loads(sender.read_text()), receiver)
            imported_path = next(
                name
                for name in list_files(receiver)
                if name.startswith("research-sessions/")
                and name.endswith(".json")
                and name not in {"research-sessions/limits.json", "research-sessions/sequence.json"}
            )
            imported = json.loads(read_file(receiver, imported_path))
            self.assertNotEqual(imported["id"], session_id)
            self.assertTrue(imported["imported_via_bundle"])
            model = next(iter(research_sessions.TOKEN_PRICES_PER_MILLION))
            credential = {"mode": "api_key", "identity": "recipient-provider"}
            settings = {"model": model, "reasoning_effort": "high"}
            with (
                patch.object(
                    research_sessions.cloud_research, "billing_enabled", return_value=False
                ),
                patch.object(research_sessions.session_log, "append"),
            ):
                research_sessions._rebind_provider_transport(imported, credential, settings)
            self.assertEqual(imported["mode"], "api_key")
            self.assertEqual(imported["model"], model)
            self.assertEqual(imported["steps"], initial["steps"])
            self.assertEqual(len(imported["transport_change_history"]), 1)
            self.assertFalse(imported["imported_via_bundle"])
            # Imported projects remain portable after their first switch.
            with patch.object(
                research_sessions.cloud_research, "billing_enabled", return_value=False
            ):
                research_sessions._rebind_provider_transport(
                    imported, {"mode": "chatgpt", "identity": "other"}, settings
                )
            self.assertEqual(imported["mode"], "chatgpt")
            self.assertEqual(imported["steps"], initial["steps"])
            self.assertEqual(len(imported["transport_change_history"]), 2)

    def test_unsettled_provider_reservations_block_cross_account_handoff(self):
        record = {
            "imported_via_bundle": True,
            "status": "stopped",
            "mode": "chatgpt",
            "steps": [{"status": "interrupted", "attempt_status": "unknown"}],
            "hard_budget_ledger": None,
        }
        with self.assertRaisesRegex(ProjectError, "interrupted"):
            research_sessions._validate_provider_transport_change(record, next_model="gpt-5")
        record["steps"] = []
        record["hard_budget_ledger"] = {
            "blocked_reason": "Provider call outcome or usage is unknown",
            "calls": [{"status": "unknown"}],
        }
        with self.assertRaisesRegex(ProjectError, "unsettled"):
            research_sessions._validate_provider_transport_change(record, next_model="gpt-5")

    def test_rebased_imports_have_private_session_ids_and_repaired_links(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project_id = str(uuid4())
            first, second = str(uuid4()), str(uuid4())
            source = root / "source.json"
            refs = {"primary": first, "related": [second, f"research-sessions/{first}.json"]}
            members = {
                "project.json": json.dumps(
                    {"schema_version": 11, "id": project_id, "title": "Two session sample"}
                ).encode(),
                f"research-sessions/{first}.json": json.dumps(
                    {
                        "id": first,
                        "project_id": project_id,
                        "project_path": str(source),
                        "session_number": 1,
                        "status": "stopped",
                        "linked_session_id": second,
                        "idempotency_key": "sender-request",
                    }
                ).encode(),
                f"research-sessions/{second}.json": json.dumps(
                    {
                        "id": second,
                        "project_id": project_id,
                        "project_path": str(source),
                        "session_number": 2,
                        "status": "stopped",
                        "linked_session_id": first,
                        "idempotency_key": "sender-request-2",
                    }
                ).encode(),
                "artifacts/session-references.json": json.dumps(refs).encode(),
                "artifacts/binary.bin": b"\\x00\\xff",
            }
            bundle = portable_bundle(members)
            copies = []
            for label in ("a", "b"):
                target = root / f"recipient-{label}.json"
                import_bundle(bundle, target)
                sessions = [
                    json.loads(read_file(target, name))
                    for name in list_files(target)
                    if name.startswith("research-sessions/") and name.endswith(".json")
                ]
                self.assertEqual(len(sessions), 2)
                mapped = {item["source_session_id"]: item for item in sessions}
                self.assertEqual(set(mapped), {first, second})
                self.assertEqual(mapped[first]["linked_session_id"], mapped[second]["id"])
                self.assertEqual(mapped[second]["linked_session_id"], mapped[first]["id"])
                self.assertNotIn(first, [item["id"] for item in sessions])
                self.assertNotIn(second, [item["id"] for item in sessions])
                self.assertNotEqual(mapped[first]["idempotency_key"], "sender-request")
                rewritten = json.loads(read_file(target, "artifacts/session-references.json"))
                self.assertEqual(rewritten["primary"], mapped[first]["id"])
                self.assertEqual(rewritten["related"][0], mapped[second]["id"])
                self.assertEqual(
                    rewritten["related"][1],
                    f"research-sessions/{mapped[first]['id']}.json",
                )
                self.assertEqual(read_file(target, "artifacts/binary.bin"), b"\\x00\\xff")
                copies.append({item["id"] for item in sessions})
            self.assertTrue(copies[0].isdisjoint(copies[1]))

    def test_definite_no_send_can_retry_with_same_uuid_but_is_capped(self):
        identity = str(uuid4())
        sender = "subject:alice"
        self.assertIsNone(project_email._reserve_delivery(sender, identity, "payload", 2))
        for attempt in range(1, project_email.MAX_SEND_ATTEMPTS):
            project_email._finish_delivery(sender, identity, "failed", 0)
            self.assertIsNone(project_email._reserve_delivery(sender, identity, "payload", 2))
        project_email._finish_delivery(sender, identity, "failed", 0)
        with self.assertRaises(project_email.MailDispatchConflict):
            project_email._reserve_delivery(sender, identity, "payload", 2)
        with sqlite3.connect(project_email._delivery_database_path()) as db:
            self.assertEqual(
                db.execute(
                    "SELECT attempts FROM project_email_dispatches WHERE request_id=?",
                    (identity,),
                ).fetchone()[0],
                project_email.MAX_SEND_ATTEMPTS,
            )

    @patch.object(project_email.cloud_auth, "send_smtp_message")
    @patch.object(project_email, "email_project_bundle", return_value=(b"{}", "shared.json"))
    @patch.object(project_email, "inspect_project")
    def test_failed_smtp_request_retries_without_double_dispatch(self, inspect, _bundle, smtp):
        inspect.return_value.project.title = "Project"
        identity = str(uuid4())
        smtp.side_effect = [
            cloud_auth.SMTPDeliveryError("SMTP credentials missing", state="failed"),
            None,
        ]
        with self.assertRaises(project_email.MailDeliveryNotSent):
            project_email.send_project_email(
                "/project.json", "bob@example.com", "", "project", None, identity
            )
        self.assertEqual(
            project_email.send_project_email(
                "/project.json", "bob@example.com", "", "project", None, identity
            ),
            1,
        )
        self.assertEqual(smtp.call_count, 2)

    @patch.object(project_email.cloud_auth, "send_smtp_message")
    @patch.object(project_email, "email_project_bundle", return_value=(b"{}", "shared.json"))
    @patch.object(project_email, "inspect_project")
    def test_local_reply_to_can_use_explicit_operator_contact(self, inspect, _bundle, smtp):
        inspect.return_value.project.title = "Project"
        with (
            patch.object(cloud_auth, "current_principal", return_value=None),
            patch.dict(
                "os.environ",
                {
                    "SIGMA_PROJECT_EMAIL_REPLY_TO": "researcher@example.org",
                    "SIGMA_INVITATION_SMTP_USERNAME": "relay@example.org",
                },
            ),
        ):
            project_email.send_project_email(
                "/project.json", "recipient@example.org", "", "project", None
            )
        self.assertEqual(smtp.call_args.kwargs["reply_to"], "researcher@example.org")

    def test_smtp_envelope_recipients_are_bcc(self):
        message = EmailMessage()
        message["Subject"] = "Project"
        message.set_content("Body")
        with (
            patch.dict(
                "os.environ",
                {
                    "SIGMA_INVITATION_SMTP_USERNAME": "sender@example.com",
                    "SIGMA_INVITATION_SMTP_HOST": "mail.example.com",
                    "SIGMA_INVITATION_SMTP_PORT": "587",
                },
            ),
            patch.object(cloud_auth, "secret_value", return_value="secret"),
            patch.object(cloud_auth.smtplib, "SMTP") as smtp,
        ):
            smtp.return_value.__enter__.return_value.send_message.return_value = {}
            cloud_auth.send_smtp_message(
                message, ["a@example.com", "b@example.com"], reply_to="author@example.org"
            )
        self.assertEqual(message["Reply-To"], "author@example.org")
        self.assertEqual(message["To"], "sender@example.com")
        self.assertEqual(message["Bcc"], "a@example.com, b@example.com")
        smtp.return_value.__enter__.return_value.send_message.assert_called_once_with(
            message,
            from_addr="sender@example.com",
            to_addrs=["a@example.com", "b@example.com"],
        )


if __name__ == "__main__":
    unittest.main()
