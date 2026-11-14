"""Two-agent chat service and API checks with deterministic provider responses."""

import asyncio
import json
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient

from sigma import chat
from sigma.api import app
from sigma.projects import ProjectError


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
    config = {
        "available": True,
        "message": "Ready.",
        "binding": "api_key",
        "model": "gpt-6.1-sol",
        "reasoning_effort": "low",
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
        TestClient(app) as client,
    ):
        response = client.post("/api/chat/turn", json=body)
        mismatch = client.post("/api/chat/turn", json={**body, "expected_binding": "other"})
        invalid = client.post("/api/chat/turn", json={**body, "speaker": "ai_3"})
    assert response.status_code == 200, response.text
    assert '"type":"started"' in response.text
    assert '"type": "complete", "text": "AI #2 reply."' in response.text
    assert mismatch.status_code == 409
    assert invalid.status_code == 422
    print("PASS chat API SSE completion, credential binding and participant validation")


def main() -> None:
    check_service()
    check_api()


if __name__ == "__main__":
    main()
