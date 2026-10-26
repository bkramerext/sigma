"""Offline tests for Gmail API invitation transport."""

import base64
import json
from email import message_from_bytes
from io import BytesIO
from urllib.parse import parse_qs

import pytest

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


def test_gmail_invitation_refreshes_token_and_sends(monkeypatch, tmp_path):
    token_file = tmp_path / "gmail-token.json"
    token_file.write_text(json.dumps({
        "client_id": "client-id",
        "client_secret": "client-secret",
        "refresh_token": "refresh-token",
    }))
    monkeypatch.setenv("SIGMA_INVITATION_GMAIL_TOKEN_FILE", str(token_file))
    monkeypatch.setenv("SIGMA_INVITATION_GMAIL_SENDER", "zetacontinuation@gmail.com")
    calls = []

    def fake_urlopen(request, timeout):
        calls.append(request)
        if request.full_url == TOKEN_ENDPOINT:
            assert parse_qs(request.data.decode())["grant_type"] == ["refresh_token"]
            return FakeResponse({"access_token": "access-token"})
        assert request.full_url == SEND_ENDPOINT
        assert request.get_header("Authorization") == "Bearer access-token"
        raw = json.loads(request.data)["raw"]
        message = message_from_bytes(base64.urlsafe_b64decode(raw))
        assert message["From"] == "zetacontinuation@gmail.com"
        assert message["To"] == "zetacontinuation@gmail.com"
        assert "applicant@example.com" in message.get_payload(decode=True).decode()
        return FakeResponse({"id": "message-id"})

    monkeypatch.setattr("sigma.gmail_delivery.urlopen", fake_urlopen)
    send_invitation("applicant@example.com", 123, recipient="zetacontinuation@gmail.com")
    assert len(calls) == 2


def test_gmail_invitation_requires_configuration(monkeypatch):
    monkeypatch.delenv("SIGMA_INVITATION_GMAIL_TOKEN_FILE", raising=False)
    monkeypatch.delenv("SIGMA_INVITATION_GMAIL_SENDER", raising=False)
    with pytest.raises(RuntimeError, match="not configured"):
        send_invitation("applicant@example.com", 123, recipient="zetacontinuation@gmail.com")


def test_gmail_invitation_does_not_leak_token_errors(monkeypatch, tmp_path):
    token_file = tmp_path / "gmail-token.json"
    token_file.write_text(json.dumps({
        "client_id": "id", "client_secret": "secret", "refresh_token": "secret-refresh"
    }))
    monkeypatch.setenv("SIGMA_INVITATION_GMAIL_TOKEN_FILE", str(token_file))
    monkeypatch.setenv("SIGMA_INVITATION_GMAIL_SENDER", "zetacontinuation@gmail.com")

    def fail(_request, timeout):
        raise OSError("secret-refresh")

    monkeypatch.setattr("sigma.gmail_delivery.urlopen", fail)
    with pytest.raises(RuntimeError, match="could not be delivered") as exc:
        send_invitation("applicant@example.com", 123, recipient="zetacontinuation@gmail.com")
    assert "secret-refresh" not in str(exc.value)
