"""End-to-end local About Feedback and Email Project MIME transport contract.

No provider calls. The same saved Gmail grant must be used for both UI routes,
including PDF and source LaTeX MIME attachments; hosted mode ignores that grant.
"""

from __future__ import annotations

import base64
import json
import os
from email import message_from_bytes, policy
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from cloud_auth_fixture import CLIENT_ID, CloudAuthFixture

from sigma import cloud_auth, gmail_delivery, project_email
from sigma.local_gmail_cli_auth import GMAIL_SEND_SCOPE, _save_grant


class FakeResponse:
    status = 200

    def __init__(self, data):
        self.stream = BytesIO(json.dumps(data).encode())

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, size=-1):
        return self.stream.read(size)


class SharedLocalMailTransportTests(CloudAuthFixture):
    def test_browser_feedback_and_email_project_share_local_gmail_oauth(self):
        messages = []
        calls = []

        def fake_urlopen(request, timeout):
            calls.append(request.full_url)
            if request.full_url == gmail_delivery.TOKEN_ENDPOINT:
                return FakeResponse({"access_token": "fixture-access"})
            self.assertEqual(request.full_url, gmail_delivery.SEND_ENDPOINT)
            raw = json.loads(request.data)["raw"]
            messages.append(
                message_from_bytes(base64.urlsafe_b64decode(raw), policy=policy.default)
            )
            return FakeResponse({"id": "fixture-mail-id"})

        with (
            patch.dict(
                os.environ,
                {
                    "SIGMA_CLOUD_AUTH_LOCAL": "true",
                    "SIGMA_CLOUD_PUBLIC_ORIGIN": "http://127.0.0.1:5173",
                },
            ),
            patch.object(gmail_delivery, "urlopen", side_effect=fake_urlopen),
        ):
            _save_grant(
                sender="admin@example.org",
                subject="google-sub-1",
                client_id=CLIENT_ID,
                client_secret="fixture-secret",
                refresh_token="fixture-refresh",
                scope=GMAIL_SEND_SCOPE,
            )
            self.assertEqual(
                cloud_auth.email_env("GMAIL_TOKEN_FILE"),
                str(self.root / "gmail-send-token.json"),
            )
            self.assertEqual(cloud_auth.email_env("GMAIL_SENDER"), "admin@example.org")
            signed = self.finish(email="admin@example.org", subject="google-sub-1")
            cfg = cloud_auth.config()
            session_cookie = cloud_auth._cookie_name(cloud_auth.SESSION_COOKIE, cfg)
            self.client.cookies.set(session_cookie, signed.cookies[session_cookie])
            feedback = self.client.post(
                "/api/cloud-auth/feedback",
                json={"message": "Please improve the About dialog feedback."},
                headers={"Origin": "http://127.0.0.1:5173"},
            )
            self.assertEqual(feedback.status_code, 200, feedback.text)
            self.assertEqual(feedback.json()["status"], "received")

            with (
                patch.object(
                    project_email,
                    "inspect_project",
                    return_value=SimpleNamespace(project=SimpleNamespace(title="Attachment Test")),
                ),
                patch.object(
                    project_email,
                    "email_project_bundle",
                    return_value=(b'{"files":{}}', "sigma-Attachment-Test.json"),
                ),
                patch.object(
                    project_email.papers,
                    "list_papers",
                    return_value=[{"paper_id": "paper-1", "pdf_available": True}],
                ),
                patch.object(
                    project_email.papers,
                    "paper_download_basename",
                    return_value="paper-v1",
                ),
                patch.object(project_email.papers, "get_pdf", return_value=b"%PDF-1.7\nfixture"),
                patch.object(
                    project_email.papers,
                    "paper_tex",
                    return_value="\\\\begin{document}fixture\\\\end{document}",
                ),
            ):
                for mode in ("project", "pdf", "pdf_tex"):
                    emailed = self.client.post(
                        "/api/projects/email",
                        json={
                            "request_id": str(uuid4()),
                            "path": "/project.json",
                            "recipients": "recipient@example.org",
                            "body": "Here is the project",
                            "mode": mode,
                            "paper_id": None if mode == "project" else "paper-1",
                        },
                        headers={"Origin": "http://127.0.0.1:5173"},
                    )
                    self.assertEqual(emailed.status_code, 200, emailed.text)
                    self.assertEqual(emailed.json(), {"sent": 1})

        self.assertEqual(calls.count(gmail_delivery.TOKEN_ENDPOINT), 4)
        self.assertEqual(calls.count(gmail_delivery.SEND_ENDPOINT), 4)
        self.assertEqual(
            [m["Subject"] for m in messages],
            [
                "New SIGMA feedback",
                "SIGMA project: Attachment Test",
                "SIGMA project: Attachment Test",
                "SIGMA project: Attachment Test",
            ],
        )
        self.assertEqual(messages[0]["To"], "admin@example.org")
        for message in messages[1:]:
            self.assertEqual(message["To"], "recipient@example.org")
        self.assertIn(
            "Please improve the About dialog feedback",
            messages[0].get_payload(decode=True).decode(),
        )
        self.assertEqual(list(messages[0].iter_attachments()), [])
        expected_filenames = [
            ["sigma-Attachment-Test.json"],
            ["sigma-Attachment-Test.json", "paper-v1.pdf"],
            ["sigma-Attachment-Test.json", "paper-v1.pdf", "paper-v1.tex"],
        ]
        for message, names in zip(messages[1:], expected_filenames, strict=True):
            attachments = list(message.iter_attachments())
            self.assertEqual([item.get_filename() for item in attachments], names)
            self.assertEqual(attachments[0].get_content_type(), "application/json")
            self.assertEqual(attachments[0].get_payload(decode=True), b'{"files":{}}')
            if len(attachments) >= 2:
                self.assertEqual(attachments[1].get_content_type(), "application/pdf")
                self.assertEqual(attachments[1].get_payload(decode=True), b"%PDF-1.7\nfixture")
            if len(attachments) == 3:
                self.assertEqual(attachments[2].get_content_type(), "application/x-tex")
                self.assertIn(b"begin{document}", attachments[2].get_payload(decode=True))

    def test_local_about_feedback_with_signin_shortcut_still_sends(self):
        """Local --signin users have no Google identity row, but can mail the operator."""
        captured = []

        def fake_urlopen(request, timeout):
            if request.full_url == gmail_delivery.TOKEN_ENDPOINT:
                return FakeResponse({"access_token": "fixture-access"})
            raw = json.loads(request.data)["raw"]
            captured.append(
                message_from_bytes(base64.urlsafe_b64decode(raw), policy=policy.default)
            )
            return FakeResponse({"id": "feedback-id"})

        with (
            patch.dict(
                os.environ,
                {
                    "SIGMA_CLOUD_AUTH_LOCAL": "true",
                    "SIGMA_CLOUD_PUBLIC_ORIGIN": "http://127.0.0.1:5173",
                    "SIGMA_LOCAL_AUTO_ADMIN": "true",
                },
            ),
            patch.object(gmail_delivery, "urlopen", side_effect=fake_urlopen),
        ):
            _save_grant(
                sender="admin@example.org",
                subject="google-sub-1",
                client_id=CLIENT_ID,
                client_secret="fixture-secret",
                refresh_token="fixture-refresh",
                scope=GMAIL_SEND_SCOPE,
            )
            self.assertEqual(
                cloud_auth._notification_admin_recipients(cloud_auth.config()),
                ["admin@example.org"],
            )
            sent = self.client.post(
                "/api/cloud-auth/feedback",
                json={"message": "Local About Feedback should notify the operator."},
                headers={"Origin": "http://127.0.0.1:5173"},
            )
            self.assertEqual(sent.status_code, 200, sent.text)
            self.assertEqual(sent.json()["status"], "received")
            with cloud_auth._db(cloud_auth.config()) as db:
                row = db.execute(
                    "SELECT notification_error FROM feedback_requests WHERE id=?",
                    (sent.json()["id"],),
                ).fetchone()
            self.assertIsNone(row["notification_error"])
        self.assertEqual(len(captured), 1)
        self.assertEqual(captured[0]["To"], "admin@example.org")
        self.assertEqual(captured[0]["Subject"], "New SIGMA feedback")
        self.assertIn(
            b"Local About Feedback should notify the operator.",
            captured[0].get_payload(decode=True),
        )

    def test_local_mail_failure_is_not_reported_as_sent(self):
        with (
            patch.dict(
                os.environ,
                {
                    "SIGMA_CLOUD_AUTH_LOCAL": "true",
                    "SIGMA_CLOUD_PUBLIC_ORIGIN": "http://127.0.0.1:5173",
                    "SIGMA_LOCAL_AUTO_ADMIN": "true",
                },
            ),
            patch(
                "sigma.mail_transport.send_message",
                side_effect=RuntimeError("offline simulated failure"),
            ),
        ):
            response = self.client.post(
                "/api/cloud-auth/feedback",
                json={"message": "Please show notification status accurately."},
                headers={"Origin": "http://127.0.0.1:5173"},
            )
            self.assertEqual(response.status_code, 200, response.text)
            self.assertIs(response.json()["email_notification_sent"], False)
            with cloud_auth._db(cloud_auth.config()) as db:
                row = db.execute(
                    "SELECT notification_error FROM feedback_requests WHERE id=?",
                    (response.json()["id"],),
                ).fetchone()
            self.assertEqual(row["notification_error"], "delivery failed")

    def test_hosted_smtp_is_unchanged_by_local_gmail_grant(self):
        _save_grant(
            sender="admin@example.org",
            subject="google-sub-1",
            client_id=CLIENT_ID,
            client_secret="fixture-secret",
            refresh_token="fixture-refresh",
            scope=GMAIL_SEND_SCOPE,
        )
        with (
            patch.dict(
                os.environ,
                {
                    "SIGMA_CLOUD_AUTH_LOCAL": "false",
                    "SIGMA_INVITATION_SMTP_USERNAME": "sender@example.org",
                    "SIGMA_INVITATION_SMTP_PASSWORD": "fixture-password",
                },
            ),
            patch.object(cloud_auth.smtplib, "SMTP") as smtp,
            patch.object(gmail_delivery, "urlopen") as gmail,
            patch.object(
                project_email,
                "inspect_project",
                return_value=SimpleNamespace(project=SimpleNamespace(title="Hosted Test")),
            ),
            patch.object(
                project_email,
                "email_project_bundle",
                return_value=(b"{}", "hosted.json"),
            ),
        ):
            self.assertEqual(cloud_auth.email_env("GMAIL_TOKEN_FILE"), "")
            from cloud_auth_fixture import ORIGIN

            signed = self.finish(email="admin@example.org", subject="google-sub-1")
            self.client.cookies.set(
                cloud_auth.SESSION_COOKIE, signed.cookies[cloud_auth.SESSION_COOKIE]
            )
            feedback = self.client.post(
                "/api/cloud-auth/feedback",
                json={"message": "Hosting SMTP path must remain unchanged."},
                headers={"Origin": ORIGIN},
            )
            self.assertEqual(feedback.status_code, 200, feedback.text)
            self.assertEqual(feedback.json()["status"], "received")
            with cloud_auth._db(cloud_auth.config()) as db:
                row = db.execute(
                    "SELECT notification_error FROM feedback_requests WHERE id=?",
                    (feedback.json()["id"],),
                ).fetchone()
            self.assertIsNone(row["notification_error"])
            emailed = self.client.post(
                "/api/projects/email",
                json={
                    "request_id": str(uuid4()),
                    "path": "/fixture.json",
                    "recipients": "reader@example.org",
                    "body": "",
                    "mode": "project",
                    "paper_id": None,
                },
                headers={"Origin": ORIGIN},
            )
            self.assertEqual(emailed.status_code, 200, emailed.text)
        self.assertEqual(emailed.json(), {"sent": 1})
        gmail.assert_not_called()
        smtp_messages = smtp.return_value.__enter__.return_value.send_message.call_args_list
        self.assertEqual(len(smtp_messages), 2)
        self.assertEqual(smtp_messages[0].args[0]["Subject"], "New SIGMA feedback")
        self.assertEqual(smtp_messages[1].args[0]["Subject"], "SIGMA project: Hosted Test")
        self.assertEqual(
            [item.get_filename() for item in smtp_messages[1].args[0].iter_attachments()],
            ["hosted.json"],
        )

    def test_hosted_email_does_not_see_local_gmail_grant(self):
        with patch.dict(
            os.environ,
            {
                "SIGMA_CLOUD_AUTH_LOCAL": "false",
                "SIGMA_CLOUD_PUBLIC_ORIGIN": "https://sigma.test",
            },
        ):
            _save_grant(
                sender="admin@example.org",
                subject="google-sub-1",
                client_id=CLIENT_ID,
                client_secret="fixture-secret",
                refresh_token="fixture-refresh",
                scope=GMAIL_SEND_SCOPE,
            )
            self.assertEqual(cloud_auth.email_env("GMAIL_TOKEN_FILE"), "")
            self.assertEqual(cloud_auth.email_env("GMAIL_SENDER"), "")

    def test_stale_local_gmail_setting_yields_to_verified_cli_grant(self):
        _save_grant(
            sender="admin@example.org",
            subject="google-sub-1",
            client_id=CLIENT_ID,
            client_secret="fixture-secret",
            refresh_token="fixture-refresh",
            scope=GMAIL_SEND_SCOPE,
        )
        with patch.dict(
            os.environ,
            {
                "SIGMA_CLOUD_AUTH_LOCAL": "true",
                "SIGMA_CLOUD_PUBLIC_ORIGIN": "http://127.0.0.1:5173",
                "SIGMA_EMAIL_GMAIL_TOKEN_FILE": "/missing/old-token.json",
                "SIGMA_EMAIL_GMAIL_SENDER": "old@example.org",
            },
        ):
            self.assertEqual(
                cloud_auth.email_env("GMAIL_TOKEN_FILE"),
                str(self.root / "gmail-send-token.json"),
            )
            self.assertEqual(cloud_auth.email_env("GMAIL_SENDER"), "admin@example.org")


if __name__ == "__main__":
    import unittest

    unittest.main()
