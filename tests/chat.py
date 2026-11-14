"""Two-agent chat service and API checks with deterministic provider responses."""

import asyncio
import json
import stat
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient

from sigma import chat, chat_transcripts
from sigma.api import app
from sigma.projects import ProjectError


def check_configuration() -> None:
    credential = {
        "mode": "api_key",
        "token": "fixture-secret",
        "status": "connected",
        "identity": "fixture-account",
    }
    discovery = {
        "connection": {"status": "connected", "guidance": "Ready."},
        "default_model": "gpt-6.1-sol",
        "default_verified": True,
        "message": "Ready.",
        "models": [
            {
                "id": "gpt-6.1-sol",
                "label": "Sol · Balanced ($$)",
                "relative_cost": "$$",
                "efforts": ["low", "medium", "high", "xhigh"],
                "availability": "available",
            },
            {
                "id": "gpt-6-luna",
                "label": "Luna · Economy ($)",
                "relative_cost": "$",
                "efforts": ["low", "medium", "high", "xhigh"],
                "availability": "unavailable",
            },
        ],
    }
    with (
        patch("sigma.chat.auth_context", new=AsyncMock(return_value=credential)),
        patch("sigma.chat.models", new=AsyncMock(return_value=discovery)),
        patch("sigma.chat.cloud_workspaces.enabled", return_value=False),
    ):
        result = asyncio.run(chat.configuration())
    assert result["available"] is True
    assert result["model"] == "gpt-6.1-sol"
    assert result["reasoning_effort"] == "low"
    assert [item["id"] for item in result["models"]] == ["gpt-6.1-sol"]
    assert "fixture-secret" not in json.dumps(result)
    print("PASS chat exposes only verified models and its actual default Thinking level")


def check_service() -> None:
    credential = {
        "mode": "api_key",
        "token": "fixture-token",
        "status": "connected",
        "identity": "api_key",
    }
    output = {
        "id": "resp_fixture",
        "status": "completed",
        "model": "gpt-6.1-sol",
        "output": [
            {
                "type": "message",
                "content": [{"type": "output_text", "text": "A deterministic reply."}],
            }
        ],
        "usage": {
            "input_tokens": 30,
            "output_tokens": 8,
            "input_tokens_details": {"cached_tokens": 0},
        },
    }
    captured: dict = {}

    class Response:
        status_code = 200

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def aiter_bytes(self):
            yield json.dumps(output).encode()

    class Client:
        def __init__(self, **_kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        def stream(self, method, url, *, headers, json):
            captured.update(method=method, url=url, headers=headers, payload=json)
            return Response()

    with (
        patch("sigma.chat.auth_context", new=AsyncMock(return_value=credential)),
        patch(
            "sigma.chat.models",
            new=AsyncMock(
                return_value={
                    "connection": {"status": "connected", "guidance": "Ready."},
                    "models": [{"id": "gpt-6.1-sol", "availability": "available"}],
                }
            ),
        ),
        patch("sigma.chat.cloud_research.billing_enabled", return_value=False),
        patch("sigma.chat.httpx.AsyncClient", Client),
    ):
        result = asyncio.run(
            chat.respond(
                speaker="ai_1",
                messages=[{"speaker": "human", "text": "Question for the pair."}],
                conversation_id=str(uuid4()),
                expected_binding="api_key",
                model="gpt-6.1-sol",
                reasoning_effort="low",
            )
        )
    assert result == "A deterministic reply."
    assert captured["method"] == "POST"
    assert captured["url"] == "https://api.openai.com/v1/responses"
    assert captured["headers"]["Authorization"] == "Bearer fixture-token"
    assert captured["payload"]["store"] is False
    assert captured["payload"]["instructions"] == chat.INSTRUCTIONS["ai_1"]
    assert "Human:\nQuestion for the pair." in captured["payload"]["input"][0]["content"]

    with patch(
        "sigma.chat.auth_context", new=AsyncMock(return_value={**credential, "identity": "changed"})
    ):
        try:
            asyncio.run(
                chat.respond(
                    speaker="ai_1",
                    messages=[{"speaker": "human", "text": "Question."}],
                    conversation_id=str(uuid4()),
                    expected_binding="api_key",
                    model="gpt-6.1-sol",
                    reasoning_effort="low",
                )
            )
        except ProjectError as exc:
            assert "account changed" in str(exc)
        else:
            raise AssertionError("A credential change must stop chat before provider dispatch")

    messages = [{"speaker": "human", "text": "earlier"}] + [
        {"speaker": "ai_1", "text": f"turn {index}"} for index in range(chat.MAX_MESSAGES)
    ]
    transcript = chat._transcript(messages)
    assert "Earlier conversation turns omitted" in transcript
    assert f"turn {chat.MAX_MESSAGES - 1}" in transcript
    print(
        "PASS selected-credential request, no-store payload, binding recheck and bounded transcript"
    )


def check_api() -> None:
    models = [
        {"id": "gpt-6.1-sol", "efforts": ["low", "medium", "high", "xhigh"]},
        {"id": "gpt-6-luna", "efforts": ["low", "medium", "high", "xhigh"]},
    ]
    config = {
        "available": True,
        "message": "Ready.",
        "binding": "api_key",
        "model": "gpt-6.1-sol",
        "reasoning_effort": "low",
        "models": models,
    }
    body = {
        "conversation_id": str(uuid4()),
        "expected_binding": "api_key",
        "speaker": "ai_2",
        "messages": [{"speaker": "human", "text": "Hello."}],
        "model": "gpt-6.1-sol",
        "reasoning_effort": "low",
    }
    with (
        patch("sigma.chat.configuration", new=AsyncMock(return_value=config)),
        patch("sigma.chat.respond", new=AsyncMock(return_value="AI #2 reply.")),
        patch(
            "sigma.chat_transcripts.open_transcript",
            return_value={
                "conversation_id": body["conversation_id"],
                "transcript_name": "fixture.md",
            },
        ),
        patch("sigma.chat_transcripts.append_message") as append_message,
        TestClient(app) as client,
    ):
        opened = client.post("/api/chat/session")
        recorded = client.post(
            "/api/chat/message",
            json={"conversation_id": body["conversation_id"], "speaker": "human", "text": "Hello."},
        )
        response = client.post("/api/chat/turn", json=body)
        mismatch = client.post("/api/chat/turn", json={**body, "expected_binding": "other"})
        invalid = client.post("/api/chat/turn", json={**body, "speaker": "ai_3"})
        invalid_record = client.post(
            "/api/chat/message",
            json={"conversation_id": "bad", "speaker": "human", "text": "Hello."},
        )
        selected = client.post(
            "/api/chat/turn",
            json={**body, "model": "gpt-6-luna", "reasoning_effort": "medium"},
        )
        unsupported = client.post("/api/chat/turn", json={**body, "model": "unreviewed-model"})
    assert opened.status_code == 200 and opened.json()["transcript_name"] == "fixture.md"
    assert recorded.status_code == 204
    append_message.assert_called_once_with(body["conversation_id"], "human", "Hello.")
    assert invalid_record.status_code == 422
    assert response.status_code == 200, response.text
    assert '"type":"started"' in response.text
    assert '"type": "complete", "text": "AI #2 reply."' in response.text
    assert mismatch.status_code == 409
    assert invalid.status_code == 422
    assert selected.status_code == 200
    assert unsupported.status_code == 422
    print("PASS chat API model/thinking validation, SSE completion and participant validation")


def check_transcripts() -> None:
    with TemporaryDirectory() as temp:
        state = Path(temp)
        with patch("sigma.chat_transcripts.state_directory", return_value=state):
            session = chat_transcripts.open_transcript()
            directory = state / "chat-transcripts"
            path = directory / session["transcript_name"]
            assert path.is_file()
            assert session["transcript_name"].endswith(f"_{session['conversation_id']}.md")
            assert len(session["transcript_name"]) > 30
            assert stat.S_IMODE(directory.stat().st_mode) == 0o700
            assert stat.S_IMODE(path.stat().st_mode) == 0o600

            messages = [
                ("human", "Name the *sporadic finite simple groups*."),
                ("ai_1", "The largest is the **Monster**."),
                ("ai_2", r"Its order is \(8.08\times10^{53}\)."),
            ]
            for speaker, text in messages:
                chat_transcripts.append_message(session["conversation_id"], speaker, text)
            content = path.read_text(encoding="utf-8")
            assert content.index("## Human ·") < content.index("## AI #1 ·")
            assert content.index("## AI #1 ·") < content.index("## AI #2 ·")
            assert all(text in content for _, text in messages)

            original = path.read_bytes()
            backup = directory / "transcript-backup.md"
            path.rename(backup)
            path.symlink_to(backup.name)
            try:
                try:
                    chat_transcripts.append_message(session["conversation_id"], "ai_1", "Unsafe")
                except ProjectError:
                    pass
                else:
                    raise AssertionError("Transcript append followed a symlink")
                assert backup.read_bytes() == original
            finally:
                path.unlink()
                backup.rename(path)
    print("PASS timestamped private transcript, ordered append, and symlink rejection")


def main() -> None:
    check_configuration()
    check_service()
    check_api()
    check_transcripts()


if __name__ == "__main__":
    main()
