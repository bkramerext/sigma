"""Offline tests for Gmail API invitation transport."""

import base64
import json
from email import message_from_bytes
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, main
from unittest.mock import patch
from urllib.parse import parse_qs

from sigma.gmail_delivery import SEND_ENDPOINT, TOKEN_ENDPOINT, send_invitation


class FakeResponse:
    status = 200

    def __init__(self, data):
        self.data = BytesIO(json.dumps(data).encode())

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, size=-1):
        return self.data.read(size)


class GmailDeliveryTests(TestCase):
    def test_refresh_and_send(self):
        with TemporaryDirectory() as directory:
            token_file = Path(directory) / "gmail-token.json"
            token_file.write_text(
                json.dumps(
                    {
                        "client_id": "client-id",
                        "client_secret": "client-secret",
                        "refresh_token": "refresh-token",
                    }
                )
            )
            calls = []

            def fake_urlopen(request, timeout):
                calls.append(request)
                if request.full_url == TOKEN_ENDPOINT:
                    self.assertEqual(
                        parse_qs(request.data.decode())["grant_type"], ["refresh_token"]
                    )
                    return FakeResponse({"access_token": "access-token"})
                self.assertEqual(request.full_url, SEND_ENDPOINT)
                self.assertEqual(request.get_header("Authorization"), "Bearer access-token")
                raw = json.loads(request.data)["raw"]
                message = message_from_bytes(base64.urlsafe_b64decode(raw))
                self.assertEqual(message["From"], "zetacontinuation@gmail.com")
                self.assertEqual(message["To"], "zetacontinuation@gmail.com")
                decoded_payload = message.get_payload(decode=True)
                assert isinstance(decoded_payload, bytes)
                self.assertIn("applicant@example.com", decoded_payload.decode())
                return FakeResponse({"id": "message-id"})

            env = {
                "SIGMA_INVITATION_GMAIL_TOKEN_FILE": str(token_file),
                "SIGMA_INVITATION_GMAIL_SENDER": "zetacontinuation@gmail.com",
            }
            with (
                patch.dict("os.environ", env),
                patch("sigma.gmail_delivery.urlopen", side_effect=fake_urlopen),
            ):
                send_invitation(
                    "applicant@example.com", 123, recipient=env["SIGMA_INVITATION_GMAIL_SENDER"]
                )
            self.assertEqual(len(calls), 2)

    def test_requires_configuration(self):
        with (
            patch.dict(
                "os.environ",
                {
                    "SIGMA_INVITATION_GMAIL_TOKEN_FILE": "",
                    "SIGMA_INVITATION_GMAIL_SENDER": "",
                },
            ),
            self.assertRaisesRegex(RuntimeError, "not configured"),
        ):
            send_invitation("applicant@example.com", 123, recipient="zetacontinuation@gmail.com")

    def test_does_not_leak_token_errors(self):
        with TemporaryDirectory() as directory:
            token_file = Path(directory) / "gmail-token.json"
            token_file.write_text(
                json.dumps(
                    {
                        "client_id": "id",
                        "client_secret": "secret",
                        "refresh_token": "secret-refresh",
                    }
                )
            )
            env = {
                "SIGMA_INVITATION_GMAIL_TOKEN_FILE": str(token_file),
                "SIGMA_INVITATION_GMAIL_SENDER": "zetacontinuation@gmail.com",
            }
            with (
                patch.dict("os.environ", env),
                patch("sigma.gmail_delivery.urlopen", side_effect=OSError("secret-refresh")),
                self.assertRaisesRegex(RuntimeError, "could not be delivered") as raised,
            ):
                send_invitation(
                    "applicant@example.com", 123, recipient=env["SIGMA_INVITATION_GMAIL_SENDER"]
                )
            self.assertNotIn("secret-refresh", str(raised.exception))


if __name__ == "__main__":
    main()
