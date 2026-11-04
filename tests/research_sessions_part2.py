# ruff: noqa: F401, F811
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


def test_t37_obligation_identity_lifecycle_and_history(path: Path):
    view = initialize_project(
        path, "Scoped obligation history", "Check an exact claim.", research_mode="mathematical"
    )
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
    context = research_sessions._agent_context(record, "investigator", 1)
    assert context["prior_artifacts"][0]["extract_truncated_fields"] == ["method"]
    assert context["prior_artifacts"][0]["evidence_availability"] == (
        "incomplete_extract_original_not_supplied"
    )
    assert context["obligation_ledger"][0]["source_artifact_availability"] == (
        "incomplete_extract_original_not_supplied"
    )
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
    # Many material sources no longer force an otherwise valid session to stop.
    # Selected sources are bounded; omitted originals remain saved and named.
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
    record = {
        "id": session_id,
        "project_path": view.path,
        "project_id": view.project.id,
        "strategy_id": strategy.id,
        "strategy_title": strategy.title,
        "strategy_text": strategy.approach,
        "problem": view.project.problem,
        "current_question": "Test one precise consequence.",
        "strategy_snapshot": [],
        "artifacts": artifacts,
    }
    context = research_sessions._agent_context(record, "investigator", 1)
    assert len(context["prior_artifacts"]) == research_sessions.MAX_CONTEXT_ARTIFACTS
    assert context["context_manifest"]["mandatory_source_omitted_count"] == 1
    assert artifacts[0]["id"] in context["context_manifest"]["mandatory_source_omitted_ids"]
    assert artifacts[0]["id"] not in context["context_artifact_ids"]
    assert artifacts[-1]["id"] in context["context_artifact_ids"]
    assert context["context_manifest"]["omitted_count"] == 1
    assert research_sessions._json_bytes(context) <= research_sessions.MAX_AGENT_CONTEXT_BYTES

    # A required obligation whose text extract is incomplete must remain
    # visibly incomplete rather than being sent as complete evidence.
    record["artifacts"] = [
        {
            "id": "long-open-obligation",
            "sequence": 1,
            "strategy_id": strategy.id,
            "open_obligations": ["Resolve " + "x" * 710],
            "method": "Saved complete source remains in the original artifact.",
        }
    ]
    truncated = research_sessions._agent_context(record, "investigator", 1)
    open_item = truncated["obligation_ledger"][0]
    assert open_item["status"] == "unresolved"
    assert open_item["text_complete"] is False
    assert truncated["incomplete_unresolved_obligation_count"] == 1
    assert truncated["context_manifest"]["incomplete_unresolved_obligations"]["count"] == 1

    # Older unresolved items may be excluded from one bounded provider packet,
    # but their IDs and unresolved status are not erased from saved artifacts.
    original_obligations = [
        f"Open problem {index}" for index in range(research_sessions.MAX_CONTEXT_OBLIGATIONS + 3)
    ]
    record["artifacts"] = [
        {
            "id": "many-open-obligations",
            "sequence": 1,
            "strategy_id": strategy.id,
            "open_obligations": original_obligations,
        }
    ]
    bounded = research_sessions._agent_context(record, "investigator", 1)
    assert len(bounded["obligation_ledger"]) == research_sessions.MAX_CONTEXT_OBLIGATIONS
    assert bounded["obligation_ledger_omitted_count"] == 3
    assert len(bounded["obligation_ledger_omitted_ids"]) == 3
    assert all(item["status"] == "unresolved" for item in bounded["obligation_ledger"])
    assert original_obligations[0] not in [item["text"] for item in bounded["obligation_ledger"]]
    assert original_obligations[-1] in [item["text"] for item in bounded["obligation_ledger"]]


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
        if progress.get("scheduler_version") == 2:
            assert "Investigator agent call 1/" in progress["message"]
        else:
            assert "Investigator agent turn 1/12 in progress" in progress["message"]
        await research_sessions.control_session(str(path), started["id"], "pause")
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


def test_protocol_completion_label_requires_every_configured_role_turn():
    strategy_ids = ["strategy-a", "strategy-b"]
    steps = [
        {
            "strategy_id": strategy_id,
            "role": role,
            "cycle": cycle,
            "status": "completed",
        }
        for strategy_id in strategy_ids
        for cycle in (1, 2, 3)
        for role in ("investigator", "skeptic")
    ]
    record = {
        "id": str(uuid4()),
        "status": "ended",
        "strategy_ids": strategy_ids,
        "cycle_limit": 3,
        "steps": steps,
        "artifacts": [{}, {}, {}],
        "events": [],
        "message": "The research is incomplete.",
        "current_action": "Ended · research incomplete",
    }
    assert research_sessions._mark_protocol_complete(record)
    assert record["status"] == "ended"
    assert record["termination_reason_code"] == "protocol_complete"
    assert record["current_action"] == "Completed · configured protocol"
    assert "All 12 configured" in record["message"]
    assert "unverified research notes" in record["message"]
    assert record["events"][-1]["kind"] == "session.protocol_complete"

    # Operation Narrow Passage: two strategies and two rounds produce
    # eight accepted role turns, even if twelve attempts are permitted.
    narrow = {
        **record,
        "id": str(uuid4()),
        "cycle_limit": 2,
        "call_limit": 12,
        "calls_used": 8,
        "steps": [step for step in steps if step["cycle"] <= 2],
        "events": [],
        "termination_reason_code": "round_limit_reached",
        "message": "The research is incomplete.",
        "current_action": "Ended · research incomplete",
    }
    assert research_sessions._mark_protocol_complete(narrow)
    assert narrow["status"] == "ended"
    assert narrow["termination_reason_code"] == "protocol_complete"
    assert narrow["current_action"] == "Completed · configured protocol"
    assert "All 8 configured" in narrow["message"]
    assert "incomplete" not in narrow["message"]
    assert len(narrow["steps"]) == 8

    incomplete = dict(record)
    incomplete["events"] = []
    incomplete["steps"] = steps[:-1]
    incomplete["termination_reason_code"] = "round_limit_reached"
    incomplete["current_action"] = "Ended · research incomplete"
    assert not research_sessions._mark_protocol_complete(incomplete)
    assert incomplete["current_action"] == "Ended · research incomplete"
    assert incomplete["termination_reason_code"] == "round_limit_reached"


def test_worker_cancel_before_dispatch_does_not_claim_provider_call():
    record = {"id": str(uuid4()), "status": "running", "steps": [], "events": []}
    research_sessions._record_worker_cancellation(record)
    assert record["status"] == "paused"
    assert record["current_action"] == "Paused before dispatch"
    assert "No provider request was dispatched" in record["message"]
    assert record["events"][-1]["kind"] == "paused_before_dispatch"
    assert record.get("calls_used", 0) == 0


def test_worker_cancel_with_running_call_preserves_dispatch_uncertainty():
    step = {
        "id": str(uuid4()),
        "role": "investigator",
        "status": "running",
        "provider_input_audit": {"status": "provider_request_dispatched"},
    }
    record = {
        "id": str(uuid4()),
        "status": "running",
        "steps": [step],
        "events": [],
        "strategy_runs": [],
    }
    research_sessions._record_worker_cancellation(record)
    assert record["current_action"] == "Paused after interrupted step"
    assert step["status"] == "interrupted"
    assert step["provider_input_audit"]["status"] == "call_interrupted_dispatch_unknown"
    assert record["events"][-1]["kind"] == "call.interrupted"


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
        *[httpx.ReadTimeout("") for _ in range(research_sessions.MAX_TRANSIENT_AUTO_RETRIES + 1)],
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
    assert research_sessions.CALL_TIMEOUT == 3600
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
    assert research_sessions.get_limits(str(path)) == research_sessions.NEW_DEFAULT_LIMITS
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
    # This historical two-call test is deliberately exercised with v1 limits.
    limits = {**research_sessions.DEFAULT_LIMITS, "research_rounds": 1, "model_calls": 2}
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
    initialize_project(path, "Limits project", "A question", research_mode="mathematical")
    # Retain the historical explicit-call-ceiling validation contract.
    research_sessions.save_limits(str(path), dict(research_sessions.DEFAULT_LIMITS))
    before = research_sessions.get_limits(str(path))
    invalid = [
        {**before, "model_calls": 1},
        {**before, "model_calls": 121},
        {**before, "research_rounds": 61, "model_calls": 30},
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
        "research_rounds": 60,
        "model_calls": 120,
        "session_duration_minutes": 7 * 24 * 60,
        "output_tokens_per_call": 20000,
        "maximum_estimated_cost_usd": 100,
    }
    assert research_sessions.save_limits(str(path), valid_upper) == valid_upper
    research_sessions.save_limits(str(path), before)
    assert research_sessions.get_limits(str(path)) == before
    older_saved = {**before, "research_rounds": 3, "model_calls": 1}
    limits_file = path / "research-sessions" / "limits.json"
    limits_file.write_text(json.dumps(older_saved), encoding="utf-8")
    assert research_sessions.get_limits(str(path)) == older_saved
    try:
        research_sessions.save_limits(str(path), older_saved)
    except ProjectError:
        pass
    else:
        raise AssertionError("new settings validation accepted a saved value above its bound")


def test_contradictory_skeptic_counterexample_does_not_cancel_continuation():
    assert research_sessions.coordinate_decision(
        "continue",
        "decisive_counterexample",
        "Proceed with a bounded next test",
        ["One gap remains"],
        1,
        9,
        2,
        54,
    ) == ("continue", "Proceed with a bounded next test")
    assert research_sessions.coordinate_decision(
        "stop",
        "decisive_counterexample",
        "",
        [],
        1,
        9,
        2,
        54,
    ) == ("stop_decisive_counterexample", "")


def test_coordinator_obligations_do_not_multiply_across_rounds():
    artifacts = []
    for cycle in range(1, 10):
        old = [f"Obligation {index}" for index in range(1, cycle)]
        current = f"Obligation {cycle}"
        artifacts.append(
            {
                "id": f"artifact-{cycle}",
                "project_id": "project",
                "strategy_id": "strategy",
                "assumptions": [f"Assumption {cycle}"],
                "investigator_output": {"open_obligations": [current]},
                "skeptic_output": {
                    "remaining_obligations": old + [current],
                    "model_remaining_obligations": [current],
                    "coordinator_added_obligations": old,
                },
                "open_obligations": old + [current],
            }
        )
        ledger, omitted, _ = research_sessions._obligation_ledger(
            artifacts,
            project_id="project",
            strategy_id="strategy",
        )
        assert len(ledger) == cycle, (cycle, len(ledger))
        assert omitted == 0
        assert {item["text"] for item in ledger} == set(old + [current])
    legacy, _, _ = research_sessions._obligation_ledger(
        [{"id": "legacy", "open_obligations": ["Legacy obligation"]}],
        project_id="project",
        strategy_id="strategy",
    )
    assert [item["text"] for item in legacy] == ["Legacy obligation"]


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
    limits = dict(research_sessions.DEFAULT_LIMITS)
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
        limits = dict(research_sessions.DEFAULT_LIMITS)
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
    assert no_next_path["assessment"] == "mixed" and "inconclusive" in no_next_path["label"]
    negative = research_sessions._outcome(
        {
            "status": "completed",
            "artifacts": [{**artifact, "coordinator_decision": "stop_decisive_counterexample"}],
        }
    )
    # A stop marker with no actual counterexample is not negative evidence.
    assert negative["assessment"] == "mixed"
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
    view = initialize_project(
        path, "Sequence metadata", "Keep session numbering separate.", research_mode="mathematical"
    )
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
        research_mode="mathematical",
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
    # Distinct wording alone is not a cited scientific contradiction;
    # the second unverified assertion does not erase a complete candidate.
    assert "### Complete reviewed candidate answer" in conflict["conclusion"]

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


def test_e1_peer_inspection_does_not_hide_complete_unverified_candidate():
    """Maximum Regions E1: no retroactive evidence mutation or paid requests."""
    from copy import deepcopy

    peer_note = "Inspect the saved peer proof artifact before independent verification."
    followup = {
        "text": peer_note,
        "kind": "peer_source_inspection",
        "basis_artifact_ids": ["peer-artifact"],
        "rationale": (
            "The independent peer inspection does not supply a premise or inference "
            "in the self-contained reviewed derivation."
        ),
    }
    argument = [
        {
            "epistemic_status": "deduction",
            "argument": "The insertion bound and attaining construction agree.",
            "review": {
                "disposition": "accepted",
                "rationale": "The lower and upper region bounds follow from the recorded construction.",
                "objection": "",
            },
        }
    ]
    investigation = {"claim_is_conditional": False, "assumptions": []}
    record = {
        "investigation_type": "mathematical",
        "artifacts": [{"id": "peer-artifact", "strategy_id": "euler"}],
    }
    branch = {"strategy_id": "incremental"}
    output = {
        "objective_status": "achieved",
        "assessment": "continue",
        "stop_reason": "recoverable_objection",
        "next_question": peer_note,
        "verification_status": "convincing_unverified",
        "solution_claim": "R(n) = 1 + n(n+1)/2.",
        "argument_summary": "Upper bound and explicit attainment.",
        "proof_obligations": ["Insertion bound reviewed", "Attainment reviewed"],
        "claim_is_conditional": False,
        "remaining_obligations": [peer_note],
        "unresolved_objections": [peer_note],
        "objections": [peer_note],
        "verification_followups": [followup],
        "response": "The proof is a convincing but unverified candidate.",
    }
    classify = lambda value, steps=argument, inv=investigation, rec=record: (
        research_sessions._reviewed_objective_candidate(rec, branch, inv, value, steps, [])
    )
    assert classify(output) == (True, [peer_note])
    assert (
        "verification_followups"
        in research_sessions._research_schema(research_sessions.Skeptic)["required"]
    )

    # None of these substantive/ungrounded cases may be waived.
    bad = deepcopy(output)
    bad["remaining_obligations"].append("Prove the missing lower-bound step.")
    assert classify(bad)[0] is False
    bad = deepcopy(output)
    bad["verification_followups"][0]["basis_artifact_ids"] = ["invented-source"]
    assert classify(bad)[0] is False
    bad = deepcopy(output)
    bad["verification_followups"][0]["text"] = "A different task"
    assert classify(bad)[0] is False
    bad = deepcopy(output)
    bad["verification_status"] = "incomplete"
    assert classify(bad)[0] is False
    bad = deepcopy(output)
    bad["objective_status"] = "partial"
    assert classify(bad)[0] is False
    bad = deepcopy(output)
    bad["claim_is_conditional"] = True
    assert classify(bad)[0] is False
    bad = deepcopy(output)
    bad["stop_reason"] = "decisive_counterexample"
    assert classify(bad)[0] is False
    bad = deepcopy(output)
    bad["verification_followups"] = []
    assert classify(bad)[0] is False
    challenged = deepcopy(argument)
    challenged[0]["review"]["disposition"] = "challenged"
    challenged[0]["review"]["objection"] = "This inference is missing a premise."
    assert classify(output, challenged)[0] is False
    bad = deepcopy(record)
    bad["artifacts"].append(
        {
            "id": "counterexample",
            "strategy_id": "incremental",
            "coordinator_decision": "stop_decisive_counterexample",
            "objections": ["A genuine counterexample"],
        }
    )
    # Branch-local decisive counterexamples cannot be erased by peer followups.
    assert (
        research_sessions._reviewed_objective_candidate(
            bad, branch, investigation, output, argument, [bad["artifacts"][-1]]
        )[0]
        is False
    )

    achieved_review = {
        "status": "achieved",
        "claim": output["solution_claim"],
        "argument_summary": output["argument_summary"],
        "argument_steps": argument,
        "verification_status": "convincing_unverified",
        "unresolved_objections": [],
        "independent_verification_followups": [peer_note],
        "basis_artifact_ids": ["accepted-artifact"],
    }
    accepted = {
        "id": "accepted-artifact",
        "strategy_id": "incremental",
        "sequence": 2,
        "coordinator_decision": "stop_productive_conclusion",
        "objective_review": achieved_review,
        "skeptic_output": {"objective_status": "achieved"},
        "skeptic_response": "Convincing but unverified",
        "open_obligations": [peer_note],
    }
    partial = {
        "id": "partial-artifact",
        "strategy_id": "euler",
        "sequence": 3,
        "coordinator_decision": "stop_round_limit",
        "objective_review": {
            "status": "partial",
            "claim": "A second route is unfinished.",
            "verification_status": "incomplete",
        },
        "skeptic_output": {"objective_status": "partial"},
        "skeptic_response": "Peer review remains open",
        "open_obligations": [],
    }
    saved = {
        "status": "ended",
        "strategy_runs": [],
        "artifacts": [accepted, partial],
    }
    positive = research_sessions._outcome_without_metrics(saved)
    assert positive["assessment"] == "positive"
    assert positive["solution_review"]["independent_verification_followups"] == [peer_note]
    assert "independently verified" in " ".join(positive["caveats"])
    assert peer_note in positive["conclusion"]
    reversed_record = {**saved, "artifacts": list(reversed(saved["artifacts"]))}
    reversed_result = research_sessions._outcome_without_metrics(reversed_record)
    assert reversed_result["assessment"] == positive["assessment"]
    assert reversed_result["solution_review"] == positive["solution_review"]
    assert reversed_result["conclusion"] == positive["conclusion"]

    historical = {
        **saved,
        "artifacts": [
            {
                **accepted,
                "objective_review": {
                    "status": "partial",
                    "claim": output["solution_claim"],
                    "verification_status": "incomplete",
                },
            }
        ],
    }
    old = research_sessions._outcome_without_metrics(historical)
    assert old["assessment"] == "mixed"
    assert "promising finding" in old["label"]
    # The historical frozen record was never rewritten.
    assert historical["artifacts"][0]["objective_review"]["status"] == "partial"
    contradictory = deepcopy(saved)
    contradictory["artifacts"][1]["skeptic_output"] = {
        "objective_status": "partial",
        "cross_strategy_relations": [{"relation": "contradicts"}],
    }
    assert research_sessions._outcome_without_metrics(contradictory)["assessment"] == "mixed"


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
    # A positive candidate can terminate only the configured final round.
    # This fixture intentionally schedules one round; live Golden 9 math uses three.
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
        payload = json.loads(request.content)
        provider_requests.append(payload)
        response = outputs.pop(0)
        # In the final aggregate proof cycle the saved ledger must receive
        # explicit, evidence-linked dispositions. Model agreement alone no
        # longer globally closes previous Investigator obligations.
        context = json.loads(payload["input"])
        if context.get("cycle") == 3 and response.get("objective_status") == "achieved":
            basis_ids = context.get("context_artifact_ids", [])[-3:]
            response["obligation_reviews"] = [
                {
                    "obligation_id": item["obligation_id"],
                    "status": "addressed",
                    "basis_artifact_ids": basis_ids,
                    "basis_step_ids": [],
                    "rationale": (
                        "The accepted saved upper-bound, attaining-construction, "
                        "and boundary-case proof steps establish this obligation."
                    ),
                }
                for item in context.get("obligation_ledger", [])
                if item.get("status") == "unresolved"
            ]
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
            str(path), strategy.id, str(uuid4()), view.project.id, credential["identity"]
        )
        finished = await wait_for(path, started["id"])
        assert "context manifest explains selection" in provider_requests[1]["instructions"]
        skeptic_context = json.loads(provider_requests[1]["input"])
        assert skeptic_context["context_manifest"]["policy_version"] == "continuity-v2"
        assert "prior_artifacts" in skeptic_context
        assert skeptic_context["investigator_output"]["claim"] == proof["claim"]
        assert all(isinstance(step.get("context_manifest"), dict) for step in finished["steps"])
        from sigma.api import export_project_view

        exported_session = next(
            item
            for item in export_project_view(str(path))["research_sessions"]
            if item["id"] == finished["id"]
        )
        assert exported_session["steps"][1]["context_manifest"]["policy_version"] == "continuity-v2"
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
        assert finished["termination_reason_code"] == "protocol_complete"
        assert finished["current_action"] == "Completed · configured protocol"
        assert "All 2 configured" in finished["message"]
        assert "unverified research notes" in finished["message"]
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
    # The counterexample must be reviewed on the final configured round.
    # Earlier rounds deliberately continue under PR #476's protocol policy.
    research_sessions.save_limits(
        str(path),
        {**research_sessions.DEFAULT_LIMITS, "research_rounds": 1, "model_calls": 2},
    )
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
    # The counterexample refutes the attempted formula, not the global
    # project objective of establishing the true maximum region count.
    assert finished["outcome"]["assessment"] == "mixed"
    assert finished["outcome"]["solution_review"]["status"] == "not_achieved"
    assert finished["outcome"]["solution_review"]["unresolved_objections"] == [
        "The n=2 counterexample refutes the proposed candidate."
    ]
    assert finished["strategy_assessments"][0]["assessment"] == "unproductive"
    persisted = research_sessions.get_session(str(path), started["id"])
    assert persisted["outcome"] == finished["outcome"]
    assert persisted["artifacts"][0]["skeptic_response"] == genuine_objection["response"]


async def test_strategy_skeptic_does_not_wait_for_sibling_investigator(path: Path):
    """A fast branch can reach Skeptic while a sibling Investigator is stalled."""
    view, first, credential, config = await setup(path)
    second = create_strategy(
        path, "Independent fast route", "Complete an unrelated argument."
    ).project.strategies[-1]
    limits = dict(research_sessions.DEFAULT_LIMITS)
    limits.update(research_rounds=1, model_calls=4)
    research_sessions.save_limits(str(path), limits)
    fast_skeptic_seen = asyncio.Event()
    started_roles: dict[str, list[str]] = {first.id: [], second.id: []}

    async def handler(request):
        payload = json.loads(request.content)
        context = json.loads(payload["input"])
        strategy_id = context["strategy"]["id"]
        role = payload["text"]["format"]["name"]
        started_roles[strategy_id].append(role)
        if strategy_id == first.id and role == "research_investigator":
            # The original global Investigator wave barrier deadlocks here.
            await asyncio.wait_for(fast_skeptic_seen.wait(), timeout=3)
        if strategy_id == second.id and role == "research_skeptic":
            # Only durably committed reviewed peer findings can cross into
            # this turn. The slow Investigator is still in flight.
            assert context["other_strategy_evidence"] == []
            fast_skeptic_seen.set()
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
        finished = await asyncio.wait_for(wait_for(path, started["id"]), timeout=8)

    assert fast_skeptic_seen.is_set()
    assert finished["status"] == "ended", finished["message"]
    assert finished["calls_used"] == 4
    assert len(finished["artifacts"]) == 2
    for roles in started_roles.values():
        assert roles == ["research_investigator", "research_skeptic"], roles


async def test_preflight_failure_isolates_branch_and_commits_sibling(path: Path):
    """A branch preflight failure cannot throw away a sibling's completed review."""
    view, first, credential, config = await setup(path)
    second = create_strategy(
        path, "Completed sibling route", "Finish an independent argument."
    ).project.strategies[-1]
    limits = {**research_sessions.DEFAULT_LIMITS, "research_rounds": 1, "model_calls": 4}
    research_sessions.save_limits(str(path), limits)
    original_role_call = research_sessions._portfolio_role_call
    sibling_completed = asyncio.Event()

    async def injected_role_call(session_id, location, strategy_id, role, cycle, semaphore, lock):
        if strategy_id == first.id and role == "investigator":
            await asyncio.wait_for(sibling_completed.wait(), timeout=5)
            raise ProjectError(
                "AI account or billing connection could not be verified; session paused before a new call."
            )
        result = await original_role_call(
            session_id, location, strategy_id, role, cycle, semaphore, lock
        )
        if strategy_id == second.id and role == "skeptic" and result is True:
            sibling_completed.set()
        return result

    async def handler(request):
        payload = json.loads(request.content)
        context = json.loads(payload["input"])
        output = (
            investigation(context["cycle"])
            if payload["text"]["format"]["name"] == "research_investigator"
            else skeptic(context["cycle"], "stop")
        )
        return httpx.Response(200, json=provider_response(output))

    with (
        patch.object(research_sessions, "auth_context", new=AsyncMock(return_value=credential)),
        patch.object(research_sessions, "configuration", new=AsyncMock(return_value=config)),
        patch.object(research_sessions, "execution_capabilities", return_value=[]),
        patch.object(research_sessions, "_portfolio_role_call", new=injected_role_call),
        patch(
            "sigma.research_sessions.httpx.AsyncClient",
            side_effect=lambda **kw: REAL_CLIENT(transport=httpx.MockTransport(handler), **kw),
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
        final = await asyncio.wait_for(wait_for(path, started["id"]), timeout=10)

    assert sibling_completed.is_set()
    assert len(final["artifacts"]) == 1, final.get("message")
    assert final["artifacts"][0]["strategy_id"] == second.id
    saved = {branch["strategy_id"]: branch for branch in final["strategy_runs"]}
    assert saved[first.id]["status"] == "paused"
    assert saved[second.id]["status"] == "ended"
    assert final["status"] == "paused"
    reopened = research_sessions.get_session(str(path), started["id"])
    assert len(reopened["artifacts"]) == 1


async def test_stop_is_responsive_during_slow_provider_preflight(path: Path):
    """Pausing or stopping does not wait behind a model/account network check."""
    view, first, credential, config = await setup(path)
    limits = {**research_sessions.DEFAULT_LIMITS, "research_rounds": 1, "model_calls": 2}
    research_sessions.save_limits(str(path), limits)
    checking = asyncio.Event()
    release = asyncio.Event()
    verification_calls = 0

    async def account_check():
        nonlocal verification_calls
        verification_calls += 1
        if verification_calls > 1:
            checking.set()
            await release.wait()
        return credential

    with (
        patch.object(research_sessions, "auth_context", new=account_check),
        patch.object(research_sessions, "configuration", new=AsyncMock(return_value=config)),
        patch.object(research_sessions, "execution_capabilities", return_value=[]),
    ):
        started = await research_sessions.start_session(
            str(path),
            first.id,
            str(uuid4()),
            view.project.id,
            credential["identity"],
            expected_limits=limits,
        )
        await asyncio.wait_for(checking.wait(), timeout=5)
        try:
            stopped = await asyncio.wait_for(
                research_sessions.control_session(str(path), started["id"], "stop"),
                timeout=1,
            )
            assert stopped["status"] == "stopped"
        finally:
            release.set()
        saved = research_sessions.get_session(str(path), started["id"])
        assert saved["status"] == "stopped"
        assert saved["calls_used"] == 0
        assert saved["steps"] == []


async def test_duplicate_strategy_dispatch_is_fenced_during_provider_call(path: Path):
    """Two dispatchers must not run the same strategy turn concurrently."""
    view, first, credential, config = await setup(path)
    limits = {
        **research_sessions.DEFAULT_LIMITS,
        "research_rounds": 1,
        "model_calls": 2,
    }
    research_sessions.save_limits(str(path), limits)
    investigator_started = asyncio.Event()
    release_investigator = asyncio.Event()
    requests: list[str] = []

    async def handler(request):
        payload = json.loads(request.content)
        role = payload["text"]["format"]["name"]
        requests.append(role)
        if role == "research_investigator":
            investigator_started.set()
            await release_investigator.wait()
        output = investigation(1) if role == "research_investigator" else skeptic(1, "stop")
        return httpx.Response(200, json=provider_response(output))

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
        started = await research_sessions.start_session(
            str(path),
            first.id,
            str(uuid4()),
            view.project.id,
            credential["identity"],
            expected_limits=limits,
        )
        await asyncio.wait_for(investigator_started.wait(), timeout=5)
        try:
            duplicate = await asyncio.wait_for(
                research_sessions._portfolio_role_call(
                    started["id"],
                    str(path),
                    first.id,
                    "investigator",
                    1,
                    asyncio.Semaphore(2),
                    research_sessions._session_state_lock(started["id"]),
                ),
                timeout=5,
            )
            assert duplicate is False
            saved = research_sessions.get_session(str(path), started["id"])
            assert len([step for step in saved["steps"] if step["status"] == "running"]) == 1
        finally:
            release_investigator.set()
        finished = await asyncio.wait_for(wait_for(path, started["id"]), timeout=8)

    assert requests == ["research_investigator", "research_skeptic"], requests
    assert finished["calls_used"] == 2
    assert len(finished["steps"]) == 2
    assert len(finished["artifacts"]) == 1


if __name__ == "__main__":
    from research_sessions_split_runner import run

    run(2)
