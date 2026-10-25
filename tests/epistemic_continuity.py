"""Offline role transport through real persistent session dispatch and exports."""

import asyncio
import hashlib
import importlib.util
import json
import os
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import httpx
from research_sessions import (
    REAL_CLIENT,
    investigation,
    provider_response,
    setup,
    skeptic,
    wait_for,
)

from sigma import research_sessions
from sigma.api import export_project_view
from sigma.project_reports import render_report
from sigma.projects import create_strategy, initialize_project, inspect_project
from sigma.research_state import current_understanding

program_spec = importlib.util.spec_from_file_location(
    "continuity_graph_programs",
    Path(__file__).resolve().parents[1] / "browser_checks/computation_programs.py",
)
assert program_spec and program_spec.loader
programs = importlib.util.module_from_spec(program_spec)
program_spec.loader.exec_module(programs)
ERROR, GRAPH_FIRST = programs.ERROR, programs.GRAPH_FIRST


def investigator_step(cycle: int, claim: str, argument: str, sources: list[str]) -> dict:
    value = investigation(cycle)
    value.update(
        claim=claim,
        method="OFFLINE SCRIPT: examine only this bounded parity claim and its saved source.",
        reasoning_steps=[
            {
                "title": "Bounded parity step",
                "argument": argument,
                "epistemic_status": "deduction",
                "basis_artifact_ids": sources,
            }
        ],
        assumptions=[],
        evidence_status="Offline scripted role derivation; no independent verifier or computation.",
        open_obligations=[
            "Characterize broader perturbations without assuming this local lemma solves the project."
        ],
    )
    return value


def skeptic_step(cycle: int, source_ids: list[str], response: str) -> dict:
    value = skeptic(cycle)
    value.update(
        response="OFFLINE SCRIPT: " + response,
        reasoning_assessments=[
            {
                "step_number": 1,
                "disposition": "accepted",
                "rationale": response,
                "objection": "",
                "basis_artifact_ids": source_ids,
            }
        ],
        assumptions_reviewed=[],
        proof_obligations=["Broader perturbation classification is not established."],
        remaining_obligations=["Broader perturbation classification is not established."],
        unresolved_objections=[],
        verification_status="incomplete",
        objective_status="partial",
        solution_claim="The cited local parity step holds; the larger characterization remains open.",
        argument_summary=response,
    )
    return value


def export(path: Path, destination: Path, slug: str) -> dict:
    audit = export_project_view(str(path))
    filename = destination / f"{slug}.audit.json"
    filename.write_text(json.dumps(audit, ensure_ascii=False, separators=(",", ":")) + "\n")
    files = [filename]
    for fmt in ("txt", "html", "tex"):
        report, _ = render_report(audit, fmt)
        target = destination / f"{slug}.report.{fmt}"
        target.write_text(report)
        files.append(target)
    return {
        "slug": slug,
        "project_id": audit["project"]["id"],
        "session_ids": [item["id"] for item in audit["research_sessions"]],
        "files": [
            {
                "path": str(item),
                "bytes": item.stat().st_size,
                "sha256": hashlib.sha256(item.read_bytes()).hexdigest(),
            }
            for item in files
        ],
    }


async def parity_project(path: Path, capture: list[dict]) -> dict:
    view, strategy, credential, config = await setup(path)
    limits = research_sessions.get_limits(str(path))
    limits.update(research_rounds=2, model_calls=4)
    research_sessions.save_limits(str(path), limits)
    phase = "first"
    first_artifact_id = None

    async def handler(request):
        nonlocal first_artifact_id
        body = json.loads(request.content)
        context = json.loads(body["input"])
        role = body["text"]["format"]["name"]
        capture.append({"phase": phase, "role": role, "body": body})
        cycle = context["cycle"]
        if phase == "first":
            if role == "research_investigator" and cycle == 1:
                result = investigator_step(
                    1,
                    "For every integer n, n(n+1) is even.",
                    "Consecutive integers have opposite parity, so their product is divisible by 2.",
                    [],
                )
            elif role == "research_skeptic" and cycle == 1:
                result = skeptic_step(
                    1,
                    [],
                    "The parity lemma follows from exhaustive parity cases; retain the broader duty.",
                )
                result["next_question"] = (
                    "Use the saved parity lemma to test addition of 2 without rewriting its derivation."
                )
            elif role == "research_investigator" and cycle == 2:
                earlier = context["prior_artifacts"][0]
                first_artifact_id = earlier["id"]
                assert earlier["reasoning_steps"][0]["argument"].startswith("Consecutive integers")
                assert "addition of 2" in context["question"]
                result = investigator_step(
                    2,
                    "For every integer n, n(n+1)+2 is even.",
                    "The saved parity lemma covers n(n+1); adding the even integer 2 preserves parity.",
                    [first_artifact_id],
                )
            else:
                assert role == "research_skeptic" and cycle == 2
                assert first_artifact_id in context["context_artifact_ids"]
                assert context["prior_artifacts"][0]["reasoning_steps"][0]["argument"].startswith(
                    "Consecutive integers"
                )
                assert "complete argument to be rewritten" not in body["instructions"]
                result = skeptic_step(
                    2,
                    [first_artifact_id],
                    "The new +2 step cites the supplied earlier parity lemma; no full rewrite is needed. The project-wide classification remains open.",
                )
        elif phase == "later_session":
            if role == "research_investigator":
                prior = next(
                    item
                    for item in context["prior_session_findings"]
                    if item["id"] == first_artifact_id
                )
                assert prior["reasoning_steps"][0]["argument"].startswith("Consecutive integers")
                assert not prior["extract_truncated_fields"]
                result = investigator_step(
                    1,
                    "For every integer n, n(n+1)+4 is even.",
                    "The supplied saved lemma establishes the product parity; adding 4 preserves it.",
                    [first_artifact_id],
                )
            else:
                assert first_artifact_id in context["prior_session_artifact_ids"]
                result = skeptic_step(
                    1,
                    [first_artifact_id],
                    "The specifically cited prior-session parity lemma supports the local +4 delta; the larger project remains open.",
                )
        else:
            assert role == "research_investigator"
            assert first_artifact_id not in context["prior_session_artifact_ids"]
            assert first_artifact_id not in context["context_artifact_ids"]
            result = investigator_step(
                1,
                "Unrelated strategy falsely borrows parity proof.",
                "An unrelated source is claimed as support.",
                [first_artifact_id],
            )
        return httpx.Response(200, json=provider_response(result))

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
            str(path), strategy.id, str(uuid4()), view.project.id, credential["identity"]
        )
        first = await wait_for(path, started["id"])
        assert first["status"] == "ended" and len(first["artifacts"]) == 2
        first_bytes = (path / "research-sessions" / f"{first['id']}.json").read_bytes()
        assert first_artifact_id == first["artifacts"][0]["id"]
        assert (
            first_artifact_id in first["artifacts"][1]["reasoning_steps"][0]["basis_artifact_ids"]
        )
        limits = research_sessions.get_limits(str(path))
        limits.update(research_rounds=1, model_calls=2)
        research_sessions.save_limits(str(path), limits)
        phase = "later_session"
        started = await research_sessions.start_session(
            str(path), strategy.id, str(uuid4()), view.project.id, credential["identity"]
        )
        later = await wait_for(path, started["id"])
        assert later["status"] == "ended" and len(later["artifacts"]) == 1
        assert (
            first_artifact_id in later["artifacts"][0]["reasoning_steps"][0]["basis_artifact_ids"]
        )
        assert (path / "research-sessions" / f"{first['id']}.json").read_bytes() == first_bytes
        unrelated = create_strategy(
            path, "Unrelated geometry", "Investigate bounded polygon geometry, not parity."
        ).project.strategies[-1]
        phase = "foreign"
        started = await research_sessions.start_session(
            str(path), unrelated.id, str(uuid4()), view.project.id, credential["identity"]
        )
        foreign = await wait_for(path, started["id"])
        assert foreign["status"] == "failed" and not foreign["artifacts"]
        assert (
            "not supplied" in foreign["message"].lower() or "context" in foreign["message"].lower()
        )
        assert (path / "research-sessions" / f"{first['id']}.json").read_bytes() == first_bytes
    exported = export_project_view(str(path))
    assert len(exported["research_sessions"]) == 3
    return {
        "project_id": view.project.id,
        "first_session_id": first["id"],
        "later_session_id": later["id"],
        "foreign_session_id": foreign["id"],
        "first_artifact_id": first_artifact_id,
        "calls": sum(1 for item in capture if item["phase"] != "foreign"),
        "foreign_rejected_calls": sum(1 for item in capture if item["phase"] == "foreign"),
        "first_record_unchanged": True,
    }


def graph_investigator(cycle: int, source: str | None, prior_id: str | None = None) -> dict:
    value = investigation(cycle)
    value.update(
        claim="A bounded graph experiment is proposed; no result is known until execution is saved."
        if source
        else "OFFLINE SCRIPT ASSERTION: a graph computation supports the guard, despite no saved execution.",
        method="OFFLINE SCRIPT: compare immediate reverse-edge checking with actual acyclicity on a bounded graph.",
        reasoning_steps=[
            {
                "title": "Candidate graph test",
                "argument": "A previous failure is operational only; the next code changes to enumerate actual candidate insertions."
                if prior_id
                else "A proposed local graph test requires a saved execution before drawing an inference.",
                "epistemic_status": "conjecture",
                "basis_artifact_ids": [prior_id] if prior_id else [],
            }
        ],
        assumptions=[],
        evidence_status="Offline scripted role output; actual local execution, if any, is separate evidence.",
        open_obligations=[
            "Prove the arbitrary-size insertion condition and characterize update cost."
        ],
        python_code=source,
    )
    return value


def graph_skeptic(cycle: int, execution: dict | None, *, next_test: str) -> dict:
    value = skeptic_step(
        cycle,
        [],
        "The scripted review retains the exact execution scope and the unsolved general invariant.",
    )
    value.update(
        assessment="revise" if cycle == 1 else "continue",
        stop_reason="recoverable_objection",
        next_question=next_test,
        remaining_obligations=[next_test, "General proof and complexity remain open."],
        proof_obligations=["Prove the general insertion invariant and complexity."],
        unresolved_objections=["Finite checks cannot prove the arbitrary-size claim."],
    )
    if execution is None:
        value.update(
            response="OFFLINE SCRIPT ASSERTION: bounded computation supports the guard, but no execution is recorded.",
            solution_claim="Only a bounded computational observation supports the local candidate.",
            argument_summary="No execution is attached; the scripted assertion cannot be independently checked.",
            computation_feedback=None,
            computational_citations=[],
        )
        return value
    completed = execution["status"] == "completed"
    observed_field = "stdout" if completed else "stderr"
    value.update(
        response="OFFLINE SCRIPT interpreting actual saved output: "
        + execution.get(observed_field, ""),
        solution_claim="The local reverse-edge-only guard has a bounded counterexample; the general repaired rule is unproved."
        if completed
        else "The sandbox attempt failed operationally; no graph counterexample was observed yet.",
        argument_summary="Only the actual saved execution status and output are observed.",
        computation_feedback={
            "research_artifact_id": None,
            "execution_id": execution["id"],
            "observed_status": execution["status"],
            "observed_field": observed_field,
            "observed_text_sha256": hashlib.sha256(
                execution.get(observed_field, "").encode()
            ).hexdigest(),
            "reported_effect": "counterexample" if completed else "inconclusive",
            "next_test": next_test,
        },
        computational_citations=[
            {
                "research_artifact_id": None,
                "execution_id": execution["id"],
                "evidence": "output" if completed else "error",
                "filename": None,
                "use": "result" if completed else "limitation",
            }
        ],
    )
    return value


async def graph_project(path: Path, capture: list[dict], *, withheld: bool) -> dict:
    view = initialize_project(
        path,
        "DAG insertion control",
        "Does checking only for the immediate reverse edge keep a DAG acyclic after insertion? Find a bounded counterexample or report what remains unresolved.",
    )
    strategy = create_strategy(
        path,
        "Test the local guard",
        "Test a three-vertex witness, then investigate a reachability repair and proof duty.",
    ).project.strategies[0]
    credential = {
        "identity": "fixture-account",
        "mode": "api_key",
        "token": "fixture-token",
        "status": "connected",
    }
    config = {"available": True, "model": "gpt-6.1-sol", "reasoning_effort": "high"}
    limits = research_sessions.get_limits(str(path))
    limits.update(research_rounds=1 if withheld else 2, model_calls=2 if withheld else 4)
    research_sessions.save_limits(str(path), limits)
    phase = "initial"

    async def handler(request):
        body = json.loads(request.content)
        context = json.loads(body["input"])
        role = body["text"]["format"]["name"]
        capture.append(
            {
                "project": "graph-withheld" if withheld else "graph-present",
                "phase": phase,
                "role": role,
                "body": body,
            }
        )
        cycle = context["cycle"]
        if phase == "followup":
            assert cycle == 1
            prior = context["prior_session_findings"]
            witness = next(
                item
                for item in prior
                if isinstance(item.get("python_execution"), dict)
                and item["python_execution"].get("status") == "completed"
            )
            assert "witness" in witness["python_execution"]["stdout"]
            if role == "research_investigator":
                result = graph_investigator(1, None, witness["id"])
                result["claim"] = (
                    "The saved counterexample rejects the old guard; next investigate the reachability condition."
                )
                result["method"] = (
                    "OFFLINE SCRIPT: use the exact saved witness as a negative constraint; no new computation is claimed."
                )
            else:
                result = skeptic_step(
                    1,
                    [witness["id"]],
                    "The saved witness constrains the next test; a failed earlier run did not refute the guard.",
                )
                result["next_question"] = (
                    "Prove or falsify reachability from v to u as the insertion condition."
                )
            return httpx.Response(200, json=provider_response(result))
        if role == "research_investigator":
            if withheld:
                result = graph_investigator(1, None)
            elif cycle == 1:
                result = graph_investigator(1, ERROR)
            else:
                assert "Replace failing code" in context["question"]
                prior = context["prior_artifacts"][-1]
                assert prior["investigator_output"]["python_execution"]["status"] == "failed"
                result = graph_investigator(2, GRAPH_FIRST, prior["id"])
        else:
            execution = context.get("investigator_output", {}).get("python_execution")
            assert withheld == (execution is None)
            if withheld:
                result = graph_skeptic(
                    1, None, next_test="Run a bounded graph check before claiming evidence."
                )
            elif cycle == 1:
                assert execution["status"] == "failed"
                result = graph_skeptic(
                    1,
                    execution,
                    next_test="Replace failing code with a bounded three-vertex graph witness search.",
                )
            else:
                assert execution["status"] == "completed"
                assert json.loads(execution["stdout"])["witness"]
                result = graph_skeptic(
                    2,
                    execution,
                    next_test="Test the reachability guard and retain the general proof duty.",
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
            str(path), strategy.id, str(uuid4()), view.project.id, credential["identity"]
        )
        initial = await wait_for(path, started["id"])
        assert initial["status"] == "ended"
        assert len(initial["artifacts"]) == (1 if withheld else 2)
        initial_bytes = (path / "research-sessions" / f"{initial['id']}.json").read_bytes()
        if not withheld:
            first_execution = initial["artifacts"][0]["investigator_output"]["python_execution"]
            second_execution = initial["artifacts"][1]["investigator_output"]["python_execution"]
            assert (
                first_execution["status"] == "failed" and second_execution["status"] == "completed"
            )
            assert "witness" in second_execution["stdout"]
            limits = research_sessions.get_limits(str(path))
            limits.update(research_rounds=1, model_calls=2)
            research_sessions.save_limits(str(path), limits)
            phase = "followup"
            started = await research_sessions.start_session(
                str(path), strategy.id, str(uuid4()), view.project.id, credential["identity"]
            )
            followup = await wait_for(path, started["id"])
            assert followup["status"] == "ended" and len(followup["artifacts"]) == 1
            assert (
                path / "research-sessions" / f"{initial['id']}.json"
            ).read_bytes() == initial_bytes
    audit = export_project_view(str(path))
    session = audit["research_sessions"][0]
    if withheld:
        assert session["outcome"]["verification_label"] == "Incomplete"
        assert all(
            not artifact["investigator_output"].get("python_execution")
            for artifact in session["artifacts"]
        )
        assert "bounded computational observation" in session["outcome"]["conclusion"]
        assert any(
            "0 executions" in item["value"] for item in session["outcome"]["metrics"]["operational"]
        )
        report, _ = render_report(audit, "txt")
        assert "Only a bounded computational observation" in report
        assert "Python runs by status: 0 executions" in report
    else:
        assert len(audit["research_sessions"]) == 2
        assert any(
            "failed" in item["value"] and "completed" in item["value"]
            for item in session["outcome"]["metrics"]["operational"]
        )
        report, _ = render_report(audit, "txt")
        assert "reverse-edge-only guard has a bounded counterexample" in report
        assert "Python runs by status: 1 completed, 1 failed" in report
    state = current_understanding(str(path))
    assert state["findings"]
    assert all(finding["verification"] != "Verified" for finding in state["findings"])
    return {
        "project_id": view.project.id,
        "initial_session_id": initial["id"],
        "followup_session_id": followup["id"] if not withheld else None,
        "execution_ids": [
            artifact["investigator_output"]["python_execution"]["id"]
            for artifact in initial["artifacts"]
            if isinstance(artifact["investigator_output"].get("python_execution"), dict)
        ],
        "execution_statuses": [
            artifact["investigator_output"]["python_execution"]["status"]
            for artifact in initial["artifacts"]
            if isinstance(artifact["investigator_output"].get("python_execution"), dict)
        ],
        "current_finding_count": len(state["findings"]),
        "initial_record_unchanged": True,
    }


async def invalid_source_project(
    original: Path, path: Path, capture: list[dict], *, kind: str, source_artifact_id: str
) -> dict:
    """Taint one isolated saved source, then attempt closure through real dispatch."""
    shutil.copytree(original, path)
    source_session_id = None
    for file in (path / "research-sessions").glob("*.json"):
        if file.name in {"limits.json", "sequence.json"}:
            continue
        record = json.loads(file.read_text())
        record["project_path"] = str(path.resolve())
        for artifact in record.get("artifacts", []):
            if artifact["id"] == source_artifact_id:
                source_session_id = record["id"]
                if kind == "retracted":
                    artifact["retracted_by_artifact_ids"] = [str(uuid4())]
                else:
                    artifact["reasoning_steps"][0]["argument"] += (
                        " Supplementary unreviewed detail." * 70
                    )
        file.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n")
    assert source_session_id
    source_file = path / "research-sessions" / f"{source_session_id}.json"
    source_bytes = source_file.read_bytes()
    view = inspect_project(path)
    strategy = view.project.strategies[0]
    credential = {
        "identity": "fixture-account",
        "mode": "api_key",
        "token": "fixture-token",
        "status": "connected",
    }
    config = {"available": True, "model": "gpt-6.1-sol", "reasoning_effort": "high"}

    async def handler(request):
        body = json.loads(request.content)
        context = json.loads(body["input"])
        role = body["text"]["format"]["name"]
        capture.append({"project": f"parity-{kind}", "role": role, "body": body})
        if role == "research_investigator":
            assert source_artifact_id in context["prior_session_artifact_ids"]
            source = next(
                item
                for item in context["prior_session_findings"]
                if item["id"] == source_artifact_id
            )
            if kind == "retracted":
                assert source["retracted_by_artifact_ids"]
            else:
                assert "reasoning_steps" in source["extract_truncated_fields"]
            result = investigator_step(
                1,
                "A further bounded parity claim remains open.",
                "This current step does not independently close the saved obligation.",
                [],
            )
        else:
            obligation = next(
                item for item in context["obligation_ledger"] if item["status"] == "unresolved"
            )
            result = skeptic_step(
                1,
                [source_artifact_id],
                "OFFLINE ADVERSARIAL ROLE: claim that the tainted old source closes the obligation.",
            )
            result["obligation_reviews"] = [
                {
                    "obligation_id": obligation["obligation_id"],
                    "status": "addressed",
                    "basis_artifact_ids": [source_artifact_id],
                    "basis_step_ids": [],
                    "rationale": "The old source supposedly settles this obligation without a fresh derivation.",
                }
            ]
        return httpx.Response(200, json=provider_response(result))

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
            str(path), strategy.id, str(uuid4()), view.project.id, credential["identity"]
        )
        rejected = await wait_for(path, started["id"])
    assert rejected["status"] == "failed" and not rejected["artifacts"]
    assert "complete, unretracted" in rejected["message"], rejected["message"]
    assert source_file.read_bytes() == source_bytes
    audit = export_project_view(str(path))
    assert any(
        item["id"] == rejected["id"] and item["status"] == "failed"
        for item in audit["research_sessions"]
    )
    return {
        "project_id": view.project.id,
        "rejected_session_id": rejected["id"],
        "tainted_source_artifact_id": source_artifact_id,
        "kind": kind,
        "source_record_unchanged_after_rejected_call": True,
    }


async def main() -> None:
    with TemporaryDirectory(prefix="sigma-epistemic-continuity-") as temporary:
        root = Path(temporary)
        output = (
            Path(os.environ["SIGMA_CONTINUITY_EXPORT_DIR"]).resolve()
            if os.environ.get("SIGMA_CONTINUITY_EXPORT_DIR")
            else None
        )
        if output:
            output.mkdir(parents=True, exist_ok=True)
        capture: list[dict] = []
        parity = await parity_project(root / "parity.sigma", capture)
        retracted = await invalid_source_project(
            root / "parity.sigma",
            root / "parity-retracted.sigma",
            capture,
            kind="retracted",
            source_artifact_id=parity["first_artifact_id"],
        )
        truncated = await invalid_source_project(
            root / "parity.sigma",
            root / "parity-truncated.sigma",
            capture,
            kind="truncated",
            source_artifact_id=parity["first_artifact_id"],
        )
        present = await graph_project(root / "graph-present.sigma", capture, withheld=False)
        withheld = await graph_project(root / "graph-withheld.sigma", capture, withheld=True)
        if output:
            manifest = {
                "transport": "offline scripted provider; normal SIGMA session dispatch and persistence; graph-present uses actual local Docker Python",
                "live_provider_calls": 0,
                "actual_provider_cost_usd": 0,
                "projects": [
                    export(root / "parity.sigma", output, "parity"),
                    export(root / "parity-retracted.sigma", output, "parity-retracted"),
                    export(root / "parity-truncated.sigma", output, "parity-truncated"),
                    export(root / "graph-present.sigma", output, "graph-present"),
                    export(root / "graph-withheld.sigma", output, "graph-withheld"),
                ],
                "observations": {
                    "parity": parity,
                    "parity_retracted": retracted,
                    "parity_truncated": truncated,
                    "graph_present": present,
                    "graph_withheld": withheld,
                },
                "captured_provider_requests": "provider-requests.jsonl",
                "synthetic_controls": [
                    "parity-retracted: source artifact is a deliberately marked isolated copy",
                    "parity-truncated: source reasoning argument was lengthened only in an isolated copy",
                ],
            }
            (output / "provider-requests.jsonl").write_text(
                "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in capture)
            )
            (output / "MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n")
        print(
            "PASS persisted parity step A → cycle step B → later session; exact source IDs, unchanged origin, foreign rejection"
        )
        print("PASS retracted and truncated source closures rejected through real Skeptic dispatch")
        print(
            "PASS graph real failed/completed execution, saved witness follow-up, withheld prose contradiction"
        )
        print(
            json.dumps(
                {
                    "parity": parity,
                    "parity_retracted": retracted,
                    "parity_truncated": truncated,
                    "graph_present": present,
                    "graph_withheld": withheld,
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    asyncio.run(main())
