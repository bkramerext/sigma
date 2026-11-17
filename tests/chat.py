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

from sigma import chat, chat_supervisor, chat_transcripts
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
                research_objective="Always challenge the assumptions.",
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
        "Research Objective:\nAlways challenge the assumptions.\n\nHuman:"
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
    assert "Earlier conversation turns omitted" in transcript
    assert f"turn {chat.MAX_MESSAGES - 1}" in transcript
    print(
        "PASS selected-credential request, no-store payload, binding recheck and bounded transcript"
    )


def check_streamed_multisegment_completion() -> None:
    from sigma.plan_stream import completed

    response_id = "resp_bounded_fixture"
    text = ["First line.", " Second line."]
    events = [
        {"type": "response.created", "sequence_number": 0, "response": {"id": response_id}},
        {"type": "response.output_text.delta", "sequence_number": 1, "delta": "".join(text)},
        {
            "type": "response.completed",
            "sequence_number": 2,
            "response": {
                "id": response_id,
                "model": "gpt-6.1-sol",
                "status": "completed",
                "output": [
                    {
                        "type": "message",
                        "content": [{"type": "output_text", "text": part} for part in text],
                    }
                ],
            },
        },
    ]

    class FakeStream:
        status_code = 200

        def __init__(self):
            self.headers = {"content-type": "text/event-stream"}

        async def aiter_bytes(self):
            for event in events:
                yield ("data: " + json.dumps(event) + "\\n\\n").encode()

    raw = asyncio.run(completed(FakeStream()))
    assert chat._response_text(raw, "gpt-6.1-sol") == "".join(text)
    print("PASS multi-part completed output matches joined stream text")


def check_response_recovery() -> None:
    completed = {
        "model": "gpt-6.1-sol",
        "status": "completed",
        "output": [{"type": "reasoning"}, {"type": "message", "content": None}],
        "output_text": "Recovered adapter text.",
    }
    assert chat._response_text(completed, "gpt-6.1-sol") == "Recovered adapter text."
    canonical = {
        **completed,
        "output": [
            {"type": "message", "content": [{"type": "output_text", "text": "Canonical text."}]}
        ],
    }
    assert chat._response_text(canonical, "gpt-6.1-sol") == "Canonical text."
    refused = {
        **completed,
        "output": [{"type": "message", "content": [{"type": "refusal", "refusal": "No."}]}],
    }
    for bad in (
        {**completed, "status": "incomplete"},
        refused,
        {**completed, "output": [], "output_text": ""},
    ):
        try:
            chat._response_text(bad, "gpt-6.1-sol")
        except ProjectError:
            pass
        else:
            raise AssertionError("Invalid or refused model response accepted")
    print("PASS Brainstorm completed-response recovery without accepting incomplete/refused text")


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
        long_repeated = "Expanded Repeated instruction " * 310
        long_record = client.post(
            "/api/chat/message",
            json={
                "conversation_id": body["conversation_id"],
                "speaker": "human",
                "text": long_text,
            },
        )
        repeated_record = client.post(
            "/api/chat/message",
            json={
                "conversation_id": body["conversation_id"],
                "speaker": "objective",
                "text": "Check sources.",
            },
        )
        long_turn = client.post(
            "/api/chat/turn",
            json={
                **body,
                "messages": [{"speaker": "human", "text": long_text}],
                "research_objective": long_repeated,
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
    assert opened.status_code == 200 and opened.json()["transcript_name"] == "fixture.md"
    assert recorded.status_code == 204
    assert long_record.status_code == 204
    assert repeated_record.status_code == 204
    assert long_turn.status_code == 200, long_turn.text
    assert len(long_text) > 8000 and len(long_repeated) > 8000
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
    print("PASS chat API model/thinking validation, SSE completion and participant validation")


def check_slow_turn_heartbeat() -> None:
    """A slow model turn must keep its SSE connection alive and still complete."""
    body = {
        "conversation_id": str(uuid4()),
        "expected_binding": "api_key",
        "speaker": "ai_1",
        "messages": [{"speaker": "human", "text": "Think carefully."}],
        "model": "gpt-6.1-sol",
        "reasoning_effort": "high",
    }
    config = {
        "available": True,
        "message": "Ready.",
        "binding": "api_key",
        "models": [{"id": "gpt-6.1-sol", "efforts": ["high"]}],
    }

    async def slow_turn(**_kwargs):
        await asyncio.sleep(0.05)
        return "A carefully reasoned reply."

    with (
        patch("sigma.chat.configuration", new=AsyncMock(return_value=config)),
        patch("sigma.chat.respond", side_effect=slow_turn),
        patch("sigma.api.CHAT_HEARTBEAT_SECONDS", 0.01),
        TestClient(app) as client,
    ):
        response = client.post("/api/chat/turn", json=body)
    assert response.status_code == 200, response.text
    assert ": keepalive\n\n" in response.text
    assert '"type": "complete", "text": "A carefully reasoned reply."' in response.text
    print("PASS brainstorm SSE heartbeat during slow reasoning and eventual completion")


def check_supervisor() -> None:
    assert "NEVER direct the AIs to stop the conversation" in chat_supervisor.INSTRUCTIONS
    example = {
        "rubric": {
            "alignment": 1.2,
            "originality": 0.8,
            "advancement": 1.3,
            "evidence": 1.0,
            "momentum": 0.6,
        },
        "assessment": "Progress is constructive but validation is limited.",
        "action": "nudge",
        "recipient": "ai_2",
        "guidance": "Clarify the question that remains unresolved.",
        "breakthrough_candidate": False,
        "breakthrough_invalidated": False,
    }
    result = chat_supervisor.parse_assessment(json.dumps(example))
    assert result["score"] == 4.9
    conversation = [
        {"speaker": "human", "text": "Discover something new."},
        {"speaker": "ai_1", "text": "An idea."},
        {"speaker": "ai_2", "text": "An objection."},
        {
            "speaker": "supervisor",
            "text": "Research progress: 4.9 / 10.0",
            "recipient": result["recipient"],
            "guidance": result["guidance"],
        },
    ]
    assert "Research progress" not in chat._transcript(conversation, "ai_1")
    assert "Research progress" not in chat._transcript(conversation, "ai_2")
    assert "Clarify the question" not in chat._transcript(conversation, "ai_1")
    assert "Clarify the question" in chat._transcript(conversation, "ai_2")
    candidate = chat_supervisor.parse_assessment(
        json.dumps(
            {
                **example,
                "action": "continue",
                "recipient": None,
                "guidance": "",
                "breakthrough_candidate": True,
            }
        )
    )
    assert candidate["score"] == 10.0
    invalidation = chat_supervisor.parse_assessment(
        json.dumps(
            {
                **example,
                "action": "continue",
                "recipient": None,
                "guidance": "",
                "breakthrough_invalidated": True,
            }
        )
    )
    assert invalidation["breakthrough_invalidated"] is True
    assert invalidation["score"] == 4.9
    print("PASS supervisor scoring, invalidation, and recipient-isolated guidance")


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
            ]
            for speaker, text in messages:
                chat_transcripts.append_message(session["conversation_id"], speaker, text)
            chat_transcripts.append_message(
                session["conversation_id"], "objective", "Challenge the assumptions."
            )
            chat_transcripts.append_message(session["conversation_id"], "objective", "(cleared)")
            long_entry = "Detailed workbench evidence. " * 320
            assert len(long_entry) > 8000
            chat_transcripts.append_message(session["conversation_id"], "human", long_entry)
            content = path.read_text(encoding="utf-8")
            assert "## Research Objective ·" in content
            assert "Challenge the assumptions." in content
            assert "(cleared)" in content
            assert long_entry in content
            assert f"Session ID: {session['conversation_id']}" in content
            assert content.index("## Human ·") < content.index("## AI #1 ·")
            assert content.index("## AI #1 ·") < content.index("## AI #2 ·")
            assert all(text in content for _, text in messages)

            options = chat_transcripts.list_transcripts()
            assert options == [{"name": session["transcript_name"]}]
            restored = chat_transcripts.load_transcript(session["transcript_name"])
            assert restored["conversation_id"] == session["conversation_id"]
            assert restored["transcript_path"] == session["transcript_path"]
            assert restored["research_objective"] == ""
            assert restored["next_speaker"] == "ai_1"
            assert restored["messages"][0] == {"speaker": "human", "text": messages[0][1]}
            assert restored["messages"][2] == {"speaker": "ai_2", "text": messages[2][1]}
            assert restored["messages"][-1]["text"] == long_entry
            assert not restored["supervisor_enabled"]
            with TestClient(app) as client:
                listed = client.get("/api/chat/transcripts")
                selected = client.get("/api/chat/transcripts/" + session["transcript_name"])
                traversal = client.get("/api/chat/transcripts/not-a-transcript.md")
            assert listed.status_code == 200
            assert listed.json() == options
            assert selected.status_code == 200
            assert selected.json()["conversation_id"] == session["conversation_id"]
            assert traversal.status_code in {400, 404, 422}

            chat_transcripts.append_message(
                session["conversation_id"],
                "supervisor",
                "Research progress: 4.5 / 10.0\\n\\nTo AI #2: Clarify the assumption.",
            )
            resumed_guidance = chat_transcripts.load_transcript(session["transcript_name"])
            assert resumed_guidance["supervisor_enabled"]
            assert resumed_guidance["messages"][-1]["recipient"] == "ai_2"
            assert resumed_guidance["messages"][-1]["guidance"] == "Clarify the assumption."

            chat_transcripts.append_message(
                session["conversation_id"], "supervisor_setting", "disabled"
            )
            disabled = chat_transcripts.load_transcript(session["transcript_name"])
            assert disabled["supervisor_enabled"] is False
            assert all(
                message["speaker"] != "supervisor_setting" for message in disabled["messages"]
            )
            chat_transcripts.append_message(
                session["conversation_id"], "supervisor_setting", "enabled"
            )
            reenabled = chat_transcripts.load_transcript(session["transcript_name"])
            assert reenabled["supervisor_enabled"] is True

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
    check_response_recovery()
    check_streamed_multisegment_completion()
    check_api()
    check_slow_turn_heartbeat()
    check_supervisor()
    check_transcripts()


if __name__ == "__main__":
    main()
