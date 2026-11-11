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

from sigma import agentic, papers, proposals, python_sandbox, research_sessions, text_views
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

if __package__:
    from .research_sessions_part1 import (
        investigation,
        provider_response,
        setup,
        skeptic,
        wait_for,
    )
else:
    from research_sessions_part1 import (
        investigation,
        provider_response,
        setup,
        skeptic,
        wait_for,
    )

# Legacy role-only fixtures deliberately leave the new compiler off.
# tests/reference_compiler_integration.py explicitly enables and tests it.
os.environ.setdefault("SIGMA_REFERENCE_COMPILATION_ENABLED", "false")

MODEL = "gpt-6.1-sol"
REAL_CLIENT = httpx.AsyncClient


async def test_provider_gate_fairness_and_cancelled_waiter() -> None:
    """A busy session cannot starve another owner; cancellation leaks no slot."""
    gate = research_sessions._FairProviderGate(1)
    await gate.acquire("user-a")
    order: list[str] = []

    async def queue(owner: str, label: str) -> None:
        await gate.acquire(owner)
        order.append(label)

    first_a = asyncio.create_task(queue("user-a", "a1"))
    second_a = asyncio.create_task(queue("user-a", "a2"))
    first_b = asyncio.create_task(queue("user-b", "b1"))
    await asyncio.sleep(0)
    gate.release()
    await first_b
    assert order == ["b1"], order
    gate.release()
    await first_a
    assert order == ["b1", "a1"], order
    gate.release()
    await second_a
    assert order == ["b1", "a1", "a2"], order
    gate.release()
    assert gate.active == 0

    await gate.acquire("user-a")
    cancelled = asyncio.create_task(queue("user-b", "cancelled"))
    await asyncio.sleep(0)
    cancelled.cancel()
    try:
        await cancelled
    except asyncio.CancelledError:
        pass
    else:
        raise AssertionError("Cancelled capacity waiter unexpectedly completed")
    gate.release()
    assert gate.active == 0 and not gate.waiting and not gate.owners


def test_backend_global_provider_file_slots_are_bounded(root: Path) -> None:
    """No 33rd provider request can pass the backend's shared 32-slot gate."""
    with (
        patch.object(research_sessions.cloud_workspaces, "storage_root", return_value=root),
        patch.dict("os.environ", {"SIGMA_RESEARCH_GLOBAL_INFLIGHT": "32"}),
    ):
        held: list[int] = []
        try:
            for _ in range(32):
                fd = research_sessions._shared_provider_slot()
                assert fd is not None
                held.append(fd)
            assert research_sessions._shared_provider_slot() is None
        finally:
            for fd in held:
                research_sessions.fcntl.flock(fd, research_sessions.fcntl.LOCK_UN)
                research_sessions.os.close(fd)
        again = research_sessions._shared_provider_slot()
        assert again is not None
        research_sessions.fcntl.flock(again, research_sessions.fcntl.LOCK_UN)
        research_sessions.os.close(again)


async def test_global_inflight_limit_bounds_multiple_strategy_sessions(root: Path):
    """Concurrent sessions share the process-level provider admission limit."""
    left = root / "global-provider-left.sigma"
    right = root / "global-provider-right.sigma"
    left_view, first_left, credential, config = await setup(left)
    right_view, first_right, _, _ = await setup(right)
    second_left = create_strategy(
        left, "Left peer", "Independent second route."
    ).project.strategies[-1]
    second_right = create_strategy(
        right, "Right peer", "Independent second route."
    ).project.strategies[-1]
    limits = {
        **research_sessions.DEFAULT_LIMITS,
        "model_calls": 4,
        "research_rounds": 1,
    }
    research_sessions.save_limits(str(left), limits)
    research_sessions.save_limits(str(right), limits)
    state: dict[str, Any] = {"active": 0, "maximum": 0, "seen": set()}
    sequences: dict[str, list[str]] = {}

    async def handler(request):
        payload = json.loads(request.content)
        context = json.loads(payload["input"])
        strategy_id = context["strategy"]["id"]
        role = payload["text"]["format"]["name"]
        sequences.setdefault(strategy_id, []).append(role)
        state["seen"].add(strategy_id)
        state["active"] += 1
        state["maximum"] = max(state["maximum"], state["active"])
        try:
            await asyncio.sleep(0.025)
            output = (
                investigation(context["cycle"])
                if role == "research_investigator"
                else skeptic(context["cycle"], "stop")
            )
            return httpx.Response(200, json=provider_response(output))
        finally:
            state["active"] -= 1

    with (
        patch.dict(
            "os.environ",
            {
                "SIGMA_RESEARCH_GLOBAL_INFLIGHT": "2",
                "SIGMA_RESEARCH_SESSION_INFLIGHT": "3",
            },
        ),
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
        started_left, started_right = await asyncio.gather(
            research_sessions.start_session(
                str(left),
                first_left.id,
                str(uuid4()),
                left_view.project.id,
                credential["identity"],
                expected_limits=limits,
                strategy_ids=[first_left.id, second_left.id],
            ),
            research_sessions.start_session(
                str(right),
                first_right.id,
                str(uuid4()),
                right_view.project.id,
                credential["identity"],
                expected_limits=limits,
                strategy_ids=[first_right.id, second_right.id],
            ),
        )
        finished = await asyncio.wait_for(
            asyncio.gather(
                wait_for(left, started_left["id"]),
                wait_for(right, started_right["id"]),
            ),
            timeout=10,
        )

    assert state["maximum"] == 2, state
    assert state["active"] == 0
    assert len(state["seen"]) == 4
    assert all(item["status"] == "ended" for item in finished), finished
    assert all(item["calls_used"] == 4 for item in finished)
    assert all(len(item["artifacts"]) == 2 for item in finished)
    assert all(
        roles == ["research_investigator", "research_skeptic"] for roles in sequences.values()
    )


async def test_concurrent_strategy_portfolio(path: Path):
    view, first, credential, config = await setup(path)
    second = create_strategy(
        path, "Boundary-first", "Start with degenerate and small boundary cases."
    ).project.strategies[-1]
    third = create_strategy(
        path, "Counterexample search", "Search for assumptions that make the claim fail."
    ).project.strategies[-1]
    limits = dict(research_sessions.DEFAULT_LIMITS)
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


async def test_session7_context_pause_recovers_original_18_turn_research(path: Path):
    """An old context guard at approximately turn 11 must not destroy the session.

    Restart the *same* research after its preflight context interruption and
    preserve every committed artifact. The provider is a deterministic mock.
    """
    view, first, credential, config = await setup(path)
    second = create_strategy(
        path, "Independent reliability route", "Test failure isolation."
    ).project.strategies[-1]
    third = create_strategy(
        path, "Independent recovery route", "Test recovery safety."
    ).project.strategies[-1]
    limits = research_sessions.save_limits(
        str(path),
        {
            **research_sessions.DEFAULT_LIMITS,
            "research_rounds": 3,
            "model_calls": 18,
            "session_duration_minutes": None,
        },
    )
    requests = 0
    old_guard_active = False
    original_context = research_sessions._agent_context

    def context_with_reproduction(record, role, cycle):
        if old_guard_active:
            raise research_sessions.ResearchContextLimitError(
                "Synthetic old 256 KB context guard; saved original is intact."
            )
        return original_context(record, role, cycle)

    async def handler(request):
        nonlocal requests, old_guard_active
        requests += 1
        # Reproduce the observable boundary of Session #7 after eleven turns.
        # The guard rejects *new* context assembly, never an in-flight call.
        if requests == 11:
            old_guard_active = True
        payload = json.loads(request.content)
        context = json.loads(payload["input"])
        result = (
            investigation(context["cycle"])
            if payload["text"]["format"]["name"] == "research_investigator"
            else skeptic(context["cycle"])
        )
        return httpx.Response(200, json=provider_response(result))

    with (
        patch.object(research_sessions, "_agent_context", side_effect=context_with_reproduction),
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
        interrupted = await wait_for(path, started["id"])
        assert interrupted["status"] in {"paused", "stopped"}, interrupted["message"]
        assert 11 <= interrupted["calls_used"] < 18, interrupted["calls_used"]
        assert interrupted["artifacts"], "Context interruption must retain completed work"
        assert any(e["kind"] == "research.context_blocked" for e in interrupted["events"])
        committed = {a["id"]: deepcopy(a) for a in interrupted["artifacts"]}
        old_guard_active = False
        resumed = await research_sessions.control_session(str(path), started["id"], "resume")
        assert resumed["id"] == started["id"]
        finished = await wait_for(path, started["id"])

    assert finished["status"] in {"ended", "completed"}, finished["message"]
    assert finished["calls_used"] == 18, finished["message"]
    assert requests == 18
    assert len(finished["artifacts"]) == 9
    saved = {a["id"]: a for a in finished["artifacts"]}
    assert all(saved[item_id] == source for item_id, source in committed.items())
    assert len(saved) == len({a["id"] for a in finished["artifacts"]})
    assert len([step for step in finished["steps"] if step["status"] == "completed"]) == 18


async def test_three_strategies_reach_18_turns_each_after_transport_failure_at_turn_14(
    path: Path,
):
    """54 completed agent turns survive a transient failure at dispatch fourteen.

    Provider attempts remain separately budgeted, while a technical failure
    never masquerades as research completion. No paid provider is contacted.
    """
    view, first, credential, config = await setup(path)
    second = create_strategy(
        path, "Reliability propagation", "Investigate how tool failures propagate."
    ).project.strategies[-1]
    third = create_strategy(
        path, "Architectural mitigations", "Test controls against faulty observations."
    ).project.strategies[-1]
    limits = research_sessions.save_limits(
        str(path),
        {
            **research_sessions.DEFAULT_LIMITS,
            "research_rounds": 9,
            # One failed, separately accounted attempt must not consume the
            # final successful Investigator/Skeptic turn.
            "model_calls": 56,
            "session_duration_minutes": None,
        },
    )
    requests = 0
    dispatched_contexts = []
    # Leave room for the expanded project-type methodology and provenance
    # metadata while still exercising dispatch compaction under a limit well
    # below the 256 KB production guard.
    dispatch_limit = 96_000

    async def handler(request):
        nonlocal requests
        requests += 1
        if requests == 14:
            raise httpx.ReadError("Synthetic transport interruption at turn fourteen")
        payload = json.loads(request.content)
        context = json.loads(payload["input"])
        dispatched_contexts.append(context)
        assert research_sessions._json_bytes(context) <= dispatch_limit
        cycle = context["cycle"]
        response = (
            investigation(cycle)
            if payload["text"]["format"]["name"] == "research_investigator"
            else skeptic(cycle)
        )
        if payload["text"]["format"]["name"] == "research_investigator":
            # Valid maximum-sized provider fields, not a malformed 20 KB
            # method that fails schema validation before context is tested.
            response["method"] += " Long saved method detail." * 170
            response["reasoning_steps"].extend(
                {
                    "title": f"Additional consideration {i}",
                    "argument": "Substantial but unresolved derivation. " * 150,
                    "epistemic_status": "conjecture",
                    "basis_artifact_ids": [],
                }
                for i in range(3)
            )
        else:
            response["response"] += " Long saved Skeptic objection." * 155
        if (
            context["strategy"]["id"] == first.id
            and cycle == 1
            and payload["text"]["format"]["name"] == "research_skeptic"
        ):
            # Reproduce the actual session #6 contradiction: Skeptic requests
            # continuation but labels an earlier result decisive counterexample.
            response["stop_reason"] = "decisive_counterexample"
            response["assessment"] = "continue"
        return httpx.Response(200, json=provider_response(response))

    with (
        patch.object(research_sessions, "MAX_AGENT_CONTEXT_BYTES", dispatch_limit),
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

    branches = finished["strategy_runs"]
    assert requests == 55, (requests, finished["message"])
    assert finished["calls_used"] == 55
    assert finished["status"] == "ended", (finished["status"], finished["message"])
    assert len(finished["artifacts"]) == 27
    assert len([s for s in finished["steps"] if s["status"] == "completed"]) == 54
    assert len([s for s in finished["steps"] if s["status"] == "failed"]) == 1
    assert all(branch["cycle"] == 9 for branch in branches), branches
    assert all(len(branch["artifacts"]) == 9 for branch in branches), branches
    assert all(branch["status"] == "ended" for branch in branches), branches
    assert (
        next(
            artifact
            for artifact in finished["artifacts"]
            if artifact["strategy_id"] == first.id and artifact["strategy_cycle"] == 1
        )["coordinator_decision"]
        == "continue"
    )
    assert finished.get("termination_reason_code") != "research_completed_early"
    assert research_sessions.get_session(str(path), started["id"])["calls_used"] == 55
    # Attempt fourteen fails before its request body is inspected by the mock.
    assert len(dispatched_contexts) == 54
    # The source-selector may bound history before the dispatch-only compactor
    # runs. Test the invariant rather than requiring a particular algorithm
    # or provenance marker: cumulative saved research greatly exceeds the
    # allowable request, but every submitted packet remains under budget.
    assert research_sessions._json_bytes(finished["artifacts"]) > dispatch_limit * 3
    assert all(
        len(a["investigator_output"]["method"]) > 4_000
        and len(a["investigator_output"]["reasoning_steps"]) == 4
        for a in finished["artifacts"]
    ), "Dispatch compaction must preserve original saved evidence"


async def test_portfolio_cross_strategy_reviews_ground_synthesis_in_peer_evidence(path: Path):
    view, first, credential, config = await setup(path)
    second = create_strategy(
        path, "Complementary route", "Derive a separate invariant and compare its consequences."
    ).project.strategies[-1]
    project_before = (path / "project.json").read_bytes()
    limits = dict(research_sessions.DEFAULT_LIMITS)
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
    # A cross-strategy handoff is queued only while its recipient is active.
    # Both strategies stop in cycle 2, so a terminal batch need not enqueue
    # a future handoff. Verify any emitted events have real saved provenance;
    # the required peer evidence is checked in the provider requests below.
    available_handoffs = [
        event for event in trace if event["type"] == "cross_strategy_artifact_availability"
    ]
    saved_artifact_ids = {item["id"] for item in finished["artifacts"]}
    assert all(
        event["source_artifact_id"] in saved_artifact_ids
        and event["target_artifact_id"] in saved_artifact_ids
        for event in available_handoffs
    )
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


async def test_parallel_budget_pressure_defers_without_ending_research(path: Path):
    """Temporary simultaneous reservations must not change a funded outcome."""
    view, first, credential, config = await setup(path)
    second = create_strategy(
        path, "Second funded approach", "Test an independent boundary case."
    ).project.strategies[-1]
    limits = {
        **research_sessions.DEFAULT_LIMITS,
        "research_rounds": 1,
        "model_calls": 4,
        "output_tokens_per_call": 20000,
        # Versioned method notes legitimately increase the prompt's bounded
        # cost reserve. Keep the ceiling above four settled fixture calls but
        # below two simultaneous worst-case output reservations.
        "maximum_estimated_cost_usd": 0.40,
    }
    research_sessions.save_limits(str(path), limits)
    observed_deferral = []
    original_pending = research_sessions._portfolio_has_pending_reservation

    def monitor_pending(record, exclude_step_id=None):
        pending = original_pending(record, exclude_step_id)
        if pending:
            observed_deferral.append(True)
        return pending

    async def handler(request):
        payload = json.loads(request.content)
        context = json.loads(payload["input"])
        await asyncio.sleep(0.04)
        role = payload["text"]["format"]["name"]
        output = (
            investigation(context["cycle"])
            if role == "research_investigator"
            else skeptic(context["cycle"], "stop")
        )
        return httpx.Response(200, json=provider_response(output))

    with (
        patch.object(research_sessions, "auth_context", new=AsyncMock(return_value=credential)),
        patch.object(research_sessions, "configuration", new=AsyncMock(return_value=config)),
        patch.object(research_sessions, "execution_capabilities", return_value=[]),
        patch.object(
            research_sessions,
            "_portfolio_has_pending_reservation",
            side_effect=monitor_pending,
        ),
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
        finished = await asyncio.wait_for(wait_for(path, started["id"]), timeout=10)

    assert observed_deferral, "Concurrent funding pressure was not exercised"
    assert finished["status"] == "ended", finished["message"]
    assert finished["calls_used"] == 4
    assert len(finished["artifacts"]) == 2
    assert all(branch["status"] == "ended" for branch in finished["strategy_runs"])


async def _main_wave_dispatch_for_parity(
    session_id: str,
    path: str,
    selected: list[dict[str, Any]],
    semaphore: asyncio.Semaphore,
    state_lock: asyncio.Lock,
    run_wave,
) -> None:
    """Original main@48c1fb2 dispatch logic, retained as baseline fixture.

    This deliberately uses the original three wave phases and calls the same
    role implementation as production. Only scheduling changes in the A/B.
    """
    needs_review = [branch for branch in selected if branch.get("pending_investigation")]
    needs_investigation = [branch for branch in selected if not branch.get("pending_investigation")]
    await run_wave(
        [
            research_sessions._portfolio_role_call_with_recovery(
                session_id,
                path,
                branch["strategy_id"],
                "skeptic",
                branch["cycle"],
                semaphore,
                state_lock,
            )
            for branch in needs_review
        ]
    )
    investigators = await run_wave(
        [
            research_sessions._portfolio_role_call_with_recovery(
                session_id,
                path,
                branch["strategy_id"],
                "investigator",
                branch["cycle"] + 1,
                semaphore,
                state_lock,
            )
            for branch in needs_investigation
        ]
    )
    investigator_success = [
        branch
        for branch, result in zip(needs_investigation, investigators, strict=True)
        if result is True
    ]
    await run_wave(
        [
            research_sessions._portfolio_role_call_with_recovery(
                session_id,
                path,
                branch["strategy_id"],
                "skeptic",
                branch["cycle"] + 1,
                semaphore,
                state_lock,
            )
            for branch in investigator_success
        ]
    )


def test_parallel_schedule_preserves_research_semantics(root: Path) -> None:
    """Identical deterministic role outputs must produce identical research data.

    Exclude request IDs, timestamps and nondeterministic wall-clock ordering;
    include model context, peer evidence, findings and coordinator decisions.
    """

    async def scenario(name: str, fanout: int):
        path = root / f"parity-{name}.sigma"
        view, first, credential, config = await setup(path)
        second = create_strategy(
            path, "Independent peer", "Derive a complementary invariant."
        ).project.strategies[-1]
        limits = {**research_sessions.DEFAULT_LIMITS, "research_rounds": 3, "model_calls": 12}
        research_sessions.save_limits(str(path), limits)
        seen: dict[tuple[str, int, str], dict[str, Any]] = {}
        slow_investigator_active = False
        fast_skeptic_overlapped_slow_investigator = False
        fast_skeptic_entered = asyncio.Event()

        async def handler(request):
            nonlocal slow_investigator_active, fast_skeptic_overlapped_slow_investigator
            payload = json.loads(request.content)
            context = json.loads(payload["input"])
            role = payload["text"]["format"]["name"]
            title = context["strategy"]["title"]
            cycle = context["cycle"]
            peers = context["other_strategy_evidence"]
            assert bool(peers) is (cycle > 1), (title, role, cycle)
            seen[(title, cycle, role)] = {
                "question": context["question"],
                "prior_claims": [item["claim_or_question"] for item in context["prior_artifacts"]],
                "peer_claims": [item["claim_or_question"] for item in peers],
                "peer_assumptions": [item["assumptions"] for item in peers],
                "peer_objections": [item["objections"] for item in peers],
                "handoff_relations": [
                    item["relation"] for item in context.get("peer_handoffs", [])
                ],
                "handoff_sources": [
                    item["source_strategy_title"] for item in context.get("peer_handoffs", [])
                ],
                "pending_claim": (
                    context.get("investigator_output", {}).get("claim")
                    if role == "research_skeptic"
                    else None
                ),
            }
            if title == first.title and cycle == 1 and role == "research_investigator":
                slow_investigator_active = True
                try:
                    if name == "parallel":
                        # A handshake makes the intended overlap deterministic
                        # even on a busy CI runner; a fixed sleep is racy.
                        await asyncio.wait_for(fast_skeptic_entered.wait(), timeout=5)
                    else:
                        await asyncio.sleep(0.06)
                finally:
                    slow_investigator_active = False
            elif title == second.title and cycle == 1 and role == "research_skeptic":
                if slow_investigator_active:
                    fast_skeptic_overlapped_slow_investigator = True
                fast_skeptic_entered.set()
                await asyncio.sleep(0.002)
            else:
                await asyncio.sleep(0.002)
            if role == "research_investigator":
                output = investigation(cycle)
                output["claim"] = f"{title} finding at round {cycle}."
            else:
                output = skeptic(
                    cycle,
                    "stop" if cycle == 3 else "revise",
                    "productive_conclusion" if cycle == 3 else "recoverable_objection",
                )
                output["next_question"] = (
                    "Test peer evidence on the next round." if cycle < 3 else ""
                )
                if title == first.title and cycle == 2:
                    assert peers, "A peer finding is required for the handoff"
                    output["cross_strategy_relations"] = [
                        {
                            "strategy_id": second.id,
                            "artifact_id": peers[-1]["artifact_id"],
                            "relation": "contradicts",
                            "rationale": "Compare the independent invariant's assumptions before transfer.",
                        }
                    ]
                if context.get("peer_handoffs"):
                    output["peer_handoff_reviews"] = [
                        {
                            "handoff_id": item["handoff_id"],
                            "disposition": "reject",
                            "assumption_comparison": "Independent invariant assumptions have not been established as equivalent.",
                            "rationale": "Do not transfer this purported contradiction without validating its domain.",
                        }
                        for item in context["peer_handoffs"]
                    ]
            return httpx.Response(200, json=provider_response(output))

        with (
            patch.dict("os.environ", {"SIGMA_RESEARCH_GLOBAL_INFLIGHT": str(fanout)}),
            patch.object(research_sessions, "auth_context", new=AsyncMock(return_value=credential)),
            patch.object(research_sessions, "configuration", new=AsyncMock(return_value=config)),
            patch.object(research_sessions, "execution_capabilities", return_value=[]),
            patch.object(
                research_sessions,
                "_portfolio_run_selected",
                new=(
                    _main_wave_dispatch_for_parity
                    if name == "original-main"
                    else research_sessions._portfolio_run_selected
                ),
            ),
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
            finished = await asyncio.wait_for(wait_for(path, started["id"]), timeout=10)
        assert finished["status"] == "ended" and finished["calls_used"] == 12
        assert len(finished["artifacts"]) == 6 and len(seen) == 12
        assert seen[(second.title, 3, "research_investigator")]["handoff_relations"] == [
            "contradicts"
        ]
        titles = {first.id: first.title, second.id: second.title}
        findings = sorted(
            (
                titles[artifact["strategy_id"]],
                artifact["strategy_cycle"],
                artifact["claim_or_question"],
                artifact["method"],
                tuple(artifact["objections"]),
                artifact["coordinator_decision"],
                artifact["next_question"],
            )
            for artifact in finished["artifacts"]
        )
        decisions = [
            (
                titles[branch["strategy_id"]],
                branch["status"],
                branch["cycle"],
                branch["calls_used"],
                branch.get("last_decision"),
                branch.get("current_question"),
            )
            for branch in finished["strategy_runs"]
        ]
        # Cross-session-generated UUIDs are expected to differ. Normalize
        # referenced artifact IDs by their actual strategy and round, while
        # retaining handoff referential integrity and all meaningful words.
        artifact_labels = {
            row["id"]: f"<artifact:{titles[row['strategy_id']]}:{row['strategy_cycle']}>"
            for row in finished["artifacts"]
        }

        def normalize(value):
            if isinstance(value, str):
                for identifier, label in artifact_labels.items():
                    value = value.replace(identifier, label)
                return value
            if isinstance(value, dict):
                return {key: normalize(child) for key, child in value.items()}
            if isinstance(value, (tuple, list)):
                return tuple(normalize(child) for child in value)
            return value

        return (
            normalize(seen),
            normalize(findings),
            normalize(decisions),
            finished["outcome"]["assessment"],
            fast_skeptic_overlapped_slow_investigator,
        )

    baseline = asyncio.run(scenario("original-main", 3))
    parallel = asyncio.run(scenario("parallel", 32))
    assert baseline[:-1] == parallel[:-1], (
        "New parallel dispatch changed provider inputs or research results "
        "relative to original main@48c1fb2 scheduling"
    )
    assert baseline[-1] is False, "Original main unexpectedly overlapped the phases"
    assert parallel[-1] is True, "Parallel scheduling did not exercise overlap"


async def test_peer_finding_changes_target_investigator_after_stop_and_resume(path: Path):
    view, source, credential, config = await setup(path)
    target = create_strategy(
        path, "Real-analysis route", "Derive an invariant for all real line arrangements."
    ).project.strategies[-1]
    limits = dict(research_sessions.DEFAULT_LIMITS)
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
    limits = dict(research_sessions.DEFAULT_LIMITS)
    limits.update(research_rounds=2, model_calls=12)
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

    assert finished["status"] == "ended" and finished["calls_used"] == 8
    assert finished["termination_reason_code"] == "protocol_complete"
    branches = {item["strategy_id"]: item for item in finished["strategy_runs"]}
    assert branches[first.id]["status"] == "ended"
    # The Skeptic's unproductive assessment remains saved, but the protocol
    # continues through the configured final round before reporting its limit.
    assert branches[first.id]["last_decision"] == "stop_budget_exhausted"
    assert len(branches[first.id]["artifacts"]) == 2
    assert any(event["kind"] == "coordinator.early_stop_deferred" for event in finished["events"])
    actions = {
        item["strategy_id"]: item for item in finished["portfolio_decision"]["strategy_actions"]
    }
    assert actions[first.id]["action"] == "hold_for_limits"
    assert "configured budget" in actions[first.id]["rationale"]
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
    limits = dict(research_sessions.DEFAULT_LIMITS)
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
    assert 4 <= state["maximum"] <= 10
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
    limits = dict(research_sessions.DEFAULT_LIMITS)
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

    limits = dict(research_sessions.DEFAULT_LIMITS)
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
    test_limits = dict(research_sessions.DEFAULT_LIMITS)
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
            if request_state["count"] >= 4 and request_state["active"] == 2:
                break
            await asyncio.sleep(0.01)
        assert request_state["count"] == 4
        assert request_state["active"] == 2
        assert request_state["maximum"] == 3
        stopped = await research_sessions.control_session(str(path), started["id"], "stop")
        assert stopped["status"] == "stopped"
        assert request_state["count"] == 4
        assert request_state["active"] == 0
        interrupted = research_sessions.get_session(str(path), started["id"])
        # The fast branch finished I/S before stop; its review is still durable
        # as a pending Skeptic until the coordinator resumes.
        assert interrupted["artifacts"] == []
        assert interrupted["calls_used"] == 4
        assert len(interrupted["steps"]) == 4
        assert sum(step["status"] == "completed" for step in interrupted["steps"]) == 2
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
    limits = dict(research_sessions.DEFAULT_LIMITS)
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
            if state["count"] == 4:
                break
            await asyncio.sleep(0.01)
        assert state["count"] == state["active"] == 4
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
        patch.object(research_sessions, "configuration", new=AsyncMock(return_value=config)),
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

    async def handler(request):
        role = json.loads(request.content)["text"]["format"]["name"]
        output = investigation(1) if role == "research_investigator" else skeptic(1, "stop")
        return httpx.Response(200, json=provider_response(output))

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

    assert finished["status"] == "ended"
    # The objective-review policy may continue a promising sibling beyond
    # its first I/S pair. Every completed pair must have a committed artifact.
    artifacts = finished["artifacts"]
    assert artifacts, finished["message"]
    assert finished["calls_used"] == 2 * len(artifacts)
    failed_events = [
        event for event in finished["events"] if event["kind"] == "call.preflight_failed"
    ]
    assert len(failed_events) == 1
    failure = failed_events[0]
    expected_titles = {first.id: first.title, second.id: second.title}
    assert failure["strategy_id"] in expected_titles
    assert finished["artifacts"][0]["strategy_id"] != failure["strategy_id"]
    assert failure["strategy_title"] == expected_titles[failure["strategy_id"]]
    assert failure["role"] == "investigator"
    assert failure["failure_stage"] == "project_snapshot"
    assert failure["failure_kind"] == "preflight_error"
    assert failure["dispatched"] is False
    assert "temporary project snapshot service failure" not in failure["message"]
    completed_steps = [step for step in finished["steps"] if step["status"] == "completed"]
    assert len(completed_steps) == finished["calls_used"]
    assert all(step["strategy_id"] != failure["strategy_id"] for step in completed_steps)
    assert {step["role"] for step in completed_steps} == {"investigator", "skeptic"}
    assert completed_steps[0]["output"]["claim"].startswith("Claim 1:")
    successful_strategy = next(
        strategy_id for strategy_id in expected_titles if strategy_id != failure["strategy_id"]
    )
    assert all(artifact["strategy_id"] == successful_strategy for artifact in artifacts)
    reviewed_cycles = {artifact["strategy_cycle"] for artifact in artifacts}
    assert len(reviewed_cycles) == len(artifacts)
    for cycle in reviewed_cycles:
        assert {
            step["role"]
            for step in completed_steps
            if step["strategy_id"] == successful_strategy and step["cycle"] == cycle
        } == {"investigator", "skeptic"}
    assert all(step.get("strategy_id") != failure["strategy_id"] for step in finished["steps"])


async def test_portfolio_preflight_timeout_pauses_without_spending_calls_and_recovers(
    path: Path,
):
    view, strategy, credential, config = await setup(path)
    limits = dict(research_sessions.DEFAULT_LIMITS)
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


async def test_resume_persists_paused_time_before_guarded_reread(path: Path):
    view, strategy, credential, config = await setup(path)
    entered = asyncio.Event()

    async def handler(_request):
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
            str(path), strategy.id, str(uuid4()), view.project.id, credential["identity"]
        )
        await asyncio.wait_for(entered.wait(), 2)
        await research_sessions.control_session(str(path), started["id"], "pause")

    saved = research_sessions._read(str(path), started["id"])
    saved["status"] = "paused"
    saved["deadline_at"] = (datetime.now(UTC) - timedelta(seconds=30)).isoformat()
    saved["stopped_at"] = (datetime.now(UTC) - timedelta(seconds=60)).isoformat()
    for branch in saved["strategy_runs"]:
        branch["status"] = "paused"
    research_sessions._save(str(path), saved)

    async def idle_worker(*_args):
        await asyncio.Event().wait()

    with (
        patch.object(research_sessions, "auth_context", new=AsyncMock(return_value=credential)),
        patch.object(research_sessions, "configuration", new=AsyncMock(return_value=config)),
        patch.object(research_sessions, "_worker", new=idle_worker),
    ):
        resumed = await research_sessions.control_session(str(path), started["id"], "resume")
        assert resumed["status"] == "queued"
        durable = research_sessions._read(str(path), started["id"])
        assert datetime.fromisoformat(durable["deadline_at"]) > datetime.now(UTC)
        assert durable["stopped_duration_seconds"] >= 59
        assert durable.get("stopped_at") is None
        await research_sessions.control_session(str(path), started["id"], "pause")


async def test_portfolio_isolates_one_strategy_provider_failure(path: Path):
    view, first, credential, config = await setup(path)
    # Isolate this portfolio fixture from earlier tests' user-global limits.
    research_sessions.save_limits(str(path), research_sessions.NEW_DEFAULT_LIMITS)
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
    # Preserve this historical v1 recovery contract with its spare attempt budget.
    # Version-2 sessions instead have exact paired-call ceilings.
    research_sessions.save_limits(str(path), dict(research_sessions.DEFAULT_LIMITS))
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
            return httpx.Response(
                200,
                headers={
                    "content-type": "text/event-stream",
                    "x-request-id": "req-limited-123",
                    "x-codex-primary-used-percent": "100",
                    "x-codex-secondary-used-percent": "36",
                    "set-cookie": "secret=never-log",
                },
                text=body,
            )
        return httpx.Response(
            429,
            headers={
                "x-request-id": "req-limited-123",
                "x-codex-primary-used-percent": "100",
                "x-codex-secondary-used-percent": "36",
                "set-cookie": "secret=never-log",
            },
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

    assert finished["status"] == "paused"
    assert len(provider_calls) == 1
    assert provider_calls == [first.id]
    assert "Provider usage limit reached" in finished["message"]
    branches = {branch["strategy_id"]: branch for branch in finished["strategy_runs"]}
    assert branches[first.id]["status"] == "paused"
    assert branches[second.id]["status"] == "paused"
    assert "Click Resume" in branches[second.id]["reason"]
    limited = next(step for step in finished["steps"] if step["status"] == "failed")
    assert limited["failure_kind"] == "provider_limited"
    assert limited["provider_http_status"] == (200 if streamed else 429)
    assert limited["provider_error_code"] == "subscription_sharing_usage_limit_exceeded"
    assert limited["provider_request_id"] == "req-limited-123"
    assert limited["provider_response_shape"] in {"responses-error", "other-object"}
    assert limited["provider_limit_headers"] == {
        "x-codex-primary-used-percent": "100",
        "x-codex-secondary-used-percent": "36",
    }
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
    assert datetime.fromisoformat(finished["stopped_at"]) <= datetime.fromisoformat(
        limited["finished_at"]
    )


async def test_chatgpt_usage_limit_recovers_only_after_explicit_resume(path: Path):
    view, strategy, credential, config = await setup(path)
    credential["mode"] = "chatgpt"
    limits = {**research_sessions.DEFAULT_LIMITS, "research_rounds": 1, "model_calls": 2}
    research_sessions.save_limits(str(path), limits)
    provider_limited = True
    calls: list[str] = []

    async def handler(request):
        nonlocal provider_limited
        payload = json.loads(request.content)
        role = payload["text"]["format"]["name"]
        calls.append(role)
        if provider_limited:
            return httpx.Response(
                429,
                json={"error": {"code": "subscription_sharing_usage_limit_exceeded"}},
            )
        output = (
            investigation(1)
            if role == "research_investigator"
            else skeptic(1, "stop", "no_progress")
        )
        response_id = f"recovered-{len(calls)}"
        envelope = {
            "id": response_id,
            "status": "completed",
            "usage": {"input_tokens": 25, "output_tokens": 12},
            "output": [
                {
                    "type": "message",
                    "content": [{"type": "output_text", "text": json.dumps(output)}],
                }
            ],
        }
        events = [
            {"type": "response.created", "sequence_number": 0, "response": {"id": response_id}},
            {"type": "response.completed", "sequence_number": 1, "response": envelope},
        ]
        body = "".join(f"event: {event['type']}\ndata: {json.dumps(event)}\n\n" for event in events)
        return httpx.Response(200, headers={"content-type": "text/event-stream"}, text=body)

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
            str(path), strategy.id, str(uuid4()), view.project.id, credential["identity"]
        )
        paused = await wait_for(path, started["id"])
        assert paused["status"] == "paused"
        assert paused["calls_used"] == 1 and calls == ["research_investigator"]
        rejected_attempt = paused["steps"][0]["attempt_id"]
        original_token_ceiling = paused["total_token_limit"]

        # No paid-attempt or time extension occurs without approval.
        try:
            await research_sessions.control_session(str(path), started["id"], "resume")
        except ProjectError as exc:
            assert "exactly 1 explicitly authorized additional attempts" in str(exc)
        else:
            raise AssertionError("Ordinary Resume silently added a provider attempt")
        repeated = await research_sessions.control_session(
            str(path), started["id"], "repair", additional_calls=1
        )
        assert repeated["status"] == "queued"
        paused_again = await wait_for(path, started["id"])
        assert paused_again["status"] == "paused"
        assert paused_again["calls_used"] == 2
        assert paused_again["call_limit"] == 3
        assert sum(step["status"] == "completed" for step in paused_again["steps"]) == 0

        provider_limited = False
        resumed = await research_sessions.control_session(
            str(path), started["id"], "repair", additional_calls=1
        )
        assert resumed["status"] == "queued"
        # A repeated Resume while already queued cannot add a second budget.
        duplicate = await research_sessions.control_session(str(path), started["id"], "resume")
        assert duplicate["call_limit"] == resumed["call_limit"]
        finished = await wait_for(path, started["id"])

    assert len(calls) == 4
    assert finished["calls_used"] == 4
    assert finished["call_limit"] == 4  # Two accepted role slots, two rejected attempts.
    assert finished["total_token_limit"] == original_token_ceiling
    assert [step["status"] for step in finished["steps"]] == [
        "failed",
        "failed",
        "completed",
        "completed",
    ]
    assert finished["steps"][0]["attempt_id"] == rejected_attempt
    assert finished["provider_usage_limited"] is False
    assert sum(step["status"] == "completed" for step in finished["steps"]) == 2
    assert [step["role"] for step in finished["steps"][2:]] == ["investigator", "skeptic"]


async def test_invalid_completed_response_is_not_marked_dispatch_unknown(path: Path):
    view, strategy, credential, config = await setup(path)
    limits = {**research_sessions.DEFAULT_LIMITS, "research_rounds": 1, "model_calls": 2}
    research_sessions.save_limits(str(path), limits)

    async def handler(request):
        payload = json.loads(request.content)
        context = json.loads(payload["input"])
        role = payload["text"]["format"]["name"]
        if role == "research_investigator":
            output = investigation(1)
        else:
            output = skeptic(1)
            obligation = context["obligation_ledger"][0]
            output["obligation_reviews"] = [
                {
                    "obligation_id": obligation["obligation_id"],
                    "status": "unresolved",
                    "basis_artifact_ids": [],
                    "basis_step_ids": ["step-not-selected"],
                    "rationale": "The cited step is intentionally outside the supplied context.",
                }
            ]
        response = provider_response(output)
        response["id"] = f"response-{role}"
        return httpx.Response(200, json=response)

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
            str(path), strategy.id, str(uuid4()), view.project.id, credential["identity"]
        )
        finished = await wait_for(path, started["id"])

    skeptic_step = next(step for step in finished["steps"] if step["role"] == "skeptic")
    audit = skeptic_step["provider_input_audit"]
    assert finished["calls_used"] == 2
    assert skeptic_step["status"] == "failed"
    assert skeptic_step["failure_kind"] == "response_invalid"
    assert skeptic_step["response_validation_kind"] == "unsupported_context_reference"
    assert audit["status"] == "provider_response_invalid"
    assert audit["provider_response_id"] == "response-research_skeptic"
    assert skeptic_step["token_usage"] == {
        "input_tokens": 120,
        "cached_input_tokens": 20,
        "output_tokens": 80,
    }
    assert skeptic_step["token_usage_status"] == "reported"
    assert "not supplied" in finished["message"].lower()


def test_provider_limit_v2_40_of_54_offers_ordinary_resume_and_correct_progress():
    # Crucible acceptance: 36 completed agent calls + four known rejected
    # attempts leave 18 missing protocol slots but only 14 funded attempts.
    strategy_ids = ["formalist", "historical", "reception"]
    steps = []
    runs = []
    for strategy_id in strategy_ids:
        runs.append(
            {
                "strategy_id": strategy_id,
                "strategy_title": strategy_id.title(),
                "status": "failed",
                "cycle": 7,
                "pending_investigation": None,
                "termination_reason_code": "provider_limited",
            }
        )
        for cycle in range(1, 7):
            for role in ("investigator", "skeptic"):
                steps.append(
                    {
                        "id": f"{strategy_id}-{cycle}-{role}",
                        "strategy_id": strategy_id,
                        "role": role,
                        "cycle": cycle,
                        "status": "completed",
                    }
                )
    for index, strategy_id in enumerate(["formalist", "formalist", "historical", "reception"]):
        steps.append(
            {
                "id": f"rejected-{index}",
                "strategy_id": strategy_id,
                "role": "investigator",
                "cycle": 7,
                "status": "failed",
                "failure_kind": "provider_limited",
                "provider_input_audit": {"status": "provider_response_rejected"},
            }
        )
    record = {
        "id": "crucible-40-of-54",
        "status": "failed",
        "scheduler_version": 2,
        "provider_usage_limited": True,
        "cycle": 7,
        "cycle_limit": 9,
        "turns_per_round": 3,
        "research_round_limit": 3,
        "call_limit": 54,
        "calls_used": 40,
        "strategy_runs": runs,
        "steps": steps,
        "artifacts": [],
        "message": "The provider account usage limit was reached.",
    }

    preview = research_sessions._public(record)
    recovery = preview["provider_limit_continuation"]
    assert recovery == {
        "eligible": True,
        "missing_calls": 18,
        "reason": None,
    }
    assert preview["protocol_completed_calls"] == 36
    assert preview["protocol_target_calls"] == 54
    assert "Click Resume" in preview["next_step_guidance"]
    assert "authorize" not in preview["next_step_guidance"].lower()
    assert record["call_limit"] == 54  # A read must not authorize extra calls.
    reason_code, message = research_sessions._portfolio_termination(record, runs)
    assert reason_code == "provider_or_strategy_failure"
    assert "40 of 54 agent calls" in message
    assert "Round 3 of 3, Turn 1 of 3" in message
    assert "round 7 of 9" not in message

    # Unsafe states must not present a one-click recovery action.
    record["steps"][-1]["failure_kind"] = "provider_error"
    preview = research_sessions._public(record)
    assert preview["provider_limit_continuation"]["eligible"] is False


async def test_provider_limit_recovery_completes_full_v2_protocol(path: Path) -> None:
    """Account-limit recovery fills 54 accepted slots without replaying saved work."""
    view, first, credential, config = await setup(path)
    second_view = create_strategy(path, "Historical route", "Test independent evidence.")
    second = next(row for row in second_view.project.strategies if row.id != first.id)
    third_view = create_strategy(path, "Critical route", "Check a competing explanation.")
    third = next(
        row for row in third_view.project.strategies if row.id not in {first.id, second.id}
    )
    ids = [first.id, second.id, third.id]
    credential["mode"] = "chatgpt"
    # v2 uses three rounds * three paired turns per round * three strategies:
    # 54 accepted role calls. model_calls is 18 per strategy, not 54 globally.
    limits = research_sessions.save_limits(str(path), dict(research_sessions.NEW_DEFAULT_LIMITS))
    accepted = 0
    exhausted = False
    requests: list[tuple[str, str, int]] = []

    async def handler(request):
        nonlocal accepted, exhausted
        payload = json.loads(request.content)
        context = json.loads(payload["input"][0]["content"])
        role = payload["text"]["format"]["name"]
        key = (context["strategy"]["id"], role, context["cycle"])
        requests.append(key)
        if accepted >= 36 and not exhausted:
            return httpx.Response(
                429,
                json={"error": {"code": "subscription_sharing_usage_limit_exceeded"}},
            )
        accepted += 1
        output = (
            investigation(context["cycle"])
            if role == "research_investigator"
            else skeptic(context["cycle"])
        )
        # The ChatGPT Responses adapter requires a streamed response, unlike
        # the API-key mode's plain JSON response. Match the actual protocol.
        response_id = f"crucible-recovery-{len(requests)}"
        envelope = {
            "id": response_id,
            "status": "completed",
            "usage": {"input_tokens": 25, "output_tokens": 12},
            "output": [
                {
                    "type": "message",
                    "content": [{"type": "output_text", "text": json.dumps(output)}],
                }
            ],
        }
        events = [
            {"type": "response.created", "sequence_number": 0, "response": {"id": response_id}},
            {"type": "response.completed", "sequence_number": 1, "response": envelope},
        ]
        body = "".join(f"event: {event['type']}\ndata: {json.dumps(event)}\n\n" for event in events)
        return httpx.Response(200, headers={"content-type": "text/event-stream"}, text=body)

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
            expected_limits=limits,
            strategy_ids=ids,
        )
        paused = await wait_for(path, started["id"])
        assert paused["status"] == "paused", paused["message"]
        assert accepted == 36
        assert len(paused["artifacts"]) == 18
        assert paused["provider_usage_limited"] is True
        assert paused["provider_limit_continuation"]["eligible"] is True
        saved_ids = {item["id"] for item in paused["artifacts"]}
        previous_steps = deepcopy(paused["steps"])
        previous_cost_limit = paused.get("maximum_estimated_cost_usd")
        previous_token_limit = paused["total_token_limit"]
        # Simulate three more *definitively rejected* provider requests at
        # the same unfinished role boundary. They have no accepted output.
        record = research_sessions._read(str(path), started["id"])
        rejected = next(
            step
            for step in reversed(record["steps"])
            if step.get("failure_kind") == "provider_limited"
        )
        for index in range(3):
            replay = deepcopy(rejected)
            replay["id"] = str(uuid4())
            replay["attempt_id"] = str(uuid4())
            ledger = record.get("hard_budget_ledger")
            if ledger is not None:
                assert isinstance(ledger, dict)
                reserve_before_dispatch(
                    ledger, call_id=replay["attempt_id"], request_body=b"rejected-provider-request"
                )
                settle_rejected(ledger, call_id=replay["attempt_id"])
            record["steps"].append(replay)
            record["calls_used"] += 1
        research_sessions._save(str(path), record)
        snapshot = research_sessions.get_session(str(path), started["id"])
        assert snapshot["calls_used"] == 40
        assert snapshot["protocol_completed_calls"] == 36
        assert snapshot["protocol_target_calls"] == 54
        assert snapshot["provider_limit_continuation"]["eligible"]
        # Refresh and repeated reads cannot perform a provider request.
        assert research_sessions.get_session(str(path), started["id"])["calls_used"] == 40
        assert accepted == 36

        exhausted = True
        try:
            await research_sessions.control_session(str(path), started["id"], "resume")
        except ProjectError as exc:
            assert "exactly 4 explicitly authorized additional attempts" in str(exc)
        else:
            raise AssertionError("Ordinary Resume silently increased the attempt ceiling")
        resumed = await research_sessions.control_session(
            str(path), started["id"], "repair", additional_calls=4
        )
        assert resumed["status"] == "queued"
        assert resumed["call_limit"] == 58
        assert resumed["total_token_limit"] == previous_token_limit
        assert resumed.get("maximum_estimated_cost_usd") == previous_cost_limit
        finished = await wait_for(path, started["id"])

    assert finished["calls_used"] == 58
    accepted_steps = [step for step in finished["steps"] if step.get("status") == "completed"]
    assert len(accepted_steps) == 54
    assert (
        len({(step["strategy_id"], step["role"], step["cycle"]) for step in accepted_steps}) == 54
    )
    assert saved_ids <= {item["id"] for item in finished["artifacts"]}
    assert len(finished["artifacts"]) == 27
    assert [step["id"] for step in finished["steps"][: len(previous_steps)]] == [
        step["id"] for step in previous_steps
    ]
    assert finished["termination_reason_code"] == "protocol_complete"
    assert len(finished["call_limit_adjustments"]) == 1
    assert finished["call_limit_adjustments"][0]["automatic_provider_limit_replacement"] is False
    assert finished["call_limit_adjustments"][0]["additional_calls"] == 4


def test_provider_limit_recovery_requires_known_dispatch_and_enough_turns():
    strategy_id = str(uuid4())
    record = {
        "provider_usage_limited": True,
        "cycle_limit": 3,
        "call_limit": 6,
        "calls_used": 3,
        "strategy_runs": [
            {"strategy_id": strategy_id, "status": "failed", "current_action": "Failed"}
        ],
        "steps": [
            {"strategy_id": strategy_id, "role": "investigator", "status": "completed"},
            {"strategy_id": strategy_id, "role": "skeptic", "status": "completed"},
            {
                "strategy_id": strategy_id,
                "role": "investigator",
                "status": "failed",
                "failure_kind": "provider_limited",
                "provider_input_audit": {"status": "provider_response_rejected"},
            },
        ],
    }
    branches, reason = research_sessions._provider_limit_recovery_plan(record)
    assert branches is None and "Only 3 call attempts remain" in str(reason)

    record["call_limit"] = 7
    branches, reason = research_sessions._provider_limit_recovery_plan(record)
    assert reason is None and branches == record["strategy_runs"]

    record["steps"].append(
        {
            "strategy_id": strategy_id,
            "role": "skeptic",
            "status": "failed",
            "failure_kind": "provider_error",
            "provider_input_audit": {"status": "call_failed_dispatch_unknown"},
        }
    )
    record["calls_used"] = 4
    branches, reason = research_sessions._provider_limit_recovery_plan(record)
    assert branches is None and "uncertain or non-rejected" in str(reason)
    assert "Only 3 call attempts remain" in str(reason)


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
    limits = dict(research_sessions.DEFAULT_LIMITS)
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
    limits = dict(research_sessions.DEFAULT_LIMITS)
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


async def test_e004_unsupported_achieved_no_progress_reaches_configured_rounds(
    path: Path, *, unproductive_no_progress: bool = False
):
    """An early claimed solution or unproductive report cannot truncate the protocol."""
    view, strategy, credential, config = await setup(path)
    limits = dict(research_sessions.DEFAULT_LIMITS)
    limits.update(research_rounds=3, model_calls=6)
    limits = research_sessions.save_limits(str(path), limits)
    dispatched = []

    async def handler(request):
        payload = json.loads(request.content)
        role = payload["text"]["format"]["name"]
        context = json.loads(payload["input"])
        cycle = context["cycle"]
        dispatched.append((role, cycle))
        if role == "research_investigator":
            response = investigation(cycle)
        else:
            response = {
                **skeptic(cycle, "stop", "no_progress"),
                "objective_status": "not_achieved" if unproductive_no_progress else "achieved",
                "remaining_obligations": [],
                "unresolved_objections": [],
                "next_question": "",
                "strategy_contribution": "unproductive" if unproductive_no_progress else "solution",
                "objections": [],
                "response": "The proposed result seems to cover the objective, but its proof premises are unreviewed.",
            }
        return httpx.Response(200, json=provider_response(response))

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
    assert finished["calls_used"] == 6
    assert finished["termination_reason_code"] == "protocol_complete"
    assert [artifact["strategy_cycle"] for artifact in finished["artifacts"]] == [1, 2, 3]
    assert [artifact["coordinator_decision"] for artifact in finished["artifacts"][:2]] == [
        "revise",
        "revise",
    ]
    assert len(dispatched) == 6
    if not unproductive_no_progress:
        # An unsupported positive claim is explicitly reopened. An unproductive
        # stop may already have been converted into a revision without a
        # distinct deferred-stop event; the six accepted turns prove continuity.
        assert any(
            event["kind"]
            in {
                "coordinator.provisional_stop_reopened",
                "coordinator.early_stop_deferred",
                # Preserved Investigator obligations can cause an immediate
                # revision before the legacy deferred-stop branches run.
                # The coordinator still schedules independent verification.
                "coordinator.convergence_verification_scheduled",
            }
            for event in finished["events"]
        )
        assert finished["convergence_status"] == "model_reported_unverified"
        assert all(artifact["convergence"]["reported"] for artifact in finished["artifacts"])
        assert any(event["kind"] == "research.convergence_reported" for event in finished["events"])
        assert "independent" in finished["artifacts"][0]["next_question"].lower()
    else:
        assert finished.get("convergence_status") is None
        assert not any(artifact["convergence"]["reported"] for artifact in finished["artifacts"])
    # Reaching the configured protocol is not a certification of the model's claim.
    assert finished["outcome"]["assessment"] != "positive"
    assert finished["outcome"]["solution_review"]["status"] != "achieved"
    assert finished["outcome"]["solution_review"]["verification_status"] == "incomplete"


async def test_incomplete_productive_stop_uses_remaining_round(path: Path):
    view, strategy, credential, config = await setup(path)
    limits = dict(research_sessions.DEFAULT_LIMITS)
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


if __name__ == "__main__":
    from research_sessions_split_runner import run

    run(3, half=1)
