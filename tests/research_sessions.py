"""Persistent A17 sessions use deterministic provider fixtures only."""

import asyncio
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import httpx

from sigma import research_sessions
from sigma.projects import ProjectError, create_strategy, edit_strategy, initialize_project

MODEL = "gpt-6.1-sol"
REAL_CLIENT = httpx.AsyncClient


def provider_response(value):
    return {
        "status": "completed",
        "output": [
            {"type": "message", "content": [{"type": "output_text", "text": json.dumps(value)}]}
        ],
    }


def investigation(n):
    return {
        "claim": f"Claim {n}: a candidate consequence follows from cycle {n}.",
        "method": f"Derive the consequence using the strategy in cycle {n}.",
        "assumptions": [f"Assumption {n}"],
        "evidence_status": "Unverified model derivation; no tool was run.",
        "open_obligations": [f"Obligation {n}"],
    }


def skeptic(n, assessment="continue"):
    return {
        "assessment": assessment,
        "response": f"Independent objection review for cycle {n}.",
        "objections": [f"Check boundary case {n}"],
        "remaining_obligations": [f"Resolve obligation {n}"],
        "next_question": f"Investigate the distinct consequence for cycle {n + 1}.",
    }


async def wait_for(path, session_id, terminal=True):
    for _ in range(300):
        current = research_sessions.get_session(str(path), session_id)
        if (
            (current["status"] in {"completed", "failed", "stopped", "paused"})
            if terminal
            else current["calls_used"]
        ):
            return current
        await asyncio.sleep(0.01)
    raise AssertionError("research worker did not make progress")


async def setup(path: Path):
    view = initialize_project(path, "Session project", "A bounded mathematical question")
    strategy = create_strategy(
        path, "Saved approach", "Derive a recurrence and check its boundary cases."
    ).project.strategies[0]
    credential = {
        "identity": "fixture-account",
        "mode": "api_key",
        "token": "fixture-token",
        "status": "connected",
    }
    config = {"available": True, "model": MODEL, "reasoning_effort": "high"}
    return view, strategy, credential, config


async def test_three_cycles_and_idempotency(path: Path):
    view, strategy, credential, config = await setup(path)
    before = (path / "project.json").read_bytes()
    outputs = [
        investigation(1),
        skeptic(1, "revise"),
        investigation(2),
        skeptic(2),
        investigation(3),
        skeptic(3),
    ]
    contexts = []

    async def handler(request):
        payload = json.loads(request.content)
        assert payload["model"] == MODEL and payload["store"] is False
        assert payload["max_output_tokens"] == 4000
        assert payload["text"]["format"]["strict"] is True
        assert payload["text"]["format"]["name"] in {"research_investigator", "research_skeptic"}
        context = json.loads(payload["input"])
        contexts.append((payload["text"]["format"]["name"], context))
        return httpx.Response(200, json=provider_response(outputs.pop(0)))

    with (
        patch.object(research_sessions, "auth_context", new=AsyncMock(return_value=credential)),
        patch.object(research_sessions, "configuration", new=AsyncMock(return_value=config)),
        patch(
            "sigma.research_sessions.httpx.AsyncClient",
            side_effect=lambda **kwargs: REAL_CLIENT(
                transport=httpx.MockTransport(handler), **kwargs
            ),
        ),
    ):
        key = str(uuid4())
        started, concurrent_duplicate = await asyncio.gather(
            research_sessions.start_session(
                str(path), strategy.id, key, view.project.id, credential["identity"]
            ),
            research_sessions.start_session(
                str(path), strategy.id, key, view.project.id, credential["identity"]
            ),
        )
        assert concurrent_duplicate["id"] == started["id"]
        assert started["session_number"] == concurrent_duplicate["session_number"] == 1
        finished = await wait_for(path, started["id"])
        duplicate = await research_sessions.start_session(
            str(path), strategy.id, key, view.project.id, credential["identity"]
        )
        assert duplicate["id"] == started["id"]

    assert finished["status"] == "completed" and finished["calls_used"] == 6
    assert len(finished["artifacts"]) == 3 and [a["sequence"] for a in finished["artifacts"]] == [
        1,
        2,
        3,
    ]
    assert [role for role, _ in contexts] == ["research_investigator", "research_skeptic"] * 3
    # The Python coordinator's revise branch uses the skeptic's actual next question.
    assert contexts[2][1]["question"] == skeptic(1, "revise")["next_question"]
    assert contexts[2][1]["prior_artifacts"][0]["id"] == finished["artifacts"][0]["id"]
    assert contexts[4][1]["prior_artifacts"][1]["id"] == finished["artifacts"][1]["id"]
    assert [a["coordinator_decision"] for a in finished["artifacts"]] == [
        "revise",
        "continue",
        "stop_budget_exhausted",
    ]
    assert finished["artifacts"][2]["next_question"] == ""
    assert (path / "project.json").read_bytes() == before
    assert finished["artifacts"][0]["note"].startswith("Unverified")
    assert "fixture-token" not in json.dumps(finished) and "fixture-account" not in json.dumps(
        finished
    )
    assert len(research_sessions.list_sessions(str(path))) == 1
    assert [event["sequence"] for event in finished["events"]] == list(
        range(1, len(finished["events"]) + 1)
    )
    assert any(event["kind"] == "coordinator.started" for event in finished["events"])


async def test_pause_counts_interrupted_call(path: Path):
    view, strategy, credential, config = await setup(path)
    started_call = asyncio.Event()
    hang = [True]

    async def handler(request):
        started_call.set()
        if hang[0]:
            await asyncio.Event().wait()
        role = json.loads(request.content)["text"]["format"]["name"]
        output = investigation(1) if role == "research_investigator" else skeptic(1, "stop")
        return httpx.Response(200, json=provider_response(output))

    with (
        patch.object(research_sessions, "auth_context", new=AsyncMock(return_value=credential)),
        patch.object(research_sessions, "configuration", new=AsyncMock(return_value=config)),
        patch(
            "sigma.research_sessions.httpx.AsyncClient",
            side_effect=lambda **kwargs: REAL_CLIENT(
                transport=httpx.MockTransport(handler), **kwargs
            ),
        ),
    ):
        started = await research_sessions.start_session(
            str(path), strategy.id, str(uuid4()), view.project.id, credential["identity"]
        )
        await asyncio.wait_for(started_call.wait(), 2)
        progress = research_sessions.get_session(str(path), started["id"])
        assert "Investigator provider call 1/6 in progress" in progress["message"]
        paused = await research_sessions.control_session(str(path), started["id"], "pause")
        await asyncio.sleep(0.02)
        paused = research_sessions.get_session(str(path), started["id"])
    assert paused["status"] == "paused" and paused["calls_used"] == 1
    assert paused["steps"][-1]["status"] == "interrupted"
    from sigma import agentic, proposals, text_views

    for gate in (agentic._gate, proposals._gate, text_views._gate, research_sessions._gate):
        assert gate.acquire(blocking=False)
        gate.release()
    hang[0] = False
    with (
        patch.object(research_sessions, "auth_context", new=AsyncMock(return_value=credential)),
        patch.object(research_sessions, "configuration", new=AsyncMock(return_value=config)),
        patch(
            "sigma.research_sessions.httpx.AsyncClient",
            side_effect=lambda **kwargs: REAL_CLIENT(
                transport=httpx.MockTransport(handler), **kwargs
            ),
        ),
    ):
        resumed, duplicate_resume = await asyncio.gather(
            research_sessions.control_session(str(path), started["id"], "resume"),
            research_sessions.control_session(str(path), started["id"], "resume"),
        )
        assert resumed["status"] == "queued" and resumed["calls_used"] == 1
        assert duplicate_resume["id"] == started["id"]
        resumed = await wait_for(path, started["id"])
    assert resumed["status"] == "completed" and resumed["calls_used"] == 3
    assert resumed["artifacts"][0]["coordinator_decision"] == "stop"

    started_call.clear()
    hang[0] = True
    with (
        patch.object(research_sessions, "auth_context", new=AsyncMock(return_value=credential)),
        patch.object(research_sessions, "configuration", new=AsyncMock(return_value=config)),
        patch(
            "sigma.research_sessions.httpx.AsyncClient",
            side_effect=lambda **kwargs: REAL_CLIENT(
                transport=httpx.MockTransport(handler), **kwargs
            ),
        ),
    ):
        stopped_start = await research_sessions.start_session(
            str(path), strategy.id, str(uuid4()), view.project.id, credential["identity"]
        )
        assert stopped_start["session_number"] == 2
        await asyncio.wait_for(started_call.wait(), 2)
        await research_sessions.control_session(str(path), stopped_start["id"], "stop")
        await asyncio.sleep(0.02)
        stopped = research_sessions.get_session(str(path), stopped_start["id"])
    assert stopped["status"] == "stopped" and stopped["calls_used"] == 1
    assert stopped["steps"][-1]["status"] == "interrupted"
    with patch.object(research_sessions, "auth_context", new=AsyncMock(return_value=credential)):
        rejected = await research_sessions.control_session(str(path), stopped_start["id"], "resume")
    assert rejected["status"] == "stopped"


async def test_malformed_output_and_restart(path: Path):
    view, strategy, credential, config = await setup(path)

    async def malformed(request):
        return httpx.Response(200, json=provider_response({"claim": "Only a partial response"}))

    with (
        patch.object(research_sessions, "auth_context", new=AsyncMock(return_value=credential)),
        patch.object(research_sessions, "configuration", new=AsyncMock(return_value=config)),
        patch(
            "sigma.research_sessions.httpx.AsyncClient",
            side_effect=lambda **kwargs: REAL_CLIENT(
                transport=httpx.MockTransport(malformed), **kwargs
            ),
        ),
    ):
        started = await research_sessions.start_session(
            str(path), strategy.id, str(uuid4()), view.project.id, credential["identity"]
        )
        failed = await wait_for(path, started["id"])
    assert failed["status"] == "failed" and failed["artifacts"] == []
    assert failed["steps"][0]["status"] == "failed" and failed["calls_used"] == 1

    interrupted_id = str(uuid4())
    record = {
        "schema_version": 1,
        "id": interrupted_id,
        "project_path": str(path.resolve()),
        "project_id": view.project.id,
        "strategy_id": strategy.id,
        "strategy_title": strategy.title,
        "strategy_text": strategy.approach,
        "problem": view.project.problem,
        "model": MODEL,
        "reasoning_effort": "high",
        "mode": "api_key",
        "identity_hash": "0" * 64,
        "guard_hash": "1" * 64,
        "idempotency_key": str(uuid4()),
        "status": "running",
        "created_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-01T00:00:00+00:00",
        "calls_used": 1,
        "call_limit": 6,
        "cycle": 0,
        "current_question": "Resume only explicitly",
        "current_step": "interrupted-step",
        "steps": [{"id": "interrupted-step", "role": "investigator", "status": "running"}],
        "artifacts": [],
        "message": "running",
    }
    research_sessions._save(str(path), record)
    recovered = research_sessions.get_session(str(path), interrupted_id)
    assert recovered["status"] == "paused" and recovered["calls_used"] == 1
    assert recovered["steps"][0]["status"] == "interrupted"
    assert "not be retried automatically" in recovered["message"]


async def test_chatgpt_stream(path: Path):
    view, strategy, _, _ = await setup(path)
    credential = {
        "identity": "chatgpt:fixture",
        "mode": "chatgpt",
        "token": "fixture-token",
        "status": "connected",
    }
    output = investigation(1)
    envelope = {
        "id": "response-1",
        "status": "completed",
        "output": [
            {"type": "message", "content": [{"type": "output_text", "text": json.dumps(output)}]}
        ],
    }
    events = [
        {"type": "response.created", "sequence_number": 0, "response": {"id": "response-1"}},
        {"type": "response.completed", "sequence_number": 1, "response": envelope},
    ]
    body = "".join(f"event: {item['type']}\ndata: {json.dumps(item)}\n\n" for item in events)

    async def handler(request):
        payload = json.loads(request.content)
        assert payload["stream"] is True and "max_output_tokens" not in payload
        assert (
            isinstance(payload["input"], list) and request.headers["Accept"] == "text/event-stream"
        )
        return httpx.Response(200, headers={"content-type": "text/event-stream"}, text=body)

    record = {
        "model": MODEL,
        "reasoning_effort": "high",
        "mode": "chatgpt",
        "identity_hash": research_sessions._digest(credential["identity"]),
    }
    with (
        patch.object(research_sessions, "auth_context", new=AsyncMock(return_value=credential)),
        patch(
            "sigma.research_sessions.httpx.AsyncClient",
            side_effect=lambda **kwargs: REAL_CLIENT(
                transport=httpx.MockTransport(handler), **kwargs
            ),
        ),
    ):
        result = await research_sessions._call(
            record, "investigator", {"problem": view.project.problem, "strategy": strategy.approach}
        )
    assert result == output


async def test_changed_bindings_pause_before_provider(path: Path):
    view, strategy, credential, config = await setup(path)
    changed = {**credential, "identity": "different-account"}
    entered = asyncio.Event()
    release = asyncio.Event()
    provider_calls = []

    async def blocked_gate():
        entered.set()
        await release.wait()
        return []

    async def handler(request):
        provider_calls.append(request)
        return httpx.Response(200, json=provider_response(investigation(1)))

    with (
        patch.object(
            research_sessions, "auth_context", new=AsyncMock(side_effect=[credential, changed])
        ),
        patch.object(research_sessions, "configuration", new=AsyncMock(return_value=config)),
        patch.object(research_sessions, "_acquire_gates", new=blocked_gate),
        patch(
            "sigma.research_sessions.httpx.AsyncClient",
            side_effect=lambda **kwargs: REAL_CLIENT(
                transport=httpx.MockTransport(handler), **kwargs
            ),
        ),
    ):
        started = await research_sessions.start_session(
            str(path), strategy.id, str(uuid4()), view.project.id, credential["identity"]
        )
        await asyncio.wait_for(entered.wait(), 2)
        edit_strategy(
            str(path), strategy.id, strategy.title, strategy.approach + " Revised source."
        )
        release.set()
        paused = await wait_for(path, started["id"])
    assert paused["status"] == "paused" and paused["calls_used"] == 0
    assert "Project or strategy changed" in paused["message"]
    assert provider_calls == []

    account_path = path.parent / "account-change.sigma"
    account_view, account_strategy, account_credential, account_config = await setup(account_path)
    entered.clear()
    release.clear()
    with (
        patch.object(
            research_sessions,
            "auth_context",
            new=AsyncMock(
                side_effect=[account_credential, {**account_credential, "identity": "other"}]
            ),
        ),
        patch.object(
            research_sessions, "configuration", new=AsyncMock(return_value=account_config)
        ),
        patch.object(research_sessions, "_acquire_gates", new=blocked_gate),
        patch(
            "sigma.research_sessions.httpx.AsyncClient",
            side_effect=lambda **kwargs: REAL_CLIENT(
                transport=httpx.MockTransport(handler), **kwargs
            ),
        ),
    ):
        started = await research_sessions.start_session(
            str(account_path),
            account_strategy.id,
            str(uuid4()),
            account_view.project.id,
            account_credential["identity"],
        )
        await asyncio.wait_for(entered.wait(), 2)
        release.set()
        paused = await wait_for(account_path, started["id"])
    assert paused["status"] == "paused" and paused["calls_used"] == 0
    assert "AI account or billing identity changed" in paused["message"]
    assert provider_calls == []


async def test_storage_limit_pauses_without_artifact(path: Path):
    view, strategy, credential, config = await setup(path)
    outputs = [investigation(1), skeptic(1)]
    original_save = research_sessions._save

    def limited_save(project_path, record):
        if record.get("artifacts"):
            raise ProjectError("Research session storage limit reached")
        original_save(project_path, record)

    async def handler(request):
        return httpx.Response(200, json=provider_response(outputs.pop(0)))

    with (
        patch.object(research_sessions, "auth_context", new=AsyncMock(return_value=credential)),
        patch.object(research_sessions, "configuration", new=AsyncMock(return_value=config)),
        patch.object(research_sessions, "_save", new=limited_save),
        patch(
            "sigma.research_sessions.httpx.AsyncClient",
            side_effect=lambda **kwargs: REAL_CLIENT(
                transport=httpx.MockTransport(handler), **kwargs
            ),
        ),
    ):
        started = await research_sessions.start_session(
            str(path), strategy.id, str(uuid4()), view.project.id, credential["identity"]
        )
        paused = await wait_for(path, started["id"])
    assert paused["status"] == "paused" and paused["calls_used"] == 2
    assert paused["artifacts"] == []
    assert paused["steps"][-1]["status"] == "interrupted"
    assert "storage limit reached" in paused["message"].lower()


def main():
    with TemporaryDirectory() as temporary:
        root = Path(temporary)
        asyncio.run(test_three_cycles_and_idempotency(root / "cycles.sigma"))
        asyncio.run(test_pause_counts_interrupted_call(root / "pause.sigma"))
        asyncio.run(test_malformed_output_and_restart(root / "recovery.sigma"))
        asyncio.run(test_chatgpt_stream(root / "chatgpt.sigma"))
        asyncio.run(test_changed_bindings_pause_before_provider(root / "binding.sigma"))
        asyncio.run(test_storage_limit_pauses_without_artifact(root / "storage.sigma"))
    print("Persistent research session scenarios passed.")


if __name__ == "__main__":
    main()
