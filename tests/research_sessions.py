"""Persistent A17 sessions use deterministic provider fixtures only."""

import asyncio
import json
import time
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
    project_path,
    set_strategy_enabled,
)

MODEL = "gpt-6.1-sol"
REAL_CLIENT = httpx.AsyncClient


def provider_response(value):
    value = dict(value)
    if "claim" in value:
        value.setdefault("human_guidance_reviews", [])
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
    submitted_payloads = []

    async def handler(request):
        payload = json.loads(request.content)
        assert payload["model"] == MODEL and payload["store"] is False
        assert payload["max_output_tokens"] == 12000
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
        assert started["call_limit"] == 30
        assert started["cycle_limit"] == 3
        assert started["duration_limit_minutes"] == 60
        assert started["output_token_limit"] == 12000
        finished = await wait_for(path, started["id"])
        duplicate = await research_sessions.start_session(
            str(path), strategy.id, key, view.project.id, credential["identity"]
        )
        assert duplicate["id"] == started["id"]

    assert finished["status"] == "ended" and finished["calls_used"] == 6
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
    assert exported_session["strategy_text"] == strategy.approach
    assert exported_session["problem"] == view.project.problem
    metrics = exported_session["outcome"]["metrics"]
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
    outputs = [investigation(1), skeptic(1, "stop", "productive_conclusion")]
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
            "session_id": completed["id"],
            "session_number": completed["session_number"],
            "strategy_id": strategy.id,
            "strategy_title": strategy.title,
            "extract_truncated_fields": [],
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
            return httpx.Response(503, json={"error": {"code": "temporary_unavailable"}})
        context = json.loads(payload["input"])
        role = payload["text"]["format"]["name"]
        if role == "research_investigator":
            assert len(context["prior_session_failures"]) == 1
            failure = context["prior_session_failures"][0]
            assert failure["attempt_id"] in context["prior_session_failure_attempt_ids"]
            assert failure["failure_kind"] == "provider_error"
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
        for index in range(100)
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
        assert "Investigator provider call 1/30 in progress" in progress["message"]
        paused = await research_sessions.control_session(str(path), started["id"], "pause")
        await asyncio.sleep(0.02)
        paused = research_sessions.get_session(str(path), started["id"])
    assert paused["status"] == "paused" and paused["calls_used"] == 1
    assert paused["steps"][-1]["status"] == "interrupted"
    paused_metrics = {
        item["label"]: item["value"] for item in paused["outcome"]["metrics"]["operational"]
    }
    assert "1 interrupted / cancelled" in paused_metrics["Model calls by status"]
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
        assert "2 interrupted / cancelled" in stopped_metrics["Model calls by status"]
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
        try:
            await research_sessions._call(
                {**record, "output_token_limit": 11},
                "investigator",
                {"problem": view.project.problem, "strategy": strategy.approach},
            )
        except ProjectError as exc:
            assert "exceeded the configured per-call token limit" in str(exc)
        else:
            raise AssertionError("ChatGPT response exceeded the configured output token limit")
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
    operational_metrics = {
        item["label"]: item["value"] for item in finished["outcome"]["metrics"]["operational"]
    }
    assert operational_metrics["Tokens · input / output / cached / total"] == "240 / 160 / 40 / 400"
    assert operational_metrics["Estimated monetary cost"] == (
        "$0.002004 estimated (rates checked 2026-10-23)"
    )
    assert research_sessions.get_limits(str(path)) == future


def test_limits_validation(path: Path):
    initialize_project(path, "Limits project", "A question")
    before = research_sessions.get_limits(str(path))
    invalid = [
        {**before, "model_calls": 31},
        {**before, "research_rounds": 6, "model_calls": 30},
        {**before, "research_rounds": 3, "model_calls": 5},
        {**before, "session_duration_minutes": 7 * 24 * 60 + 1},
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
        "research_rounds": 5,
        "model_calls": 30,
        "session_duration_minutes": 7 * 24 * 60,
        "output_tokens_per_call": 16384,
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
    assert [item["strategy_title"] for item in findings] == ["Branch one", "Branch two"]
    assert (
        findings[0]["reasoning_steps"][0]["review"]["objection"]
        == "The bound is not yet established."
    )
    assert findings[0]["status"] == "partial"
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
                "argument": "The pieces are asserted to create n new regions.",
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
                "argument": "The arrangement consists of n distinct straight lines in the Euclidean plane. A maximizing arrangement is in general position: no two lines are parallel and no three meet at one point.",
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
        "assumptions_reviewed": ["Distinct straight lines in the Euclidean plane."],
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
        assert finished["outcome"]["assessment"] == "positive"
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

        # Three cycles can distribute the proof across saved artifacts. The
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
        assert all(
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
        # start_session takes the first snapshot. The first branch then fails
        # preflight; its sibling proceeds to the provider fixture.
        if snapshot_calls == 2:
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
    assert "1 rejected" in metrics["Model calls by status"]
    assert "1 provider failure(s) (1 rejected" in metrics["Provider failures / retries"]
    assert branches[second.id]["status"] == "ended"
    assert finished["artifacts"]
    assert {item["strategy_id"] for item in finished["artifacts"]} == {second.id}
    assert any(
        strategy_id == first.id and role == "research_investigator" for strategy_id, role in roles
    )
    assert all(strategy_id == second.id for strategy_id, _ in roles if strategy_id != first.id)


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
    assert "1 timed out" in timeout_metrics["Model calls by status"]
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
    assert finished["events"][-1]["kind"] == "portfolio.completed"


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

    token_limit = 12_000

    async def oversized_parsed(request):
        response = provider_response(investigation(1))
        response["output"][0]["content"][0]["text"] += " " * 70_000
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

    calls = operational["Model calls by status"]
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
    assert quality["Research cycles"] == "2 completed / 2 started"
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
    assert research_sessions._estimate_cost(MODEL, missing_cached) is None

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
    assert "unavailable" in uncached_ops["Estimated monetary cost"]

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


def main():
    test_request_audit_truncation_tokens_and_reconciliation()
    with TemporaryDirectory() as temporary:
        root = Path(temporary)
        asyncio.run(test_disabled_strategy_never_starts_a_run(root / "disabled.sigma"))
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
        asyncio.run(test_chatgpt_stream(root / "chatgpt.sigma"))
        asyncio.run(
            test_session_deadline_bounds_generous_call_timeout(
                root / "generous-call-deadline.sigma"
            )
        )
        asyncio.run(test_limits_snapshot_and_usage_cost(root / "limits.sigma"))
        test_limits_validation(root / "invalid-limits.sigma")
        asyncio.run(test_legacy_limits_are_preserved(root / "legacy-limits.sigma"))
        asyncio.run(test_single_project_admission(root / "single-session.sigma"))
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
        asyncio.run(test_generic_objective_review_on_binary_strings(root / "binary-strings.sigma"))
        test_outcome_classification()
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
    print("Persistent research session scenarios passed.")


if __name__ == "__main__":
    main()
