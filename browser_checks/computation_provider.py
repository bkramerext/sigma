"""Scripted HTTP provider only. Python/Sage execution is never patched/mocked."""

import hashlib
import importlib.util
import json
import os
from pathlib import Path

import httpx

from browser_checks.computation_programs import (
    ERROR,
    GRAPH_FIRST,
    GRAPH_NEXT,
    RESTART,
    SAGE,
    SUBSET_FIRST,
    SUBSET_NEXT,
    TIMEOUT,
)

spec = importlib.util.spec_from_file_location(
    "research_helpers", Path(__file__).resolve().parents[1] / "tests/research_sessions.py"
)
helpers = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helpers)


def observed(context):
    pending = context.get("investigator_output")
    candidates = []
    if isinstance(pending, dict):
        for field in ["python_execution", "sage_execution"]:
            if isinstance(pending.get(field), dict):
                candidates.append((None, pending[field]))
    for artifact in reversed(context.get("prior_artifacts", [])):
        for field in ["python_execution", "sage_execution"]:
            execution = artifact.get("investigator_output", {}).get(field)
            if isinstance(execution, dict):
                candidates.append((artifact["id"], execution))
    return candidates[0] if candidates else (None, None)


def select(execution, scenario):
    if execution is None:
        return (
            "No session computation was observed. Run the bounded candidate check before claiming a counterexample or choosing a repaired invariant.",
            "inconclusive",
            None,
        )
    if execution["status"] != "completed":
        return (
            f"The actual run is {execution['status']}; it establishes no mathematical disproof. Diagnose the recorded execution failure, then propose changed bounded code before testing the local candidate.",
            "inconclusive",
            None,
        )
    try:
        result = json.loads(execution["stdout"])
    except (ValueError, TypeError):
        return (
            "The completed run has no parseable observation. Inspect its source/output before drawing a mathematical inference.",
            "inconclusive",
            None,
        )
    if result.get("witness"):
        witness = json.dumps(result["witness"], sort_keys=True)
        question = (
            f"Observed counterexample {witness}. Separate the six-step residuals by n modulo 3, then identify the missing phase/boundary obligation; do not infer the global recurrence or limit."
            if scenario == "subset"
            else f"Observed counterexample {witness}. Replace immediate reverse-edge checking by a reachability test and compare it with recomputation on all four-vertex DAG insertions; retain the invariant/complexity proof duty."
        )
        return question, "counterexample", result
    return (
        "Finite agreement only. Prove the scoped invariant/phase identity, cover update/boundary semantics, and state what remains unknown about the full problem.",
        "bounded_support",
        result,
    )


async def handler(request):
    if request.method == "GET":
        return httpx.Response(200, json={"object": "list", "data": [{"id": "gpt-6.1-sol"}]})
    body = json.loads(request.content)
    context = json.loads(body["input"])
    role = body["text"]["format"]["name"].removeprefix("research_")
    cycle = context["cycle"]
    cases = json.loads(Path(os.environ["SIGMA_COMPUTATION_CASES"]).read_text())
    case = cases[context["strategy"]["id"]]
    scenario = case["scenario"]
    mode = case["mode"]
    artifact_id, execution = observed(context)
    next_test, effect, _result = select(execution, scenario)
    citations = []
    if execution:
        citations = [
            {
                "research_artifact_id": artifact_id,
                "execution_id": execution["id"],
                "evidence": "output"
                if execution.get("stdout") and execution["status"] == "completed"
                else "error",
                "filename": None,
                "use": "result"
                if execution["status"] == "completed" and execution.get("stdout")
                else "limitation",
            }
        ]
    if role == "investigator":
        output = helpers.investigation(cycle)
        source = None
        if mode != "withheld":
            if cycle == 1:
                source = {"error": ERROR, "timeout": TIMEOUT, "restart": RESTART, "sage": SAGE}.get(
                    mode, SUBSET_FIRST if scenario == "subset" else GRAPH_FIRST
                )
            elif mode == "restart":
                source = (
                    SUBSET_FIRST
                    + "\n# changed source after interrupted reservation; bounded retry is explicit\n"
                )
            elif mode not in {"error", "timeout", "sage"} and effect == "counterexample":
                source = SUBSET_NEXT if scenario == "subset" else GRAPH_NEXT
        output.update(
            claim="Bounded computational test proposed; its outcome is not known until the sandbox returns."
            if source
            else "No new program proposed; the recorded execution and unresolved duties constrain this step.",
            method="Evaluator-authored offline code proposal/feedback control. No precomputed result supplied.",
            reasoning_steps=[
                {
                    "title": "Finite experiment, not a theorem",
                    "argument": "Execute the stated bounded candidate test; use only the actual saved observation to revise the next question.",
                    "epistemic_status": "assumption",
                    "basis_artifact_ids": [],
                }
            ],
            claim_is_conditional=True,
            assumptions=["Finite tests do not prove the full project claim"],
            evidence_status="Offline scripted provider proposes code; actual runtime execution is separate evidence.",
            open_obligations=[
                "Validate the local candidate against actual execution, then retain the general proof/complexity duty."
            ],
            python_code=source if mode != "sage" else None,
            sage_code=source if mode == "sage" else None,
            computational_citations=citations,
        )
    else:
        output = helpers.skeptic(
            cycle,
            assessment="revise"
            if cycle == 1 and mode not in {"error", "timeout", "sage"}
            else "stop",
            stop_reason="recoverable_objection" if cycle == 1 else "no_progress",
        )
        response = (
            "No session computation was observed; no local failure is established."
            if execution is None
            else (
                "Actual sandbox output: " + execution["stdout"]
                if execution["status"] == "completed"
                else f"Actual sandbox status {execution['status']}; no mathematical disproof follows. "
                + execution.get("stderr", "")
            )
        )
        output.update(
            response="OFFLINE SCRIPT interpreting actual execution: " + response,
            objections=["A finite computation does not settle the general research question."],
            remaining_obligations=[next_test],
            next_question=next_test if output["assessment"] == "revise" else "",
            objective_status="partial",
            solution_claim="Only the bounded computational observation is supported; the general project remains unresolved.",
            argument_summary=response,
            reasoning_assessments=[],
            claim_is_conditional=True,
            assumptions_reviewed=["The script and finite domain must be independently checked"],
            proof_obligations=[
                "Prove the scoped invariant or matrix identity and boundaries; retain broader complexity/asymptotic questions."
            ],
            unresolved_objections=["No general proof supplied."],
            verification_status="incomplete",
            strategy_contribution="productive",
            contribution_rationale="Real bounded runtime evidence informs a scripted next-test choice; autonomous research judgment is untested.",
            computational_citations=citations,
        )
        output["computation_feedback"] = None
        if execution:
            field = (
                "stdout"
                if execution.get("stdout") and execution["status"] == "completed"
                else "stderr"
            )
            output["computation_feedback"] = {
                "research_artifact_id": artifact_id,
                "execution_id": execution["id"],
                "observed_status": execution["status"],
                "observed_field": field,
                "observed_text_sha256": hashlib.sha256(
                    execution.get(field, "").encode()
                ).hexdigest(),
                "reported_effect": effect,
                "next_test": next_test,
            }
    if mode == "invalid_feedback" and role == "skeptic" and output.get("computation_feedback"):
        output["computation_feedback"]["observed_text_sha256"] = "0" * 64
    packet = context.get("approved_continuation", {})
    output["continuation_reviews"] = [
        {
            "artifact_id": row["artifact_id"],
            "uptake": "considered",
            "treatment": "negative_constraint"
            if row["artifact"].get("skeptic_output", {}).get("stop_reason")
            == "decisive_counterexample"
            else "unverified_input",
            "rationale": "Retain inherited scope and recorded negative evidence; this experiment tests a different bounded local claim.",
            "next_test": next_test,
        }
        for row in packet.get("sources", [])
    ]
    entry = {
        "role": role,
        "cycle": cycle,
        "case": case,
        "request_body": body,
        "response": output,
        "observed_execution_id": execution["id"] if execution else None,
        "selected_followup": next_test,
        "transport": "offline HTTP script; real Docker runtime is unpatched",
    }
    with Path(os.environ["SIGMA_COMPUTATION_CAPTURE"]).open("a") as stream:  # noqa: ASYNC230 - bounded offline ledger
        stream.write(json.dumps(entry) + "\n")
    return httpx.Response(200, json=helpers.provider_response(output))


RealClient = httpx.AsyncClient


class OfflineClient(RealClient):
    def __init__(self, *args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        super().__init__(*args, **kwargs)


httpx.AsyncClient = OfflineClient
from sigma.api import app

__all__ = ["app"]
