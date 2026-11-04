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
from sigma.project_bundle import import_bundle, portable_bundle, read_file
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
            target = root / "recipient.json"
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
            import_bundle(payload, target)
            imported = json.loads(read_file(target, f"research-sessions/{session_id}.json"))
            self.assertEqual(imported["status"], "stopped")
            self.assertTrue(imported["imported_via_bundle"])
            self.assertEqual(imported["project_id"], project_id)
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
        self.assertIsNone(
            project_email._reserve_delivery("subject:b", str(uuid4()), "other", 1)
        )
        with patch.object(project_email, "DAILY_GLOBAL_LIMIT", 6):
            with self.assertRaises(project_email.MailRateLimit):
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
                    for attempt in range(2):
                        with self.assertRaises(project_email.MailDispatchConflict):
                            project_email.send_project_email(
                                "/project.json",
                                "first@example.com second@example.com",
                                "hello",
                                "project",
                                None,
                                identity,
                            )
                    sending.assert_called_once()
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
    def test_repeated_send_returns_original_without_sending_twice(
        self, inspect, _bundle, smtp
    ):
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
            imported = json.loads(
                read_file(receiver, f"research-sessions/{session_id}.json")
            )
            self.assertTrue(imported["imported_via_bundle"])
            model = next(iter(research_sessions.TOKEN_PRICES_PER_MILLION))
            credential = {"mode": "api_key", "identity": "recipient-provider"}
            settings = {"model": model, "reasoning_effort": "high"}
            with patch.object(research_sessions.cloud_research, "billing_enabled", return_value=False):
                research_sessions._rebind_imported_transport(imported, credential, settings)
            self.assertEqual(imported["mode"], "api_key")
            self.assertEqual(imported["model"], model)
            self.assertEqual(imported["steps"], initial["steps"])
            self.assertEqual(len(imported["transport_change_history"]), 1)
            self.assertFalse(imported["imported_via_bundle"])
            with self.assertRaises(ProjectError):
                research_sessions._rebind_imported_transport(
                    imported, {"mode": "chatgpt", "identity": "other"}, settings
                )

    def test_unsettled_provider_reservations_block_cross_account_handoff(self):
        record = {
            "imported_via_bundle": True,
            "status": "stopped",
            "mode": "chatgpt",
            "steps": [{"status": "interrupted", "attempt_status": "unknown"}],
            "hard_budget_ledger": None,
        }
        with self.assertRaisesRegex(ProjectError, "interrupted"):
            research_sessions._validate_imported_transport_change(record, next_model="gpt-5")
        record["steps"] = []
        record["hard_budget_ledger"] = {
            "blocked_reason": "Provider call outcome or usage is unknown",
            "calls": [{"status": "unknown"}],
        }
        with self.assertRaisesRegex(ProjectError, "unsettled"):
            research_sessions._validate_imported_transport_change(record, next_model="gpt-5")

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
            cloud_auth.send_smtp_message(message, ["a@example.com", "b@example.com"])
        self.assertEqual(message["To"], "sender@example.com")
        self.assertEqual(message["Bcc"], "a@example.com, b@example.com")
        smtp.return_value.__enter__.return_value.send_message.assert_called_once_with(
            message,
            from_addr="sender@example.com",
            to_addrs=["a@example.com", "b@example.com"],
        )


if __name__ == "__main__":
    unittest.main()
