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

from sigma import agentic, chatgpt_auth, research_sessions
from sigma.agentic_evidence import get_run, list_runs
from sigma.agentic_evidence import save as save_evidence
from sigma.api import agentic_runs_view, app, export_project_view
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
    "prior_finding_ids": [],
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


async def exercise(
    path: str,
    outputs: list[dict],
    before: bytes,
    *,
    call_limit: int = 6,
    expected_problem_prefix: str = "How many length-n binary strings avoid two consecutive 1s?",
):
    limits = dict(research_sessions.DEFAULT_LIMITS)
    limits["model_calls"] = call_limit
    limits["research_rounds"] = min(limits["research_rounds"], call_limit // 2)
    research_sessions.save_limits(path, limits)
    calls: list[dict] = []

    async def handler(request):
        if request.method == "GET":
            return httpx.Response(200, json={"object": "list", "data": [{"id": MODEL}]})
        payload = json.loads(request.content)
        assert payload["model"] == MODEL and payload["store"] is False
        assert payload["reasoning"] == {"effort": "high"}
        assert payload["max_output_tokens"] == agentic.MAX_OUTPUT_TOKENS
        assert payload["text"]["format"]["strict"] is True
        assert payload["text"]["format"]["name"].startswith("strategy_")
        role = payload["text"]["format"]["name"]
        if role == "strategy_explore":
            assert "bounded STRATEGY" in payload["instructions"]
            assert "not a complete solution" in payload["instructions"]
        elif role == "strategy_revise":
            assert "targeted revision" in payload["instructions"]
            assert "bounded approach" in payload["instructions"]
        elif role == "strategy_challenge":
            assert "not an established solution" in payload["instructions"]
            assert "external evidence" in payload["instructions"]
        context = json.loads(payload["input"])
        assert context["project"]["research_problem"].startswith(expected_problem_prefix)
        calls.append({"role": payload["text"]["format"]["name"], "context": context})
        return httpx.Response(200, json=provider_output(outputs.pop(0)))

    def client(**kwargs):
        return REAL_CLIENT(transport=httpx.MockTransport(handler), **kwargs)

    with patch("sigma.agentic.httpx.AsyncClient", side_effect=client):
        events = await collect(path)
    assert (Path(path) / "project.json").read_bytes() == before
    assert [event["sequence"] for event in events] == list(range(1, len(events) + 1))
    assert len({event["run_id"] for event in events}) == 1
    assert events[0]["type"] == "run.started" and events[0]["max_calls"] == call_limit
    assert len(calls) <= call_limit and not outputs, (calls, outputs)
    return events, calls


async def main_async(root: Path):
    await chatgpt_auth.select("api_key")
    source_before = SOURCE.read_bytes()
    sample = sample_projects()["projects"]
    assert any(
        item["id"] == "counting-constrained-binary-strings" and item["strategy_count"] == 1
        for item in sample
    )
    view = open_sample_project("counting-constrained-binary-strings")
    assert len(view.project.strategies) == len(view.project.active_order) == 1
    path = view.path
    before = (Path(path) / "project.json").read_bytes()
    assert before != source_before
    assert view.project.id != "counting-constrained-binary-strings"
    assert view.project.title == "Counting Constrained Binary Strings v1"

    # Provider fields capped at 300 characters must never expose clipped prose.
    clipped = {
        **CANDIDATE,
        "summary": ("A complete sentence. " + "This unfinished continuation " * 12)[:300],
    }
    clipped_review = {
        **DISTINCT,
        "public_summary": ("A valid review sentence. " + "Unfinished reviewer text " * 12)[:300],
    }
    events, _ = await exercise(path, [clipped, clipped_review], before)
    assert events[-1]["type"] == "run.completed"
    assert events[-1]["draft"]["summary"] == "A complete sentence."
    trace = get_run(path, events[-1]["run_id"])
    assert trace["steps"][0]["output"]["summary"] == "A complete sentence."
    assert trace["steps"][1]["output"]["public_summary"] == "A valid review sentence."
    assert trace["terminal"]["summary"] == "A valid review sentence."

    incomplete = {**CANDIDATE, "summary": "An unfinished summary without punctuation"}

    async def incomplete_handler(request):
        return httpx.Response(200, json=provider_output(incomplete))

    with patch(
        "sigma.agentic.httpx.AsyncClient",
        side_effect=lambda **kwargs: REAL_CLIENT(
            transport=httpx.MockTransport(incomplete_handler), **kwargs
        ),
    ):
        rejected = await collect(path)
    assert rejected[-1]["type"] == "run.failed"
    assert "malformed research output" in rejected[-1]["summary"]
    assert get_run(path, rejected[-1]["run_id"])["terminal"]["status"] == "failed"

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
    assert export["export_version"] == 2
    assert export["project"]["id"] == view.project.id
    assert len(export["project"]["strategies"]) == 1
    assert any(run["run_id"] == events[-1]["run_id"] for run in export["agentic_runs"])
    assert any(run["steps"][0]["output"] == CANDIDATE for run in export["agentic_runs"])
    assert any(event["type"] == "activity.started" for event in events)
    assert any(event["type"] == "decision" and event["outcome"] == "present" for event in events)
    assert len(inspect_project(path).project.strategies) == 1
    provenance = accepted_provenance(events[-1]["receipt"], path)
    saved = create_strategy(
        path,
        events[-1]["draft"]["title"],
        events[-1]["draft"]["approach"],
        events[-1]["draft"]["summary"],
        provenance,
    )
    assert (
        len(saved.project.strategies) == 2 and saved.project.strategies[1].provenance == provenance
    )
    independent = open_sample_project("counting-constrained-binary-strings")
    assert independent.project.id != view.project.id
    assert len(independent.project.strategies) == len(independent.project.active_order) == 1
    assert SOURCE.read_bytes() == source_before
    print(
        "PASS seeded sample, real explore/challenge events, unsaved review, explicit acceptance, reopen and immutable source"
    )

    before = (Path(path) / "project.json").read_bytes()
    events, calls = await exercise(path, [ALTERNATIVE, DISTINCT], before)
    assert events[-1]["type"] == "run.completed"
    assert any(
        item["approach"].startswith(CANDIDATE["approach"])
        for item in calls[0]["context"]["project"]["existing_strategies"]
    )
    assert events[-1]["draft"]["title"] == ALTERNATIVE["title"]
    research_sessions._save(
        path,
        {
            "id": "session-history",
            "session_number": 1,
            "project_path": str(Path(path).resolve()),
            "status": "completed",
            "created_at": "2026-01-01T00:00:00+00:00",
            "strategy_title": "Boundary counterexample",
            "artifacts": [
                {
                    "id": "finding-history",
                    "sequence": 1,
                    "strategy_id": "strategy-history",
                    "claim_or_question": "A binary strings counterexample appears at the boundary.",
                    "method": "Compare shifted positions at the smallest boundary case.",
                    "evidence_status": "Finite counterexample reproduced; general explanation open.",
                    "objections": ["The example may not generalize."],
                    "open_obligations": ["Explain the boundary behavior."],
                    "coordinator_decision": "continue",
                    "next_question": "Why does the position shift fail at the boundary?",
                }
            ],
        },
    )
    history_candidate = {
        **ALTERNATIVE,
        "prior_finding_ids": ["finding-history"],
    }
    events, calls = await exercise(path, [history_candidate, DISTINCT], before)
    assert (
        calls[0]["context"]["project"]["prior_research_findings"][0]["session_id"]
        == "session-history"
    )
    assert "finding-history" in events[-1]["draft"]["approach"]
    assert "session-history" in events[-1]["draft"]["approach"]
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
    events, calls = await exercise(
        path,
        [CANDIDATE, OVERLAP, CANDIDATE, OVERLAP],
        before,
        call_limit=4,
    )
    assert events[-1]["type"] == "run.stopped" and len(calls) == 4
    stopped_trace = get_run(path, events[-1]["run_id"])
    assert stopped_trace["terminal"]["status"] == "stopped"
    assert stopped_trace["steps"][1]["effective_assessment"] == "overlapping"
    assert stopped_trace["steps"][1]["override_reason"] is None
    events, calls = await exercise(
        path,
        [ALTERNATIVE, review_revision, ALTERNATIVE, OVERLAP, ALTERNATIVE, review_revision],
        before,
        call_limit=6,
    )
    assert events[-1]["type"] == "run.stopped"
    assert "6 of 6 configured model calls" in events[-1]["summary"]
    assert "passed independent review" in events[-1]["summary"]
    assert len(calls) == 6
    assert len(inspect_project(path).project.strategies) == 2

    # A large configured ceiling does not become a target; the reviewer can
    # trigger one targeted revision and a fresh independent review.
    events, calls = await exercise(
        path,
        [ALTERNATIVE, review_revision, ALTERNATIVE, DISTINCT],
        before,
        call_limit=30,
    )
    assert events[-1]["type"] == "run.completed"
    assert len(calls) == 4
    assert calls[-1]["role"] == "strategy_challenge"
    assert get_run(path, events[-1]["run_id"])["steps"][-1]["call_index"] == 4

    # Strategy length grows well beyond the legacy limit, with room for
    # reviewer-facing mechanism and evidence notes in the assembled field.
    long_candidate = agentic.Candidate.model_validate(
        {
            **CANDIDATE,
            "approach": "A" * 40000,
            "first_tests": "T" * 700,
            "assumptions": "S" * 600,
            "failure_modes": "F" * 700,
            "mechanism": "M" * 800,
            "evidence_boundary": "E" * 800,
        }
    )
    assembled = (
        f"{long_candidate.approach}\n\nMechanism\n{long_candidate.mechanism}"
        f"\n\nEvidence status\n{long_candidate.evidence_boundary}"
    )
    assert 10_000 < len(assembled) < agentic.MAX_CANDIDATE_APPROACH
    assert (
        agentic.Proposal.model_validate(
            {
                **long_candidate.model_dump(
                    exclude={"mechanism", "evidence_boundary", "prior_finding_ids"}
                ),
                "approach": assembled,
            }
        ).approach
        == assembled
    )

    events, calls = await exercise(
        path,
        [CANDIDATE, OVERLAP, CANDIDATE, OVERLAP],
        before,
        call_limit=30,
    )
    assert events[-1]["type"] == "run.stopped" and len(calls) == 4
    assert "passed independent review" in events[-1]["summary"]
    assert events[-1]["sequence"] <= agentic.MAX_EVENTS

    narrow_path = open_sample_project("operation-narrow-passage").path
    narrow_view = inspect_project(narrow_path)
    assert len(narrow_view.project.strategies) == 2
    assert research_sessions.get_limits(narrow_path)["model_calls"] == 12
    narrow_before = (Path(narrow_path) / "project.json").read_bytes()
    events, calls = await exercise(
        narrow_path,
        [
            ALTERNATIVE,
            review_revision,
            ALTERNATIVE,
            DISTINCT,
        ],
        narrow_before,
        call_limit=30,
        expected_problem_prefix="Imagine a fictional crisis at Second Thomas Shoal",
    )
    assert events[-1]["type"] == "run.completed" and len(calls) == 4
    assert len(inspect_project(narrow_path).project.strategies) == 2
    print(
        "PASS settings-backed call budgets, extended candidate fields, narrow-passage sample flow, skeptical revision and no mutation"
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
    assert any(
        strategy.title == CANDIDATE["title"]
        for strategy in inspect_project(path).project.strategies
    )
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
