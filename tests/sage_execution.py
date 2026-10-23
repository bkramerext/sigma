"""Deterministic Sage contracts, agent guidance, evidence and restart/cancel safety."""

import asyncio
import hashlib
import json
from contextlib import ExitStack
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import httpx
from fastapi.testclient import TestClient
from pydantic import ValidationError
from research_sessions import (
    MODEL,
    REAL_CLIENT,
    investigation,
    provider_response,
    setup,
    skeptic,
    wait_for,
)

from sigma import papers, python_sandbox, research_sessions, research_tools
from sigma.api import app, export_project_view
from sigma.project_reports import render_report

SAGE_CODE = "R.<x> = PolynomialRing(QQ)\nprint(factor(x^4 - 1))"


def capabilities(available=True):
    with patch.object(
        python_sandbox, "_image_identity", return_value="sha256:" + "a" * 64 if available else None
    ):
        return research_tools.execution_capabilities()


def provider_stack(credential, config, handler, tools):
    stack = ExitStack()
    stack.enter_context(
        patch.object(research_sessions, "auth_context", new=AsyncMock(return_value=credential))
    )
    stack.enter_context(
        patch.object(research_sessions, "configuration", new=AsyncMock(return_value=config))
    )
    stack.enter_context(
        patch.object(research_sessions, "execution_capabilities", return_value=tools)
    )
    stack.enter_context(
        patch(
            "sigma.research_sessions.httpx.AsyncClient",
            side_effect=lambda **kwargs: REAL_CLIENT(
                transport=httpx.MockTransport(handler), **kwargs
            ),
        )
    )
    return stack


def test_contract():
    for available in (True, False):
        tools = capabilities(available)
        assert {tool["runtime"] for tool in tools} == {"python", "sagemath"}
        assert all(tool["available"] is available for tool in tools)
        for role in ("investigator", "skeptic"):
            instructions = research_sessions._role_instructions(role, {"execution_tools": tools})
            assert f"SageMath is {'available' if available else 'unavailable'}" in instructions
            assert "sage_code" in instructions and "sage_execution" in instructions
            assert "Only the Investigator dispatches" in instructions
            assert (
                "next Investigator cycle" in instructions
                and "not independent formal proof" in instructions
            )
    try:
        research_sessions.Investigator.model_validate(
            {**investigation(1), "python_code": "print(1)", "sage_code": SAGE_CODE}
        )
    except ValidationError:
        pass
    else:
        raise AssertionError("Ambiguous two-runtime proposal accepted")
    schema = research_sessions._research_schema(research_sessions.Investigator)
    assert set(schema["required"]) == set(schema["properties"])
    assert "sage_code" in schema["required"]
    incomplete = research_sessions._outcome_metrics(
        {"calls_used": 0, "steps": [{"output": {"sage_execution": {"status": "completed"}}}]},
        {"assessment": "pending"},
    )
    assert {item["label"]: item["value"] for item in incomplete["operational"]}[
        "SageMath runs by status"
    ] == "— (execution record without ID)"
    args = python_sandbox.docker_command(image=python_sandbox.SAGE_IMAGE, runtime_name="sagemath")
    for arg in (
        "--network=none",
        "--memory=1024m",
        "--memory-swap=1024m",
        "--cpus=1",
        "--pids-limit=64",
        "--read-only",
        "--user=65532:65532",
        "--cap-drop=ALL",
        "--security-opt=no-new-privileges",
        "--pull=never",
    ):
        assert arg in args
    assert not any("mount" in arg or "volume" in arg for arg in args)
    assert python_sandbox.docker_command(runtime_name="sagemath")[-1] == python_sandbox.SAGE_IMAGE
    assert python_sandbox._EXECUTION_GATE.acquire(blocking=False)
    try:
        assert asyncio.run(python_sandbox.execute(SAGE_CODE, "sagemath")).status == "busy"
    finally:
        python_sandbox._EXECUTION_GATE.release()


async def test_integrated(path, status, available=True):
    view, strategy, credential, config = await setup(path)
    limits = research_sessions.get_limits(str(path))
    limits["research_rounds"] = 1
    research_sessions.save_limits(str(path), limits)
    tools = capabilities(available)
    contexts = []
    result = python_sandbox.ExecutionResult(
        status,
        0 if status == "completed" else None,
        "(x - 1) * (x + 1) * (x^2 + 1)\n" if status == "completed" else "",
        "" if status == "completed" else "recorded failure",
        8,
        "sha256:" + "a" * 64,
        (("factors.txt", "text/plain", b"finite computation"),) if status == "completed" else (),
    )

    async def handler(request):
        payload = json.loads(request.content)
        context = json.loads(payload["input"])
        role = payload["text"]["format"]["name"]
        assert context["execution_tools"] == tools
        assert payload["instructions"] == research_sessions._role_instructions(
            role.removeprefix("research_"), context
        )
        assert (
            f"SageMath is {'available' if available else 'unavailable'}" in payload["instructions"]
        )
        contexts.append(context)
        if role == "research_investigator":
            assert "sage_code" in payload["text"]["format"]["schema"]["required"]
            output = {**investigation(1), "sage_code": SAGE_CODE}
        else:
            execution = context["investigator_output"]["sage_execution"]
            assert execution["status"] == status and execution["source"] == SAGE_CODE
            assert execution["runtime"] == "sagemath" and execution["syntax"] == "sage-preparsed"
            assert execution["agent"]["role"] == "investigator"
            output = skeptic(1)
        return httpx.Response(200, json=provider_response(output))

    with (
        provider_stack(credential, config, handler, tools),
        patch.object(python_sandbox, "execute", new=AsyncMock(return_value=result)) as execute,
    ):
        started = await research_sessions.start_session(
            str(path), strategy.id, str(uuid4()), view.project.id, credential["identity"]
        )
        finished = await wait_for(path, started["id"])
    execute.assert_awaited_once_with(SAGE_CODE, "sagemath")
    assert finished["calls_used"] == 2 and len(contexts) == 2
    evidence = finished["artifacts"][0]["investigator_output"]["sage_execution"]
    assert evidence == python_sandbox.get_execution(path, evidence["id"])
    assert evidence["source_sha256"] == hashlib.sha256(SAGE_CODE.encode()).hexdigest()
    assert evidence["session_id"] == started["id"] and evidence["strategy_id"] == strategy.id
    assert evidence["agent"]["step_id"] == finished["steps"][0]["id"]
    assert finished["steps"][0]["execution_tools"] == tools
    metrics = finished["outcome"]["metrics"]
    values = {item["label"]: item["value"] for item in metrics["operational"]}
    assert values["SageMath runs by status"] == f"1 {status}"
    assert values["Python runs by status"] == "0 executions"
    assert metrics["sources"]["execution_ids"] == [evidence["id"]]
    assert finished["outcome"]["solution_review"]["verification_status"] != "verified"
    if status == "completed":
        assert (
            python_sandbox.get_execution_artifact(path, evidence["id"], "factors.txt")[0]
            == b"finite computation"
        )
    for role in ("investigator", "skeptic"):
        peer = {
            "strategy_id": str(uuid4()),
            "strategy_title": "Peer",
            "strategy_text": "Review",
            "current_question": "Review",
            "pending_investigation": investigation(1),
        }
        context = research_sessions._portfolio_context(finished, peer, role, 1)
        assert context["other_strategy_evidence"][0]["sage_execution"]["id"] == evidence["id"]
    assert (
        research_sessions._prior_session_findings(str(path), str(uuid4()))[0]["sage_execution"][
            "id"
        ]
        == evidence["id"]
    )
    exported = export_project_view(str(path))
    assert exported["research_sessions"][0]["outcome"]["metrics"] == metrics
    for fmt in ("txt", "html"):
        report, _ = render_report(exported, fmt)
        assert isinstance(report, str) and "SageMath runs by status" in report
    with patch("sigma.api.export_project_view", return_value=exported):
        snapshot, _ = papers._snapshot(str(path))
    assert any(
        item["kind"] == "artifact"
        and item["data"]["investigator_output"]["sage_execution"]["id"] == evidence["id"]
        for item in snapshot["sources"]
    )
    with TestClient(app) as client:
        read = client.get(
            f"/api/projects/research-executions/{evidence['id']}", params={"path": str(path)}
        )
        assert read.status_code == 200 and read.json() == evidence
        bad = client.post(
            "/api/projects/research-executions",
            json={"path": str(path), "source": "print(1)", "runtime": "shell"},
        )
        assert bad.status_code == 422


async def test_recovery_and_runtime_identity(path):
    view, strategy, _, _ = await setup(path)
    session_id, step_id = str(uuid4()), str(uuid4())
    output = {**investigation(1), "sage_code": SAGE_CODE}
    record = {
        "id": session_id,
        "project_path": str(path.resolve()),
        "project_id": view.project.id,
        "status": "running",
        "model": MODEL,
        "reasoning_effort": "medium",
        "strategy_runs": [
            {
                "strategy_id": strategy.id,
                "strategy_title": "Sage",
                "cycle": 1,
                "pending_investigation": output,
            }
        ],
        "steps": [
            {
                "id": step_id,
                "strategy_id": strategy.id,
                "role": "investigator",
                "cycle": 1,
                "status": "completed",
                "output": output,
            }
        ],
        "events": [],
    }
    research_sessions._save(str(path), record)
    fake = python_sandbox.ExecutionResult("failed", 1, "", "bad experiment", 5)
    with patch.object(python_sandbox, "execute", new=AsyncMock(return_value=fake)):
        saved = await python_sandbox.execute_research_code(
            path,
            SAGE_CODE,
            session_id=session_id,
            strategy_id=strategy.id,
            cycle=1,
            runtime_name="sagemath",
            step_id=step_id,
        )
        # Identical bytes in a different runtime cannot attach Sage's result.
        assert (
            python_sandbox.find_session_execution(
                path, session_id=session_id, strategy_id=strategy.id, cycle=1, source=SAGE_CODE
            )
            is None
        )
    target = path / "research-executions" / f"{saved['id']}.json"
    reserved = json.loads(target.read_text())
    for uncertain in (False, True):
        if uncertain:
            reserved.update(status="running", stdout="", stderr="", exit_code=None)
            target.write_text(json.dumps(reserved))
        research_sessions._save(str(path), record)
        with patch.object(
            research_sessions,
            "execute_research_code",
            new=AsyncMock(side_effect=AssertionError("Recovery must never duplicate a run")),
        ):
            await research_sessions._complete_pending_python(
                session_id, str(path), strategy.id, 1, asyncio.Lock()
            )
        loaded = research_sessions._read(str(path), session_id)
        evidence = loaded["strategy_runs"][0]["pending_investigation"]["sage_execution"]
        assert evidence["id"] == saved["id"]
        assert evidence["status"] == ("interrupted" if uncertain else "failed")
        record["strategy_runs"][0]["pending_investigation"].pop("sage_execution", None)
    reserved["runtime_version"] = "older-profile"
    target.write_text(json.dumps(reserved))
    # Preserve an uncertain original reservation in its own cycle, but do not
    # reuse a failed older runtime profile for a newly requested experiment.
    assert (
        python_sandbox.find_session_execution(
            path,
            session_id=session_id,
            strategy_id=strategy.id,
            cycle=1,
            source=SAGE_CODE,
            runtime_name="sagemath",
        )
        is not None
    )
    assert (
        python_sandbox.find_session_execution(
            path,
            session_id=session_id,
            strategy_id=strategy.id,
            cycle=2,
            source=SAGE_CODE,
            runtime_name="sagemath",
            include_prior_failures=True,
        )
        is None
    )


async def test_failure_reuse_then_revision(path):
    view, strategy, credential, config = await setup(path)
    tools = capabilities()
    outputs = [
        dict(investigation(1), sage_code="raise ValueError('revise')"),
        skeptic(1, "revise"),
        dict(investigation(2), sage_code="raise ValueError('revise')"),
        skeptic(2, "revise"),
        dict(investigation(3), sage_code=SAGE_CODE),
        skeptic(3),
    ]
    seen = []

    async def handler(request):
        context = json.loads(json.loads(request.content)["input"])
        if "investigator_output" in context:
            seen.append(context["investigator_output"])
        return httpx.Response(200, json=provider_response(outputs.pop(0)))

    async def execute(source, runtime):
        assert runtime == "sagemath"
        return python_sandbox.ExecutionResult(
            "completed" if source == SAGE_CODE else "failed",
            0 if source == SAGE_CODE else 1,
            "finite check" if source == SAGE_CODE else "",
            "" if source == SAGE_CODE else "revise",
            5,
        )

    with (
        provider_stack(credential, config, handler, tools),
        patch.object(python_sandbox, "execute", new=AsyncMock(side_effect=execute)) as sandbox,
    ):
        started = await research_sessions.start_session(
            str(path), strategy.id, str(uuid4()), view.project.id, credential["identity"]
        )
        finished = await wait_for(path, started["id"])
    assert sandbox.await_count == 2 and finished["calls_used"] == 6
    assert seen[0]["sage_execution"] == seen[1]["sage_execution"]
    assert "original" in seen[1]["sage_execution_reuse_reason"]
    assert seen[2]["sage_execution"]["status"] == "completed"
    assert {item["label"]: item["value"] for item in finished["outcome"]["metrics"]["operational"]}[
        "SageMath runs by status"
    ] == "1 completed · 1 failed"


async def test_mixed_queue_stop_and_resume(root):
    from sigma.projects import ProjectError, create_strategy

    path = root / "mixed-queue.sigma"
    view, strategy_a, credential, config = await setup(path)
    view_b, strategy_b, _, _ = await setup(root / "second-session.sigma")
    added = create_strategy(path, "Python peer", "Inspect a finite Python experiment.")
    peer = next(item for item in added.project.strategies if item.id != strategy_a.id)
    limits = research_sessions.get_limits(str(path))
    limits["research_rounds"] = 1
    research_sessions.save_limits(str(path), limits)
    entered, release = asyncio.Event(), asyncio.Event()
    dispatched = []

    async def execute(source, runtime="python"):
        dispatched.append(runtime)
        entered.set()
        await release.wait()
        return python_sandbox.ExecutionResult("completed", 0, "exact saved evidence", "", 20)

    async def handler(request):
        payload = json.loads(request.content)
        context = json.loads(payload["input"])
        if payload["text"]["format"]["name"] == "research_investigator":
            output = (
                {**investigation(1), "sage_code": SAGE_CODE}
                if context["strategy"]["id"] == strategy_a.id
                else {**investigation(1), "python_code": "print(1)"}
            )
        else:
            field = (
                "sage_execution"
                if context["strategy"]["id"] == strategy_a.id
                else "python_execution"
            )
            assert context["investigator_output"][field]["stdout"] == "exact saved evidence"
            output = skeptic(1)
        return httpx.Response(200, json=provider_response(output))

    with (
        provider_stack(credential, config, handler, capabilities()),
        patch.object(python_sandbox, "execute", new=AsyncMock(side_effect=execute)),
    ):
        started = await research_sessions.start_session(
            str(path),
            strategy_a.id,
            str(uuid4()),
            view.project.id,
            credential["identity"],
            strategy_ids=[strategy_a.id, peer.id],
        )
        await asyncio.wait_for(entered.wait(), 2)
        # Existing architecture admits one research session at a time. Preserve
        # that policy rather than introducing cross-session concurrency in T26.
        try:
            await research_sessions.start_session(
                str(root / "second-session.sigma"),
                strategy_b.id,
                str(uuid4()),
                view_b.project.id,
                credential["identity"],
            )
        except ProjectError as exc:
            assert "Another research worker" in str(exc)
        else:
            raise AssertionError("Second research session unexpectedly admitted")
        for _ in range(200):
            current = research_sessions.get_session(str(path), started["id"])
            if "Waiting for Python execution" in current["strategy_runs"][1]["current_action"]:
                break
            await asyncio.sleep(0.01)
        else:
            raise AssertionError("Mixed runtime proposal did not queue")
        stop_task = asyncio.create_task(
            research_sessions.control_session(str(path), started["id"], "stop")
        )
        await asyncio.sleep(0)
        release.set()
        await asyncio.wait_for(stop_task, 2)
        stopped = await wait_for(path, started["id"])
        assert dispatched == ["sagemath"] and stopped["calls_used"] == 2
        assert stopped["artifacts"] == []
        saved = stopped["strategy_runs"][0]["pending_investigation"]["sage_execution"]
        assert saved["status"] == "completed" and saved["agent"]["role"] == "investigator"
        await research_sessions.control_session(str(path), started["id"], "resume")
        finished = await wait_for(path, started["id"])
    assert dispatched == ["sagemath", "python"] and finished["calls_used"] == 4, (
        dispatched,
        finished["calls_used"],
        finished["status"],
        finished["message"],
        finished["strategy_runs"],
    )
    sage_artifact = next(
        item for item in finished["artifacts"] if item["strategy_id"] == strategy_a.id
    )
    assert sage_artifact["investigator_output"]["sage_execution"] == saved
    values = {
        item["label"]: item["value"] for item in finished["outcome"]["metrics"]["operational"]
    }
    assert values["SageMath runs by status"] == values["Python runs by status"] == "1 completed"


def main():
    test_contract()
    with TemporaryDirectory() as temporary:
        root = Path(temporary)
        for status in (
            "completed",
            "failed",
            "timeout",
            "interrupted",
            "output_limit",
            "busy",
            "unavailable",
        ):
            asyncio.run(test_integrated(root / f"{status}.sigma", status, status != "unavailable"))
        asyncio.run(test_recovery_and_runtime_identity(root / "recovery.sigma"))
        asyncio.run(test_failure_reuse_then_revision(root / "revision.sigma"))
        asyncio.run(test_mixed_queue_stop_and_resume(root))
    print(
        "PASS Sage agent advertisement, typed selection, persisted evidence/API/artifacts/metrics, failure revision and crash-safe recovery"
    )


if __name__ == "__main__":
    main()
