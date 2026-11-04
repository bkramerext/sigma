"""Provider-free tests for project email attachment and SMTP behavior."""

from __future__ import annotations

import json
import tempfile
import unittest
from email.message import EmailMessage
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from sigma import cloud_auth, project_email
from sigma.project_bundle import import_bundle, portable_bundle, read_file
from sigma.projects import ProjectError


class ProjectEmailTests(unittest.TestCase):
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
