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
        "python_code": None,
        "sage_code": None,
        "prior_session_failure_attempt_ids": [],
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
            assert (
                "retracted_cross_strategy_source_artifact_ids"
                in payload["text"]["format"]["schema"]["required"]
            )
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
        }
    ], next_context["prior_session_findings"]
    assert next_context["prior_session_artifact_ids"] == [completed["artifacts"][0]["id"]]
    persisted = research_sessions.get_session(str(path), next_session["id"])
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
    try:
        research_sessions._agent_context(oversized_context, "skeptic", 2)
    except ProjectError as exc:
        assert "safe input limit" in str(exc)
    else:
        raise AssertionError("oversized complete history was silently truncated")

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
        assert (
            "entire ordered set of current-session saved artifacts"
            in provider_requests[1]["instructions"]
        )
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
        assert any("unverified" in item.lower() for item in finished["outcome"]["caveats"])
        rows = finished["strategy_assessments"]
        assert [row["assessment"] for row in rows] == ["contributed_to_solution", "not_used"]
        assert rows[0]["basis_artifact_ids"] == [finished["artifacts"][0]["id"]]
        assert rows[1]["basis_artifact_ids"] == []

        # The same candidate language must not override a Skeptic's material,
        # unresolved objection. Before the evidence-contract fix this passed
        # the special-case keyword checklist and was incorrectly promoted.
        incomplete_review = {
            **review,
            "assessment": "continue",
            "stop_reason": "recoverable_objection",
            "response": "No mathematical counterexample is apparent, but the central component-identification step remains asserted.",
            "objections": ["The region/sign-set identification remains asserted."],
            "remaining_obligations": ["Justify that each sign set is exactly one component."],
            "next_question": "Review the component-identification step.",
            "objective_status": "not_achieved",
            "proof_obligations": ["Review the insertion argument."],
            "verification_status": "incomplete",
            "unresolved_objections": ["The region/sign-set identification remains asserted."],
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
        assert incomplete["outcome"]["solution_review"]["status"] == "not_achieved"
        assert "region/sign-set" in " ".join(
            incomplete["outcome"]["solution_review"]["unresolved_objections"]
        )
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
    view = initialize_project(
        path,
        "Maximum Regions · answer-free regression",
        "Determine the greatest number of regions formed by n distinct straight lines in the plane. State assumptions, derive an upper bound, and give a construction if you can.",
        research_mode="mathematical",
        difficulty="easy",
    )
    strategy = create_strategy(
        path,
        "Incremental line insertion",
        "Study what one newly inserted line can add. Bound its segments by its intersections with the earlier lines, and seek a configuration attaining the bound.",
    ).project.strategies[0]
    credential = {
        "identity": "fixture-account",
        "mode": "api_key",
        "token": "fixture-token",
        "status": "connected",
    }
    config = {"available": True, "model": MODEL, "reasoning_effort": "high"}
    outputs = [investigation(1), skeptic(1, "stop", "productive_conclusion")]
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

    assert finished["status"] == "ended" and finished["artifacts"]
    assert len(inputs) == 2
    for context in inputs:
        assert context["problem"] == view.project.problem
        assert context["strategy"]["approach"] == strategy.approach
        prompt = json.dumps(context)
        assert "1 + n(n+1)/2" not in prompt
        assert "y=kx+k^2" not in prompt
    # This is an answer-leakage regression fixture, not evidence that a model
    # can independently solve the problem; the provider is mocked above.


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
            completion_order.append((context["strategy"]["id"], role))
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


def main():
    with TemporaryDirectory() as temporary:
        root = Path(temporary)
        asyncio.run(test_disabled_strategy_never_starts_a_run(root / "disabled.sigma"))
        asyncio.run(test_three_cycles_and_idempotency(root / "cycles.sigma"))
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
        asyncio.run(
            test_maximum_regions_solution_and_frozen_attribution(root / "maximum-regions.sigma")
        )
        asyncio.run(
            test_answer_free_maximum_regions_prompt(root / "maximum-regions-answer-free.sigma")
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
