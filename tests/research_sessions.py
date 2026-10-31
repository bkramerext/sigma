"""Persistent A17 sessions use deterministic provider fixtures only."""

import asyncio
import json
import shutil
import sys
import time
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from html import escape
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import httpx

from sigma import agentic, papers, proposals, python_sandbox, research_sessions, text_views
from sigma.projects import (
    ProjectError,
    create_strategy,
    edit_strategy,
    initialize_project,
    inspect_project,
    project_path,
    set_strategy_enabled,
)
from sigma.research_budget import BudgetExceeded

MODEL = "gpt-6.1-sol"
REAL_CLIENT = httpx.AsyncClient


def test_transient_provider_failure_classes_are_bounded_and_permanent_errors_not_retried():
    assert research_sessions._transient_failure_kind(TimeoutError()) == "timeout"
    assert research_sessions._transient_failure_kind(httpx.ReadError("stream reset")) == (
        "transport_interrupted"
    )
    assert (
        research_sessions._transient_failure_kind(
            research_sessions.ChatGPTProviderRejection(
                "temporary provider failure",
                state="unavailable",
                code=None,
                http_status=503,
                streamed=False,
            )
        )
        == "provider_temporary"
    )
    rate_limit = research_sessions.ChatGPTProviderRejection(
        "temporary rate limit",
        state="limited",
        code=None,
        http_status=429,
        streamed=False,
    )
    assert research_sessions._provider_failure_fields(rate_limit)["failure_kind"] == (
        "provider_rate_limited"
    )
    assert research_sessions._transient_failure_kind(rate_limit) == "provider_rate_limited"
    account_limit = research_sessions.ChatGPTProviderRejection(
        "plan usage limit",
        state="limited",
        code="subscription_sharing_usage_limit_exceeded",
        http_status=429,
        streamed=False,
    )
    assert research_sessions._transient_failure_kind(account_limit) is None
    assert (
        research_sessions._transient_failure_kind(
            ProjectError(
                "ChatGPT stream ended without a valid response.completed. No strategy was saved."
            )
        )
        == "stream_incomplete"
    )
    assert (
        research_sessions._transient_failure_kind(
            research_sessions.ChatGPTProviderRejection(
                "invalid request",
                state="error",
                code=None,
                http_status=400,
                streamed=False,
            )
        )
        is None
    )


def test_portfolio_termination_does_not_promote_scheduler_terminal_to_research_success():
    record = {"calls_used": 7, "call_limit": 30, "cycle": 2, "cycle_limit": 3}
    failed, message = research_sessions._portfolio_termination(
        record,
        [
            {
                "strategy_title": "Warp Drive",
                "status": "failed",
                "last_decision": None,
                "artifacts": ["saved-finding"],
            }
        ],
    )
    assert failed == "provider_or_strategy_failure"
    assert "7 of 30" in message and "round 2 of 3" in message
    assert "1 finding was preserved" in message and "incomplete" in message

    completed, success_message = research_sessions._portfolio_termination(
        record,
        [
            {
                "strategy_title": "Converged route",
                "status": "ended",
                "last_decision": "stop_productive_conclusion",
                "reason": "Independent checks agree within the stated scope.",
            }
        ],
    )
    assert completed == "research_completed_early"
    assert "7 of 30" in success_message
    assert "Independent checks agree" in success_message


def test_sponsorship_does_not_shorten_project_duration():
    configured = {**research_sessions.DEFAULT_LIMITS, "session_duration_minutes": 60}
    with patch.object(research_sessions.cloud_workspaces, "enabled", return_value=True):
        effective = research_sessions._effective_limits(configured)
    assert configured["session_duration_minutes"] == 60
    assert effective["session_duration_minutes"] == 60


async def test_unlimited_duration_completes_without_session_deadline(path: Path):
    view, strategy, credential, config = await setup(path)
    limits = {
        **research_sessions.DEFAULT_LIMITS,
        "session_duration_minutes": None,
        "research_rounds": 1,
        "model_calls": 2,
    }
    research_sessions.save_limits(str(path), limits)
    assert research_sessions.get_limits(str(path))["session_duration_minutes"] is None
    with patch.object(research_sessions.cloud_workspaces, "enabled", return_value=True):
        assert research_sessions._effective_limits(limits)["session_duration_minutes"] is None

    async def handler(request):
        payload = json.loads(request.content)
        result = (
            investigation(1)
            if payload["text"]["format"]["name"] == "research_investigator"
            else skeptic(1, "stop", "no_progress")
        )
        return httpx.Response(200, json=provider_response(result))

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
            str(path),
            strategy.id,
            str(uuid4()),
            view.project.id,
            credential["identity"],
            expected_limits=limits,
        )
        assert started["deadline_at"] is None
        assert started["configured_duration_limit_minutes"] is None
        assert started["duration_limit_minutes"] is None
        assert research_sessions._call_timeout_seconds(started) == research_sessions.CALL_TIMEOUT
        finished = await wait_for(path, started["id"])

    assert finished["status"] == "ended", finished.get("message")
    assert finished["deadline_at"] is None
    assert finished["calls_used"] == 2
    assert len(finished["artifacts"]) == 1
    research_sessions.save_limits(str(path), {**limits, "session_duration_minutes": 5})
    # New project settings never rewrite a completed session's frozen limits.
    saved = research_sessions._read(str(path), started["id"])
    assert saved["deadline_at"] is None
    assert saved["duration_limit_minutes"] is None
    try:
        research_sessions._save(str(path), {**saved, "backend_build_commit": "f" * 40})
    except ProjectError:
        pass
    else:
        raise AssertionError("A saved directory session accepted a different source commit")


async def test_portfolio_retry_wrapper_has_a_hard_attempt_bound():
    results = iter(["retry", "retry", "retry"])
    with (
        patch.object(
            research_sessions,
            "_portfolio_role_call",
            new=AsyncMock(side_effect=lambda *args, **kwargs: next(results)),
        ) as role_call,
        patch.object(
            research_sessions,
            "_read",
            return_value={"strategy_runs": [{"strategy_id": "strategy", "status": "queued"}]},
        ),
        patch.object(research_sessions, "_save"),
        patch.object(research_sessions, "_event"),
        patch.object(research_sessions, "_call_timeout_seconds", return_value=60),
    ):
        result = await research_sessions._portfolio_role_call_with_recovery(
            str(uuid4()),
            "/unused",
            "strategy",
            "investigator",
            1,
            asyncio.Semaphore(1),
            asyncio.Lock(),
        )
    assert result is False
    assert role_call.await_count == 3


async def test_transient_timeout_retries_as_a_new_accounted_turn(path: Path):
    view, strategy, credential, config = await setup(path)
    research_sessions.save_limits(
        str(path), {**research_sessions.DEFAULT_LIMITS, "research_rounds": 1, "model_calls": 4}
    )
    attempts = []

    async def handler(request):
        payload = json.loads(request.content)
        role = payload["text"]["format"]["name"]
        attempts.append(role)
        if len(attempts) == 1:
            raise httpx.ReadTimeout("transient fixture timeout")
        value = (
            investigation(1)
            if role == "research_investigator"
            else skeptic(1, "stop", "no_progress")
        )
        return httpx.Response(200, json=provider_response(value))

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

    assert attempts == ["research_investigator"] * 2 + ["research_skeptic"]
    assert finished["calls_used"] == 3
    assert [step["status"] for step in finished["steps"]] == ["failed", "completed", "completed"]
    assert finished["steps"][0]["failure_kind"] == "timeout"
    assert len(finished["artifacts"]) == 1
    assert finished["termination_reason_code"] == "round_limit_reached"
    assert "configured round limit" in finished["message"]
    assert "incomplete" in finished["message"]
    assert finished["strategy_runs"][0]["status"] == "ended"
    assert finished["strategy_runs"][0]["last_decision"] == "stop_budget_exhausted"
    assert "1 finding was preserved" in finished["message"]


async def test_repeated_transient_failures_are_isolated_and_explained(path: Path):
    view, strategy, credential, config = await setup(path)
    limits = research_sessions.get_limits(str(path))
    limits.update({"research_rounds": 2, "model_calls": 6})
    research_sessions.save_limits(str(path), limits)
    attempts = 0

    async def handler(_request):
        nonlocal attempts
        attempts += 1
        return httpx.Response(503, json={"error": {"code": "temporary_unavailable"}})

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

    branch = finished["strategy_runs"][0]
    assert finished["status"] == "failed"
    assert finished["calls_used"] == attempts == 2
    assert [step["status"] for step in finished["steps"]] == ["failed", "failed"]
    assert all(step["failure_kind"] == "provider_temporary" for step in finished["steps"])
    assert branch["status"] == "failed"
    assert branch["recovery_attempts_exhausted"] is True
    assert finished["termination_reason_code"] == "provider_or_strategy_failure"
    assert "temporary error after one automatic retry" in finished["message"]
    assert "incomplete" in finished["message"]
    assert finished["artifacts"] == []


async def test_last_affordable_provider_failure_names_failure_and_exhaustion(path: Path):
    view, strategy, credential, config = await setup(path)
    limits = research_sessions.get_limits(str(path))
    limits.update({"research_rounds": 2, "model_calls": 2})
    research_sessions.save_limits(str(path), limits)

    async def handler(request):
        payload = json.loads(request.content)
        if payload["text"]["format"]["name"] == "research_skeptic":
            raise httpx.ReadTimeout("final skeptic turn timed out")
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
        finished = await wait_for(path, started["id"])

    branch = finished["strategy_runs"][0]
    assert finished["status"] == "failed"
    assert finished["calls_used"] == 2
    assert [step["status"] for step in finished["steps"]] == ["completed", "failed"]
    assert finished["steps"][-1]["failure_kind"] == "timeout"
    assert branch["status"] == "failed"
    assert branch["termination_reason_code"] == "timeout"
    assert finished["termination_reason_code"] == "provider_or_strategy_failure"
    assert "provider response timed out" in finished["message"]
    assert "final available turn" in finished["message"]
    assert "no further agent turn remained for recovery" in finished["message"]
    assert finished["artifacts"] == []


async def test_last_shared_turn_failure_survives_terminal_sibling_finalization(path: Path):
    view, first, credential, config = await setup(path)
    second = create_strategy(path, "Second route", "Check another derivation.").project.strategies[
        -1
    ]
    limits = research_sessions.get_limits(str(path))
    limits.update({"research_rounds": 3, "model_calls": 6})
    limits = research_sessions.save_limits(str(path), limits)
    calls = []

    async def handler(request):
        payload = json.loads(request.content)
        context = json.loads(payload["input"])
        strategy_id = context["strategy"]["id"]
        cycle = context["cycle"]
        role = payload["text"]["format"]["name"]
        calls.append((strategy_id, role, cycle))
        if strategy_id == first.id and role == "research_skeptic":
            terminal_review = skeptic(1, "stop", "no_progress")
            terminal_review["remaining_obligations"] = []
            terminal_review["next_question"] = ""
            terminal_review["objections"] = []
            terminal_review["unresolved_objections"] = []
            return httpx.Response(200, json=provider_response(terminal_review))
        if strategy_id == first.id:
            result = investigation(cycle)
            result["open_obligations"] = []
            return httpx.Response(200, json=provider_response(result))
        if strategy_id == second.id and role == "research_skeptic" and cycle == 2:
            raise httpx.ReadTimeout("final shared turn timed out")
        if strategy_id == second.id and role == "research_skeptic":
            return httpx.Response(200, json=provider_response(skeptic(1)))
        return httpx.Response(200, json=provider_response(investigation(cycle)))

    with (
        patch.object(research_sessions, "auth_context", new=AsyncMock(return_value=credential)),
        patch.object(research_sessions, "configuration", new=AsyncMock(return_value=config)),
        patch.object(research_sessions, "_portfolio_call_concurrency", return_value=1),
        patch(
            "sigma.research_sessions.httpx.AsyncClient",
            side_effect=lambda **kwargs: REAL_CLIENT(
                transport=httpx.MockTransport(handler), **kwargs
            ),
        ),
    ):
        started = await research_sessions.start_session(
            str(path),
            first.id,
            str(uuid4()),
            view.project.id,
            credential["identity"],
            expected_limits=limits,
            strategy_ids=[first.id, second.id],
        )
        finished = await wait_for(path, started["id"])

    branches = {branch["strategy_id"]: branch for branch in finished["strategy_runs"]}
    assert finished["status"] == "ended"
    assert finished["calls_used"] == len(calls) == 6, (
        finished["calls_used"],
        calls,
        finished["message"],
        branches,
    )
    assert calls[-1] == (second.id, "research_skeptic", 2), (calls, finished["message"], branches)
    assert branches[first.id]["status"] == "ended"
    assert branches[first.id]["artifacts"]
    assert branches[second.id]["status"] == "failed"
    assert branches[second.id]["termination_reason_code"] == "timeout"
    assert [step["status"] for step in finished["steps"]].count("failed") == 1
    assert finished["steps"][-1]["failure_kind"] == "timeout"
    assert finished["termination_reason_code"] == "provider_or_strategy_failure"
    assert len(finished["artifacts"]) == 2
    assert "Second route: provider response timed out" in finished["message"]
    assert "final available turn" in finished["message"]
    assert "no further agent turn remained for recovery" in finished["message"]
    assert "2 findings were preserved" in finished["message"]
    assert "incomplete" in finished["message"]
    assert "Completed" not in finished["message"]
    assert finished["events"][-1]["kind"] == "portfolio.terminated"


async def test_expired_deadline_preserves_sibling_partial_artifacts(path: Path):
    view, first, credential, config = await setup(path)
    second = create_strategy(
        path, "Second route", "Check a distinct derivation."
    ).project.strategies[-1]
    limits = research_sessions.get_limits(str(path))
    limits.update({"research_rounds": 2, "model_calls": 3})
    limits = research_sessions.save_limits(str(path), limits)
    started_event = asyncio.Event()
    holder: dict[str, str] = {}
    calls = []

    async def handler(request):
        await started_event.wait()
        payload = json.loads(request.content)
        context = json.loads(payload["input"])
        role = payload["text"]["format"]["name"]
        calls.append((context["strategy"]["id"], role))
        if role == "research_skeptic":
            record = research_sessions._read(str(path), holder["id"])
            record["configured_duration_limit_minutes"] = 60
            record["duration_limit_minutes"] = 60
            record["deadline_at"] = (datetime.now(UTC) - timedelta(seconds=1)).isoformat()
            research_sessions._save(str(path), record)
            output = skeptic(1, "stop", "no_progress")
        else:
            output = investigation(1)
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
            str(path),
            first.id,
            str(uuid4()),
            view.project.id,
            credential["identity"],
            expected_limits=limits,
            strategy_ids=[first.id, second.id],
        )
        holder["id"] = started["id"]
        started_event.set()
        finished = await wait_for(path, started["id"])

    branches = {branch["strategy_id"]: branch for branch in finished["strategy_runs"]}
    assert finished["status"] == "ended"
    assert finished["calls_used"] == len(calls) == 2, (
        finished["calls_used"],
        calls,
        finished["message"],
        finished["strategy_runs"],
    )
    assert len(finished["artifacts"]) == 1
    saved_strategy_id = finished["artifacts"][0]["strategy_id"]
    assert branches[saved_strategy_id]["artifacts"]
    assert branches[saved_strategy_id]["status"] == "ended"
    assert branches[second.id if saved_strategy_id == first.id else first.id]["status"] == "ended"
    assert finished["termination_reason_code"] == "time_limit_reached"
    assert "effective time ceiling of 60 minutes" in finished["message"]
    assert "1 finding was preserved" in finished["message"]
    assert "incomplete" in finished["message"]


def test_rate_limit_retry_observes_provider_retry_after_and_minimum_backoff():
    assert (
        research_sessions._portfolio_retry_delay({"failure_kind": "provider_rate_limited"}, 0) == 5
    )
    assert (
        research_sessions._portfolio_retry_delay(
            {"failure_kind": "provider_rate_limited", "retry_after_seconds": 17}, 0
        )
        == 17
    )
    assert (
        research_sessions._portfolio_retry_delay({"failure_kind": "provider_temporary"}, 0) == 0.25
    )
    from sigma.plan_stream import failure

    with patch("sigma.plan_stream.inference_failure"):
        try:
            failure(
                429,
                {"error": {"code": "rate_limit_exceeded"}},
                "chatgpt",
                retry_after="17",
            )
        except research_sessions.ChatGPTProviderRejection as exc:
            assert exc.retry_after_seconds == 17
        else:
            raise AssertionError("Expected a classified temporary provider rate limit")


def test_backend_build_is_pinned_at_backend_start() -> None:
    from sigma.build_info import build_commit
    from sigma.server import _build_sha

    build_commit.cache_clear()
    try:
        with patch.dict("os.environ", {"SIGMA_BUILD_COMMIT": "A" * 40}):
            assert build_commit() == "a" * 40
            assert _build_sha() == "a" * 7
        # A changed environment/checkout must not relabel an already running
        # backend's session and call evidence.
        with patch.dict("os.environ", {"SIGMA_BUILD_COMMIT": "B" * 40}):
            assert build_commit() == "a" * 40
    finally:
        build_commit.cache_clear()


def provider_response(value):
    value = dict(value)
    if "claim" in value:
        value.setdefault("human_guidance_reviews", [])
        value.setdefault("claim_is_conditional", False)
        value.setdefault(
            "reasoning_steps",
            [
                {
                    "title": "Current bounded result",
                    "argument": "A saved research step states the local claim and the evidence used to support it.",
                    "epistemic_status": "deduction",
                    "basis_artifact_ids": [],
                }
            ],
        )
    if "assessment" in value:
        value.setdefault("human_guidance_reviews", [])
        value.setdefault("claim_is_conditional", False)
        value.setdefault("obligation_reviews", [])
        value.setdefault(
            "reasoning_assessments",
            [
                {
                    "step_number": 1,
                    "disposition": "accepted",
                    "rationale": "The cited local argument follows from its stated evidence and assumptions.",
                    "objection": "",
                    "basis_artifact_ids": [],
                }
            ],
        )
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
        "reasoning_steps": [
            {
                "title": f"Cycle {n} bounded consequence",
                "argument": f"The cycle {n} strategy yields its stated local consequence under the recorded assumption.",
                "epistemic_status": "deduction",
                "basis_artifact_ids": [],
            }
        ],
        "claim_is_conditional": False,
        "assumptions": [f"Assumption {n}"],
        "evidence_status": "Unverified model derivation; no tool was run.",
        "open_obligations": [f"Obligation {n}"],
        "python_code": None,
        "sage_code": None,
        "prior_session_failure_attempt_ids": [],
        "human_guidance_reviews": [],
        "computational_citations": [],
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
        "reasoning_assessments": [
            {
                "step_number": 1,
                "disposition": "accepted",
                "rationale": "The stated local consequence follows from its supplied premise for this cycle.",
                "objection": "",
                "basis_artifact_ids": [],
            }
        ],
        "claim_is_conditional": False,
        "assumptions_reviewed": [f"Assumption {n}"],
        "proof_obligations": [f"Check obligation {n}"],
        "unresolved_objections": [],
        "supporting_cycles": list(range(1, n + 1)),
        "verification_status": "convincing_unverified",
        "strategy_contribution": "productive",
        "contribution_rationale": "The saved derivation advances the objective through the linked strategy.",
        "cross_strategy_relations": [],
        "retracted_cross_strategy_source_artifact_ids": [],
        "peer_handoff_reviews": [],
        "human_guidance_reviews": [],
        "obligation_reviews": [],
        "computational_citations": [],
    }


def bare_execution(execution):
    return {key: value for key, value in execution.items() if key != "artifact_inspections"}


def execution_tool_fixture(python_available: bool):
    return [
        {
            "name": "Scientific Python",
            "available": python_available,
            "request_field": "python_code",
            "result_field": "python_execution",
        },
        {
            "name": "SageMath",
            "available": False,
            "request_field": "sage_code",
            "result_field": "sage_execution",
        },
    ]


async def wait_for(path, session_id, terminal=True):
    for _ in range(300):
        current = research_sessions.get_session(str(path), session_id)
        worker = research_sessions._tasks.get(session_id)
        settled = worker is None or worker.done()
        if (
            (current["status"] in {"completed", "ended", "failed", "stopped", "paused"} and settled)
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


def test_request_audit_truncation_tokens_and_reconciliation():
    context = {"problem": "Answer-free objective", "strategy": "Incremental reasoning"}
    record = {
        "mode": "chatgpt",
        "model": MODEL,
        "reasoning_effort": "high",
        "output_token_limit": 4000,
    }
    body = research_sessions._role_request_payload(record, "investigator", context)
    audit = research_sessions._role_input_audit(record, "investigator", context, "fixture-token")
    assert audit["kind"] == "exact_provider_request_body"
    research_sessions._expand_role_input_audit(audit)
    assert audit["request_body"] == body and audit["headers_included"] is False
    submitted = body["input"][0]["content"]
    assert submitted == json.dumps(context, ensure_ascii=False)
    assert "fixture-token" not in json.dumps(audit)
    concurrent_contexts = [
        {"problem": "Shared objective", "strategy": "Concurrent route A"},
        {"problem": "Shared objective", "strategy": "Concurrent route B"},
    ]
    concurrent_payloads = [
        research_sessions._role_request_payload(record, "investigator", item)
        for item in concurrent_contexts
    ]
    concurrent_steps = [
        {
            "id": f"same-role-step-{index}",
            "role": "investigator",
            "status": "running",
            "provider_input_audit": research_sessions._role_input_audit(
                record, "investigator", item, "fixture-token"
            ),
        }
        for index, item in enumerate(concurrent_contexts)
    ]
    concurrent_record = {"steps": concurrent_steps}
    research_sessions._assert_saved_role_input_matches(
        concurrent_record, "investigator", concurrent_payloads[0], "same-role-step-0"
    )
    try:
        research_sessions._assert_saved_role_input_matches(
            concurrent_record, "investigator", concurrent_payloads[1], "same-role-step-0"
        )
    except ProjectError as exc:
        assert "did not match" in str(exc)
    else:
        raise AssertionError("A same-role request must not validate against another step's audit")
    try:
        research_sessions._assert_saved_role_input_matches(
            concurrent_record, "investigator", concurrent_payloads[0], None
        )
    except ProjectError as exc:
        assert "audit is missing" in str(exc)
    else:
        raise AssertionError("Calls with recorded steps must provide their exact step ID")
    try:
        research_sessions._role_input_audit(
            record,
            "investigator",
            {"problem": "refresh_token=synthetic-secret-value"},
            "fixture-token",
        )
    except ProjectError as exc:
        assert "credential-like" in str(exc)
        assert "synthetic-secret-value" not in str(exc)
    else:
        raise AssertionError(
            "Credential-like prompt data must be rejected before audit persistence"
        )

    investigator_output = {"method": "m" * 6000}
    skeptic_output = {"response": "r" * 6000}
    assert research_sessions._potential_truncation_fields("investigator", investigator_output) == [
        "method"
    ]
    assert research_sessions._potential_truncation_fields("skeptic", skeptic_output) == ["response"]
    assert (
        research_sessions._research_schema(research_sessions.Investigator)["properties"]["method"][
            "maxLength"
        ]
        == 6000
    )
    assert (
        research_sessions._research_schema(research_sessions.Skeptic)["properties"]["response"][
            "maxLength"
        ]
        == 6000
    )
    safe_execution = research_sessions._execution_with_inspections(
        {
            "id": "execution-fixture",
            "status": "completed",
            "stdout": "30",
            "artifacts": [],
            "private_config": {"token": "synthetic-confidential-value"},
        },
        "unused-fixture-path",
    )
    assert "private_config" not in safe_execution
    assert "synthetic-confidential-value" not in json.dumps(safe_execution)

    accounting = {
        "steps": [{"status": "completed", "token_usage": {"input_tokens": 3, "output_tokens": 2}}],
        "status": "ended",
    }
    research_sessions._refresh_token_accounting(accounting)
    assert accounting["tokens_used"] == 5 and accounting["token_usage_status"] == "complete"
    accounting["steps"].append({"status": "completed", "token_usage_status": "unavailable"})
    research_sessions._refresh_token_accounting(accounting)
    assert accounting["tokens_used"] == 5 and accounting["token_usage_status"] == "partial"
    unavailable = {"steps": [{"status": "completed"}], "status": "ended"}
    research_sessions._refresh_token_accounting(unavailable)
    assert unavailable["tokens_used"] is None and unavailable["token_usage_status"] == "unavailable"

    archived = json.loads(
        Path(
            "docs/evaluations/fixtures/t17-8-answer-free/live-session-91e96112-27ce-412e-841f-5cbf67cbba75.json"
        ).read_text()
    )["research_sessions"][0]
    archived_public = research_sessions._public(archived)
    assert archived_public["tokens_used"] == 38591
    assert archived_public["token_usage_status"] == "complete"
    paused_fixture = deepcopy(archived)
    paused_fixture["status"] = "paused"
    paused_fixture["message"] = (
        "Backend restarted before the session completed. At least one dispatched provider call has unknown completion or billing status and will not be retried automatically."
    )
    paused_fixture["steps"] = [{"status": "interrupted", "interruption_reason": "backend_restart"}]
    pause_public = research_sessions._public(paused_fixture)
    assert "check provider usage or billing first" in pause_public["next_step_guidance"]
    assert "does not replay that attempt" in pause_public["next_step_guidance"]
    paused_fixture["message"] = (
        "Backend restarted before the session completed. No provider request was recorded in flight."
    )
    paused_fixture["steps"] = []
    assert (
        "No provider request was recorded in flight"
        in research_sessions._public(paused_fixture)["next_step_guidance"]
    )
    paused_fixture["message"] = (
        "Paused by user. A dispatched provider request may still consume allowance."
    )
    paused_fixture["steps"] = []
    assert (
        "Resume when you are ready"
        in research_sessions._public(paused_fixture)["next_step_guidance"]
    )
    paused_fixture["status"] = "failed"
    paused_fixture["message"] = "Provider returned an ambiguous failure after dispatch."
    failed_guidance = research_sessions._public(paused_fixture)["next_step_guidance"]
    assert "confirm provider usage or billing" in failed_guidance
    assert "start a new session" in failed_guidance
    assert "another attempt is free or safe" in failed_guidance
    paused_fixture["message"] = (
        "The conservative estimated cost reserve for another call exceeds the session limit; no additional call was made."
    )
    paused_fixture["status"] = "paused"
    assert "only if you approve" in research_sessions._public(paused_fixture)["next_step_guidance"]
    paused_fixture["status"] = "ended"
    paused_fixture["message"] = (
        "Configured model-call limit reached. Findings are unverified research notes."
    )
    assert "start a new session" in research_sessions._public(paused_fixture)["next_step_guidance"]
    paused_fixture["status"] = "paused"
    for message, expected in (
        (
            "Project or strategy changed; session paused before a new call.",
            "enable the session's saved strategies",
        ),
        (
            "AI account or billing identity changed; session paused before a new call.",
            "Restore the intended AI account",
        ),
        (
            "Selected model is no longer available; session paused before a new call.",
            "Check the selected model",
        ),
        (
            "Configured session duration reached while waiting for provider access. No new call was made.",
            "start a new session",
        ),
        (
            "Research storage limit reached. Existing artifacts were retained.",
            "Resolve that limit before resuming",
        ),
    ):
        paused_fixture["message"] = message
        assert expected in research_sessions._public(paused_fixture)["next_step_guidance"]
    source_artifacts = json.loads(json.dumps(archived["artifacts"]))
    archived["artifacts"] = []
    for artifact in source_artifacts:
        archived["artifacts"].append(artifact)
        if isinstance(artifact.get("skeptic_output"), dict):
            research_sessions._reconcile_skeptic_obligations(
                archived,
                artifact["investigator_output"],
                artifact["skeptic_output"],
                artifact["strategy_id"],
                artifact["sequence"],
            )
        research_sessions._reconcile_artifact_open_obligations(archived, artifact)
    assert archived["artifacts"][0]["open_obligations"]
    assert (
        archived["artifacts"][1]["open_obligations"]
        == archived["artifacts"][1]["skeptic_output"]["remaining_obligations"]
    )
    assert archived["artifacts"][1]["skeptic_output"]["model_remaining_obligations"] == []
    assert archived["artifacts"][1]["skeptic_output"]["coordinator_global_closure"]["accepted"]
    assert archived["artifacts"][1]["skeptic_output"]["coordinator_closed_obligations"]

    strategy_id = "strategy-fixture"
    artifact_id = "artifact-fixture"
    decision = research_sessions._portfolio_decision(
        {
            "artifacts": [
                {
                    "id": artifact_id,
                    "strategy_id": strategy_id,
                    "strategy_review": {
                        "assessment": "solution",
                        "basis_artifact_ids": [artifact_id],
                    },
                }
            ],
            "strategy_runs": [
                {
                    "strategy_id": strategy_id,
                    "strategy_title": "Completed",
                    "status": "ended",
                    "last_decision": "stop_productive_conclusion",
                    "artifacts": [artifact_id],
                }
            ],
        }
    )
    assert [item["strategy_title"] for item in decision["completed_strategies"]] == ["Completed"]
    assert decision["stopped_strategies"] == []


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


def test_project_concurrency_max_four_and_legacy_read(root: Path) -> None:
    view = initialize_project(
        root / "project-concurrency-bounds.sigma", "Bounded project", "Check project limits"
    )
    path = view.path
    original = dict(research_sessions.DEFAULT_LIMITS)
    assert research_sessions.get_limits(path)["max_concurrent_sessions"] == 1
    saved = research_sessions.save_limits(path, {**original, "max_concurrent_sessions": 4})
    assert saved["max_concurrent_sessions"] == 4

    for invalid in (0, 5, "5", -1, "not-a-number"):
        try:
            research_sessions.save_limits(path, {**original, "max_concurrent_sessions": invalid})
        except ProjectError as exc:
            assert "between 1 and 4" in str(exc)
        else:
            raise AssertionError(f"Project limit {invalid!r} exceeded 1–4 cap")

    # Old projects saved without bounds remain readable and can be brought
    # into compliance without rewriting their project bundle on mere inspection.
    legacy = {
        **original,
        "research_rounds": 5,
        "model_calls": 120,
        "max_concurrent_sessions": 17,
    }
    saved_path = Path(path) / "research-sessions" / "limits.json"
    saved_path.write_text(json.dumps(legacy), encoding="utf-8")
    assert research_sessions.get_limits(path)["max_concurrent_sessions"] == 4
    assert json.loads(saved_path.read_text())["max_concurrent_sessions"] == 17
    research_sessions.save_limits(path, research_sessions.get_limits(path))
    assert json.loads(saved_path.read_text())["max_concurrent_sessions"] == 4


async def test_start_preflight_does_not_hold_project_or_global_admission_locks(path: Path):
    """A slow credential check must not hold a blocking flock across await."""
    view, strategy, credential, config = await setup(path)
    entered = asyncio.Event()
    release = asyncio.Event()

    async def slow_auth():
        entered.set()
        await release.wait()
        return credential

    async def dormant_worker(_session_id: str, _path: str):
        return None

    with (
        patch.object(research_sessions, "auth_context", new=slow_auth),
        patch.object(research_sessions, "configuration", new=AsyncMock(return_value=config)),
        patch.object(research_sessions, "_worker", new=dormant_worker),
    ):
        task = asyncio.create_task(
            research_sessions.start_session(
                str(path), strategy.id, str(uuid4()), view.project.id, credential["identity"]
            )
        )
        try:
            await asyncio.wait_for(entered.wait(), timeout=2)

            # A concurrent request must still be able to acquire both admission
            # locks while the external account check is pending.
            async def acquire_both():
                async with research_sessions._manager_lock:
                    with research_sessions._project_manager_lock(str(path)):
                        return True

            assert await asyncio.wait_for(acquire_both(), timeout=2)
        finally:
            release.set()
        result = await asyncio.wait_for(task, timeout=2)
        await research_sessions._tasks[result["id"]]


async def test_start_revalidates_project_after_slow_preflight(path: Path):
    view, strategy, credential, config = await setup(path)
    entered = asyncio.Event()
    release = asyncio.Event()

    async def slow_auth():
        entered.set()
        await release.wait()
        return credential

    with (
        patch.object(research_sessions, "auth_context", new=slow_auth),
        patch.object(research_sessions, "configuration", new=AsyncMock(return_value=config)),
    ):
        task = asyncio.create_task(
            research_sessions.start_session(
                str(path), strategy.id, str(uuid4()), view.project.id, credential["identity"]
            )
        )
        try:
            await asyncio.wait_for(entered.wait(), timeout=2)
            edit_strategy(
                str(path), strategy.id, "Revised approach", "Revise the recurrence hypothesis."
            )
        finally:
            release.set()
        try:
            await asyncio.wait_for(task, timeout=2)
        except ProjectError as exc:
            assert "changed during research preflight" in str(exc)
        else:
            raise AssertionError("Stale strategy snapshots must not dispatch research")
    assert research_sessions.list_sessions(str(path)) == []


async def test_project_concurrent_session_limit_is_atomic(path: Path):
    view, strategy, credential, config = await setup(path)
    limits = {**research_sessions.DEFAULT_LIMITS, "max_concurrent_sessions": 2}
    research_sessions.save_limits(str(path), limits)
    release = asyncio.Event()

    async def parked_worker(_session_id: str, _path: str) -> None:
        await release.wait()

    with (
        patch.object(research_sessions, "auth_context", new=AsyncMock(return_value=credential)),
        patch.object(research_sessions, "configuration", new=AsyncMock(return_value=config)),
        patch.object(research_sessions, "_worker", new=parked_worker),
    ):
        attempts = await asyncio.gather(
            *(
                research_sessions.start_session(
                    str(path),
                    strategy.id,
                    str(uuid4()),
                    view.project.id,
                    credential["identity"],
                    limits,
                )
                for _ in range(3)
            ),
            return_exceptions=True,
        )
        started = [item for item in attempts if isinstance(item, dict)]
        rejected = [item for item in attempts if isinstance(item, ProjectError)]
        assert len(started) == 2 and len(rejected) == 1
        assert "maximum concurrent sessions" in str(rejected[0]).lower()
        stopped = await research_sessions.control_session(str(path), started[0]["id"], "stop")
        assert stopped["status"] == "stopped"
        after_release = await research_sessions.start_session(
            str(path), strategy.id, str(uuid4()), view.project.id, credential["identity"], limits
        )
        workers = [research_sessions._tasks[item["id"]] for item in [*started, after_release]]
        release.set()
        await asyncio.gather(*workers, return_exceptions=True)
        for item in started:
            research_sessions._tasks.pop(item["id"], None)


async def test_distinct_portfolio_sessions_dispatch_simultaneously(root: Path):
    """Different projects and two sessions in one project must overlap provider I/O."""
    for same_project in (False, True):
        scenario = "same-project" if same_project else "distinct-projects"
        left = root / f"{scenario}-a.sigma"
        right = left if same_project else root / f"{scenario}-b.sigma"
        first_view, first_strategy, credential, config = await setup(left)
        if same_project:
            second_view, second_strategy = first_view, first_strategy
        else:
            second_view, second_strategy, _, _ = await setup(right)

        limits = {
            **research_sessions.DEFAULT_LIMITS,
            "research_rounds": 1,
            "model_calls": 2,
            "max_concurrent_sessions": 2 if same_project else 1,
        }
        research_sessions.save_limits(str(left), limits)
        if not same_project:
            research_sessions.save_limits(str(right), limits)
        running: set[str] = set()
        both_running = asyncio.Event()

        async def provider(
            record,
            role,
            context,
            timeout_seconds=None,
            step_id=None,
            running=running,
            both_running=both_running,
        ):
            del context, timeout_seconds
            assert isinstance(step_id, str)
            if role == "investigator":
                running.add(record["id"])
                if len(running) == 2:
                    both_running.set()
                # Serializing all portfolios would deadlock or time out here.
                await asyncio.wait_for(both_running.wait(), timeout=3)
                return investigation(1), {"input_tokens": 120, "output_tokens": 90}
            return skeptic(1, "stop"), {"input_tokens": 120, "output_tokens": 90}

        with (
            patch.object(research_sessions, "auth_context", new=AsyncMock(return_value=credential)),
            patch.object(research_sessions, "configuration", new=AsyncMock(return_value=config)),
            patch.object(research_sessions, "_call", new=AsyncMock(side_effect=provider)),
            patch.object(research_sessions, "execution_capabilities", return_value=[]),
        ):
            first, second = await asyncio.gather(
                research_sessions.start_session(
                    str(left),
                    first_strategy.id,
                    str(uuid4()),
                    first_view.project.id,
                    credential["identity"],
                ),
                research_sessions.start_session(
                    str(right),
                    second_strategy.id,
                    str(uuid4()),
                    second_view.project.id,
                    credential["identity"],
                ),
            )
            assert first["id"] != second["id"]
            finished = await asyncio.wait_for(
                asyncio.gather(
                    wait_for(left, first["id"]),
                    wait_for(right, second["id"]),
                ),
                timeout=8,
            )

        assert len(running) == 2
        assert all(item["status"] == "ended" for item in finished)
        assert all(item["calls_used"] == 2 and len(item["artifacts"]) == 1 for item in finished)
        assert all(item["tokens_reserved"] == 0 for item in finished)


async def test_stop_one_session_does_not_cancel_sibling_and_resume_keeps_work(path: Path):
    """Stop/Resume must act on the selected session, not another active session."""
    view, strategy, credential, config = await setup(path)
    limits = {
        **research_sessions.DEFAULT_LIMITS,
        "research_rounds": 1,
        "model_calls": 4,
        "max_concurrent_sessions": 2,
    }
    research_sessions.save_limits(str(path), limits)
    first_entered = asyncio.Event()
    second_entered = asyncio.Event()
    resumed_entered = asyncio.Event()
    release_second = asyncio.Event()
    first_id = ""
    second_id = ""
    attempts: dict[str, int] = {}

    async def provider(record, role, _context, timeout_seconds=None, step_id=None):
        del timeout_seconds
        assert isinstance(step_id, str)
        session_id = record["id"]
        if role == "investigator":
            attempts[session_id] = attempts.get(session_id, 0) + 1
            if session_id == first_id and attempts[session_id] == 1:
                first_entered.set()
                await asyncio.Event().wait()
                raise AssertionError("Stopped provider must never complete")
            if session_id == second_id:
                second_entered.set()
                await release_second.wait()
            if session_id == first_id and attempts[session_id] == 2:
                resumed_entered.set()
            return investigation(1), {"input_tokens": 120, "output_tokens": 90}
        return skeptic(1, "stop"), {"input_tokens": 120, "output_tokens": 90}

    with (
        patch.object(research_sessions, "auth_context", new=AsyncMock(return_value=credential)),
        patch.object(research_sessions, "configuration", new=AsyncMock(return_value=config)),
        patch.object(research_sessions, "_call", new=AsyncMock(side_effect=provider)),
        patch.object(research_sessions, "execution_capabilities", return_value=[]),
    ):
        first = await research_sessions.start_session(
            str(path), strategy.id, str(uuid4()), view.project.id, credential["identity"]
        )
        first_id = first["id"]
        await asyncio.wait_for(first_entered.wait(), 3)
        second = await research_sessions.start_session(
            str(path), strategy.id, str(uuid4()), view.project.id, credential["identity"]
        )
        second_id = second["id"]
        await asyncio.wait_for(second_entered.wait(), 3)
        assert not research_sessions._tasks[second_id].done()

        stopped = await research_sessions.control_session(str(path), first_id, "stop")
        assert stopped["status"] == "stopped"
        assert not research_sessions._tasks[second_id].done()
        assert research_sessions.get_session(str(path), second_id)["status"] in {
            "queued",
            "running",
        }
        assert attempts[second_id] == 1

        resumed = await research_sessions.control_session(str(path), first_id, "resume")
        assert resumed["status"] == "queued"
        await asyncio.wait_for(resumed_entered.wait(), 3)
        assert not research_sessions._tasks[second_id].done()
        release_second.set()
        first_result, second_result = await asyncio.wait_for(
            asyncio.gather(wait_for(path, first_id), wait_for(path, second_id)), 8
        )
        assert first_result["status"] == second_result["status"] == "ended"
        assert first_result["id"] == first_id and second_result["id"] == second_id
        assert len(first_result["artifacts"]) == len(second_result["artifacts"]) == 1
        assert attempts[first_id] == 2 and attempts[second_id] == 1
        assert first_result["tokens_reserved"] == second_result["tokens_reserved"] == 0


async def test_foreign_worker_lock_blocks_resume_and_removal(path: Path):
    """Another process's live execution must not be resumed or deleted."""
    view, strategy, credential, config = await setup(path)
    entered = asyncio.Event()

    async def provider(_record, _role, _context, timeout_seconds=None, step_id=None):
        del timeout_seconds, step_id
        entered.set()
        await asyncio.Event().wait()
        raise AssertionError("Cancelled provider continued")

    with (
        patch.object(research_sessions, "auth_context", new=AsyncMock(return_value=credential)),
        patch.object(research_sessions, "configuration", new=AsyncMock(return_value=config)),
        patch.object(research_sessions, "_call", new=AsyncMock(side_effect=provider)),
        patch.object(research_sessions, "execution_capabilities", return_value=[]),
    ):
        started = await research_sessions.start_session(
            str(path), strategy.id, str(uuid4()), view.project.id, credential["identity"]
        )
        await asyncio.wait_for(entered.wait(), 3)
        stopped = await research_sessions.control_session(str(path), started["id"], "stop")
        assert stopped["status"] == "stopped"

        lock_path = research_sessions._worker_lock_path(str(path), started["id"])
        lock_owner = await asyncio.create_subprocess_exec(
            sys.executable,
            "-c",
            "import fcntl, os, sys; "
            "fd=os.open(sys.argv[1], os.O_CREAT|os.O_RDWR, 0o600); "
            "fcntl.flock(fd, fcntl.LOCK_EX); "
            "print('locked', flush=True); "
            "sys.stdin.buffer.read(1); os.close(fd)",
            str(lock_path),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        assert lock_owner.stdout is not None and lock_owner.stdin is not None
        try:
            assert await asyncio.wait_for(lock_owner.stdout.readline(), 3) == b"locked\n"
            for operation in (
                research_sessions.control_session(str(path), started["id"], "resume"),
                research_sessions.remove_session(str(path), started["id"], stopped["updated_at"]),
            ):
                try:
                    await operation
                except ProjectError as exc:
                    assert "releasing resources" in str(exc)
                else:
                    raise AssertionError("Live foreign worker ownership was ignored")
            assert research_sessions.get_session(str(path), started["id"])["status"] == "stopped"
            # Deleting the entire project must also reject a live foreign worker.
            from sigma.api import DeleteProjectRequest, delete_project_view

            with patch.dict("os.environ", {"SIGMA_PROJECTS_ROOT": str(path.parent)}):
                try:
                    await delete_project_view(
                        DeleteProjectRequest(path=str(path), expected_project_id=view.project.id)
                    )
                except ProjectError as exc:
                    assert "releasing resources" in str(exc), str(exc)
                else:
                    raise AssertionError("Project deletion ignored a foreign worker")
            assert path.exists()
        finally:
            lock_owner.stdin.write(b"x")
            await lock_owner.stdin.drain()
            lock_owner.stdin.close()
            assert await asyncio.wait_for(lock_owner.wait(), 3) == 0

        removed = await research_sessions.remove_session(
            str(path), started["id"], stopped["updated_at"]
        )
        assert removed["removed"] is True


async def test_three_cycles_and_idempotency(path: Path):
    view, strategy, credential, config = await setup(path)
    limits = research_sessions.get_limits(str(path))
    limits.update({"research_rounds": 3, "model_calls": 6})
    research_sessions.save_limits(str(path), limits)
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
    submitted_payloads = []

    async def handler(request):
        payload = json.loads(request.content)
        assert payload["model"] == MODEL and payload["store"] is False
        assert payload["max_output_tokens"] == research_sessions.MODEL_OUTPUT_LIMITS[MODEL]
        assert payload["text"]["format"]["strict"] is True
        assert payload["text"]["format"]["name"] in {"research_investigator", "research_skeptic"}
        if payload["text"]["format"]["name"] == "research_skeptic":
            assert "stop_reason" in payload["text"]["format"]["schema"]["required"]
            assert (
                "retracted_cross_strategy_source_artifact_ids"
                in payload["text"]["format"]["schema"]["required"]
            )
        context = json.loads(payload["input"])
        contexts.append((payload["text"]["format"]["name"], context))
        submitted_payloads.append(payload)
        return httpx.Response(200, json=provider_response(outputs.pop(0)))

    with (
        patch.object(research_sessions, "auth_context", new=AsyncMock(return_value=credential)),
        patch.object(research_sessions, "configuration", new=AsyncMock(return_value=config)),
        patch.object(research_sessions, "build_commit", return_value="a" * 40),
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
        assert started["backend_build_commit"] == "a" * 40
        assert started["call_limit"] == 6
        assert started["cycle_limit"] == 3
        assert started["duration_limit_minutes"] == 60
        assert started["output_token_limit"] == 4000
        finished = await wait_for(path, started["id"])
        duplicate = await research_sessions.start_session(
            str(path), strategy.id, key, view.project.id, credential["identity"]
        )
        assert duplicate["id"] == started["id"]

    assert finished["backend_build_commit"] == "a" * 40
    assert all(step["backend_build_commit"] == "a" * 40 for step in finished["steps"])
    assert finished["status"] == "ended" and finished["calls_used"] == 6
    from sigma import session_log

    session_log.flush()
    from sigma.session_log import _frames as read_session_log_frames
    from sigma.session_log import log_path as session_log_path

    trace, _ = read_session_log_frames(session_log_path(str(path), view.project.id, finished["id"]))
    requests = {
        event["request_id"]: event for event in trace if event["type"] == "provider_request"
    }
    responses = {
        event["request_id"]: event for event in trace if event["type"] == "provider_response"
    }
    assert len(requests) == len(responses) == 6
    assert set(requests) == set(responses)
    assert [requests[key]["request"] for key in requests] == submitted_payloads
    assert all(event["response"]["status"] == "completed" for event in responses.values())
    saved_name = session_log._short_name(path, view.project.id)
    # The fixture claim does not mention the project subject, so it must not
    # produce a misleading label from generic result wording.
    assert saved_name == "Research Project"
    assert "fixture-token" not in json.dumps(trace)
    assert finished["tokens_used"] == 1200 and finished["token_usage_status"] == "complete"
    assert [
        step["provider_input_audit"]["request_body"] for step in finished["steps"]
    ] == submitted_payloads
    assert all(not step["provider_input_audit"]["headers_included"] for step in finished["steps"])
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
    assert "session_log" not in json.dumps(exported)
    assert exported_session["strategy_text"] == strategy.approach
    assert exported_session["problem"] == view.project.problem
    assert exported_session["backend_build_commit"] == "a" * 40
    assert all(step["backend_build_commit"] == "a" * 40 for step in exported_session["steps"])
    metrics = exported_session["outcome"]["metrics"]
    assert (
        next(item["value"] for item in metrics["operational"] if item["label"] == "Backend build")
        == "a" * 40
    )
    assert metrics == finished["outcome"]["metrics"]
    assert metrics["sources"]["session_id"] == finished["id"]
    assert metrics["sources"]["step_ids"] == sorted(step["id"] for step in finished["steps"])
    from sigma.project_reports import render_report

    plain_report, _ = render_report(exported, "txt")
    html_report, _ = render_report(exported, "html")
    assert isinstance(plain_report, str) and isinstance(html_report, str)
    for group in ("operational", "research_quality"):
        for item in metrics[group]:
            assert f"{item['label']}: {item['value']}" in plain_report
            assert f"<dt>{escape(item['label'])}</dt>" in html_report
            assert f"<dd>{escape(item['value'])}</dd>" in html_report
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


async def test_legacy_worker_aggregates_usage_and_audits_inputs(path: Path):
    view, strategy, credential, config = await setup(path)
    calls = [investigation(1), skeptic(1, "stop", "productive_conclusion")]
    calls[0]["method"] = "m" * 6000
    calls[1]["response"] = "r" * 6000
    calls[0]["open_obligations"] = []

    async def defer_worker(*_args):
        return None

    async def fake_call(_record, _role, _context, _timeout=None, step_id=None):
        assert isinstance(step_id, str)
        return calls.pop(0), {
            "input_tokens": 7,
            "output_tokens": 5,
            "cached_input_tokens": None,
        }

    with (
        patch.object(research_sessions, "auth_context", new=AsyncMock(return_value=credential)),
        patch.object(research_sessions, "configuration", new=AsyncMock(return_value=config)),
        patch.object(research_sessions, "_worker", new=defer_worker),
    ):
        started = await research_sessions.start_session(
            str(path), strategy.id, str(uuid4()), view.project.id, credential["identity"]
        )
    record = research_sessions._read(str(path), started["id"])
    record.pop("strategy_runs")
    record["status"] = "queued"
    research_sessions._save(str(path), record)
    with (
        patch.object(research_sessions, "auth_context", new=AsyncMock(return_value=credential)),
        patch.object(research_sessions, "configuration", new=AsyncMock(return_value=config)),
        patch.object(research_sessions, "_call", new=fake_call),
    ):
        await research_sessions._worker(started["id"], str(path))
    finished = research_sessions.get_session(str(path), started["id"])
    assert finished["status"] == "ended" and finished["calls_used"] == 2
    assert finished["tokens_used"] == 24 and finished["token_usage_status"] == "complete"
    assert len(finished["steps"]) == 2
    assert all(
        step["provider_input_audit"]["kind"] == "exact_provider_request_body"
        for step in finished["steps"]
    )
    assert finished["steps"][0]["potential_truncation_fields"] == ["method"]
    assert finished["steps"][1]["potential_truncation_fields"] == ["response"]


async def test_investigator_python_is_run_and_reviewed(path: Path):
    view, strategy, credential, config = await setup(path)
    limits = research_sessions.get_limits(str(path))
    limits["research_rounds"] = 1
    research_sessions.save_limits(str(path), limits)
    code = "print(6 * 7)"
    first = {**investigation(1), "python_code": code}
    execution = {
        "id": str(uuid4()),
        "status": "timeout",
        "exit_code": 124,
        "stdout": "",
        "stderr": "Execution exceeded the 15-second wall limit.",
        "duration_ms": 15_000,
        "source": code,
        "artifacts": [],
        "environment": {"network": "none", "memory_bytes": 536870912},
    }
    outputs = [first, skeptic(1, "stop", "no_progress")]
    contexts = []
    provider_payloads = []

    async def handler(request):
        payload = json.loads(request.content)
        provider_payloads.append(payload)
        context = json.loads(payload["input"])
        contexts.append((payload["text"]["format"]["name"], context))
        return httpx.Response(200, json=provider_response(outputs.pop(0)))

    with (
        patch.object(research_sessions, "auth_context", new=AsyncMock(return_value=credential)),
        patch.object(research_sessions, "configuration", new=AsyncMock(return_value=config)),
        patch.object(
            research_sessions,
            "execution_capabilities",
            return_value=execution_tool_fixture(True),
        ),
        patch(
            "sigma.research_sessions.httpx.AsyncClient",
            side_effect=lambda **kwargs: REAL_CLIENT(
                transport=httpx.MockTransport(handler), **kwargs
            ),
        ),
        patch.object(
            research_sessions,
            "execute_research_code",
            new=AsyncMock(return_value=execution),
        ) as sandbox,
    ):
        started = await research_sessions.start_session(
            str(path),
            strategy.id,
            str(uuid4()),
            view.project.id,
            credential["identity"],
            expected_limits=limits,
        )
        finished = await wait_for(path, started["id"])

    sandbox.assert_awaited_once()
    sandbox_call = sandbox.await_args
    assert sandbox_call is not None
    assert sandbox_call.args[1] == code
    assert sandbox_call.kwargs == {
        "session_id": started["id"],
        "strategy_id": strategy.id,
        "cycle": 1,
        "runtime_name": "python",
        "step_id": next(step["id"] for step in finished["steps"] if step["role"] == "investigator"),
    }
    assert [role for role, _ in contexts] == [
        "research_investigator",
        "research_skeptic",
    ], (contexts, finished)
    assert contexts[0][1]["execution_tools"][0]["available"] is True
    assert "Scientific Python is available" in provider_payloads[0]["instructions"]
    assert (
        "a finite computation does not prove a general claim"
        in provider_payloads[1]["instructions"]
    )
    skeptic_context = contexts[1][1]["investigator_output"]
    assert skeptic_context["python_code"] == code
    assert {
        key: value
        for key, value in skeptic_context["python_execution"].items()
        if key != "artifact_inspections"
    } == execution
    assert skeptic_context["python_execution"]["artifact_inspections"] == []
    assert skeptic_context["python_execution"]["status"] == "timeout"
    assert finished["steps"][0]["output"] == finished["artifacts"][0]["investigator_output"]
    sources = finished["outcome"]["metrics"]["sources"]
    assert sources["session_id"] == started["id"]
    assert sources["execution_ids"] == [execution["id"]]
    assert sources["artifact_ids"] == [finished["artifacts"][0]["id"]]
    assert sources["step_ids"] == sorted(step["id"] for step in finished["steps"])
    artifact = finished["artifacts"][0]
    assert artifact["session_id"] == started["id"] and artifact["strategy_id"] == strategy.id
    assert artifact["strategy_cycle"] == 1
    assert {
        key: value
        for key, value in artifact["investigator_output"]["python_execution"].items()
        if key != "artifact_inspections"
    } == execution
    assert (
        finished["artifacts"][0]["investigator_output"]["python_execution"]["id"] == execution["id"]
    )
    assert any(event["kind"] == "python.started" for event in finished["events"])
    completed_event = next(
        event for event in finished["events"] if event["kind"] == "python.completed"
    )
    assert execution["id"] in completed_event["message"]
    assert execution["status"] in completed_event["message"]
    from sigma.api import export_project_view

    exported = export_project_view(str(path))
    exported_artifact = exported["research_sessions"][0]["artifacts"][0]
    assert exported_artifact["investigator_output"]["python_code"] == code
    assert {
        key: value
        for key, value in exported_artifact["investigator_output"]["python_execution"].items()
        if key != "artifact_inspections"
    } == execution
    with patch("sigma.api.export_project_view", return_value=exported):
        paper_evidence, _ = papers._snapshot(str(path))
    paper_sources = {item["id"]: item["data"] for item in paper_evidence["sources"]}
    paper_artifact = next(
        value for key, value in paper_sources.items() if key.startswith("artifact:")
    )
    assert paper_artifact["investigator_output"]["python_code"] == code
    assert paper_artifact["investigator_output"]["python_execution"]["source"] == code
    # Cross-strategy coordination must see the failure, not only the original
    # pre-execution claim. Its preview leaves the original exact evidence intact.
    peer_branch = {
        "strategy_id": str(uuid4()),
        "strategy_title": "Peer approach",
        "strategy_text": "Review the computation independently.",
        "current_question": "Does peer evidence change the approach?",
        "pending_investigation": investigation(1),
    }
    for role in ("investigator", "skeptic"):
        peer_context = research_sessions._portfolio_context(finished, peer_branch, role, 1)
        preview = peer_context["other_strategy_evidence"][0]["python_execution"]
        assert preview["id"] == execution["id"] and preview["status"] == "timeout"
        assert preview["source"] == code and preview["stderr"] == execution["stderr"]
    assert {
        key: value
        for key, value in finished["artifacts"][0]["investigator_output"][
            "python_execution"
        ].items()
        if key != "artifact_inspections"
    } == execution
    large_preview_record = json.loads(json.dumps(finished))
    large_execution = large_preview_record["artifacts"][0]["investigator_output"][
        "python_execution"
    ]
    large_execution.update(stdout="x" * 3000, stderr="e" * 2000)
    peer_context = research_sessions._portfolio_context(
        large_preview_record, peer_branch, "skeptic", 1
    )
    preview = peer_context["other_strategy_evidence"][0]["python_execution"]
    assert preview["stdout_truncated"] and len(preview["stdout"]) == 2000
    assert preview["stderr_truncated"] and len(preview["stderr"]) == 1000
    assert large_execution["stdout"] == "x" * 3000 and preview["source"] == code
    prior_findings = research_sessions._prior_session_findings(str(path), str(uuid4()))
    assert prior_findings[0]["python_execution"]["id"] == execution["id"]
    assert prior_findings[0]["python_execution"]["status"] == "timeout"


async def test_recovery_reuses_saved_python_execution(path: Path):
    view, strategy, _, _ = await setup(path)
    session_id = str(uuid4())
    code = "print('persist before session update')"
    investigation_output = {**investigation(1), "python_code": code}
    record = {
        "id": session_id,
        "project_path": str(project_path(path)),
        "project_id": view.project.id,
        "status": "running",
        "strategy_runs": [
            {
                "strategy_id": strategy.id,
                "strategy_title": "Saved approach",
                "cycle": 1,
                "pending_investigation": investigation_output,
                "current_action": "Python execution",
            }
        ],
        "steps": [
            {
                "id": str(uuid4()),
                "strategy_id": strategy.id,
                "role": "investigator",
                "cycle": 1,
                "output": investigation_output,
            }
        ],
        "events": [],
    }
    research_sessions._save(str(path), record)
    container_result = python_sandbox.ExecutionResult(
        "completed", 0, "persist before session update\n", "", 50, "sha256:" + "a" * 64
    )
    with patch.object(python_sandbox, "execute", return_value=container_result):
        saved_execution = await python_sandbox.execute_research_code(
            str(path),
            code,
            session_id=session_id,
            strategy_id=strategy.id,
            cycle=1,
        )
    with patch.object(
        research_sessions,
        "execute_research_code",
        new=AsyncMock(side_effect=AssertionError("recovery must not rerun saved code")),
    ) as execute:
        await research_sessions._complete_pending_python(
            session_id, str(path), strategy.id, 1, asyncio.Lock()
        )
    execute.assert_not_awaited()
    recovered = research_sessions._read(str(path), session_id)
    branch = recovered["strategy_runs"][0]
    assert bare_execution(branch["pending_investigation"]["python_execution"]) == saved_execution
    assert bare_execution(recovered["steps"][0]["output"]["python_execution"]) == saved_execution
    assert any(event["kind"] == "python.recovered" for event in recovered["events"])


async def test_stop_during_python_execution_preserves_provenance(path: Path):
    view, strategy, credential, config = await setup(path)
    limits = research_sessions.get_limits(str(path))
    limits["research_rounds"] = 1
    research_sessions.save_limits(str(path), limits)
    code = "while True: pass"
    execution = {
        "id": str(uuid4()),
        "status": "timeout",
        "exit_code": 124,
        "stdout": "",
        "stderr": "Execution exceeded the 15-second wall limit.",
        "duration_ms": 15_000,
        "source": code,
        "artifacts": [],
        "environment": {"network": "none"},
    }
    execution_started = asyncio.Event()
    release_execution = asyncio.Event()
    provider_calls = []

    async def handler(request):
        provider_calls.append(json.loads(request.content))
        return httpx.Response(
            200,
            json=provider_response({**investigation(1), "python_code": code}),
        )

    async def delayed_execution(*_args, **_kwargs):
        execution_started.set()
        await release_execution.wait()
        return execution

    with (
        patch.object(research_sessions, "auth_context", new=AsyncMock(return_value=credential)),
        patch.object(research_sessions, "configuration", new=AsyncMock(return_value=config)),
        patch(
            "sigma.research_sessions.httpx.AsyncClient",
            side_effect=lambda **kwargs: REAL_CLIENT(
                transport=httpx.MockTransport(handler), **kwargs
            ),
        ),
        patch.object(research_sessions, "execute_research_code", new=delayed_execution),
    ):
        started = await research_sessions.start_session(
            str(path),
            strategy.id,
            str(uuid4()),
            view.project.id,
            credential["identity"],
            expected_limits=limits,
        )
        await asyncio.wait_for(execution_started.wait(), 2)
        stop_task = asyncio.create_task(
            research_sessions.control_session(str(path), started["id"], "stop")
        )
        await asyncio.sleep(0)
        release_execution.set()
        stopped = await asyncio.wait_for(stop_task, 2)

    assert stopped["status"] == "stopped"
    assert len(provider_calls) == 1  # the Skeptic is not called after a user stop
    saved = research_sessions.get_session(str(path), started["id"])
    pending = saved["strategy_runs"][0]["pending_investigation"]
    assert pending["python_code"] == code
    assert bare_execution(pending["python_execution"]) == execution
    assert pending["python_execution"]["artifact_inspections"] == []
    assert saved["steps"][0]["status"] == "completed"
    assert saved["steps"][0]["output"] == pending
    assert any(event["kind"] == "python.completed" for event in saved["events"])


async def test_failed_experiment_is_reused_then_revised(path: Path):
    view, strategy, credential, config = await setup(path)
    limits = research_sessions.get_limits(str(path))
    limits.update({"research_rounds": 3, "model_calls": 6})
    research_sessions.save_limits(str(path), limits)
    bad_code, repaired_code = (
        "raise ValueError('singular system')",
        "print('rank=1; underdetermined')",
    )
    calls, contexts = [], []

    async def compute(_path, source, **provenance):
        calls.append(source)
        result = python_sandbox.ExecutionResult(
            "failed" if source == bad_code else "completed",
            1 if source == bad_code else 0,
            "" if source == bad_code else "rank=1; underdetermined\n",
            "ValueError: singular system" if source == bad_code else "",
            5,
        )
        with patch.object(python_sandbox, "execute", return_value=result):
            return await python_sandbox.execute_research_code(_path, source, **provenance)

    async def handler(request):
        payload = json.loads(request.content)
        context = json.loads(payload["input"])
        cycle = context["cycle"]
        if payload["text"]["format"]["name"] == "research_investigator":
            if cycle > 1:
                assert (
                    context["prior_artifacts"][-1]["investigator_output"]["python_execution"][
                        "status"
                    ]
                    == "failed"
                )
            output = {
                **investigation(cycle),
                "python_code": bad_code if cycle < 3 else repaired_code,
            }
        else:
            evidence = context["investigator_output"]
            contexts.append(evidence)
            assert evidence["python_execution"]["source"] == evidence["python_code"]
            output = skeptic(cycle)
            output["next_question"] = (
                "Use rank-revealing least squares and report the null space; failure is not mathematical refutation."
            )
        return httpx.Response(200, json=provider_response(output))

    with (
        patch.object(research_sessions, "auth_context", new=AsyncMock(return_value=credential)),
        patch.object(research_sessions, "configuration", new=AsyncMock(return_value=config)),
        patch.object(research_sessions, "execute_research_code", new=compute),
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
    assert finished["status"] == "ended" and len(finished["artifacts"]) == 3, finished
    assert calls == [bad_code, repaired_code]
    assert contexts[0]["python_execution"] == contexts[1]["python_execution"]
    assert contexts[1]["python_execution"]["cycle"] == 1
    assert "original" in contexts[1]["python_execution_reuse_reason"]
    assert contexts[2]["python_execution"]["status"] == "completed"
    assert any(event["kind"] == "python.reused" for event in finished["events"])


async def test_restart_during_python_has_no_automatic_rerun(path: Path):
    await test_recovery_reuses_saved_python_execution(path)
    record = research_sessions._all(str(path))[0]
    branch = record["strategy_runs"][0]
    prior = branch["pending_investigation"].pop("python_execution")
    stored = path / "research-executions" / f"{prior['id']}.json"
    # Reproduce a real crash state: intent was published, terminal result was
    # never written. The host cannot infer whether the program actually ran.
    prior.update(status="running", exit_code=None, stdout="", stderr="", duration_ms=None)
    stored.write_text(json.dumps(prior))
    research_sessions._save(str(path), record)
    with patch.object(
        research_sessions,
        "execute_research_code",
        new=AsyncMock(side_effect=AssertionError("uncertain execution must not rerun")),
    ):
        await research_sessions._complete_pending_python(
            record["id"], str(path), branch["strategy_id"], 1, asyncio.Lock()
        )
    recovered = research_sessions._read(str(path), record["id"])
    evidence = recovered["strategy_runs"][0]["pending_investigation"]["python_execution"]
    assert evidence["status"] == "interrupted" and evidence["exit_code"] is None
    assert evidence["stdout"] == "" and "may have run" in evidence["interruption_reason"]
    recovered["deadline_at"] = "2000-01-01T00:00:00+00:00"
    pending = recovered["strategy_runs"][0]["pending_investigation"]
    pending.pop("python_execution")
    pending["python_code"] = "print('new work after deadline')"
    research_sessions._save(str(path), recovered)
    with patch.object(
        research_sessions,
        "execute_research_code",
        new=AsyncMock(side_effect=AssertionError("expired work must not dispatch")),
    ):
        await research_sessions._complete_pending_python(
            record["id"], str(path), branch["strategy_id"], 1, asyncio.Lock()
        )
    expired = research_sessions._read(str(path), record["id"])
    assert "python_execution" not in expired["strategy_runs"][0]["pending_investigation"]


async def test_portfolio_python_queue_and_stop(path: Path):
    for action in ("complete", "stop", "project-change"):
        stopping = action != "complete"
        case = path.with_name(action + ".sigma")
        view, first, credential, config = await setup(case)
        strategies = [first] + [
            create_strategy(
                case, f"Computation {i}", "Run an independently attributed finite experiment."
            ).project.strategies[-1]
            for i in (2, 3)
        ]
        limits = research_sessions.get_limits(str(case))
        limits.update(research_rounds=1, model_calls=6)
        limits = research_sessions.save_limits(str(case), limits)
        entered, release = asyncio.Event(), asyncio.Event()
        calls = []
        provider_investigations = []
        state = {"active": 0, "maximum": 0}

        async def handler(request, provider_investigations=provider_investigations):
            payload = json.loads(request.content)
            context = json.loads(payload["input"])
            if payload["text"]["format"]["name"] == "research_investigator":
                provider_investigations.append(context["strategy"]["id"])
                output = {**investigation(1), "python_code": "print('finite check')"}
            else:
                assert context["investigator_output"]["python_execution"]["status"] == "completed"
                output = skeptic(1, "stop", "productive_conclusion")
            return httpx.Response(200, json=provider_response(output))

        async def compute(
            _path,
            source,
            calls=calls,
            state=state,
            entered=entered,
            release=release,
            stopping=stopping,
            **provenance,
        ):
            calls.append(provenance)
            state["active"] += 1
            state["maximum"] = max(state["maximum"], state["active"])
            entered.set()
            try:
                if stopping:
                    await release.wait()
                else:
                    await asyncio.sleep(0.05)
                return {
                    "id": str(uuid4()),
                    "source": source,
                    "status": "completed",
                    "exit_code": 0,
                    "stdout": "finite check\n",
                    "stderr": "",
                    "artifacts": [],
                    **provenance,
                }
            finally:
                state["active"] -= 1

        with (
            patch.object(research_sessions, "auth_context", new=AsyncMock(return_value=credential)),
            patch.object(research_sessions, "configuration", new=AsyncMock(return_value=config)),
            patch.object(research_sessions, "execute_research_code", new=compute),
            patch(
                "sigma.research_sessions.httpx.AsyncClient",
                side_effect=lambda **kwargs: REAL_CLIENT(
                    transport=httpx.MockTransport(handler), **kwargs
                ),
            ),
        ):
            started = await research_sessions.start_session(
                str(case),
                first.id,
                str(uuid4()),
                view.project.id,
                credential["identity"],
                expected_limits=limits,
                strategy_ids=[item.id for item in strategies],
            )
            if stopping:
                await entered.wait()
                for _ in range(100):
                    if len(provider_investigations) == 3:
                        break
                    await asyncio.sleep(0.01)
                assert len(provider_investigations) == 3
                if action == "stop":
                    stop = asyncio.create_task(
                        research_sessions.control_session(str(case), started["id"], "stop")
                    )
                    await asyncio.sleep(0.02)
                    release.set()
                    finished = await stop
                else:
                    set_strategy_enabled(case, first.id, False)
                    release.set()
                    finished = await wait_for(case, started["id"])
            else:
                finished = await wait_for(case, started["id"])
        assert state["maximum"] == 1 and state["active"] == 0
        assert len(calls) == (1 if stopping else 3), calls
        assert (
            finished["status"]
            == {"complete": "ended", "stop": "stopped", "project-change": "paused"}[action]
        ), finished
        if stopping:
            assert len([e for e in finished["events"] if e["kind"] == "python.started"]) == 1
            assert len(finished["steps"]) == 3 and finished["calls_used"] == 3
        else:
            assert len(finished["artifacts"]) == 3 and finished["calls_used"] == 6


async def test_new_session_receives_prior_saved_findings(path: Path):
    view, strategy, credential, config = await setup(path)
    outputs = [investigation(1), skeptic(1, "stop", "decisive_counterexample")]
    contexts = []
    continuation_started = asyncio.Event()

    async def handler(request):
        payload = json.loads(request.content)
        context = json.loads(payload["input"])
        contexts.append((payload["text"]["format"]["name"], context))
        if context.get("prior_session_findings"):
            continuation_started.set()
            await asyncio.Event().wait()
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
        first = await research_sessions.start_session(
            str(path), strategy.id, str(uuid4()), view.project.id, credential["identity"]
        )
        completed = await wait_for(path, first["id"])
        assert completed["status"] == "ended" and len(completed["artifacts"]) == 1
        next_session = await research_sessions.start_session(
            str(path), strategy.id, str(uuid4()), view.project.id, credential["identity"]
        )
        await asyncio.wait_for(continuation_started.wait(), 2)
        await research_sessions.control_session(str(path), next_session["id"], "stop")

    next_context = next(
        item[1]
        for item in reversed(contexts)
        if item[0] == "research_investigator" and item[1].get("prior_session_findings")
    )
    assert next_context["prior_session_findings"] == [
        {
            "id": completed["artifacts"][0]["id"],
            "sequence": 1,
            "claim_or_question": completed["artifacts"][0]["claim_or_question"],
            "method": completed["artifacts"][0]["method"],
            "assumptions": ["Assumption 1"],
            "evidence_status": completed["artifacts"][0]["evidence_status"],
            "objections": completed["artifacts"][0]["objections"],
            "open_obligations": completed["artifacts"][0]["open_obligations"],
            "limitations": [
                "Check boundary case 1",
                "Obligation 1",
                "Resolve obligation 1",
                "Check obligation 1",
            ],
            "assumptions_reviewed": ["Assumption 1"],
            "coordinator_decision": completed["artifacts"][0]["coordinator_decision"],
            "next_question": completed["artifacts"][0]["next_question"],
            "skeptic_output": {
                "next_question": completed["artifacts"][0]["skeptic_output"]["next_question"],
            },
            "session_id": completed["id"],
            "session_number": completed["session_number"],
            "strategy_id": strategy.id,
            "strategy_title": strategy.title,
            "extract_truncated_fields": [],
            "reasoning_steps": [
                {
                    "number": 1,
                    "title": "Cycle 1 bounded consequence",
                    "epistemic_status": "deduction",
                    "basis_artifact_ids": [],
                    "argument": "The cycle 1 strategy yields its stated local consequence under the recorded assumption.",
                    "review": {
                        "disposition": "accepted",
                        "rationale": "The stated local consequence follows from its supplied premise for this cycle.",
                        "objection": "",
                    },
                }
            ],
            "source_readiness": {
                "state": "model_reviewed_steps",
                "assumptions": "model_reviewed",
                "original_in_context": False,
                "independently_verified": False,
            },
        }
    ], next_context["prior_session_findings"]
    assert next_context["prior_session_artifact_ids"] == [completed["artifacts"][0]["id"]]
    assert any(
        item["text"] == "Obligation 1" and item["status"] == "unresolved"
        for item in next_context["obligation_ledger"]
    )
    persisted = research_sessions.get_session(str(path), next_session["id"])
    assert persisted["prior_session_obligations"]
    assert persisted["prior_session_obligations"][0]["strategy_id"] == strategy.id
    assert (
        persisted["steps"][0]["prior_session_artifact_ids"]
        == next_context["prior_session_artifact_ids"]
    )


async def test_failed_attempt_guides_next_session_with_provenance(path: Path):
    view, strategy, credential, config = await setup(path)
    requests = []

    async def handler(request):
        payload = json.loads(request.content)
        requests.append(payload)
        if len(requests) == 1:
            return httpx.Response(403, json={"error": {"code": "permission_denied"}})
        context = json.loads(payload["input"])
        role = payload["text"]["format"]["name"]
        if role == "research_investigator":
            assert len(context["prior_session_failures"]) == 1
            failure = context["prior_session_failures"][0]
            assert failure["attempt_id"] in context["prior_session_failure_attempt_ids"]
            assert failure["failure_kind"] == "provider_rejected"
            assert "Python" in payload["instructions"]
            assert "Scientific Python is unavailable" in payload["instructions"]
            result = investigation(1)
            result["prior_session_failure_attempt_ids"] = [failure["attempt_id"]]
            result["method"] = (
                "The prior provider attempt was operationally unavailable, not mathematical evidence; "
                "this bounded retry changes to a self-contained symbolic derivation without proposing code."
            )
        else:
            assert context["prior_session_failures"][0]["attempt_id"] == failed_attempt_id
            assert (
                "Do not treat prior_session_failures as mathematical evidence"
                in payload["instructions"]
            )
            result = skeptic(1, "stop", "productive_conclusion")
        return httpx.Response(200, json=provider_response(result))

    with (
        patch.object(research_sessions, "auth_context", new=AsyncMock(return_value=credential)),
        patch.object(research_sessions, "configuration", new=AsyncMock(return_value=config)),
        patch.object(
            research_sessions,
            "execution_capabilities",
            return_value=execution_tool_fixture(False),
        ),
        patch(
            "sigma.research_sessions.httpx.AsyncClient",
            side_effect=lambda **kwargs: REAL_CLIENT(
                transport=httpx.MockTransport(handler), **kwargs
            ),
        ),
    ):
        failed_start = await research_sessions.start_session(
            str(path), strategy.id, str(uuid4()), view.project.id, credential["identity"]
        )
        failed = await wait_for(path, failed_start["id"])
        assert failed["status"] == "failed" and failed["artifacts"] == []
        failed_path = research_sessions._directory(str(path)) / f"{failed['id']}.json"
        original_bytes = failed_path.read_bytes()
        failed_attempt_id = failed["steps"][0]["id"]

        retry_start = await research_sessions.start_session(
            str(path), strategy.id, str(uuid4()), view.project.id, credential["identity"]
        )
        retried = await wait_for(path, retry_start["id"])

    assert retried["status"] == "ended"
    assert failed_path.read_bytes() == original_bytes
    artifact = retried["artifacts"][0]
    assert artifact["prior_session_failure_attempt_ids"] == [failed_attempt_id]
    retry_step = next(item for item in retried["steps"] if item["role"] == "investigator")
    assert retry_step["prior_session_failure_attempt_ids"] == [failed_attempt_id]
    assert retried["prior_session_failures"][0]["attempt_id"] == failed_attempt_id


def test_prior_session_failure_history_prioritizes_newest_attempts(path: Path):
    view = initialize_project(path, "Failure history", "A bounded research question.")
    old_session_id, new_session_id = str(uuid4()), str(uuid4())

    def save_failed_session(
        session_id: str, created_at: str, attempt_id: str, attempted_at: str
    ) -> None:
        research_sessions._save(
            view.path,
            {
                "id": session_id,
                "project_path": view.path,
                "project_id": view.project.id,
                "session_number": 1,
                "strategy_id": "strategy",
                "strategy_title": "Approach",
                "status": "failed",
                "created_at": created_at,
                "updated_at": created_at,
                "steps": [
                    {
                        "id": attempt_id,
                        "strategy_id": "strategy",
                        "strategy_title": "Approach",
                        "role": "investigator",
                        "cycle": 1,
                        "status": "failed",
                        "started_at": attempted_at,
                        "finished_at": attempted_at,
                        "failure_kind": "provider_error",
                    }
                ],
            },
        )

    older_attempt = str(uuid4())
    newer_attempt = str(uuid4())
    # Deliberately make session creation order disagree with attempt recency.
    save_failed_session(
        old_session_id,
        "2026-10-23T12:00:00+00:00",
        older_attempt,
        "2026-10-23T10:00:00+00:00",
    )
    save_failed_session(
        new_session_id,
        "2026-10-23T09:00:00+00:00",
        newer_attempt,
        "2026-10-23T11:00:00+00:00",
    )
    findings, omitted = research_sessions._prior_session_failures(view.path, str(uuid4()))
    assert omitted == 0
    assert [item["attempt_id"] for item in findings] == [newer_attempt, older_attempt]
    assert [item["attempted_at"] for item in findings] == [
        "2026-10-23T11:00:00+00:00",
        "2026-10-23T10:00:00+00:00",
    ]


def test_continuation_context_is_bounded(path: Path):
    view = initialize_project(path, "Long-history project", "A bounded research question.")
    source_id = str(uuid4())
    source = {
        "id": source_id,
        "project_path": view.path,
        "project_id": view.project.id,
        "session_number": 1,
        "strategy_id": str(uuid4()),
        "strategy_title": "Long history approach",
        "status": "ended",
        "created_at": research_sessions._now(),
        "updated_at": research_sessions._now(),
        "artifacts": [
            {
                "id": str(uuid4()),
                "sequence": sequence,
                "strategy_id": str(uuid4()),
                "claim_or_question": f"Finding {sequence} " + "x" * 3000,
                "method": "Method " + "y" * 3000,
                "evidence_status": "Unverified " + "z" * 3000,
                "objections": ["Objection " + "o" * 300 for _ in range(12)],
                "open_obligations": ["Obligation " + "p" * 300 for _ in range(12)],
                "coordinator_decision": "continue",
                "next_question": "Next " + "q" * 3000,
            }
            for sequence in range(1, 21)
        ],
    }
    research_sessions._save(view.path, source)
    current = {
        "id": str(uuid4()),
        "project_path": view.path,
        "problem": view.project.problem,
        "strategy_id": str(uuid4()),
        "strategy_title": "Current approach",
        "strategy_text": "Continue from saved findings.",
        "current_question": "Avoid repeating prior work.",
        "strategy_snapshot": [],
        "artifacts": [],
    }
    context = research_sessions._agent_context(current, "investigator", 1)
    encoded = json.dumps(context, ensure_ascii=False)
    findings = context["prior_session_findings"]
    assert 1 <= len(findings) <= 12
    assert "Finding 20" in findings[0]["claim_or_question"]
    assert "[truncated; inspect the original saved artifact]" in findings[0]["claim_or_question"]
    assert len(encoded) < 48000
    assert source["artifacts"][0]["claim_or_question"].endswith("x" * 3000)


def test_t37_context_selection_is_stable_and_loss_visible(path: Path):
    view = initialize_project(path, "Evidence selection", "Keep the active question bounded.")
    strategy_id = str(uuid4())
    session_id = str(uuid4())
    counterexample_id = str(uuid4())
    old_obligation_id = str(uuid4())
    latest_id = str(uuid4())
    artifacts = [
        {
            "id": counterexample_id,
            "sequence": 1,
            "session_id": session_id,
            "strategy_id": strategy_id,
            "claim_or_question": "A plausible claim is refuted by x=7.",
            "method": "Substitute x=7 into the claimed identity; the two sides differ.",
            "evidence_status": "Concrete counterexample; claim is false under stated assumptions.",
            "coordinator_decision": "stop_decisive_counterexample",
            "objections": ["The proposed universal claim fails at x=7."],
            "open_obligations": [],
        },
        {
            "id": old_obligation_id,
            "sequence": 2,
            "session_id": session_id,
            "strategy_id": strategy_id,
            "claim_or_question": "An older obligation not mentioned later.",
            "method": "Old method.",
            "evidence_status": "Unverified.",
            "open_obligations": ["Check the old boundary case."],
        },
    ]
    artifacts.extend(
        {
            "id": str(uuid4()),
            "sequence": index,
            "session_id": session_id,
            "strategy_id": strategy_id,
            "claim_or_question": f"Optional historical note {index} " + "q" * 2200,
            "method": "Routine intermediate prose " + "m" * 2500,
            "evidence_status": "Unverified intermediate note.",
            "open_obligations": [],
            "objections": [],
        }
        for index in range(3, 131)
    )
    artifacts.append(
        {
            "id": latest_id,
            "sequence": 131,
            "session_id": session_id,
            "strategy_id": strategy_id,
            "claim_or_question": "Test the current narrow claim.",
            "method": "Compare both sides under the stated domain assumptions.",
            "evidence_status": "Unverified.",
            "open_obligations": ["Show the claim holds for every allowed input."],
            "objections": [],
        }
    )
    original_json = json.dumps(artifacts, ensure_ascii=False)
    context_record = {
        "id": str(uuid4()),
        "project_path": view.path,
        "project_id": view.project.id,
        "problem": view.project.problem,
        "strategy_id": strategy_id,
        "strategy_title": "Test a claim",
        "strategy_text": "Use direct substitution and a proof attempt.",
        "current_question": "Find a discriminating test for the current claim.",
        "strategy_snapshot": [],
        "artifacts": artifacts,
    }
    first = research_sessions._agent_context(context_record, "investigator", 132)
    second = research_sessions._agent_context(context_record, "investigator", 132)
    selected_ids = [item["id"] for item in first["prior_artifacts"]]
    assert selected_ids == [item["id"] for item in second["prior_artifacts"]]
    assert {counterexample_id, old_obligation_id, latest_id} <= set(selected_ids)
    assert len(selected_ids) <= research_sessions.MAX_CONTEXT_ARTIFACTS
    assert first["context_manifest"]["omitted_count"] > 100
    assert any(
        counterexample_id in item["source_ids"] and item["status"] == "selected"
        for item in first["context_manifest"]["sources"]
    )
    assert any(
        any(source_id not in selected_ids for source_id in item["source_ids"])
        and item["status"] == "omitted"
        for item in first["context_manifest"]["sources"]
    )
    obligations = {item["text"]: item for item in first["obligation_ledger"]}
    assert obligations["Show the claim holds for every allowed input."]["status"] == "unresolved"
    assert obligations["Check the old boundary case."]["status"] == "unresolved"
    assert first["question"] == "Find a discriminating test for the current claim."
    assert json.dumps(artifacts, ensure_ascii=False) == original_json
    assert (
        first["context_manifest"]["assembled_context_bytes"]
        <= research_sessions.MAX_AGENT_CONTEXT_BYTES
    )

    live_step_id = str(uuid4())
    current_review_context = research_sessions._agent_context(
        {
            **context_record,
            "pending_investigation": {
                "claim": "Current investigator claim",
                "open_obligations": ["Check the investigator's claimed boundary."],
            },
            "steps": [
                {
                    "id": live_step_id,
                    "role": "investigator",
                    "cycle": 132,
                    "strategy_id": strategy_id,
                }
            ],
        },
        "skeptic",
        132,
    )
    live_obligation = next(
        item
        for item in current_review_context["obligation_ledger"]
        if item["text"] == "Check the investigator's claimed boundary."
    )
    assert live_obligation["status"] == "unresolved"
    assert live_obligation["source_step_ids"] == [live_step_id]
    assert current_review_context["investigator_step_id"] == live_step_id

    old_disproof_id = str(uuid4())
    previous_session_id = str(uuid4())
    research_sessions._save(
        view.path,
        {
            "id": previous_session_id,
            "project_path": view.path,
            "project_id": view.project.id,
            "session_number": 1,
            "strategy_id": strategy_id,
            "strategy_title": "Earlier approach",
            "status": "ended",
            "created_at": research_sessions._now(),
            "updated_at": research_sessions._now(),
            "artifacts": [
                {
                    "id": old_disproof_id if index == 1 else str(uuid4()),
                    "sequence": index,
                    "strategy_id": strategy_id,
                    "claim_or_question": f"Prior claim {index}",
                    "method": "Substitute the alleged boundary value.",
                    "evidence_status": "Concrete counterexample at x=7"
                    if index == 1
                    else "Unverified note",
                    "coordinator_decision": "stop_decisive_counterexample"
                    if index == 1
                    else "continue",
                    "objections": [],
                    "open_obligations": [],
                }
                for index in range(1, 14)
            ],
        },
    )
    prior, prior_omitted, prior_omitted_ids = research_sessions._prior_session_findings_index(
        view.path, str(uuid4())
    )
    assert prior[0]["id"] == old_disproof_id
    assert prior_omitted == 1 and len(prior_omitted_ids) == 1

    explicit_statuses = ("unresolved", "addressed", "superseded", "retracted", "unknown")
    status_artifacts = []
    status_ids = {}
    for status in explicit_statuses:
        text = f"Disposition evidence for {status}."
        obligation_id = research_sessions._obligation_identity(
            text, project_id=None, strategy_id=None, assumptions=[]
        )
        artifact_id = str(uuid4())
        status_ids[status] = obligation_id
        status_artifacts.append(
            {
                "id": artifact_id,
                "open_obligations": [text],
                "skeptic_output": {
                    "obligation_reviews": [
                        {
                            "obligation_id": obligation_id,
                            "status": status,
                            "basis_artifact_ids": [artifact_id]
                            if status in {"addressed", "superseded", "retracted"}
                            else [],
                            "basis_step_ids": [],
                            "rationale": "Explicit fixture disposition for deterministic ledger coverage.",
                        }
                    ]
                },
            }
        )
    disposition_ledger, disposition_omitted, _ = research_sessions._obligation_ledger(
        status_artifacts
    )
    assert disposition_omitted == 0
    assert {item["status"] for item in disposition_ledger} == set(explicit_statuses)
    assert all(
        item.get("epistemic_status") == "model_reported_unverified"
        for item in disposition_ledger
        if item["status"] in {"addressed", "superseded", "retracted"}
    )
    many_unknown = [
        {
            "id": str(index),
            "open_obligations": [f"Historical obligation {index}"],
            "obligation_dispositions": [
                {"text": f"Historical obligation {index}", "status": "unknown"}
            ],
        }
        for index in range(research_sessions.MAX_CONTEXT_OBLIGATIONS + 36)
    ]
    bounded_ledger, omitted_obligations, omitted_obligation_ids = (
        research_sessions._obligation_ledger(many_unknown)
    )
    assert len(bounded_ledger) == research_sessions.MAX_CONTEXT_OBLIGATIONS
    assert omitted_obligations == 36 and len(omitted_obligation_ids) == 32
    assert all(item["status"] == "unknown" for item in bounded_ledger)

    over_budget = {
        **context_record,
        "id": str(uuid4()),
        "problem": "😀" * 70_000,
        "artifacts": [],
    }
    try:
        research_sessions._agent_context(over_budget, "investigator", 1)
    except research_sessions.ResearchContextLimitError as exc:
        assert "No provider call was made" in str(exc)
    else:
        raise AssertionError("UTF-8 over-budget mandatory question was accepted")


def test_t37_obligation_identity_lifecycle_and_history(path: Path):
    view = initialize_project(path, "Scoped obligation history", "Check an exact claim.")
    strategy = str(uuid4())
    text = "Prove the boundary case under the stated domain."
    a1, a2, reopen = str(uuid4()), str(uuid4()), str(uuid4())
    id_integer = research_sessions._obligation_identity(
        text, project_id=view.project.id, strategy_id=strategy, assumptions=["x is integer"]
    )
    id_real = research_sessions._obligation_identity(
        text, project_id=view.project.id, strategy_id=strategy, assumptions=["x is real"]
    )
    scoped = [
        {
            "id": a1,
            "strategy_id": strategy,
            "project_id": view.project.id,
            "assumptions": ["x is integer"],
            "open_obligations": [text],
            "obligation_dispositions": [
                {
                    "obligation_id": id_integer,
                    "status": "addressed",
                    "basis_artifact_ids": [a1],
                    "rationale": "Explicit fixture.",
                }
            ],
        },
        {
            "id": a2,
            "strategy_id": strategy,
            "project_id": view.project.id,
            "assumptions": ["x is real"],
            "open_obligations": [text],
        },
        {
            "id": reopen,
            "strategy_id": strategy,
            "project_id": view.project.id,
            "assumptions": ["x is integer"],
            "open_obligations": [text],
        },
    ]
    initial_ledger, _, _ = research_sessions._obligation_ledger(
        scoped[:2], project_id=view.project.id, strategy_id=strategy
    )
    initial_by_id = {item["obligation_id"]: item for item in initial_ledger}
    assert initial_by_id[id_integer]["status"] == "addressed"
    assert initial_by_id[id_real]["status"] == "unresolved"
    ledger, omitted, _ = research_sessions._obligation_ledger(
        scoped, project_id=view.project.id, strategy_id=strategy
    )
    assert omitted == 0 and len(ledger) == 2
    by_id = {item["obligation_id"]: item for item in ledger}
    assert by_id[id_integer]["status"] == "unresolved"  # later restatement reopens it
    assert by_id[id_real]["status"] == "unresolved"  # integer disposition cannot cross scope
    assert by_id[id_integer]["source_artifact_ids"] == [a1, reopen]

    prefix = "P" * 705
    long_a, long_b = prefix + "A", prefix + "B"
    long_ledger, _, _ = research_sessions._obligation_ledger(
        [
            {"id": "long-a", "strategy_id": strategy, "open_obligations": [long_a]},
            {"id": "long-b", "strategy_id": strategy, "open_obligations": [long_b]},
        ],
        project_id=view.project.id,
        strategy_id=strategy,
    )
    assert len(long_ledger) == 2
    assert all(item["text_complete"] is False for item in long_ledger)

    # Old text-only IDs remain readable only when the mapping is unambiguous.
    old_text = "Legacy obligation without a stored identifier."
    old_id = research_sessions._legacy_obligation_identity(old_text)
    legacy, _, _ = research_sessions._obligation_ledger(
        [
            {"id": "legacy-source", "strategy_id": strategy, "open_obligations": [old_text]},
            {
                "id": "legacy-review",
                "strategy_id": strategy,
                "obligation_dispositions": [
                    {
                        "obligation_id": old_id,
                        "status": "addressed",
                        "basis_artifact_ids": ["legacy-source"],
                    }
                ],
            },
        ],
        project_id=view.project.id,
        strategy_id=strategy,
    )
    assert legacy[0]["status"] == "addressed"
    ambiguous, _, _ = research_sessions._obligation_ledger(
        [
            {
                "id": "legacy-i",
                "strategy_id": strategy,
                "assumptions": ["integer"],
                "open_obligations": [old_text],
            },
            {
                "id": "legacy-r",
                "strategy_id": strategy,
                "assumptions": ["real"],
                "open_obligations": [old_text],
            },
            {
                "id": "legacy-d",
                "strategy_id": strategy,
                "obligation_dispositions": [
                    {
                        "obligation_id": old_id,
                        "status": "addressed",
                        "basis_artifact_ids": ["legacy-i"],
                    }
                ],
            },
        ],
        project_id=view.project.id,
        strategy_id=strategy,
    )
    assert all(item["status"] == "unresolved" for item in ambiguous)
    assert all(item.get("ambiguous_legacy_dispositions") for item in ambiguous)

    repeated = [
        {
            "id": f"repeat-{i}",
            "sequence": i,
            "strategy_id": strategy,
            "claim_or_question": "Routine discussion mentions a counterexample but proves nothing.",
            "method": "Routine discussion.",
            "evidence_status": "Unverified.",
            "open_obligations": ["One unresolved shared obligation."],
            "objections": [],
        }
        for i in range(105)
    ]
    ledger, _, _ = research_sessions._obligation_ledger(
        repeated, project_id=view.project.id, strategy_id=strategy
    )
    selected, manifest = research_sessions._select_context_artifacts(
        repeated, "investigator", view.path, ledger
    )
    assert len(selected) <= research_sessions.MAX_CONTEXT_ARTIFACTS
    assert len(ledger) == 1 and ledger[0]["source_artifact_count"] == 105
    assert manifest["obligation_source_omissions"][0]["omitted_count"] >= 100
    assert not any(research_sessions._artifact_is_critical(item) for item in repeated)
    routine_context = research_sessions._agent_context(
        {
            "id": str(uuid4()),
            "project_path": view.path,
            "project_id": view.project.id,
            "problem": view.project.problem,
            "strategy_id": strategy,
            "strategy_title": "Routine repeats",
            "strategy_text": "Continue carefully.",
            "current_question": "Resolve the repeated open obligation.",
            "strategy_snapshot": [],
            "artifacts": repeated,
        },
        "investigator",
        106,
    )
    assert len(routine_context["prior_artifacts"]) <= research_sessions.MAX_CONTEXT_ARTIFACTS
    assert routine_context["outstanding_obligations"] == ["One unresolved shared obligation."]
    assert (
        routine_context["context_manifest"]["obligation_source_omissions"][0]["omitted_count"]
        >= 100
    )

    # Coordinator reconciliation may add obligations beyond the provider's
    # 12-item schema ceiling. Preserve that ledger-backed list up to the
    # existing 64-obligation context bound so Resume does not truncate it.
    reconciled_obligations = [f"Reconciled obligation {number}." for number in range(16)]
    expanded_evidence = research_sessions._compact_context_artifact(
        {
            "id": "expanded-obligation-evidence",
            "open_obligations": reconciled_obligations,
            "investigator_output": {"open_obligations": reconciled_obligations},
            "skeptic_output": {"remaining_obligations": reconciled_obligations},
        },
        view.path,
    )
    assert expanded_evidence["open_obligations"] == reconciled_obligations
    assert expanded_evidence["skeptic_output"]["remaining_obligations"] == reconciled_obligations
    assert expanded_evidence["extract_truncated_fields"] == []
    long_reconciled_obligation = "A coordinator-retained obligation. " + "details " * 80
    bounded_obligation = research_sessions._compact_context_artifact(
        {
            "id": "long-reconciled-obligation",
            "open_obligations": [long_reconciled_obligation],
            "skeptic_output": {"remaining_obligations": [long_reconciled_obligation]},
        },
        view.path,
    )
    assert bounded_obligation["open_obligations"] == [long_reconciled_obligation]
    assert bounded_obligation["skeptic_output"]["remaining_obligations"] == [
        long_reconciled_obligation
    ]
    assert bounded_obligation["extract_truncated_fields"] == []
    beyond_context_bound = research_sessions._compact_context_artifact(
        {
            "id": "over-bound-obligations",
            "open_obligations": [
                f"Over-bound obligation {number}."
                for number in range(research_sessions.MAX_CONTEXT_OBLIGATIONS + 1)
            ],
        },
        view.path,
    )
    assert "open_obligations" in beyond_context_bound["extract_truncated_fields"]

    # A complete multi-step proof must survive the deterministic extract intact.
    long_proof = {
        "id": "long-proof",
        "strategy_id": strategy,
        "open_obligations": ["Resolve this proof obligation."],
        "claim_or_question": "Claim",
        "method": "Step 1. " + "A complete proof step. " * 200,
        "evidence_status": "Unverified",
    }
    compact_proof = research_sessions._compact_context_artifact(long_proof, view.path)
    assert compact_proof["method"] == long_proof["method"]
    assert compact_proof["extract_truncated_fields"] == []

    # A required proof source with decisive content beyond the deterministic
    # extract bound must not be represented to a provider as supplied evidence.
    decisive = {
        "id": "truncated-proof",
        "strategy_id": strategy,
        "open_obligations": ["Resolve this proof obligation."],
        "claim_or_question": "Claim",
        "method": "M" * 12_001 + " decisive final line",
        "evidence_status": "Unverified",
    }
    before = json.dumps(decisive)
    record = {
        "id": str(uuid4()),
        "project_path": view.path,
        "project_id": view.project.id,
        "problem": view.project.problem,
        "strategy_id": strategy,
        "strategy_title": "Scoped",
        "strategy_text": "Investigate",
        "current_question": "Continue",
        "strategy_snapshot": [],
        "artifacts": [decisive],
    }
    try:
        research_sessions._agent_context(record, "investigator", 1)
    except research_sessions.ResearchContextLimitError as exc:
        assert "extract is incomplete" in str(exc)
        assert "No provider call was made" in str(exc)
    else:
        raise AssertionError("A mandatory artifact with truncated decisive content was supplied")
    assert json.dumps(decisive) == before

    # Freeze an ordinary-language obligation ahead of thirteen routine notes,
    # and keep its strategy scope when assembled for a later session.
    prior_id = str(uuid4())
    other_strategy = str(uuid4())
    prior_artifacts = [
        {
            "id": "old-open",
            "sequence": 1,
            "strategy_id": strategy,
            "assumptions": ["integer domain"],
            "open_obligations": ["Establish the induction step for every integer n."],
        }
    ]
    prior_artifacts.extend(
        {
            "id": f"routine-{i}",
            "sequence": i + 1,
            "strategy_id": strategy,
            "claim_or_question": f"Ordinary routine finding {i}.",
            "open_obligations": [],
        }
        for i in range(13)
    )
    prior_artifacts.append(
        {
            "id": "other-domain",
            "strategy_id": other_strategy,
            "open_obligations": ["Do not transfer this unrelated domain obligation."],
        }
    )
    research_sessions._save(
        view.path,
        {
            "id": prior_id,
            "project_path": view.path,
            "project_id": view.project.id,
            "strategy_id": strategy,
            "status": "ended",
            "created_at": research_sessions._now(),
            "artifacts": prior_artifacts,
        },
    )
    (
        frozen,
        frozen_omitted,
        frozen_omitted_ids,
        frozen_omitted_by_strategy,
        frozen_omitted_ids_by_strategy,
        _,
    ) = research_sessions._prior_session_obligations_index(view.path, str(uuid4()), [strategy])
    assert frozen_omitted == 0 and not frozen_omitted_ids
    assert len(frozen) == 1 and frozen[0]["source_artifact_ids"] == ["old-open"]
    findings, findings_omitted, findings_omitted_ids = (
        research_sessions._prior_session_findings_index(
            view.path,
            str(uuid4()),
            strategy_ids=[strategy],
            obligation_source_ids={"old-open"},
        )
    )
    assert findings[0]["id"] == "old-open"
    assert findings[0]["extract_truncated_fields"] == []
    assert findings_omitted == 2 and len(findings_omitted_ids) == 2
    resumed_record = {
        "id": str(uuid4()),
        "project_path": view.path,
        "project_id": view.project.id,
        "problem": view.project.problem,
        "strategy_id": strategy,
        "strategy_title": "Scoped",
        "strategy_text": "Continue",
        "current_question": "Review remaining proof obligation.",
        "strategy_snapshot": [],
        "artifacts": [],
        "prior_session_obligations": frozen,
        "prior_session_findings": findings,
        "prior_session_findings_omitted": findings_omitted,
        "prior_session_findings_omitted_source_ids": findings_omitted_ids,
        "prior_session_obligations_omitted": frozen_omitted,
        "prior_session_obligation_omitted_by_strategy": frozen_omitted_by_strategy,
        "prior_session_obligation_omitted_ids_by_strategy": frozen_omitted_ids_by_strategy,
    }
    research_sessions._save(view.path, {**resumed_record, "status": "paused"})
    restored = research_sessions._read(view.path, resumed_record["id"])
    resumed_context = research_sessions._agent_context(restored, "investigator", 1)
    assert (
        resumed_context["obligation_ledger"][0]["text"] == prior_artifacts[0]["open_obligations"][0]
    )
    assert resumed_context["obligation_ledger"][0]["status"] == "unresolved"
    assert (
        resumed_context["obligation_ledger"][0]["source_artifact_availability"]
        == "adequate_bounded_extract_original_not_supplied"
    )
    assert all(
        "unrelated domain" not in item["text"] for item in resumed_context["obligation_ledger"]
    )

    # The same historical obligation remains present when its early source is
    # too large for the bounded prior-finding extract, but its evidence must be
    # explicitly unavailable rather than represented as inspected.
    prior_artifacts[0]["method"] = "Beginning of method. " + "tail" * 400
    research_sessions._save(
        view.path,
        {
            "id": prior_id,
            "project_path": view.path,
            "project_id": view.project.id,
            "strategy_id": strategy,
            "status": "ended",
            "created_at": research_sessions._now(),
            "artifacts": prior_artifacts,
        },
    )
    truncated_findings, _, _ = research_sessions._prior_session_findings_index(
        view.path, str(uuid4()), strategy_ids=[strategy], obligation_source_ids={"old-open"}
    )
    assert truncated_findings[0]["id"] == "old-open"
    assert "method" in truncated_findings[0]["extract_truncated_fields"]
    truncated_record = {
        **resumed_record,
        "id": str(uuid4()),
        "prior_session_findings": truncated_findings,
    }
    truncated_context = research_sessions._agent_context(truncated_record, "investigator", 1)
    carried = next(
        item
        for item in truncated_context["obligation_ledger"]
        if item["text"] == prior_artifacts[0]["open_obligations"][0]
    )
    assert carried["status"] == "unresolved"
    assert carried["source_artifact_availability"] == "incomplete_extract_original_not_supplied"


async def test_t37_mandatory_context_blocks_before_provider(path: Path):
    view, strategy, _, _ = await setup(path)
    session_id = str(uuid4())
    artifacts = [
        {
            "id": str(uuid4()),
            "sequence": index,
            "session_id": session_id,
            "project_id": view.project.id,
            "strategy_id": strategy.id,
            "claim_or_question": f"Counterexample candidate {index}",
            "method": f"Explicit counterexample investigation {index}.",
            "evidence_status": "Concrete counterexample candidate; preserve for Skeptic review.",
            "coordinator_decision": "stop_decisive_counterexample",
            "assumptions": ["The domain is fixed."],
            "objections": [],
            "open_obligations": [],
        }
        for index in range(research_sessions.MAX_CONTEXT_ARTIFACTS + 1)
    ]
    branch = {
        "strategy_id": strategy.id,
        "strategy_title": strategy.title,
        "strategy_text": strategy.approach,
        "current_question": "Test one precise consequence.",
        "status": "queued",
        "cycle": 0,
        "calls_used": 0,
        "artifacts": [],
    }
    record = {
        "id": session_id,
        "project_path": view.path,
        "project_id": view.project.id,
        "strategy_id": strategy.id,
        "strategy_title": strategy.title,
        "strategy_text": strategy.approach,
        "problem": view.project.problem,
        "current_question": branch["current_question"],
        "strategy_snapshot": [],
        "artifacts": artifacts,
        "strategy_runs": [branch],
        "steps": [],
        "events": [],
        "status": "running",
        "calls_used": 0,
        "call_limit": 6,
    }
    research_sessions._save(view.path, record)
    credential_mock = AsyncMock(side_effect=AssertionError("provider preflight must not run"))
    with (
        patch.object(research_sessions, "execution_capabilities", return_value=[]),
        patch.object(research_sessions, "auth_context", new=credential_mock),
    ):
        success = await research_sessions._portfolio_role_call(
            session_id,
            view.path,
            strategy.id,
            "investigator",
            1,
            asyncio.Semaphore(1),
            asyncio.Lock(),
        )
    saved = research_sessions._read(view.path, session_id)
    assert success is False
    assert credential_mock.await_count == 0
    assert saved["calls_used"] == 0 and saved["steps"] == []
    assert saved["strategy_runs"][0]["status"] == "paused"
    assert (
        "mandatory current-session evidence sources exceed" in saved["strategy_runs"][0]["reason"]
    )
    assert any(event["kind"] == "research.context_blocked" for event in saved["events"])

    # A required obligation whose deterministic text extract would truncate
    # must also stop at assembly, before the authentication/provider boundary.
    truncated_session_id = str(uuid4())
    truncated_branch = {**branch, "status": "queued", "calls_used": 0, "artifacts": []}
    truncated_record = {
        **record,
        "id": truncated_session_id,
        "strategy_runs": [truncated_branch],
        "artifacts": [
            {
                "id": "long-open-obligation",
                "sequence": 1,
                "strategy_id": strategy.id,
                "open_obligations": ["Resolve " + "x" * 710],
                "method": "Saved complete source remains in the original artifact.",
            }
        ],
        "status": "running",
        "calls_used": 0,
        "steps": [],
        "events": [],
    }
    research_sessions._save(view.path, truncated_record)
    credential_mock.reset_mock()
    with (
        patch.object(research_sessions, "execution_capabilities", return_value=[]),
        patch.object(research_sessions, "auth_context", new=credential_mock),
    ):
        allowed = await research_sessions._portfolio_role_call(
            truncated_session_id,
            view.path,
            strategy.id,
            "investigator",
            1,
            asyncio.Semaphore(1),
            asyncio.Lock(),
        )
    blocked = research_sessions._read(view.path, truncated_session_id)
    assert allowed is False and credential_mock.await_count == 0
    assert blocked["calls_used"] == 0 and blocked["steps"] == []
    assert "obligation exceeds the safe extract bound" in blocked["strategy_runs"][0]["reason"], (
        blocked["strategy_runs"][0]["reason"]
    )


async def test_clipped_investigator_automatically_recovers(path: Path):
    view, strategy, credential, config = await setup(path)
    limits = {**research_sessions.DEFAULT_LIMITS, "research_rounds": 1, "model_calls": 4}
    research_sessions.save_limits(str(path), limits)
    submitted = []

    async def handler(request):
        payload = json.loads(request.content)
        submitted.append(payload)
        role = payload["text"]["format"]["name"]
        if len(submitted) == 1:
            assert role == "research_investigator"
            return httpx.Response(
                200,
                json={
                    "status": "incomplete",
                    "incomplete_details": {"reason": "max_output_tokens"},
                    "usage": {"input_tokens": 120, "output_tokens": 4000},
                    "output": [
                        {
                            "type": "message",
                            "content": [
                                {
                                    "type": "output_text",
                                    "text": '{"claim": "partial untrusted statement',
                                }
                            ],
                        }
                    ],
                },
            )
        if len(submitted) == 2:
            assert role == "research_investigator"
            assert "retry_after_clipped_response" in json.loads(payload["input"])
            assert "compact" in payload["instructions"]
            return httpx.Response(200, json=provider_response(investigation(1)))
        assert role == "research_skeptic"
        return httpx.Response(200, json=provider_response(skeptic(1, "stop")))

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
    assert len(submitted) == 3
    assert finished["calls_used"] == 3
    assert [step["status"] for step in finished["steps"]] == [
        "incomplete",
        "completed",
        "completed",
    ]
    assert [step["role"] for step in finished["steps"]] == [
        "investigator",
        "investigator",
        "skeptic",
    ]
    assert finished["steps"][0]["token_usage"]["output_tokens"] == 4000
    assert finished["steps"][0]["partial_output"].startswith('{"claim": "partial')
    assert len(finished["artifacts"]) == 1
    assert finished["artifacts"][0]["investigator_output"]["claim"].startswith("Claim 1")
    assert "partial untrusted statement" not in json.dumps(finished["artifacts"])
    assert finished["estimated_cost_usd"] > 0


async def test_legacy_ended_clipped_response_can_resume(path: Path):
    view, strategy, credential, config = await setup(path)
    started_calls = []

    async def handler(request):
        started_calls.append(json.loads(request.content))
        role = started_calls[-1]["text"]["format"]["name"]
        return httpx.Response(
            200,
            json=provider_response(
                investigation(1) if role == "research_investigator" else skeptic(1, "stop")
            ),
        )

    limits = {**research_sessions.DEFAULT_LIMITS, "research_rounds": 1, "model_calls": 4}
    research_sessions.save_limits(str(path), limits)

    async def parked_worker(_session_id, _path):
        await asyncio.Event().wait()

    # Stop an undispatched placeholder to create a deterministic legacy fixture.
    with (
        patch.object(research_sessions, "auth_context", new=AsyncMock(return_value=credential)),
        patch.object(research_sessions, "configuration", new=AsyncMock(return_value=config)),
        patch.object(research_sessions, "_worker", new=parked_worker),
    ):
        started = await research_sessions.start_session(
            str(path), strategy.id, str(uuid4()), view.project.id, credential["identity"]
        )
        await research_sessions.control_session(str(path), started["id"], "stop")
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
        old = research_sessions._read(str(path), started["id"])
        old["status"] = "ended"
        old["calls_used"] = 1
        old["terminal_reason"] = "Provider response clipped at max_output_tokens."
        old["message"] = (
            "The provider response was clipped at the output-token limit. "
            "Partial output and usage were preserved; the run is incomplete and was not retried."
        )
        old["steps"] = [
            {
                "id": str(uuid4()),
                "role": "investigator",
                "cycle": 1,
                "strategy_id": strategy.id,
                "status": "incomplete",
                "incomplete_reason": "max_output_tokens",
                "partial_output": "partial",
                "token_usage": {"input_tokens": 120, "output_tokens": 500},
                "finished_at": old["updated_at"],
            }
        ]
        old["strategy_runs"][0].update(
            {
                "status": "ended",
                "current_action": "Incomplete · output limit",
                "calls_used": 1,
                "cycle": 1,
            }
        )
        # Keep cost accounting stable; avoid fabricating billed calls.
        research_sessions._save(str(path), old)
        assert research_sessions.get_session(str(path), started["id"])[
            "recoverable_clipped_response"
        ]
        resumed = await research_sessions.control_session(str(path), started["id"], "resume")
        assert resumed["status"] == "queued"
        finished = await wait_for(path, started["id"])
    assert len(started_calls) >= 2
    assert finished["calls_used"] >= 3
    assert finished["steps"][0]["status"] == "incomplete"
    assert len(finished["artifacts"]) >= 1


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
        assert "Investigator agent turn 1/12 in progress" in progress["message"]
        paused = await research_sessions.control_session(str(path), started["id"], "pause")
        await asyncio.sleep(0.02)
        paused = research_sessions.get_session(str(path), started["id"])
    assert paused["status"] == "paused" and paused["calls_used"] == 1
    assert paused["steps"][-1]["status"] == "interrupted"
    paused_metrics = {
        item["label"]: item["value"] for item in paused["outcome"]["metrics"]["operational"]
    }
    assert "1 interrupted / cancelled" in paused_metrics["Agent turns by status"]
    assert "1 later attempt(s)" not in paused_metrics["Provider failures / retries"]
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
        stopped_metrics = {
            item["label"]: item["value"] for item in stopped["outcome"]["metrics"]["operational"]
        }
        assert "2 interrupted / cancelled" in stopped_metrics["Agent turns by status"]
        assert "1 later attempt(s)" in stopped_metrics["Provider failures / retries"]
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
        rejection_message = ""
        try:
            await research_sessions.control_session(str(path), stopped_start["id"], "resume")
        except ProjectError as exc:
            rejection_message = str(exc)
            assert "authentication (401)" in rejection_message.lower()
        else:
            raise AssertionError("Rejected provider credentials must visibly reject resume")
    rejected = research_sessions.get_session(str(path), stopped_start["id"])
    assert rejected["status"] == "stopped"  # rejected credentials leave it stopped
    assert rejected["message"] == rejection_message


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

    clipped_path = path.parent / "clipped-output.sigma"
    clipped_view, clipped_strategy, clipped_credential, clipped_config = await setup(clipped_path)

    async def clipped(request):
        return httpx.Response(
            200,
            json={
                "status": "incomplete",
                "incomplete_details": {"reason": "max_output_tokens"},
                "usage": {"input_tokens": 120, "output_tokens": 700},
                "output": [
                    {
                        "type": "message",
                        "content": [{"type": "output_text", "text": "partial JSON fragment"}],
                    }
                ],
            },
        )

    with (
        patch.object(
            research_sessions, "auth_context", new=AsyncMock(return_value=clipped_credential)
        ),
        patch.object(
            research_sessions, "configuration", new=AsyncMock(return_value=clipped_config)
        ),
        patch(
            "sigma.research_sessions.httpx.AsyncClient",
            side_effect=lambda **kwargs: REAL_CLIENT(
                transport=httpx.MockTransport(clipped), **kwargs
            ),
        ),
    ):
        started = await research_sessions.start_session(
            str(clipped_path),
            clipped_strategy.id,
            str(uuid4()),
            clipped_view.project.id,
            clipped_credential["identity"],
        )
        incomplete = await wait_for(clipped_path, started["id"])
    assert incomplete["status"] == "paused" and incomplete["artifacts"] == []
    assert [step["status"] for step in incomplete["steps"]] == ["incomplete", "incomplete"]
    assert all(step["partial_output"] == "partial JSON fragment" for step in incomplete["steps"])
    assert all(step["token_usage"]["output_tokens"] == 700 for step in incomplete["steps"])
    assert incomplete["calls_used"] == 2
    assert incomplete["next_step_guidance"] and "Resume" in incomplete["next_step_guidance"]
    assert incomplete["strategy_runs"][0]["status"] == "paused"
    assert not any(step.get("role") == "skeptic" for step in incomplete["steps"])

    retained_path = path.parent / "assessment-error.sigma"
    retained_view, retained_strategy, retained_credential, retained_config = await setup(
        retained_path
    )
    outputs = [
        investigation(1),
        skeptic(1),
        investigation(2),
        httpx.ReadTimeout(""),
        httpx.ReadTimeout(""),
    ]

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
        # ChatGPT controls its own response length; the internal per-call
        # reservation is not a reason to discard complete, valid findings.
        above_soft_limit = await research_sessions._call(
            {**record, "output_token_limit": 11},
            "investigator",
            {"problem": view.project.problem, "strategy": strategy.approach},
        )
        assert above_soft_limit == result
    assert result == (output, {"input_tokens": 25, "cached_input_tokens": 5, "output_tokens": 12})


async def test_session_deadline_bounds_generous_call_timeout(path: Path):
    _, _, credential, _ = await setup(path)
    assert research_sessions.CALL_TIMEOUT == 900
    cancelled = asyncio.Event()

    async def handler(request):
        try:
            await asyncio.sleep(5)
        finally:
            cancelled.set()
        return httpx.Response(200, json=provider_response(investigation(1)))

    record = {
        "model": MODEL,
        "reasoning_effort": "high",
        "mode": credential["mode"],
        "identity_hash": research_sessions._digest(credential["identity"]),
        "deadline_at": (datetime.now(UTC) + timedelta(seconds=0.05)).isoformat(),
    }
    started = time.monotonic()
    with (
        patch.object(research_sessions, "auth_context", new=AsyncMock(return_value=credential)),
        patch(
            "sigma.research_sessions.httpx.AsyncClient",
            side_effect=lambda **kwargs: REAL_CLIENT(
                transport=httpx.MockTransport(handler), **kwargs
            ),
        ),
    ):
        try:
            await asyncio.wait_for(research_sessions._call(record, "investigator", {}), 1)
        except TimeoutError:
            pass
        else:
            raise AssertionError("An in-flight call must stop at the session deadline")
    assert time.monotonic() - started < 0.8
    assert cancelled.is_set()


async def test_limits_snapshot_and_usage_cost(path: Path):
    view, strategy, credential, config = await setup(path)
    assert research_sessions.get_limits(str(path)) == research_sessions.DEFAULT_LIMITS
    limits = {
        **research_sessions.DEFAULT_LIMITS,
        "research_rounds": 1,
        "model_calls": 2,
        "session_duration_minutes": 10,
        "output_tokens_per_call": 700,
        "maximum_estimated_cost_usd": 10.0,
        "maximum_input_tokens_per_session": 200_000,
    }
    assert research_sessions.save_limits(str(path), limits) == limits
    outputs = [investigation(1), skeptic(1)]

    async def handler(request):
        payload = json.loads(request.content)
        assert payload["max_output_tokens"] == research_sessions.MODEL_OUTPUT_LIMITS[MODEL]
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
    assert finished["maximum_estimated_cost_usd"] == 10.0
    assert finished["cost_status"] == "available" and finished["estimated_cost_usd"] > 0
    assert all(step["token_usage"]["input_tokens"] == 120 for step in finished["steps"])
    for step in finished["steps"]:
        reservation = step["provider_input_audit"]["budget_reservation"]
        assert reservation["request_body_bytes"] > 0
        assert reservation["input_token_bound"] == reservation["request_body_bytes"] + 8192
        assert reservation["status"] == "reserved"
    assert all(item["status"] == "settled" for item in finished["hard_budget_ledger"]["calls"])
    operational_metrics = {
        item["label"]: item["value"] for item in finished["outcome"]["metrics"]["operational"]
    }
    assert operational_metrics["Tokens · input / output / cached / total"] == "240 / 160 / 40 / 400"
    assert operational_metrics["Estimated monetary cost"] == (
        "$0.002004 estimated (rates checked 2026-10-23)"
    )
    assert research_sessions.get_limits(str(path)) == future


async def test_prior_obligation_reference_compaction_keeps_text_and_traceability(path: Path):
    view, strategy, _, _ = await setup(path)
    obligation_texts = [
        f"Resolve historical boundary case {index} without changing the invariant."
        for index in range(15)
    ]
    artifacts = []
    for obligation_text in obligation_texts:
        for _ in range(research_sessions.MAX_OBLIGATION_SOURCE_ARTIFACTS):
            artifacts.append(
                {
                    "id": str(uuid4()),
                    "strategy_id": strategy.id,
                    "claim_or_question": "Review the saved boundary case.",
                    "open_obligations": [obligation_text],
                }
            )
    prior_id = str(uuid4())
    research_sessions._save(
        str(path),
        {
            "id": prior_id,
            "project_path": view.path,
            "project_id": view.project.id,
            "strategy_id": strategy.id,
            "status": "completed",
            "created_at": research_sessions._now(),
            "artifacts": artifacts,
        },
    )

    with patch("sigma.sponsor_diagnostics.record") as diagnostic:
        frozen, omitted, _, omitted_by_strategy, _, _ = (
            research_sessions._prior_session_obligations_index(
                str(path), str(uuid4()), [strategy.id], diagnostics=True
            )
        )
    diagnostic.assert_called_once()
    assert diagnostic.call_args.args[0] == "sponsor_context"
    diagnostic_status = diagnostic.call_args.args[1]
    assert diagnostic_status.startswith("o0_b")
    assert len(diagnostic_status) <= 64 and diagnostic_status.replace("_", "").isalnum()

    assert omitted == 0
    assert omitted_by_strategy == {}
    assert {item["text"] for item in frozen} == set(obligation_texts)
    assert len(frozen) == len(obligation_texts)
    assert (
        research_sessions._json_bytes(frozen)
        <= research_sessions.MAX_PRIOR_OBLIGATION_CONTEXT_BYTES
    )
    compacted = [item for item in frozen if item.get("source_refs_omitted_count", 0)]
    assert compacted
    for item in compacted:
        assert len(item["source_refs"]) == 2
        assert item["source_refs"][0]["artifact_id"] == item["source_artifact_ids"][0]
        assert item["source_refs"][-1]["artifact_id"] == item["source_artifact_ids"][-1]
        assert (
            item["source_refs_omitted_count"]
            == research_sessions.MAX_OBLIGATION_SOURCE_ARTIFACTS - 2
        )

    saved = research_sessions._all(str(path))
    assert len(saved) == 1 and len(saved[0]["artifacts"]) == len(artifacts)


async def test_aggregate_prior_obligation_snapshot_retains_all_under_64kb(path: Path):
    view, first_strategy, _, _ = await setup(path)
    strategies = [first_strategy]
    for index in range(2):
        strategies.append(
            create_strategy(
                path,
                f"Saved approach {index + 2}",
                "Check a saved result against its boundary cases.",
            ).project.strategies[-1]
        )

    expected_texts = set()
    for strategy_index, strategy in enumerate(strategies):
        artifacts = []
        for obligation_index in range(13):
            text = (
                f"Investigate saved boundary condition {strategy_index:02d}-{obligation_index:02d}: "
                "preserve the original invariant and compare the reported cases."
            )
            expected_texts.add(text)
            for _ in range(research_sessions.MAX_OBLIGATION_SOURCE_ARTIFACTS):
                artifacts.append(
                    {
                        "id": str(uuid4()),
                        "strategy_id": strategy.id,
                        "claim_or_question": "Review the saved boundary case.",
                        "open_obligations": [text],
                    }
                )
        research_sessions._save(
            str(path),
            {
                "id": str(uuid4()),
                "project_path": view.path,
                "project_id": view.project.id,
                "strategy_id": strategy.id,
                "status": "completed",
                "created_at": research_sessions._now(),
                "artifacts": artifacts,
            },
        )

    frozen, omitted, _, omitted_by_strategy, _, _ = (
        research_sessions._prior_session_obligations_index(
            str(path), str(uuid4()), [strategy.id for strategy in strategies]
        )
    )
    assert omitted == 0 and omitted_by_strategy == {}
    assert {item["text"] for item in frozen} == expected_texts
    frozen_bytes = research_sessions._json_bytes(frozen)
    assert 32_000 < frozen_bytes <= research_sessions.MAX_PRIOR_OBLIGATION_CONTEXT_BYTES


async def test_prior_obligation_overflow_allows_repeatable_bounded_research(path: Path):
    """A large, unresolved history is a disclosure constraint, never a start blocker."""
    view, strategy, credential, config = await setup(path)
    prior_id = str(uuid4())
    artifacts = [
        {
            "id": str(uuid4()),
            "strategy_id": strategy.id,
            "claim_or_question": f"Saved investigation {index}.",
            "open_obligations": [
                f"Resolve distinct boundary obligation {index} for the recurrence."
            ],
        }
        for index in range(35)
    ]
    research_sessions._save(
        str(path),
        {
            "id": prior_id,
            "project_path": view.path,
            "project_id": view.project.id,
            "strategy_id": strategy.id,
            "status": "completed",
            "created_at": research_sessions._now(),
            "artifacts": artifacts,
        },
    )
    prior_bytes = (path / "research-sessions" / f"{prior_id}.json").read_bytes()
    limits = {**research_sessions.get_limits(str(path)), "research_rounds": 1, "model_calls": 2}
    research_sessions.save_limits(str(path), limits)
    provider_calls = []

    async def fake_provider(request):
        payload = json.loads(request.content)
        provider_calls.append(payload)
        if payload["text"]["format"]["name"] == "research_investigator":
            result = investigation(1)
        else:
            result = skeptic(1)
        return httpx.Response(200, json=provider_response(result))

    with (
        patch.object(research_sessions, "auth_context", new=AsyncMock(return_value=credential)),
        patch.object(research_sessions, "configuration", new=AsyncMock(return_value=config)),
        patch(
            "sigma.research_sessions.httpx.AsyncClient",
            side_effect=lambda **kwargs: REAL_CLIENT(
                transport=httpx.MockTransport(fake_provider), **kwargs
            ),
        ),
    ):
        first = await research_sessions.start_session(
            str(path), strategy.id, str(uuid4()), view.project.id, credential["identity"]
        )
        assert first["prior_session_obligations_omitted"] == 11
        assert len(first["prior_session_obligation_omitted_ids_by_strategy"][strategy.id]) == 11
        assert len(first["prior_session_obligations"]) == 24
        finished = await wait_for(path, first["id"])
        assert finished["calls_used"] == 2 and finished["artifacts"]
        first_manifest = finished["steps"][0]["context_manifest"]
        assert first_manifest["omitted_prior_session_obligations"]["count"] == 11
        assert len(first_manifest["omitted_prior_session_obligations"]["obligation_ids"]) == 11
        assert any(
            "11 prior-session unresolved obligations" in note
            for note in finished["outcome"]["caveats"]
        )

        # The same original strategy must remain runnable after its history
        # grows beyond the context bound; no manual forking or disabling.
        for index in range(35, 65):
            artifacts.append(
                {
                    "id": str(uuid4()),
                    "strategy_id": strategy.id,
                    "claim_or_question": f"Saved investigation {index}.",
                    "open_obligations": [
                        f"Resolve distinct boundary obligation {index} for the recurrence."
                    ],
                }
            )
        old = research_sessions._read(str(path), prior_id)
        research_sessions._save(str(path), {**old, "artifacts": artifacts})
        expanded_bytes = (path / "research-sessions" / f"{prior_id}.json").read_bytes()
        second = await research_sessions.start_session(
            str(path), strategy.id, str(uuid4()), view.project.id, credential["identity"]
        )
        assert second["prior_session_obligations_omitted"] >= 41
        repeated = await wait_for(path, second["id"])
        assert repeated["calls_used"] == 2 and repeated["artifacts"], (
            repeated.get("status"),
            repeated.get("message"),
            repeated.get("termination_reason_code"),
            repeated.get("steps"),
        )
        assert (
            repeated["steps"][0]["context_manifest"]["omitted_prior_session_obligations"]["count"]
            >= 41
        )
        assert (path / "research-sessions" / f"{prior_id}.json").read_bytes() == expanded_bytes

    assert len(provider_calls) == 4
    assert prior_bytes != expanded_bytes
    assert len(research_sessions._all(str(path))) == 3


def test_limits_validation(path: Path):
    initialize_project(path, "Limits project", "A question")
    before = research_sessions.get_limits(str(path))
    invalid = [
        {**before, "model_calls": 1},
        {**before, "model_calls": 121},
        {**before, "research_rounds": 6, "model_calls": 30},
        {**before, "session_duration_minutes": 7 * 24 * 60 + 1},
        {**before, "output_tokens_per_call": 20001},
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
        "research_rounds": 5,
        "model_calls": 120,
        "session_duration_minutes": 7 * 24 * 60,
        "output_tokens_per_call": 20000,
        "maximum_estimated_cost_usd": 100,
    }
    assert research_sessions.save_limits(str(path), valid_upper) == valid_upper
    research_sessions.save_limits(str(path), before)
    assert research_sessions.get_limits(str(path)) == before
    older_saved = {**before, "research_rounds": 6, "model_calls": 20}
    limits_file = path / "research-sessions" / "limits.json"
    limits_file.write_text(json.dumps(older_saved), encoding="utf-8")
    assert research_sessions.get_limits(str(path)) == older_saved
    try:
        research_sessions.save_limits(str(path), older_saved)
    except ProjectError:
        pass
    else:
        raise AssertionError("new settings validation accepted a saved value above its bound")


def test_shared_turn_schedule_accepts_strategy_count_changes():
    """A saved shared turn ceiling schedules whole pairs without strategy-count coupling."""
    for count in (1, 3, 5):
        active = [{"strategy_id": str(index)} for index in range(count)]
        for turns in (3, 6, 12):
            selected, cursor = research_sessions._affordable_portfolio_branches(active, turns, 0)
            assert len(selected) == min(count, turns // 2)
            assert len({item["strategy_id"] for item in selected}) == len(selected)
            assert cursor == len(selected) % count
        # Changing the active strategy count never invalidates the saved setting.
        limits = {**research_sessions.DEFAULT_LIMITS, "research_rounds": 3, "model_calls": 3}
        research_sessions._validate_limits(limits)
    five = [{"strategy_id": str(index)} for index in range(5)]
    first, cursor = research_sessions._affordable_portfolio_branches(five, 6, 0)
    second, _ = research_sessions._affordable_portfolio_branches(five, 2, cursor)
    assert [item["strategy_id"] for item in first] == ["0", "1", "2"]
    assert [item["strategy_id"] for item in second] == ["3"]

    # A changing active set preserves round-robin progress and serves every
    # remaining strategy before repeating one when each wave has one pair.
    active = [{"strategy_id": value} for value in "ABCD"]
    selected, cursor = research_sessions._affordable_portfolio_branches(active, 2, 0)
    assert [item["strategy_id"] for item in selected] == ["A"]
    active = [{"strategy_id": value} for value in "BCDE"]
    order = []
    for _ in active:
        selected, cursor = research_sessions._affordable_portfolio_branches(active, 2, cursor)
        order.extend(item["strategy_id"] for item in selected)
    assert order == ["C", "D", "E", "B"]

    # A pending Skeptic costs one final turn. An unstarted Investigator still
    # costs a pair and must not be selected when only one turn remains.
    mixed = [
        {"strategy_id": "investigator"},
        {"strategy_id": "skeptic", "pending_investigation": {"claim": "saved"}},
    ]
    selected, _ = research_sessions._affordable_portfolio_branches(mixed, 1, 0)
    assert [item["strategy_id"] for item in selected] == ["skeptic"]
    mixed = [
        {"strategy_id": "I0"},
        {"strategy_id": "I1"},
        {"strategy_id": "S2", "pending_investigation": {"claim": "saved"}},
    ]
    selected, cursor = research_sessions._affordable_portfolio_branches(mixed, 3, 0)
    assert [item["strategy_id"] for item in selected] == ["I0", "S2"]
    assert cursor == 0  # cursor advances past the last selected branch, not by count


async def test_pending_skeptic_uses_final_turn_and_deferred_outcome_is_specific(path: Path):
    view, first, credential, config = await setup(path)
    second_view = create_strategy(path, "Deferred route", "Check an independent argument.")
    second = next(item for item in second_view.project.strategies if item.id != first.id)
    limits = research_sessions.get_limits(str(path))
    limits.update(research_rounds=2, model_calls=2)
    limits = research_sessions.save_limits(str(path), limits)
    dispatched = []

    async def handler(request):
        payload = json.loads(request.content)
        context = json.loads(payload["input"])
        role = payload["text"]["format"]["name"]
        dispatched.append((context["strategy"]["id"], role, context["cycle"]))
        output = (
            investigation(context["cycle"])
            if role == "research_investigator"
            else skeptic(context["cycle"], "stop", "productive_conclusion")
        )
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
            str(path),
            first.id,
            str(uuid4()),
            view.project.id,
            credential["identity"],
            expected_limits=limits,
            strategy_ids=[first.id, second.id],
        )
        finished = await wait_for(path, started["id"])

    assert finished["status"] == "ended" and finished["calls_used"] == 2
    assert [role for _, role, _ in dispatched] == ["research_investigator", "research_skeptic"]
    assert dispatched[0][0] == dispatched[1][0] == first.id
    assert dispatched[0][2] == dispatched[1][2] == 1
    by_strategy_round = {}
    for step in finished["steps"]:
        by_strategy_round.setdefault((step["strategy_id"], step["cycle"]), set()).add(step["role"])
    assert all(roles == {"investigator", "skeptic"} for roles in by_strategy_round.values())
    deferred = next(run for run in finished["strategy_runs"] if run["strategy_id"] == second.id)
    assert deferred["calls_used"] == 0 and deferred["current_action"] == "Budget exhausted"
    assert deferred["reason"].startswith("Deferred:"), deferred
    assert second.title in finished["message"]
    assert deferred["status"] == "ended" and "Deferred:" in deferred["reason"]
    assert finished["outcome"]["solution_review"]["status"] != "achieved"


async def test_adversarial_achieved_reviews_never_publish_unsupported_solution(path: Path):
    async def run_case(case: str, skeptic_output: dict, turns: int, rounds: int):
        case_path = path.with_name(f"{case}.sigma")
        view, strategy, credential, config = await setup(case_path)
        limits = research_sessions.get_limits(str(case_path))
        limits.update(research_rounds=rounds, model_calls=turns)
        limits = research_sessions.save_limits(str(case_path), limits)
        calls = []

        async def handler(request):
            payload = json.loads(request.content)
            role = payload["text"]["format"]["name"]
            calls.append(role)
            output = (
                {**investigation(1), "claim": "Claim 1 is contradicted by the reviewed result."}
                if role == "research_investigator"
                else skeptic_output
            )
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
                str(case_path),
                strategy.id,
                str(uuid4()),
                view.project.id,
                credential["identity"],
                expected_limits=limits,
            )
            finished = await wait_for(case_path, started["id"])
        assert finished["status"] == "ended"
        assert finished["calls_used"] == turns == 2
        assert calls == ["research_investigator", "research_skeptic"]
        assert finished["outcome"]["solution_review"]["status"] != "achieved", case
        assert finished["outcome"]["assessment"] != "positive", case
        assert "Complete reviewed candidate answer" not in finished["outcome"]["conclusion"], case
        return finished

    productive_with_gap = skeptic(1, "stop", "productive_conclusion")
    productive = await run_case("productive-with-gap", productive_with_gap, 2, 1)
    assert productive["artifacts"][0]["skeptic_output"]["remaining_obligations"]

    contradictory = {
        **skeptic(1, "continue", "productive_conclusion"),
        "objective_status": "achieved",
        "solution_claim": "A different claim: the result is 17.",
        "remaining_obligations": [],
        "unresolved_objections": [],
        "next_question": "Reconcile the conflicting claims before finalizing.",
        "objections": [],
    }
    conflict = await run_case("contradictory-achieved", contradictory, 2, 1)
    assert conflict["artifacts"][0]["objective_review"]["status"] == "partial"

    unsupported_at_limit = {
        **skeptic(1, "stop", "productive_conclusion"),
        "objective_status": "achieved",
        "remaining_obligations": [],
        "unresolved_objections": [],
        "next_question": "",
        "objections": [],
        "reasoning_assessments": [
            {
                "step_number": 1,
                "disposition": "challenged",
                "rationale": "The conclusion does not follow from the stated local step.",
                "objection": "The reasoning omits the argument needed to establish the objective.",
                "basis_artifact_ids": [],
            }
        ],
    }
    bounded = await run_case("achieved-at-turn-limit", unsupported_at_limit, 2, 1)
    assert bounded["terminal_reason"] == "stop_budget_exhausted"
    assert bounded["artifacts"][0]["objective_review"]["status"] == "partial"


async def test_legacy_limits_are_preserved(path: Path):
    view, strategy, credential, _ = await setup(path)
    legacy = {
        "research_rounds": 3,
        "model_calls": 6,
        "session_duration_minutes": 180,
        "output_tokens_per_call": 4000,
        "maximum_estimated_cost_usd": 500.0,
    }
    (path / "research-sessions").mkdir(mode=0o700)
    limits_file = path / "research-sessions" / "limits.json"
    limits_file.write_text(json.dumps(legacy), encoding="utf-8")
    legacy = {**legacy, "max_concurrent_sessions": 1}
    limits_file.write_text(
        json.dumps(
            {key: value for key, value in legacy.items() if key != "max_concurrent_sessions"}
        ),
        encoding="utf-8",
    )
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
    failed_portfolio = research_sessions._outcome(
        {
            "status": "failed",
            "artifacts": [],
            "strategy_runs": [
                {
                    "strategy_id": "failed-route",
                    "strategy_title": "Failed route",
                    "status": "failed",
                    "reason": "Provider failed before a complete cycle.",
                }
            ],
        }
    )
    failed_finding = failed_portfolio["solution_review"]["strategy_findings"][0]
    assert failed_finding["strategy_id"] == "failed-route"
    assert failed_finding["status"] == "execution_failed"
    assert failed_finding["failure_reason"] == "Provider failed before a complete cycle."
    assert failed_finding["research_artifact_ids"] == []
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
    legacy_review = {
        "status": "partial",
        "claim": "Historical review without a verification status.",
    }
    legacy_outcome = research_sessions._outcome(
        {
            "status": "ended",
            "artifacts": [{**artifact, "objective_review": legacy_review}],
        }
    )
    assert legacy_outcome["solution_review"]["verification_status"] == "unknown"
    assert "verification_status" not in legacy_review  # derived default does not mutate evidence
    strategy_step = {
        "number": 1,
        "title": "Bounded branch result",
        "argument": "This is an explicit partial derivation for one strategy.",
        "epistemic_status": "deduction",
        "basis_artifact_ids": [],
        "research_artifact_id": "a1",
        "review": {
            "disposition": "unresolved",
            "rationale": "The branch needs a second lemma.",
            "objection": "The bound is not yet established.",
        },
    }
    portfolio = research_sessions._outcome(
        {
            "status": "ended",
            "strategy_id": "s1",
            "strategy_title": "Branch one",
            "strategy_runs": [
                {"strategy_id": "s1", "strategy_title": "Branch one", "status": "ended"},
                {
                    "strategy_id": "s2",
                    "strategy_title": "Branch two",
                    "status": "ended",
                },
                {
                    "strategy_id": "s3",
                    "strategy_title": "Failed before first artifact",
                    "status": "failed",
                    "reason": "Provider timed out before a complete research cycle.",
                    "artifacts": [],
                },
            ],
            "artifacts": [
                {
                    **artifact,
                    "id": "a1",
                    "strategy_id": "s1",
                    "strategy_title": "Branch one",
                    "reasoning_steps": [strategy_step],
                    "objective_review": {
                        "status": "partial",
                        "claim": "A bound candidate.",
                        "argument_steps": [strategy_step],
                    },
                },
                {
                    **artifact,
                    "id": "a2",
                    "strategy_id": "s2",
                    "strategy_title": "Branch two",
                    "reasoning_steps": [{**strategy_step, "research_artifact_id": "a2"}],
                    "objective_review": {
                        "status": "achieved",
                        "claim": "A reviewed conclusion.",
                        "argument_steps": [{**strategy_step, "research_artifact_id": "a2"}],
                    },
                },
            ],
        }
    )
    findings = portfolio["solution_review"]["strategy_findings"]
    assert [item["strategy_title"] for item in findings] == [
        "Branch one",
        "Branch two",
        "Failed before first artifact",
    ]
    assert (
        findings[0]["reasoning_steps"][0]["review"]["objection"]
        == "The bound is not yet established."
    )
    assert findings[0]["status"] == "partial"
    assert findings[0]["research_artifact_ids"] == ["a1"]
    assert findings[1]["research_artifact_ids"] == ["a2"]
    assert findings[2]["status"] == "execution_failed"
    assert findings[2]["execution_status"] == "failed"
    assert findings[2]["research_artifact_ids"] == []
    assert "timed out" in findings[2]["failure_reason"]
    assert "timed out" in findings[2]["open_obligations"][0]
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


def test_session_listing_ignores_sequence_metadata(path: Path):
    view = initialize_project(path, "Sequence metadata", "Keep session numbering separate.")
    directory = Path(view.path) / "research-sessions"
    directory.mkdir()
    (directory / "sequence.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "project_id": view.project.id,
                "project_path": str(project_path(view.path)),
                "next_session_number": 1,
            }
        )
    )
    assert research_sessions.list_sessions(view.path) == []


def test_outcome_conclusions_are_bounded_honest_and_synthesized(path: Path):
    view = initialize_project(
        path,
        "Conclusion cases",
        "Determine whether the stated formula holds for all n, and justify it.",
    )
    conclusion_step = {
        "number": 1,
        "title": "Match the insertion bound",
        "argument": "The insertion bound and attaining construction give the same value.",
        "epistemic_status": "deduction",
        "basis_artifact_ids": ["artifact-a"],
        "research_artifact_id": "artifact-a",
        "review": {
            "disposition": "accepted",
            "rationale": "The cited construction attains the upper bound.",
            "objection": "",
            "basis_artifact_ids": ["artifact-a"],
        },
    }
    artifact = {
        "id": "artifact-a",
        "sequence": 1,
        "strategy_id": "strategy-a",
        "claim_or_question": "R(n) = 1 + n(n+1)/2",
        "method": "The insertion argument gives the upper bound.",
        "skeptic_response": "The argument is coherent, but no external checker was used.",
        "reasoning_steps": [conclusion_step],
        "coordinator_decision": "stop_productive_conclusion",
        "open_obligations": [],
        "objective_review": {
            "status": "achieved",
            "verification_status": "convincing_unverified",
            "claim": "R(n) = 1 + n(n+1)/2 for every n ≥ 0.",
            "argument_summary": "The insertion bound and explicit arrangement match.",
            "argument_steps": [conclusion_step],
            "unresolved_objections": [],
            "basis_artifact_ids": ["artifact-a"],
        },
    }
    success = research_sessions._outcome(
        {"status": "ended", "problem": view.project.problem, "artifacts": [artifact]}
    )
    assert "### Complete reviewed candidate answer" in success["conclusion"]
    assert "for every n ≥ 0" in success["conclusion"]
    assert "not independently verified" in success["conclusion"].lower()

    oversized_artifact = {
        **artifact,
        "argument_summary": "Long supporting detail. "
        * (research_sessions.MAX_CONCLUSION_CHARACTERS // 10),
    }
    oversized = research_sessions._outcome_conclusion(
        {"status": "ended", "artifacts": [oversized_artifact]},
        {
            "assessment": "positive",
            "solution_review": {
                "status": "achieved",
                "claim": "R(n) = 1 + n(n+1)/2 for every n ≥ 0.",
                "argument_summary": oversized_artifact["argument_summary"],
                "unresolved_objections": [],
                "open_obligations": [],
            },
            "caveats": [],
            "basis_artifact_ids": ["artifact-a"],
        },
    )
    assert len(oversized) <= research_sessions.MAX_CONCLUSION_CHARACTERS
    assert oversized.startswith("### Conclusion truncated\n\n")
    assert "### Verification and scope" in oversized
    assert "not independently verified" in oversized.lower()
    assert "exceeded the display limit" in oversized
    assert "R(n) = 1 + n(n+1)/2" not in oversized
    assert oversized.endswith("before relying on it.")

    partial_artifact = {
        **artifact,
        "objective_review": {
            "status": "partial",
            "claim": "The upper bound appears to be triangular.",
            "argument_summary": "An attaining construction has not been established.",
            "unresolved_objections": ["The construction is missing."],
            "basis_artifact_ids": ["artifact-a"],
        },
        "open_obligations": ["Give an arrangement attaining the bound."],
    }
    partial = research_sessions._outcome(
        {"status": "ended", "problem": view.project.problem, "artifacts": [partial_artifact]}
    )
    assert "### Partial finding" in partial["conclusion"]
    assert "does not establish a complete answer" in partial["conclusion"]
    assert "The construction is missing." in partial["conclusion"]

    failed = research_sessions._outcome(
        {"status": "failed", "artifacts": [], "message": "Provider failed before saving."}
    )
    assert "### Failed investigation" in failed["conclusion"]
    assert "establishes no answer" in failed["conclusion"]

    unresolved = research_sessions._outcome({"status": "ended", "artifacts": []})
    assert "### Unresolved investigation" in unresolved["conclusion"]
    assert "No answer" in unresolved["conclusion"]

    branches = [
        {
            "strategy_id": "strategy-a",
            "strategy_title": "Insertion",
            "status": "ended",
            "artifacts": ["artifact-a"],
        },
        {
            "strategy_id": "strategy-b",
            "strategy_title": "Failed search",
            "status": "failed",
            "artifacts": [],
            "reason": "No finding saved.",
        },
    ]
    multi = research_sessions._outcome(
        {
            "status": "ended",
            "problem": view.project.problem,
            "strategy_runs": branches,
            "strategy_assessments": [
                {
                    "strategy_id": "strategy-a",
                    "strategy_title": "Insertion",
                    "assessment": "contributed_to_solution",
                },
                {
                    "strategy_id": "strategy-b",
                    "strategy_title": "Failed search",
                    "assessment": "unknown",
                },
            ],
            "artifacts": [artifact],
        }
    )
    assert "### Findings across strategies" in multi["conclusion"]
    assert "Insertion — candidate finding (unverified)" in multi["conclusion"]
    assert "Failed search — failed" in multi["conclusion"]
    assert "has not independently verified" in multi["conclusion"].lower()

    conflicting_artifact = {
        **artifact,
        "id": "artifact-b",
        "sequence": 2,
        "strategy_id": "strategy-b",
        "objective_review": {
            "status": "achieved",
            "claim": "R(n) = n² for every n.",
            "argument_summary": "A distinct candidate was reported.",
            "basis_artifact_ids": ["artifact-b"],
        },
    }
    conflict = research_sessions._outcome(
        {
            "status": "ended",
            "strategy_runs": [
                branches[0],
                {**branches[1], "status": "ended", "artifacts": ["artifact-b"]},
            ],
            "artifacts": [artifact, conflicting_artifact],
        }
    )
    assert "different candidate answers" in conflict["conclusion"]
    assert "remains unresolved" in conflict["conclusion"]

    # New sessions save the derived Markdown with their outcome. Historical
    # records without this version receive an honest fallback on read.
    persisted = {
        "schema_version": 1,
        "id": str(uuid4()),
        "project_path": view.path,
        "project_id": view.project.id,
        "status": "ended",
        "session_number": 1,
        "strategy_id": "strategy-a",
        "strategy_title": "Insertion",
        "strategy_runs": [],
        "strategy_assessments": [],
        "strategy_snapshot": [],
        "problem": view.project.problem,
        "steps": [],
        "events": [],
        "artifacts": [artifact],
        "outcome_conclusion_version": 1,
        "guard_state_hash": "project-state-fixture",
        "outcome": success,
    }
    research_sessions._save(view.path, persisted)
    reloaded = research_sessions._read(view.path, persisted["id"])
    assert reloaded["outcome"]["conclusion"] == success["conclusion"]
    assert research_sessions._public(reloaded)["outcome"]["conclusion"] == success["conclusion"]
    assert "outcome_conclusion_version" not in research_sessions._public(reloaded)
    assert "guard_state_hash" not in research_sessions._public(reloaded)
    snapshot, _ = papers._snapshot(view.path)
    session_source = next(item for item in snapshot["sources"] if item["kind"] == "session")
    assert session_source["data"]["outcome"]["conclusion"] == success["conclusion"]

    structured_step = {
        "number": 1,
        "title": "Count the pieces made by an inserted line",
        "argument": "At most n−1 intersections divide the new line into at most n pieces.",
        "epistemic_status": "deduction",
        "basis_artifact_ids": ["artifact-a"],
        "research_artifact_id": "artifact-a",
        "review": {
            "disposition": "accepted",
            "rationale": "The crossing bound implies at most n pieces.",
            "objection": "",
            "basis_artifact_ids": ["artifact-a"],
        },
    }
    structured_artifact = {
        **artifact,
        "reasoning_steps": [structured_step],
        "objective_review": {
            "status": "achieved",
            "claim": "Conditional on general position, R(n) = 1 + n(n+1)/2 for every n.",
            "claim_scope": "conditional",
            "argument_summary": "The insertion bound and attaining construction match under the stated premise.",
            "argument_steps": [structured_step],
            "assumptions": ["The lines are in general position."],
            "proof_obligations": [],
            "unresolved_objections": [],
            "basis_artifact_ids": ["artifact-a"],
        },
    }
    structured_record = {
        **persisted,
        "id": str(uuid4()),
        "session_number": 3,
        "artifacts": [structured_artifact],
        "outcome": research_sessions._outcome(
            {
                "status": "ended",
                "problem": view.project.problem,
                "artifacts": [structured_artifact],
            }
        ),
    }
    research_sessions._save(view.path, structured_record)
    structured_reloaded = research_sessions._read(view.path, structured_record["id"])
    structured_public = research_sessions._public(structured_reloaded)
    structured_review = structured_public["outcome"]["solution_review"]
    assert structured_public["outcome"]["conclusion"] == structured_record["outcome"]["conclusion"]
    assert structured_review["claim_scope"] == "conditional"
    assert structured_review["argument_steps"][0]["review"]["disposition"] == "accepted"
    assert structured_review["strategy_findings"][0]["reasoning_steps"][0]["review"]["rationale"]
    assert "Conditional on general position" in structured_public["outcome"]["conclusion"]

    legacy = {
        **persisted,
        "id": str(uuid4()),
        "session_number": 2,
        "outcome": dict(persisted["outcome"]),
    }
    legacy.pop("outcome_conclusion_version")
    legacy["outcome"].pop("conclusion", None)
    research_sessions._save(view.path, legacy)
    legacy_public = research_sessions._public(research_sessions._read(view.path, legacy["id"]))
    assert legacy_public["outcome"]["conclusion"] is None
    assert legacy_public["outcome"]["summary"] == legacy["outcome"]["summary"]
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
    assert (
        positive_but_failed["assessment"] == "mixed"
        and any(
            "no structured argument steps" in caveat.lower()
            for caveat in positive_but_failed["caveats"]
        )
        and any("Execution failed" in caveat for caveat in positive_but_failed["caveats"])
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


def test_deliberate_argument_gap_is_preserved_and_not_complete():
    long_gap = (
        "At most n−1 crossings give at most n pieces; the argument asserts that every piece contributes a new region. "
        * 48
    )
    assert len(long_gap) > 3000
    assert (
        research_sessions.ResearchReasoningStep.model_validate(
            {
                "title": "Extended insertion claim",
                "argument": long_gap,
                "epistemic_status": "deduction",
                "basis_artifact_ids": [],
            }
        ).argument
        == long_gap
    )
    investigation_record = {
        "reasoning_steps": [
            {
                "title": "Intersections divide the new line",
                "argument": "At most n-1 crossings give at most n pieces.",
                "epistemic_status": "deduction",
                "basis_artifact_ids": [],
            },
            {
                "title": "Each piece adds a new region",
                "argument": long_gap,
                "epistemic_status": "deduction",
                "basis_artifact_ids": [],
            },
        ]
    }
    skeptic_record = {
        "reasoning_assessments": [
            {
                "step_number": 1,
                "disposition": "accepted",
                "rationale": "The crossing bound gives at most n line pieces.",
                "objection": "",
                "basis_artifact_ids": [],
            },
            {
                "step_number": 2,
                "disposition": "challenged",
                "rationale": "This conclusion does not follow from the piece count alone.",
                "objection": "The piece count alone does not show that each piece lies in a distinct old region or that each region met in its interior is split into two.",
                "basis_artifact_ids": [],
            },
        ]
    }
    argument = research_sessions._reviewed_argument(investigation_record, skeptic_record)
    assert len(argument) == 2
    assert argument[1]["argument"] == long_gap
    assert argument[1]["review"]["disposition"] == "challenged"
    assert "distinct old region" in argument[1]["review"]["objection"]
    assert not research_sessions._argument_is_complete(argument)
    conjectured = [
        {
            "epistemic_status": "conjecture",
            "review": {
                "disposition": "accepted",
                "rationale": "The plausible pattern matches every supplied finite example.",
                "objection": "",
            },
        }
    ]
    assert research_sessions._argument_is_complete(conjectured)
    assert not research_sessions._argument_is_complete(conjectured, mathematical_proof=True)
    accepted_assumption = [
        {
            "argument": "The equation holds under premise P.",
            "epistemic_status": "assumption",
            "review": {
                "disposition": "accepted",
                "rationale": "This premise is explicitly stated as a condition of the claim.",
                "objection": "",
            },
        }
    ]
    assert not research_sessions._argument_is_complete(
        accepted_assumption,
        mathematical_proof=True,
        declared_assumptions=["The equation holds under premise P."],
        reviewed_assumptions=["The equation holds under premise P."],
    )
    assert research_sessions._argument_is_complete(
        accepted_assumption,
        mathematical_proof=True,
        claim_is_conditional=True,
        declared_assumptions=["The equation holds under premise P."],
        reviewed_assumptions=["The equation holds under premise P."],
    )
    assert not research_sessions._argument_is_complete(
        accepted_assumption,
        mathematical_proof=True,
        claim_is_conditional=True,
        declared_assumptions=[],
        reviewed_assumptions=[],
    )
    assert not research_sessions._argument_is_complete(
        accepted_assumption,
        mathematical_proof=True,
        claim_is_conditional=True,
        declared_assumptions=["The equation holds under premise P."],
        reviewed_assumptions=[],
    )
    assert not research_sessions._argument_is_complete(
        accepted_assumption,
        mathematical_proof=True,
        claim_is_conditional=True,
        declared_assumptions=["A different premise."],
        reviewed_assumptions=["The equation holds under premise P."],
    )
    assert (
        research_sessions._claim_scope(
            {"claim_is_conditional": True}, {"claim_is_conditional": False}
        )
        == "disputed"
    )


async def test_maximum_regions_solution_and_frozen_attribution(path: Path):
    problem = (
        "For each integer n >= 0, determine the maximum number of regions formed by n lines. "
        "Derive a formula, prove the upper bound, and show an arrangement attains it, including n=0."
    )
    view = initialize_project(
        path, "Maximum Regions Formed by Lines", problem, research_mode="mathematical"
    )
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
        "reasoning_steps": [
            {
                "title": "Scope and assumptions",
                "argument": "Lines are distinct straight lines in the Euclidean plane.",
                "epistemic_status": "assumption",
                "basis_artifact_ids": [],
            },
            {
                "title": "At most n new regions",
                "argument": "The nth line has at most n−1 distinct intersection points with earlier lines. These points divide it into at most n pieces. Each piece lies in one old region, and adding the line can split that region into at most two, so at most n new regions are created.",
                "epistemic_status": "deduction",
                "basis_artifact_ids": [],
            },
            {
                "title": "An intersection splits a region",
                "argument": "Each old region is an intersection of open half-planes and therefore convex. Along the inserted line, distinct pieces cannot lie in one old region: if they did, convexity would include the intervening crossing point on an old line, outside that region. Every open region met by the new line has points on both sides, so it is split into two.",
                "epistemic_status": "deduction",
                "basis_artifact_ids": [],
            },
            {
                "title": "Attaining every increment",
                "argument": "For lines y=kx+k², k=1,…,n, line k meets earlier line i at x=−(i+k). These x-coordinates are distinct as i varies, and the pairwise intersections are not triple intersections. Thus line k has k−1 distinct crossings and is cut into k pieces, each splitting a different old region.",
                "epistemic_status": "deduction",
                "basis_artifact_ids": [],
            },
            {
                "title": "Recurrence and base case",
                "argument": "The upper bound gives R(k)≤R(k−1)+k, and the construction attains k new regions at every insertion, so R(k)=R(k−1)+k for the maximizing arrangement. The empty arrangement has R(0)=1.",
                "epistemic_status": "deduction",
                "basis_artifact_ids": [],
            },
            {
                "title": "Closed form",
                "argument": "Induction gives R(n)=1+Σ(k=1…n)k=1+n(n+1)/2: it holds at n=0, and adding n to 1+(n−1)n/2 yields 1+n(n+1)/2.",
                "epistemic_status": "deduction",
                "basis_artifact_ids": [],
            },
        ],
        "assumptions": ["Lines are distinct straight lines in the Euclidean plane."],
        "claim_is_conditional": True,
        "evidence_status": "Complete unverified argument; no formal checker was run.",
        "open_obligations": [],
        "python_code": None,
        "sage_code": None,
        "prior_session_failure_attempt_ids": [],
        "computational_citations": [],
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
        "reasoning_assessments": [
            {
                "step_number": 1,
                "disposition": "accepted",
                "rationale": "The domain and general-position conditions are explicit and match the construction used for attainability.",
                "objection": "",
                "basis_artifact_ids": [],
            },
            {
                "step_number": 2,
                "disposition": "accepted",
                "rationale": "At most n−1 crossings create at most n line pieces, each able to split at most one prior region.",
                "objection": "",
                "basis_artifact_ids": [],
            },
            {
                "step_number": 3,
                "disposition": "accepted",
                "rationale": "Convexity prevents separated pieces sharing one region, and openness guarantees both sides of each cut.",
                "objection": "",
                "basis_artifact_ids": [],
            },
            {
                "step_number": 4,
                "disposition": "accepted",
                "rationale": "The pairwise intersection coordinates are distinct for fixed k, with no triple intersections, so all k pieces are realized.",
                "objection": "",
                "basis_artifact_ids": [],
            },
            {
                "step_number": 5,
                "disposition": "accepted",
                "rationale": "The universal insertion bound and the attaining family give matching recurrence increments from the empty arrangement.",
                "objection": "",
                "basis_artifact_ids": [],
            },
            {
                "step_number": 6,
                "disposition": "accepted",
                "rationale": "The sum identity follows by induction from n=0 and addition of the nth increment.",
                "objection": "",
                "basis_artifact_ids": [],
            },
        ],
        "claim_is_conditional": True,
        "assumptions_reviewed": ["Lines are distinct straight lines in the Euclidean plane."],
        "proof_obligations": [
            "Insertion lemma splits each affected region into two [cycle 1].",
            "The insertion bound proves the upper bound [cycle 1].",
            "The explicit family attains each bound [cycle 1].",
            "The empty arrangement and small values are covered [cycle 1].",
        ],
        "verification_status": "convincing_unverified",
        "unresolved_objections": [],
        "supporting_cycles": [1],
        "strategy_contribution": "solution",
        "contribution_rationale": "The linked argument supplies both the matching upper bound and an explicit attaining construction.",
    }
    outputs = [proof, review]
    history = [
        {"id": f"artifact-{index}", "sequence": index, "method": f"Evidence {index}"}
        for index in range(1, 5)
    ]
    context_record = {
        "problem": problem,
        "strategy_id": strategy.id,
        "strategy_title": strategy.title,
        "strategy_text": strategy.approach,
        "current_question": "review the complete record",
        "artifacts": history,
        "pending_investigation": proof,
    }
    history_context = research_sessions._agent_context(context_record, "skeptic", 5)
    assert [item["id"] for item in history_context["prior_artifacts"]] == [
        "artifact-1",
        "artifact-2",
        "artifact-3",
        "artifact-4",
    ]
    oversized_context = {**context_record, "artifacts": [{"id": "old", "method": "x" * 300000}]}
    compacted = research_sessions._agent_context(oversized_context, "skeptic", 2)
    assert compacted["prior_artifacts"][0]["method"].startswith("x" * 100)
    assert (
        "truncated; inspect the original saved artifact"
        in compacted["prior_artifacts"][0]["method"]
    )
    assert "old" in compacted["context_manifest"]["sources"][0]["source_ids"]
    assert oversized_context["artifacts"][0]["method"] == "x" * 300000

    provider_requests = []

    async def handler(request):
        provider_requests.append(json.loads(request.content))
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
        assert "context manifest explains selection" in provider_requests[1]["instructions"]
        skeptic_context = json.loads(provider_requests[1]["input"])
        assert skeptic_context["context_manifest"]["policy_version"] == "t37-v1"
        assert "prior_artifacts" in skeptic_context
        assert skeptic_context["investigator_output"]["claim"] == proof["claim"]
        assert all(isinstance(step.get("context_manifest"), dict) for step in finished["steps"])
        from sigma.api import export_project_view

        exported_session = next(
            item
            for item in export_project_view(str(path))["research_sessions"]
            if item["id"] == finished["id"]
        )
        assert exported_session["steps"][1]["context_manifest"]["policy_version"] == "t37-v1"
        assert (
            exported_session["outcome"]["solution_review"]["argument_steps"]
            == finished["outcome"]["solution_review"]["argument_steps"]
        )
        from sigma.project_reports import render_report

        report, _ = render_report(export_project_view(str(path)), "txt")
        assert isinstance(report, str)
        assert "At most n new regions" in report
        assert "the pairwise intersection coordinates are distinct" in report.lower()
        assert "Skeptic rationale: At most n−1 crossings" in report
        paper_snapshot, _ = papers._snapshot(str(path))
        paper_artifact = next(
            item for item in paper_snapshot["sources"] if item["kind"] == "artifact"
        )
        assert paper_artifact["data"]["reasoning_steps"][1]["title"] == "At most n new regions"
        assert "Attaining every increment" in json.dumps(paper_snapshot, ensure_ascii=False)
        assert finished["status"] == "ended"
        assert finished["termination_reason_code"] == "research_completed_early"
        assert finished["current_action"] == "Completed · early research conclusion"
        assert "reviews supported stopping" in finished["message"]
        assert "unverified research results" in finished["message"]
        assert finished["outcome"]["assessment"] == "positive"
        assert finished["outcome"]["solution_review"]["claim_scope"] == "conditional"
        assert finished["outcome"]["solution_review"]["claim"].startswith(
            "Conditional on: Lines are distinct straight lines in the Euclidean plane."
        )
        assert finished["outcome"]["label"] == "Positive · solution candidate (unverified)"
        assert finished["artifacts"][0]["coordinator_decision"] == "stop_productive_conclusion"
        assert any(
            event["kind"] == "coordinator.assessment_conflict" for event in finished["events"]
        )
        assert not any(
            event["kind"] == "coordinator.assessment_reconciled" for event in finished["events"]
        )
        assert len(finished["outcome"]["solution_review"]["proof_obligations"]) == 4
        assert (
            finished["outcome"]["solution_review"]["verification_status"] == "convincing_unverified"
        )
        assert finished["outcome"]["solution_review"]["basis_artifact_ids"] == [
            finished["artifacts"][0]["id"]
        ]
        saved_argument = finished["outcome"]["solution_review"]["argument_steps"]
        assert len(saved_argument) == 6
        assert saved_argument[1]["title"] == "At most n new regions"
        assert "at most n pieces" in saved_argument[1]["argument"]
        assert saved_argument[1]["research_artifact_id"] == finished["artifacts"][0]["id"]
        assert saved_argument[1]["review"]["disposition"] == "accepted"
        argument_titles = [item["title"].lower() for item in saved_argument]
        assert any("assumption" in title for title in argument_titles)
        assert any("attain" in title for title in argument_titles)
        assert any("recurrence" in title for title in argument_titles)
        assert all(item["epistemic_status"] == "deduction" for item in saved_argument[1:])
        full_argument = " ".join(item["argument"] for item in saved_argument)
        assert "at most n" in full_argument and "different old region" in full_argument
        assert "R(k)=R(k−1)+k" in full_argument and "R(0)=1" in full_argument
        assert "1+n(n+1)/2" in full_argument
        assert all(item["review"]["disposition"] == "accepted" for item in saved_argument)
        assert any("unverified" in item.lower() for item in finished["outcome"]["caveats"])
        rows = finished["strategy_assessments"]
        assert [row["assessment"] for row in rows] == ["contributed_to_solution", "not_used"]
        assert rows[0]["basis_artifact_ids"] == [finished["artifacts"][0]["id"]]
        assert rows[1]["basis_artifact_ids"] == []

        # An achieved summary with no remaining obligations still cannot
        # override a Skeptic's challenge to one logical proof step.
        incomplete_review = {
            **review,
            "assessment": "continue",
            "stop_reason": "recoverable_objection",
            "response": "The crossing count alone does not justify that each line piece splits a different old region.",
            "objections": [],
            "remaining_obligations": [],
            "next_question": "Review the component-identification step.",
            "objective_status": "achieved",
            "proof_obligations": ["Review the insertion argument."],
            "verification_status": "convincing_unverified",
            "unresolved_objections": [],
            "reasoning_assessments": [
                {
                    **item,
                    "disposition": "challenged",
                    "rationale": "The piece-count bound alone does not show that every piece splits a different old region.",
                    "objection": "The argument must show that the pieces lie in distinct old regions and that each region met in its interior is split into two.",
                }
                if item["step_number"] == 2
                else item
                for item in review["reasoning_assessments"]
            ],
            "strategy_contribution": "productive",
        }
        research_sessions.save_limits(
            str(path),
            {
                "research_rounds": 1,
                "model_calls": 2,
                "session_duration_minutes": 10,
                "output_tokens_per_call": 4000,
                "maximum_estimated_cost_usd": None,
            },
        )
        outputs.extend([proof, incomplete_review])
        incomplete_started = await research_sessions.start_session(
            str(path), strategy.id, str(uuid4()), view.project.id, credential["identity"]
        )
        incomplete = await wait_for(path, incomplete_started["id"])
        assert incomplete["outcome"]["assessment"] == "mixed"
        assert incomplete["outcome"]["solution_review"]["status"] == "partial"
        challenged = incomplete["outcome"]["solution_review"]["argument_steps"][1]
        assert challenged["review"]["disposition"] == "challenged"
        assert "pieces lie in distinct old regions" in challenged["review"]["objection"]
        research_sessions.save_limits(str(path), research_sessions.DEFAULT_LIMITS)

        # Three research rounds can distribute the proof across saved artifacts. The
        research_sessions.save_limits(
            str(path),
            {
                "research_rounds": 3,
                "model_calls": 6,
                "session_duration_minutes": 10,
                "output_tokens_per_call": 4000,
                "maximum_estimated_cost_usd": None,
            },
        )
        # final Skeptic explicitly cites them and closes the review.
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
                    "open_obligations": [
                        "Connect the saved insertion argument and construction to the complete objective."
                    ],
                },
                {
                    **review,
                    "assessment": "stop",
                    "stop_reason": "unresolved",
                    "response": "The ordered saved evidence closes the upper bound, attainment, and boundary obligations. No material objection remains; this is convincing but unverified.",
                    "argument_summary": "The empty arrangement and small values match the formula.",
                    "objections": [],
                    "remaining_obligations": [],
                    "next_question": "",
                    "objective_status": "achieved",
                    "proof_obligations": [
                        "Upper bound via line insertion [cycle 1].",
                        "Attainment via distinct intersections [cycle 2].",
                        "Base case and small values [cycle 3].",
                    ],
                    "verification_status": "convincing_unverified",
                    "unresolved_objections": [],
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
        assert aggregate["artifacts"][-1]["coordinator_decision"] == ("stop_productive_conclusion")
        assert aggregate["outcome"]["assessment"] == "positive"
        assert aggregate["outcome"]["solution_review"]["status"] == "achieved"
        assert (
            "Open obligations remain; inspect the saved artifacts before relying on this result."
            not in aggregate["outcome"]["caveats"]
        )
        assert aggregate["outcome"]["solution_review"]["verification_status"] == (
            "convincing_unverified"
        )
        assert aggregate["strategy_assessments"][0]["assessment"] == "contributed_to_solution"
        assert len(aggregate["outcome"]["solution_review"]["basis_artifact_ids"]) == 3, aggregate[
            "outcome"
        ]["solution_review"]
        aggregate_skeptic_context = json.loads(provider_requests[-1]["input"])
        assert [item["id"] for item in aggregate_skeptic_context["prior_artifacts"]] == [
            item["id"] for item in aggregate["artifacts"][:2]
        ]
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


async def test_answer_free_maximum_regions_prompt(path: Path):
    # Keep the shipped acceptance task answer-free end to end. This goes
    # through normal session creation and request assembly, rather than only
    # checking the source fixture strings.
    title = "Maximum regions formed by straight lines"
    problem = (
        "For each nonnegative integer n, determine the greatest possible number of regions into "
        "which n distinct straight lines divide the Euclidean plane. Establish an exact answer "
        "for all n with a rigorous upper bound and a construction that attains it. State any "
        "geometric assumptions required for the argument."
    )
    strategy_title = "Incremental line insertion"
    strategy_text = (
        "Examine how adding one line changes the connected regions of an arrangement of earlier "
        "lines. Identify what would need to be proved for an upper bound and what separate "
        "evidence would demonstrate attainability. Do not assume that a particular arrangement "
        "or formula is optimal."
    )
    view = initialize_project(
        path,
        title,
        problem,
        research_mode="mathematical",
        difficulty="easy",
    )
    strategy = create_strategy(
        path,
        strategy_title,
        strategy_text,
    ).project.strategies[0]
    research_sessions.save_limits(
        str(path),
        {
            "research_rounds": 1,
            "model_calls": 2,
            "session_duration_minutes": 30,
            "output_tokens_per_call": 4000,
            "maximum_estimated_cost_usd": None,
        },
    )
    credential = {
        "identity": "fixture-account",
        "mode": "api_key",
        "token": "fixture-token",
        "status": "connected",
    }
    config = {"available": True, "model": MODEL, "reasoning_effort": "high"}
    outputs = [investigation(1), skeptic(1, "stop", "productive_conclusion")]
    requests = []

    async def handler(request):
        payload = json.loads(request.content)
        requests.append(
            {
                "role": payload["text"]["format"]["name"],
                "instructions": payload["instructions"],
                "context": json.loads(payload["input"]),
            }
        )
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

    assert finished["status"] == "ended" and finished["artifacts"]
    assert len(requests) == 2
    initial = requests[0]
    assert initial["role"] == "research_investigator"
    context = initial["context"]
    assert context["problem"] == problem == view.project.problem
    assert context["strategy"]["title"] == strategy_title == strategy.title
    assert context["strategy"]["approach"] == strategy_text == strategy.approach
    assert context["prior_artifacts"] == []
    assert context["prior_session_findings"] == []
    assert context["obligation_ledger"] == []
    assert context["prior_session_obligations_omitted"] == 0
    assert context["prior_session_failures"] == []
    manifest_sources = context["context_manifest"]["sources"]
    assert manifest_sources == [
        {
            "category": "project_strategy_snapshot",
            "source_ids": [strategy.id],
            "reason": "bounded portfolio overview for strategy and domain context",
            "representation": "bounded_snapshot",
            "status": "selected",
        }
    ]

    # Normalize whitespace and superscript so harmless formatting changes do
    # not let a known formula or attaining family slip through the audit.
    initial_request = json.dumps(initial, ensure_ascii=False).casefold()
    normalized = "".join(initial_request.split()).replace("²", "^2")
    forbidden = (
        "1+n(n+1)/2",
        "n(n+1)/2",
        "y=kx+k^2",
        "x=-(i+k)",
        "linesl_k",
    )
    assert not any(leak in normalized for leak in forbidden)
    # The old literal-space assertion would miss this formatting variant;
    # the normalized audit must identify both the formula and construction.
    synthetic_leak = "R(n) = 1 + n (n + 1) / 2; L_k: y = k x + k²"
    normalized_synthetic_leak = "".join(synthetic_leak.casefold().split()).replace("²", "^2")
    assert any(leak in normalized_synthetic_leak for leak in forbidden)
    # This is an answer-leakage regression fixture, not evidence that a model
    # can independently solve the problem; the provider is mocked above.


async def test_maximum_regions_false_candidate_is_rejected(path: Path):
    problem = (
        "For each integer n >= 0, determine the maximum number of regions formed by n distinct "
        "straight lines in the plane. State assumptions, derive an upper bound, and give a "
        "construction if you can."
    )
    view = initialize_project(
        path,
        "Maximum Regions · counterexample regression",
        problem,
        research_mode="mathematical",
        difficulty="easy",
    )
    strategy = create_strategy(
        path,
        "Test the insertion estimate",
        "Check small arrangements, then look for a general upper bound and a matching construction.",
    ).project.strategies[0]
    credential = {
        "identity": "fixture-account",
        "mode": "api_key",
        "token": "fixture-token",
        "status": "connected",
    }
    config = {"available": True, "model": MODEL, "reasoning_effort": "high"}
    incorrect = {
        **investigation(1),
        "claim": "The maximum is R(n) = n^2 + 1.",
        "method": (
            "Assume each new line adds 2n regions, so summing gives this quadratic candidate. "
            "This estimate has not been checked against arrangements."
        ),
        "evidence_status": "Unverified candidate; the increment estimate is unsupported.",
        "open_obligations": ["Check the proposed increment against a two-line arrangement."],
    }
    genuine_objection = {
        **skeptic(1, "stop", "decisive_counterexample"),
        "response": (
            "For n=2 the claim predicts five regions, but two distinct lines form at most four "
            "regions: if parallel they form three, and if they intersect they form four. This "
            "contradicts the claimed maximum, so the proposed formula is false."
        ),
        "objections": [
            "At n=2, the claimed value is unattainable; two lines form at most four regions."
        ],
        "remaining_obligations": [],
        "next_question": "Revise the increment estimate against the two-line case.",
        "objective_status": "not_achieved",
        "solution_claim": "The proposed R(n) = n^2 + 1 candidate is false.",
        "argument_summary": "The n=2 case contradicts the candidate's predicted value.",
        "proof_obligations": ["Check all arrangements of two distinct lines."],
        "unresolved_objections": ["The n=2 counterexample refutes the proposed candidate."],
        "supporting_cycles": [1],
        "verification_status": "incomplete",
        "strategy_contribution": "unproductive",
        "contribution_rationale": "The proposed increment estimate fails on the two-line case.",
    }
    outputs = [incorrect, genuine_objection]
    inputs = []

    async def handler(request):
        payload = json.loads(request.content)
        inputs.append(json.loads(payload["input"]))
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

    # The sealed evaluator's counterexample is supplied only as the Skeptic
    # response. Neither the wrong candidate nor its rebuttal is in the initial
    # Investigator context, and no general reference formula is disclosed.
    assert len(inputs) == 2
    initial_context = json.dumps(inputs[0])
    assert "n^2 + 1" not in initial_context
    assert "n(n+1)/2" not in initial_context
    assert inputs[0]["problem"] == problem
    assert inputs[0]["strategy"]["approach"] == strategy.approach

    assert finished["status"] == "ended"
    assert finished["terminal_reason"] == "stop_decisive_counterexample"
    assert finished["artifacts"][0]["coordinator_decision"] == "stop_decisive_counterexample"
    assert finished["artifacts"][0]["objections"] == genuine_objection["objections"]
    assert finished["outcome"]["assessment"] == "negative"
    assert finished["outcome"]["solution_review"]["status"] == "not_achieved"
    assert finished["outcome"]["solution_review"]["unresolved_objections"] == [
        "The n=2 counterexample refutes the proposed candidate."
    ]
    assert finished["strategy_assessments"][0]["assessment"] == "unproductive"
    persisted = research_sessions.get_session(str(path), started["id"])
    assert persisted["outcome"] == finished["outcome"]
    assert persisted["artifacts"][0]["skeptic_response"] == genuine_objection["response"]


async def test_concurrent_strategy_portfolio(path: Path):
    view, first, credential, config = await setup(path)
    second = create_strategy(
        path, "Boundary-first", "Start with degenerate and small boundary cases."
    ).project.strategies[-1]
    third = create_strategy(
        path, "Counterexample search", "Search for assumptions that make the claim fail."
    ).project.strategies[-1]
    limits = research_sessions.get_limits(str(path))
    limits["model_calls"] = 8
    limits = research_sessions.save_limits(str(path), limits)
    state = {"active": 0, "maximum": 0}
    request_contexts = []

    async def handler(request):
        payload = json.loads(request.content)
        context = json.loads(payload["input"])
        request_contexts.append((payload["text"]["format"]["name"], context))
        state["active"] += 1
        state["maximum"] = max(state["maximum"], state["active"])
        try:
            await asyncio.sleep(0.04)
            strategy_name = context["strategy"]["title"]
            cycle = context["cycle"]
            if payload["text"]["format"]["name"] == "research_investigator":
                output = {
                    **investigation(cycle),
                    "claim": f"{strategy_name} claim for branch cycle {cycle}.",
                }
            else:
                output = skeptic(cycle)
            return httpx.Response(200, json=provider_response(output))
        finally:
            state["active"] -= 1

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
            str(path),
            first.id,
            str(uuid4()),
            view.project.id,
            credential["identity"],
            expected_limits=limits,
            strategy_ids=[first.id, second.id, third.id],
        )
        finished = await wait_for(path, started["id"])

    assert finished["status"] == "ended", (
        finished["status"],
        finished["message"],
        finished["calls_used"],
        finished["strategy_runs"],
    )
    expected_strategy_ids = {first.id, second.id, third.id}
    assert finished["strategy_ids"] == [first.id, second.id, third.id]
    assert state["maximum"] == 3, state
    assert state["maximum"] <= 3
    assert finished["calls_used"] == 8
    assert len(finished["artifacts"]) == 4
    assert {item["strategy_id"] for item in finished["artifacts"]} == expected_strategy_ids
    assert {
        item["strategy_id"]
        for item in finished["strategy_assessments"]
        if item["assessment"] != "not_used"
    } == expected_strategy_ids
    assert all(step["status"] == "completed" for step in finished["steps"])
    assert finished.get("current_steps", []) == []
    assert any(step.get("peer_strategy_artifact_ids") for step in finished["steps"])
    assert len(request_contexts) == 8
    assert {context["strategy"]["id"] for _, context in request_contexts} == expected_strategy_ids
    assert finished["portfolio_decision"]["basis_artifact_ids"] == [
        item["id"] for item in finished["artifacts"]
    ]
    assert len(finished["portfolio_decision"]["strategy_actions"]) == 3
    assert finished["portfolio_decision"]["status"] == "model_reported_unverified"


async def test_portfolio_cross_strategy_reviews_ground_synthesis_in_peer_evidence(path: Path):
    view, first, credential, config = await setup(path)
    second = create_strategy(
        path, "Complementary route", "Derive a separate invariant and compare its consequences."
    ).project.strategies[-1]
    project_before = (path / "project.json").read_bytes()
    limits = research_sessions.get_limits(str(path))
    limits.update({"research_rounds": 2, "model_calls": 8})
    limits = research_sessions.save_limits(str(path), limits)
    seen_contexts = []

    async def handler(request):
        payload = json.loads(request.content)
        role = payload["text"]["format"]["name"]
        context = json.loads(payload["input"])
        seen_contexts.append((role, context))
        strategy = context["strategy"]
        cycle = context["cycle"]
        if role == "research_investigator":
            result = investigation(cycle)
            result["claim"] = f"{strategy['title']} finding in cycle {cycle}."
            if cycle == 1:
                result["method"] = (
                    "Derive a branch-local invariant, leaving an explicit comparison question."
                )
            else:
                peers = context["other_strategy_evidence"]
                assert len(peers) == 1
                result["method"] = (
                    "Revised after comparing peer artifact "
                    + peers[0]["artifact_id"]
                    + "; the mechanisms are complementary, not a shared proof."
                )
        else:
            result = skeptic(
                cycle,
                "revise" if cycle == 1 else "stop",
                "recoverable_objection" if cycle == 1 else "productive_conclusion",
            )
            if cycle == 1:
                result["next_question"] = (
                    "Compare this invariant against the other strategy's saved evidence."
                )
            else:
                peers = context["other_strategy_evidence"]
                assert len(peers) == 1
                result["cross_strategy_relations"] = [
                    {
                        "strategy_id": peers[0]["strategy_id"],
                        "artifact_id": peers[0]["artifact_id"],
                        "relation": "complements",
                        "rationale": "The distinct invariant supplies a missing case needed by the peer route.",
                    }
                ]
                result["next_question"] = ""
        return httpx.Response(200, json=provider_response(result))

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
            str(path),
            first.id,
            str(uuid4()),
            view.project.id,
            credential["identity"],
            expected_limits=limits,
            strategy_ids=[first.id, second.id],
        )
        finished = await wait_for(path, started["id"])

    assert finished["status"] == "ended" and finished["calls_used"] == 8
    assert len(finished["artifacts"]) == 4
    assert all(branch["status"] == "ended" for branch in finished["strategy_runs"])
    second_cycle_investigations = [
        context
        for role, context in seen_contexts
        if role == "research_investigator" and context["cycle"] == 2
    ]
    assert len(second_cycle_investigations) == 2
    assert all(
        len(context["other_strategy_evidence"]) == 1 for context in second_cycle_investigations
    )
    second_cycle_skeptics = [
        context
        for role, context in seen_contexts
        if role == "research_skeptic" and context["cycle"] == 2
    ]
    assert len(second_cycle_skeptics) == 2
    assert all(len(context["other_strategy_evidence"]) == 1 for context in second_cycle_skeptics)
    assert all(
        artifact["skeptic_output"]["cross_strategy_relations"][0]["artifact_id"]
        in {item["id"] for item in finished["artifacts"]}
        for artifact in finished["artifacts"]
        if artifact["strategy_cycle"] == 2
    )
    from sigma.session_log import _frames as read_session_log_frames
    from sigma.session_log import log_path as session_log_path

    trace, _ = read_session_log_frames(session_log_path(str(path), view.project.id, finished["id"]))
    assert any(event["type"] == "cross_strategy_artifact_availability" for event in trace)
    peer_requests = [
        event
        for event in trace
        if event["type"] == "provider_request" and event.get("peer_evidence_available")
    ]
    assert peer_requests
    assert all(
        event["peer_evidence_available"] == event["peer_evidence_in_actual_request"]
        for event in peer_requests
    )
    decision = finished["portfolio_decision"]
    assert len(decision["strategy_actions"]) == 2
    assert len(decision["combination_candidates"]) == 1
    combination = decision["combination_candidates"][0]
    assert set(combination["strategy_ids"]) == {first.id, second.id}
    assert combination["status"] == "unverified_candidate_for_human_review"
    assert len(combination["basis_artifact_ids"]) == 4
    assert decision["status"] == "model_reported_unverified"
    assert any("never edit" in item for item in decision["limitations"])
    assert (path / "project.json").read_bytes() == project_before


async def test_peer_finding_changes_target_investigator_after_stop_and_resume(path: Path):
    view, source, credential, config = await setup(path)
    target = create_strategy(
        path, "Real-analysis route", "Derive an invariant for all real line arrangements."
    ).project.strategies[-1]
    limits = research_sessions.get_limits(str(path))
    limits.update({"research_rounds": 3, "model_calls": 10})
    limits = research_sessions.save_limits(str(path), limits)
    preflight_waiting = asyncio.Event()
    preflight_interrupted = False
    observed = []

    async def configuration_gate(*_args, **_kwargs):
        nonlocal preflight_interrupted
        relation_saved = any(
            artifact.get("skeptic_output", {}).get("cross_strategy_relations")
            for record in research_sessions._all(str(path))
            for artifact in record.get("artifacts", [])
        )
        if relation_saved and not preflight_interrupted:
            preflight_interrupted = True
            preflight_waiting.set()
            await asyncio.Event().wait()
        return config

    async def handler(request):
        payload = json.loads(request.content)
        role = payload["text"]["format"]["name"]
        context = json.loads(payload["input"])
        strategy_id = context["strategy"]["id"]
        cycle = context["cycle"]
        observed.append((role, strategy_id, cycle, context))
        if role == "research_investigator":
            result = investigation(cycle)
            if cycle == 2 and strategy_id == source.id:
                result["assumptions"] = ["Coordinates and coefficients are integers"]
                result["method"] = (
                    "A parity calculation shows a contradiction only for integer-coordinate examples."
                )
            if cycle == 3:
                assert (
                    "directly examine its cited source and target artifacts"
                    in payload["instructions"]
                )
                assert (
                    "compare the source and target assumptions and domains"
                    in payload["instructions"]
                )
                assert strategy_id == target.id
                assert len(context["peer_handoffs"]) == 1
                handoff = context["peer_handoffs"][0]
                assert handoff["source_strategy_id"] == source.id
                assert handoff["target_strategy_id"] == target.id
                assert handoff["relation"] == "contradicts"
                assert handoff["source_artifact_id"] in context["question"]
                assert handoff["target_artifact_id"] in context["question"]
                result["method"] = (
                    "Tested the complementary claim in source artifact "
                    f"{handoff['source_artifact_id']} against target artifact "
                    f"{handoff['target_artifact_id']}; this changes the next step to compare "
                    "the two invariant boundaries before extending the target derivation."
                )
            return httpx.Response(200, json=provider_response(result))

        result = skeptic(cycle)
        if cycle == 1:
            result["next_question"] = "Continue the distinct branch-local derivation."
        elif cycle == 2:
            result["next_question"] = "Test the next consequence of this branch's invariant."
            if strategy_id == source.id:
                peer = next(
                    item
                    for item in context["other_strategy_evidence"]
                    if item["strategy_id"] == target.id
                )
                result["cross_strategy_relations"] = [
                    {
                        "strategy_id": target.id,
                        "artifact_id": peer["artifact_id"],
                        "relation": "contradicts",
                        "rationale": "The source route claims a contradiction, though its integer-only assumptions may differ from the target route.",
                    }
                ]
        elif strategy_id == target.id:
            result = skeptic(cycle, "stop", "productive_conclusion")
            if context.get("peer_handoffs"):
                handoff = context["peer_handoffs"][0]
                assert "peer_handoff_reviews" in payload["text"]["format"]["schema"]["properties"]
                result["peer_handoff_reviews"] = [
                    {
                        "handoff_id": handoff["handoff_id"],
                        "disposition": "reject",
                        "assumption_comparison": "The source argument assumes integer coordinates while the target strategy quantifies over all real line arrangements; that domain mismatch blocks transfer.",
                        "rationale": "The claimed contradiction does not apply to the target's broader domain and leaves its approach unrefuted.",
                    }
                ]
        return httpx.Response(200, json=provider_response(result))

    with (
        patch.object(research_sessions, "auth_context", new=AsyncMock(return_value=credential)),
        patch.object(research_sessions, "configuration", new=configuration_gate),
        patch(
            "sigma.research_sessions.httpx.AsyncClient",
            side_effect=lambda **kwargs: REAL_CLIENT(
                transport=httpx.MockTransport(handler), **kwargs
            ),
        ),
    ):
        started = await research_sessions.start_session(
            str(path),
            source.id,
            str(uuid4()),
            view.project.id,
            credential["identity"],
            expected_limits=limits,
            strategy_ids=[source.id, target.id],
        )
        await asyncio.wait_for(preflight_waiting.wait(), 5)
        before_stop = research_sessions.get_session(str(path), started["id"])
        source_artifact = next(
            artifact
            for artifact in before_stop["artifacts"]
            if artifact["strategy_id"] == source.id and artifact["strategy_cycle"] == 2
        )
        target_first_artifact = next(
            artifact
            for artifact in before_stop["artifacts"]
            if artifact["strategy_id"] == target.id and artifact["strategy_cycle"] == 1
        )
        stopped = await research_sessions.control_session(str(path), started["id"], "stop")

        stopped_target = next(
            item for item in stopped["strategy_runs"] if item["strategy_id"] == target.id
        )
        pending = stopped_target["pending_peer_handoffs"]
        assert len(pending) == 1
        assert pending[0]["source_artifact_id"] == source_artifact["id"]
        assert pending[0]["target_artifact_id"] == target_first_artifact["id"]
        assert stopped["calls_used"] == 8

        resumed = await research_sessions.control_session(str(path), started["id"], "resume")
        finished = await wait_for(path, resumed["id"])

    assert finished["status"] == "ended"
    assert finished["calls_used"] == 10
    cycle_three_investigators = [
        item for item in observed if item[0] == "research_investigator" and item[2] == 3
    ]
    assert [
        (role, strategy_id, cycle) for role, strategy_id, cycle, _ in cycle_three_investigators
    ] == [("research_investigator", target.id, 3)]
    target_third = next(
        artifact
        for artifact in finished["artifacts"]
        if artifact["strategy_id"] == target.id and artifact["strategy_cycle"] == 3
    )
    assert "changes the next step" in target_third["investigator_output"]["method"]
    assert target_third["peer_handoffs_prompted"] == pending
    target_third_step = next(
        step
        for step in finished["steps"]
        if step["strategy_id"] == target.id
        and step["role"] == "investigator"
        and step["cycle"] == 3
    )
    assert target_third_step["peer_handoff_artifact_ids"] == [
        source_artifact["id"],
        target_first_artifact["id"],
    ]
    assert target_third_step["peer_handoff_ids"] == [pending[0]["handoff_id"]]
    assert target_third["peer_handoffs_prompted"][0]["handoff_id"] == pending[0]["handoff_id"]
    target_third_skeptic = next(
        item
        for item in observed
        if item[0] == "research_skeptic" and item[1] == target.id and item[2] == 3
    )
    assert [item["handoff_id"] for item in target_third_skeptic[3]["peer_handoffs"]] == [
        item["handoff_id"] for item in pending
    ]
    assert target_third_skeptic[3]["peer_handoffs"][0]["retracted"] is False
    portfolio = finished["portfolio_decision"]
    assert len(portfolio["rejected_transfers"]) == 1
    assert portfolio["rejected_transfers"][0]["source_artifact_id"] == source_artifact["id"]
    assert portfolio["rejected_transfers"][0]["review_artifact_id"] == target_third["id"]
    assert portfolio["conflict_candidates"] == []
    assert (
        target_third["skeptic_output"]["peer_handoff_reviews"][0]["handoff_id"]
        == pending[0]["handoff_id"]
    )


async def test_portfolio_marks_unsuccessful_approach_without_mutating_strategy_pool(path: Path):
    view, first, credential, config = await setup(path)
    second = create_strategy(
        path, "Alternate route", "Try an independent structural decomposition."
    ).project.strategies[-1]
    project_before = (path / "project.json").read_bytes()
    limits = research_sessions.get_limits(str(path))
    limits["model_calls"] = 6
    limits = research_sessions.save_limits(str(path), limits)

    async def handler(request):
        payload = json.loads(request.content)
        context = json.loads(payload["input"])
        role = payload["text"]["format"]["name"]
        strategy_id = context["strategy"]["id"]
        cycle = context["cycle"]
        if role == "research_investigator":
            output = investigation(cycle)
            output["claim"] = f"Candidate claim for {context['strategy']['title']}."
            if strategy_id == first.id:
                output["open_obligations"] = []
        elif strategy_id == first.id:
            output = skeptic(cycle, "stop", "no_progress")
            output["next_question"] = ""
            output["objections"] = ["The proposed invariant does not control the boundary case."]
            output["remaining_obligations"] = []
            output["strategy_contribution"] = "unproductive"
            output["contribution_rationale"] = "This route did not produce a useful consequence."
        else:
            output = skeptic(
                cycle,
                "stop" if cycle == 2 else "continue",
                "productive_conclusion" if cycle == 2 else "recoverable_objection",
            )
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
            str(path),
            first.id,
            str(uuid4()),
            view.project.id,
            credential["identity"],
            expected_limits=limits,
            strategy_ids=[first.id, second.id],
        )
        finished = await wait_for(path, started["id"])

    assert finished["status"] == "ended" and finished["calls_used"] == 6
    branches = {item["strategy_id"]: item for item in finished["strategy_runs"]}
    assert branches[first.id]["status"] == "ended"
    assert branches[first.id]["last_decision"] == "stop_no_progress"
    actions = {
        item["strategy_id"]: item for item in finished["portfolio_decision"]["strategy_actions"]
    }
    assert actions[first.id]["action"] == "abandon_for_session"
    assert "no concrete next step" in actions[first.id]["rationale"]
    assert actions[first.id]["basis_artifact_ids"]
    assert branches[second.id]["artifacts"]
    assert (path / "project.json").read_bytes() == project_before
    persisted = research_sessions.inspect_project(str(path)).project
    assert all(strategy.enabled for strategy in persisted.strategies)


async def test_ten_strategy_portfolio_respects_concurrency_and_budget(path: Path):
    view, first, credential, config = await setup(path)
    strategies = [first]
    for index in range(1, 10):
        strategies.append(
            create_strategy(
                path,
                f"Independent route {index}",
                f"Use a distinct route and explicitly test boundary {index}.",
            ).project.strategies[-1]
        )
    limits = research_sessions.get_limits(str(path))
    limits["model_calls"] = 20
    limits = research_sessions.save_limits(str(path), limits)
    state = {"active": 0, "maximum": 0}
    first_response_gate = asyncio.Event()
    delays = {
        strategy.id: (len(strategies) - index) * 0.005 for index, strategy in enumerate(strategies)
    }
    completion_order = []
    started_at = time.perf_counter()

    async def handler(request):
        payload = json.loads(request.content)
        context = json.loads(payload["input"])
        # Portfolio provider I/O must not own unrelated process-global gates.
        # Per-session state locks and the session's semaphore enforce the bounds.
        assert not any(
            gate.locked()
            for gate in (proposals._gate, agentic._gate, text_views._gate, research_sessions._gate)
        )
        state["active"] += 1
        state["maximum"] = max(state["maximum"], state["active"])
        try:
            await asyncio.sleep(delays[context["strategy"]["id"]])
            role = payload["text"]["format"]["name"]
            output = (
                investigation(context["cycle"])
                if role == "research_investigator"
                else skeptic(context["cycle"])
            )
            if context["strategy"]["id"] == first.id and role == "research_investigator":
                await first_response_gate.wait()
            completion_order.append((context["strategy"]["id"], role))
            if context["strategy"]["id"] != first.id:
                first_response_gate.set()
            return httpx.Response(200, json=provider_response(output))
        finally:
            state["active"] -= 1

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
            str(path),
            first.id,
            str(uuid4()),
            view.project.id,
            credential["identity"],
            expected_limits=limits,
            strategy_ids=[strategy.id for strategy in strategies],
        )
        finished = await wait_for(path, started["id"])

    expected_ids = {strategy.id for strategy in strategies}
    assert finished["status"] == "ended"
    assert finished["calls_used"] == 20
    assert len(finished["steps"]) == 20
    assert len(finished["artifacts"]) == 10
    assert {artifact["strategy_id"] for artifact in finished["artifacts"]} == expected_ids
    assert all(branch["status"] == "ended" for branch in finished["strategy_runs"])
    assert state["maximum"] == 3
    assert state["maximum"] <= 3
    assert not any(
        gate.locked()
        for gate in (proposals._gate, agentic._gate, text_views._gate, research_sessions._gate)
    )
    assert completion_order[0][0] != first.id, completion_order
    print(
        "PASS 10-strategy load: "
        f"max provider concurrency {state['maximum']}, 20/20 calls, "
        f"10 artifacts, out-of-order responses, {time.perf_counter() - started_at:.3f}s"
    )


async def test_forked_strategy_followup_preserves_parent_comparison(path: Path):
    view, parent, credential, config = await setup(path)
    limits = research_sessions.get_limits(str(path))
    limits.update(research_rounds=1, model_calls=2)
    research_sessions.save_limits(str(path), limits)
    first_outputs = [investigation(1), skeptic(1, "stop", "productive_conclusion")]

    async def first_handler(_request):
        return httpx.Response(200, json=provider_response(first_outputs.pop(0)))

    with (
        patch.object(research_sessions, "auth_context", new=AsyncMock(return_value=credential)),
        patch.object(research_sessions, "configuration", new=AsyncMock(return_value=config)),
        patch(
            "sigma.research_sessions.httpx.AsyncClient",
            side_effect=lambda **kwargs: REAL_CLIENT(
                transport=httpx.MockTransport(first_handler), **kwargs
            ),
        ),
    ):
        first_start = await research_sessions.start_session(
            str(path), parent.id, str(uuid4()), view.project.id, credential["identity"]
        )
        first_session = await wait_for(path, first_start["id"])

    assert len(first_session["artifacts"]) == 1
    source = first_session["artifacts"][0]
    fork = create_strategy(
        path,
        "Evidence-based revision",
        "Fork rationale: revise parent strategy "
        f"{parent.id} after Session #{first_session['session_number']}. "
        f"Saved finding: {source['claim_or_question']} "
        f"Objections: {', '.join(source['objections'])}. "
        f"Open obligations: {', '.join(source['open_obligations'])}. "
        f"Next question: {source['next_question']}",
    ).project.strategies[-1]
    assert parent.approach == "Derive a recurrence and check its boundary cases."
    assert parent.id in fork.approach and source["claim_or_question"] in fork.approach
    followup_contexts = []

    async def followup_handler(request):
        payload = json.loads(request.content)
        context = json.loads(payload["input"])
        followup_contexts.append(context)
        role = payload["text"]["format"]["name"]
        if role == "research_investigator":
            result = {
                **investigation(context["cycle"]),
                "claim": f"{context['strategy']['title']} makes a distinct claim.",
            }
        else:
            result = skeptic(context["cycle"], "stop", "productive_conclusion")
        return httpx.Response(200, json=provider_response(result))

    limits = research_sessions.get_limits(str(path))
    limits.update(research_rounds=1, model_calls=4)
    research_sessions.save_limits(str(path), limits)
    with (
        patch.object(research_sessions, "auth_context", new=AsyncMock(return_value=credential)),
        patch.object(research_sessions, "configuration", new=AsyncMock(return_value=config)),
        patch(
            "sigma.research_sessions.httpx.AsyncClient",
            side_effect=lambda **kwargs: REAL_CLIENT(
                transport=httpx.MockTransport(followup_handler), **kwargs
            ),
        ),
    ):
        followup_start = await research_sessions.start_session(
            str(path),
            parent.id,
            str(uuid4()),
            view.project.id,
            credential["identity"],
            expected_limits=limits,
            strategy_ids=[parent.id, fork.id],
        )
        followup = await wait_for(path, followup_start["id"])

    assert followup["status"] == "ended"
    assert followup["strategy_ids"] == [parent.id, fork.id]
    assert len(followup["artifacts"]) == 2
    assert {artifact["strategy_id"] for artifact in followup["artifacts"]} == {
        parent.id,
        fork.id,
    }
    assert len(followup["strategy_assessments"]) == 2
    assert all(item["assessment"] == "productive" for item in followup["strategy_assessments"])
    assert all(context["prior_session_findings"] for context in followup_contexts)
    assert {item["strategy_id"] for item in followup["strategy_assessments"]} == {
        parent.id,
        fork.id,
    }


async def test_stop_concurrent_portfolio_preserves_completed_boundary(path: Path):
    view, first, credential, config = await setup(path)
    test_limits = research_sessions.get_limits(str(path))
    test_limits["model_calls"] = 6
    research_sessions.save_limits(str(path), test_limits)
    second = create_strategy(path, "Second line", "Try a distinct derivation.").project.strategies[
        -1
    ]
    third = create_strategy(path, "Third line", "Search for a counterexample.").project.strategies[
        -1
    ]
    entered = asyncio.Event()
    request_state = {"count": 0, "active": 0, "maximum": 0}
    project_before = (path / "project.json").read_bytes()

    async def handler(request):
        payload = json.loads(request.content)
        request_state["count"] += 1
        request_state["active"] += 1
        request_state["maximum"] = max(request_state["maximum"], request_state["active"])
        entered.set()
        try:
            context = json.loads(payload["input"])
            role = payload["text"]["format"]["name"]
            if (
                request_state["count"] <= 3
                and context["strategy"]["id"] != first.id
                and role == "research_investigator"
            ):
                await asyncio.Event().wait()
            elif request_state["count"] <= 3:
                await asyncio.sleep(0.03)
            cycle = context["cycle"]
            output = investigation(cycle) if role == "research_investigator" else skeptic(cycle)
            return httpx.Response(200, json=provider_response(output))
        finally:
            request_state["active"] -= 1

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
            str(path),
            first.id,
            str(uuid4()),
            view.project.id,
            credential["identity"],
            strategy_ids=[first.id, second.id, third.id],
        )
        for _ in range(100):
            if request_state["count"] >= 3 and request_state["active"] == 2:
                break
            await asyncio.sleep(0.01)
        assert request_state["count"] == 3
        assert request_state["active"] == 2
        assert request_state["maximum"] == 3
        stopped = await research_sessions.control_session(str(path), started["id"], "stop")
        assert stopped["status"] == "stopped"
        assert request_state["count"] == 3
        assert request_state["active"] == 0
        interrupted = research_sessions.get_session(str(path), started["id"])
        assert interrupted["artifacts"] == []
        assert interrupted["calls_used"] == 3
        assert len(interrupted["steps"]) == 3
        assert sum(step["status"] == "completed" for step in interrupted["steps"]) == 1
        assert sum(step["status"] == "interrupted" for step in interrupted["steps"]) == 2
        completed = next(step for step in interrupted["steps"] if step["status"] == "completed")
        assert completed["output"]["claim"]
        assert interrupted["current_steps"] == []
        resumed = await research_sessions.control_session(str(path), started["id"], "resume")
        finished = await wait_for(path, resumed["id"])

    assert finished["status"] == "ended", (
        finished["status"],
        finished["message"],
        finished["calls_used"],
        finished["strategy_runs"],
    )
    assert finished["calls_used"] == 6
    assert request_state["count"] == 6
    assert len(finished["artifacts"]) == 2
    assert any(step["status"] == "completed" and step.get("output") for step in finished["steps"])
    assert all(branch["status"] == "ended" for branch in finished["strategy_runs"])
    assert finished["portfolio_decision"]["basis_artifact_ids"] == [
        artifact["id"] for artifact in finished["artifacts"]
    ]
    assert len(finished["portfolio_decision"]["strategy_actions"]) == 3
    assert len({artifact["id"] for artifact in finished["artifacts"]}) == 2
    assert (path / "project.json").read_bytes() == project_before


async def test_stop_reconciles_queued_portfolio_branches(path: Path):
    view, first, credential, config = await setup(path)
    additional = [
        create_strategy(
            path, f"Approach {index}", "Try an independent derivation."
        ).project.strategies[-1]
        for index in range(2, 5)
    ]
    entered = asyncio.Event()
    state = {"count": 0, "active": 0}
    limits = research_sessions.get_limits(str(path))
    limits["model_calls"] = 8
    limits = research_sessions.save_limits(str(path), limits)

    async def handler(_request):
        state["count"] += 1
        state["active"] += 1
        entered.set()
        try:
            await asyncio.Event().wait()
        finally:
            state["active"] -= 1
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
            str(path),
            first.id,
            str(uuid4()),
            view.project.id,
            credential["identity"],
            expected_limits=limits,
            strategy_ids=[first.id, *(item.id for item in additional)],
        )
        await asyncio.wait_for(entered.wait(), 2)
        for _ in range(100):
            if state["count"] == 3:
                break
            await asyncio.sleep(0.01)
        assert state["count"] == state["active"] == 3
        stopped = await research_sessions.control_session(str(path), started["id"], "stop")

    assert stopped["status"] == "stopped"
    assert state["active"] == 0
    assert len(stopped["strategy_runs"]) == 4
    assert all(branch["status"] == "stopped" for branch in stopped["strategy_runs"]), stopped[
        "strategy_runs"
    ]
    assert stopped["portfolio_decision"]["active_strategies"] == []
    assert all(
        action["action"] not in {"continue", "revise"}
        for action in stopped["portfolio_decision"]["strategy_actions"]
    )


async def test_portfolio_preflight_failure_terminates_instead_of_spinning(path: Path):
    view, strategy, credential, config = await setup(path)

    with (
        patch.object(research_sessions, "auth_context", new=AsyncMock(return_value=credential)),
        patch.object(
            research_sessions,
            "configuration",
            new=AsyncMock(
                side_effect=[config, ProjectError("temporary configuration service failure")]
            ),
        ),
    ):
        started = await research_sessions.start_session(
            str(path), strategy.id, str(uuid4()), view.project.id, credential["identity"]
        )
        finished = await wait_for(path, started["id"])

    assert finished["status"] == "paused"
    assert finished["calls_used"] == 0
    assert all(branch["status"] == "paused" for branch in finished["strategy_runs"])
    assert "configuration service failure" in finished["message"].lower()
    failures = [event for event in finished["events"] if event["kind"] == "call.preflight_failed"]
    assert len(failures) == 1
    assert failures[0]["strategy_id"] == strategy.id
    assert failures[0]["strategy_title"] == strategy.title
    assert failures[0]["role"] == "investigator"
    assert failures[0]["failure_stage"] == "model_configuration"
    assert failures[0]["failure_kind"] == "preflight_error"
    assert failures[0]["dispatched"] is False


async def test_portfolio_audits_mixed_preflight_failure_and_sibling_success(path: Path):
    view, first, credential, config = await setup(path)
    second = create_strategy(
        path, "Independent check", "Try an independent derivation and boundary check."
    ).project.strategies[-1]
    snapshot_calls = 0
    real_snapshot = research_sessions._snapshot

    def fail_first_worker_snapshot(target):
        nonlocal snapshot_calls
        snapshot_calls += 1
        # start_session takes the initial snapshot and revalidates after
        # async provider preflight. The first worker snapshot then fails.
        if snapshot_calls == 3:
            raise ProjectError("temporary project snapshot service failure")
        return real_snapshot(target)

    async def handler(_request):
        return httpx.Response(200, json=provider_response(investigation(1)))

    with (
        patch.object(research_sessions, "auth_context", new=AsyncMock(return_value=credential)),
        patch.object(research_sessions, "configuration", new=AsyncMock(return_value=config)),
        patch.object(research_sessions, "_snapshot", side_effect=fail_first_worker_snapshot),
        patch(
            "sigma.research_sessions.httpx.AsyncClient",
            side_effect=lambda **kwargs: REAL_CLIENT(
                transport=httpx.MockTransport(handler), **kwargs
            ),
        ),
    ):
        started = await research_sessions.start_session(
            str(path),
            first.id,
            str(uuid4()),
            view.project.id,
            credential["identity"],
            strategy_ids=[first.id, second.id],
        )
        finished = await wait_for(path, started["id"])

    assert finished["status"] == "failed"
    assert finished["calls_used"] == 1
    failed_events = [
        event for event in finished["events"] if event["kind"] == "call.preflight_failed"
    ]
    assert len(failed_events) == 1
    failure = failed_events[0]
    expected_titles = {first.id: first.title, second.id: second.title}
    assert failure["strategy_id"] in expected_titles
    assert failure["strategy_title"] == expected_titles[failure["strategy_id"]]
    assert failure["role"] == "investigator"
    assert failure["failure_stage"] == "project_snapshot"
    assert failure["failure_kind"] == "preflight_error"
    assert failure["dispatched"] is False
    assert "temporary project snapshot service failure" not in failure["message"]
    completed_steps = [step for step in finished["steps"] if step["status"] == "completed"]
    assert len(completed_steps) == 1
    assert completed_steps[0]["strategy_id"] in expected_titles
    assert completed_steps[0]["strategy_id"] != failure["strategy_id"]
    assert completed_steps[0]["role"] == "investigator"
    assert completed_steps[0]["output"]["claim"].startswith("Claim 1:")
    assert all(step.get("strategy_id") != failure["strategy_id"] for step in finished["steps"])


async def test_portfolio_preflight_timeout_pauses_without_spending_calls_and_recovers(
    path: Path,
):
    view, strategy, credential, config = await setup(path)
    limits = research_sessions.get_limits(str(path))
    limits.update(research_rounds=1, model_calls=2)
    research_sessions.save_limits(str(path), limits)
    config_calls = 0

    async def configuration_with_one_timeout(*_args, **_kwargs):
        nonlocal config_calls
        config_calls += 1
        if config_calls == 2:
            await asyncio.Event().wait()
        return config

    async def handler(request):
        payload = json.loads(request.content)
        context = json.loads(payload["input"])
        role = payload["text"]["format"]["name"]
        output = (
            investigation(context["cycle"])
            if role == "research_investigator"
            else skeptic(context["cycle"], "stop", "productive_conclusion")
        )
        return httpx.Response(200, json=provider_response(output))

    with (
        patch.object(research_sessions, "auth_context", new=AsyncMock(return_value=credential)),
        patch.object(research_sessions, "configuration", new=configuration_with_one_timeout),
        patch.object(research_sessions, "PREFLIGHT_TIMEOUT", 0.01),
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
        assert paused["status"] == "paused"
        assert paused["calls_used"] == 0
        assert "timed out" in paused["message"].lower()
        assert all(branch["status"] == "paused" for branch in paused["strategy_runs"])
        failure_events = [
            event for event in paused["events"] if event["kind"] == "call.preflight_failed"
        ]
        assert len(failure_events) == 1
        assert failure_events[0]["strategy_id"] == strategy.id
        assert failure_events[0]["role"] == "investigator"
        assert failure_events[0]["failure_stage"] == "model_configuration"
        assert failure_events[0]["failure_kind"] == "timeout"
        assert failure_events[0]["dispatched"] is False

        resumed = await research_sessions.control_session(str(path), started["id"], "resume")
        finished = await wait_for(path, resumed["id"])

    assert finished["status"] == "ended"
    assert finished["calls_used"] == 2
    assert len(finished["artifacts"]) == 1
    assert finished["strategy_runs"][0]["status"] == "ended"


async def test_resume_limits_reconcile_portfolio_terminal_state(path: Path):
    for limit_kind in ("deadline", "calls"):
        case_path = path.with_name(f"{limit_kind}.sigma")
        view, strategy, credential, config = await setup(case_path)
        entered = asyncio.Event()

        async def handler(_request, entered=entered):
            entered.set()
            await asyncio.Event().wait()
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
                str(case_path), strategy.id, str(uuid4()), view.project.id, credential["identity"]
            )
            await asyncio.wait_for(entered.wait(), 2)
            await research_sessions.control_session(str(case_path), started["id"], "pause")

        record = research_sessions._read(str(case_path), started["id"])
        record.pop("stopped_at", None)
        record["status"] = "paused"
        if limit_kind == "deadline":
            record["deadline_at"] = "2000-01-01T00:00:00+00:00"
        else:
            record["deadline_at"] = "2999-01-01T00:00:00+00:00"
            record["calls_used"] = record["call_limit"]
        # Simulate a stale/older snapshot whose coordinator still advertises active work.
        record["portfolio_decision"] = research_sessions._portfolio_decision(record)
        for branch in record["strategy_runs"]:
            branch["status"] = "paused"
        research_sessions._save(str(case_path), record)

        with (
            patch.object(research_sessions, "auth_context", new=AsyncMock(return_value=credential)),
            patch.object(research_sessions, "configuration", new=AsyncMock(return_value=config)),
        ):
            ended = await research_sessions.control_session(str(case_path), started["id"], "resume")
        assert ended["status"] == "ended", (limit_kind, ended["status"], ended["message"])
        assert all(branch["status"] == "ended" for branch in ended["strategy_runs"])
        assert ended["portfolio_decision"]["active_strategies"] == []
        assert all(
            action["action"] not in {"continue", "revise"}
            for action in ended["portfolio_decision"]["strategy_actions"]
        )


async def test_portfolio_isolates_one_strategy_provider_failure(path: Path):
    view, first, credential, config = await setup(path)
    second = create_strategy(
        path, "Independent approach", "Use a different derivation."
    ).project.strategies[-1]
    roles = []

    async def handler(request):
        payload = json.loads(request.content)
        context = json.loads(payload["input"])
        roles.append((context["strategy"]["id"], payload["text"]["format"]["name"]))
        if context["strategy"]["id"] == first.id:
            return httpx.Response(400, json={"error": {"message": "fixture request rejected"}})
        role = payload["text"]["format"]["name"]
        cycle = context["cycle"]
        output = investigation(cycle) if role == "research_investigator" else skeptic(cycle)
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
            str(path),
            first.id,
            str(uuid4()),
            view.project.id,
            credential["identity"],
            strategy_ids=[first.id, second.id],
        )
        finished = await wait_for(path, started["id"])

    assert finished["status"] == "ended"
    branches = {item["strategy_id"]: item for item in finished["strategy_runs"]}
    assert branches[first.id]["status"] == "failed"
    assert branches[first.id]["reason"]
    rejected = next(step for step in finished["steps"] if step["strategy_id"] == first.id)
    assert rejected["failure_kind"] == "provider_rejected"
    assert rejected["provider_http_status"] == 400
    metrics = {
        item["label"]: item["value"] for item in finished["outcome"]["metrics"]["operational"]
    }
    assert "1 rejected" in metrics["Agent turns by status"]
    assert "1 provider failure(s) (1 rejected" in metrics["Provider failures / retries"]
    assert branches[second.id]["status"] == "ended"
    assert finished["artifacts"]
    assert {item["strategy_id"] for item in finished["artifacts"]} == {second.id}
    assert any(
        strategy_id == first.id and role == "research_investigator" for strategy_id, role in roles
    )
    assert all(strategy_id == second.id for strategy_id, _ in roles if strategy_id != first.id)


async def test_portfolio_stops_after_chatgpt_usage_limit(
    path: Path, *, streamed: bool = False, sse_error_event: bool = False
):
    view, first, credential, config = await setup(path)
    credential["mode"] = "chatgpt"
    second = create_strategy(
        path, "Independent approach", "Use a different derivation."
    ).project.strategies[-1]
    provider_calls = []

    async def handler(request):
        payload = json.loads(request.content)
        context = json.loads(payload["input"][0]["content"])
        provider_calls.append(context["strategy"]["id"])
        if streamed:
            events = [
                {"type": "response.created", "sequence_number": 0, "response": {"id": "limited-1"}},
                (
                    {
                        "type": "error",
                        "sequence_number": 1,
                        "error": {"code": "subscription_sharing_usage_limit_exceeded"},
                    }
                    if sse_error_event
                    else {
                        "type": "response.failed",
                        "sequence_number": 1,
                        "response": {
                            "id": "limited-1",
                            "status": "failed",
                            "error": {"code": "subscription_sharing_usage_limit_exceeded"},
                        },
                    }
                ),
            ]
            body = "".join(
                f"event: {event['type']}\ndata: {json.dumps(event)}\n\n" for event in events
            )
            return httpx.Response(200, headers={"content-type": "text/event-stream"}, text=body)
        return httpx.Response(
            429,
            json={"error": {"code": "subscription_sharing_usage_limit_exceeded"}},
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
        patch.object(research_sessions, "_portfolio_call_concurrency", return_value=1),
    ):
        started = await research_sessions.start_session(
            str(path),
            first.id,
            str(uuid4()),
            view.project.id,
            credential["identity"],
            strategy_ids=[first.id, second.id],
        )
        finished = await wait_for(path, started["id"])

    assert finished["status"] == "ended"
    assert len(provider_calls) == 1
    assert provider_calls == [first.id]
    assert (
        "ChatGPT rejected a request because its plan or app usage limit was reached"
        in finished["message"]
    )
    branches = {branch["strategy_id"]: branch for branch in finished["strategy_runs"]}
    assert branches[first.id]["status"] == "failed"
    assert branches[second.id]["status"] == "ended"
    assert "Not started because ChatGPT rejected a request" in branches[second.id]["reason"]
    limited = next(step for step in finished["steps"] if step["status"] == "failed")
    assert limited["failure_kind"] == "provider_limited"
    assert limited["provider_http_status"] == (200 if streamed else 429)
    assert limited["provider_error_code"] == "subscription_sharing_usage_limit_exceeded"
    metrics = {
        item["label"]: item["value"] for item in finished["outcome"]["metrics"]["operational"]
    }
    assert "1 rejected" in metrics["Agent turns by status"]
    assert "subscription_sharing_usage_limit_exceeded" in limited["failure_message"]
    assert "separate from SIGMA's sponsored-dollar allowance" in limited["failure_message"]
    if streamed:
        assert limited["provider_response_channel"] == "stream"
        assert limited["provider_stream_event"] == (
            "error" if sse_error_event else "response.failed"
        )
        assert "HTTP transport 200" in limited["failure_message"]
        assert "HTTP 400" not in limited["failure_message"]
        assert "HTTP 400" not in finished["message"]
    else:
        assert limited["provider_response_channel"] == "http"
        assert limited.get("provider_stream_event") is None
        assert "HTTP 429" in limited["failure_message"]
    assert finished["calls_used"] == 1


async def test_portfolio_timeout_is_not_misclassified_as_strategy_failure(path: Path):
    view, first, credential, config = await setup(path)
    second = create_strategy(
        path, "Independent approach", "Use a different derivation."
    ).project.strategies[-1]

    async def handler(request):
        payload = json.loads(request.content)
        context = json.loads(payload["input"])
        if context["strategy"]["id"] == first.id:
            await asyncio.sleep(0.1)
        role = payload["text"]["format"]["name"]
        cycle = context["cycle"]
        output = investigation(cycle) if role == "research_investigator" else skeptic(cycle)
        return httpx.Response(200, json=provider_response(output))

    with (
        patch.object(research_sessions, "auth_context", new=AsyncMock(return_value=credential)),
        patch.object(research_sessions, "configuration", new=AsyncMock(return_value=config)),
        patch.object(research_sessions, "CALL_TIMEOUT", 0.01),
        patch(
            "sigma.research_sessions.httpx.AsyncClient",
            side_effect=lambda **kwargs: REAL_CLIENT(
                transport=httpx.MockTransport(handler), **kwargs
            ),
        ),
    ):
        started = await research_sessions.start_session(
            str(path),
            first.id,
            str(uuid4()),
            view.project.id,
            credential["identity"],
            strategy_ids=[first.id, second.id],
        )
        finished = await wait_for(path, started["id"])

    branches = {item["strategy_id"]: item for item in finished["strategy_runs"]}
    actions = {
        item["strategy_id"]: item for item in finished["portfolio_decision"]["strategy_actions"]
    }
    failed_steps = [step for step in finished["steps"] if step["strategy_id"] == first.id]
    assert branches[first.id]["status"] == "failed"
    assert "timed out" in branches[first.id]["reason"]
    assert failed_steps[0]["status"] == "failed"
    assert failed_steps[0]["failure_kind"] == "timeout"
    assert failed_steps[0]["timeout_seconds"] == 0.01
    assert "remote processing may still complete" in failed_steps[0]["failure_message"].lower()
    assert failed_steps[0].get("output") is None
    assert branches[second.id]["status"] == "ended"
    assert branches[second.id]["artifacts"]
    assert actions[first.id]["action"] == "hold_after_failure"
    assert "not evidence" in actions[first.id]["rationale"]
    assert actions[second.id]["action"] not in {"continue", "revise"}, actions[second.id]
    assert finished["status"] == "ended"
    timeout_metrics = {
        item["label"]: item["value"] for item in finished["outcome"]["metrics"]["operational"]
    }
    assert "1 timed out" in timeout_metrics["Agent turns by status"]
    assert "1 timed out" in timeout_metrics["Provider failures / retries"]


async def test_portfolio_rejects_fabricated_cross_strategy_references(path: Path):
    view, first, credential, config = await setup(path)
    second = create_strategy(
        path, "Peer route", "Try a different proof invariant."
    ).project.strategies[-1]

    async def handler(request):
        payload = json.loads(request.content)
        context = json.loads(payload["input"])
        role = payload["text"]["format"]["name"]
        output = (
            investigation(context["cycle"])
            if role == "research_investigator"
            else skeptic(context["cycle"])
        )
        if role == "research_skeptic" and context["strategy"]["id"] == first.id:
            output["cross_strategy_relations"] = [
                {
                    "strategy_id": second.id,
                    "artifact_id": "fabricated-peer-artifact",
                    "relation": "complements",
                    "rationale": "This fabricated peer citation should be rejected.",
                }
            ]
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
            str(path),
            first.id,
            str(uuid4()),
            view.project.id,
            credential["identity"],
            strategy_ids=[first.id, second.id],
        )
        finished = await wait_for(path, started["id"])

    branches = {item["strategy_id"]: item for item in finished["strategy_runs"]}
    assert finished["status"] == "ended"
    assert branches[first.id]["status"] == "failed"
    assert "reference not present" in branches[first.id]["reason"]
    assert branches[first.id]["artifacts"] == []
    assert branches[second.id]["status"] == "ended"
    assert branches[second.id]["artifacts"]
    assert finished["portfolio_decision"]["cross_strategy_reviews"] == []


def test_portfolio_requires_reciprocal_complement_and_surfaces_conflicts():
    first_id, second_id = str(uuid4()), str(uuid4())
    first_artifact, second_artifact = str(uuid4()), str(uuid4())
    record = {
        "artifacts": [
            {
                "id": first_artifact,
                "strategy_id": first_id,
                "skeptic_output": {
                    "cross_strategy_relations": [
                        {
                            "strategy_id": second_id,
                            "artifact_id": second_artifact,
                            "relation": "complements",
                            "rationale": "This route may supply an independent missing lemma.",
                        }
                    ]
                },
            },
            {"id": second_artifact, "strategy_id": second_id, "skeptic_output": {}},
        ],
        "strategy_runs": [
            {
                "strategy_id": first_id,
                "strategy_title": "First route",
                "status": "running",
                "artifacts": [first_artifact],
            },
            {
                "strategy_id": second_id,
                "strategy_title": "Second route",
                "status": "running",
                "artifacts": [second_artifact],
            },
        ],
    }
    decision = research_sessions._portfolio_decision(record)
    assert decision["combination_candidates"] == []

    record["artifacts"][0]["skeptic_output"]["cross_strategy_relations"][0]["relation"] = (
        "contradicts"
    )
    decision = research_sessions._portfolio_decision(record)
    assert len(decision["conflict_candidates"]) == 1
    assert decision["strategy_actions"][0]["action"] == "resolve_cross_strategy_conflict"
    assert decision["strategy_actions"][1]["action"] == "resolve_cross_strategy_conflict"


def test_peer_handoff_noop_and_domain_mismatch_controls():
    source_id, target_id = "source-strategy", "target-strategy"
    source_artifact_id, target_artifact_id = "source-evidence", "target-evidence"
    source_branch = {
        "strategy_id": source_id,
        "strategy_title": "Integer route",
        "status": "queued",
        "artifacts": [source_artifact_id],
    }
    target_branch: dict[str, Any] = {
        "strategy_id": target_id,
        "strategy_title": "Real-analysis route",
        "status": "queued",
        "current_question": "Continue the real-domain argument.",
    }
    source_artifact = {
        "id": source_artifact_id,
        "strategy_id": source_id,
        "strategy_title": "Integer route",
        "sequence": 1,
        "skeptic_output": {
            "cross_strategy_relations": [
                {
                    "strategy_id": target_id,
                    "artifact_id": target_artifact_id,
                    "relation": "unrelated",
                    "rationale": "The vocabulary overlaps but no shared claim is identified.",
                }
            ]
        },
    }
    target_artifact = {
        "id": target_artifact_id,
        "strategy_id": target_id,
        "strategy_title": "Real-analysis route",
        "sequence": 2,
        "claim_or_question": "The target argument assumes x is real and positive.",
        "skeptic_output": {"cross_strategy_relations": []},
    }
    target_branch["artifacts"] = [target_artifact_id]
    record = {
        "strategy_runs": [source_branch, target_branch],
        "artifacts": [source_artifact, target_artifact],
    }

    research_sessions._queue_peer_handoffs(record, source_branch, source_artifact)
    assert "pending_peer_handoffs" not in target_branch
    assert target_branch["current_question"] == "Continue the real-domain argument."

    source_artifact["skeptic_output"]["cross_strategy_relations"] = [
        {
            "strategy_id": target_id,
            "artifact_id": target_artifact_id,
            "relation": "contradicts",
            "rationale": "This integer-only example may conflict, but the target states x is real and positive.",
        }
    ]
    research_sessions._queue_peer_handoffs(record, source_branch, source_artifact)
    handoff = target_branch["pending_peer_handoffs"][0]
    assert handoff["source_artifact_id"] == source_artifact_id
    assert handoff["target_artifact_id"] == target_artifact_id
    assert "assumptions and domains match" in target_branch["current_question"]
    # A reported contradiction queues a scoped challenge; it never declares the
    # target branch refuted or changes its saved strategy state automatically.
    assert target_branch["status"] == "queued"

    retraction = {
        "id": "source-retraction",
        "strategy_id": source_id,
        "sequence": 3,
        "skeptic_output": {
            "cross_strategy_relations": [],
            "retracted_cross_strategy_source_artifact_ids": [source_artifact_id],
        },
    }
    target_branch["active_peer_handoffs"] = [handoff]
    record["artifacts"].append(retraction)
    research_sessions._retract_peer_handoffs(record, source_branch, retraction)
    assert "pending_peer_handoffs" not in target_branch
    assert target_branch["current_question"] == "Continue the real-domain argument."
    assert target_branch["status"] == "queued"
    assert record["artifacts"][0]["skeptic_output"]["cross_strategy_relations"]
    record.update({"id": str(uuid4()), "problem": "A real-domain objective."})
    target_branch.update({"strategy_text": "Use a real-domain proof.", "pending_investigation": {}})
    skeptic_context = research_sessions._portfolio_context(record, target_branch, "skeptic", 1)
    assert skeptic_context["peer_handoffs"][0]["retracted"] is True

    decision = research_sessions._portfolio_decision(record)
    assert decision["conflict_candidates"] == []
    assert len(decision["retracted_peer_handoffs"]) == 1
    assert decision["retracted_peer_handoffs"][0]["retracted_by_artifact_id"] == retraction["id"]

    # A later retraction cannot erase the fact that the target already saw the
    # handoff. Preserve that causal history while marking it withdrawn.
    second_source_id = "source-evidence-later"
    source_branch["artifacts"].append(second_source_id)
    second_source = {
        "id": second_source_id,
        "strategy_id": source_id,
        "strategy_title": "Integer route",
        "sequence": 3,
        "skeptic_output": {
            "cross_strategy_relations": [
                {
                    "strategy_id": target_id,
                    "artifact_id": target_artifact_id,
                    "relation": "complements",
                    "rationale": "A second, later claimed connection.",
                }
            ]
        },
    }
    record["artifacts"].append(second_source)
    research_sessions._queue_peer_handoffs(record, source_branch, second_source)
    consumed_handoffs = list(target_branch["pending_peer_handoffs"])
    consumed_target_artifact = {
        "id": "target-after-handoff",
        "strategy_id": target_id,
        "peer_handoffs_prompted": consumed_handoffs,
    }
    target_branch.pop("pending_peer_handoffs")
    target_branch.pop("peer_handoff_base_question")
    record["artifacts"].append(consumed_target_artifact)
    retraction_after_use = {
        "id": "source-retraction-after-use",
        "strategy_id": source_id,
        "skeptic_output": {
            "cross_strategy_relations": [],
            "retracted_cross_strategy_source_artifact_ids": [second_source_id],
        },
    }
    record["artifacts"].append(retraction_after_use)
    research_sessions._retract_peer_handoffs(record, source_branch, retraction_after_use)
    assert consumed_target_artifact["peer_handoffs_prompted"] == consumed_handoffs
    assert any(
        item["source_artifact_id"] == second_source_id
        and item["retracted_by_artifact_id"] == retraction_after_use["id"]
        for item in record["retracted_peer_handoffs"]
    )
    assert all(
        item["source_artifact_id"] != second_source_id
        for item in research_sessions._portfolio_decision(record)["cross_strategy_reviews"]
    )


def test_peer_handoff_queue_defers_without_silent_loss():
    source_id, target_id = "queue-source", "queue-target"
    target_artifact_id = "queue-target-artifact"
    target_branch = {
        "strategy_id": target_id,
        "strategy_title": "Target",
        "status": "running",
        "current_question": "Continue the target route.",
        "artifacts": [target_artifact_id],
    }
    source_branch = {"strategy_id": source_id, "strategy_title": "Source", "artifacts": []}
    target_artifact = {
        "id": target_artifact_id,
        "strategy_id": target_id,
        "strategy_title": "Target",
        "sequence": 1,
        "skeptic_output": {},
    }
    record = {"strategy_runs": [source_branch, target_branch], "artifacts": [target_artifact]}
    for index in range(6):
        source_artifact = {
            "id": f"source-artifact-{index}",
            "strategy_id": source_id,
            "strategy_title": "Source",
            "sequence": index + 1,
            "skeptic_output": {
                "cross_strategy_relations": [
                    {
                        "strategy_id": target_id,
                        "artifact_id": target_artifact_id,
                        "relation": "supports",
                        "rationale": f"Evidence {index} may inform the target route.",
                    }
                ]
            },
        }
        record["artifacts"].append(source_artifact)
        research_sessions._queue_peer_handoffs(record, source_branch, source_artifact)

    assert len(target_branch["pending_peer_handoffs"]) == 4
    assert len(target_branch["deferred_peer_handoffs"]) == 2
    queued_ids = {
        item["handoff_id"]
        for item in target_branch["pending_peer_handoffs"] + target_branch["deferred_peer_handoffs"]
    }
    consumed = target_branch.pop("pending_peer_handoffs")
    research_sessions._promote_deferred_peer_handoffs(record)
    assert len(target_branch["pending_peer_handoffs"]) == 2
    assert target_branch["deferred_peer_handoffs"] == []
    assert queued_ids == {
        item["handoff_id"] for item in consumed + target_branch["pending_peer_handoffs"]
    }


def test_peer_handoff_deferred_storage_is_bounded_and_reports_overflow():
    source_id, target_id = "bounded-source", "bounded-target"
    target_artifact_id = "bounded-target-artifact"
    target_branch = {
        "strategy_id": target_id,
        "strategy_title": "Target",
        "status": "running",
        "current_question": "Continue the target route.",
        "artifacts": [target_artifact_id],
    }
    source_branch = {"strategy_id": source_id, "strategy_title": "Source", "artifacts": []}
    record = {
        "strategy_runs": [source_branch, target_branch],
        "artifacts": [
            {
                "id": target_artifact_id,
                "strategy_id": target_id,
                "strategy_title": "Target",
                "sequence": 1,
                "skeptic_output": {},
            }
        ],
    }
    total = 4 + research_sessions.MAX_DEFERRED_PEER_HANDOFFS + 10
    for index in range(total):
        source_artifact = {
            "id": f"bounded-source-{index}",
            "strategy_id": source_id,
            "strategy_title": "Source",
            "sequence": index + 1,
            "skeptic_output": {
                "cross_strategy_relations": [
                    {
                        "strategy_id": target_id,
                        "artifact_id": target_artifact_id,
                        "relation": "supports",
                        "rationale": f"Finding {index} can inform the target route.",
                    }
                ]
            },
        }
        record["artifacts"].append(source_artifact)
        research_sessions._queue_peer_handoffs(record, source_branch, source_artifact)

    assert len(target_branch["pending_peer_handoffs"]) == 4
    assert (
        len(target_branch["deferred_peer_handoffs"]) == research_sessions.MAX_DEFERRED_PEER_HANDOFFS
    )
    assert target_branch["deferred_peer_handoff_overflow_count"] == 10
    assert (
        len(target_branch["deferred_peer_handoff_overflow"])
        == research_sessions.MAX_RECORDED_HANDOFF_OVERFLOW
    )
    assert target_branch["deferred_peer_handoff_overflow_omitted_count"] == 2
    assert target_branch["deferred_peer_handoff_overflow"][-1]["source_artifact_id"] == (
        f"bounded-source-{total - 1}"
    )
    assert len(json.dumps(target_branch).encode("utf-8")) < 32_000
    overflow = research_sessions._portfolio_decision(record)["deferred_handoff_overflows"][0]
    assert overflow["overflow_count"] == 10
    assert overflow["omitted_overflow_records"] == 2


async def test_portfolio_budget_too_small_for_next_pair_is_finalized(path: Path):
    view, first, credential, config = await setup(path)
    second = create_strategy(path, "Second strategy", "Try another mechanism.").project.strategies[
        -1
    ]
    limits = research_sessions.get_limits(str(path))
    limits["research_rounds"] = 2
    limits["model_calls"] = 5
    limits = research_sessions.save_limits(str(path), limits)

    async def handler(request):
        payload = json.loads(request.content)
        context = json.loads(payload["input"])
        role = payload["text"]["format"]["name"]
        output = (
            investigation(context["cycle"])
            if role == "research_investigator"
            else skeptic(context["cycle"])
        )
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
            str(path),
            first.id,
            str(uuid4()),
            view.project.id,
            credential["identity"],
            expected_limits=limits,
            strategy_ids=[first.id, second.id],
        )
        finished = await wait_for(path, started["id"])

    assert finished["status"] == "ended"
    assert finished["calls_used"] == 4
    assert finished["outcome"]["assessment"]
    assert len(finished["strategy_assessments"]) == 2
    assert all(branch["status"] == "ended" for branch in finished["strategy_runs"])
    assert finished["events"][-1]["kind"] == "portfolio.terminated"
    assert "shared turns could not fund another complete" in finished["message"].lower()
    assert "incomplete" in finished["message"].lower()
    assert all("deferred" in branch["reason"].lower() for branch in finished["strategy_runs"])


async def test_three_strategies_launch_under_three_turn_shared_ceiling(path: Path):
    view, first, credential, config = await setup(path)
    second_view = create_strategy(path, "Second route", "Check a separate argument.")
    second = next(item for item in second_view.project.strategies if item.id != first.id)
    third_view = create_strategy(path, "Third route", "Check a third argument.")
    third = next(
        item for item in third_view.project.strategies if item.id not in {first.id, second.id}
    )
    limits = research_sessions.get_limits(str(path))
    limits.update({"research_rounds": 3, "model_calls": 3})
    limits = research_sessions.save_limits(str(path), limits)
    dispatched = []

    async def handler(request):
        payload = json.loads(request.content)
        context = json.loads(payload["input"])
        role = payload["text"]["format"]["name"]
        dispatched.append((context["strategy"]["id"], role))
        output = (
            investigation(context["cycle"])
            if role == "research_investigator"
            else skeptic(context["cycle"])
        )
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
            str(path),
            first.id,
            str(uuid4()),
            view.project.id,
            credential["identity"],
            expected_limits=limits,
            strategy_ids=[first.id, second.id, third.id],
        )
        finished = await wait_for(path, started["id"])
    assert finished["status"] == "ended"
    assert finished["calls_used"] == 2
    assert len(finished["artifacts"]) == 1
    assert [role for _, role in dispatched] == ["research_investigator", "research_skeptic"]
    assert sum(branch["calls_used"] for branch in finished["strategy_runs"]) == 2
    assert all(
        branch["status"] == "ended" and "deferred" in branch["reason"].lower()
        for branch in finished["strategy_runs"]
    )
    assert "deferred strategies" in finished["message"].lower()
    assert "incomplete" in finished["message"].lower()


async def test_incomplete_productive_stop_uses_remaining_round(path: Path):
    view, strategy, credential, config = await setup(path)
    limits = research_sessions.get_limits(str(path))
    limits.update({"research_rounds": 2, "model_calls": 4})
    limits = research_sessions.save_limits(str(path), limits)
    roles = []

    async def handler(request):
        payload = json.loads(request.content)
        context = json.loads(payload["input"])
        role = payload["text"]["format"]["name"]
        roles.append((role, context["cycle"]))
        output = (
            investigation(context["cycle"])
            if role == "research_investigator"
            else skeptic(
                context["cycle"],
                assessment="stop" if context["cycle"] == 1 else "continue",
                stop_reason="productive_conclusion"
                if context["cycle"] == 1
                else "recoverable_objection",
            )
        )
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
            str(path),
            strategy.id,
            str(uuid4()),
            view.project.id,
            credential["identity"],
            expected_limits=limits,
        )
        finished = await wait_for(path, started["id"])
    assert finished["status"] == "ended"
    assert finished["calls_used"] == 4
    assert finished["outcome"]["solution_review"]["status"] != "achieved"
    assert finished["outcome"]["assessment"] != "positive"
    assert "Complete reviewed candidate answer" not in finished["outcome"]["conclusion"]
    assert [artifact["strategy_cycle"] for artifact in finished["artifacts"]] == [1, 2]
    assert finished["artifacts"][0]["coordinator_decision"] == "continue"
    assert any(
        event["kind"] == "coordinator.incomplete_conclusion_reopened"
        for event in finished["events"]
    )
    assert roles == [
        ("research_investigator", 1),
        ("research_skeptic", 1),
        ("research_investigator", 2),
        ("research_skeptic", 2),
    ]


async def test_configured_cost_cap_reports_second_call_refusal(path: Path):
    """A completed Investigator followed by a refused Skeptic reports the real 1/6 stop."""
    view, strategy, credential, config = await setup(path)
    limits = {
        **research_sessions.DEFAULT_LIMITS,
        "model_calls": 6,
        "research_rounds": 3,
        "maximum_estimated_cost_usd": 0.05,
    }
    limits = research_sessions.save_limits(str(path), limits)
    calls = []

    async def handler(request):
        role = json.loads(request.content)["text"]["format"]["name"]
        calls.append(role)
        return httpx.Response(
            200,
            json=provider_response(
                investigation(1) if role == "research_investigator" else skeptic(1)
            ),
        )

    with (
        patch.object(research_sessions, "auth_context", new=AsyncMock(return_value=credential)),
        patch.object(research_sessions, "configuration", new=AsyncMock(return_value=config)),
        patch.object(research_sessions, "_reserve_cost", side_effect=[0.03, 0.05]),
        patch.object(research_sessions, "_estimate_cost", return_value=0.02),
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
        finished = await wait_for(path, started["id"])

    assert calls == ["research_investigator"]
    assert finished["calls_used"] == 1 and finished["call_limit"] == 6, finished
    assert finished["status"] == "paused", finished
    assert finished["current_action"] == "Paused · cost limit"
    assert "configured session cost limit" in finished["message"]
    assert "Completed research and cost reservations are preserved" in finished["message"]
    assert finished["strategy_runs"][0]["funding_resume_allowed"] is True
    assert "conservative cost reserve" in finished["outcome"]["summary"]


async def test_session_token_and_hard_ledger_stops_are_diagnostic(path: Path):
    token_message = research_sessions._portfolio_limit_message(
        {"cycle": 1, "cycle_limit": 3, "calls_used": 1, "call_limit": 6, "steps": []},
        [
            {
                "strategy_title": "Saved approach",
                "current_action": "Token limit",
                "calls_used": 1,
                "cycle": 1,
                "reason": "The bounded session token budget cannot reserve another provider call.",
            }
        ],
    )
    assert token_message and "1/6 agent turns" in token_message
    assert "bounded session token budget" in token_message
    assert "No Skeptic agent turn was dispatched" in token_message

    view, strategy, credential, config = await setup(path.parent / "hard-ledger.sigma")
    hard_limits = {
        **research_sessions.DEFAULT_LIMITS,
        "model_calls": 6,
        "research_rounds": 3,
        "maximum_estimated_cost_usd": 10.0,
        "maximum_input_tokens_per_session": 600_000,
    }
    dispatches = []
    real_reserve = research_sessions.reserve_before_dispatch

    async def provider(request):
        role = json.loads(request.content)["text"]["format"]["name"]
        return httpx.Response(
            200,
            json=provider_response(
                investigation(1) if role == "research_investigator" else skeptic(1)
            ),
        )

    def refuse_second_hard_reservation(*args, **kwargs):
        dispatches.append("reserve")
        if len(dispatches) == 2:
            raise BudgetExceeded("Research arm cumulative input-token limit would be exceeded")
        return real_reserve(*args, **kwargs)

    with (
        patch.object(research_sessions, "auth_context", new=AsyncMock(return_value=credential)),
        patch.object(research_sessions, "configuration", new=AsyncMock(return_value=config)),
        patch.object(research_sessions, "execution_capabilities", return_value=[]),
        patch.object(
            research_sessions, "reserve_before_dispatch", side_effect=refuse_second_hard_reservation
        ),
        patch(
            "sigma.research_sessions.httpx.AsyncClient",
            side_effect=lambda **kwargs: REAL_CLIENT(
                transport=httpx.MockTransport(provider), **kwargs
            ),
        ),
    ):
        hard_limits = research_sessions.save_limits(str(view.path), hard_limits)
        started = await research_sessions.start_session(
            str(view.path),
            strategy.id,
            str(uuid4()),
            view.project.id,
            credential["identity"],
            hard_limits,
        )
        hard_stopped = await wait_for(view.path, started["id"])

    assert hard_stopped["calls_used"] == 1 and hard_stopped["call_limit"] == 6, {
        "calls_used": hard_stopped.get("calls_used"),
        "call_limit": hard_stopped.get("call_limit"),
        "message": hard_stopped.get("message"),
        "terminal_reason": hard_stopped.get("terminal_reason"),
    }
    assert "hard token/cost budget refused" in hard_stopped["message"], hard_stopped.get("message")
    assert "No Skeptic agent turn was dispatched" in hard_stopped["message"]
    assert hard_stopped["outcome"]["summary"]


async def test_generic_objective_review_on_binary_strings(path: Path):
    problem = (
        "For each integer n >= 0, count binary strings of length n containing no two "
        "consecutive 1s. The empty string counts for n = 0. Derive and justify a general "
        "formula or recurrence for the count, including the necessary initial values. "
        "Check the result on small n. Do not assume a particular proof method."
    )
    view = initialize_project(path, "Counting Constrained Binary Strings", problem)
    strategy = create_strategy(
        path,
        "Partition by final symbol",
        "Split valid strings by whether the last bit is 0 or 1, prove the recurrence, and check initial values.",
    ).project.strategies[0]
    credential = {
        "identity": "fixture-account",
        "mode": "api_key",
        "token": "fixture-token",
        "status": "connected",
    }
    config = {"available": True, "model": MODEL, "reasoning_effort": "high"}
    candidate = {
        "claim": "The count is a_n = F_(n+2), equivalently a_0=1, a_1=2, and a_n=a_(n-1)+a_(n-2).",
        "method": (
            "For n>=2, partition valid strings by their last bit. Appending 0 gives a bijection "
            "with valid strings of length n-1. A string ending in 1 has penultimate bit 0, and "
            "removing that final 01 gives a bijection with valid strings of length n-2. The two "
            "classes are disjoint and exhaustive, so a_n=a_(n-1)+a_(n-2). There is one empty "
            "string and two valid strings of length one. This proves the Fibonacci formula by induction."
        ),
        "assumptions": ["The two classes are defined by the final symbol."],
        "evidence_status": "Complete inductive argument; no formal checker was run.",
        "open_obligations": [],
        "python_code": None,
        "sage_code": None,
        "prior_session_failure_attempt_ids": [],
        "computational_citations": [],
    }
    accepted = {
        **skeptic(1, "stop", "productive_conclusion"),
        "response": "The final-symbol classes are disjoint and exhaustive; the recurrence and base cases support the claim for every n.",
        "objections": [],
        "remaining_obligations": [],
        "next_question": "",
        "objective_status": "achieved",
        "solution_claim": "a_n=F_(n+2), with a_0=1, a_1=2, and a_n=a_(n-1)+a_(n-2).",
        "argument_summary": "The final-bit partition gives a disjoint recurrence; induction identifies the sequence with F_(n+2).",
        "proof_obligations": [
            "The final-bit classes are disjoint and exhaustive [cycle 1].",
            "The recurrence and initial values imply the general Fibonacci formula [cycle 1].",
        ],
        "verification_status": "convincing_unverified",
        "unresolved_objections": [],
        "supporting_cycles": [1],
        "strategy_contribution": "solution",
        "contribution_rationale": "The linked final-symbol argument derives and proves the recurrence.",
    }
    incomplete = {
        **accepted,
        "assessment": "continue",
        "stop_reason": "recoverable_objection",
        "response": "The small values fit Fibonacci, but the recurrence is asserted rather than proved for every n.",
        "objections": ["No argument establishes the recurrence for arbitrary n."],
        "remaining_obligations": ["Prove the disjoint exhaustive final-symbol partition."],
        "next_question": "Prove the recurrence from the final-symbol cases.",
        "objective_status": "partial",
        "proof_obligations": ["Derive the recurrence."],
        "verification_status": "incomplete",
        "unresolved_objections": ["The recurrence remains unsupported."],
        "strategy_contribution": "productive",
    }
    outputs = [candidate, accepted]

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
        complete_start = await research_sessions.start_session(
            str(path), strategy.id, str(uuid4()), view.project.id, credential["identity"]
        )
        complete = await wait_for(path, complete_start["id"])
        assert complete["outcome"]["assessment"] == "positive"
        assert complete["strategy_assessments"][0]["assessment"] == "contributed_to_solution"

        research_sessions.save_limits(
            str(path),
            {
                "research_rounds": 1,
                "model_calls": 2,
                "session_duration_minutes": 10,
                "output_tokens_per_call": 4000,
                "maximum_estimated_cost_usd": None,
            },
        )
        outputs.extend([candidate, incomplete])
        partial_start = await research_sessions.start_session(
            str(path), strategy.id, str(uuid4()), view.project.id, credential["identity"]
        )
        partial = await wait_for(path, partial_start["id"])
        assert partial["outcome"]["assessment"] == "mixed"
        assert partial["outcome"]["solution_review"]["status"] == "partial"
        assert "recurrence remains unsupported" in " ".join(partial["outcome"]["caveats"])


async def test_remove_terminal_and_monotonic_number(path: Path):
    view, strategy, credential, config = await setup(path)
    terminal_review = skeptic(1, "stop", "no_progress")
    terminal_review["remaining_obligations"] = []
    terminal_review["next_question"] = ""
    terminal_investigation = investigation(1)
    terminal_investigation["open_obligations"] = []
    outputs = [terminal_investigation, terminal_review]

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
            await research_sessions.remove_session(str(path), first["id"], "stale-revision")
        except ProjectError as exc:
            assert "changed" in str(exc).lower()
        else:
            raise AssertionError("stale session removal was accepted")
        removed = await research_sessions.remove_session(
            str(path), first["id"], finished["updated_at"]
        )
        assert removed == {"removed": True, "id": first["id"], "session_number": 1}
        assert research_sessions.list_sessions(str(path)) == []
        assert (path / "project.json").exists()
        assert research_sessions.get_limits(str(path)) == research_sessions.DEFAULT_LIMITS
        second_terminal_review = skeptic(2, "stop", "no_progress")
        second_terminal_review["remaining_obligations"] = []
        second_terminal_review["next_question"] = ""
        second_terminal_investigation = investigation(2)
        second_terminal_investigation["open_obligations"] = []
        outputs[:] = [second_terminal_investigation, second_terminal_review]
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
            assert "maximum concurrent sessions" in str(exc)
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


async def test_remove_running_session_cancels_execution_and_releases_slot(path: Path):
    view, strategy, credential, config = await setup(path)
    entered = asyncio.Event()

    async def handler(_request) -> httpx.Response:
        entered.set()
        await asyncio.Event().wait()
        raise AssertionError("blocked provider handler unexpectedly returned")

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
        active = research_sessions.get_session(str(path), started["id"])
        removed = await research_sessions.remove_session(
            str(path), started["id"], active["updated_at"]
        )
        assert removed["id"] == started["id"]
        assert research_sessions._tasks.get(started["id"]) is None
        assert research_sessions.list_sessions(str(path)) == []
        second = await research_sessions.start_session(
            str(path), strategy.id, str(uuid4()), view.project.id, credential["identity"]
        )
        assert second["status"] == "queued"
        await research_sessions.control_session(str(path), second["id"], "stop")


async def test_remove_racing_with_completion_is_idempotently_terminal(path: Path):
    view, strategy, credential, config = await setup(path)
    entered, release = asyncio.Event(), asyncio.Event()
    outputs = [investigation(1), skeptic(1, "stop", "no_progress")]
    outputs[-1]["remaining_obligations"] = []
    outputs[-1]["next_question"] = ""

    async def handler(_request) -> httpx.Response:
        entered.set()
        await release.wait()
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
        await asyncio.wait_for(entered.wait(), 2)
        active = research_sessions.get_session(str(path), started["id"])
        deletion = asyncio.create_task(
            research_sessions.remove_session(str(path), started["id"], active["updated_at"])
        )
        release.set()
        removed = await asyncio.wait_for(deletion, 3)
        assert removed["id"] == started["id"]
        assert research_sessions.list_sessions(str(path)) == []
        assert started["id"] not in research_sessions._tasks


async def test_project_deletion_stops_all_active_sessions_first(path: Path):
    view, strategy, credential, config = await setup(path)
    entered = asyncio.Event()

    async def handler(_request) -> httpx.Response:
        entered.set()
        await asyncio.Event().wait()
        raise AssertionError("blocked provider handler unexpectedly returned")

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
        stopped = await research_sessions.stop_project_sessions(str(path))
        assert stopped == [started["id"]]
        assert research_sessions.get_session(str(path), started["id"])["status"] == "stopped"
        assert research_sessions._tasks.get(started["id"]) is None
        assert not research_sessions.has_active_session(str(path))
        shutil.rmtree(path)
        assert not path.exists()


async def test_response_transport_and_parsed_bounds(path: Path):
    repeated_transport_failure = "Research provider transport exceeded the 8 MB safety bound"
    assert (
        research_sessions._portfolio_failure_message(
            [
                {"status": "failed", "reason": repeated_transport_failure},
                {"status": "failed", "reason": f"  {repeated_transport_failure}  "},
                {"status": "failed", "reason": "A separate branch failed."},
                {"status": "completed", "reason": repeated_transport_failure},
            ]
        )
        == f"{repeated_transport_failure}; A separate branch failed."
    )
    view, strategy, credential, config = await setup(path)
    oversized_projects = path.parent / "transport.sigma"
    transport_view, transport_strategy, _, _ = await setup(oversized_projects)

    async def oversized_transport(request):
        response = provider_response(investigation(1))
        response["padding"] = "x" * 8_010_000
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
    assert failed["status"] == "failed"
    assert "safe size limit" in failed["message"]
    assert failed["steps"][0]["failure_kind"] == "response_too_large"
    assert failed["artifacts"] == []

    token_limit = 12_000

    async def oversized_parsed(request):
        response = provider_response(investigation(1))
        response["output"][0]["content"][0]["text"] += " " * 70_000
        response["padding"] = "x" * 1_010_000
        return httpx.Response(200, json=response)

    oversized_text = json.dumps(investigation(1)) + " " * 70_000
    assert len(oversized_text.encode("utf-8")) > token_limit * 4
    record = {
        "model": MODEL,
        "reasoning_effort": "high",
        "mode": credential["mode"],
        "identity_hash": research_sessions._digest(credential["identity"]),
        "output_token_limit": token_limit,
    }
    with (
        patch.object(research_sessions, "auth_context", new=AsyncMock(return_value=credential)),
        patch(
            "sigma.research_sessions.httpx.AsyncClient",
            side_effect=lambda **kwargs: REAL_CLIENT(
                transport=httpx.MockTransport(oversized_parsed), **kwargs
            ),
        ),
    ):
        accepted = await research_sessions._call(
            record,
            "investigator",
            {"problem": view.project.problem, "strategy": strategy.approach},
        )
    assert accepted == (
        investigation(1),
        {"input_tokens": 120, "cached_input_tokens": 20, "output_tokens": 80},
    )


async def test_changed_bindings_pause_before_provider(path: Path):
    view, strategy, credential, config = await setup(path)
    changed = {**credential, "identity": "different-account"}
    entered = asyncio.Event()
    release = asyncio.Event()
    provider_calls = []

    original_role_call = research_sessions._portfolio_role_call

    async def blocked_role_call(*args, **kwargs):
        entered.set()
        await release.wait()
        return await original_role_call(*args, **kwargs)

    async def handler(request):
        provider_calls.append(request)
        return httpx.Response(200, json=provider_response(investigation(1)))

    with (
        patch.object(
            research_sessions, "auth_context", new=AsyncMock(side_effect=[credential, changed])
        ),
        patch.object(research_sessions, "configuration", new=AsyncMock(return_value=config)),
        patch.object(research_sessions, "_portfolio_role_call", new=blocked_role_call),
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
        patch.object(research_sessions, "_portfolio_role_call", new=blocked_role_call),
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


async def test_legacy_resume_accepts_reverted_eligibility_events(path: Path):
    view, strategy, credential, config = await setup(path)
    gate_entered = asyncio.Event()
    provider_calls = []

    async def blocked_role_call(*_args, **_kwargs):
        gate_entered.set()
        await asyncio.Event().wait()
        return False

    async def handler(request):
        provider_calls.append(request)
        role = json.loads(request.content)["text"]["format"]["name"]
        output = investigation(1) if role == "research_investigator" else skeptic(1, "stop")
        return httpx.Response(200, json=provider_response(output))

    with (
        patch.object(research_sessions, "auth_context", new=AsyncMock(return_value=credential)),
        patch.object(research_sessions, "configuration", new=AsyncMock(return_value=config)),
        patch.object(research_sessions, "_portfolio_role_call", new=blocked_role_call),
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
        await asyncio.wait_for(gate_entered.wait(), 2)
        paused = await research_sessions.control_session(str(path), started["id"], "pause")
        assert paused["status"] == "paused"

    record = research_sessions._read(str(path), started["id"])
    record.pop("guard_state_hash")  # Exercise records created before semantic guards existed.
    research_sessions._save(str(path), record)
    from sigma.projects import set_strategy_enabled

    set_strategy_enabled(str(path), strategy.id, False)
    set_strategy_enabled(str(path), strategy.id, True)
    current = inspect_project(path).project
    assert research_sessions._legacy_resume_state_matches(record, current)

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
        finished = await wait_for(path, resumed["id"])
    assert finished["status"] == "ended"
    assert len(provider_calls) == finished["calls_used"] == 6


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
    assert all(step["status"] == "completed" and step.get("output") for step in paused["steps"])
    assert paused["strategy_runs"][0]["pending_skeptic"]
    assert "storage limit reached" in paused["message"].lower()


def test_outcome_metrics_from_persisted_evidence(path: Path):
    view = initialize_project(path, "Metrics fixture", "A persisted evidence accounting test")
    session_id = str(uuid4())
    execution_id = str(uuid4())
    shared_python = {
        "id": execution_id,
        "status": "completed",
        "artifacts": [{"filename": "result.csv", "size_bytes": 128, "sha256": "same-file-hash"}],
    }
    artifacts = [
        {
            "id": "finding-a",
            "strategy_id": "strategy-a",
            "strategy_cycle": 1,
            "claim_or_question": "Alpha finding",
            "coordinator_decision": "continue",
            "open_obligations": ["Check a boundary", "Check a boundary"],
            "investigator_output": {"python_execution": shared_python},
            "objective_review": {
                "status": "partial",
                "claim": "Conclusion Alpha",
                "proof_obligations": ["Check a boundary"],
                "unresolved_objections": ["Independence is unclear"],
                "basis_artifact_ids": ["finding-a"],
            },
        },
        {
            "id": "finding-b",
            "strategy_id": "strategy-b",
            "strategy_cycle": 1,
            "claim_or_question": "Beta finding",
            "coordinator_decision": "continue",
            "open_obligations": ["Check a tail case"],
            "investigator_output": {"python_execution": shared_python},
            "objective_review": {
                "status": "partial",
                "claim": "Conclusion Beta",
                "proof_obligations": ["Check a tail case"],
                "unresolved_objections": [],
                "basis_artifact_ids": ["finding-b"],
            },
        },
    ]
    duplicate_id = "call-completed"
    started = "2026-10-23T10:00:00+00:00"
    record = {
        "id": session_id,
        "project_path": str(project_path(path)),
        "project_id": view.project.id,
        "session_number": 1,
        "strategy_id": "strategy-a",
        "strategy_title": "Alpha",
        "strategy_snapshot": [],
        "strategy_runs": [
            {"strategy_id": "strategy-a", "strategy_title": "Alpha", "calls_used": 3},
            {"strategy_id": "strategy-b", "strategy_title": "Beta", "calls_used": 1},
            {"strategy_id": "never-ran", "strategy_title": "Not run", "calls_used": 0},
        ],
        "mode": "chatgpt",
        "model": MODEL,
        "reasoning_effort": "medium",
        "status": "ended",
        "created_at": started,
        "started_at": started,
        "updated_at": "2026-10-23T10:02:00+00:00",
        "calls_used": 5,
        "call_limit": 8,
        "cycle": 1,
        "artifacts": artifacts,
        "strategy_assessments": [
            {"assessment": "productive"},
            {"assessment": "not_used"},
        ],
        "steps": [
            {
                "id": duplicate_id,
                "role": "investigator",
                "cycle": 1,
                "strategy_id": "strategy-a",
                "strategy_title": "Alpha",
                "status": "completed",
                "started_at": started,
                "finished_at": "2026-10-23T10:00:10+00:00",
                "token_usage": {
                    "input_tokens": 10,
                    "cached_input_tokens": 3,
                    "output_tokens": 4,
                },
                "output": {"python_execution": shared_python},
            },
            {"id": duplicate_id, "role": "investigator", "status": "completed"},
            {
                "id": "call-rejected",
                "role": "skeptic",
                "cycle": 1,
                "strategy_id": "strategy-a",
                "strategy_title": "Alpha",
                "status": "failed",
                "failure_kind": "provider_rejected",
                "provider_http_status": 400,
                "failure_message": "ChatGPT rejected the request (HTTP 400).",
                "started_at": started,
                "finished_at": "2026-10-23T10:00:12+00:00",
            },
            {
                "id": "call-interrupted",
                "role": "investigator",
                "cycle": 1,
                "strategy_id": "strategy-b",
                "strategy_title": "Beta",
                "status": "interrupted",
                "failure_kind": "interrupted",
                "started_at": started,
                "finished_at": "2026-10-23T10:00:15+00:00",
            },
            {
                "id": "call-cancelled-retry",
                "role": "investigator",
                "cycle": 1,
                "strategy_id": "strategy-a",
                "strategy_title": "Alpha",
                "status": "interrupted",
                "failure_kind": "cancelled",
                "started_at": started,
                "finished_at": "2026-10-23T10:00:20+00:00",
            },
        ],
    }
    research_sessions._save(str(path), record)
    loaded = research_sessions.get_session(str(path), session_id)
    metrics = loaded["outcome"]["metrics"]
    operational = {item["label"]: item["value"] for item in metrics["operational"]}
    quality = {item["label"]: item["value"] for item in metrics["research_quality"]}
    # Historical session records must never be assigned a newer build SHA.
    assert operational["Backend build"] == "Unknown (session build not recorded)"
    resumed_record = deepcopy(record)
    resumed_record["backend_build_commit"] = "1" * 40
    resumed_record["steps"][0]["backend_build_commit"] = "2" * 40
    resumed_metrics = research_sessions._outcome_metrics(resumed_record, loaded["outcome"])
    resumed_build = next(
        item["value"] for item in resumed_metrics["operational"] if item["label"] == "Backend build"
    )
    assert resumed_build == "Created: " + "1" * 40 + " · calls: " + "2" * 40
    assert metrics["sources"] == {
        "session_id": session_id,
        "step_ids": sorted({step["id"] for step in record["steps"]}),
        "artifact_ids": ["finding-a", "finding-b"],
        "execution_ids": [execution_id],
        "strategy_ids": ["strategy-a", "strategy-b"],
    }
    # The source inventory resolves to unchanged structured evidence, including
    # interrupted/reused states. Counts alone are not claim provenance.
    assert loaded["steps"] == record["steps"]
    assert loaded["artifacts"] == record["artifacts"]
    assert loaded["artifacts"][1]["investigator_output"]["python_execution"] == shared_python
    saved = json.loads((path / "research-sessions" / f"{session_id}.json").read_text())
    assert "metrics" not in saved.get("outcome", {})

    calls = operational["Agent turns by status"]
    assert calls.startswith("5 budget-counted calls (1 step status unavailable")
    assert "1 completed" in calls and "1 rejected" in calls
    assert "2 interrupted / cancelled" in calls and "1 status unavailable" in calls
    provider_failures = operational["Provider failures / retries"]
    assert "1 provider failure(s)" in provider_failures
    assert "2 interrupted / cancelled" in provider_failures
    assert "1 later attempt(s)" in provider_failures
    assert "no automatic retries" in provider_failures
    assert (
        "— (1/5 calls report token usage" in operational["Tokens · input / output / cached / total"]
    )
    assert "plan allowance consumption unknown" in operational["Estimated monetary cost"]
    assert operational["Python runs by status"] == "1 completed"
    assert "1 Python file(s) (128 B)" in operational["Artifacts and storage"]
    assert (
        "Alpha" in quality["Strategies investigated"]
        and "Beta" in quality["Strategies investigated"]
    )
    assert "Not run" not in quality["Strategies investigated"]
    assert quality["Research rounds"] == "2 completed / 2 started"
    assert quality["Evidence-backed conclusions"] == "2 conclusion(s) · 2 cited finding(s)"
    assert "Check a boundary" in quality["Open proof obligations"]
    assert "Independence is unclear" in quality["Unresolved objections"]

    missing_cached = research_sessions._usage({"usage": {"input_tokens": 7, "output_tokens": 2}})
    assert missing_cached is not None
    assert missing_cached == {
        "input_tokens": 7,
        "cached_input_tokens": None,
        "output_tokens": 2,
    }
    # Missing cached-token metadata is priced conservatively as all uncached,
    # so known provider usage does not create an indefinite cost hold.
    assert research_sessions._estimate_cost(MODEL, missing_cached) == 0.000034

    uncached_metadata = research_sessions._outcome_metrics(
        {
            "mode": "api_key",
            "model": MODEL,
            "status": "ended",
            "calls_used": 1,
            "started_at": started,
            "updated_at": "2026-10-23T10:00:02+00:00",
            "steps": [
                {
                    "id": "one-api-call",
                    "role": "investigator",
                    "cycle": 1,
                    "status": "completed",
                    "started_at": started,
                    "finished_at": "2026-10-23T10:00:01+00:00",
                    "token_usage": missing_cached,
                }
            ],
            "artifacts": [],
        },
        {"label": "Pending", "assessment": "pending", "solution_review": None},
    )
    uncached_ops = {item["label"]: item["value"] for item in uncached_metadata["operational"]}
    assert uncached_ops["Tokens · input / output / cached / total"] == (
        "7 / 2 / — (0/1 calls include cached-token metadata) / 9"
    )
    assert "$0.000034 estimated" in uncached_ops["Estimated monetary cost"]

    unlinked_execution = research_sessions._outcome_metrics(
        {
            "mode": "chatgpt",
            "model": MODEL,
            "status": "ended",
            "calls_used": 0,
            "steps": [
                {"id": "broken-step", "output": {"python_execution": {"status": "completed"}}}
            ],
            "artifacts": [],
        },
        {"label": "Pending", "assessment": "pending", "solution_review": None},
    )
    assert {item["label"]: item["value"] for item in unlinked_execution["operational"]}[
        "Python runs by status"
    ] == "— (execution record without ID)"


async def test_concurrent_human_guidance_is_delivered_and_attributed(path: Path):
    view, first, credential, config = await setup(path)
    research_sessions.save_limits(str(path), {**research_sessions.DEFAULT_LIMITS, "model_calls": 6})
    second = create_strategy(
        path, "Second saved approach", "Test the independent boundary case."
    ).project.strategies[-1]
    entered = asyncio.Event()
    release_initial = asyncio.Event()
    initial_investigators = 0
    calls: list[tuple[str, str, dict[str, Any]]] = []

    async def fake_call(record, role, context, timeout=None, step_id=None):
        assert isinstance(step_id, str)
        nonlocal initial_investigators
        strategy_id = context["strategy"]["id"]
        calls.append((role, strategy_id, json.loads(json.dumps(context))))
        if role == "investigator" and context["cycle"] == 1:
            initial_investigators += 1
            if initial_investigators == 2:
                entered.set()
            await release_initial.wait()
            return investigation(1), None
        if role == "investigator":
            return investigation(context["cycle"]), None
        output = skeptic(context["cycle"])
        guidance = context.get("human_guidance", [])
        if guidance:
            assert strategy_id == second.id
            output["next_question"] = (
                "Prioritize the requested boundary case against the saved counterexample."
            )
            output["human_guidance_reviews"] = [
                {
                    "intervention_id": item["intervention_id"],
                    "uptake": "applied",
                    "rationale": "I changed the next check to test the specified boundary case.",
                }
                for item in guidance
            ]
        return output, None

    with (
        patch.object(research_sessions, "auth_context", new=AsyncMock(return_value=credential)),
        patch.object(research_sessions, "configuration", new=AsyncMock(return_value=config)),
        patch.object(research_sessions, "_call", new=fake_call),
    ):
        started = await research_sessions.start_session(
            str(path),
            first.id,
            str(uuid4()),
            view.project.id,
            credential["identity"],
            strategy_ids=[first.id, second.id],
        )
        await asyncio.wait_for(entered.wait(), timeout=2)
        before = research_sessions.get_session(str(path), started["id"])
        assert before["calls_used"] == 2 and len(before["steps"]) == 2
        queued = await research_sessions.submit_intervention(
            str(path),
            started["id"],
            "objection",
            "Check whether the boundary case invalidates the claimed induction step.",
            [second.id],
            ["skeptic"],
        )
        intervention = queued["interventions"][-1]
        assert queued["calls_used"] == 2
        assert intervention["status"] == "queued"
        assert intervention["target_strategy_ids"] == [second.id]
        assert intervention["deliveries"][0]["status"] == "queued"
        release_initial.set()
        finished = await wait_for(path, started["id"])

    assert finished["status"] == "ended"
    assert finished["calls_used"] == 6
    assert len(finished["artifacts"]) == 3
    assert all(
        not context.get("human_guidance") for role, _, context in calls if role == "investigator"
    )
    target_skeptic_calls = [
        context
        for role, strategy_id, context in calls
        if role == "skeptic" and strategy_id == second.id
    ]
    guided = next(context for context in target_skeptic_calls if context.get("human_guidance"))
    assert guided["human_guidance"] == [
        {
            "intervention_id": intervention["id"],
            "kind": "objection",
            "text": "Check whether the boundary case invalidates the claimed induction step.",
            "submitted_at": intervention["submitted_at"],
        }
    ]
    target_artifact = next(
        artifact for artifact in finished["artifacts"] if artifact["strategy_id"] == second.id
    )
    assert (
        target_artifact["next_question"]
        == "Prioritize the requested boundary case against the saved counterexample."
    )
    assert (
        target_artifact["skeptic_output"]["human_guidance_reviews"][0]["intervention_id"]
        == intervention["id"]
    )
    delivery = finished["interventions"][-1]["deliveries"][0]
    assert delivery["status"] == "acknowledged" and delivery["uptake"] == "applied"
    step = next(
        item for item in finished["steps"] if item["id"] == delivery["attempts"][0]["step_id"]
    )
    assert step["strategy_id"] == second.id and step["role"] == "skeptic"
    assert delivery["target_cycle"] == delivery["attempts"][0]["cycle"] == step["cycle"]
    assert step["human_intervention_ids"] == [intervention["id"]]
    assert [
        event["kind"] for event in finished["events"] if event["kind"].startswith("intervention.")
    ] == ["intervention.accepted", "intervention.delivered", "intervention.acknowledged"]


async def test_intervention_delivery_pause_resume_keeps_attempt_provenance(path: Path):
    view, strategy, credential, config = await setup(path)
    research_sessions.save_limits(str(path), {**research_sessions.DEFAULT_LIMITS, "model_calls": 6})
    skeptic_entered = asyncio.Event()
    release_skeptic = asyncio.Event()
    guided_skeptic_calls = 0
    contexts = []

    async def fake_call(record, role, context, timeout=None, step_id=None):
        assert isinstance(step_id, str)
        nonlocal guided_skeptic_calls
        contexts.append((role, json.loads(json.dumps(context))))
        guidance = context.get("human_guidance", [])
        if role == "investigator":
            return investigation(context["cycle"]), None
        output = skeptic(context["cycle"])
        if guidance:
            guided_skeptic_calls += 1
            output["human_guidance_reviews"] = [
                {
                    "intervention_id": item["intervention_id"],
                    "uptake": "considered",
                    "rationale": "I considered the instruction and recorded its limitation.",
                }
                for item in guidance
            ]
            if guided_skeptic_calls == 1:
                skeptic_entered.set()
                await release_skeptic.wait()
        return output, None

    with (
        patch.object(research_sessions, "auth_context", new=AsyncMock(return_value=credential)),
        patch.object(research_sessions, "configuration", new=AsyncMock(return_value=config)),
        patch.object(research_sessions, "_call", new=fake_call),
    ):
        started = await research_sessions.start_session(
            str(path), strategy.id, str(uuid4()), view.project.id, credential["identity"]
        )
        for _ in range(200):
            if research_sessions.get_session(str(path), started["id"])["calls_used"]:
                break
            await asyncio.sleep(0.01)
        queued = await research_sessions.submit_intervention(
            str(path),
            started["id"],
            "priority",
            "Prioritize the missing boundary case.",
            [strategy.id],
            ["skeptic"],
        )
        intervention_id = queued["interventions"][-1]["id"]
        await asyncio.wait_for(skeptic_entered.wait(), timeout=2)
        interrupted = await research_sessions.control_session(str(path), started["id"], "pause")
        assert interrupted["status"] == "paused" and interrupted["calls_used"] == 2
        delivery = interrupted["interventions"][-1]["deliveries"][0]
        assert delivery["status"] == "queued"
        assert delivery["attempts"][0]["status"] == "interrupted"
        assert not interrupted["artifacts"]

        release_skeptic.set()
        resumed = await research_sessions.control_session(str(path), started["id"], "resume")
        assert resumed["status"] == "queued"
        finished = await wait_for(path, started["id"])

    assert finished["calls_used"] == 5
    item = next(entry for entry in finished["interventions"] if entry["id"] == intervention_id)
    assert item["status"] == "acknowledged"
    attempts = item["deliveries"][0]["attempts"]
    assert [attempt["status"] for attempt in attempts] == ["interrupted", "acknowledged"]
    guided_contexts = [
        context for role, context in contexts if role == "skeptic" and context.get("human_guidance")
    ]
    assert len(guided_contexts) == 2
    assert all(
        context["human_guidance"][0]["intervention_id"] == intervention_id
        for context in guided_contexts
    )
    assert all(
        any(
            intervention_id in source.get("source_ids", [])
            and source.get("category") == "human_guidance"
            for source in context["context_manifest"]["sources"]
        )
        for context in guided_contexts
    )
    guided_steps = [
        step
        for step in finished["steps"]
        if intervention_id in step.get("human_intervention_ids", [])
    ]
    assert len(guided_steps) == 2
    assert all("context_manifest" in step for step in guided_steps)
    assert len(finished["artifacts"]) == 2
    assert finished["artifacts"][0]["investigator_output"]["claim"] == investigation(1)["claim"]


def test_intervention_recovery_supersession_and_rejection(path: Path):
    view, strategy, _, _ = asyncio.run(setup(path))
    session_id = str(uuid4())
    step_id = str(uuid4())
    intervention_id = str(uuid4())
    now = research_sessions._now()
    record = {
        "id": session_id,
        "project_path": str(project_path(path)),
        "project_id": view.project.id,
        "strategy_id": strategy.id,
        "strategy_ids": [strategy.id],
        "status": "running",
        "updated_at": now,
        "message": "In progress",
        "current_action": "Investigator",
        "current_step": step_id,
        "current_steps": [step_id],
        "calls_used": 1,
        "steps": [
            {"id": step_id, "role": "investigator", "strategy_id": strategy.id, "status": "running"}
        ],
        "strategy_runs": [
            {
                "strategy_id": strategy.id,
                "strategy_title": strategy.title,
                "status": "running",
                "current_action": "Investigator",
            }
        ],
        "events": [],
        "interventions": [
            {
                "id": intervention_id,
                "kind": "evidence",
                "text": "Inspect the supplied exact computation.",
                "target_strategy_ids": [strategy.id],
                "target_roles": ["investigator"],
                "status": "delivered",
                "submitted_at": now,
                "deliveries": [
                    {
                        "strategy_id": strategy.id,
                        "role": "investigator",
                        "status": "delivered",
                        "attempts": [
                            {"step_id": step_id, "status": "delivered", "delivered_at": now}
                        ],
                    }
                ],
            }
        ],
    }
    research_sessions._save(str(path), record)
    recovered = research_sessions.get_session(str(path), session_id)
    assert recovered["status"] == "paused"
    assert recovered["steps"][0]["status"] == "interrupted"
    delivery = recovered["interventions"][0]["deliveries"][0]
    assert delivery["status"] == "queued" and delivery["attempts"][0]["status"] == "interrupted"
    assert recovered["calls_used"] == 1
    assert "intervention.delivery_interrupted" in [event["kind"] for event in recovered["events"]]

    first = asyncio.run(
        research_sessions.submit_intervention(
            str(path),
            session_id,
            "priority",
            "Try the finite exceptional case first.",
            [strategy.id],
            ["investigator"],
        )
    )["interventions"][-1]
    second = asyncio.run(
        research_sessions.submit_intervention(
            str(path),
            session_id,
            "priority",
            "Instead test the boundary case first.",
            [strategy.id],
            ["investigator"],
            first["id"],
        )
    )["interventions"][-1]
    current = research_sessions.get_session(str(path), session_id)
    assert (
        next(item for item in current["interventions"] if item["id"] == first["id"])["status"]
        == "superseded"
    )
    assert second["status"] == "queued"
    for index in range(21):
        asyncio.run(
            research_sessions.submit_intervention(
                str(path),
                session_id,
                "priority",
                f"Bounded repeat guidance {index}.",
                [strategy.id],
                ["investigator"],
            )
        )
    try:
        asyncio.run(
            research_sessions.submit_intervention(
                str(path),
                session_id,
                "priority",
                "This request exceeds the accepted guidance bound.",
                [strategy.id],
                ["investigator"],
            )
        )
    except ProjectError as exc:
        assert "24-feedback limit" in str(exc)
    else:
        raise AssertionError("A session must reject guidance past its explicit bound")
    bounded = research_sessions.get_session(str(path), session_id)
    assert sum(item["status"] != "rejected" for item in bounded["interventions"]) == 24
    assert bounded["interventions"][-1]["status"] == "rejected"

    record = research_sessions._read(str(path), session_id)
    record["status"] = "ended"
    research_sessions._save(str(path), record)
    try:
        asyncio.run(
            research_sessions.submit_intervention(
                str(path),
                session_id,
                "objection",
                "This arrives after termination.",
                [strategy.id],
                ["skeptic"],
            )
        )
    except ProjectError as exc:
        assert "rejected and recorded" in str(exc)
    else:
        raise AssertionError("A terminal-session intervention must be rejected")
    final = research_sessions.get_session(str(path), session_id)
    assert final["interventions"][-1]["status"] == "rejected"
    assert "intervention.rejected" in [event["kind"] for event in final["events"]]


def test_epistemic_presentation_is_conservative_and_read_only() -> None:
    archive = Path(__file__).resolve().parents[1] / (
        "docs/evaluations/fixtures/t17-8-answer-free/"
        "live-session-91e96112-27ce-412e-841f-5cbf67cbba75.json"
    )
    archive_bytes = archive.read_bytes()
    original = json.loads(archive_bytes)["research_sessions"][0]
    for code, expected in (
        ("incomplete", "Incomplete"),
        ("convincing_unverified", "Convincing but unverified"),
        ("unknown", "Unknown"),
        ("verified", "Reported verified; not independently checked by SIGMA"),
        (None, "Unknown"),  # legacy derived default, never written back
    ):
        for status in ("ended", "failed"):
            for structured in (True, False):
                record = deepcopy(original)
                record["status"] = status
                for artifact in record["artifacts"]:
                    review = artifact["objective_review"]
                    if code is None:
                        review.pop("verification_status", None)
                    else:
                        review["verification_status"] = code
                    if structured:
                        # Representation fixture only, not an enriched historical proof.
                        review["argument_steps"] = [
                            {
                                "number": 1,
                                "title": "Representation fixture",
                                "argument": "This tests structured availability, not mathematical validity.",
                                "epistemic_status": "conjecture",
                                "basis_artifact_ids": [],
                            }
                        ]
                before = deepcopy(record)
                outcome = research_sessions._outcome(record)
                assert outcome["verification_label"] == expected
                if code != "convincing_unverified":
                    assert outcome["assessment"] == "mixed"
                    assert "Complete reviewed candidate answer" not in outcome["conclusion"]
                assert expected in outcome["conclusion"]
                if code != "convincing_unverified":
                    assert "convincing but unverified candidate" not in " ".join(outcome["caveats"])
                public = research_sessions._public(record)
                assert public["outcome"]["verification_label"] == expected
                metric = next(
                    item
                    for item in public["outcome"]["metrics"]["research_quality"]
                    if item["label"] == "Verification status"
                )
                assert metric["value"] == expected
                availability = public["outcome"]["argument_availability"]
                assert availability["status"] == ("structured" if structured else "narrative")
                if not structured:
                    assert "saved narrative is available" in availability["label"]
                    assert "unstructured argument, unassessed" in outcome["label"]
                    assert (
                        "cannot be assessed as a complete argument from this record"
                        not in outcome["summary"]
                    )
                    # Historical summaries remain available without being
                    # misattributed as an agent-authored Conclusion.
                    assert public["outcome"]["conclusion"] is None
                    assert public["outcome"]["summary"]
                assert record == before
    # Absence and partial work remain distinct from a recorded candidate narrative.
    partial = deepcopy(original)
    partial["artifacts"][-1]["objective_review"]["status"] = "partial"
    partial["artifacts"][-1]["objective_review"]["verification_status"] = "incomplete"
    assert research_sessions._outcome(partial)["verification_label"] == "Incomplete"
    empty = research_sessions._outcome({"status": "failed", "artifacts": []})
    assert empty["verification_label"] == "Not recorded"
    assert empty["argument_availability"]["status"] == "not_recorded"
    from sigma.research_epistemics import argument_availability

    assert argument_availability({"claim": "An assertion alone"})["status"] == "not_recorded"
    assert archive.read_bytes() == archive_bytes


def test_source_readiness_distinguishes_content_from_verification():
    """Typed source availability is domain-neutral and never proof certification."""
    source = {
        "id": "saved-evidence",
        "assumptions": ["Samples were randomly assigned"],
        "assumptions_reviewed": ["  samples WERE randomly   assigned "],
        "reasoning_steps": [
            {
                "argument": "Under the recorded sampling procedure the two groups differ.",
                "review": {"disposition": "accepted", "objection": ""},
            }
        ],
        "extract_truncated_fields": [],
    }
    readiness = research_sessions._finding_source_readiness
    assert readiness(source) == {
        "state": "model_reviewed_steps",
        "assumptions": "model_reviewed",
        "original_in_context": False,
        "independently_verified": False,
    }
    disputed = deepcopy(source)
    disputed["assumptions_reviewed"] = ["Different selection procedure"]
    assert readiness(disputed)["assumptions"] == "requires_review"
    truncated = deepcopy(source)
    truncated["extract_truncated_fields"] = ["method", "reasoning_steps"]
    assert readiness(truncated)["state"] == "incomplete_extract"
    withdrawn = deepcopy(truncated)
    withdrawn["retracted_by_artifact_ids"] = ["retraction"]
    assert readiness(withdrawn)["state"] == "withdrawn"
    narrative = {"method": "Compare conflicting archive sources."}
    assert readiness(narrative)["state"] == "narrative_unverified"
    assert readiness(narrative)["assumptions"] == "none_declared"
    incomplete = {"reasoning_steps": [{"argument": "A hypothesis, not a finding."}]}
    assert readiness(incomplete)["state"] == "unresolved_steps"


def test_saved_followup_question_selection():
    """A newer terminal outcome must block stale or unprovided follow-ups."""

    def session(
        number,
        strategy_id,
        decision="stop_budget_exhausted",
        stop_reason="recoverable_objection",
        assessment="continue",
        retracted=False,
    ):
        artifact = {
            "id": f"artifact-{number}",
            "strategy_id": strategy_id,
            "coordinator_decision": decision,
            "next_question": "" if decision == "stop_budget_exhausted" else "New bounded test",
            "skeptic_output": {
                "stop_reason": stop_reason,
                "assessment": assessment,
                "next_question": "New bounded test",
            },
            "objective_review": {"status": "partial"},
        }
        if retracted:
            artifact["retracted_by_artifact_ids"] = ["later-retraction"]
        return {
            "id": f"session-{number}",
            "session_number": number,
            "status": "ended",
            "created_at": f"2026-10-25T00:00:{number:02d}Z",
            "artifacts": [artifact],
        }

    older = session(1, "A")
    current = session(2, "A")
    peer = session(3, "B")
    supplied = [
        {
            "strategy_id": strategy,
            "id": f"artifact-{number}",
            "session_id": f"session-{number}",
            "next_question": "",
            "skeptic_output": {"next_question": "New bounded test"},
            "extract_truncated_fields": [],
        }
        for number, strategy in ((1, "A"), (2, "A"), (3, "B"))
    ]
    select = research_sessions._saved_followup_questions
    result = select([older, current, peer], ["A", "B"], supplied)
    assert result["A"]["artifact_id"] == "artifact-2"
    assert result["A"]["source_field"] == "skeptic_output.next_question"
    assert result["A"]["status"] == "model_suggested_unverified"
    assert result["B"]["artifact_id"] == "artifact-3"
    assert select([older, current], ["A"], supplied[:1]) == {}
    # A shortened material scope cannot silently authorize carrying a question.
    shortened: list[dict[str, Any]] = [dict(item) for item in supplied]
    shortened[1]["extract_truncated_fields"] = ["assumptions"]
    assert select([older, current], ["A"], shortened) == {}
    # Truncating an unused source field does not invalidate the Skeptic's
    # complete, separately supplied next question.
    shortened[1]["extract_truncated_fields"] = ["next_question"]
    assert select([older, current], ["A"], shortened)["A"]["artifact_id"] == "artifact-2"
    shortened[1]["extract_truncated_fields"] = ["skeptic_output.next_question"]
    assert select([older, current], ["A"], shortened) == {}
    # A shortened *argument* does not invalidate a bounded next test by itself.
    shortened[1]["extract_truncated_fields"] = ["reasoning_steps"]
    assert select([older, current], ["A"], shortened)["A"]["artifact_id"] == "artifact-2"
    for blocked in (
        session(2, "A", stop_reason="decisive_counterexample"),
        session(2, "A", stop_reason="productive_conclusion"),
        session(2, "A", stop_reason="no_progress"),
        session(2, "A", retracted=True),
        session(2, "A", decision="stop_no_progress"),
        session(2, "A", assessment="stop"),
    ):
        assert select([older, blocked], ["A"], supplied) == {}
    assert select([older, peer], ["A"], supplied)["A"]["artifact_id"] == "artifact-1"
    assert select([older], ["B"], supplied) == {}

    # A matching artifact ID does not establish that the same complete
    # question and historical session are visible in the frozen role context.
    absent = deepcopy(supplied)
    absent[1]["skeptic_output"] = {}
    assert select([older, current], ["A"], absent) == {}
    mismatch = deepcopy(supplied)
    mismatch[1]["skeptic_output"]["next_question"] = "Conflicting proposal"
    assert select([older, current], ["A"], mismatch) == {}
    foreign = deepcopy(supplied)
    foreign[1]["session_id"] = "session-1"
    assert select([older, current], ["A"], foreign) == {}
    missing_session = deepcopy(supplied)
    del missing_session[1]["session_id"]
    assert select([older, current], ["A"], missing_session) == {}
    duplicate = deepcopy(supplied)
    duplicate.append(deepcopy(duplicate[1]))
    assert select([older, current], ["A"], duplicate) == {}
    competing_strategy = deepcopy(supplied)
    competing_strategy[1]["strategy_id"] = "B"
    assert select([older, current], ["A"], competing_strategy) == {}

    # A manually interrupted or failed later run is not a new automatic
    # endorsement of the latest question. It also blocks stale fallback.
    for state in ("queued", "running", "paused", "stopped", "failed"):
        interrupted = deepcopy(current)
        interrupted["status"] = state
        assert select([older, interrupted], ["A"], supplied) == {}

    # A completed record with its exact artifact question is also supported.
    active = session(2, "A", decision="continue")
    complete = deepcopy(supplied)
    complete[1]["next_question"] = "New bounded test"
    assert select([older, active], ["A"], complete)["A"]["source_field"] == (
        "artifact.next_question"
    )
    complete[1]["next_question"] = "Incomplete or altered question"
    assert select([older, active], ["A"], complete) == {}


async def test_saved_followup_question_reaches_real_dispatch(path: Path):
    """A budget-ended model suggestion is carried by ID, not treated as approval."""
    view, strategy, credential, config = await setup(path)
    other = create_strategy(
        path, "Independent history inquiry", "Evaluate source reliability in a bounded archive."
    ).project.strategies[-1]
    limits = research_sessions.get_limits(str(path))
    limits.update(research_rounds=1, model_calls=2)
    research_sessions.save_limits(str(path), limits)
    phase = "seed"
    seen = []
    later_dispatched = asyncio.Event()
    question = (
        "Check a specific edge case using the earlier observation, not a new project-wide claim."
    )

    async def handler(request):
        nonlocal phase
        payload = json.loads(request.content)
        context = json.loads(payload["input"])
        role = payload["text"]["format"]["name"]
        seen.append((phase, role, context))
        if phase == "later":
            if context["strategy"]["id"] == strategy.id:
                later_dispatched.set()
            await asyncio.Event().wait()
        if role == "research_investigator":
            return httpx.Response(200, json=provider_response(investigation(1)))
        response = skeptic(1, "continue", "recoverable_objection")
        response["next_question"] = question
        return httpx.Response(200, json=provider_response(response))

    with (
        patch.object(research_sessions, "auth_context", new=AsyncMock(return_value=credential)),
        patch.object(research_sessions, "configuration", new=AsyncMock(return_value=config)),
        patch.object(research_sessions, "execution_capabilities", return_value=[]),
        patch(
            "sigma.research_sessions.httpx.AsyncClient",
            side_effect=lambda **kwargs: REAL_CLIENT(
                transport=httpx.MockTransport(handler), **kwargs
            ),
        ),
    ):
        first = await research_sessions.start_session(
            str(path), strategy.id, str(uuid4()), view.project.id, credential["identity"]
        )
        ended = await wait_for(path, first["id"])
        assert ended["status"] == "ended" and len(ended["artifacts"]) == 1
        artifact = ended["artifacts"][0]
        assert artifact["coordinator_decision"] == "stop_budget_exhausted"
        assert artifact["next_question"] == ""
        assert artifact["skeptic_output"]["next_question"] == question
        original_bytes = (path / "research-sessions" / f"{ended['id']}.json").read_bytes()

        limits.update(model_calls=4)
        research_sessions.save_limits(str(path), limits)
        phase = "later"
        next_session = await research_sessions.start_session(
            str(path),
            strategy.id,
            str(uuid4()),
            view.project.id,
            credential["identity"],
            strategy_ids=[strategy.id, other.id],
        )
        branches = {row["strategy_id"]: row for row in next_session["strategy_runs"]}
        assert branches[strategy.id]["current_question"] == question
        assert branches[other.id]["current_question"].startswith("Advance this strategy")
        source = branches[strategy.id]["initial_question_source"]
        assert source["artifact_id"] == artifact["id"]
        assert source["session_id"] == ended["id"]
        assert source["status"] == "model_suggested_unverified"
        assert next_session["current_question"] == question
        await asyncio.wait_for(later_dispatched.wait(), 2)
        carried = next(
            context
            for stage, role, context in seen
            if stage == "later"
            and role == "research_investigator"
            and context["strategy"]["id"] == strategy.id
        )
        assert carried["question"] == question
        assert carried["question_source"] == source
        assert artifact["id"] in carried["prior_session_artifact_ids"]
        source_finding = next(
            finding
            for finding in carried["prior_session_findings"]
            if finding["id"] == artifact["id"]
        )
        assert source_finding["skeptic_output"]["next_question"] == question
        assert source_finding["source_readiness"]["independently_verified"] is False
        assert source_finding["source_readiness"]["original_in_context"] is False
        await research_sessions.control_session(str(path), next_session["id"], "stop")

        # Researcher-approved continuations have priority over automatic suggestions.
        approved = {
            strategy.id: {
                "question": "Researcher-approved, narrower follow-up",
                "parent_strategy_id": strategy.id,
                "sources": [],
                "rejected_sources": [],
                "packet_digest": "offline-test-only",
            }
        }
        with (
            patch("sigma.continuations.approved_packets", return_value=approved),
            patch.object(research_sessions, "_worker", new=AsyncMock()),
        ):
            override = await research_sessions.start_session(
                str(path), strategy.id, str(uuid4()), view.project.id, credential["identity"]
            )
            assert override["current_question"] == approved[strategy.id]["question"]
            assert "initial_question_source" not in override
            await research_sessions.control_session(str(path), override["id"], "stop")
        assert (path / "research-sessions" / f"{ended['id']}.json").read_bytes() == original_bytes


async def test_cross_domain_continuation_dispatch_with_offline_roles(path: Path):
    """One saved question must carry across domains without answer-key tuning.

    Real project persistence and provider dispatch are exercised; the roles
    themselves are scripted local HTTP fixtures, not research judgments.
    """
    cases = (
        (
            "biology",
            "Does an observed growth change survive control for batch effects?",
            "Growth under different reagent conditions",
            "Reagent and culture batches were assigned independently.",
            "Compare within-batch replicate growth estimates before any causal claim.",
        ),
        (
            "default",
            "Which of two conflicting archive accounts has stronger provenance?",
            "Source criticism and competing archive accounts",
            "The two documents refer to the same recorded event.",
            "Inspect custody and dating for each original source before reconciliation.",
        ),
        (
            "military",
            "Which routing plan satisfies bounded resource constraints?",
            "Assess a fictional logistics scenario under stated limits",
            "The simulated route capacity remains constant during the scenario.",
            "Test whether the alternative route remains feasible under reduced capacity.",
        ),
        (
            "mathematical",
            "Does a bounded numerical pattern generalize?",
            "Test a finite case without asserting a universal theorem",
            "The proposed recurrence is restricted to nonnegative indices.",
            "Check the first unsampled index against the proposed recurrence.",
        ),
    )
    for index, (mode, question, approach, assumption, followup) in enumerate(cases):
        root = path / f"domain-{index}.sigma"
        view = initialize_project(root, f"Cross-domain case {index}", question, research_mode=mode)
        strategy = create_strategy(root, "Bounded local test", approach).project.strategies[0]
        limits = research_sessions.get_limits(str(root))
        limits.update(research_rounds=1, model_calls=2)
        research_sessions.save_limits(str(root), limits)
        credential = {
            "identity": "offline-case",
            "mode": "api_key",
            "token": "fixture-token",
            "status": "connected",
        }
        config = {"available": True, "model": MODEL, "reasoning_effort": "high"}
        state = {"phase": "seed", "captured": [], "dispatched": asyncio.Event()}

        async def handler(request, *, case=(mode, assumption, followup), state=state):
            case_mode, case_assumption, case_followup = case
            context = json.loads(json.loads(request.content)["input"])
            role = json.loads(request.content)["text"]["format"]["name"]
            state["captured"].append((state["phase"], role, context))
            if state["phase"] == "later":
                state["dispatched"].set()
                await asyncio.Event().wait()
            if role == "research_investigator":
                response = investigation(1)
                response["claim"] = f"Unverified local claim for {case_mode}"
                response["assumptions"] = [case_assumption]
                response["evidence_status"] = "Scripted proposition, not verified."
            else:
                response = skeptic(1, "continue", "recoverable_objection")
                response["assumptions_reviewed"] = [case_assumption]
                response["next_question"] = case_followup
            return httpx.Response(200, json=provider_response(response))

        with (
            patch.object(research_sessions, "auth_context", new=AsyncMock(return_value=credential)),
            patch.object(research_sessions, "configuration", new=AsyncMock(return_value=config)),
            patch.object(research_sessions, "execution_capabilities", return_value=[]),
            patch(
                "sigma.research_sessions.httpx.AsyncClient",
                side_effect=lambda **kwargs: REAL_CLIENT(
                    transport=httpx.MockTransport(handler), **kwargs
                ),
            ),
        ):
            first = await research_sessions.start_session(
                str(root), strategy.id, str(uuid4()), view.project.id, credential["identity"]
            )
            ended = await wait_for(root, first["id"])
            assert ended["status"] == "ended"
            assert ended["artifacts"][0]["coordinator_decision"] == "stop_budget_exhausted"
            saved = (root / "research-sessions" / f"{ended['id']}.json").read_bytes()
            state["phase"] = "later"
            limits.update(model_calls=4)
            research_sessions.save_limits(str(root), limits)
            later = await research_sessions.start_session(
                str(root), strategy.id, str(uuid4()), view.project.id, credential["identity"]
            )
            assert later["current_question"] == followup
            assert later["initial_question_source"]["artifact_id"] == ended["artifacts"][0]["id"]
            await asyncio.wait_for(state["dispatched"].wait(), 2)
            contexts = [
                context
                for stage, role, context in state["captured"]
                if stage == "later" and role == "research_investigator"
            ]
            assert contexts and contexts[0]["question"] == followup
            assert contexts[0]["question_source"] == later["initial_question_source"]
            finding = next(
                row
                for row in contexts[0]["prior_session_findings"]
                if row["id"] == ended["artifacts"][0]["id"]
            )
            assert finding["skeptic_output"]["next_question"] == followup
            assert finding["source_readiness"]["independently_verified"] is False
            assert finding["source_readiness"]["assumptions"] == "model_reviewed"
            assert finding["strategy_id"] == strategy.id
            await research_sessions.control_session(str(root), later["id"], "stop")
            assert (root / "research-sessions" / f"{ended['id']}.json").read_bytes() == saved


def test_outcome_includes_derived_execution_provenance() -> None:
    record = {
        "id": "saved-session",
        "status": "ended",
        "artifacts": [
            {
                "id": "saved-finding",
                "coordinator_decision": "continue",
                "claim_or_question": "Unverified model proposal",
                "skeptic_response": "No successful computation was observed.",
                "investigator_output": {
                    "python_execution": {
                        "id": "saved-execution",
                        "status": "timeout",
                        "source": "print('unobserved')",
                        "stderr": "Timed out",
                    }
                },
            }
        ],
        "steps": [],
    }
    original = deepcopy(record)
    outcome = research_sessions._outcome(record)
    provenance = outcome["execution_provenance"]
    assert provenance["completed_count"] == 0
    assert provenance["records"][0]["id"] == "saved-execution"
    assert provenance["records"][0]["statuses"] == ["timeout"]
    assert provenance["records"][0]["artifact_ids"] == ["saved-finding"]
    assert record == original


def test_cost_limit_outcome_preserves_partial_cycle_reason() -> None:
    strategy_id = str(uuid4())
    branch = {
        "strategy_id": strategy_id,
        "strategy_title": "Direct counting",
        "status": "ended",
        "current_action": "Cost limit",
        "cycle": 1,
        "calls_used": 1,
        "reason": "A conservative cost reserve prevented another provider call.",
    }
    record = {
        "status": "ended",
        "cycle": 1,
        "cycle_limit": 3,
        "calls_used": 1,
        "call_limit": 6,
        "terminal_reason": f"Direct counting: {branch['reason']}",
        "strategy_runs": [branch],
        "steps": [{"strategy_id": strategy_id, "cycle": 1, "role": "investigator"}],
        "artifacts": [],
    }
    message = research_sessions._portfolio_cost_limit_message(record, [branch])
    assert message is not None
    assert "round 1 of 3" in message
    assert "1/6 agent turns" in message
    assert "No Skeptic agent turn was dispatched" in message
    outcome = research_sessions._outcome_without_metrics(record)
    assert "conservative cost reserve" in outcome["summary"]
    assert "conservative cost reserve" in outcome["caveats"][-1]


def test_unknown_provider_attempt_keeps_held_session_cost() -> None:
    record = {
        "model": MODEL,
        "cost_status": "unavailable",
        "estimated_cost_usd": None,
        "estimated_cost_reserved_usd": 0.24,
        "steps": [
            {
                "status": "completed",
                "token_usage": {
                    "input_tokens": 10_000,
                    "cached_input_tokens": 0,
                    "output_tokens": 4_000,
                },
            },
            {"status": "failed", "attempt_status": "unknown"},
        ],
    }
    step = {"cost_reserve": 0.24}

    research_sessions._retain_unknown_cost_reservation(record, step)

    assert record["cost_status"] == "available"
    assert record["estimated_cost_usd"] == research_sessions._estimate_cost(
        MODEL, record["steps"][0]["token_usage"]
    )
    assert record["estimated_cost_reserved_usd"] == 0.24


def test_sponsored_unlimited_cost_still_reserves_global_call_spend() -> None:
    record = {
        "mode": "chatgpt",
        "model": MODEL,
        "reasoning_effort": "high",
        "cloud_sponsored": True,
        "maximum_estimated_cost_usd": None,
        "output_token_limit": 12_000,
    }
    reserve = research_sessions._call_cost_reservation(
        record, {"problem": "A bounded test"}, "investigator", None
    )
    assert reserve is not None and reserve > 0
    assert (
        research_sessions._call_cost_reservation(
            {**record, "cloud_sponsored": False, "mode": "api_key"},
            {"problem": "A bounded test"},
            "investigator",
            None,
        )
        is None
    )

    branch = {
        "strategy_title": "Tadpole mechanism",
        "current_action": "Budget limit",
        "reason": "Cloud inference cannot be bounded for this model.",
    }
    message = research_sessions._portfolio_limit_message(
        {"cycle": 1, "cycle_limit": 3, "calls_used": 0, "call_limit": 30, "steps": []},
        [branch],
    )
    assert message is not None
    assert "account or global spending budget" in message
    assert "Cloud inference cannot be bounded" in message


def test_sponsored_portfolio_serializes_allowance_reservations() -> None:
    with patch.object(research_sessions.cloud_research, "billing_enabled", return_value=True):
        assert research_sessions._portfolio_call_concurrency() == 1
    with patch.object(research_sessions.cloud_research, "billing_enabled", return_value=False):
        assert research_sessions._portfolio_call_concurrency() == 3


def test_project_cost_denial_reports_affordable_first_call() -> None:
    from sigma.research_budget import new_ledger, reserve_before_dispatch

    ledger = new_ledger(
        call_limit=2,
        input_token_limit=100_000,
        output_tokens_per_call=4_000,
        cost_limit_usd=0.05,
        input_price_per_million=2.5,
        output_price_per_million=10.0,
    )
    try:
        reserve_before_dispatch(ledger, call_id=str(uuid4()), request_body=b"{}")
    except BudgetExceeded as exc:
        message = str(exc)
        assert "reserved cost limit would be exceeded" in message
        assert "$0.0605" in message
        assert "$0.0500" in message
        assert "No provider call was dispatched" in message
        assert "session cost allowance" in message
    else:
        raise AssertionError("A $0.05 session cap funded a $0.0605 provider reserve")
    assert ledger["calls"] == []


def main():
    test_backend_build_is_pinned_at_backend_start()
    test_project_cost_denial_reports_affordable_first_call()
    test_outcome_includes_derived_execution_provenance()
    test_cost_limit_outcome_preserves_partial_cycle_reason()
    test_unknown_provider_attempt_keeps_held_session_cost()
    test_sponsored_unlimited_cost_still_reserves_global_call_spend()
    test_transient_provider_failure_classes_are_bounded_and_permanent_errors_not_retried()
    test_portfolio_termination_does_not_promote_scheduler_terminal_to_research_success()
    test_sponsorship_does_not_shorten_project_duration()
    test_rate_limit_retry_observes_provider_retry_after_and_minimum_backoff()
    test_sponsored_portfolio_serializes_allowance_reservations()
    test_epistemic_presentation_is_conservative_and_read_only()
    test_source_readiness_distinguishes_content_from_verification()
    test_saved_followup_question_selection()
    test_request_audit_truncation_tokens_and_reconciliation()
    with TemporaryDirectory() as temporary:
        root = Path(temporary)
        asyncio.run(
            test_unlimited_duration_completes_without_session_deadline(root / "unlimited.sigma")
        )
        asyncio.run(test_transient_timeout_retries_as_a_new_accounted_turn(root / "retry.sigma"))
        asyncio.run(
            test_repeated_transient_failures_are_isolated_and_explained(root / "repeat.sigma")
        )
        asyncio.run(
            test_last_affordable_provider_failure_names_failure_and_exhaustion(
                root / "last-turn.sigma"
            )
        )
        asyncio.run(
            test_last_shared_turn_failure_survives_terminal_sibling_finalization(
                root / "last-shared-turn-multistrategy.sigma"
            )
        )
        asyncio.run(
            test_expired_deadline_preserves_sibling_partial_artifacts(
                root / "deadline-scheduler.sigma"
            )
        )
        asyncio.run(test_portfolio_retry_wrapper_has_a_hard_attempt_bound())
        test_project_concurrency_max_four_and_legacy_read(root)
        asyncio.run(test_disabled_strategy_never_starts_a_run(root / "disabled.sigma"))
        asyncio.run(
            test_project_concurrent_session_limit_is_atomic(root / "concurrency-limit.sigma")
        )
        asyncio.run(test_distinct_portfolio_sessions_dispatch_simultaneously(root))
        asyncio.run(
            test_stop_one_session_does_not_cancel_sibling_and_resume_keeps_work(
                root / "sibling-stop-resume.sigma"
            )
        )
        asyncio.run(
            test_foreign_worker_lock_blocks_resume_and_removal(root / "foreign-worker-owner.sigma")
        )
        asyncio.run(test_three_cycles_and_idempotency(root / "cycles.sigma"))
        asyncio.run(
            test_legacy_worker_aggregates_usage_and_audits_inputs(root / "legacy-worker.sigma")
        )
        asyncio.run(test_investigator_python_is_run_and_reviewed(root / "python-review.sigma"))
        asyncio.run(test_recovery_reuses_saved_python_execution(root / "python-recovery.sigma"))
        asyncio.run(test_restart_during_python_has_no_automatic_rerun(root / "python-crash.sigma"))
        asyncio.run(test_failed_experiment_is_reused_then_revised(root / "python-revision.sigma"))
        asyncio.run(test_portfolio_python_queue_and_stop(root / "python-queue.sigma"))
        asyncio.run(
            test_stop_during_python_execution_preserves_provenance(root / "python-stop.sigma")
        )
        asyncio.run(test_new_session_receives_prior_saved_findings(root / "continuation.sigma"))
        asyncio.run(
            test_saved_followup_question_reaches_real_dispatch(
                root / "saved-question-continuation.sigma"
            )
        )
        asyncio.run(test_cross_domain_continuation_dispatch_with_offline_roles(root))
        asyncio.run(
            test_failed_attempt_guides_next_session_with_provenance(
                root / "failed-continuation.sigma"
            )
        )
        test_prior_session_failure_history_prioritizes_newest_attempts(
            root / "failure-recency.sigma"
        )
        test_continuation_context_is_bounded(root / "continuation-stress.sigma")
        test_t37_context_selection_is_stable_and_loss_visible(root / "t37-context.sigma")
        test_t37_obligation_identity_lifecycle_and_history(root / "t37-obligation-review.sigma")
        asyncio.run(test_t37_mandatory_context_blocks_before_provider(root / "t37-blocked.sigma"))
        asyncio.run(test_pause_counts_interrupted_call(root / "pause.sigma"))
        asyncio.run(test_malformed_output_and_restart(root / "recovery.sigma"))
        asyncio.run(
            test_clipped_investigator_automatically_recovers(root / "clipped-auto-recovery.sigma")
        )
        asyncio.run(
            test_legacy_ended_clipped_response_can_resume(root / "clipped-legacy-resume.sigma")
        )
        asyncio.run(test_chatgpt_stream(root / "chatgpt.sigma"))
        asyncio.run(
            test_portfolio_stops_after_chatgpt_usage_limit(root / "chatgpt-http-limit.sigma")
        )
        asyncio.run(
            test_portfolio_stops_after_chatgpt_usage_limit(
                root / "chatgpt-sse-limit.sigma", streamed=True
            )
        )
        asyncio.run(
            test_portfolio_stops_after_chatgpt_usage_limit(
                root / "chatgpt-sse-error-event.sigma", streamed=True, sse_error_event=True
            )
        )
        asyncio.run(
            test_session_deadline_bounds_generous_call_timeout(
                root / "generous-call-deadline.sigma"
            )
        )
        asyncio.run(test_limits_snapshot_and_usage_cost(root / "limits.sigma"))
        asyncio.run(
            test_prior_obligation_reference_compaction_keeps_text_and_traceability(
                root / "prior-obligation-compaction.sigma"
            )
        )
        asyncio.run(
            test_aggregate_prior_obligation_snapshot_retains_all_under_64kb(
                root / "prior-obligation-aggregate.sigma"
            )
        )
        asyncio.run(
            test_prior_obligation_overflow_allows_repeatable_bounded_research(
                root / "prior-obligation-overflow.sigma"
            )
        )
        test_limits_validation(root / "invalid-limits.sigma")
        test_shared_turn_schedule_accepts_strategy_count_changes()
        asyncio.run(
            test_pending_skeptic_uses_final_turn_and_deferred_outcome_is_specific(
                root / "portfolio-final-skeptic-turn.sigma"
            )
        )
        asyncio.run(
            test_adversarial_achieved_reviews_never_publish_unsupported_solution(
                root / "adversarial-achievement.sigma"
            )
        )
        asyncio.run(test_legacy_limits_are_preserved(root / "legacy-limits.sigma"))
        asyncio.run(test_single_project_admission(root / "single-session.sigma"))
        asyncio.run(
            test_remove_running_session_cancels_execution_and_releases_slot(
                root / "remove-running.sigma"
            )
        )
        asyncio.run(
            test_remove_racing_with_completion_is_idempotently_terminal(
                root / "remove-completion-race.sigma"
            )
        )
        asyncio.run(
            test_project_deletion_stops_all_active_sessions_first(
                root / "project-delete-active.sigma"
            )
        )
        asyncio.run(test_response_transport_and_parsed_bounds(root / "parsed.sigma"))
        asyncio.run(test_changed_bindings_pause_before_provider(root / "binding.sigma"))
        asyncio.run(test_storage_limit_pauses_without_artifact(root / "storage.sigma"))
        asyncio.run(test_remove_terminal_and_monotonic_number(root / "removal.sigma"))
        test_deliberate_argument_gap_is_preserved_and_not_complete()
        asyncio.run(
            test_maximum_regions_solution_and_frozen_attribution(root / "maximum-regions.sigma")
        )
        asyncio.run(
            test_answer_free_maximum_regions_prompt(root / "maximum-regions-answer-free.sigma")
        )
        asyncio.run(
            test_maximum_regions_false_candidate_is_rejected(
                root / "maximum-regions-counterexample.sigma"
            )
        )
        asyncio.run(test_concurrent_strategy_portfolio(root / "portfolio.sigma"))
        asyncio.run(
            test_portfolio_cross_strategy_reviews_ground_synthesis_in_peer_evidence(
                root / "portfolio-cross-review.sigma"
            )
        )
        asyncio.run(
            test_peer_finding_changes_target_investigator_after_stop_and_resume(
                root / "portfolio-peer-handoff.sigma"
            )
        )
        asyncio.run(
            test_portfolio_marks_unsuccessful_approach_without_mutating_strategy_pool(
                root / "portfolio-unsuccessful.sigma"
            )
        )
        asyncio.run(
            test_ten_strategy_portfolio_respects_concurrency_and_budget(
                root / "portfolio-ten.sigma"
            )
        )
        asyncio.run(
            test_forked_strategy_followup_preserves_parent_comparison(
                root / "portfolio-followup.sigma"
            )
        )
        asyncio.run(
            test_stop_concurrent_portfolio_preserves_completed_boundary(
                root / "portfolio-stop.sigma"
            )
        )
        asyncio.run(
            test_stop_reconciles_queued_portfolio_branches(root / "portfolio-stop-queued.sigma")
        )
        asyncio.run(
            test_portfolio_preflight_failure_terminates_instead_of_spinning(
                root / "portfolio-preflight-failure.sigma"
            )
        )
        asyncio.run(
            test_start_preflight_does_not_hold_project_or_global_admission_locks(
                root / "admission-preflight-locks.sigma"
            )
        )
        asyncio.run(
            test_start_revalidates_project_after_slow_preflight(
                root / "admission-preflight-revalidation.sigma"
            )
        )
        asyncio.run(
            test_portfolio_audits_mixed_preflight_failure_and_sibling_success(
                root / "portfolio-preflight-mixed-wave.sigma"
            )
        )
        asyncio.run(
            test_portfolio_preflight_timeout_pauses_without_spending_calls_and_recovers(
                root / "portfolio-preflight-timeout.sigma"
            )
        )
        asyncio.run(
            test_resume_limits_reconcile_portfolio_terminal_state(
                root / "portfolio-resume-limits.sigma"
            )
        )
        asyncio.run(
            test_portfolio_isolates_one_strategy_provider_failure(
                root / "portfolio-isolated-failure.sigma"
            )
        )
        asyncio.run(
            test_portfolio_timeout_is_not_misclassified_as_strategy_failure(
                root / "portfolio-timeout.sigma"
            )
        )
        asyncio.run(
            test_portfolio_rejects_fabricated_cross_strategy_references(
                root / "portfolio-fabricated-reference.sigma"
            )
        )
        test_portfolio_requires_reciprocal_complement_and_surfaces_conflicts()
        test_peer_handoff_noop_and_domain_mismatch_controls()
        test_peer_handoff_queue_defers_without_silent_loss()
        test_peer_handoff_deferred_storage_is_bounded_and_reports_overflow()
        asyncio.run(
            test_concurrent_human_guidance_is_delivered_and_attributed(
                root / "human-intervention-concurrent.sigma"
            )
        )
        asyncio.run(
            test_intervention_delivery_pause_resume_keeps_attempt_provenance(
                root / "human-intervention-resume.sigma"
            )
        )
        test_intervention_recovery_supersession_and_rejection(
            root / "human-intervention-recovery.sigma"
        )
        asyncio.run(
            test_portfolio_budget_too_small_for_next_pair_is_finalized(
                root / "portfolio-tight-budget.sigma"
            )
        )
        asyncio.run(
            test_three_strategies_launch_under_three_turn_shared_ceiling(
                root / "portfolio-three-turns.sigma"
            )
        )
        asyncio.run(
            test_incomplete_productive_stop_uses_remaining_round(
                root / "portfolio-incomplete-stop.sigma"
            )
        )
        asyncio.run(
            test_configured_cost_cap_reports_second_call_refusal(
                root / "portfolio-cost-cap-second-call.sigma"
            )
        )
        asyncio.run(
            test_session_token_and_hard_ledger_stops_are_diagnostic(
                root / "portfolio-token-hard-limit.sigma"
            )
        )
        asyncio.run(test_generic_objective_review_on_binary_strings(root / "binary-strings.sigma"))
        test_outcome_classification()
        test_session_listing_ignores_sequence_metadata(root / "session-sequence-metadata.sigma")
        test_outcome_conclusions_are_bounded_honest_and_synthesized(
            root / "outcome-conclusion.sigma"
        )
        test_outcome_metrics_from_persisted_evidence(root / "outcome-metrics.sigma")
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
    print("Persistent research session scenarios passed.")  # CI retrigger


if __name__ == "__main__":
    main()
