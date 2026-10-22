"""Offline, controlled A14 coordinator and sample-project scenarios."""

import asyncio
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import AsyncMock, patch

import httpx
from pydantic import ValidationError

from sigma import agentic, chatgpt_auth
from sigma.api import app
from sigma.projects import create_strategy, inspect_project
from sigma.proposals import accepted_provenance
from sigma.samples import open_sample_project, sample_projects

MODEL = "gpt-6.1-sol"
SOURCE = Path("samples/counting-constrained-binary-strings/project.json")
CANDIDATE = {
    "title": "Recurrence from the final symbol",
    "summary": "Partition valid strings by the last symbol and justify a recurrence.",
    "approach": "Partition valid length-n strings according to whether the final symbol is 0 or 1; the latter forces a 0 immediately before it. Prove this partition is disjoint and exhaustive before deriving a recurrence.",
    "first_tests": "Enumerate n=0,1,2,5,10 and compare with 1,2,3,13,144; these checks are not proof.",
    "assumptions": "The empty string is included; the terminal partition handles n below two separately.",
    "failure_modes": "A wrong base case or overlooking the forced predecessor invalidates the recurrence.",
    "mechanism": "A disjoint terminal-symbol decomposition maps the two classes to shorter valid strings.",
    "evidence_boundary": "The recurrence is proposed and requires a bijection proof; small cases are only checks.",
}
ALTERNATIVE = {
    **CANDIDATE,
    "title": "Choose positions of nonadjacent ones",
    "summary": "Count valid strings by selecting shifted positions for their ones.",
    "approach": "For exactly k ones, map their increasing positions i_j to shifted positions i_j-(j-1). Prove this is a bijection with k-subsets of n-k+1 positions, then sum over k.",
    "mechanism": "A position-shift bijection turns a spacing constraint into an ordinary subset count, unlike terminal-state recurrence splitting.",
}
DISTINCT = {
    "assessment": "distinct",
    "public_summary": "The mechanism is distinct and relevant; the proposed bijection still needs a full proof.",
    "mechanism_comparison": "No existing strategies use this mechanism, or the position-shift bijection differs from terminal recurrence splitting.",
    "objections": ["Prove the mapping is reversible and check boundary indices."],
    "missing_obligations": "Show that the proposed partition or bijection covers every valid string exactly once.",
    "revision_needed": False,
}
OVERLAP = {
    **DISTINCT,
    "assessment": "overlapping",
    "public_summary": "The proposed mechanism repeats the existing terminal-symbol recurrence.",
    "mechanism_comparison": "The prior strategy already partitions by the final symbol and derives the same recurrence.",
}
REAL_CLIENT = httpx.AsyncClient


def provider_output(value):
    return {
        "status": "completed",
        "model": MODEL,
        "output": [
            {"type": "message", "content": [{"type": "output_text", "text": json.dumps(value)}]}
        ],
    }


async def collect(path: str):
    return [event async for event in agentic.agentic_events(path)]


async def exercise(path: str, outputs: list[dict], before: bytes):
    calls: list[dict] = []

    async def handler(request):
        if request.method == "GET":
            return httpx.Response(200, json={"object": "list", "data": [{"id": MODEL}]})
        payload = json.loads(request.content)
        assert payload["model"] == MODEL and payload["store"] is False
        assert payload["reasoning"] == {"effort": "high"}
        assert payload["max_output_tokens"] == 6000
        assert payload["text"]["format"]["strict"] is True
        assert payload["text"]["format"]["name"].startswith("strategy_")
        context = json.loads(payload["input"])
        assert context["project"]["research_problem"].startswith("For each integer n >= 0")
        calls.append({"role": payload["text"]["format"]["name"], "context": context})
        return httpx.Response(200, json=provider_output(outputs.pop(0)))

    def client(**kwargs):
        return REAL_CLIENT(transport=httpx.MockTransport(handler), **kwargs)

    with patch("sigma.agentic.httpx.AsyncClient", side_effect=client):
        events = await collect(path)
    assert (Path(path) / "project.json").read_bytes() == before
    assert [event["sequence"] for event in events] == list(range(1, len(events) + 1))
    assert len({event["run_id"] for event in events}) == 1
    assert len(calls) <= 6 and not outputs
    return events, calls


async def main_async(root: Path):
    await chatgpt_auth.select("api_key")
    source_before = SOURCE.read_bytes()
    sample = sample_projects()["projects"]
    assert any(
        item["id"] == "counting-constrained-binary-strings" and item["strategy_count"] == 0
        for item in sample
    )
    view = open_sample_project("counting-constrained-binary-strings")
    assert not view.project.strategies and not view.project.active_order
    path = view.path
    before = (Path(path) / "project.json").read_bytes()
    assert before != source_before
    assert view.project.id != "counting-constrained-binary-strings"
    assert view.project.title.endswith(" (copy)")

    events, calls = await exercise(path, [CANDIDATE, DISTINCT], before)
    assert [call["role"] for call in calls] == ["strategy_explore", "strategy_challenge"]
    assert events[-1]["type"] == "run.completed"
    assert events[-1]["draft"]["title"] == CANDIDATE["title"]
    assert any(event["type"] == "activity.started" for event in events)
    assert any(event["type"] == "decision" and event["outcome"] == "present" for event in events)
    assert inspect_project(path).project.strategies == ()
    provenance = accepted_provenance(events[-1]["receipt"], path)
    saved = create_strategy(
        path,
        events[-1]["draft"]["title"],
        events[-1]["draft"]["approach"],
        events[-1]["draft"]["summary"],
        provenance,
    )
    assert (
        len(saved.project.strategies) == 1 and saved.project.strategies[0].provenance == provenance
    )
    independent = open_sample_project("counting-constrained-binary-strings")
    assert independent.project.id != view.project.id
    assert not independent.project.strategies
    assert SOURCE.read_bytes() == source_before
    print(
        "PASS sample zero-pool, real explore/challenge events, unsaved review, explicit acceptance, reopen and immutable source"
    )

    before = (Path(path) / "project.json").read_bytes()
    events, calls = await exercise(path, [ALTERNATIVE, DISTINCT], before)
    assert events[-1]["type"] == "run.completed"
    assert calls[0]["context"]["project"]["existing_strategies"][0]["approach"].startswith(
        CANDIDATE["approach"]
    )
    assert events[-1]["draft"]["title"] == ALTERNATIVE["title"]
    events, calls = await exercise(path, [CANDIDATE, DISTINCT, ALTERNATIVE, DISTINCT], before)
    assert [call["role"] for call in calls] == [
        "strategy_explore",
        "strategy_challenge",
        "strategy_explore",
        "strategy_challenge",
    ]
    assert any(event.get("outcome") == "retry" for event in events)
    assert events[-1]["type"] == "run.completed"
    review_revision = {
        **DISTINCT,
        "revision_needed": True,
        "public_summary": "Revise a boundary argument before presenting this distinct idea.",
    }
    events, calls = await exercise(
        path, [ALTERNATIVE, review_revision, ALTERNATIVE, DISTINCT], before
    )
    assert [call["role"] for call in calls] == [
        "strategy_explore",
        "strategy_challenge",
        "strategy_revise",
        "strategy_challenge",
    ]
    assert any(event.get("outcome") == "revise" for event in events)
    events, calls = await exercise(path, [CANDIDATE, OVERLAP, CANDIDATE, OVERLAP], before)
    assert events[-1]["type"] == "run.stopped" and len(calls) == 4
    events, calls = await exercise(
        path,
        [ALTERNATIVE, review_revision, ALTERNATIVE, OVERLAP, ALTERNATIVE, review_revision],
        before,
    )
    assert events[-1]["type"] == "run.failed" and "Six-call" in events[-1]["summary"]
    assert len(calls) == agentic.MAX_CALLS
    assert len(inspect_project(path).project.strategies) == 1
    print(
        "PASS later novelty corpus, duplicate retry, skeptical revision, exhausted no-proposal branch and no mutation"
    )

    async def bad_handler(request):
        if request.method == "GET":
            return httpx.Response(200, json={"object": "list", "data": [{"id": MODEL}]})
        return httpx.Response(200, json=provider_output({"invalid": "shape"}))

    with patch(
        "sigma.agentic.httpx.AsyncClient",
        side_effect=lambda **kwargs: REAL_CLIENT(
            transport=httpx.MockTransport(bad_handler), **kwargs
        ),
    ):
        events = await collect(path)
        assert events[-1]["type"] == "run.failed"
    assert not agentic._gate.locked()
    assert (Path(path) / "project.json").read_bytes() == before
    print("PASS malformed provider output fails with terminal event and releases run gate")
    try:
        agentic.ProgressEvent(
            type="activity.completed",
            sequence=1,
            run_id="x",
            kind="challenge",
            attempt=1,
            summary="review",
        )
    except ValidationError:
        pass
    else:
        raise AssertionError("Invalid reviewer progress event was accepted")

    async def refused_handler(request):
        if request.method == "GET":
            return httpx.Response(200, json={"object": "list", "data": [{"id": MODEL}]})
        return httpx.Response(
            200,
            json={
                "status": "completed",
                "model": MODEL,
                "output": [{"type": "message", "content": [{"type": "refusal"}]}],
            },
        )

    with patch(
        "sigma.agentic.httpx.AsyncClient",
        side_effect=lambda **kwargs: REAL_CLIENT(
            transport=httpx.MockTransport(refused_handler), **kwargs
        ),
    ):
        refused = await collect(path)
    assert refused[-1]["type"] == "run.failed" and "declined" in refused[-1]["summary"]

    with patch(
        "sigma.agentic.auth_context",
        new=AsyncMock(return_value={"identity": "changed", "mode": "api_key", "token": "test"}),
    ):
        events = [
            event async for event in agentic.agentic_events(path, expected_binding="original")
        ]
    assert events[-1]["type"] == "run.failed" and "account/billing" in events[-1]["summary"]
    events = [event async for event in agentic.agentic_events(path, expected_project_id="wrong")]
    assert events[-1]["type"] == "run.failed" and "identity" in events[-1]["summary"]

    started = asyncio.Event()

    async def pending_handler(request):
        if request.method == "GET":
            return httpx.Response(200, json={"object": "list", "data": [{"id": MODEL}]})
        started.set()
        await asyncio.sleep(20)
        return httpx.Response(200, json=provider_output(CANDIDATE))

    def pending_client(**kwargs):
        return REAL_CLIENT(transport=httpx.MockTransport(pending_handler), **kwargs)

    with patch("sigma.agentic.httpx.AsyncClient", side_effect=pending_client):
        running = agentic.agentic_events(path)
        first = await anext(running)
        assert first["type"] == "run.started"
        duplicate = await collect(path)
        assert (
            duplicate[-1]["type"] == "run.failed" and "already active" in duplicate[-1]["summary"]
        )
        assert (await anext(running))["type"] == "activity.started"
        pending = asyncio.create_task(anext(running))
        await asyncio.wait_for(started.wait(), 2)
        pending.cancel()
        try:
            await pending
        except asyncio.CancelledError:
            pass
        await running.aclose()
        assert not agentic._gate.locked()
        started.clear()
        with patch("sigma.agentic.CALL_SECONDS", 0.01):
            timeout_events = await collect(path)
        assert (
            timeout_events[-1]["type"] == "run.failed"
            and "timed out" in timeout_events[-1]["summary"]
        )
        assert not agentic._gate.locked()
    assert (Path(path) / "project.json").read_bytes() == before
    print(
        "PASS binding/identity changes, duplicate run, cancellation, timeout and clean gate release"
    )

    # Exercise ChatGPT-plan Responses streaming without a real account or network.
    binding = {"identity": "plan-fixture", "mode": "chatgpt", "token": "fixture-token"}

    def plan_handler(request):
        payload = json.loads(request.content)
        assert payload["stream"] is True and "max_output_tokens" not in payload
        assert isinstance(payload["input"], list)
        text = json.dumps(CANDIDATE)
        raw = {**provider_output(CANDIDATE), "id": "resp-agentic-fixture"}
        stream_events = [
            {
                "type": "response.created",
                "sequence_number": 0,
                "response": {"id": "resp-agentic-fixture", "status": "in_progress"},
            },
            {"type": "response.output_text.delta", "sequence_number": 1, "delta": text},
            {"type": "response.completed", "sequence_number": 2, "response": raw},
        ]
        content = "".join(
            f"event: {item['type']}\ndata: {json.dumps(item)}\n\n" for item in stream_events
        )
        return httpx.Response(200, headers={"content-type": "text/event-stream"}, content=content)

    with (
        patch("sigma.agentic.auth_context", new=AsyncMock(return_value=binding)),
        patch(
            "sigma.agentic.httpx.AsyncClient",
            side_effect=lambda **kwargs: REAL_CLIENT(
                transport=httpx.MockTransport(plan_handler), **kwargs
            ),
        ),
    ):
        candidate = await agentic._invoke(
            "explore",
            {"project": {"research_problem": "fixture"}},
            {"model": MODEL, "reasoning_effort": "high"},
            binding,
            inspect_project(path),
        )
    assert isinstance(candidate, agentic.Candidate) and candidate.title == CANDIDATE["title"]
    print(
        "PASS ChatGPT-plan streamed Responses adapter preserves selected model/effort and request mode"
    )

    # The real ASGI stream must cancel a pending provider call on browser disconnect.
    started.clear()
    queue: asyncio.Queue[dict] = asyncio.Queue()
    await queue.put(
        {"type": "http.request", "body": json.dumps({"path": path}).encode(), "more_body": False}
    )
    sent = []

    async def send(message):
        sent.append(message)

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/api/projects/proposals/agentic",
        "raw_path": b"/api/projects/proposals/agentic",
        "query_string": b"",
        "root_path": "",
        "headers": [(b"host", b"testserver"), (b"content-type", b"application/json")],
        "server": ("testserver", 80),
        "client": ("127.0.0.1", 1234),
    }
    with patch("sigma.agentic.httpx.AsyncClient", side_effect=pending_client):
        serving = asyncio.create_task(app(scope, queue.get, send))
        await asyncio.wait_for(started.wait(), 2)
        await queue.put({"type": "http.disconnect"})
        await asyncio.wait_for(serving, 2)
        assert not agentic._gate.locked()
    print("PASS ASGI browser disconnect cancels active agentic provider work")


def main():
    with (
        TemporaryDirectory() as directory,
        patch.dict(
            os.environ,
            {
                "SIGMA_STATE_DIR": str(Path(directory) / "state"),
                "SIGMA_AUTH_HOME": str(Path(directory) / "auth"),
                "SIGMA_PROJECTS_ROOT": str(Path(directory) / "managed"),
                "OPENAI_API_KEY": "explicit-agentic-fixture-not-a-secret",
            },
        ),
    ):
        (Path(directory) / "managed").mkdir()
        asyncio.run(main_async(Path(directory)))


if __name__ == "__main__":
    main()
