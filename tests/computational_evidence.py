"""Safe computational artifact previews and cross-session citation provenance."""

import asyncio
import hashlib
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from uuid import uuid4

import httpx
from PIL import Image, ImageDraw
from research_sessions import (
    execution_tool_fixture,
    investigation,
    provider_response,
    setup,
    skeptic,
    wait_for,
)
from sage_execution import provider_stack

from sigma import computational_evidence, python_sandbox, research_sessions
from sigma.projects import ProjectError

SOURCE = "import numpy as np\nprint('slope=', np.polyfit([0, 1, 2], [1, 3, 5], 1)[0])"


def png_plot(width=640, height=360):
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((24, 18, width - 20, height - 25), outline="black", width=3)
    draw.line((28, height - 40, width // 2, height // 2, width - 25, 24), fill="black", width=5)
    target = io.BytesIO()
    image.save(target, format="PNG")
    return target.getvalue()


def test_preview_bounds_and_formats():
    plot = computational_evidence.inspect_artifact_bytes("plot.png", "image/png", png_plot())
    assert plot["status"] == "available" and plot["format"] == "png"
    assert "64×20 grayscale rendering" in plot["notice"]
    assert len(plot["representation"]) <= computational_evidence.MAX_PREVIEW_CHARS
    assert sum(character not in " \n" for character in plot["representation"]) > 100
    assert "axis labels" in plot["notice"]

    text = computational_evidence.inspect_artifact_bytes(
        "values.csv", "text/csv", b"x,y\n0,1\n1,3\n\x00instruction"
    )
    assert text["status"] == "available" and "\\u0000" in text["representation"]
    assert "Untrusted artifact text" in text["notice"]
    long_text = computational_evidence.inspect_artifact_bytes(
        "large.txt", "text/plain", b"z" * (computational_evidence.MAX_PREVIEW_CHARS + 50)
    )
    assert long_text["truncated"] is True
    assert long_text["representation"].endswith("[truncated; inspect the original saved artifact]")

    corrupt = computational_evidence.inspect_artifact_bytes(
        "broken.png", "image/png", b"\x89PNGbroken"
    )
    assert corrupt["status"] == "corrupt" and "no visual preview" in corrupt["notice"]
    oversized_pixels = computational_evidence.inspect_artifact_bytes(
        "large.png", "image/png", png_plot(2500, 900)
    )
    assert oversized_pixels["status"] == "oversized"
    oversized_bytes = computational_evidence.inspect_artifact_bytes(
        "big.csv", "text/csv", b"x" * (computational_evidence.MAX_ARTIFACT_BYTES + 1)
    )
    assert oversized_bytes["status"] == "oversized"
    unsupported = computational_evidence.inspect_artifact_bytes(
        "proof.pdf", "application/pdf", b"%PDF-1.7\nopaque"
    )
    assert unsupported["status"] == "unsupported" and "application/pdf" in unsupported["notice"]


def test_runtime_execution_status_metrics():
    python_done = {
        "id": "python-done",
        "status": "completed",
        "runtime": "python",
        "artifacts": [{"filename": "result.csv", "size_bytes": 100, "sha256": "same-python-file"}],
    }
    python_timeout = {"id": "python-timeout", "status": "timeout", "runtime": "python"}
    python_failed = {"id": "python-failed", "status": "failed", "runtime": "python"}
    sage_completed = {"id": "sage-completed", "status": "completed", "runtime": "sagemath"}
    sage_failed = {
        "id": "sage-failed",
        "status": "failed",
        "runtime": "sagemath",
        "artifacts": [{"filename": "debug.bin", "size_bytes": 250, "sha256": "sage-file"}],
    }
    sage_cancelled = {"id": "sage-cancelled", "status": "cancelled", "runtime": "sagemath"}
    sage_other = {"id": "sage-other", "status": "queued", "runtime": "sagemath"}
    record = {
        "id": "metrics",
        "mode": "chatgpt",
        "calls_used": 0,
        "steps": [
            {"id": "p1", "output": {"python_execution": python_done}},
            {"id": "p2", "output": {"python_execution": python_timeout}},
            {"id": "p4", "output": {"python_execution": python_failed}},
            {"id": "p3", "output": {"python_execution": {"status": "future_status"}}},
            {"id": "s1", "output": {"sage_execution": sage_failed}},
            {"id": "s2", "output": {"sage_execution": sage_cancelled}},
            {"id": "s3", "output": {"sage_execution": sage_other}},
            {"id": "s4", "output": {"sage_execution": sage_failed}},
            {"id": "s5", "output": {"sage_execution": sage_completed}},
        ],
        "artifacts": [
            {"id": "a1", "investigator_output": {"python_execution": python_done}},
            {"id": "a2", "investigator_output": {"sage_execution": sage_failed}},
        ],
    }
    metrics = research_sessions._outcome_metrics(
        record, {"assessment": "pending", "label": "Pending", "solution_review": None}
    )
    operational = {item["label"]: item["value"] for item in metrics["operational"]}
    assert operational["Python runs by status"] == (
        "1 completed, 1 failed, 1 timeout · — (execution record without ID)"
    )
    assert operational["SageMath runs by status"] == (
        "1 cancelled · 1 completed · 1 failed · 1 queued"
    )
    assert "2 computation file(s) (350 B)" in operational["Artifacts and storage"]
    assert metrics["sources"]["execution_ids"] == [
        "python-done",
        "python-failed",
        "python-timeout",
        "sage-cancelled",
        "sage-completed",
        "sage-failed",
        "sage-other",
    ]
    proposal_only = research_sessions._outcome_metrics(
        {
            "id": "proposal",
            "mode": "chatgpt",
            "calls_used": 0,
            "steps": [{"id": "proposal-step", "output": {"sage_code": "print(2^3)"}}],
            "artifacts": [],
        },
        {"assessment": "pending", "label": "Pending", "solution_review": None},
    )
    proposal_metrics = {item["label"]: item["value"] for item in proposal_only["operational"]}
    assert proposal_metrics["SageMath runs by status"] == (
        "0 executions (SageMath proposal saved; execution not recorded)"
    )


async def test_cross_session_computation_reuse(path: Path, runtime_name: str = "python"):
    view, strategy, credential, config = await setup(path)
    source = (
        SOURCE
        if runtime_name == "python"
        else "R.<x> = PolynomialRing(QQ)\nprint(factor((x - 1) * (x + 1)))"
    )
    code_field = "python_code" if runtime_name == "python" else "sage_code"
    result_field = "python_execution" if runtime_name == "python" else "sage_execution"
    old_session_id, old_step_id, old_artifact_id = map(str, (uuid4(), uuid4(), uuid4()))
    source_step = {
        "id": old_step_id,
        "cycle": 1,
        "role": "investigator",
        "strategy_id": strategy.id,
        "status": "completed",
        "output": {**investigation(1), code_field: source},
    }
    old_session = {
        "id": old_session_id,
        "project_path": str(path.resolve()),
        "project_id": view.project.id,
        "session_number": 1,
        "strategy_id": strategy.id,
        "strategy_title": strategy.title,
        "strategy_text": strategy.approach,
        "status": "ended",
        "created_at": research_sessions._now(),
        "updated_at": research_sessions._now(),
        "steps": [source_step],
        "strategy_runs": [{"strategy_id": strategy.id, "cycle": 1}],
        "artifacts": [],
        "events": [],
    }
    research_sessions._save(str(path), old_session)
    png = png_plot()
    result = python_sandbox.ExecutionResult(
        "completed",
        0,
        "slope=2.0\n" if runtime_name == "python" else "(x - 1) * (x + 1)\n",
        "",
        13,
        "sha256:" + "a" * 64,
        (("plot.png", "image/png", png), ("values.csv", "text/csv", b"x,y\n0,1\n1,3\n2,5\n")),
    )
    with patch.object(python_sandbox, "execute", return_value=result):
        execution = await python_sandbox.execute_research_code(
            path,
            source,
            session_id=old_session_id,
            strategy_id=strategy.id,
            cycle=1,
            step_id=old_step_id,
            runtime_name=runtime_name,
        )
    old_artifact = {
        "id": old_artifact_id,
        "sequence": 1,
        "strategy_id": strategy.id,
        "claim_or_question": "A linear synthetic dataset has slope two.",
        "method": "Fit a line to three deterministic points and inspect the plotted line.",
        "assumptions": ["The values are generated from a linear relationship."],
        "evidence_status": "Finite synthetic calculation; unverified.",
        "objections": ["This does not establish behavior outside the sampled points."],
        "open_obligations": ["Check input provenance and more general data."],
        "investigator_output": {
            **investigation(1),
            code_field: source,
            result_field: execution,
        },
        "skeptic_output": skeptic(1),
    }
    old_session["artifacts"] = [old_artifact]
    old_session["steps"][0]["output"] = old_artifact["investigator_output"]
    research_sessions._save(str(path), old_session)
    prior_bytes = (research_sessions._directory(str(path)) / f"{old_session_id}.json").read_bytes()

    limits = research_sessions.get_limits(str(path))
    limits["research_rounds"] = 1
    research_sessions.save_limits(str(path), limits)
    tools = execution_tool_fixture(True)
    if runtime_name == "sagemath":
        tools[1]["available"] = True
    observed = []
    citation = {
        "research_artifact_id": old_artifact_id,
        "execution_id": execution["id"],
        "evidence": "artifact",
        "filename": "plot.png",
        "use": "result",
    }

    async def handler(request):
        payload = json.loads(request.content)
        role = payload["text"]["format"]["name"]
        context = json.loads(payload["input"])
        finding = next(
            item for item in context["prior_session_findings"] if item["id"] == old_artifact_id
        )
        saved_execution = finding[result_field]
        assert saved_execution["id"] == execution["id"]
        assert saved_execution["status"] == "completed"
        assert saved_execution["source"] == source
        assert saved_execution["stdout"] == (
            "slope=2.0\n" if runtime_name == "python" else "(x - 1) * (x + 1)\n"
        )
        assert saved_execution["session_id"] == old_session_id
        assert saved_execution["agent"]["step_id"] == old_step_id
        plot_evidence = next(
            item
            for item in saved_execution["artifact_inspections"]
            if item["filename"] == "plot.png"
        )
        assert plot_evidence["sha256"] == hashlib.sha256(png).hexdigest()
        assert plot_evidence["inspection"]["status"] == "available"
        assert len(plot_evidence["inspection"]["representation"]) < 1400
        assert (
            next(
                item
                for item in saved_execution["artifact_inspections"]
                if item["filename"] == "values.csv"
            )["inspection"]["representation"]
            == "x,y\n0,1\n1,3\n2,5\n"
        )
        observed.append((role, context))
        if role == "research_investigator":
            assert "Reused evidence retains its original" in payload["instructions"]
            output = {
                **investigation(1),
                "claim": "The saved synthetic data fit has slope two.",
                "method": f"Synthesizing earlier computation {execution['id']}; no new run is claimed.",
                "evidence_status": "The cited prior finite computation completed; generality remains unverified.",
                "computational_citations": [citation],
            }
        else:
            assert context["investigator_output"]["computational_citations"] == [citation]
            assert context["investigator_output"]["method"].find("no new run") >= 0
            output = {
                **skeptic(1, "stop", "productive_conclusion"),
                "response": "The citation points to the completed prior run; it only tests its three synthetic points.",
                "computational_citations": [citation],
            }
        return httpx.Response(200, json=provider_response(output))

    with provider_stack(credential, config, handler, tools):
        started = await research_sessions.start_session(
            str(path), strategy.id, str(uuid4()), view.project.id, credential["identity"]
        )
        finished = await wait_for(path, started["id"])

    assert [role for role, _ in observed] == ["research_investigator", "research_skeptic"]
    assert finished["calls_used"] == 2
    assert all(
        step["output"]["computational_citations"] == [citation] for step in finished["steps"]
    )
    assert finished["artifacts"][0]["investigator_output"]["computational_citations"] == [citation]
    assert finished["steps"][0]["computation_inspections"]
    assert any(
        item["research_artifact_id"] == old_artifact_id
        and item["execution_id"] == execution["id"]
        and item["filename"] == "plot.png"
        for item in finished["steps"][0]["computation_inspections"]
    )
    assert all(
        item.get("session_id") != started["id"] for item in python_sandbox.list_executions(path)
    )
    assert (
        research_sessions._directory(str(path)) / f"{old_session_id}.json"
    ).read_bytes() == prior_bytes

    artifact_path = (
        python_sandbox._execution_directory(path) / f"{execution['id']}.artifacts" / "plot.png"
    )
    artifact_path.write_bytes(b"changed after capture")
    damaged = computational_evidence.inspect_execution_artifacts(path, execution, old_artifact_id)
    assert damaged[0]["inspection"]["status"] == "unavailable"
    try:
        python_sandbox.get_execution_artifact(path, execution["id"], "plot.png")
    except ProjectError:
        pass
    else:
        raise AssertionError("Modified captured artifact passed the existing integrity check")


async def test_failed_cross_session_evidence_is_only_a_limitation(path: Path):
    view, strategy, _, _ = await setup(path)
    session_id, step_id, artifact_id = map(str, (uuid4(), uuid4(), uuid4()))
    source = "raise ValueError('singular denominator')"
    investigator = {**investigation(1), "sage_code": source}
    session = {
        "id": session_id,
        "project_path": str(path.resolve()),
        "project_id": view.project.id,
        "session_number": 1,
        "strategy_id": strategy.id,
        "strategy_title": strategy.title,
        "strategy_text": strategy.approach,
        "status": "ended",
        "created_at": research_sessions._now(),
        "updated_at": research_sessions._now(),
        "steps": [
            {
                "id": step_id,
                "cycle": 1,
                "role": "investigator",
                "strategy_id": strategy.id,
                "status": "completed",
                "output": investigator,
            }
        ],
        "strategy_runs": [{"strategy_id": strategy.id, "cycle": 1}],
        "artifacts": [],
        "events": [],
    }
    research_sessions._save(str(path), session)
    failed_result = python_sandbox.ExecutionResult(
        "failed", 1, "", "ValueError: singular denominator", 7, "sha256:" + "c" * 64
    )
    with patch.object(python_sandbox, "execute", return_value=failed_result):
        execution = await python_sandbox.execute_research_code(
            path,
            source,
            session_id=session_id,
            strategy_id=strategy.id,
            cycle=1,
            runtime_name="sagemath",
            step_id=step_id,
        )
    artifact = {
        "id": artifact_id,
        "sequence": 1,
        "strategy_id": strategy.id,
        "claim_or_question": "The symbolic computation did not produce a result.",
        "method": "Attempt exact Sage evaluation and diagnose its failure.",
        "assumptions": [],
        "evidence_status": "Execution failed; this is not evidence against the mathematical claim.",
        "objections": [],
        "open_obligations": ["Change the singular input before retrying."],
        "investigator_output": {
            **investigator,
            "sage_execution": execution,
        },
        "skeptic_output": skeptic(1),
    }
    session["steps"][0]["output"] = artifact["investigator_output"]
    session["artifacts"] = [artifact]
    research_sessions._save(str(path), session)
    findings = research_sessions._prior_session_findings(str(path), str(uuid4()))
    finding = next(item for item in findings if item["id"] == artifact_id)
    evidence = finding["sage_execution"]
    assert evidence["status"] == "failed"
    assert evidence["source"] == source
    assert evidence["stderr"] == "ValueError: singular denominator"
    assert evidence["session_id"] == session_id and evidence["agent"]["step_id"] == step_id
    assert "not evidence against" in finding["evidence_status"]
    assert evidence["artifact_inspections"] == []
    unsupported_result_citation = {
        "research_artifact_id": artifact_id,
        "execution_id": execution["id"],
        "evidence": "error",
        "filename": None,
        "use": "result",
    }
    try:
        research_sessions._validate_computation_citations(
            {"prior_session_findings": findings}, [unsupported_result_citation]
        )
    except ProjectError as exc:
        assert "failed computation" in str(exc)
    else:
        raise AssertionError("A failed prior computation was accepted as a result citation")
    limitation_citation = {**unsupported_result_citation, "use": "limitation"}
    research_sessions._validate_computation_citations(
        {"prior_session_findings": findings}, [limitation_citation]
    )


def main():
    test_preview_bounds_and_formats()
    test_runtime_execution_status_metrics()
    with TemporaryDirectory() as temporary:
        asyncio.run(test_cross_session_computation_reuse(Path(temporary) / "t28-python.sigma"))
        asyncio.run(
            test_cross_session_computation_reuse(Path(temporary) / "t28-sage.sigma", "sagemath")
        )
        asyncio.run(
            test_failed_cross_session_evidence_is_only_a_limitation(
                Path(temporary) / "t28-failed.sigma"
            )
        )
    print("Computational evidence previews and cross-session citation scenarios passed.")


if __name__ == "__main__":
    main()
