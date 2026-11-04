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
            messages.append(message_from_bytes(base64.urlsafe_b64decode(raw), policy=policy.default))
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
                emailed = self.client.post(
                    "/api/projects/email",
                    json={
                        "request_id": str(uuid4()),
                        "path": "/project.json",
                        "recipients": "recipient@example.org",
                        "body": "Here is the project",
                        "mode": "pdf_tex",
                        "paper_id": "paper-1",
                    },
                    headers={"Origin": "http://127.0.0.1:5173"},
                )
            self.assertEqual(emailed.status_code, 200, emailed.text)
            self.assertEqual(emailed.json(), {"sent": 1})

        self.assertEqual(calls.count(gmail_delivery.TOKEN_ENDPOINT), 2)
        self.assertEqual(calls.count(gmail_delivery.SEND_ENDPOINT), 2)
        self.assertEqual(
            [m["Subject"] for m in messages],
            [
                "New SIGMA feedback",
                "SIGMA project: Attachment Test",
            ],
        )
        self.assertEqual(messages[0]["To"], "admin@example.org")
        self.assertEqual(messages[1]["To"], "recipient@example.org")
        self.assertIn(
            "Please improve the About dialog feedback",
            messages[0].get_payload(decode=True).decode(),
        )
        self.assertEqual(list(messages[0].iter_attachments()), [])
        attachments = list(messages[1].iter_attachments())
        self.assertEqual(
            [item.get_filename() for item in attachments],
            ["sigma-Attachment-Test.json", "paper-v1.pdf", "paper-v1.tex"],
        )
        self.assertEqual(
            [item.get_content_type() for item in attachments],
            ["application/json", "application/pdf", "application/x-tex"],
        )
        self.assertEqual(attachments[0].get_payload(decode=True), b'{"files":{}}')
        self.assertEqual(attachments[1].get_payload(decode=True), b"%PDF-1.7\nfixture")
        self.assertIn(b"begin{document}", attachments[2].get_payload(decode=True))

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

    def test_explicit_empty_settings_disable_local_grant_discovery(self):
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
                "SIGMA_EMAIL_GMAIL_TOKEN_FILE": "",
            },
        ):
            self.assertEqual(cloud_auth.email_env("GMAIL_TOKEN_FILE"), "")


if __name__ == "__main__":
    import unittest

    unittest.main()
