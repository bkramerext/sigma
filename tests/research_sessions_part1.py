# ruff: noqa: F401
# pyright: reportUndefinedVariable=false
"""Persistent A17 sessions use deterministic provider fixtures only."""

import asyncio
import json
import os
import shutil
import subprocess
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

from sigma import (
    agentic,
    papers,
    proposals,
    python_sandbox,
    research_preferences,
    research_presence,
    research_sessions,
    text_views,
)
from sigma.projects import (
    ProjectError,
    create_strategy,
    edit_strategy,
    initialize_project,
    inspect_project,
    project_path,
    set_strategy_enabled,
    update_project,
)
from sigma.research_budget import (
    BudgetExceeded,
    authorize_independent_review_after_unknown,
    increase_call_limit,
    mark_unknown,
    new_ledger,
    reserve_before_dispatch,
    settle_after_response,
    settle_rejected,
    totals,
)

# Legacy role-only fixtures deliberately leave the new compiler off.
# tests/reference_compiler_integration.py explicitly enables and tests it.
os.environ.setdefault("SIGMA_REFERENCE_COMPILATION_ENABLED", "false")

MODEL = "gpt-6.1-sol"
REAL_CLIENT = httpx.AsyncClient


def test_rejected_call_releases_hard_tokens_but_counts_attempt() -> None:
    ledger = new_ledger(
        call_limit=3,
        input_token_limit=200_000,
        output_tokens_per_call=4000,
        cost_limit_usd=5.0,
        input_price_per_million=1.0,
        output_price_per_million=10.0,
    )
    reserve_before_dispatch(ledger, call_id="rejected", request_body=b"test")
    settle_rejected(ledger, call_id="rejected")
    current = totals(ledger)
    assert current["calls_including_unknown"] == 1
    assert current["input_tokens_used_or_reserved"] == 0
    assert current["output_tokens_used_or_reserved"] == 0
    assert current["cost_usd_used_or_reserved"] == 0
    reserve_before_dispatch(ledger, call_id="next", request_body=b"another")
    assert totals(ledger)["calls_including_unknown"] == 2
    preserved_input_limit = ledger["input_token_limit"]
    preserved_cost_limit = ledger["cost_limit_usd"]
    assert increase_call_limit(ledger, 4) == (3, 4)
    assert ledger["call_limit"] == 4
    assert ledger["input_token_limit"] == preserved_input_limit
    assert ledger["cost_limit_usd"] == preserved_cost_limit
    settle_after_response(ledger, call_id="next", input_tokens=100, output_tokens=50)
    reserved = reserve_before_dispatch(ledger, call_id="uncertain", request_body=b"unknown")
    reserved_bounds = deepcopy(reserved)
    mark_unknown(ledger, call_id="uncertain")
    held = totals(ledger)
    assert held["blocked_reason"] == "Provider call outcome or usage is unknown"
    try:
        reserve_before_dispatch(ledger, call_id="premature", request_body=b"blocked")
    except BudgetExceeded:
        pass
    else:
        raise AssertionError("An unreviewed unknown call did not block provider dispatch")
    try:
        authorize_independent_review_after_unknown(ledger, uncertain_call_ids={"different-id"})
    except BudgetExceeded:
        pass
    else:
        raise AssertionError("The recovery ledger accepted mismatched uncertain calls")
    assert ledger["blocked_reason"] is not None
    # Invalid provider usage is *not* an unknown-dispatch review approval.
    ledger["blocked_reason"] = "Provider input usage exceeded or failed its reserved bound"
    try:
        authorize_independent_review_after_unknown(ledger, uncertain_call_ids={"uncertain"})
    except BudgetExceeded:
        pass
    else:
        raise AssertionError("Invalid usage was incorrectly converted into a recoverable call")
    ledger["blocked_reason"] = "Provider call outcome or usage is unknown"
    authorize_independent_review_after_unknown(ledger, uncertain_call_ids={"uncertain"})
    assert ledger["calls"][-1] == {**reserved_bounds, "status": "unknown"}
    assert totals(ledger)["input_tokens_used_or_reserved"] == held["input_tokens_used_or_reserved"]
    assert totals(ledger)["cost_usd_used_or_reserved"] == held["cost_usd_used_or_reserved"]
    reserve_before_dispatch(ledger, call_id="independent-skeptic", request_body=b"fresh-review")
    try:
        increase_call_limit(ledger, 3)
    except BudgetExceeded as exc:
        assert "only be increased" in str(exc)
    else:
        raise AssertionError("A research call ceiling was reduced")


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
        provider_request_id="req_safe-123",
        response_shape="responses-error",
        provider_limit_headers={
            "x-codex-primary-used-percent": "100",
            "set-cookie": "secret=session",
        },
    )
    assert research_sessions._provider_failure_fields(rate_limit)["failure_kind"] == (
        "provider_rate_limited"
    )
    assert research_sessions._provider_failure_fields(rate_limit)["provider_request_id"] == (
        "req_safe-123"
    )
    assert research_sessions._provider_failure_fields(rate_limit)["provider_response_shape"] == (
        "responses-error"
    )
    assert research_sessions._provider_failure_fields(rate_limit)["provider_limit_headers"] == {
        "x-codex-primary-used-percent": "100"
    }
    assert research_sessions._transient_failure_kind(rate_limit) == "provider_rate_limited"
    account_limit = research_sessions.ChatGPTProviderRejection(
        "plan usage limit",
        state="limited",
        code="subscription_sharing_usage_limit_exceeded",
        http_status=429,
        streamed=False,
    )
    assert research_sessions._transient_failure_kind(account_limit) is None
    project_hard_limit = research_sessions.ChatGPTProviderRejection(
        "OpenAI API project hard spending limit reached",
        state="limited",
        code="project_spend_limit_exceeded",
        http_status=429,
        streamed=False,
    )
    assert research_sessions._provider_failure_fields(project_hard_limit) == {
        "failure_kind": "provider_limited",
        "provider_http_status": 429,
        "provider_response_channel": "http",
        "provider_error_code": "project_spend_limit_exceeded",
    }
    assert research_sessions._transient_failure_kind(project_hard_limit) is None
    wrapped_project_cap = ProjectError(
        "OpenAI API rejected request (HTTP 429; project_spend_limit_exceeded)."
    )
    assert research_sessions._provider_failure_fields(wrapped_project_cap) == {
        "failure_kind": "provider_limited",
        "provider_http_status": 429,
        "provider_error_code": "project_spend_limit_exceeded",
    }
    assert research_sessions._transient_failure_kind(wrapped_project_cap) is None
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


def test_context_manifest_compaction_preserves_omission_accounting():
    """Audit pointers can shrink without erasing omitted research evidence."""
    manifest = {
        "sources": [
            {
                "category": "prior_session_obligation",
                "source_ids": [str(uuid4()) for _ in range(400)],
                "reason": "saved source identities",
                "representation": "bounded",
                "status": "selected",
            }
        ],
        "omitted_prior_session_obligations": {
            "count": 80,
            "obligation_ids": [str(uuid4()) for _ in range(80)],
            "reason": "saved originals remain available",
        },
    }
    research_sessions._bound_context_manifest(manifest)
    assert research_sessions._json_bytes(manifest) <= research_sessions.MAX_CONTEXT_MANIFEST_BYTES
    omitted = manifest["omitted_prior_session_obligations"]
    assert omitted["count"] == 80
    assert len(omitted["obligation_ids"]) + omitted["obligation_ids_not_listed_count"] == 80
    source = manifest["sources"][0]
    assert len(source["source_ids"]) + source["source_ids_not_listed_count"] == 400


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
    results = iter(["retry"] * 4)
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
    assert role_call.await_count == 4


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
    assert finished["termination_reason_code"] == "protocol_complete"
    assert "All 2 configured Investigator/Skeptic role turns" in finished["message"]
    assert "incomplete" not in finished["message"]
    assert finished["strategy_runs"][0]["status"] == "ended"
    assert finished["strategy_runs"][0]["last_decision"] == "stop_budget_exhausted"
    assert "saved findings remain unverified research notes" in finished["message"]


async def test_repeated_transient_failures_are_isolated_and_explained(path: Path):
    view, strategy, credential, config = await setup(path)
    limits = dict(research_sessions.DEFAULT_LIMITS)
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
    assert finished["calls_used"] == attempts == 3
    assert [step["status"] for step in finished["steps"]] == ["failed"] * 3
    assert all(step["failure_kind"] == "provider_temporary" for step in finished["steps"])
    assert branch["status"] == "failed"
    assert branch["recovery_attempts_exhausted"] is True
    assert finished["termination_reason_code"] == "provider_or_strategy_failure"
    assert "temporary error after two automatic retries" in finished["message"]
    assert "incomplete" in finished["message"]
    assert finished["artifacts"] == []


async def test_last_affordable_provider_failure_names_failure_and_exhaustion(path: Path):
    view, strategy, credential, config = await setup(path)
    limits = dict(research_sessions.DEFAULT_LIMITS)
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
    limits = dict(research_sessions.DEFAULT_LIMITS)
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
            if cycle == 2:
                raise httpx.ReadTimeout("final shared turn timed out")
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
    assert calls[-1] == (first.id, "research_skeptic", 2), (calls, finished["message"], branches)
    assert branches[first.id]["status"] == "failed"
    assert branches[first.id]["artifacts"]
    assert branches[first.id]["termination_reason_code"] == "timeout"
    assert branches[second.id]["status"] == "ended"
    assert [step["status"] for step in finished["steps"]].count("failed") == 1
    assert finished["steps"][-1]["failure_kind"] == "timeout"
    assert finished["termination_reason_code"] == "provider_or_strategy_failure"
    assert len(finished["artifacts"]) == 2
    assert "Saved approach: provider response timed out" in finished["message"]
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
    limits = dict(research_sessions.DEFAULT_LIMITS)
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
                provider_request_id="req_safe-123",
                provider_limit_headers={
                    "x-ratelimit-reset-requests": "1s",
                    "x-codex-secondary-used-percent": "36",
                    "authorization": "secret",
                    "x-codex-primary-used-percent": "100\\nsecret",
                },
            )
        except research_sessions.ChatGPTProviderRejection as exc:
            assert exc.retry_after_seconds == 17
            assert exc.provider_request_id == "req_safe-123"
            assert exc.response_shape == "responses-error"
            assert exc.code == "rate_limit_exceeded"
            assert exc.provider_limit_headers == {
                "x-ratelimit-reset-requests": "1s",
                "x-codex-secondary-used-percent": "36",
            }
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


def test_e002_stale_managed_backend_guard_blocks_paid_research() -> None:
    from sigma import build_info

    with patch.dict("os.environ", {"SIGMA_UI_INSTANCE_ID": "managed-instance"}):
        build_info.build_commit.cache_clear()
        try:
            with (
                patch.object(build_info, "build_commit", return_value="3" * 40),
                patch.object(build_info, "checkout_commit", return_value="4" * 40),
            ):
                assert build_info.local_build_mismatch() == ("3" * 40, "4" * 40)
            with patch.object(
                research_sessions, "local_build_mismatch", return_value=("3" * 40, "4" * 40)
            ):
                try:
                    research_sessions._require_current_local_backend()
                except ProjectError as exc:
                    assert "backend is stale" in str(exc)
                    assert "no research provider call" in str(exc)
                else:
                    raise AssertionError("Stale managed backend did not block research")
            with (
                patch.object(build_info, "build_commit", return_value="4" * 40),
                patch.object(build_info, "checkout_commit", return_value="4" * 40),
            ):
                assert build_info.local_build_mismatch() is None
        finally:
            build_info.build_commit.cache_clear()
    with patch.object(build_info, "checkout_commit", return_value="4" * 40):
        assert build_info.local_build_mismatch() is None


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


async def wait_for(path, session_id, terminal=True, *, timeout_seconds=15.0):
    # Check for inactivity, not a fixed end-to-end deadline: a deterministic
    # 54-call fixture can legitimately need more than a few seconds under CI.
    started_at = time.monotonic()
    latest_progress_at = started_at
    previous_progress = None
    while True:
        current = research_sessions.get_session(str(path), session_id)
        worker = research_sessions._tasks.get(session_id)
        settled = worker is None or worker.done()
        if (
            (current["status"] in {"completed", "ended", "failed", "stopped", "paused"} and settled)
            if terminal
            else current["calls_used"]
        ):
            return current
        now = time.monotonic()
        progress = (current["status"], current["calls_used"], len(current.get("steps", [])))
        if progress != previous_progress:
            latest_progress_at = now
            previous_progress = progress
        if now - latest_progress_at >= timeout_seconds or now - started_at >= max(
            120.0, timeout_seconds * 6
        ):
            raise AssertionError(
                "research worker did not make progress "
                f"(status={current['status']}, calls_used={current['calls_used']}, "
                f"worker_settled={settled}, inactive_seconds={now - latest_progress_at:.1f})"
            )
        await asyncio.sleep(0.01)


async def setup(path: Path):
    view = initialize_project(
        path, "Session project", "A bounded mathematical question", research_mode="mathematical"
    )
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


def test_project_type_research_references_replace_keyword_catalog(monkeypatch):
    from sigma import project_types, research_method_sources

    monkeypatch.setattr(project_types, "custom_types", list)
    for mode in (item.id for item in project_types.builtin_types()):
        selected = research_method_sources.select_method_sources(
            mode, "Unrelated title", "unrelated subject", (), ()
        )
        assert selected["status"] == "selected"
        assert selected["branch"] is None
        assert len(selected["sources"]) == 3, mode
        assert [item["tier"] for item in selected["sources"]] == [
            "general",
            "general",
            "discipline",
        ]
        assert all(item["project_type_id"] == "common" for item in selected["sources"][:2])
        assert all(item["project_type_id"] == mode for item in selected["sources"][2:])
        assert selected["advisory"] is None
        assert research_method_sources.methodology_digest(selected)
        later = research_method_sources.select_method_sources(
            mode,
            "Other",
            "Another problem",
            (),
            ({"id": "old-session", "research_method_sources": selected},),
        )
        assert later["status"] == "reused"
        assert later["sources"] == selected["sources"]
        assert later["source_session_id"] == "old-session"


def test_project_type_inheritance_more_than_three_is_advisory(monkeypatch):
    from sigma import project_types, research_method_sources

    refs = (
        {"name": "Special Method", "url": "https://example.org/special-method"},
        {"name": "Measurement", "url": "https://example.org/measurement"},
    )
    physics = next(t for t in project_types.builtin_types() if t.id == "physics")
    child = project_types.ProjectType(
        id="custom-physics",
        name="Special Physics",
        scope="Research",
        user_defined=True,
        icon=project_types.placeholder_icon(),
        based_on="physics",
        research_standards_references=refs + (physics.research_standards_references[0],),
    )
    monkeypatch.setattr(project_types, "custom_types", lambda: [child])
    selected = research_method_sources.select_method_sources(
        child.id, "This title should not change references", "", (), ()
    )
    assert [row["tier"] for row in selected["sources"]] == [
        "general",
        "general",
        "discipline",
        "branch",
        "branch",
    ]
    assert len({row["url"] for row in selected["sources"]}) == 5
    assert selected["advisory"] and "5 research-method references" in selected["advisory"]
    assert "not been independently inspected" in selected["sources"][-1]["notes"]

    revised = project_types.ProjectType(
        **{**child.__dict__, "research_standards_references": refs[:1]}
    )
    monkeypatch.setattr(project_types, "custom_types", lambda: [revised])
    changed = research_method_sources.select_method_sources(
        child.id, "", "", (), ({"id": "older", "research_method_sources": selected},)
    )
    assert changed["status"] == "selected"  # no stale reference reuse after edit
    assert len(changed["sources"]) == 4
    assert selected["sources"][-1]["url"] == refs[1]["url"]  # old snapshot immutable
    assert changed["advisory"]


def test_project_type_reference_ancestry_missing_and_cyclic_parents(monkeypatch):
    from sigma import project_types, research_method_sources

    root = project_types.ProjectType(
        id="custom-root",
        name="Root",
        scope="Research",
        user_defined=True,
        icon=project_types.placeholder_icon(),
        based_on="physics",
        research_standards_references=({"name": "Root", "url": "https://example.org/root"},),
    )
    leaf = project_types.ProjectType(
        id="custom-leaf",
        name="Leaf",
        scope="Research",
        user_defined=True,
        icon=project_types.placeholder_icon(),
        based_on="custom-root",
        research_standards_references=({"name": "Leaf", "url": "https://example.org/leaf"},),
    )
    monkeypatch.setattr(project_types, "custom_types", lambda: [root, leaf])
    resolved = research_method_sources.select_method_sources("custom-leaf", "", "", (), ())
    assert [r["project_type_id"] for r in resolved["sources"]] == [
        "common",
        "common",
        "physics",
        "custom-root",
        "custom-leaf",
    ]
    missing = project_types.ProjectType(**{**leaf.__dict__, "based_on": "not-found"})
    monkeypatch.setattr(project_types, "custom_types", lambda: [missing])
    assert (
        len(research_method_sources.select_method_sources("custom-leaf", "", "", (), ())["sources"])
        == 3
    )
    cyclic_root = project_types.ProjectType(**{**root.__dict__, "based_on": "custom-leaf"})
    monkeypatch.setattr(project_types, "custom_types", lambda: [cyclic_root, leaf])
    assert (
        len(research_method_sources.select_method_sources("custom-root", "", "", (), ())["sources"])
        == 4
    )


def test_project_type_methods_reach_both_agents_and_skeptic_challenges(monkeypatch):
    from sigma import project_types, research_method_sources

    custom = project_types.ProjectType(
        id="special",
        name="Special",
        scope="Research",
        user_defined=True,
        icon=project_types.placeholder_icon(),
        based_on="biology",
        research_standards_references=({"name": "Special", "url": "https://example.org/special"},),
    )
    monkeypatch.setattr(project_types, "custom_types", lambda: [custom])
    selected = research_method_sources.select_method_sources("special", "", "", (), ())
    context = {
        "problem": "A research problem",
        "investigation_type": "special",
        "research_method_version": research_sessions.RESEARCH_METHOD_VERSION,
        "methodology_source_material": selected["sources"],
        "methodology_source_catalog_version": selected["version"],
        "execution_tools": [],
    }
    record = {
        "mode": "chatgpt",
        "model": MODEL,
        "reasoning_effort": "high",
        "output_token_limit": 4000,
    }
    for role in ("investigator", "skeptic"):
        packet = research_sessions._role_request_payload(record, role, context)
        for source in selected["sources"]:
            assert source["url"] in packet["input"][0]["content"]
    assert "Review whether the Investigator's assumptions" in (
        research_sessions._role_instructions("skeptic", context)
    )
    assert "Review whether the Investigator's assumptions" not in (
        research_sessions._role_instructions("investigator", context)
    )
    assert "Scientifically justified departures are allowed" in (
        research_sessions._role_instructions("skeptic", context)
    )
    old = {**context, "methodology_source_catalog_version": "methodology-catalog-v1"}
    assert "Review whether the Investigator's assumptions" not in (
        research_sessions._role_instructions("skeptic", old)
    )


def test_research_methodology_outcome_is_not_claimed_as_independent_science():
    from sigma import research_method_sources

    selected = research_method_sources.select_method_sources(
        "physics", "Warp", "causal spacetime metric", (), ()
    )
    record = {
        "id": "method-test",
        "status": "queued",
        "steps": [],
        "artifacts": [],
        "strategy_runs": [],
        "research_method_sources": selected,
    }
    outcome = research_sessions._outcome(record)
    assert outcome["source_material"] == selected
    assert outcome["source_material"]["status"] == "selected"
    assert "verification_label" in outcome
    assert {r["url"] for r in outcome["source_material"]["sources"]} == {
        "https://www.nationalacademies.org/read/25303",
        "https://jbi-global-wiki.refined.site/download/attachments/355599504/JBI%20Manual%20for%20Evidence%20Synthesis%202024.pdf",
        "https://www.nationalacademies.org/read/13395/chapter/2",
    }


def test_phase2_methodology_routes_common_and_domain_methods_without_overfit():
    """Every current research mode gets a shared core and one suited lens."""
    from sigma.projects import ResearchMode

    assert set(research_sessions.RESEARCH_MODE_METHOD_GUIDANCE) == {
        mode.value for mode in ResearchMode
    }
    common = {
        "execution_tools": [],
        "research_method_version": research_sessions.RESEARCH_METHOD_VERSION,
    }
    math = {**common, "investigation_type": "mathematical"}
    physics = {**common, "investigation_type": "physics"}
    bio = {**common, "investigation_type": "biology"}
    systems = {**common, "investigation_type": "computer_science"}
    law = {**common, "investigation_type": "law"}
    math_inv = research_sessions._role_instructions("investigator", math)
    math_skep = research_sessions._role_instructions("skeptic", math)
    physics_inv = research_sessions._role_instructions("investigator", physics)
    bio_inv = research_sessions._role_instructions("investigator", bio)
    sys_inv = research_sessions._role_instructions("investigator", systems)
    law_inv = research_sessions._role_instructions("investigator", law)

    # A new research session receives evidence-to-action expectations, while
    # a resumed v2 session must not silently adopt a different methodology.
    assert research_sessions.RESEARCH_METHOD_VERSION == "phase2-i2-v3"
    assert "actually executed computation" in math_inv
    assert "actual result" in math_skep
    assert "novelty unassessed" in physics_inv
    assert "discriminating next_question" in math_skep
    assert "discriminating next_question" not in math_inv
    old_context = {**physics, "research_method_version": "phase2-i2-v2"}
    old_instructions = research_sessions._role_instructions("skeptic", old_context)
    assert "actually executed computation" not in old_instructions
    assert "discriminating next_question" not in old_instructions
    # These are strict schema/provenance clarifications, not a method-version
    # change; frozen v2 sessions need the same explicit empty-list semantics.
    assert "if no IDs are supplied, return an empty array" in old_instructions
    assert "If no approved continuation sources are supplied, return an empty array" in (
        old_instructions
    )
    packet_context = {
        **old_context,
        "approved_continuation": {"sources": [{"artifact_id": "a" * 36}]},
        "prior_session_failure_attempt_ids": ["attempt-1"],
    }
    packet_instructions = research_sessions._role_instructions("investigator", packet_context)
    assert "inspect every selected source" in packet_instructions
    assert "use only the exact IDs supplied" in packet_instructions
    assert research_sessions._role_instructions("skeptic", {}) == (
        research_sessions._role_instructions("skeptic", {"research_method_version": "phase2-i2-v2"})
    )

    for mode in ResearchMode:
        for role in ("investigator", "skeptic"):
            guidance = research_sessions._role_instructions(
                role, {**common, "investigation_type": mode.value}
            )
            assert "Across disciplines, specify the question" in guidance
            assert "source pointer is not an inspected source" in guidance
            assert "No live external-source retrieval tool is available" in guidance
            assert research_sessions.RESEARCH_MODE_METHOD_GUIDANCE[mode.value] in guidance
            assert "one- or two-sentence status" in guidance

    assert "In any branch of mathematics" in math_inv
    assert "universal claims" in math_skep
    assert "general relativity" not in math_inv.lower()
    assert "For any branch of physics" in physics_inv
    assert "general relativity" in physics_inv.lower()
    assert "No unperformed intervention" in bio_inv
    assert "external ground truth" in sys_inv
    assert "controlling authority" in law_inv
    assert "For any branch of physics" not in math_inv
    assert "In any branch of mathematics" not in physics_inv
    assert "For biological hypotheses" not in physics_inv

    for context in ({}, {"investigation_type": "unknown"}, {"investigation_type": 42}):
        fallback = research_sessions._role_instructions("skeptic", {**common, **context})
        assert "Across disciplines" in fallback
        assert "unit of analysis" in fallback
        assert "For any branch of physics" not in fallback


def test_method_sources_yield_to_mandatory_research_when_context_is_full():
    """Noncritical methodology must never make a genuine research turn fail."""
    context = {
        "problem": "A fixed scientific objective.",
        "methodology_source_material": [{"id": "source", "notes": "optional methods " * 1000}],
        "methodology_source_status": "selected",
        "context_manifest": {"sources": []},
    }
    assert research_sessions.compact_dispatch_context(context, limit=1200)
    assert "methodology_source_material" not in context
    assert context["methodology_source_status"] == "omitted_due_to_context_limit"
    assert context["problem"] == "A fixed scientific objective."
    assert context["context_manifest"]["methodology_sources_not_supplied"]["count"] == 1


def test_method_source_notes_reach_real_role_request_audit():
    """The pre-turn source decision reaches both roles without a provider call."""
    from sigma import research_method_sources

    selected = research_method_sources.select_method_sources(
        "physics", "Warp Drive Design", "spacetime metric and curvature", (), ()
    )
    context = {
        "problem": "Investigate a spacetime model without assuming feasibility.",
        "investigation_type": "physics",
        "research_method_version": research_sessions.RESEARCH_METHOD_VERSION,
        "methodology_source_material": selected["sources"],
        "methodology_source_status": selected["status"],
        "execution_tools": [],
    }
    record = {
        "mode": "chatgpt",
        "model": MODEL,
        "reasoning_effort": "high",
        "output_token_limit": 4000,
    }
    for role in ("investigator", "skeptic"):
        request = research_sessions._role_request_payload(record, role, context)
        assert "methodology_source_material" in request["input"][0]["content"]
        assert research_method_sources.CATALOG[0]["notes"] in request["input"][0]["content"]
        assert "NASEM" in request["input"][0]["content"]
        assert "Use the session's methodology_source_material" in request["instructions"]
        assert "No live external-source retrieval tool" in request["instructions"]
        assert "For any branch of physics" in request["instructions"]


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
    assert "Click Resume" in failed_guidance
    assert "another attempt may incur a charge" in failed_guidance
    paused_fixture["message"] = (
        "The conservative estimated cost reserve for another call exceeds the session limit; no additional call was made."
    )
    paused_fixture["status"] = "paused"
    assert "only if you approve" in research_sessions._public(paused_fixture)["next_step_guidance"]
    paused_fixture["status"] = "ended"
    paused_fixture["message"] = (
        "Configured model-call limit reached. Findings are unverified research notes."
    )
    assert "Click Resume" in research_sessions._public(paused_fixture)["next_step_guidance"]
    paused_fixture["status"] = "paused"
    for message, expected in (
        (
            "Project or strategy changed; session paused before a new call.",
            "enable the session's saved strategies",
        ),
        (
            "AI account or billing identity changed; session paused before a new call.",
            "Research is independent of the ChatGPT account",
        ),
        (
            "Selected model is no longer available; session paused before a new call.",
            "Check that the current connection supports the saved model",
        ),
        (
            "Configured session duration reached while waiting for provider access. No new call was made.",
            "click Resume",
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
    # An achieved declaration cannot globally close unreviewed obligations.
    assert not archived["artifacts"][1]["skeptic_output"]["coordinator_global_closure"]["accepted"]
    assert not archived["artifacts"][1]["skeptic_output"]["coordinator_closed_obligations"]

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
        root / "project-concurrency-bounds.sigma",
        "Bounded project",
        "Check project limits",
        research_mode="mathematical",
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
    saved_path.parent.mkdir(parents=True, exist_ok=True)
    saved_path.write_text(json.dumps(legacy), encoding="utf-8")
    assert research_sessions.get_limits(path)["max_concurrent_sessions"] == 4
    assert json.loads(saved_path.read_text())["max_concurrent_sessions"] == 17
    research_sessions.save_limits(path, research_sessions.get_limits(path))
    # User-scoped saves cannot mutate portable project-local legacy data.
    assert json.loads(saved_path.read_text())["max_concurrent_sessions"] == 17


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
        result = await asyncio.wait_for(task, timeout=12)
        await research_sessions._tasks[result["id"]]


async def test_start_preserves_frozen_inputs_after_slow_preflight(path: Path):
    view, strategy, credential, config = await setup(path)
    entered = asyncio.Event()
    release = asyncio.Event()

    async def slow_auth():
        entered.set()
        await release.wait()
        return credential

    async def no_provider_worker(_session_id: str, _path: str):
        # The regression validates admission without invoking a paid provider.
        return

    with (
        patch.object(research_sessions, "_worker", new=no_provider_worker),
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
        # A saturated CI runner may delay source prefetch after auth completes.
        # Lock responsiveness is independently asserted by the two-second gate above.
        started = await asyncio.wait_for(task, timeout=10)
        await research_sessions._tasks[started["id"]]
    record = research_sessions._read(str(path), started["id"])
    assert record["strategy_text"] == strategy.approach
    assert record["strategy_title"] == strategy.title
    assert record["strategy_runs"][0]["strategy_text"] == strategy.approach
    assert inspect_project(path).project.strategies[0].title == "Revised approach"
    assert len(research_sessions.list_sessions(str(path))) == 1


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
        assert len(started) == 3, attempts
        assert sorted(item["session_number"] for item in started) == [1, 2, 3]
        # Admission never discards another collaborator's independent Session
        # just because the execution capacity is occupied. The worker gate,
        # not admission, limits simultaneous provider dispatch.
        stopped = await research_sessions.control_session(str(path), started[0]["id"], "stop")
        assert stopped["status"] == "stopped"
        after_release = await research_sessions.start_session(
            str(path), strategy.id, str(uuid4()), view.project.id, credential["identity"], limits
        )
        assert after_release["session_number"] == 4
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
    limits = dict(research_sessions.DEFAULT_LIMITS)
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


async def test_legacy_background_disconnect_after_gate_wait(path: Path) -> None:
    """Legacy dispatch cannot charge after the final viewer closes during preflight."""
    view, strategy, credential, config = await setup(path)
    viewer = research_presence.open_viewer(str(path))
    assert research_presence.has_live_viewer(str(path))

    async def idle_worker(*_args):
        return None

    with (
        patch(
            "sigma.global_research_settings._path",
            return_value=path.parent / "research-settings.json",
        ),
        patch.object(research_sessions, "auth_context", new=AsyncMock(return_value=credential)),
        patch.object(research_sessions, "configuration", new=AsyncMock(return_value=config)),
        patch.object(research_sessions, "_worker", new=idle_worker),
    ):
        started = await research_sessions.start_session(
            str(path),
            strategy.id,
            str(uuid4()),
            view.project.id,
            credential["identity"],
            browser_presence_required=True,
        )

    record = research_sessions._read(str(path), started["id"])
    record.pop("strategy_runs")
    record["status"] = "queued"
    research_sessions._save(str(path), record)
    provider = AsyncMock(side_effect=AssertionError("Unexpected provider dispatch"))

    async def disconnect_during_gate():
        research_presence.close_viewer(viewer)
        assert not research_presence.has_live_viewer(str(path))
        return []

    with (
        patch(
            "sigma.global_research_settings._path",
            return_value=path.parent / "research-settings.json",
        ),
        patch.object(research_sessions, "auth_context", new=AsyncMock(return_value=credential)),
        patch.object(research_sessions, "configuration", new=AsyncMock(return_value=config)),
        patch.object(research_sessions, "_acquire_gates", new=disconnect_during_gate),
        patch.object(research_sessions, "_call", new=provider),
    ):
        await research_sessions._worker(started["id"], str(path))
    saved = research_sessions._read(str(path), started["id"])
    assert saved["status"] == "paused"
    assert saved["stop_advisory"] is True
    assert saved["calls_used"] == 0
    assert saved["steps"] == []
    provider.assert_not_awaited()


async def test_investigator_python_is_run_and_reviewed(path: Path):
    view, strategy, credential, config = await setup(path)
    limits = dict(research_sessions.DEFAULT_LIMITS)
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
    limits = dict(research_sessions.DEFAULT_LIMITS)
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
    limits = dict(research_sessions.DEFAULT_LIMITS)
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
        limits = dict(research_sessions.DEFAULT_LIMITS)
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
        assert len(calls) == (1 if action == "stop" else 3), calls
        assert (
            finished["status"]
            == {"complete": "ended", "stop": "stopped", "project-change": "ended"}[action]
        ), finished
        if action == "stop":
            assert len([e for e in finished["events"] if e["kind"] == "python.started"]) == 1
            assert len(finished["steps"]) == 3 and finished["calls_used"] == 3
        else:
            assert len(finished["artifacts"]) == 3 and finished["calls_used"] == 6
            assert len([e for e in finished["events"] if e["kind"] == "python.started"]) == 3
        if action == "project-change":
            assert not any(event["kind"] == "research.paused" for event in finished["events"]), (
                "Live strategy edits must not pause the frozen running session"
            )


async def test_new_session_receives_prior_saved_findings(path: Path):
    view, strategy, credential, config = await setup(path)
    # This test exercises cross-session finding transfer, not early research
    # termination. Give the source session a complete one-round protocol.
    limits = dict(research_sessions.DEFAULT_LIMITS)
    limits.update(research_rounds=1, model_calls=2)
    research_sessions.save_limits(str(path), limits)
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
    view = initialize_project(
        path, "Failure history", "A bounded research question.", research_mode="mathematical"
    )
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
    view = initialize_project(
        path, "Long-history project", "A bounded research question.", research_mode="mathematical"
    )
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
    view = initialize_project(
        path,
        "Evidence selection",
        "Keep the active question bounded.",
        research_mode="mathematical",
    )
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
        message = str(exc)
        assert "No provider call was made" in message
        assert "phase=agent_assembly" in message
        assert "role=investigator" in message
        assert f"limit {research_sessions.MAX_AGENT_CONTEXT_BYTES}B" in message
        assert "problem=" in message
        assert "😀" not in message  # Never dump an oversized private prompt.
        assert len(message) < 1000
    else:
        raise AssertionError("UTF-8 over-budget mandatory question was accepted")


def test_project_compact_obligation_ids_preserve_legacy_references(path: Path):
    """Project aliases survive recomputation and never rewrite historical IDs."""
    from sigma.project_obligation_ids import assign_project_obligation_ids

    view = initialize_project(
        path, "Project obligation aliases", "Prove the claim.", research_mode="mathematical"
    )
    project_id = view.project.id
    strategy_id = str(uuid4())
    a = "Check a counterexample under assumption A."
    b = "Establish the boundary case under assumption B."
    first_digest = research_sessions._obligation_identity(
        a, project_id=project_id, strategy_id=strategy_id, assumptions=[]
    )
    second_digest = research_sessions._obligation_identity(
        b, project_id=project_id, strategy_id=strategy_id, assumptions=[]
    )
    assert assign_project_obligation_ids(str(path), [first_digest]) == {first_digest: "o1"}
    assert assign_project_obligation_ids(str(path), [first_digest, second_digest]) == {
        first_digest: "o1",
        second_digest: "o2",
    }
    assert assign_project_obligation_ids(str(path), [second_digest]) == {second_digest: "o2"}

    old_artifact = {
        "id": str(uuid4()),
        "project_id": project_id,
        "strategy_id": strategy_id,
        "open_obligations": [a],
    }
    original = deepcopy(old_artifact)
    legacy, _, _ = research_sessions._obligation_ledger(
        [old_artifact], project_id=project_id, strategy_id=strategy_id
    )
    assert legacy[0]["obligation_id"] == first_digest
    assert old_artifact == original

    new_artifact = {
        "id": str(uuid4()),
        "project_id": project_id,
        "strategy_id": strategy_id,
        "open_obligations": [b],
    }
    compact, _, _ = research_sessions._obligation_ledger(
        [new_artifact],
        project_id=project_id,
        strategy_id=strategy_id,
        prior_obligations=legacy,
        identity_path=str(path),
    )
    ids = {row["obligation_id"] for row in compact}
    assert ids == {first_digest, "o2"}, ids
    assert compact[0]["obligation_id"] == first_digest
    assert compact[1]["obligation_id"] == "o2"
    assert new_artifact["open_obligations"] == [b]

    # All three ID families are accepted as references, but an agent cannot
    # review an ID absent from the supplied ledger.
    for value in ("o12", first_digest, str(uuid4())):
        assert (
            research_sessions.ObligationReview(
                obligation_id=value,
                status="unresolved",
                basis_artifact_ids=[],
                basis_step_ids=[],
                rationale="This still requires verification.",
            ).obligation_id
            == value
        )


def test_literature_research_prompts_use_interpretation_without_weakening_provenance() -> None:
    """Literature's built-in lens reaches both roles without optional source guides."""
    context = {
        "investigation_type": "literature",
        "research_method_version": "phase2-i2-v3",
        "execution_tools": [],
    }
    for role in ("investigator", "skeptic"):
        prompt = research_sessions._role_instructions(role, context)
        assert "develop a defensible interpretation rather than a formal proof" in prompt
        assert "Close-read the actual work" in prompt
        assert "never invent quotations" in prompt
        assert "Separate what a literary work depicts from documented history" in prompt
        assert "Keep evidence provenance auditable" in prompt
        assert "Allow imaginative, tentative readings" in prompt
        assert "without repeatedly announcing that an interpretation is speculative" in prompt
        assert "do not" in prompt and "unsupported historical events" in prompt
        assert "methodology_source_material" in prompt
        if role == "skeptic":
            assert "probe selective quotation" in prompt
            assert "rejecting a clearly qualified interpretation" in prompt
        else:
            assert "build an interpretive thesis" in prompt

    math_prompt = research_sessions._role_instructions(
        "investigator", {**context, "investigation_type": "mathematical"}
    )
    assert "formalize exact objects" in math_prompt
    assert "develop a defensible interpretation" not in math_prompt


if __name__ == "__main__":
    from research_sessions_split_runner import run

    run(1)
