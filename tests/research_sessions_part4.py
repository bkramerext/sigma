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


async def test_generic_objective_review_on_binary_strings(path: Path):
    problem = (
        "For each integer n >= 0, count binary strings of length n containing no two "
        "consecutive 1s. The empty string counts for n = 0. Derive and justify a general "
        "formula or recurrence for the count, including the necessary initial values. "
        "Check the result on small n. Do not assume a particular proof method."
    )
    view = initialize_project(
        path, "Counting Constrained Binary Strings", problem, research_mode="computer_science"
    )
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
        "reasoning_steps": [
            {
                "title": "Disjoint and exhaustive final-bit cases",
                "argument": (
                    "For every n >= 2 each admissible string ends in exactly one of "
                    "0 and 1, so the two final-symbol classes are disjoint and exhaustive."
                ),
                "epistemic_status": "deduction",
                "basis_artifact_ids": [],
            },
            {
                "title": "Ending-zero class",
                "argument": (
                    "Deleting a terminal 0 is a bijection between admissible n-bit "
                    "strings ending in 0 and all admissible (n-1)-bit strings."
                ),
                "epistemic_status": "deduction",
                "basis_artifact_ids": [],
            },
            {
                "title": "Ending-one class",
                "argument": (
                    "For n >= 2, an admissible string ending in 1 must end in 01. "
                    "Deleting that suffix gives a bijection to admissible (n-2)-bit strings."
                ),
                "epistemic_status": "deduction",
                "basis_artifact_ids": [],
            },
            {
                "title": "Initial counts, recurrence, and closed form",
                "argument": (
                    "The empty string gives a_0=1; 0 and 1 give a_1=2. The two "
                    "bijections prove a_n=a_(n-1)+a_(n-2) for every n >= 2, "
                    "so induction gives a_n=F_(n+2). It yields a_2=3 and a_3=5."
                ),
                "epistemic_status": "deduction",
                "basis_artifact_ids": [],
            },
        ],
        # The final-symbol split is a definition, not an unproved premise.
        "assumptions": [],
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
        "reasoning_assessments": [
            {
                "step_number": 1,
                "disposition": "accepted",
                "rationale": "Every admissible string has exactly one last bit, so these cases cover all valid strings.",
                "objection": "",
                "basis_artifact_ids": [],
            },
            {
                "step_number": 2,
                "disposition": "accepted",
                "rationale": "Appending or removing a terminal zero preserves admissibility in both directions.",
                "objection": "",
                "basis_artifact_ids": [],
            },
            {
                "step_number": 3,
                "disposition": "accepted",
                "rationale": "The forbidden adjacent ones force terminal 01, whose removal preserves admissibility.",
                "objection": "",
                "basis_artifact_ids": [],
            },
            {
                "step_number": 4,
                "disposition": "accepted",
                "rationale": "The bijections establish the recurrence for all n >= 2 and the base counts complete induction.",
                "objection": "",
                "basis_artifact_ids": [],
            },
        ],
        "assumptions_reviewed": [],
        "scientific_evidence_review": {
            "sufficiency": "sufficient_for_scoped_claim",
            "claim_kind": "formal_proof",
            "objective_requirements": [
                "Prove a counting recurrence for every n >= 2.",
                "Establish initial counts and the Fibonacci closed form.",
                "Check small n explicitly.",
            ],
            # A first-cycle review cannot cite its own not-yet-saved artifact.
            "basis_artifact_ids": [],
            "basis_step_numbers": [1, 2, 3, 4],
            "rationale": (
                "Accepted disjoint cases and two bijections establish the universal "
                "recurrence, initial values, and induction without empirical premises."
            ),
        },
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
    # The test concerns terminal-session removal and numbering, not an
    # early model-decided research stop. Configure a complete single round.
    limits = dict(research_sessions.DEFAULT_LIMITS)
    limits.update(research_rounds=1, model_calls=2)
    limits = research_sessions.save_limits(str(path), limits)
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
        assert research_sessions.get_limits(str(path)) == limits
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
        # Background provider dispatch can take longer under CI contention.
        await asyncio.wait_for(entered.wait(), 10)
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


async def test_remove_paused_session_stops_it_before_deleting(path: Path):
    """A session displayed as stopped can be removed without resuming provider work."""
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
        paused = await research_sessions.control_session(str(path), started["id"], "pause")
        assert paused["status"] == "paused"

        # The revision guard still protects against removing stale UI state.
        try:
            await research_sessions.remove_session(str(path), started["id"], "stale-revision")
        except ProjectError as exc:
            assert "changed" in str(exc)
        else:
            raise AssertionError("stale paused session removal was accepted")
        assert research_sessions.get_session(str(path), started["id"])["status"] == "paused"

        removed = await research_sessions.remove_session(
            str(path), started["id"], paused["updated_at"]
        )
        assert removed == {"removed": True, "id": started["id"], "session_number": 1}
        assert research_sessions.list_sessions(str(path)) == []
        assert research_sessions._tasks.get(started["id"]) is None

        next_session = await research_sessions.start_session(
            str(path), strategy.id, str(uuid4()), view.project.id, credential["identity"]
        )
        assert next_session["session_number"] == 2
        await research_sessions.control_session(str(path), next_session["id"], "stop")


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


async def test_project_edits_do_not_pause_research_but_account_changes_do(path: Path):
    view, strategy, credential, config = await setup(path)
    entered = asyncio.Event()
    release = asyncio.Event()
    provider_calls = []

    original_role_call = research_sessions._portfolio_role_call

    async def pinned_configuration(*, view, context, frozen_model=None, frozen_effort=None):
        # Future user settings may change, but a running session explicitly
        # supplies its frozen model/effort on every subsequent provider call.
        assert frozen_model in (None, MODEL)
        assert frozen_effort in (None, "high")
        return config

    async def blocked_role_call(*args, **kwargs):
        entered.set()
        await release.wait()
        return await original_role_call(*args, **kwargs)

    async def handler(request):
        provider_calls.append(request)
        role = json.loads(request.content)["text"]["format"]["name"]
        output = skeptic(1, "stop") if role == "research_skeptic" else investigation(1)
        return httpx.Response(200, json=provider_response(output))

    with (
        patch.object(research_sessions, "auth_context", new=AsyncMock(return_value=credential)),
        patch.object(
            research_sessions, "configuration", new=AsyncMock(side_effect=pinned_configuration)
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
            str(path), strategy.id, str(uuid4()), view.project.id, credential["identity"]
        )
        await asyncio.wait_for(entered.wait(), 2)
        edit_strategy(
            str(path), strategy.id, strategy.title, strategy.approach + " Revised source."
        )
        set_strategy_enabled(str(path), strategy.id, False)
        current = inspect_project(path).project
        update_project(
            str(path),
            current.title,
            current.problem + " (edited after session started)",
            getattr(current.investigation_type, "value", current.investigation_type),
            current.ai_model,
            "medium",
            {
                "title": current.title,
                "problem": current.problem,
                "investigation_type": getattr(
                    current.investigation_type, "value", current.investigation_type
                ),
                "ai_model": current.ai_model,
                "reasoning_effort": current.reasoning_effort,
                "difficulty": current.difficulty.value if current.difficulty else None,
                "show_advanced_outcome_details": False,
            },
            show_advanced_outcome_details=True,
        )
        assert not inspect_project(path).project.show_advanced_outcome_details
        assert inspect_project(path).project.reasoning_effort == current.reasoning_effort
        release.set()
        continued = await wait_for(path, started["id"])
    assert continued["status"] in {"completed", "ended"}, continued["message"]
    assert continued["calls_used"] >= 2
    assert len(provider_calls) >= 2
    # The running session must retain its original, accepted strategy.
    persisted = research_sessions._read(str(path), started["id"])
    assert persisted["strategy_text"] == strategy.approach
    assert persisted["strategy_runs"][0]["strategy_text"] == strategy.approach
    assert persisted["problem"] == view.project.problem
    assert persisted["model"] == config["model"]

    account_path = path.parent / "account-change.sigma"
    account_view, account_strategy, account_credential, account_config = await setup(account_path)
    entered.clear()
    release.clear()
    provider_calls.clear()
    account_check_count = 0

    async def switched_account():
        nonlocal account_check_count
        account_check_count += 1
        return (
            account_credential
            if account_check_count == 1
            else {**account_credential, "identity": "other", "token": "new-account-token"}
        )

    with (
        patch.object(research_sessions, "auth_context", new=switched_account),
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
        continued = await wait_for(account_path, started["id"])
    assert continued["status"] in {"completed", "ended"}, continued["message"]
    assert continued["calls_used"] >= 2
    assert len(provider_calls) >= 2
    assert all(
        call.headers["Authorization"] == "Bearer new-account-token" for call in provider_calls
    )
    assert research_sessions._read(str(account_path), started["id"])["identity_hash"] == (
        research_sessions._digest(account_credential["identity"])
    )


async def test_native_stopped_session_moves_between_providers(path: Path) -> None:
    """Unimported project research can change providers without replaying calls."""
    view, strategy, account, config = await setup(path)
    current = {"account": account}

    async def connected_account():
        return current["account"]

    with (
        patch.object(research_sessions, "auth_context", new=connected_account),
        patch.object(research_sessions, "configuration", new=AsyncMock(return_value=config)),
        patch.object(research_sessions, "_worker", new=AsyncMock()),
    ):
        started = await research_sessions.start_session(
            str(path), strategy.id, str(uuid4()), view.project.id, account["identity"]
        )
        await asyncio.sleep(0)
        stopped = await research_sessions.control_session(str(path), started["id"], "stop")
        assert stopped["status"] == "stopped"
        original = deepcopy(research_sessions._read(str(path), started["id"]))
        current["account"] = {
            **account,
            "mode": "chatgpt",
            "identity": "chatgpt:other-account",
            "token": "different-provider-token",
        }
        resumed = await research_sessions.control_session(str(path), started["id"], "resume")
        assert resumed["status"] == "queued"
        saved = research_sessions._read(str(path), started["id"])
        assert saved["mode"] == "chatgpt"
        assert saved["identity_hash"] == research_sessions._digest("chatgpt:other-account")
        assert saved["steps"] == original["steps"]
        assert saved["artifacts"] == original["artifacts"]
        assert saved["calls_used"] == original["calls_used"]
        assert saved["transport_change_history"][-1]["reason"] == (
            "stopped_session_provider_change"
        )
        assert saved["imported_via_bundle"] is False


def test_model_switch_preserves_old_hard_budget_costs() -> None:
    """Old settled calls retain their cost; future calls use the new model price."""
    current_model = MODEL
    target_model = next(
        name for name in research_sessions.TOKEN_PRICES_PER_MILLION if name != current_model
    )
    old_price = research_sessions.TOKEN_PRICES_PER_MILLION[current_model]
    new_price = research_sessions.TOKEN_PRICES_PER_MILLION[target_model]
    ledger = new_ledger(
        call_limit=8,
        input_token_limit=500_000,
        output_tokens_per_call=4000,
        cost_limit_usd=100,
        input_price_per_million=max(old_price["input"], old_price["cache_write"]),
        output_price_per_million=old_price["output"],
    )
    reserve_before_dispatch(ledger, call_id="old-call", request_body=b"first request")
    settle_after_response(ledger, call_id="old-call", input_tokens=10, output_tokens=20)
    old_call = deepcopy(ledger["calls"][0])
    record = {
        "status": "stopped",
        "mode": "api_key",
        "model": current_model,
        "reasoning_effort": "high",
        "identity_hash": "former-account",
        "steps": [],
        "hard_budget_ledger": ledger,
        "estimated_cost_reserved_usd": 0.0,
    }
    with patch.object(research_sessions.cloud_research, "billing_enabled", return_value=False):
        research_sessions._rebind_provider_transport(
            record,
            {"identity": "chatgpt:new", "mode": "chatgpt"},
            {"model": target_model, "reasoning_effort": "medium"},
        )
    assert record["model"] == target_model
    assert ledger["calls"][0] == old_call
    assert ledger["input_price_per_million"] == max(new_price["input"], new_price["cache_write"])
    assert ledger["output_price_per_million"] == new_price["output"]
    reserve_before_dispatch(ledger, call_id="future-call", request_body=b"future")
    assert ledger["calls"][0] == old_call
    unknown = deepcopy(record)
    unknown["steps"] = [
        {"role": "investigator", "status": "interrupted", "attempt_status": "unknown"}
    ]
    try:
        research_sessions._validate_provider_transport_change(unknown, next_model=current_model)
    except ProjectError as exc:
        assert "unknown" in str(exc)
    else:
        raise AssertionError("Transport migration replayed an unknown provider attempt")

    # A live pill change may occur while an earlier strategy call is still in
    # flight. The old call's model and price stay pinned; only future calls
    # inherit the newly selected model/Thinking pair.
    in_flight = new_ledger(
        call_limit=5,
        input_token_limit=500_000,
        output_tokens_per_call=4000,
        cost_limit_usd=100,
        input_price_per_million=max(old_price["input"], old_price["cache_write"]),
        output_price_per_million=old_price["output"],
    )
    reserve_before_dispatch(in_flight, call_id="in-flight", request_body=b"old model")
    live = {
        "mode": "api_key",
        "model": current_model,
        "reasoning_effort": "high",
        "steps": [{"id": "in-flight", "role": "investigator", "status": "running"}],
        "hard_budget_ledger": in_flight,
    }
    research_sessions._apply_live_model_selection(
        live, {"model": target_model, "reasoning_effort": "medium"}
    )
    assert (live["model"], live["reasoning_effort"]) == (target_model, "medium")
    assert live["steps"][0]["model"] == current_model
    assert live["steps"][0]["reasoning_effort"] == "high"
    assert live["model_change_history"][-1]["calls_used"] == 0
    assert "already dispatched" in live["events"][-1]["message"].lower()
    settle_after_response(
        in_flight,
        call_id="in-flight",
        input_tokens=100,
        output_tokens=40,
        input_price_per_million=max(old_price["input"], old_price["cache_write"]),
        output_price_per_million=old_price["output"],
    )
    historical = in_flight["calls"][0]["cost_bound_usd"]
    assert (
        abs(
            historical
            - (100 * max(old_price["input"], old_price["cache_write"]) + 40 * old_price["output"])
            / 1_000_000
        )
        < 1e-10
    )
    reserve_before_dispatch(in_flight, call_id="new-model", request_body=b"new model")
    assert in_flight["calls"][1]["cost_bound_usd"] > 0
    assert in_flight["calls"][0]["cost_bound_usd"] == historical


async def test_emailed_project_import_resumes_under_recipient_provider(path: Path):
    """Real start/stop/export/import/Resume, not just synthetic path-rewrite tests."""
    from sigma.project_email import email_project_bundle
    from sigma.project_transfer import import_project

    view, strategy, sender, config = await setup(path)

    async def idle_worker(*_args):
        # Admission and persistence are real; a provider call would be unsafe.
        return None

    with (
        patch.object(research_sessions, "auth_context", new=AsyncMock(return_value=sender)),
        patch.object(research_sessions, "configuration", new=AsyncMock(return_value=config)),
        patch.object(research_sessions, "_worker", new=idle_worker),
    ):
        started = await research_sessions.start_session(
            str(path), strategy.id, str(uuid4()), view.project.id, sender["identity"]
        )
        await asyncio.sleep(0)
        stopped = await research_sessions.control_session(str(path), started["id"], "stop")
        assert stopped["status"] == "stopped"

    payload, _filename = email_project_bundle(str(path))
    for label, recipient_mode in (("same", "api_key"), ("different", "chatgpt")):
        receiver_path = path.parent / f"email-recipient-{label}.sigma"
        import_project(json.loads(payload), receiver_path)
        recipient_project_id = inspect_project(receiver_path).project.id
        assert recipient_project_id != view.project.id
        imported = research_sessions._all(str(receiver_path))[0]
        recipient_session_id = imported["id"]
        assert recipient_session_id != started["id"]
        assert imported["source_session_id"] == started["id"]
        assert imported["imported_via_bundle"] is True
        assert imported["project_path"] == str(receiver_path.resolve())
        assert imported["status"] == "stopped"
        assert imported["project_id"] == recipient_project_id

        recipient = {
            **sender,
            "identity": "independent-researcher-" + label,
            "mode": recipient_mode,
            "token": "recipient-credential-" + label,
        }
        with (
            patch.object(research_sessions, "auth_context", new=AsyncMock(return_value=recipient)),
            patch.object(research_sessions, "configuration", new=AsyncMock(return_value=config)),
            patch.object(research_sessions, "_worker", new=idle_worker),
        ):
            resumed = await research_sessions.control_session(
                str(receiver_path), recipient_session_id, "resume"
            )
            assert resumed["status"] == "queued", resumed.get("message")
            saved = research_sessions._read(str(receiver_path), recipient_session_id)
            assert saved["mode"] == recipient_mode
            assert saved["project_id"] == recipient_project_id
            assert saved["status"] == "queued"
            assert saved["calls_used"] == stopped["calls_used"]
            assert saved["steps"] == research_sessions._read(str(path), started["id"])["steps"]
            assert saved["transport_change_history"][-1]["to_mode"] == recipient_mode
            assert saved["identity_hash"] == research_sessions._digest(recipient["identity"])
            assert saved["imported_via_bundle"] is False


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
    view = initialize_project(
        path,
        "Metrics fixture",
        "A persisted evidence accounting test",
        research_mode="mathematical",
    )
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
                    assert outcome["assessment"] == "mixed"
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
    limits = dict(research_sessions.DEFAULT_LIMITS)
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
    from hashlib import sha256

    def frozen_method(url: str) -> dict[str, object]:
        # This is a provider-free dispatch test, not a live-site availability
        # check. Return inspected, checksum-valid source content for PDFs too.
        excerpt = (
            "Deterministic offline methodological reference. Explicitly distinguish "
            "observations, uncertainty, and assumptions in the tested argument. "
            "Use reproducible analysis rather than unsupported inference. "
            f"Configured URL: {url}"
        )
        digest = sha256(excerpt.encode("utf-8")).hexdigest()
        return {
            "status": "retrieved",
            "url": url,
            "excerpt": excerpt,
            "excerpt_sha256": digest,
            "content_sha256": digest,
            "reason": None,
        }

    cases = (
        (
            "biology",
            "Does an observed growth change survive control for batch effects?",
            "Growth under different reagent conditions",
            "Reagent and culture batches were assigned independently.",
            "Compare within-batch replicate growth estimates before any causal claim.",
        ),
        (
            "philosophy",
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
        limits = dict(research_sessions.DEFAULT_LIMITS)
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
            patch(
                "sigma.research_reference_content.freeze_reference_content",
                side_effect=frozen_method,
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


def test_parallel_funding_uses_estimates_without_changing_provider_request() -> None:
    record = {
        "mode": "api_key",
        "model": MODEL,
        "reasoning_effort": "high",
        "output_token_limit": 4000,
    }
    context = {"problem": "Shared research objective", "strategy": "Independent approach"}
    provider_request = research_sessions._role_request_payload(record, "investigator", context)
    assert provider_request["max_output_tokens"] == research_sessions.MODEL_OUTPUT_LIMITS[MODEL]
    cost_estimate = research_sessions._reserve_cost(record, context, "investigator", estimate=True)
    legacy_worst_case = research_sessions._reserve_cost(record, context, "investigator")
    assert cost_estimate is not None and legacy_worst_case is not None
    assert 0 < cost_estimate < legacy_worst_case


def test_portfolio_capacity_tracks_strategies_not_billing_mode() -> None:
    for sponsored in (True, False):
        with patch.object(
            research_sessions.cloud_research, "billing_enabled", return_value=sponsored
        ):
            assert research_sessions._portfolio_call_concurrency(1) == 1
            assert research_sessions._portfolio_call_concurrency(12) == 12
    with patch.dict("os.environ", {"SIGMA_RESEARCH_GLOBAL_INFLIGHT": "32"}):
        assert research_sessions._portfolio_global_limit() == 32


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


def test_obligation_dispatch_citations_exclude_withheld_history() -> None:
    """No paid Skeptic response should be invited to cite unsupplied IDs."""
    from copy import deepcopy

    saved = {
        "obligation_id": "open-1",
        "status": "unresolved",
        "text": "Check the counterexample.",
        "source_artifact_ids": ["present", "withheld", "prior"],
        "source_artifact_count": 5,
        "basis_artifact_ids": ["present", "withheld"],
        "supplied_source_artifact_ids": ["present", "withheld"],
        "pointer_source_artifact_ids": ["withheld"],
        "source_step_ids": ["old-step", "current-step"],
        "basis_step_ids": ["old-step", "current-step"],
        "source_artifact_availability": "adequate_bounded_extract_original_not_supplied",
    }
    original = deepcopy(saved)
    context = {
        "context_artifact_ids": ["present"],
        "prior_session_artifact_ids": ["prior"],
        "investigator_step_id": "current-step",
        "obligation_ledger": [deepcopy(saved)],
    }
    research_sessions.restrict_obligation_citations_to_supplied_context(context)
    actual = context["obligation_ledger"][0]
    assert actual["source_artifact_ids"] == ["present", "prior"]
    assert actual["supplied_source_artifact_ids"] == ["present"]
    assert actual["basis_artifact_ids"] == ["present"]
    assert actual["pointer_source_artifact_ids"] == []
    assert actual["source_artifact_count"] == 5
    assert actual["unsupplied_source_artifact_count"] == 3
    assert actual["withheld_pointer_source_count"] == 1
    assert actual["source_step_ids"] == ["current-step"]
    assert actual["basis_step_ids"] == ["current-step"]
    assert actual["withheld_source_step_ids_count"] == 1
    assert actual["source_artifact_availability"] == ("incomplete_extract_original_not_supplied")
    assert saved == original, "Only the dispatch copy may change"

    # Portfolio contexts pass through this normalization after their base
    # agent context, so repeated finalization must retain omission accounting.
    research_sessions.restrict_obligation_citations_to_supplied_context(context)
    assert actual["withheld_pointer_source_count"] == 1
    assert actual["withheld_source_step_ids_count"] == 1

    allowed = {
        "context_artifact_ids": ["present"],
        "prior_session_artifact_ids": [],
        "investigator_step_id": "current-step",
        "obligation_ledger": [
            {
                "obligation_id": "open-2",
                "source_artifact_ids": ["present"],
                "source_artifact_count": 1,
                "supplied_source_artifact_ids": ["present"],
                "source_step_ids": ["current-step"],
                "source_artifact_availability": "adequate_bounded_extract_original_not_supplied",
            }
        ],
    }
    research_sessions.restrict_obligation_citations_to_supplied_context(allowed)
    assert allowed["obligation_ledger"][0]["source_artifact_ids"] == ["present"]
    assert allowed["obligation_ledger"][0]["source_artifact_availability"] == (
        "adequate_bounded_extract_original_not_supplied"
    )


def test_obligation_dispatch_request_contains_only_supplied_citations() -> None:
    """Inspect the final serialized Skeptic inputs for both context builders."""
    with TemporaryDirectory() as temporary:
        path = Path(temporary) / "dispatch-citation-audit.sigma"
        _test_obligation_dispatch_request_contains_only_supplied_citations(path)


def _test_obligation_dispatch_request_contains_only_supplied_citations(path: Path) -> None:
    from copy import deepcopy

    view = initialize_project(path, "Dispatch citation audit", "Check evidence references.")
    strategy_id = str(uuid4())
    peer_strategy_id = str(uuid4())
    investigator_step_id = str(uuid4())
    source = {
        "id": "selected-source",
        "project_id": view.project.id,
        "session_id": "saved-session",
        "strategy_id": strategy_id,
        "strategy_title": "Selected strategy",
        "sequence": 1,
        "strategy_cycle": 1,
        "claim_or_question": "Selected bounded evidence.",
        "evidence_status": "unverified extract",
    }
    obligation = {
        "obligation_id": "open-1",
        "strategy_id": strategy_id,
        "status": "unresolved",
        "text": "Review the counterexample.",
        "source_artifact_ids": ["selected-source", "prior-source", "withheld-source"],
        "source_artifact_count": 3,
        "basis_artifact_ids": ["selected-source", "withheld-source"],
        "supplied_source_artifact_ids": ["selected-source", "withheld-source"],
        "pointer_source_artifact_ids": ["withheld-source"],
        "source_step_ids": ["old-step"],
        "basis_step_ids": ["old-step"],
    }
    record = {
        "id": str(uuid4()),
        "project_path": view.path,
        "project_id": view.project.id,
        "project_title": view.project.title,
        "problem": view.project.problem,
        "model": MODEL,
        "reasoning_effort": "high",
        "mode": "chatgpt",
        "strategy_ids": [strategy_id, peer_strategy_id],
        "strategy_id": strategy_id,
        "strategy_title": "Selected strategy",
        "strategy_text": "Inspect supplied evidence.",
        "current_question": "Review the saved counterexample.",
        "strategy_snapshot": [],
        "artifacts": [source],
        "steps": [
            {
                "id": investigator_step_id,
                "strategy_id": strategy_id,
                "role": "investigator",
                "cycle": 2,
                "status": "completed",
            }
        ],
        "prior_session_findings": [
            {"id": "prior-source", "claim_or_question": "Prior supplied extract."}
        ],
        "prior_session_obligations": [deepcopy(obligation)],
        "pending_investigation": {"claim": "Current claim.", "open_obligations": []},
        "status": "running",
    }
    original_obligation = deepcopy(record["prior_session_obligations"][0])
    branch = {
        "strategy_id": strategy_id,
        "strategy_title": "Selected strategy",
        "strategy_text": "Inspect supplied evidence.",
        "current_question": "Review the saved counterexample.",
        "cycle": 1,
        "status": "running",
        "pending_investigation": record["pending_investigation"],
    }

    contexts = (
        research_sessions._agent_context(record, "skeptic", 2),
        research_sessions._portfolio_context(record, branch, "skeptic", 2),
    )
    for context in contexts:
        payload = research_sessions._role_request_payload(record, "skeptic", context)
        exact_input = json.loads(payload["input"][0]["content"])
        ledger_entry = exact_input["obligation_ledger"][0]
        assert ledger_entry["source_artifact_ids"] == ["selected-source", "prior-source"]
        assert ledger_entry["basis_artifact_ids"] == ["selected-source"]
        assert ledger_entry["supplied_source_artifact_ids"] == [
            "selected-source",
            "prior-source",
        ]
        assert ledger_entry["pointer_source_artifact_ids"] == []
        assert ledger_entry["withheld_pointer_source_count"] == 1
        assert ledger_entry["withheld_source_step_ids_count"] == 1
        assert ledger_entry["withheld_basis_step_ids_count"] == 1
        assert "withheld-source" not in json.dumps(ledger_entry)
        assert "old-step" not in json.dumps(ledger_entry)
    assert record["prior_session_obligations"][0] == original_obligation


def test_e004_e005_e006_e009_e010_e011_saved_protocol_recovery_plans() -> None:
    """Sanitized six-pilot shapes: do not replay accepted, rejected or unknown calls."""

    def step(sid: str, role: str, cycle: int, status: str = "completed", *, kind=""):
        item = {
            "id": f"{sid}-{role}-{cycle}-{status}",
            "strategy_id": sid,
            "role": role,
            "cycle": cycle,
            "status": status,
        }
        if status == "failed":
            item.update(
                failure_kind=kind,
                attempt_status="not_dispatched" if kind == "budget_denied" else "usage_estimated",
                provider_input_audit={
                    "status": "prepared_before_dispatch"
                    if kind == "budget_denied"
                    else "provider_response_invalid"
                },
            )
        if status == "interrupted":
            item.update(
                failure_kind="interrupted",
                attempt_status="unknown",
                provider_input_audit={"status": "call_interrupted_dispatch_unknown"},
            )
        return item

    def done(sid: str, through: list[tuple[str, int]]):
        return [step(sid, role, cycle) for role, cycle in through]

    def branch(sid: str, status: str, cycle: int, pending: bool = False):
        return {
            "strategy_id": sid,
            "status": status,
            "cycle": cycle,
            "pending_investigation": {"claim": "saved argument"} if pending else None,
        }

    full = [(role, cycle) for cycle in (1, 2, 3) for role in ("investigator", "skeptic")]
    cases = [
        (
            "E-004 Maximum Regions",
            "ended",
            [branch("math", "ended", 1)],
            done("math", full[:2]),
            4,
            2,
        ),
        (
            "E-005 Nonconsecutive Subsets",
            "ended",
            [branch("generating", "ended", 1), branch("matrix", "failed", 1)],
            done("generating", full[:2])
            + [step("matrix", "investigator", 1, "failed", kind="response_invalid")],
            10,
            2,
        ),
        (
            "E-006/E-011 Warp",
            "ended",
            [branch("geometry", "ended", 3), branch("physical", "failed", 2, True)],
            done("geometry", full[:4])
            + done("physical", full[:3])
            + [
                step("physical", "skeptic", 2, "failed", kind="response_invalid"),
                step("physical", "investigator", 3, "failed", kind="budget_denied"),
            ],
            5,
            7,
        ),
        (
            "E-009 AI Agent",
            "stopped",
            [branch("failure", "failed", 1, True), branch("recovery", "paused", 2)],
            done("failure", full[:1])
            + done("recovery", full[:2])
            + [
                step("recovery", "investigator", 2, "failed", kind="budget_denied"),
                step("recovery", "investigator", 2, "interrupted"),
            ],
            9,
            3,
        ),
        (
            "E-010 Sovereign",
            "ended",
            [branch("federation", "failed", 3, True), branch("governance", "ended", 3)],
            done("federation", full[:5])
            + done("governance", full)
            + [step("federation", "skeptic", 3, "failed", kind="response_invalid")],
            1,
            11,
        ),
    ]
    for name, status, branches, steps, expected_missing, expected_accepted in cases:
        record = {
            "status": status,
            "cycle_limit": 3,
            "call_limit": 30,
            "calls_used": expected_accepted + len(steps) - expected_accepted,
            "strategy_runs": branches,
            "steps": steps,
        }
        plan, error = research_sessions._protocol_completion_recovery_plan(record)
        assert error is None and plan is not None, (name, error)
        assert plan["completed_turns"] == expected_accepted, name
        assert plan["required_calls"] == expected_missing, (name, plan)
        assert all(item["recovery_context"]["new_request"] for item in plan["branches"])
        assert record["steps"] == steps
    unknown_plan, unknown_error = research_sessions._protocol_completion_recovery_plan(
        {
            "status": "stopped",
            "cycle_limit": 3,
            "call_limit": 18,
            "calls_used": 4,
            "strategy_runs": [branch("recovery", "paused", 2)],
            "steps": done("recovery", full[:2])
            + [step("recovery", "investigator", 2, "interrupted")],
        }
    )
    assert unknown_error is None and unknown_plan is not None
    assert any(item["role"] == "investigator" for item in unknown_plan["branches"])


def test_terminal_protocol_completion_plan_preserves_attempt_history() -> None:
    def branch(identifier: str, *, status: str = "ended", cycle: int = 3, pending=None):
        return {
            "strategy_id": identifier,
            "strategy_title": identifier,
            "strategy_text": "Independent bounded strategy.",
            "status": status,
            "cycle": cycle,
            "current_question": "",
            "pending_investigation": pending,
            "last_decision": "stop_productive_conclusion",
        }

    def step(strategy_id: str, role: str, cycle: int, status: str = "completed"):
        item = {
            "id": f"{strategy_id}-{role}-{cycle}-{status}",
            "strategy_id": strategy_id,
            "role": role,
            "cycle": cycle,
            "status": status,
        }
        if status == "interrupted":
            item["failure_kind"] = "interrupted"
            item["provider_input_audit"] = {"status": "call_interrupted_dispatch_unknown"}
        elif status == "failed":
            item["failure_kind"] = "response_invalid"
            item["provider_input_audit"] = {"status": "provider_response_invalid"}
        return item

    first, second = "strategy-a", "strategy-b"
    completed = [
        step(strategy, role, cycle)
        for strategy in (first, second)
        for cycle in (1, 2)
        for role in ("investigator", "skeptic")
    ]
    completed += [step(strategy, "investigator", 3) for strategy in (first, second)]
    uncertain = step(first, "skeptic", 3, "interrupted")
    record = {
        "id": str(uuid4()),
        "status": "paused",
        "cycle_limit": 3,
        "call_limit": 18,
        "calls_used": 18,
        "strategy_runs": [
            branch(first, status="paused", cycle=3, pending={"claim": "Saved claim A"}),
            branch(second, status="paused", cycle=3, pending={"claim": "Saved claim B"}),
        ],
        "steps": completed + [uncertain, step(second, "skeptic", 3, "interrupted")],
    }
    plan, error = research_sessions._protocol_completion_recovery_plan(record)
    assert error is None and plan is not None
    assert plan["completed_turns"] == 10
    assert plan["required_calls"] == 2
    assert {item["strategy_id"] for item in plan["branches"]} == {first, second}
    assert all(item["role"] == "skeptic" and item["cycle"] == 3 for item in plan["branches"])
    assert all("unknown" in item["recovery_context"]["reason"] for item in plan["branches"])
    assert record["calls_used"] == 18
    assert uncertain["status"] == "interrupted"

    unsafe = deepcopy(record)
    unsafe["steps"][-1]["role"] = "investigator"
    unsafe["steps"] = [
        item
        for item in unsafe["steps"]
        if not (
            item.get("strategy_id") == second
            and item.get("role") == "investigator"
            and item.get("cycle") == 3
            and item.get("status") == "completed"
        )
    ]
    unsafe["strategy_runs"][1]["cycle"] = 2
    unsafe["strategy_runs"][1]["pending_investigation"] = None
    plan, error = research_sessions._protocol_completion_recovery_plan(unsafe)
    assert plan is None and error is not None and "will not replay" in error


def test_protocol_completion_rejects_invalid_or_duplicate_accepted_slots() -> None:
    strategy = "strategy-a"
    accepted = [
        {
            "id": f"accepted-{index}",
            "strategy_id": strategy,
            "role": role,
            "cycle": cycle,
            "status": "completed",
        }
        for index, (role, cycle) in enumerate(
            (
                ("investigator", 1),
                ("skeptic", 1),
                ("investigator", 2),
                ("skeptic", 2),
                ("investigator", 3),
                ("investigator", 4),
            )
        )
    ]
    record = {
        "status": "ended",
        "cycle_limit": 3,
        "steps": accepted,
        "strategy_runs": [
            {
                "strategy_id": strategy,
                "status": "ended",
                "cycle": 3,
                "pending_investigation": {"claim": "Unreviewed finding"},
            }
        ],
    }
    # Six accepted *counts* must not hide the missing third-round Skeptic.
    plan, error = research_sessions._protocol_completion_recovery_plan(record)
    assert plan is None and error is not None and "out-of-range" in error

    record["steps"][-1]["cycle"] = True
    plan, error = research_sessions._protocol_completion_recovery_plan(record)
    assert plan is None and error is not None and "non-integer round" in error
    record["steps"][-1]["cycle"] = ["unhashable"]
    plan, error = research_sessions._protocol_completion_recovery_plan(record)
    assert plan is None and error is not None and "non-integer round" in error

    record["steps"][-1]["cycle"] = 3
    record["steps"][-1]["role"] = "investigator"
    plan, error = research_sessions._protocol_completion_recovery_plan(record)
    assert plan is None and error is not None and "duplicate accepted" in error

    record["steps"][-1]["role"] = "skeptic"
    record["steps"][-1]["strategy_id"] = "unknown-strategy"
    plan, error = research_sessions._protocol_completion_recovery_plan(record)
    assert plan is None and error is not None and "unknown strategy" in error

    record["steps"][-1]["strategy_id"] = strategy
    record["strategy_runs"].append({**record["strategy_runs"][0]})
    plan, error = research_sessions._protocol_completion_recovery_plan(record)
    assert plan is None and error is not None and "duplicate strategy" in error


def test_terminal_protocol_completion_allows_known_invalid_response_replacement() -> None:
    first, second = "strategy-a", "strategy-b"
    steps = []
    for strategy in (first, second):
        steps.extend(
            [
                {
                    "id": f"{strategy}-i1",
                    "strategy_id": strategy,
                    "role": "investigator",
                    "cycle": 1,
                    "status": "completed",
                },
                {
                    "id": f"{strategy}-s1-invalid",
                    "strategy_id": strategy,
                    "role": "skeptic",
                    "cycle": 1,
                    "status": "failed",
                    "failure_kind": "response_invalid",
                    "provider_input_audit": {"status": "provider_response_invalid"},
                },
            ]
        )
    record = {
        "status": "failed",
        "cycle_limit": 3,
        "call_limit": 15,
        "calls_used": 4,
        "steps": steps,
        "strategy_runs": [
            {
                "strategy_id": strategy,
                "strategy_title": strategy,
                "strategy_text": "Independent bounded strategy.",
                "status": "failed",
                "cycle": 1,
                "current_question": "Question one",
                "pending_investigation": {"claim": f"Saved {strategy} claim"},
            }
            for strategy in (first, second)
        ],
    }
    plan, error = research_sessions._protocol_completion_recovery_plan(record)
    assert error is None and plan is not None
    assert plan["completed_turns"] == 2
    assert plan["required_calls"] == 10
    assert all(item["role"] == "skeptic" and item["cycle"] == 1 for item in plan["branches"])
    assert all("invalid" in item["recovery_context"]["reason"] for item in plan["branches"])

    record["call_limit"] = 12
    assert record["call_limit"] - record["calls_used"] == 8
    assert plan["required_calls"] - (record["call_limit"] - record["calls_used"]) == 2


async def test_provider_limit_unsafe_fallback_cannot_resume(path: Path) -> None:
    """Both recovery planners can reject; neither failure authorizes dispatch."""
    view, strategy, credential, config = await setup(path)

    with (
        patch.object(research_sessions, "auth_context", new=AsyncMock(return_value=credential)),
        patch.object(research_sessions, "configuration", new=AsyncMock(return_value=config)),
        patch.object(research_sessions, "_worker", new=AsyncMock()),
    ):
        started = await research_sessions.start_session(
            str(path), strategy.id, str(uuid4()), view.project.id, credential["identity"]
        )
        await asyncio.sleep(0)
        record = research_sessions._read(str(path), started["id"])
        record.update(
            {
                "status": "paused",
                "stopped_at": datetime.now(UTC).isoformat(),
                "provider_usage_limited": True,
                "cycle_limit": 1,
                "call_limit": 2,
                "calls_used": 1,
                "steps": [
                    {
                        "id": str(uuid4()),
                        "strategy_id": strategy.id,
                        "role": "investigator",
                        "cycle": 1,
                        "status": "running",
                        "attempt_status": "unknown",
                    }
                ],
            }
        )
        record["strategy_runs"][0].update(
            {"status": "paused", "cycle": 1, "pending_investigation": None}
        )
        # Simulate historical ChatGPT-plan sessions with no hard budget ledger.
        record.pop("hard_budget_ledger", None)
        research_sessions._save(str(path), record)
        original = research_sessions._read(str(path), started["id"])
        assert research_sessions._provider_limit_safe_plan(record)[0] is None
        assert research_sessions._protocol_completion_recovery_plan(record)[0] is None
        try:
            await research_sessions.control_session(str(path), started["id"], "resume")
        except ProjectError as exc:
            assert "inconsistent role attempt" in str(exc)
        else:
            raise AssertionError("Unsafe provider-limit fallback requeued incomplete research")
        assert research_sessions._read(str(path), started["id"]) == original


async def test_restart_missing_provider_reservation_is_durably_blocked(path: Path) -> None:
    """An unknown dispatched request cannot disappear from paid accounting."""
    view, strategy, credential, config = await setup(path)
    with (
        patch.object(research_sessions, "auth_context", new=AsyncMock(return_value=credential)),
        patch.object(research_sessions, "configuration", new=AsyncMock(return_value=config)),
        patch.object(research_sessions, "_worker", new=AsyncMock()),
    ):
        started = await research_sessions.start_session(
            str(path), strategy.id, str(uuid4()), view.project.id, credential["identity"]
        )
        await asyncio.sleep(0)
        record = research_sessions._read(str(path), started["id"])
        dispatched_id = str(uuid4())
        record.update(
            {
                "status": "running",
                "calls_used": 1,
                "steps": [
                    {
                        "id": dispatched_id,
                        "strategy_id": strategy.id,
                        "role": "investigator",
                        "cycle": 1,
                        "status": "running",
                        "attempt_status": "unknown",
                        "cost_reserve": 0.2,
                    }
                ],
                "hard_budget_ledger": new_ledger(
                    call_limit=2,
                    input_token_limit=400_000,
                    output_tokens_per_call=4_000,
                    cost_limit_usd=100.0,
                    input_price_per_million=1.0,
                    output_price_per_million=2.0,
                ),
            }
        )
        record["strategy_runs"][0].update({"status": "running", "cycle": 1, "calls_used": 1})
        research_sessions._save(str(path), record)
        # Emulate a new backend process: the old in-memory worker is gone.
        research_sessions._tasks.pop(started["id"], None)
        research_sessions._control.pop(started["id"], None)
        recovered = research_sessions._recover(research_sessions._read(str(path), started["id"]))
        assert recovered["status"] == "paused"
        assert recovered["steps"][0]["status"] == "interrupted"
        assert (
            recovered["hard_budget_ledger"]["blocked_reason"]
            == "Saved interrupted provider call has no matching reservation"
        )
        try:
            await research_sessions.control_session(str(path), started["id"], "resume")
        except ProjectError as exc:
            assert "no matching billing reservation" in str(exc)
        else:
            raise AssertionError("Unaccounted interrupted call admitted another provider request")
        saved = research_sessions._read(str(path), started["id"])
        assert saved["status"] == "paused"
        assert saved["steps"][0]["status"] == "interrupted"
        assert saved["steps"][0]["id"] == dispatched_id
        assert "no matching reservation" in saved["hard_budget_ledger"]["blocked_reason"]
        assert saved["hard_budget_ledger"]["calls"] == []
        # The mismatch is durable and remains closed on subsequent resumes.
        try:
            await research_sessions.control_session(str(path), started["id"], "resume")
        except ProjectError as exc:
            assert "no matching billing reservation" in str(exc)
        else:
            raise AssertionError("A second Resume cleared missing billing liability")
        assert research_sessions._read(str(path), started["id"]) == saved


async def test_restart_matching_provider_reservation_is_recoverable(path: Path) -> None:
    """A real saved reservation retains liability and permits explicit recovery."""
    view, strategy, credential, config = await setup(path)
    with (
        patch.object(research_sessions, "auth_context", new=AsyncMock(return_value=credential)),
        patch.object(research_sessions, "configuration", new=AsyncMock(return_value=config)),
        patch.object(research_sessions, "_worker", new=AsyncMock()),
    ):
        started = await research_sessions.start_session(
            str(path), strategy.id, str(uuid4()), view.project.id, credential["identity"]
        )
        await asyncio.sleep(0)
        record = research_sessions._read(str(path), started["id"])
        dispatched_id = str(uuid4())
        ledger = new_ledger(
            call_limit=2,
            input_token_limit=400_000,
            output_tokens_per_call=4_000,
            cost_limit_usd=100.0,
            input_price_per_million=1.0,
            output_price_per_million=2.0,
        )
        reserve_before_dispatch(
            ledger, call_id=dispatched_id, request_body=b"preserved provider input"
        )
        record.update(
            {
                "status": "running",
                "calls_used": 1,
                "cycle_limit": 1,
                "call_limit": 2,
                "steps": [
                    {
                        "id": dispatched_id,
                        "strategy_id": strategy.id,
                        "role": "investigator",
                        "cycle": 1,
                        "status": "running",
                        "attempt_status": "unknown",
                        "cost_reserve": 0.2,
                    }
                ],
                "hard_budget_ledger": ledger,
            }
        )
        record["strategy_runs"][0].update({"status": "running", "cycle": 1, "calls_used": 1})
        research_sessions._save(str(path), record)
        research_sessions._tasks.pop(started["id"], None)
        research_sessions._control.pop(started["id"], None)
        interrupted = research_sessions._recover(research_sessions._read(str(path), started["id"]))
        assert interrupted["status"] == "paused"
        assert interrupted["steps"][0]["status"] == "interrupted"
        assert interrupted["hard_budget_ledger"]["calls"][0]["status"] == "unknown"
        assert (
            interrupted["hard_budget_ledger"]["blocked_reason"]
            == "Provider call outcome or usage is unknown"
        )
        resumed = await research_sessions.control_session(
            str(path), started["id"], "repair", additional_calls=1
        )
        assert resumed["status"] == "queued"
        saved = research_sessions._read(str(path), started["id"])
        assert saved["hard_budget_ledger"]["calls"][0]["status"] == "unknown"
        assert saved["hard_budget_ledger"]["blocked_reason"] is None
        assert saved["steps"][0]["id"] == dispatched_id


async def test_explicit_budget_and_duration_consent_preserves_saved_state(path: Path) -> None:
    """Ordinary Resume cannot silently extend attempts or expired runtime."""
    view, strategy, credential, config = await setup(path)
    with (
        patch.object(research_sessions, "auth_context", new=AsyncMock(return_value=credential)),
        patch.object(research_sessions, "configuration", new=AsyncMock(return_value=config)),
        patch.object(research_sessions, "_worker", new=AsyncMock()),
    ):
        started = await research_sessions.start_session(
            str(path), strategy.id, str(uuid4()), view.project.id, credential["identity"]
        )
        await asyncio.sleep(0)
        record = research_sessions._read(str(path), started["id"])
        record["cycle_limit"] = 1
        record["call_limit"] = 2
        record["calls_used"] = 2
        record["status"] = "failed"
        record["deadline_at"] = (datetime.now(UTC) - timedelta(minutes=5)).isoformat()
        record["steps"] = [
            {
                "id": str(uuid4()),
                "strategy_id": strategy.id,
                "role": "investigator",
                "cycle": 1,
                "status": "failed",
                "failure_kind": "response_invalid",
                "provider_input_audit": {"status": "provider_response_invalid"},
            }
        ]
        record["strategy_runs"][0].update(
            {"status": "failed", "cycle": 1, "pending_investigation": None}
        )
        research_sessions._save(str(path), record)
        original = research_sessions._read(str(path), started["id"])
        try:
            await research_sessions.control_session(str(path), started["id"], "resume")
        except ProjectError as exc:
            assert "exactly 2 explicitly authorized additional attempts" in str(exc)
        else:
            raise AssertionError("Ordinary Resume increased its saved call ceiling")
        assert research_sessions._read(str(path), started["id"]) == original
        try:
            await research_sessions.control_session(
                str(path), started["id"], "resume", additional_calls=2
            )
        except ProjectError as exc:
            assert "for up to 60 additional minutes" in str(exc)
            assert "2220" not in str(exc)
        else:
            raise AssertionError("Extra-call consent silently extended session duration")
        assert research_sessions._read(str(path), started["id"]) == original
        resumed = await research_sessions.control_session(
            str(path), started["id"], "repair", additional_calls=2
        )
        assert resumed["status"] == "queued"
        final = research_sessions._read(str(path), started["id"])
        assert final["call_limit"] == 4
        assert final["total_token_limit"] == original["total_token_limit"]
        assert final["steps"] == original["steps"]
        assert final["protocol_completion_time_extensions"][-1]["additional_minutes"] > 0


async def test_resume_37_pending_turns_uses_actual_remaining_session_time(path: Path) -> None:
    """Sovereign 17/54: rejected call requires consent, not 37 hours upfront."""
    view, strategy, credential, config = await setup(path)
    with (
        patch.object(research_sessions, "auth_context", new=AsyncMock(return_value=credential)),
        patch.object(research_sessions, "configuration", new=AsyncMock(return_value=config)),
        patch.object(research_sessions, "_worker", new=AsyncMock()),
    ):
        started = await research_sessions.start_session(
            str(path), strategy.id, str(uuid4()), view.project.id, credential["identity"]
        )
        await asyncio.sleep(0)
        record = research_sessions._read(str(path), started["id"])
        base_branch = record["strategy_runs"][0]
        strategy_ids = [strategy.id, str(uuid4()), str(uuid4())]
        branches: list[dict[str, Any]] = []
        steps: list[dict[str, Any]] = []
        for index, strategy_id in enumerate(strategy_ids):
            branch = deepcopy(base_branch)
            branch.update(
                {
                    "strategy_id": strategy_id,
                    "strategy_title": f"Saved strategy {index + 1}",
                    "status": "paused",
                    "cycle": 3,
                    "calls_used": 6,
                    "pending_investigation": (
                        {"claim": "Saved third-round Investigator output."} if index == 2 else None
                    ),
                }
            )
            branches.append(branch)
            for cycle in range(1, 4):
                for role in ("investigator", "skeptic"):
                    if index == 2 and cycle == 3 and role == "skeptic":
                        continue
                    steps.append(
                        {
                            "id": str(uuid4()),
                            "strategy_id": strategy_id,
                            "role": role,
                            "cycle": cycle,
                            "status": "completed",
                        }
                    )
        rejected_id = str(uuid4())
        steps.append(
            {
                "id": rejected_id,
                "strategy_id": strategy_ids[2],
                "role": "skeptic",
                "cycle": 3,
                "status": "failed",
                "failure_kind": "provider_limited",
                "provider_input_audit": {"status": "provider_response_rejected"},
            }
        )
        assert len(steps) == 18
        assert sum(step["status"] == "completed" for step in steps) == 17
        record.update(
            {
                "strategy_ids": strategy_ids,
                "strategy_runs": branches,
                "steps": steps,
                "status": "paused",
                "provider_usage_limited": True,
                "stopped_at": research_sessions._now(),
                "cycle_limit": 9,
                "call_limit": 54,
                "calls_used": 18,
                "deadline_at": (datetime.now(UTC) + timedelta(minutes=15)).isoformat(),
                "configured_duration_limit_minutes": 60,
                "duration_limit_minutes": 60,
                "hard_budget_ledger": None,
            }
        )
        saved_steps = deepcopy(steps)
        plan, plan_error = research_sessions._provider_limit_safe_plan(record)
        assert plan_error is None and plan is not None, plan_error
        assert plan["completed_turns"] == 17
        assert plan["required_calls"] == 37
        research_sessions._save(str(path), record)
        original = research_sessions._read(str(path), started["id"])
        try:
            await research_sessions.control_session(str(path), started["id"], "resume")
        except ProjectError as exc:
            assert "37 new valid role turns" in str(exc)
            assert "36 attempts remain" in str(exc)
            assert "exactly 1 explicitly authorized additional attempts" in str(exc)
        else:
            raise AssertionError("Resume silently increased the paid-attempt ceiling")
        assert research_sessions._read(str(path), started["id"]) == original
        resumed = await research_sessions.control_session(
            str(path), started["id"], "resume", additional_calls=1
        )
        assert resumed["status"] == "queued"
        final = research_sessions._read(str(path), started["id"])
        assert final["call_limit"] == 55
        assert final["calls_used"] == 18
        assert final["steps"] == saved_steps
        assert final["steps"][-1]["id"] == rejected_id
        assert final.get("protocol_completion_time_extensions", []) == []
        assert datetime.fromisoformat(final["deadline_at"]) < datetime.now(UTC) + timedelta(
            minutes=20
        )


async def test_terminal_time_expiry_requires_separate_confirmation(path: Path) -> None:
    """An unfinished but time-expired session is resumable only after consent."""
    view, strategy, credential, config = await setup(path)
    with (
        patch.object(research_sessions, "auth_context", new=AsyncMock(return_value=credential)),
        patch.object(research_sessions, "configuration", new=AsyncMock(return_value=config)),
        patch.object(research_sessions, "_worker", new=AsyncMock()),
    ):
        started = await research_sessions.start_session(
            str(path), strategy.id, str(uuid4()), view.project.id, credential["identity"]
        )
        await asyncio.sleep(0)
        record = research_sessions._read(str(path), started["id"])
        record.update(
            {
                "status": "ended",
                "cycle_limit": 1,
                "call_limit": 2,
                "calls_used": 0,
                "deadline_at": (datetime.now(UTC) - timedelta(minutes=5)).isoformat(),
                "duration_limit_minutes": 60,
            }
        )
        record["strategy_runs"][0].update(
            {"status": "ended", "cycle": 0, "pending_investigation": None}
        )
        research_sessions._save(str(path), record)
        original = research_sessions._read(str(path), started["id"])
        try:
            await research_sessions.control_session(str(path), started["id"], "resume")
        except ProjectError as exc:
            assert "requires explicit approval to extend" in str(exc)
        else:
            raise AssertionError("Ordinary Resume silently extended an expired deadline")
        assert research_sessions._read(str(path), started["id"]) == original
        resumed = await research_sessions.control_session(str(path), started["id"], "repair")
        assert resumed["status"] == "queued"
        final = research_sessions._read(str(path), started["id"])
        assert final["call_limit"] == original["call_limit"]
        assert final["duration_limit_minutes"] > original["duration_limit_minutes"]
        assert final["steps"] == original["steps"]


async def test_legacy_compiler_checkpoint_resumes_after_account_change(path: Path) -> None:
    """ONP-era sessions keep their checkpoint when the account or backend changes."""
    view, strategy, credential, config = await setup(path)
    current_account = {"value": credential}

    async def connected_account():
        return current_account["value"]

    async def idle_worker(*_args):
        return None

    with (
        patch.object(research_sessions, "auth_context", new=connected_account),
        patch.object(research_sessions, "configuration", new=AsyncMock(return_value=config)),
        patch.object(
            research_sessions, "_frozen_session_configuration", new=AsyncMock(return_value=config)
        ),
        patch.object(research_sessions, "_worker", new=idle_worker),
    ):
        started = await research_sessions.start_session(
            str(path), strategy.id, str(uuid4()), view.project.id, credential["identity"]
        )
        await asyncio.sleep(0)
        saved = research_sessions._read(str(path), started["id"])
        saved.pop("reference_compilation", None)
        saved["status"] = "paused"
        saved["stopped_at"] = datetime.now(UTC).isoformat()
        saved["preserved_legacy_note"] = "Earlier paid research remains unchanged."
        for branch in saved["strategy_runs"]:
            branch["status"] = "paused"
        research_sessions._save(str(path), saved)
        current_account["value"] = {
            **credential,
            "identity": "a-new-chatgpt-account",
            "token": "a-new-chatgpt-token",
        }
        resumed = await research_sessions.control_session(str(path), started["id"], "resume")
        assert resumed["status"] == "queued"
        assert resumed["preserved_legacy_note"] == "Earlier paid research remains unchanged."
        assert await research_sessions._ensure_reference_compilation(started["id"], str(path))
        persisted = research_sessions._read(str(path), started["id"])
        assert persisted["reference_compilation"]["status"] == "not_needed"
        assert persisted["reference_compilation"]["required_for_acceptance"] is False
        assert persisted["identity_hash"] == research_sessions._digest(credential["identity"])
        assert persisted["preserved_legacy_note"] == saved["preserved_legacy_note"]


async def test_resume_repeated_unknown_provider_failures_retains_session(path: Path) -> None:
    """Each Resume is new paid work, never a replay or loss of saved research."""
    view, strategy, credential, config = await setup(path)

    async def idle_worker(*_args):
        return None

    with (
        patch.object(research_sessions, "auth_context", new=AsyncMock(return_value=credential)),
        patch.object(research_sessions, "configuration", new=AsyncMock(return_value=config)),
        patch.object(
            research_sessions, "_frozen_session_configuration", new=AsyncMock(return_value=config)
        ),
        patch.object(research_sessions, "_worker", new=idle_worker),
    ):
        started = await research_sessions.start_session(
            str(path), strategy.id, str(uuid4()), view.project.id, credential["identity"]
        )
        await asyncio.sleep(0)
        record = research_sessions._read(str(path), started["id"])
        record["cycle_limit"] = 1
        record["call_limit"] = 2
        record["calls_used"] = 0
        ledger = new_ledger(
            call_limit=2,
            input_token_limit=400_000,
            output_tokens_per_call=4_000,
            cost_limit_usd=100.0,
            input_price_per_million=1.0,
            output_price_per_million=2.0,
        )
        for index in range(2):
            unknown_id = str(uuid4())
            reserve_before_dispatch(
                ledger, call_id=unknown_id, request_body=b"unknown provider request"
            )
            mark_unknown(ledger, call_id=unknown_id)
            record["steps"].append(
                {
                    "id": unknown_id,
                    "strategy_id": strategy.id,
                    "role": "investigator",
                    "cycle": 1,
                    "status": "failed",
                    "failure_kind": "provider_error",
                    "attempt_status": "unknown",
                    "provider_input_audit": {"status": "call_failed_dispatch_unknown"},
                }
            )
            record["status"] = "failed"
            record["strategy_runs"][0].update(
                {"status": "failed", "cycle": 1, "pending_investigation": None}
            )
            record["calls_used"] += 1
            record["strategy_runs"][0]["calls_used"] = record["calls_used"]
            record["hard_budget_ledger"] = ledger
            record["stopped_at"] = datetime.now(UTC).isoformat()
            research_sessions._save(str(path), record)

            try:
                await research_sessions.control_session(str(path), started["id"], "resume")
            except ProjectError as exc:
                assert "exactly 1 explicitly authorized additional attempts" in str(exc)
            else:
                raise AssertionError("Resume increased the paid-attempt ceiling silently")
            resumed = await research_sessions.control_session(
                str(path), started["id"], "repair", additional_calls=1
            )
            assert resumed["status"] == "queued"
            assert resumed["calls_used"] == index + 1
            assert resumed["call_limit"] == 3 + index
            persisted = research_sessions._read(str(path), started["id"])
            assert len(persisted["steps"]) == index + 1
            assert persisted["hard_budget_ledger"]["blocked_reason"] is None
            assert all(
                item["status"] == "unknown" for item in persisted["hard_budget_ledger"]["calls"]
            )
            # The next synthetic provider failure begins from the saved checkpoint.
            record = persisted
            ledger = persisted["hard_budget_ledger"]


async def test_e009_stopped_unknown_investigator_explicit_repair(path: Path) -> None:
    """Ordinary Resume authorizes new work and retains unknown provider liability."""
    view, strategy, credential, config = await setup(path)

    async def idle_worker(*_args):
        return None

    with (
        patch.object(research_sessions, "auth_context", new=AsyncMock(return_value=credential)),
        patch.object(research_sessions, "configuration", new=AsyncMock(return_value=config)),
        patch.object(
            research_sessions, "_frozen_session_configuration", new=AsyncMock(return_value=config)
        ),
        patch.object(research_sessions, "_worker", new=idle_worker),
    ):
        started = await research_sessions.start_session(
            str(path), strategy.id, str(uuid4()), view.project.id, credential["identity"]
        )
        await asyncio.sleep(0)
        record = research_sessions._read(str(path), started["id"])
        branch = record["strategy_runs"][0]
        unknown_id = str(uuid4())
        record.update(
            {
                "status": "stopped",
                "stopped_at": datetime.now(UTC).isoformat(),
                "cycle_limit": 3,
                "call_limit": 7,
                "calls_used": 1,
                "deadline_at": (datetime.now(UTC) - timedelta(minutes=2)).isoformat(),
                "duration_limit_minutes": 60,
                "steps": [
                    {
                        "id": unknown_id,
                        "strategy_id": strategy.id,
                        "role": "investigator",
                        "cycle": 1,
                        "status": "interrupted",
                        "failure_kind": "interrupted",
                        "attempt_status": "unknown",
                        "provider_input_audit": {"status": "call_interrupted_dispatch_unknown"},
                    }
                ],
            }
        )
        branch.update(
            {
                "status": "stopped",
                "cycle": 1,
                "calls_used": 1,
                "pending_investigation": None,
            }
        )
        ledger = new_ledger(
            call_limit=7,
            input_token_limit=400_000,
            output_tokens_per_call=4_000,
            cost_limit_usd=100.0,
            input_price_per_million=1.0,
            output_price_per_million=2.0,
        )
        reserve_before_dispatch(ledger, call_id=unknown_id, request_body=b"unknown investigator")
        mark_unknown(ledger, call_id=unknown_id)
        record["hard_budget_ledger"] = ledger
        research_sessions._save(str(path), record)

        # The play button can request recovery, but extending the time ceiling
        # needs a separate explicit confirmation before any new paid request.
        original = research_sessions._read(str(path), started["id"])
        try:
            await research_sessions.control_session(str(path), started["id"], "resume")
        except ProjectError as exc:
            assert "requires explicit approval to extend" in str(exc)
        else:
            raise AssertionError("Ordinary Resume silently extended the duration")
        assert research_sessions._read(str(path), started["id"]) == original
        repaired = await research_sessions.control_session(str(path), started["id"], "repair")
        assert repaired["status"] == "queued"
        assert repaired["calls_used"] == 1
        assert repaired["call_limit"] == 7
        saved = research_sessions._read(str(path), started["id"])
        assert len(saved["steps"]) == 1
        assert saved["steps"][0]["status"] == "interrupted"
        assert saved["hard_budget_ledger"]["calls"][0]["status"] == "unknown"
        assert saved["hard_budget_ledger"]["blocked_reason"] is None
        assert saved["strategy_runs"][0]["protocol_completion_recovery"]["role"] == "investigator"
        assert saved["strategy_runs"][0]["protocol_completion_recovery"]["new_request"] is True
        assert saved["protocol_completion_time_extensions"][-1]["remaining_protocol_calls"] == 6


async def test_terminal_protocol_resume_extends_only_exact_shortfall(
    path: Path, *, unknown_skeptic: bool = False
) -> None:
    view, strategy, credential, config = await setup(path)

    async def idle_worker(*_args):
        return None

    with (
        patch.object(research_sessions, "auth_context", new=AsyncMock(return_value=credential)),
        patch.object(research_sessions, "configuration", new=AsyncMock(return_value=config)),
        patch.object(
            research_sessions, "_frozen_session_configuration", new=AsyncMock(return_value=config)
        ),
        patch.object(research_sessions, "_worker", new=idle_worker),
    ):
        started = await research_sessions.start_session(
            str(path), strategy.id, str(uuid4()), view.project.id, credential["identity"]
        )
        await asyncio.sleep(0)
        record = research_sessions._read(str(path), started["id"])
        branch = record["strategy_runs"][0]
        record["cycle_limit"] = 3
        record["call_limit"] = 3
        record["calls_used"] = 2
        record["deadline_at"] = (datetime.now(UTC) - timedelta(minutes=5)).isoformat()
        record["duration_limit_minutes"] = 60
        record["status"] = "failed"
        record["current_action"] = "Failed"
        accepted_id = str(uuid4())
        invalid_id = str(uuid4())
        record["steps"] = [
            {
                "id": accepted_id,
                "strategy_id": strategy.id,
                "role": "investigator",
                "cycle": 1,
                "status": "completed",
            },
            {
                "id": invalid_id,
                "strategy_id": strategy.id,
                "role": "skeptic",
                "cycle": 1,
                "status": "interrupted" if unknown_skeptic else "failed",
                "failure_kind": "interrupted" if unknown_skeptic else "response_invalid",
                "provider_input_audit": {
                    "status": (
                        "call_interrupted_dispatch_unknown"
                        if unknown_skeptic
                        else "provider_response_invalid"
                    )
                },
            },
        ]
        if unknown_skeptic:
            ledger = new_ledger(
                call_limit=3,
                input_token_limit=400_000,
                output_tokens_per_call=4000,
                cost_limit_usd=100.0,
                input_price_per_million=1.0,
                output_price_per_million=2.0,
            )
            reserve_before_dispatch(ledger, call_id=accepted_id, request_body=b"investigator")
            settle_after_response(ledger, call_id=accepted_id, input_tokens=500, output_tokens=300)
            reserve_before_dispatch(ledger, call_id=invalid_id, request_body=b"skeptic")
            mark_unknown(ledger, call_id=invalid_id)
            record["hard_budget_ledger"] = ledger
        record["call_limit"] = 3
        branch.update(
            {
                "status": "failed",
                "current_action": "Failed",
                "cycle": 1,
                "calls_used": 2,
                "pending_investigation": {
                    "claim": "Saved Investigator result for round one.",
                    "reasoning_steps": [],
                },
            }
        )
        research_sessions._save(str(path), record)
        original = research_sessions._read(str(path), started["id"])
        try:
            await research_sessions.control_session(
                str(path), started["id"], "resume", additional_calls=3
            )
        except ProjectError as exc:
            assert "exactly 4" in str(exc)
        else:
            raise AssertionError("Protocol recovery silently exceeded its saved call ceiling")
        assert research_sessions._read(str(path), started["id"]) == original

        # A cross-process worker may still own its execution fence even though
        # its saved session appears terminal: do not change any recovery state.
        with patch.object(
            research_sessions,
            "_idle_worker_lock",
            side_effect=ProjectError("Session execution is still releasing resources"),
        ):
            try:
                await research_sessions.control_session(
                    str(path), started["id"], "repair", additional_calls=4
                )
            except ProjectError as exc:
                assert "releasing resources" in str(exc)
            else:
                raise AssertionError("Recovery mutated a session while its worker was active")
        assert research_sessions._read(str(path), started["id"]) == original

        # Two concurrent authorized resumes cannot apply the same budget
        # extension twice or create duplicate session transitions.
        saved_plan = research_sessions._protocol_completion_recovery_plan

        def plan_under_lock(saved_record):
            assert research_sessions._session_state_lock(started["id"]).locked()
            return saved_plan(saved_record)

        with patch.object(
            research_sessions, "_protocol_completion_recovery_plan", new=plan_under_lock
        ):
            results = await asyncio.gather(
                research_sessions.control_session(
                    str(path), started["id"], "repair", additional_calls=4
                ),
                research_sessions.control_session(
                    str(path), started["id"], "repair", additional_calls=4
                ),
                return_exceptions=True,
            )
        resumed = next((item for item in results if isinstance(item, dict)), None)
        assert resumed is not None
        assert resumed["status"] == "queued"
        final_record = research_sessions._read(str(path), started["id"])
        if unknown_skeptic:
            assert final_record["hard_budget_ledger"]["blocked_reason"] is None
            assert final_record["hard_budget_ledger"]["calls"][-1]["status"] == "unknown"
            assert (
                sum(
                    event.get("kind") == "session.unknown_review_budget_gate_reconciled"
                    for event in final_record.get("events", [])
                )
                == 1
            )
        if original.get("hard_budget_ledger"):
            before = original["hard_budget_ledger"]
            after = final_record["hard_budget_ledger"]
            assert after["call_limit"] == before["call_limit"] + 4
            assert after["input_token_limit"] == before["input_token_limit"]
            assert after["cost_limit_usd"] == before["cost_limit_usd"]
        assert len(final_record["call_limit_adjustments"]) == 1
        assert (
            sum(
                event.get("kind") == "session.protocol_call_limit_extended"
                for event in final_record.get("events", [])
            )
            == 1
        )
        assert resumed["calls_used"] == 2
        assert resumed["call_limit"] == 7
        assert research_sessions._read(str(path), started["id"])["steps"] == original["steps"]
        assert resumed["call_limit_adjustments"][-1]["from"] == 3
        assert resumed["call_limit_adjustments"][-1]["to"] == 7
        resumed_record = research_sessions._read(str(path), started["id"])
        time_extension = resumed_record["protocol_completion_time_extensions"][-1]
        assert time_extension["remaining_protocol_calls"] == 5
        assert time_extension["elapsed_session_clock_preserved"] is True
        assert time_extension["authorized_active_minutes"] == 60
        assert time_extension["additional_minutes"] == 60
        assert time_extension["expired_deadline_gap_seconds"] >= 0
        assert time_extension["additional_minutes"] < 5 * research_sessions.CALL_TIMEOUT // 60
        assert datetime.fromisoformat(resumed_record["deadline_at"]) > datetime.now(UTC)
        assert resumed_record["duration_limit_minutes"] > 60
        branch = resumed["strategy_runs"][0]
        assert branch["cycle"] == 1
        assert branch["protocol_completion_recovery"]["role"] == "skeptic"
        context = research_sessions._portfolio_context(
            research_sessions._read(str(path), started["id"]), branch, "skeptic", 1
        )
        payload = research_sessions._role_request_payload(
            research_sessions._read(str(path), started["id"]), "skeptic", context
        )
        assert "new request" in payload["instructions"]
        assert invalid_id in json.dumps(payload)


def test_protocol_recovery_context_is_a_new_final_provider_input() -> None:
    with TemporaryDirectory() as temporary:
        path = Path(temporary) / "protocol-recovery-context.sigma"
        view = initialize_project(path, "Protocol recovery audit", "Check saved proof.")
        strategy_id = str(uuid4())
        record = {
            "id": str(uuid4()),
            "project_path": view.path,
            "project_id": view.project.id,
            "project_title": view.project.title,
            "problem": view.project.problem,
            "model": MODEL,
            "reasoning_effort": "high",
            "mode": "chatgpt",
            "strategy_ids": [strategy_id],
            "strategy_id": strategy_id,
            "strategy_title": "Saved strategy",
            "strategy_text": "Audit the saved result.",
            "current_question": "Review the saved result.",
            "strategy_snapshot": [],
            "artifacts": [],
            "steps": [],
            "prior_session_findings": [],
            "prior_session_obligations": [],
            "pending_investigation": {"claim": "Saved accepted Investigator result."},
            "status": "running",
            "protocol_completion_recovery": {
                "role": "skeptic",
                "cycle": 3,
                "reason": "A prior Skeptic dispatch has uncertain completion; this is a new independent review.",
                "prior_attempt_ids": ["unknown-attempt"],
                "new_request": True,
            },
        }
        branch = {
            "strategy_id": strategy_id,
            "strategy_title": record["strategy_title"],
            "strategy_text": record["strategy_text"],
            "current_question": record["current_question"],
            "cycle": 3,
            "status": "running",
            "pending_investigation": record["pending_investigation"],
            "protocol_completion_recovery": record["protocol_completion_recovery"],
        }
        context = research_sessions._portfolio_context(record, branch, "skeptic", 3)
        payload = research_sessions._role_request_payload(record, "skeptic", context)
        serialized = json.dumps(payload)
        assert "protocol_completion_recovery" in serialized
        assert "uncertain completion" in serialized
        assert "not a replay" in research_sessions._role_instructions("skeptic", context)
        assert context["protocol_completion_recovery"]["prior_attempt_ids"] == ["unknown-attempt"]


def test_context_compaction_preserves_obligation_count_for_portfolio_dispatch():
    """Regression for Session #5: portfolio coordination must not KeyError."""
    from copy import deepcopy

    ledger = [
        {"obligation_id": "open-a", "status": "unresolved", "text": "First open question."},
        {"obligation_id": "closed-b", "status": "resolved", "text": "Previously resolved."},
        {"obligation_id": "open-c", "status": "unresolved", "text": "Second open question."},
    ]
    original_ledger = deepcopy(ledger)
    context = {
        "problem": "Test context growth without losing active research.",
        "obligation_ledger": ledger,
        "outstanding_obligations": ["Large duplicated text " * 900, "Another open obligation"],
        "context_manifest": {"sources": []},
    }
    assert research_sessions._json_bytes(context) > 2048
    assert research_sessions.compact_dispatch_context(context, limit=2048)
    assert "outstanding_obligations" not in context
    assert context["context_manifest"]["outstanding_obligations_location"] == "obligation_ledger"
    assert research_sessions._context_obligation_count(context) == 2
    assert context["obligation_ledger"] == original_ledger

    # Older saved dispatch records may have only the legacy flat list.
    assert (
        research_sessions._context_obligation_count(
            {"outstanding_obligations": ["first", "second"]}
        )
        == 2
    )
    assert (
        research_sessions._context_obligation_count(
            {"outstanding_obligations": ["stale"], "obligation_ledger": []}
        )
        == 0
    )
    assert research_sessions._context_obligation_count({}) == 0


def test_dispatch_budget_compacts_historical_evidence_not_live_inputs():
    """Long runs preserve provenance while dropping redundant prompt bytes."""
    from copy import deepcopy

    original_evidence = [
        {
            "id": f"saved-{index}",
            "strategy_id": "strategy-a",
            "method": f"Older saved argument {index}. " + ("x" * 18000),
            "evidence_status": "Unverified",
        }
        for index in range(18)
    ]
    context = {
        "problem": "Investigate whether this agent architecture is reliable.",
        "strategy": {"id": "strategy-a", "approach": "Test competing hypotheses."},
        "question": "Continue the next research turn.",
        "prior_artifacts": deepcopy(original_evidence),
        "obligation_ledger": [
            {
                "obligation_id": "open-one",
                "text": "Check the counterexample before claiming a result.",
                "status": "unresolved",
                "source_artifact_ids": ["saved-1"],
                "supplied_source_artifact_ids": ["saved-1"],
                "source_artifact_availability": "adequate_bounded_extract_original_not_supplied",
            }
        ],
        "outstanding_obligations": ["Check the counterexample before claiming a result."],
        "context_manifest": {
            "sources": [
                {
                    "category": "current_session_material_evidence",
                    "source_ids": ["saved-0", "saved-17"],
                    "status": "selected",
                    "representation": "deterministic_extract",
                }
            ]
        },
    }
    assert research_sessions._json_bytes(context) > research_sessions.MAX_AGENT_CONTEXT_BYTES
    assert research_sessions.compact_dispatch_context(
        context, limit=research_sessions.MAX_AGENT_CONTEXT_BYTES
    )
    assert research_sessions._json_bytes(context) <= research_sessions.MAX_AGENT_CONTEXT_BYTES
    assert context["problem"] == "Investigate whether this agent architecture is reliable."
    assert context["question"] == "Continue the next research turn."
    assert context["obligation_ledger"][0]["status"] == "unresolved"
    assert context["obligation_ledger"][0]["text"] == (
        "Check the counterexample before claiming a result."
    )
    assert context["obligation_ledger"][0]["source_artifact_availability"] == (
        "incomplete_extract_original_not_supplied"
    )
    assert context["prior_artifacts"][0]["id"] == "saved-0"
    assert context["prior_artifacts"][0]["method"] == original_evidence[0]["method"]
    assert context["prior_artifacts"][1]["evidence_availability"] == (
        "pointer_only_original_not_supplied"
    )
    assert original_evidence[0]["method"].endswith("x" * 18000)
    assert (
        context["context_manifest"]["dispatch_budget_compaction"]["counts"]["prior_artifacts"] > 0
    )

    # Do not truncate the active problem and pretend a request can continue.
    huge_question = {
        "problem": "p" * (research_sessions.MAX_AGENT_CONTEXT_BYTES + 1),
        "context_manifest": {"sources": []},
        "prior_artifacts": [],
    }
    assert not research_sessions.compact_dispatch_context(
        huge_question, limit=research_sessions.MAX_AGENT_CONTEXT_BYTES
    )
    assert len(huge_question["problem"]) == research_sessions.MAX_AGENT_CONTEXT_BYTES + 1

    # One valid Investigator may contain 24 reasoning steps with 12 KB each:
    # a Skeptic must still receive an honestly incomplete bounded extract,
    # and the exact full Investigator response must remain untouched.
    oversized_investigator = {
        "claim": "A provisional local result, not a proof.",
        "method": "Method detail " * 400,
        "reasoning_steps": [
            {
                "title": f"Step {i}",
                "argument": "Reasoning detail " * 650,
                "epistemic_status": "deduction",
                "basis_artifact_ids": [],
            }
            for i in range(24)
        ],
        "open_obligations": ["Resolve the remaining counterexample"],
        "evidence_status": "Unverified model reasoning.",
    }
    saved_investigator = deepcopy(oversized_investigator)
    skeptic_context = {
        "problem": "Evaluate the provisional result without inventing proof.",
        "investigator_output": oversized_investigator.copy(),
        "investigator_step_id": "saved-investigator-step",
        "context_manifest": {"sources": []},
    }
    assert (
        research_sessions._json_bytes(skeptic_context) > research_sessions.MAX_AGENT_CONTEXT_BYTES
    )
    assert research_sessions.compact_dispatch_context(
        skeptic_context, limit=research_sessions.MAX_AGENT_CONTEXT_BYTES
    )
    assert (
        research_sessions._json_bytes(skeptic_context) <= research_sessions.MAX_AGENT_CONTEXT_BYTES
    )
    assert skeptic_context["investigator_output_extract_complete"] is False
    excerpt = skeptic_context["investigator_output"]
    assert excerpt["extract_complete"] is False
    assert excerpt["evidence_availability"] == "incomplete_extract_original_not_supplied"
    assert excerpt["reasoning_steps_total"] == 24
    assert excerpt["reasoning_steps_omitted"] == 20
    assert excerpt["reasoning_step_original_positions_supplied"] == [1, 8, 16, 24]
    assert excerpt["reasoning_step_original_positions_omitted"] == [
        index for index in range(1, 25) if index not in {1, 8, 16, 24}
    ]
    assert [item["title"] for item in excerpt["reasoning_steps"]] == [
        "Step 0",
        "Step 7",
        "Step 15",
        "Step 23",
    ]
    assert "reasoning_steps" in excerpt["extract_truncated_fields"]
    assert skeptic_context["context_manifest"]["inflight_investigator_extract"][
        "source_step_id"
    ] == ("saved-investigator-step")
    assert oversized_investigator == saved_investigator


def test_portfolio_round_ceiling_not_mislabeled_as_funding_shortage():
    """Unused turns after individual strategy limits do not mean no funding."""
    record = {"calls_used": 14, "call_limit": 18, "cycle": 3, "cycle_limit": 3}
    runs = [
        {
            "status": "ended",
            "strategy_title": "First strategy",
            "last_decision": "stop_decisive_counterexample",
            "cycle": 1,
            "artifacts": ["a1"],
        },
        {
            "status": "ended",
            "strategy_title": "Second strategy",
            "last_decision": "stop_budget_exhausted",
            "cycle": 3,
            "artifacts": ["a2", "a3", "a4"],
        },
        {
            "status": "ended",
            "strategy_title": "Third strategy",
            "last_decision": "stop_budget_exhausted",
            "cycle": 3,
            "artifacts": ["a5", "a6", "a7"],
        },
    ]
    code, message = research_sessions._portfolio_termination(record, runs)
    assert code == "round_limit_reached"
    assert "per-strategy round limit" in message
    assert "fund another" not in message
    assert "funding shortage" in message


async def test_eighteen_turns_survive_project_edits_and_bounded_context(path: Path):
    """Three strategies and three rounds continue despite live UI-style edits."""
    view, first, credential, config = await setup(path)
    next_view = create_strategy(path, "Independent second approach", "Check a second route.")
    second = next(row for row in next_view.project.strategies if row.id != first.id)
    third_view = create_strategy(path, "Independent third approach", "Check a third route.")
    third = next(
        row for row in third_view.project.strategies if row.id not in {first.id, second.id}
    )
    limits = dict(research_sessions.DEFAULT_LIMITS)
    limits.update({"research_rounds": 3, "model_calls": 18})
    limits = research_sessions.save_limits(str(path), limits)
    entered = asyncio.Event()
    release = asyncio.Event()
    submitted = []

    async def handler(request):
        payload = json.loads(request.content)
        context = json.loads(payload["input"])
        role = payload["text"]["format"]["name"]
        submitted.append((context["strategy"]["id"], role, context["cycle"]))
        if len(submitted) == 1:
            entered.set()
            await release.wait()
        if role == "research_investigator":
            output = investigation(context["cycle"])
            output["method"] += " Saved investigation detail." * 160
        else:
            # Live Session #6: a provisional counterexample ended branch one
            # after round one, leaving four turns unused in a 3x3 portfolio.
            output = (
                skeptic(context["cycle"], "stop", "decisive_counterexample")
                if context["strategy"]["id"] == first.id and context["cycle"] == 1
                else skeptic(context["cycle"])
            )
            output["response"] += " Bounded critical review." * 45
        return httpx.Response(200, json=provider_response(output))

    with (
        patch.object(research_sessions, "MAX_AGENT_CONTEXT_BYTES", 45_000),
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
        await asyncio.wait_for(entered.wait(), 2)
        edit_strategy(str(path), first.id, first.title, first.approach + " Edited while playing.")
        set_strategy_enabled(str(path), second.id, False)
        current = inspect_project(path).project
        update_project(
            str(path),
            current.title,
            current.problem + " (edited while playing)",
            getattr(current.investigation_type, "value", current.investigation_type),
            current.ai_model,
            current.reasoning_effort,
            {
                "title": current.title,
                "problem": current.problem,
                "investigation_type": getattr(
                    current.investigation_type, "value", current.investigation_type
                ),
                "ai_model": current.ai_model,
                "reasoning_effort": current.reasoning_effort,
                "difficulty": current.difficulty.value if current.difficulty else None,
                "show_advanced_outcome_details": False,
            },
            show_advanced_outcome_details=True,
        )
        release.set()
        finished = await wait_for(path, started["id"])
    assert finished["status"] in {"ended", "completed"}, finished["message"]
    assert finished["calls_used"] == 18, (finished["calls_used"], finished["message"])
    assert len(submitted) == 18
    assert len(finished["artifacts"]) == 9
    first_artifact = next(a for a in finished["artifacts"] if a["strategy_id"] == first.id)
    assert first_artifact["skeptic_output"]["stop_reason"] == "decisive_counterexample"
    assert first_artifact["coordinator_decision"] == "revise"
    assert any(
        event["kind"] == "coordinator.provisional_stop_reopened" for event in finished["events"]
    )
    assert len({strategy_id for strategy_id, _, _ in submitted}) == 3
    saved = research_sessions._read(str(path), started["id"])
    assert saved["problem"] == view.project.problem
    assert saved["strategy_runs"][0]["strategy_text"] == first.approach


def test_reference_compilation_is_bounded_and_source_attributed() -> None:
    import hashlib

    from sigma import research_reference_compiler as compiler

    sources = [
        {
            "id": "proof",
            "title": "Proof methods",
            "url": "https://example.org/proof",
            "notes": "Test induction, boundary cases, and counterexamples.",
        },
        {
            "id": "irrelevant",
            "title": "Unrelated",
            "url": "https://example.org/style",
            "notes": "Decorative formatting unrelated to the proof.",
        },
    ]
    initial = deepcopy(sources)
    session = {
        "model": MODEL,
        "mode": "api_key",
        "project_title": "A conjecture",
        "problem": "Prove a combinatorial recurrence",
        "investigation_type": "mathematical",
        "strategy_runs": [{"strategy_title": "Induction", "strategy_text": "Check base cases"}],
        "research_method_sources": {"sources": sources},
    }
    request = compiler.build_request(session)
    assert request["store"] is False
    assert request["text"]["format"]["strict"] is True
    assert request["max_output_tokens"] == compiler.OUTPUT_TOKEN_BOUND
    assert len(json.loads(request["input"])["uninspected_methodology_sources"]) == 2
    chat_request = compiler.build_request({**session, "mode": "chatgpt"})
    assert chat_request["stream"] is True and "max_output_tokens" not in chat_request

    response = {
        "guidance": " Verify base cases and counterexamples. ",
        "selected_source_ids": ["proof"],
        "omitted_source_ids": ["irrelevant"],
        "rationale": "The other reference is off topic.",
    }
    selected = compiler.validate_result(response, sources)
    assert selected["guidance"] == response["guidance"].strip()
    assert (
        selected["guidance_sha256"]
        == hashlib.sha256(selected["guidance"].encode("utf-8")).hexdigest()
    )
    assert sources == initial
    compilation_record = {
        **session,
        "reference_compilation": {
            **selected,
            "status": "completed",
            "source_sha256": "a" * 64,
        },
    }
    comparison = research_sessions._research_reference_compilation_efficiency(compilation_record)
    assert comparison is not None
    # A tiny source set can expand when compiled guidance gains provenance
    # fields. Report a signed difference rather than asserting all inputs shrink.
    assert comparison["estimated_tokens_avoided_per_use"] == (
        comparison["original_estimated_tokens"] - comparison["compiled_estimated_tokens"]
    )
    # Estimate is displayed separately from provider-metered usage.
    metric_rows = research_sessions._outcome_metrics(compilation_record, {})["operational"]
    reference_row = next(
        row for row in metric_rows if row["label"] == "Reference compilation · estimated tokens"
    )
    assert "before" in reference_row["value"] and "after" in reference_row["value"]
    assert "not measured provider usage" in reference_row["detail"]
    assert (
        research_sessions._research_reference_compilation_efficiency(
            {**compilation_record, "reference_compilation": {"status": "fallback"}}
        )
        is None
    )
    for invalid in (
        {**response, "selected_source_ids": ["invented"]},
        {**response, "omitted_source_ids": []},
        {**response, "selected_source_ids": ["proof", "proof"]},
    ):
        try:
            compiler.validate_result(invalid, sources)
        except ProjectError:
            pass
        else:
            raise AssertionError("Invalid reference compilation was accepted")

    # The model may exceed a presentation length despite valid, metered
    # structured output. Bound the usable guide without silently accepting
    # invalid source provenance or losing its original length.
    oversized = compiler.validate_result(
        {**response, "guidance": "Verify the evidence carefully. " * 70}, sources
    )
    assert oversized["guidance_compacted"] is True
    assert oversized["guidance_original_chars"] > compiler.MAX_GUIDANCE_CHARS
    assert 0 < len(oversized["guidance"]) <= compiler.MAX_GUIDANCE_CHARS
    assert oversized["guidance"].endswith("…")
    assert (
        oversized["guidance_sha256"]
        == hashlib.sha256(oversized["guidance"].encode("utf-8")).hexdigest()
    )
    assert compiler.validate_result(oversized, sources)["guidance"] == oversized["guidance"]

    context = {
        "problem": session["problem"],
        "investigation_type": "mathematical",
        "research_method_version": research_sessions.RESEARCH_METHOD_VERSION,
        "methodology_source_catalog_version": "methodology-catalog-v2",
        "methodology_source_material": [
            {"id": "compiled-methodology-guide", "notes": selected["guidance"]}
        ],
        "execution_tools": [],
    }
    role_settings = {
        "mode": "api_key",
        "model": MODEL,
        "reasoning_effort": "high",
        "output_token_limit": 4000,
    }
    for role in ("investigator", "skeptic"):
        prompt = json.dumps(research_sessions._role_request_payload(role_settings, role, context))
        assert selected["guidance"] in prompt
        assert "https://example.org/style" not in prompt


# Issue #506: provider-free paired-turn scheduling and historical isolation.
def test_paired_round_defaults_and_enabled_call_ceiling() -> None:
    limits = research_sessions._validate_limits(dict(research_sessions.NEW_DEFAULT_LIMITS))
    assert (limits["scheduler_version"], limits["research_rounds"], limits["turns_per_round"]) == (
        2,
        3,
        3,
    )
    assert limits["model_calls"] == 18
    assert [research_sessions._paired_call_limit(limits, count) for count in (0, 1, 2, 3)] == [
        0,
        18,
        36,
        54,
    ]
    assert research_sessions._paired_call_limit({**limits, "research_rounds": 2}, 2) == 24
    assert research_sessions._paired_call_limit({**limits, "turns_per_round": 4}, 2) == 48


def test_paired_round_positions_are_explicit_and_legacy_is_unchanged() -> None:
    paired = {"scheduler_version": 2, "turns_per_round": 3}
    assert [research_sessions._paired_round_position(paired, slot) for slot in range(1, 10)] == [
        (1, 1),
        (1, 2),
        (1, 3),
        (2, 1),
        (2, 2),
        (2, 3),
        (3, 1),
        (3, 2),
        (3, 3),
    ]
    assert research_sessions._paired_round_position({"cycle_limit": 3}, 2) == (2, 1)
    legacy = {"research_rounds": 2, "model_calls": 12}
    upgraded = research_sessions._new_session_limits(legacy)
    assert legacy == {"research_rounds": 2, "model_calls": 12}
    assert (upgraded["research_rounds"], upgraded["turns_per_round"], upgraded["model_calls"]) == (
        3,
        3,
        18,
    )


def test_paired_round_protocol_requires_every_accepted_role() -> None:
    steps = [
        {"strategy_id": sid, "role": role, "cycle": slot, "status": "completed"}
        for sid in ("a", "b", "c")
        for slot in range(1, 10)
        for role in ("investigator", "skeptic")
    ]
    record = {
        "status": "ended",
        "strategy_ids": ["a", "b", "c"],
        "cycle_limit": 9,
        "research_round_limit": 3,
        "turns_per_round": 3,
        "scheduler_version": 2,
        "steps": steps,
        "artifacts": [],
        "events": [],
    }
    assert research_sessions._mark_protocol_complete(record)
    assert record["termination_reason_code"] == "protocol_complete"
    assert "54 configured" in record["message"]
    missing = deepcopy(record)
    missing.pop("termination_reason_code")
    missing["steps"] = steps[:-1]
    assert not research_sessions._mark_protocol_complete(missing)
    assert missing.get("termination_reason_code") is None
    missing["steps"].append({"strategy_id": "c", "role": "skeptic", "cycle": 9, "status": "failed"})
    assert not research_sessions._mark_protocol_complete(missing)


def test_paired_round_pipeline_orders_roles_without_paid_calls() -> None:
    observed: list[tuple[str, int]] = []

    async def fake_call(
        session_id: str,
        path: str,
        strategy_id: str,
        role: str,
        cycle: int,
        semaphore: asyncio.Semaphore,
        state_lock: asyncio.Lock,
    ) -> bool:
        observed.append((role, cycle))
        return True

    async def run() -> None:
        branch: dict[str, Any] = {
            "strategy_id": "s",
            "cycle": 0,
            "pending_investigation": None,
        }
        semaphore = asyncio.Semaphore(2)
        lock = asyncio.Lock()
        with patch.object(research_sessions, "_portfolio_role_call_with_recovery", fake_call):
            for slot in range(1, 10):
                branch["cycle"] = slot - 1
                assert await research_sessions._portfolio_strategy_pipeline(
                    "session", "/unused", branch, semaphore, lock
                )
        assert observed == [
            (role, slot) for slot in range(1, 10) for role in ("investigator", "skeptic")
        ]

    asyncio.run(run())


def test_paired_round_scheduler_budget_rotates_and_keeps_partial_pairs() -> None:
    queued = [{"strategy_id": item, "pending_investigation": None} for item in ("a", "b", "c")]
    selected, cursor = research_sessions._affordable_portfolio_branches(queued, 6, 0)
    assert [item["strategy_id"] for item in selected] == ["a", "b", "c"]
    assert cursor == 0
    selected, cursor = research_sessions._affordable_portfolio_branches(queued, 2, 1)
    assert [item["strategy_id"] for item in selected] == ["b"]
    assert cursor == 2
    # An accepted Investigator that needs its Skeptic consumes only one new slot.
    queued[0]["pending_investigation"] = {"claim": "saved"}
    selected, _ = research_sessions._affordable_portfolio_branches(queued, 1, 0)
    assert [item["strategy_id"] for item in selected] == ["a"]
    assert research_sessions._affordable_portfolio_branches(queued[1:], 1, 0)[0] == []


if __name__ == "__main__":
    from research_sessions_split_runner import run

    run(4)
