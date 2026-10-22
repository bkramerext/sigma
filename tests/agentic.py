"""Offline, controlled A14 coordinator and sample-project scenarios."""

import asyncio
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import httpx
from pydantic import ValidationError

from sigma import agentic, chatgpt_auth
from sigma.agentic_evidence import get_run, list_runs
from sigma.agentic_evidence import save as save_evidence
from sigma.api import agentic_runs_view, export_project_view, app
from sigma.projects import ProjectError, create_strategy, inspect_project
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
        role = payload["text"]["format"]["name"]
        if role == "strategy_explore":
            assert "candidate SOLUTION" in payload["instructions"]
            assert "rather than proposing to study" in payload["instructions"]
        elif role == "strategy_revise":
            assert "Revise the actual solution" in payload["instructions"]
            assert "rather than substituting a plan" in payload["instructions"]
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
    evidence = get_run(path, events[-1]["run_id"])
    assert evidence["terminal"]["status"] == "completed"
    assert evidence["context"]["provider_input"]["starting_point"] == ""
    assert evidence["context"]["provider_input"]["research_problem"] == view.project.problem
    assert evidence["steps"][0]["output"] == CANDIDATE
    assert evidence["steps"][1]["output"] == DISTINCT
    assert [step["call_index"] for step in evidence["steps"]] == [1, 2]
    assert [item["type"] for item in evidence["timeline"]] == ["activity", "activity", "decision"]
    assert evidence["final_candidate"] == CANDIDATE
    assert evidence["final_draft"]["title"] == CANDIDATE["title"]
    assert "receipt" not in json.dumps(evidence) and "fixture-token" not in json.dumps(evidence)
    # Re-read by run ID demonstrates the file-backed record survives service use/restart.
    assert get_run(path, events[-1]["run_id"])["steps"] == evidence["steps"]
    assert agentic_runs_view(path)["runs"][0]["run_id"] == events[-1]["run_id"]
    assert agentic_runs_view(path, events[-1]["run_id"])["final_candidate"] == CANDIDATE
    export = export_project_view(path)
    assert export["export_version"] == 1
    assert export["project"]["id"] == view.project.id
    assert not export["project"]["strategies"]  # asdict preserves the dataclass tuple; HTTP JSON uses [].
    assert any(run["run_id"] == events[-1]["run_id"] for run in export["agentic_runs"])
    assert any(run["steps"][0]["output"] == CANDIDATE for run in export["agentic_runs"])
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
    first_review = get_run(path, events[-1]["run_id"])["steps"][1]
    assert first_review["assessment"] == "distinct"
    assert first_review["effective_assessment"] == "overlapping"
    assert first_review["override_reason"]
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
    stopped_trace = get_run(path, events[-1]["run_id"])
    assert stopped_trace["terminal"]["status"] == "stopped"
    assert stopped_trace["steps"][1]["effective_assessment"] == "overlapping"
    assert stopped_trace["steps"][1]["override_reason"] is None
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
        malformed_trace = get_run(path, events[-1]["run_id"])
        assert malformed_trace["terminal"]["status"] == "failed"
        assert malformed_trace["steps"][-1]["status"] == "failed"
        assert malformed_trace["steps"][-1]["output"] is None
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
    assert get_run(path, refused[-1]["run_id"])["steps"][-1]["status"] == "failed"

    with patch(
        "sigma.agentic.auth_context",
        new=AsyncMock(return_value={"identity": "changed", "mode": "api_key", "token": "test"}),
    ):
        events = [
            event async for event in agentic.agentic_events(path, expected_binding="original")
        ]
    assert events[-1]["type"] == "run.failed" and "account/billing" in events[-1]["summary"]
    preflight_trace = get_run(path, events[-1]["run_id"])
    assert preflight_trace["terminal"]["status"] == "failed"
    assert preflight_trace["context"]["provider_input_status"] == "not sent"
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
        immediately_closed = agentic.agentic_events(path)
        closed_start = await anext(immediately_closed)
        assert closed_start["type"] == "run.started"
        assert (await anext(immediately_closed))["type"] == "activity.started"
        await immediately_closed.aclose()
        incomplete = get_run(path, closed_start["run_id"])
        assert incomplete["terminal"]["status"] == "cancelled"
        assert incomplete["steps"][-1]["status"] == "cancelled"
        assert incomplete["steps"][-1]["output"] is None

        running = agentic.agentic_events(path)
        first = await anext(running)
        assert first["type"] == "run.started"
        duplicate = await collect(path)
        assert (
            duplicate[-1]["type"] == "run.failed" and "already active" in duplicate[-1]["summary"]
        )
        assert get_run(path, duplicate[-1]["run_id"])["terminal"]["status"] == "failed"
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
        cancelled_trace = get_run(path, first["run_id"])
        assert cancelled_trace["terminal"]["status"] == "cancelled"
        assert cancelled_trace["steps"][-1]["status"] == "cancelled"
        started.clear()
        with patch("sigma.agentic.CALL_SECONDS", 0.01):
            timeout_events = await collect(path)
        assert (
            timeout_events[-1]["type"] == "run.failed"
            and "timed out" in timeout_events[-1]["summary"]
        )
        assert get_run(path, timeout_events[-1]["run_id"])["terminal"]["status"] == "failed"
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

    def storage_handler(request):
        if request.method == "GET":
            return httpx.Response(200, json={"object": "list", "data": [{"id": MODEL}]})
        payload = json.loads(request.content)
        output = CANDIDATE if payload["text"]["format"]["name"] == "strategy_explore" else DISTINCT
        return httpx.Response(200, json=provider_output(output))

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
    assert any(item["status"] == "cancelled" for item in list_runs(path))
    print("PASS ASGI browser disconnect cancels active agentic provider work")

    # Storage failure cannot present an unsaved draft as a successful run.
    with (
        patch("sigma.agentic.save_evidence", side_effect=ProjectError("fixture disk failure")),
        patch(
            "sigma.agentic.httpx.AsyncClient",
            side_effect=lambda **kwargs: REAL_CLIENT(
                transport=httpx.MockTransport(storage_handler),
                **kwargs,
            ),
        ),
    ):
        storage_failed = await collect(path)
    assert storage_failed[-1]["type"] == "run.failed"
    assert "evidence could not be saved" in storage_failed[-1]["summary"].lower()
    assert inspect_project(path).project.strategies[0].title == CANDIDATE["title"]
    source_before = SOURCE.read_bytes()
    source_id = json.loads(source_before)["id"]
    try:
        save_evidence(
            str(SOURCE.parent),
            {"schema_version": 1, "run_id": uuid4().hex, "project_id": source_id},
        )
    except ProjectError as exc:
        assert "immutable" in str(exc)
    else:
        raise AssertionError("Agentic evidence modified a Sample source project")
    assert SOURCE.read_bytes() == source_before
    print(
        "PASS durable run evidence round-trip, failed/incomplete work, storage failure and immutable Sample source"
    )


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
