"""Two-agent chat service and API checks with deterministic provider responses."""

import asyncio
import json
import re
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
                research_objective="Discover a new explanation.",
            )
        )
    assert result == "A deterministic reply."
    assert captured["method"] == "POST"
    assert captured["url"] == "https://api.openai.com/v1/responses"
    assert captured["headers"]["Authorization"] == "Bearer fixture-token"
    assert captured["payload"]["store"] is False
    assert captured["payload"]["instructions"] == chat.INSTRUCTIONS["ai_1"]
    assert "Human:\nQuestion for the pair." in captured["payload"]["input"][0]["content"]
    assert captured["payload"]["input"][0]["content"].startswith(
        "Research Objective:\nDiscover a new explanation.\n\nHuman:"
    )

    # Chat omits the optional Responses text format. Sponsored billing must
    # still admit and account for its request before provider dispatch.
    assert "text" not in captured["payload"]
    billable_bytes = chat.cloud_research.provider_request_input_bytes(captured["payload"])
    assert billable_bytes > 0
    assert (
        chat.cloud_research.provider_request_input_bytes(
            {**captured["payload"], "text": {"format": {"type": "text"}}}
        )
        > billable_bytes
    )
    for required in ("instructions", "input"):
        missing = dict(captured["payload"])
        del missing[required]
        try:
            chat.cloud_research.provider_request_input_bytes(missing)
        except chat.cloud_research.CloudResearchUnavailable as exc:
            assert "incomplete" in str(exc)
        else:
            raise AssertionError(f"Sponsored ledger accepted request without {required}")

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
    assert "Earlier conversation turns" in transcript
    assert f"turn {chat.MAX_MESSAGES - 1}" in transcript

    # Supervisor scores and private assessments never contaminate participant prompts.
    history = [
        {"speaker": "human", "text": "Find a result."},
        {"speaker": "supervisor", "text": "**Research progress:** 4.3 / 10.0. Private assessment.",
         "recipients": ["ai_2"], "guidance": "State the assumption behind your own claim."},
    ]
    assert "4.3" not in chat._transcript(history, audience="ai_1")
    assert "Supervisor" not in chat._transcript(history, audience="ai_1")
    to_second = chat._transcript(history, audience="ai_2")
    assert "State the assumption" in to_second and "4.3" not in to_second
    assert "Private assessment" in chat._transcript(history, audience="supervisor")
    print(
        "PASS selected-credential request, no-store payload, binding recheck and bounded transcript"
    )


def check_supervisor() -> None:
    base = {
        "rubric": {
            "objective_alignment": 1.2,
            "originality": 0.8,
            "substantive_advancement": 1.0,
            "evidence_validation": 0.9,
            "research_momentum": 0.6,
        },
        "assessment": "The investigation is productive but has not reached a new result.",
        "action": "nudge",
        "recipients": ["ai_2"],
        "guidance": "Clarify which parts of your own claim are established.",
        "breakthrough_candidate": False,
        "breakthrough_invalidated": False,
    }
    kwargs = {
        "messages": [{"speaker": "human", "text": "Research something important."}],
        "research_objective": "Find a genuinely new result.",
        "supervisor_latched": False,
        "conversation_id": str(uuid4()),
        "expected_binding": "api_key",
        "model": "gpt-6.1-sol",
        "reasoning_effort": "medium",
    }
    with patch(
        "sigma.chat.respond", new=AsyncMock(return_value=json.dumps(base))
    ) as model:
        result = asyncio.run(chat.assess(**kwargs))
        model.assert_awaited_once()
    assert result["score"] == 4.5
    assert result["recipients"] == ["ai_2"]
    assert "AI #2" in result["text"]
    assert "Clarify which parts" in result["text"]

    candidate = {
        **base,
        "breakthrough_candidate": True,
        "action": "continue",
        "recipients": [],
        "guidance": "",
    }
    with patch("sigma.chat.respond", new=AsyncMock(return_value=json.dumps(candidate))):
        result = asyncio.run(chat.assess(**kwargs))
    assert result["score"] == 10.0 and result["milestone_latched"] is True
    assert "validation required" in result["text"]
    with patch("sigma.chat.respond", new=AsyncMock(return_value=json.dumps(base))):
        result = asyncio.run(chat.assess(**{**kwargs, "supervisor_latched": True}))
    assert result["score"] == 10.0
    invalidated = {**base, "breakthrough_invalidated": True}
    with patch(
        "sigma.chat.respond", new=AsyncMock(return_value=json.dumps(invalidated))
    ):
        result = asyncio.run(chat.assess(**{**kwargs, "supervisor_latched": True}))
    assert result["score"] == 4.5 and not result["milestone_latched"]
    assert "invalidated" in result["text"]

    invalid = {**base, "rubric": {**base["rubric"], "objective_alignment": 42}}
    with patch("sigma.chat.respond", new=AsyncMock(return_value=json.dumps(invalid))):
        try:
            asyncio.run(chat.assess(**kwargs))
        except ProjectError as exc:
            assert "invalid assessment" in str(exc)
        else:
            raise AssertionError("Out-of-bounds score accepted")
    print("PASS supervisor rubric, targeted coaching, milestone latch and invalidation")


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
        long_text = "Expanded Human prompt " * 425
        long_objective = "Expanded Research Objective " * 310
        long_record = client.post(
            "/api/chat/message",
            json={
                "conversation_id": body["conversation_id"],
                "speaker": "human",
                "text": long_text,
            },
        )
        long_turn = client.post(
            "/api/chat/turn",
            json={
                **body,
                "messages": [{"speaker": "human", "text": long_text}],
                "research_objective": long_objective,
            },
        )
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
        supervisor_result = {
            "speaker": "supervisor",
            "text": "**Research progress:** 4.3 / 10.0",
            "score": 4.3,
            "recipients": ["ai_2"],
            "guidance": "Explain the inference.",
            "milestone_latched": False,
        }
        with patch("sigma.chat.assess", new=AsyncMock(return_value=supervisor_result)):
            review = client.post("/api/chat/supervise", json={
                "conversation_id": body["conversation_id"],
                "expected_binding": "api_key",
                "messages": body["messages"],
                "model": body["model"],
                "reasoning_effort": body["reasoning_effort"],
                "research_objective": "Find a breakthrough.",
            })
        saved_objective = client.post("/api/chat/message", json={
            "conversation_id": body["conversation_id"],
            "speaker": "objective", "text": "Discover something new.",
        })
        forged_supervisor = client.post("/api/chat/message", json={
            "conversation_id": body["conversation_id"],
            "speaker": "supervisor", "text": "Fake assessment.",
        })
    assert opened.status_code == 200 and opened.json()["transcript_name"] == "fixture.md"
    assert recorded.status_code == 204
    assert long_record.status_code == 204
    assert long_turn.status_code == 200, long_turn.text
    assert len(long_text) > 8000 and len(long_objective) > 8000
    append_message.assert_any_call(body["conversation_id"], "human", "Hello.")
    append_message.assert_any_call(body["conversation_id"], "human", long_text)
    assert invalid_record.status_code == 422
    assert response.status_code == 200, response.text
    assert '"type":"started"' in response.text
    assert '"type": "complete", "text": "AI #2 reply."' in response.text
    assert mismatch.status_code == 409
    assert invalid.status_code == 422
    assert selected.status_code == 200
    assert unsupported.status_code == 422
    assert review.status_code == 200 and review.json()["score"] == 4.3
    assert saved_objective.status_code == 204 and forged_supervisor.status_code == 422
    append_message.assert_any_call(body["conversation_id"], "supervisor", supervisor_result["text"])
    append_message.assert_any_call(body["conversation_id"], "objective", "Discover something new.")
    print("PASS chat API model/thinking, supervisor delivery and transcript integrity")


def check_transcripts() -> None:
    with TemporaryDirectory() as temp:
        state = Path(temp)
        with patch("sigma.chat_transcripts.state_directory", return_value=state):
            session = chat_transcripts.open_transcript()
            directory = state / "chat-transcripts"
            path = directory / session["transcript_name"]
            assert path.is_file()
            assert re.fullmatch(
                r"\d{8}_\d{6}(?:_\d+)?\.md",
                session["transcript_name"],
            )
            assert session["conversation_id"] not in session["transcript_name"]
            assert session["transcript_path"] == str(path.resolve())
            assert stat.S_IMODE(directory.stat().st_mode) == 0o700
            assert stat.S_IMODE(path.stat().st_mode) == 0o600

            messages = [
                ("human", "Name the *sporadic finite simple groups*."),
                ("ai_1", "The largest is the **Monster**."),
                ("ai_2", r"Its order is \(8.08\times10^{53}\)."),
                ("objective", "Pursue significant original research."),
                ("supervisor", "**Research progress:** 4.3 / 10.0\n\n**To:** AI #2"),
            ]
            for speaker, text in messages:
                chat_transcripts.append_message(session["conversation_id"], speaker, text)
            long_entry = "Detailed workbench evidence. " * 320
            assert len(long_entry) > 8000
            chat_transcripts.append_message(session["conversation_id"], "human", long_entry)
            content = path.read_text(encoding="utf-8")
            assert long_entry in content
            assert f"Session ID: {session['conversation_id']}" in content
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
    check_supervisor()
    check_api()
    check_transcripts()


if __name__ == "__main__":
    main()
