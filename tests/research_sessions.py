"""Persistent A17 sessions use deterministic provider fixtures only."""

import asyncio
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import httpx

from sigma import research_sessions
from sigma.projects import (
    ProjectError,
    create_strategy,
    edit_strategy,
    initialize_project,
    set_strategy_enabled,
)

MODEL = "gpt-6.1-sol"
REAL_CLIENT = httpx.AsyncClient


def provider_response(value):
    return {
        "status": "completed",
        "usage": {
            "input_tokens": 120,
            "output_tokens": 80,
            "input_tokens_details": {"cached_tokens": 20},
        },
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


def skeptic(n, assessment="continue", stop_reason="recoverable_objection"):
    return {
        "assessment": assessment,
        "stop_reason": stop_reason,
        "response": f"Independent objection review for cycle {n}.",
        "objections": [f"Check boundary case {n}"],
        "remaining_obligations": [f"Resolve obligation {n}"],
        "next_question": f"Investigate the distinct consequence for cycle {n + 1}.",
        "objective_status": "partial",
        "solution_claim": "A partial consequence follows from the saved work.",
        "argument_summary": "The result uses the stated mechanism but does not settle the full objective.",
        "assumptions_reviewed": [f"Assumption {n}"],
        "proof_obligations": [f"Check obligation {n}"],
        "unresolved_objections": [],
        "supporting_cycles": list(range(1, n + 1)),
        "verification_status": "convincing_unverified",
        "strategy_contribution": "productive",
        "contribution_rationale": "The saved derivation advances the objective through the linked strategy.",
    }


async def wait_for(path, session_id, terminal=True):
    for _ in range(300):
        current = research_sessions.get_session(str(path), session_id)
        if (
            (current["status"] in {"completed", "ended", "failed", "stopped", "paused"})
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


async def test_disabled_strategy_never_starts_a_run(path: Path):
    view, strategy, _, _ = await setup(path)
    set_strategy_enabled(path, strategy.id, False)
    try:
        await research_sessions.start_session(
            str(path), strategy.id, str(uuid4()), view.project.id, "fixture-account"
        )
    except ProjectError as exc:
        assert "disabled" in str(exc).lower()
    else:
        raise AssertionError("A disabled strategy must not start a research session")
    assert research_sessions.list_sessions(str(path)) == []


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
        if payload["text"]["format"]["name"] == "research_skeptic":
            assert "stop_reason" in payload["text"]["format"]["schema"]["required"]
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

    assert finished["status"] == "ended" and finished["calls_used"] == 6
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
    assert finished["outcome"]["assessment"] == "mixed"
    assert "fixture-token" not in json.dumps(finished) and "fixture-account" not in json.dumps(
        finished
    )
    assert len(research_sessions.list_sessions(str(path))) == 1
    from sigma.api import export_project_view

    exported = export_project_view(str(path))
    exported_session = exported["research_sessions"][0]
    assert exported["export_version"] == 2
    assert exported_session["strategy_text"] == strategy.approach
    assert exported_session["problem"] == view.project.problem
    assert exported_session["steps"][0]["output"] == investigation(1)
    assert (
        exported_session["artifacts"][0]["id"] in exported_session["outcome"]["basis_artifact_ids"]
    )
    assert "fixture-token" not in json.dumps(exported) and "identity_hash" not in json.dumps(
        exported
    )
    round_trip = json.loads(json.dumps(exported))
    assert round_trip["research_sessions"] == exported["research_sessions"]
    assert [event["sequence"] for event in finished["events"]] == list(
        range(1, len(finished["events"]) + 1)
    )
    assert any(event["kind"] == "coordinator.started" for event in finished["events"])


async def test_pause_counts_interrupted_call(path: Path):
    view, strategy, credential, config = await setup(path)
    started_call = asyncio.Event()
    resumed_call = asyncio.Event()
    call_count = [0]
    hang = [True]

    async def handler(request):
        call_count[0] += 1
        started_call.set()
        if call_count[0] == 2:
            resumed_call.set()
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
        resumed = await research_sessions.control_session(str(path), started["id"], "resume")
        assert resumed["status"] == "queued"
        assert "may still complete or be billed" in resumed["message"]
        await asyncio.wait_for(resumed_call.wait(), 2)
        stopped = await research_sessions.control_session(str(path), started["id"], "stop")
        assert stopped["status"] == "stopped"
        await asyncio.sleep(0.02)
        stopped = research_sessions.get_session(str(path), started["id"])
        assert stopped["calls_used"] == 2 and stopped["steps"][-1]["status"] == "interrupted"
        stopped_elapsed = stopped["elapsed_seconds"]
        await asyncio.sleep(0.02)
        assert (
            research_sessions.get_session(str(path), started["id"])["elapsed_seconds"]
            == stopped_elapsed
        )

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
    assert rejected["status"] == "stopped"  # unavailable configuration leaves it stopped


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

    retained_path = path.parent / "assessment-error.sigma"
    retained_view, retained_strategy, retained_credential, retained_config = await setup(
        retained_path
    )
    outputs = [investigation(1), skeptic(1), investigation(2), httpx.ReadTimeout("")]

    async def fail_second_review(request):
        result = outputs.pop(0)
        if isinstance(result, Exception):
            raise result
        return httpx.Response(200, json=provider_response(result))

    with (
        patch.object(
            research_sessions, "auth_context", new=AsyncMock(return_value=retained_credential)
        ),
        patch.object(
            research_sessions, "configuration", new=AsyncMock(return_value=retained_config)
        ),
        patch(
            "sigma.research_sessions.httpx.AsyncClient",
            side_effect=lambda **kwargs: REAL_CLIENT(
                transport=httpx.MockTransport(fail_second_review), **kwargs
            ),
        ),
    ):
        started = await research_sessions.start_session(
            str(retained_path),
            retained_strategy.id,
            str(uuid4()),
            retained_view.project.id,
            retained_credential["identity"],
        )
        failed_review = await wait_for(retained_path, started["id"])
    assert failed_review["status"] == "failed" and len(failed_review["artifacts"]) == 1
    assert failed_review["outcome"]["assessment"] == "mixed"
    assert "timed out" in failed_review["message"].lower()
    assert failed_review["assessment_error"] == failed_review["message"]
    assert any("assessment failed" in item.lower() for item in failed_review["outcome"]["caveats"])

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
        "usage": {
            "input_tokens": 25,
            "output_tokens": 12,
            "input_tokens_details": {"cached_tokens": 5},
        },
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
    assert result == (output, {"input_tokens": 25, "cached_input_tokens": 5, "output_tokens": 12})


async def test_limits_snapshot_and_usage_cost(path: Path):
    view, strategy, credential, config = await setup(path)
    assert research_sessions.get_limits(str(path)) == research_sessions.DEFAULT_LIMITS
    limits = {
        "research_rounds": 1,
        "model_calls": 2,
        "session_duration_minutes": 10,
        "output_tokens_per_call": 700,
        "maximum_estimated_cost_usd": 0.1,
    }
    assert research_sessions.save_limits(str(path), limits) == limits
    outputs = [investigation(1), skeptic(1)]

    async def handler(request):
        payload = json.loads(request.content)
        assert payload["max_output_tokens"] == 700
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
        started = await research_sessions.start_session(
            str(path), strategy.id, str(uuid4()), view.project.id, credential["identity"], limits
        )
        future = {**limits, "model_calls": 4}
        research_sessions.save_limits(str(path), future)
        finished = await wait_for(path, started["id"])

    assert finished["call_limit"] == 2 and finished["cycle_limit"] == 1
    assert finished["duration_limit_minutes"] == 10 and finished["output_token_limit"] == 700
    assert finished["maximum_estimated_cost_usd"] == 0.1
    assert finished["cost_status"] == "available" and finished["estimated_cost_usd"] > 0
    assert all(step["token_usage"]["input_tokens"] == 120 for step in finished["steps"])
    assert research_sessions.get_limits(str(path)) == future


def test_limits_validation(path: Path):
    initialize_project(path, "Limits project", "A question")
    before = research_sessions.get_limits(str(path))
    invalid = [
        {**before, "model_calls": 21},
        {**before, "research_rounds": 4, "model_calls": 6},
        {**before, "research_rounds": 3, "model_calls": 5},
        {**before, "session_duration_minutes": 121},
        {**before, "output_tokens_per_call": 16385},
        {**before, "maximum_estimated_cost_usd": 0.001},
        {**before, "maximum_estimated_cost_usd": 100.01},
        {**before, "maximum_estimated_cost_usd": float("inf")},
        {**before, "research_rounds": 2.5},
    ]
    for candidate in invalid:
        try:
            research_sessions.save_limits(str(path), candidate)
        except ProjectError:
            pass
        else:
            raise AssertionError(f"invalid research limits were accepted: {candidate}")
    valid_upper = {
        **before,
        "research_rounds": 10,
        "model_calls": 20,
        "session_duration_minutes": 120,
        "output_tokens_per_call": 16384,
        "maximum_estimated_cost_usd": 100,
    }
    assert research_sessions.save_limits(str(path), valid_upper) == valid_upper
    research_sessions.save_limits(str(path), before)
    assert research_sessions.get_limits(str(path)) == before


async def test_legacy_limits_are_preserved(path: Path):
    view, strategy, credential, _ = await setup(path)
    legacy = {
        **research_sessions.DEFAULT_LIMITS,
        "session_duration_minutes": 180,
        "maximum_estimated_cost_usd": 500.0,
    }
    (path / "research-sessions").mkdir(mode=0o700)
    limits_file = path / "research-sessions" / "limits.json"
    limits_file.write_text(json.dumps(legacy), encoding="utf-8")
    assert research_sessions.get_limits(str(path)) == legacy
    try:
        research_sessions.save_limits(str(path), legacy)
    except ProjectError:
        pass
    else:
        raise AssertionError("legacy limits outside current bounds were silently accepted")
    assert research_sessions.get_limits(str(path)) == legacy
    try:
        await research_sessions.start_session(
            str(path), strategy.id, str(uuid4()), view.project.id, credential["identity"]
        )
    except ProjectError as exc:
        assert "120" in str(exc) or "100" in str(exc)
    else:
        raise AssertionError("a new session started with legacy limits outside current bounds")
    assert research_sessions.list_sessions(str(path)) == []


def test_outcome_classification():
    artifact = {
        "id": "artifact-1",
        "claim_or_question": "A bounded useful result",
        "skeptic_response": "No material objection remains in this review.",
        "open_obligations": [],
        "coordinator_decision": "stop_productive_conclusion",
    }
    positive = research_sessions._outcome({"status": "completed", "artifacts": [artifact]})
    assert positive["assessment"] == "mixed" and positive["basis_artifact_ids"] == ["artifact-1"]
    assert any("unverified" in caveat.lower() for caveat in positive["caveats"])
    no_next_path = research_sessions._outcome(
        {"status": "ended", "artifacts": [{**artifact, "coordinator_decision": "stop_no_progress"}]}
    )
    assert no_next_path["assessment"] == "mixed" and "objective unknown" in no_next_path["label"]
    negative = research_sessions._outcome(
        {
            "status": "completed",
            "artifacts": [{**artifact, "coordinator_decision": "stop_decisive_counterexample"}],
        }
    )
    assert negative["assessment"] == "negative"
    failed_partial = research_sessions._outcome(
        {"status": "failed", "artifacts": [{**artifact, "coordinator_decision": "continue"}]}
    )
    assert failed_partial["assessment"] == "mixed" and any(
        "incomplete" in caveat.lower() for caveat in failed_partial["caveats"]
    )
    pending = research_sessions._outcome({"status": "running", "artifacts": []})
    assert pending["assessment"] == "pending" and pending["provisional"]
    partial = research_sessions._outcome(
        {
            "status": "ended",
            "artifacts": [
                {
                    **artifact,
                    "coordinator_decision": "stop_no_progress",
                    "objective_review": {
                        "status": "partial",
                        "claim": "A candidate formula was found, but attainment is not proved.",
                        "verification_status": "incomplete",
                        "unresolved_objections": ["The construction is unsupported."],
                        "basis_artifact_ids": ["artifact-1"],
                    },
                }
            ],
        }
    )
    assert partial["assessment"] == "mixed" and "unsupported" in " ".join(partial["caveats"])
    # A reported assertion without a completed evidence review cannot become success.
    unsupported = research_sessions._outcome(
        {
            "status": "ended",
            "artifacts": [
                {
                    **artifact,
                    "coordinator_decision": "stop_no_progress",
                    "objective_review": {
                        "status": "not_achieved",
                        "claim": "The claim is asserted without a derivation.",
                        "verification_status": "incomplete",
                        "unresolved_objections": ["No supporting construction."],
                        "basis_artifact_ids": [],
                    },
                }
            ],
        }
    )
    assert (
        unsupported["assessment"] == "mixed"
        and "No supporting construction." in unsupported["caveats"]
    )
    # A positive research finding does not rewrite a later execution failure.
    positive_but_failed = research_sessions._outcome(
        {
            "status": "failed",
            "artifacts": [
                {
                    **artifact,
                    "objective_review": {
                        "status": "achieved",
                        "claim": "A candidate answer",
                        "verification_status": "convincing_unverified",
                        "unresolved_objections": [],
                        "basis_artifact_ids": ["artifact-1"],
                    },
                }
            ],
        }
    )
    assert positive_but_failed["assessment"] == "positive" and any(
        "Execution failed" in caveat for caveat in positive_but_failed["caveats"]
    )
    assessments = research_sessions._strategy_assessments(
        {
            "strategy_snapshot": [
                {"id": "s1", "title": "Contributing", "eligibility": "eligible"},
                {"id": "s2", "title": "Unused", "eligibility": "eligible"},
                {"id": "s3", "title": "Disabled", "eligibility": "disabled"},
            ],
            "artifacts": [
                {
                    "id": "a1",
                    "strategy_id": "s1",
                    "strategy_review": {
                        "assessment": "solution",
                        "rationale": "Linked proof evidence.",
                        "basis_artifact_ids": ["a1"],
                    },
                }
            ],
        }
    )
    assert [row["assessment"] for row in assessments] == [
        "contributed_to_solution",
        "not_used",
        "disabled",
    ]
    assert research_sessions._strategy_assessments({"artifacts": []})[0]["assessment"] == "unknown"
    shared_solution = research_sessions._strategy_assessments(
        {
            "strategy_snapshot": [
                {"id": "s1", "title": "Counting", "eligibility": "eligible"},
                {"id": "s2", "title": "Construction", "eligibility": "eligible"},
                {"id": "s3", "title": "Unproductive", "eligibility": "eligible"},
            ],
            "artifacts": [
                {
                    "id": "a1",
                    "strategy_id": "s1",
                    "strategy_review": {
                        "assessment": "solution",
                        "rationale": "Provides the upper bound.",
                        "basis_artifact_ids": ["a1"],
                    },
                },
                {
                    "id": "a2",
                    "strategy_id": "s2",
                    "strategy_review": {
                        "assessment": "solution",
                        "rationale": "Provides the attaining construction.",
                        "basis_artifact_ids": ["a2"],
                    },
                },
                {
                    "id": "a3",
                    "strategy_id": "s3",
                    "strategy_review": {
                        "assessment": "unproductive",
                        "rationale": "No evidence advanced the objective.",
                        "basis_artifact_ids": ["a3"],
                    },
                },
            ],
        }
    )
    assert [row["assessment"] for row in shared_solution] == [
        "contributed_to_solution",
        "contributed_to_solution",
        "unproductive",
    ]


async def test_maximum_regions_solution_and_frozen_attribution(path: Path):
    problem = (
        "For each integer n >= 0, determine the maximum number of regions formed by n lines. "
        "Derive a formula, prove the upper bound, and show an arrangement attains it, including n=0."
    )
    view = initialize_project(path, "Maximum Regions Formed by Lines", problem)
    strategy = create_strategy(
        path,
        "Incremental region counting with an explicit maximizing arrangement",
        "Insert lines one by one, bound each increment, and exhibit an arrangement attaining every bound.",
    ).project.strategies[0]
    create_strategy(path, "Euler face count", "Count faces through a planar graph.")
    credential = {
        "identity": "fixture-account",
        "mode": "api_key",
        "token": "fixture-token",
        "status": "connected",
    }
    config = {"available": True, "model": MODEL, "reasoning_effort": "high"}
    proof = {
        "claim": "R(n) = 1 + n(n+1)/2 for every n >= 0.",
        "method": "Each region is an intersection of open half-planes: points with a fixed choice of side for every line form a convex set, and different side choices cannot belong to the same component. The kth line meets at most k-1 earlier lines, so adds at most k regions. Two different pieces of an inserted line cannot lie in the same region, since convexity would put an intervening point on an earlier line in that region. Each encountered region is open, so a small disk around an intersection has points on both sides of the inserted line. Lines y=kx+k^2 meet each earlier line at distinct x coordinates, attaining k increments. Summing gives the formula; the empty arrangement has one region.",
        "assumptions": ["Lines are distinct straight lines in the Euclidean plane."],
        "evidence_status": "Complete unverified argument; no formal checker was run.",
        "open_obligations": [],
    }
    review = {
        **skeptic(1, "stop", "productive_conclusion"),
        "stop_reason": "decisive_counterexample",
        "response": "The alleged duplicate-line case is not a counterexample; after checking the stated distinct-line assumption, there is no counterexample. The described upper bound and construction complete the candidate argument with no substantive mathematical objection.",
        "objections": [],
        "remaining_obligations": [],
        "next_question": "",
        "objective_status": "achieved",
        "solution_claim": "R(n) = 1 + n(n+1)/2 for all n >= 0.",
        "argument_summary": "At most k regions are added at step k, and the explicit family y=kx+k^2 attains every increment; sum the increments, the empty arrangement gives R(0)=1, and verify the small values.",
        "assumptions_reviewed": ["Distinct straight lines in the Euclidean plane."],
        "proof_obligations": [],
        "verification_status": "incomplete",
        "unresolved_objections": [],
        "supporting_cycles": [1],
        "strategy_contribution": "solution",
        "contribution_rationale": "The linked argument supplies both the matching upper bound and an explicit attaining construction.",
    }
    outputs = [proof, review]
    assert research_sessions._maximum_regions_proof_obligations(problem, proof, review)

    # This mirrors a real Maximum Regions run: the initial artifact contains a
    # complete candidate argument, then later cycles clarify the small-disk
    # lemma and restate the upper bound while each individual skeptic review
    # flags the current draft as truncated. Assessment must aggregate history.
    historical_investigations = [
        {
            **proof,
            "method": (
                "The kth line has at most k − 1 distinct intersection points, hence adds at most k regions. "
                "The empty arrangement has one region. Attainment: choose L_k: y = kx + k²; "
                "the intersection coordinates −(i + k) are distinct, so each insertion adds k. "
                "Small-value checks: R(0) = 1, R(1) = 2, R(2) = 4, R(3) = 7, R(4) = 11."
            ),
        },
        {
            **proof,
            "method": "Each region is a nonempty intersection of open half-planes with one of the same side choices for every point, so it is convex and connected. Different pieces lie in different regions. Since a region is open, a small disk around an intersection contains points on both sides of the new line.",
        },
        {
            **proof,
            "method": "The complete upper-bound argument sums increments from the initial single region.",
        },
    ]
    historical_reviews = [
        {
            **review,
            "response": "No mathematical counterexample is apparent in the supplied argument.",
            "objective_status": "not_achieved",
            "objections": ["The current complete draft could state the checks more prominently."],
        },
        {
            **review,
            "response": "No mathematical counterexample is apparent; the current draft is truncated before the construction.",
            "objections": ["Current write-up is truncated before attainment."],
            "remaining_obligations": ["Repeat the construction in the current write-up."],
            "objective_status": "not_achieved",
        },
        {
            **review,
            "response": "No mathematical counterexample is apparent; earlier artifact contains the construction.",
            "objections": ["Current write-up is truncated before the construction."],
            "remaining_obligations": ["Repeat the construction in the current write-up."],
            "objective_status": "not_achieved",
        },
    ]
    assert research_sessions._maximum_regions_proof_obligations(
        problem, historical_investigations, historical_reviews
    )
    assert (
        research_sessions._maximum_regions_proof_obligations(
            problem,
            [historical_investigations[0]],
            [
                {
                    **historical_reviews[0],
                    "objections": ["The formula is contradicted by a counterexample."],
                }
            ],
        )
        is None
    )

    async def handler(request):
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
        started = await research_sessions.start_session(
            str(path), strategy.id, str(uuid4()), view.project.id, credential["identity"]
        )
        finished = await wait_for(path, started["id"])
        assert finished["status"] == "ended"
        assert finished["outcome"]["assessment"] == "positive"
        assert finished["outcome"]["label"] == "Positive · solution candidate (unverified)"
        assert finished["artifacts"][0]["coordinator_decision"] == "stop_productive_conclusion"
        assert any(
            event["kind"] == "coordinator.assessment_conflict" for event in finished["events"]
        )
        assert any(
            event["kind"] == "coordinator.assessment_reconciled" for event in finished["events"]
        )
        assert len(finished["outcome"]["solution_review"]["proof_obligations"]) == 4
        assert (
            finished["outcome"]["solution_review"]["verification_status"] == "convincing_unverified"
        )
        assert finished["outcome"]["solution_review"]["basis_artifact_ids"] == [
            finished["artifacts"][0]["id"]
        ]
        assert any("unverified" in item.lower() for item in finished["outcome"]["caveats"])
        rows = finished["strategy_assessments"]
        assert [row["assessment"] for row in rows] == ["contributed_to_solution", "not_used"]
        assert rows[0]["basis_artifact_ids"] == [finished["artifacts"][0]["id"]]
        assert rows[1]["basis_artifact_ids"] == []

        # Three cycles can distribute a complete proof across saved artifacts
        # while the final skeptic asks for a cleaner, self-contained restatement.
        outputs.extend(
            [
                {
                    **proof,
                    "claim": "R(n) = 1 + n(n+1)/2 is the maximum for n distinct lines.",
                    "method": (
                        "The kth line has at most k − 1 distinct intersection points and adds at most k regions. "
                        "Each old region is open and convex; a small disk around an intersection contains points "
                        "on both sides of the inserted line, giving the exact increment. Summing the upper bound "
                        "yields R(n) = 1 + n(n + 1)/2."
                    ),
                },
                {
                    **review,
                    "assessment": "revise",
                    "stop_reason": "recoverable_objection",
                    "response": "No mathematical counterexample is apparent. The upper-bound step is coherent; attainment and boundary checks remain to be supplied.",
                    "argument_summary": "The insertion bound gives the proposed quadratic upper bound.",
                    "objections": ["The attaining construction and boundary checks remain open."],
                    "remaining_obligations": [
                        "Provide an attaining construction and handle n = 0."
                    ],
                    "next_question": "Review whether the existing saved argument settles the requested result.",
                    "objective_status": "not_achieved",
                    "verification_status": "incomplete",
                },
                {
                    **proof,
                    "method": "Each region is a nonempty intersection of open half-planes with one of the same side choices for every point, so it is convex and connected. Different pieces of the inserted line lie in different old regions. For L_k: y = kx + k², the coordinates −(i + k) are distinct, so each insertion attains k. This supplies the matching lower bound.",
                },
                {
                    **review,
                    "assessment": "continue",
                    "stop_reason": "recoverable_objection",
                    "response": "No mathematical counterexample is apparent; the explicit family gives the matching lower bound.",
                    "argument_summary": "The construction attains each insertion bound.",
                    "objections": ["The boundary case and small-value checks remain to be stated."],
                    "remaining_obligations": ["Handle n = 0 and check small values."],
                    "next_question": "Inspect the saved construction evidence.",
                    "objective_status": "not_achieved",
                    "verification_status": "incomplete",
                    "supporting_cycles": [1, 2],
                },
                {
                    **proof,
                    "method": "The empty arrangement has one region. Small-value checks: R(0) = 1, R(1) = 2, R(2) = 4, R(3) = 7, R(4) = 11.",
                },
                {
                    **review,
                    "assessment": "continue",
                    "stop_reason": "recoverable_objection",
                    "response": "No mathematical counterexample is apparent; the boundary case and small values are now checked.",
                    "argument_summary": "The empty arrangement and small values match the formula.",
                    "objections": [
                        "The current response ends before restating small-value checks."
                    ],
                    "remaining_obligations": ["Repeat small-value checks in the current response."],
                    "next_question": "None; review the ordered saved evidence.",
                    "objective_status": "not_achieved",
                    "verification_status": "incomplete",
                    "supporting_cycles": [1, 2, 3],
                },
            ]
        )
        aggregate_started = await research_sessions.start_session(
            str(path), strategy.id, str(uuid4()), view.project.id, credential["identity"]
        )
        aggregate = await wait_for(path, aggregate_started["id"])
        assert aggregate["status"] == "ended", (
            aggregate["message"],
            aggregate.get("assessment_error"),
            aggregate["steps"][-1],
        )
        assert aggregate["terminal_reason"] == "stop_productive_conclusion"
        assert aggregate["outcome"]["assessment"] == "positive"
        assert aggregate["outcome"]["solution_review"]["status"] == "achieved"
        assert aggregate["outcome"]["solution_review"]["verification_status"] == (
            "convincing_unverified"
        )
        assert aggregate["strategy_assessments"][0]["assessment"] == "contributed_to_solution"
        assert len(aggregate["outcome"]["solution_review"]["basis_artifact_ids"]) == 3, aggregate[
            "outcome"
        ]["solution_review"]
        assert aggregate["outcome"]["solution_review"]["resolved_objections"]
        assert (
            research_sessions.get_session(str(path), aggregate_started["id"])[
                "strategy_assessments"
            ]
            == aggregate["strategy_assessments"]
        )

        # Project edits after the session do not rewrite its saved display order or labels.
        edit_strategy(str(path), strategy.id, "Renamed later", strategy.approach + " Later edit.")
        reopened = research_sessions.get_session(str(path), started["id"])
        assert reopened["strategy_assessments"] == rows
        assert reopened["strategy_assessments"][0]["strategy_title"] == strategy.title


async def test_remove_terminal_and_monotonic_number(path: Path):
    view, strategy, credential, config = await setup(path)
    outputs = [investigation(1), skeptic(1, "stop", "productive_conclusion")]

    async def handler(request):
        return httpx.Response(200, json=provider_response(outputs.pop(0)))

    async def start():
        return await research_sessions.start_session(
            str(path), strategy.id, str(uuid4()), view.project.id, credential["identity"]
        )

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
        first = await start()
        finished = await wait_for(path, first["id"])
        assert finished["session_number"] == 1 and finished["status"] == "ended"
        assert finished["outcome"]["assessment"] == "mixed"
        try:
            research_sessions.remove_session(str(path), first["id"], "stale-revision")
        except ProjectError as exc:
            assert "changed" in str(exc).lower()
        else:
            raise AssertionError("stale session removal was accepted")
        removed = research_sessions.remove_session(str(path), first["id"], finished["updated_at"])
        assert removed == {"removed": True, "id": first["id"], "session_number": 1}
        assert research_sessions.list_sessions(str(path)) == []
        assert (path / "project.json").exists()
        assert research_sessions.get_limits(str(path)) == research_sessions.DEFAULT_LIMITS
        outputs[:] = [investigation(2), skeptic(2, "stop", "productive_conclusion")]
        second = await start()
        assert second["session_number"] == 2
        await research_sessions.control_session(str(path), second["id"], "stop")


async def test_single_project_admission(path: Path):
    view, strategy, credential, config = await setup(path)
    entered, release = asyncio.Event(), asyncio.Event()

    async def handler(request):
        entered.set()
        await entered.wait()
        await release.wait()
        return httpx.Response(200, json=provider_response(investigation(1)))

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
        await asyncio.wait_for(entered.wait(), 2)
        try:
            await research_sessions.start_session(
                str(path), strategy.id, str(uuid4()), view.project.id, credential["identity"]
            )
        except ProjectError as exc:
            assert "research worker is active" in str(exc) or "queued or running" in str(exc)
        else:
            raise AssertionError("a second session was admitted for one project")
        paused = await research_sessions.control_session(str(path), started["id"], "pause")
        assert paused["status"] == "paused"
        next_session = await research_sessions.start_session(
            str(path), strategy.id, str(uuid4()), view.project.id, credential["identity"]
        )
        assert next_session["status"] == "queued"
        await research_sessions.control_session(str(path), next_session["id"], "stop")
        assert research_sessions.get_session(str(path), started["id"])["status"] == "paused"


async def test_response_transport_and_parsed_bounds(path: Path):
    view, strategy, credential, config = await setup(path)
    oversized_projects = path.parent / "transport.sigma"
    transport_view, transport_strategy, _, _ = await setup(oversized_projects)

    async def oversized_transport(request):
        response = provider_response(investigation(1))
        response["padding"] = "x" * 1_010_000
        return httpx.Response(200, json=response)

    with (
        patch.object(research_sessions, "auth_context", new=AsyncMock(return_value=credential)),
        patch.object(research_sessions, "configuration", new=AsyncMock(return_value=config)),
        patch(
            "sigma.research_sessions.httpx.AsyncClient",
            side_effect=lambda **kwargs: REAL_CLIENT(
                transport=httpx.MockTransport(oversized_transport), **kwargs
            ),
        ),
    ):
        started = await research_sessions.start_session(
            str(oversized_projects),
            transport_strategy.id,
            str(uuid4()),
            transport_view.project.id,
            credential["identity"],
        )
        failed = await wait_for(oversized_projects, started["id"])
    assert failed["status"] == "failed" and "1 MB safety bound" in failed["message"]
    assert failed["artifacts"] == []

    async def oversized_parsed(request):
        response = provider_response(investigation(1))
        response["output"][0]["content"][0]["text"] += " " * 70_000
        return httpx.Response(200, json=response)

    with (
        patch.object(research_sessions, "auth_context", new=AsyncMock(return_value=credential)),
        patch.object(research_sessions, "configuration", new=AsyncMock(return_value=config)),
        patch(
            "sigma.research_sessions.httpx.AsyncClient",
            side_effect=lambda **kwargs: REAL_CLIENT(
                transport=httpx.MockTransport(oversized_parsed), **kwargs
            ),
        ),
    ):
        started = await research_sessions.start_session(
            str(path), strategy.id, str(uuid4()), view.project.id, credential["identity"]
        )
        failed = await wait_for(path, started["id"])
    assert failed["status"] == "failed" and "Parsed research output exceeded" in failed["message"]
    assert failed["artifacts"] == []


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
        asyncio.run(test_disabled_strategy_never_starts_a_run(root / "disabled.sigma"))
        asyncio.run(test_three_cycles_and_idempotency(root / "cycles.sigma"))
        asyncio.run(test_pause_counts_interrupted_call(root / "pause.sigma"))
        asyncio.run(test_malformed_output_and_restart(root / "recovery.sigma"))
        asyncio.run(test_chatgpt_stream(root / "chatgpt.sigma"))
        asyncio.run(test_limits_snapshot_and_usage_cost(root / "limits.sigma"))
        test_limits_validation(root / "invalid-limits.sigma")
        asyncio.run(test_legacy_limits_are_preserved(root / "legacy-limits.sigma"))
        asyncio.run(test_single_project_admission(root / "single-session.sigma"))
        asyncio.run(test_response_transport_and_parsed_bounds(root / "parsed.sigma"))
        asyncio.run(test_changed_bindings_pause_before_provider(root / "binding.sigma"))
        asyncio.run(test_storage_limit_pauses_without_artifact(root / "storage.sigma"))
        asyncio.run(test_remove_terminal_and_monotonic_number(root / "removal.sigma"))
        asyncio.run(
            test_maximum_regions_solution_and_frozen_attribution(root / "maximum-regions.sigma")
        )
        test_outcome_classification()
        assert research_sessions.coordinate_decision(
            "stop", "recoverable_objection", "Test the omitted boundary case", [], 1, 3, 2, 6
        ) == ("revise", "Test the omitted boundary case")
        assert research_sessions.coordinate_decision(
            "stop", "decisive_counterexample", "", [], 1, 3, 2, 6
        ) == ("stop_decisive_counterexample", "")
        assert research_sessions.coordinate_decision("stop", "no_progress", "", [], 1, 3, 2, 6) == (
            "stop_no_progress",
            "",
        )
        assert research_sessions.coordinate_decision(
            "stop", "productive_conclusion", "", [], 1, 3, 2, 6
        ) == ("stop_productive_conclusion", "")
        assert research_sessions.coordinate_decision(
            "continue", "recoverable_objection", "Next test", [], 3, 3, 6, 6
        ) == ("stop_budget_exhausted", "")
    print("Persistent research session scenarios passed.")


if __name__ == "__main__":
    main()
