"""Bounded paper evidence validation, rendering safety and durable version scenarios."""

from __future__ import annotations

import asyncio
import copy
import json
import shutil
import threading
import unicodedata
from contextlib import nullcontext
from dataclasses import asdict
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter
from typing import Any, cast
from unittest.mock import patch

import httpx
import pypdfium2

from sigma import papers
from sigma.api import app
from sigma.plan_stream import completed, failure
from sigma.projects import ProjectError, initialize_project, inspect_project, read_project_artifact


def mock_pdf_inspection():
    """Fixture control-flow tests use sentinel PDF bytes, not validated PDFs."""
    return patch.object(papers, "_pdf_text_bounds_diagnostics", return_value=(1, []))


def draft(ref: str = "project:pid") -> papers.PaperDraft:
    return papers.PaperDraft.model_validate(
        {
            "title": "An evidence-bound exploratory note",
            "abstract": "This paper describes an exploratory record and its limitations. No formal result is asserted beyond the saved evidence.",
            "abstract_claim_ids": ["C1"],
            "problem_framing": ["The question is bounded by the saved project objective."],
            "problem_framing_claim_ids": ["C1"],
            "methods": ["We reviewed the saved sessions and their durable artifacts."],
            "methods_claim_ids": ["C1"],
            "claims": [
                {
                    "id": "C1",
                    "statement": "The saved project contains a research objective.",
                    "status": "established",
                    "evidence_refs": [ref],
                    "reasoning": "The objective is explicitly present in the project snapshot.",
                }
            ],
            "sections": [
                {
                    "heading": "Evidence reviewed",
                    "paragraphs": ["The complete snapshot was retained."],
                    "claim_ids": ["C1"],
                },
                {
                    "heading": "Interpretation",
                    "paragraphs": [r"The formula is $R(n)=1+\frac{n(n+1)}{2}$."],
                    "claim_ids": ["C1"],
                },
            ],
            "limitations": ["This paper does not establish a formal proof."],
            "open_obligations": ["A human should review the argument."],
            "conclusions": ["Only claims tied to the recorded snapshot are presented."],
            "conclusion_claim_ids": ["C1"],
            "validation_warnings": ["No external references were supplied."],
        }
    )


def fast_package(section_count: int = 2) -> tuple[dict[str, Any], papers.FastLongPaperPlan]:
    project_ref = "project:fast-fixture"
    session_ref = "session:onp-fixture"
    package = {
        "schema": "sigma-paper-evidence-v2",
        "project_id": "fast-fixture",
        "sources": [
            {
                "id": project_ref,
                "kind": "project",
                "data": {
                    "title": "A saved mathematical investigation",
                    "problem": "Assess the recorded candidate proof and its assumptions.",
                    "investigation_type": "mathematical",
                    "difficulty": "hard",
                },
            },
            {
                "id": session_ref,
                "kind": "session",
                "data": {
                    "reasoning_steps": [
                        "For n=0 the empty arrangement has one region. At step k, the new line has at most k-1 distinct crossings, hence at most k pieces.",
                        "The family L_j:y=jx+j^2 has pairwise distinct intersections along L_k, giving k pieces at every insertion.",
                    ],
                    "skeptic_objections": [
                        "The source argues that separated pieces lie in different old cells; this bridge still needs a formal check."
                    ],
                    "negative_findings": [
                        "No independent proof checker was run.",
                        "No effect.",
                    ],
                    "contradictory_findings": [
                        "The investigator calls the argument complete, while the skeptic records an unresolved convexity obligation."
                    ],
                    "proof_obligations": [
                        "Prove every arrangement cell is convex and every crossed cell splits into two cells."
                    ],
                    "results": {"computed_base_case_n0": 1},
                },
            },
        ],
    }
    plan = papers.FastLongPaperPlan(
        title="A Saved Candidate Argument and Its Verification Gaps",
        abstract=(
            "This paper reconstructs a mathematical candidate from saved evidence, "
            "including its base case, per-step bound, proposed construction, and "
            "unresolved verification obligations. It does not claim formal proof."
        ),
        abstract_claim_ids=["C1"],
        problem_framing=[
            "The project asks for an evidence-bound assessment of the saved argument."
        ],
        problem_framing_claim_ids=["C1"],
        methods=["We inspect the preserved mathematical reasoning and skeptical records."],
        methods_claim_ids=["C1"],
        claims=[
            papers.PaperClaim(
                id="C1",
                statement="The frozen record contains an unverified candidate argument.",
                status="unresolved",
                evidence_refs=[project_ref, session_ref],
                reasoning="The cited project and session records identify the claim and its open checks.",
            )
        ],
        sections=[
            papers.LongSectionPlan(
                heading=f"Evidence stage {index}",
                purpose="Explain the source-linked argument and the supporting or limiting evidence.",
                evidence_refs=[project_ref, session_ref],
                claim_ids=["C1"],
            )
            for index in range(1, section_count + 1)
        ],
        limitations=["The saved argument has not been independently verified."],
        open_obligations=[
            "Prove every arrangement cell is convex and every crossed cell splits into two cells."
        ],
        conclusions=["The evidence supports an unverified candidate, not a certified theorem."],
        conclusion_claim_ids=["C1"],
        validation_warnings=["No independent proof checker was run."],
    )
    return package, plan


def test_structured_evidence_short_tail_does_not_crash() -> None:
    """Two fragments with a short tail must merge without IndexError.

    Tadpoles exposed an augmented assignment that popped the last fragment
    before indexing [-2]; this case is deterministic and provider-free.
    """
    field = "reasoning_steps"
    fragment_width = papers.FAST_NOTE_TEXT_LENGTH - min(len(field), 55) - 3
    research = "x" * (fragment_width + 5)
    package = {
        "sources": [
            {
                "id": "session:tadpoles-fixture",
                "kind": "session",
                "data": {field: research},
            }
        ]
    }
    notes, omitted = papers._structured_evidence_index(package)
    assert len(notes) == 1
    assert notes[0].evidence_refs == ["session:tadpoles-fixture"]
    assert research in notes[0].statement
    assert omitted == []


def test_unexpected_paper_exception_yields_sanitized_sse_error() -> None:
    """An unexpected crash must not terminate HTTP 200 without an SSE error."""

    async def check() -> None:
        with TemporaryDirectory() as temporary:
            path = Path(temporary) / "paper-error.sigma"
            view = initialize_project(path, "Paper error test", "Verify SSE error recovery")

            async def crash(*_args, **_kwargs):
                raise IndexError("secret saved research must not be exposed")

            with patch.object(papers, "generate", new=crash):
                async with httpx.AsyncClient(
                    transport=httpx.ASGITransport(app=app),
                    base_url="http://testserver",
                ) as client:
                    response = await client.post(
                        "/api/projects/papers",
                        json={
                            "path": str(path),
                            "expected_project_id": view.project.id,
                            "expected_binding": "chatgpt:fixture",
                            "expected_snapshot_sha256": "a" * 64,
                        },
                    )
            assert response.status_code == 200
            assert '"type": "error"' in response.text
            assert "unexpected paper-generation error" in response.text
            assert "secret saved research" not in response.text

    asyncio.run(check())


def test_incomplete_chatgpt_paper_stream_is_rejected() -> None:
    events = [
        {"type": "response.created", "sequence_number": 0, "response": {"id": "resp-paper"}},
        {"type": "response.output_text.delta", "sequence_number": 1, "delta": "partial JSON"},
    ]
    stream = "".join("data: " + json.dumps(event) + "\n\n" for event in events)

    async def handler(_request):
        return httpx.Response(200, headers={"content-type": "text/event-stream"}, content=stream)

    real_client = httpx.AsyncClient
    with patch(
        "sigma.papers.httpx.AsyncClient",
        side_effect=lambda **kwargs: real_client(transport=httpx.MockTransport(handler), **kwargs),
    ):
        try:
            asyncio.run(
                papers._provider(
                    {"sources": []},
                    {"mode": "chatgpt", "token": "fixture"},
                    {"model": "gpt-6.1-sol", "reasoning_effort": "high"},
                )
            )
        except ProjectError as exc:
            assert "without a valid response.completed" in str(exc)
        else:
            raise AssertionError("Partial provider streams must not produce a paper draft")


def test_api_provider_failure_classification_is_safe_and_actionable() -> None:
    cases = [
        (
            {
                "error": {
                    "code": "invalid_json_schema",
                    "param": "text.format.schema",
                    "message": "private project text",
                }
            },
            "structured-output schema",
            "code=invalid_json_schema",
        ),
        (
            {"error": {"code": "model_not_found", "param": "model"}},
            "selected model",
            "model_not_found",
        ),
        ({"error": {"code": "insufficient_quota"}}, "billing or quota", "insufficient_quota"),
        (
            {"error": {"code": "secret-value", "param": "private input"}},
            "cause is not classified",
            None,
        ),
    ]
    for body, expected, safe_detail in cases:
        try:
            failure(400, body, "api_key")
        except ProjectError as exc:
            message = str(exc)
            assert expected in message
            assert "No automatic retry" in message
            assert "private project text" not in message
            assert "private input" not in message
            if safe_detail:
                assert safe_detail in message
            else:
                assert "secret-value" not in message
        else:
            raise AssertionError("Non-success provider responses must fail without retry")


def test_chatgpt_schema_rejection_is_actionable_and_redacted() -> None:
    try:
        failure(
            400,
            {
                "error": {
                    "code": "invalid_json_schema",
                    "param": "text.format.schema",
                    "message": "SECRET research and access token must not leak",
                }
            },
            "chatgpt",
        )
    except ProjectError as exc:
        message = str(exc)
        assert "structured-output schema" in message
        assert "invalid_json_schema" in message
        assert "HTTP 400" in message
        assert "account remains connected" in message
        assert "SECRET" not in message
        assert "access token" not in message
    else:
        raise AssertionError("Strict-schema rejection must be reported")


def test_visual_preference_controls_one_shot_and_long_paper_wire_schemas() -> None:
    requests: list[dict] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.content))
        return httpx.Response(
            400,
            json={
                "error": {
                    "type": "invalid_request_error",
                    "code": "invalid_json_schema",
                    "param": "text.format.schema",
                    "message": "private research content must not be surfaced",
                }
            },
        )

    real_client = httpx.AsyncClient
    with patch(
        "sigma.papers.httpx.AsyncClient",
        side_effect=lambda **kwargs: real_client(transport=httpx.MockTransport(handler), **kwargs),
    ):

        async def exercise() -> None:
            calls = [
                papers._provider(
                    {"sources": []},
                    {"mode": "api_key", "token": "fixture"},
                    {"model": "gpt-6.1-sol", "reasoning_effort": "high"},
                ),
                papers._provider(
                    {"sources": []},
                    {"mode": "api_key", "token": "fixture"},
                    {"model": "gpt-6.1-sol", "reasoning_effort": "high"},
                    include_diagrams=False,
                ),
                papers._provider_structured(
                    {"fixture": "input"},
                    {"mode": "api_key", "token": "fixture"},
                    {"model": "gpt-6.1-sol", "reasoning_effort": "high"},
                    instructions="fixture instructions",
                    schema_name="fixture_long_paper_stage",
                    response_model=papers.PaperDraft,
                ),
                papers._provider_structured(
                    {"fixture": "input"},
                    {"mode": "api_key", "token": "fixture"},
                    {"model": "gpt-6.1-sol", "reasoning_effort": "high"},
                    instructions="fixture instructions",
                    schema_name="sigma_paper_evidence_batch",
                    response_model=papers.EvidenceBatchResult,
                ),
            ]
            for call in calls:
                try:
                    await call
                except ProjectError as exc:
                    assert "code=invalid_json_schema" in str(exc)
                    assert "param=text.format.schema" in str(exc)
                    assert "private research content" not in str(exc)
                else:
                    raise AssertionError("Mock HTTP 400 must not create a draft")

        asyncio.run(exercise())

        assert len(requests) == 4  # one attempt per path/stage; no retry/fallback
        checked_schema = requests[0]["text"]["format"]["schema"]
        assert "diagrams" in checked_schema["properties"]
        assert "tables" in checked_schema["$defs"]["PaperSection"]["properties"]
        assert "VISUALS" in requests[0]["instructions"]
        unchecked_schema = requests[1]["text"]["format"]["schema"]
        assert "diagrams" not in unchecked_schema["properties"]
        assert "tables" not in unchecked_schema["$defs"]["PaperSection"]["properties"]
        assert "PaperDiagram" not in unchecked_schema["$defs"]
        assert "PaperTable" not in unchecked_schema["$defs"]
        assert "VISUALS" not in requests[1]["instructions"]
        assert "TABLES" not in requests[1]["instructions"]
    for request in requests:
        assert request["model"] == "gpt-6.1-sol"
        assert request["reasoning"] == {"effort": "high"}
        assert request["store"] is False
        assert request["max_output_tokens"] == 12000
        assert request["text"]["format"]["type"] == "json_schema"
        assert request["text"]["format"]["strict"] is True
        assert request["text"]["format"]["schema"]
        schema = request["text"]["format"]["schema"]
        assert set(schema["required"]) == set(schema["properties"])
    assert set(requests[-1]["text"]["format"]["schema"]["required"]) == {
        "notes",
        "conflicts_or_gaps",
        "covered_field_refs",
        "omitted_fields",
    }


def test_tex_proofreading_preserves_science_and_checkpoints_provider_work() -> None:
    with TemporaryDirectory() as temporary:
        checkpoint_path = Path(temporary) / "proofreading.sigma"
        initialize_project(checkpoint_path, "Proofreading fixture", "Preserve authored TeX.")
        view = inspect_project(checkpoint_path)
        state = papers._new_work(
            "a" * 64, view.project.id, "b" * 64, "fixture", "high", kind="one_shot"
        )
        tex = (
            r"\documentclass{article}"
            + "\n"
            + r"\begin{document}"
            + "\n"
            + r"$\\alpha=3$"
            + "\n"
            + r"The result holds. \\cite{source:one}"
            + "\n"
            + r"\end{document}"
            + "\n"
        )
        calls = 0
        progress: list[papers.PaperProgressEvent] = []

        async def provider(_input, _binding, _config, *, response_model, **_kwargs):
            nonlocal calls
            calls += 1
            assert response_model is papers.TeXProofreadResult
            if r"\\alpha" not in _input["exact_tex_chunk"]:
                return response_model(corrections=[]), "fixture"
            return (
                response_model(
                    corrections=[
                        papers.TeXCorrection(
                            category="math_notation",
                            find=r"\\alpha",
                            replace=r"\alpha",
                            rationale="Remove an accidental extra escape in math mode.",
                        )
                    ]
                ),
                "fixture",
            )

        async def report(
            stage: papers.PaperProgressStage,
            current: int | None,
            total: int | None,
            state: papers.PaperProgressState = "active",
            *,
            detail: str | None = None,
        ) -> None:
            progress.append(
                {
                    "type": "progress",
                    "state": state,
                    "stage": stage,
                    "current": current,
                    "total": total,
                    "started_at": "2026-10-31T00:00:00+00:00",
                    "elapsed_seconds": 0,
                    "detail": detail,
                }
            )

        async def run() -> tuple[str, dict]:
            with (
                patch.object(papers, "_compile_pdf", return_value=b"%PDF-fixture"),
                mock_pdf_inspection(),
                patch.object(papers, "_provider_structured", new=provider),
            ):
                return await papers._proofread_tex(
                    tex,
                    state,
                    binding={"identity": "fixture", "mode": "api_key", "token": "fixture"},
                    config={"model": "fixture", "reasoning_effort": "high"},
                    project_id=view.project.id,
                    project_path_value=str(checkpoint_path),
                    report=report,
                )

        corrected, provenance = asyncio.run(run())
        assert corrected != tex
        assert r"$\alpha=3$" in corrected
        assert r"\\cite{source:one}" in corrected
        assert provenance["status"] == "complete"
        assert provenance["provider_calls_attempted"] == 2
        assert provenance["pass_number"] == 2
        assert provenance["corrections"] == ["math_notation"]
        assert provenance["original_sha256"] == papers.hashlib.sha256(tex.encode()).hexdigest()
        proofread_progress = [item for item in progress if item["stage"] == "proofreading"]
        assert proofread_progress
        assert all(
            item["state"] in {"active", "milestone", "complete", "failed", "cancelled"}
            for item in progress
        )
        assert any(
            item["detail"] == "Checking and correcting typesetting issues."
            for item in proofread_progress
        )
        assert any(
            item["detail"] == "Applying mechanical corrections." and item["state"] == "milestone"
            for item in proofread_progress
        )
        assert any(
            item["detail"] == "Verifying corrected TeX." and item["state"] == "milestone"
            for item in proofread_progress
        )
        completed_calls = calls
        resumed, reused = asyncio.run(run())
        assert resumed == corrected
        assert reused["status"] == "complete"
        assert calls == completed_calls, "A completed proofreading call must not be repeated"
        if shutil.which("tectonic"):
            compiled = papers._compile_pdf(corrected, timeout_seconds=90)
            assert compiled.startswith(b"%PDF-")




def test_tex_proofreader_three_passes_with_early_convergence() -> None:
    with TemporaryDirectory() as temporary:
        path = Path(temporary) / "three-pass.sigma"
        view = initialize_project(path, "Three-pass fixture", "Convergent corrections.")
        state = papers._new_work(
            "a" * 64, view.project.id, "b" * 64, "fixture", "high", kind="one_shot"
        )
        tex = (
            r"\documentclass{article}"
            + "\n"
            + r"\begin{document}"
            + "\n"
            + r"$\\alpha+\\beta=3$"
            + "\n"
            + r"\end{document}"
            + "\n"
        )
        calls = 0

        async def provider(_payload, *_args, **_kwargs):
            nonlocal calls
            calls += 1
            corrections = []
            if calls <= 2:
                symbol = "alpha" if calls == 1 else "beta"
                corrections = [
                    papers.TeXCorrection(
                        category="math_notation",
                        find=r"\\" + symbol,
                        replace="\\" + symbol,
                        rationale="Correct a double TeX escape.",
                    )
                ]
            return papers.TeXProofreadResult(corrections=corrections), "fixture"

        async def report(*_args, **_kwargs):
            return None

        async def run():
            with (
                patch.object(papers, "_compile_pdf", return_value=b"%PDF-fixture"),
                patch.object(papers, "_provider_structured", new=provider),
            ):
                return await papers._proofread_tex(
                    tex,
                    state,
                    binding={"identity": "fixture", "mode": "api_key", "token": "fixture"},
                    config={"model": "fixture", "reasoning_effort": "high"},
                    project_id=view.project.id,
                    project_path_value=str(path),
                    report=report,
                )

        result, checkpoint = asyncio.run(run())
        assert papers.MAX_PROOFREADER_PASSES == 3
        assert checkpoint["pass_number"] == 3
        assert checkpoint["provider_calls_attempted"] == 3
        assert checkpoint["status"] == "complete"
        assert r"$\alpha+\beta=3$" in result
        assert calls == 3
        again, _ = asyncio.run(run())
        assert again == result
        assert calls == 3


def test_tex_diagnostics_allow_geometry_fixes_but_protect_visual_data() -> None:
    normal = r"\documentclass{article}\begin{document}Result $x=3$.\end{document}"
    assert papers._tex_static_diagnostics(normal) == []
    malformed = (
        r"\documentclass{article}\begin{document}\begin{align}x=3\end{equation}"
        r"\\alpha\end{document}"
    )
    warnings = papers._tex_static_diagnostics(malformed)
    assert any("Mismatched TeX environment" in warning for warning in warnings)
    assert any("double-escaped" in warning for warning in warnings)

    table_before = (
        r"\begin{longtable}{p{\dimexpr\linewidth/2\relax}p{\dimexpr\linewidth/2\relax}}"
        r"Campus & 3 GPUs\\\end{longtable}"
    )
    table_after = (
        r"\begin{longtable}{p{\dimexpr\linewidth/3\relax}p{\dimexpr\linewidth*2/3\relax}}"
        r"Campus & 3 GPUs\\\end{longtable}"
    )
    assert papers._tex_semantic_signature(table_before) == papers._tex_semantic_signature(
        table_after
    )
    assert papers._tex_semantic_signature(table_before) != papers._tex_semantic_signature(
        table_after.replace("3 GPUs", "4 GPUs")
    )

    diagram_before = (
        r"\begin{tikzpicture}\node[draw,text width=3cm] (campus) at (0,0) {Campus model};"
        r"\end{tikzpicture}"
    )
    diagram_after = (
        r"\begin{tikzpicture}\node[draw,text width=4cm] (campus) at (2,1) {Campus model};"
        r"\end{tikzpicture}"
    )
    assert papers._tex_semantic_signature(diagram_before) == papers._tex_semantic_signature(
        diagram_after
    )
    assert papers._tex_semantic_signature(diagram_before) != papers._tex_semantic_signature(
        diagram_after.replace("Campus model", "Frontier model")
    )
    assert papers._tex_semantic_signature("$α=3$") == papers._tex_semantic_signature(r"$\alpha=3$")


def test_tex_proofreader_rejects_scientific_edits_and_does_not_replay_uncertain_calls() -> None:
    with TemporaryDirectory() as temporary:
        path = Path(temporary) / "proofreading-recovery.sigma"
        view = initialize_project(path, "Proofreading recovery", "Preserve an authored conclusion.")
        state = papers._new_work(
            "c" * 64, view.project.id, "d" * 64, "fixture", "high", kind="one_shot"
        )
        tex = "\\documentclass{article}\n\\begin{document}\nThe result is 3.\n\\end{document}\n"
        calls = 0

        async def mutate(_input, _binding, _config, *, response_model, **_kwargs):
            nonlocal calls
            calls += 1
            return (
                response_model(
                    corrections=[
                        papers.TeXCorrection(
                            category="spacing",
                            find="result is 3",
                            replace="result is 4",
                            rationale="Fixture malicious scientific edit.",
                        )
                    ]
                ),
                "fixture",
            )

        async def report(*_args, **_kwargs):
            return None

        async def run() -> tuple[str, dict]:
            with (
                patch.object(papers, "_compile_pdf", return_value=b"%PDF-fixture"),
                mock_pdf_inspection(),
                patch.object(papers, "_provider_structured", new=mutate),
            ):
                return await papers._proofread_tex(
                    tex,
                    state,
                    binding={"identity": "fixture", "mode": "api_key", "token": "fixture"},
                    config={"model": "fixture", "reasoning_effort": "high"},
                    project_id=view.project.id,
                    project_path_value=str(path),
                    report=report,
                )

        preserved, provenance = asyncio.run(run())
        assert preserved == tex
        assert provenance["status"] == "fallback"
        assert provenance["corrections"] == []
        assert "changed protected scientific" in provenance["fallback_reason"]
        assert calls == 1

        interrupted_state = papers._new_work(
            "e" * 64, view.project.id, "f" * 64, "fixture", "high", kind="one_shot"
        )
        large_tex = (
            "\\documentclass{article}\n\\begin{document}\n\n"
            + "A " * 5_500
            + "\n\n"
            + "B " * 5_500
            + "\n\n\\end{document}\n"
        )
        assert len(papers._tex_chunks(large_tex)) == 2
        resumed_calls = 0

        async def interrupt_second(_input, _binding, _config, *, response_model, **_kwargs):
            nonlocal resumed_calls
            resumed_calls += 1
            if resumed_calls == 2:
                raise asyncio.CancelledError()
            return response_model(corrections=[]), "fixture"

        async def interrupt() -> None:
            with (
                patch.object(papers, "_compile_pdf", return_value=b"%PDF-fixture"),
                mock_pdf_inspection(),
                patch.object(papers, "_provider_structured", new=interrupt_second),
            ):
                await papers._proofread_tex(
                    large_tex,
                    interrupted_state,
                    binding={"identity": "fixture", "mode": "api_key", "token": "fixture"},
                    config={"model": "fixture", "reasoning_effort": "high"},
                    project_id=view.project.id,
                    project_path_value=str(path),
                    report=report,
                )

        try:
            asyncio.run(interrupt())
        except asyncio.CancelledError:
            pass
        else:
            raise AssertionError("The proofreader fixture should interrupt on its second chunk")
        assert interrupted_state["proofreading"]["attempts"] == ["complete", "dispatched"]
        with patch.object(papers, "_compile_pdf", return_value=b"%PDF-fixture"):
            recovered, recovered_provenance = asyncio.run(
                papers._proofread_tex(
                    large_tex,
                    interrupted_state,
                    binding={"identity": "fixture", "mode": "api_key", "token": "fixture"},
                    config={"model": "fixture", "reasoning_effort": "high"},
                    project_id=view.project.id,
                    project_path_value=str(path),
                    report=report,
                )
            )
        assert recovered == large_tex
        assert recovered_provenance["status"] == "fallback"
        assert resumed_calls == 2, "The ambiguous second provider call must not be replayed"


def test_one_shot_and_long_form_both_proofread_before_compiling() -> None:
    with TemporaryDirectory() as temporary:
        one_path = Path(temporary) / "one-shot.sigma"
        long_path = Path(temporary) / "long-form.sigma"
        one_view = initialize_project(one_path, "One-shot proofreading", "Test stage ordering.")
        long_view = initialize_project(long_path, "Long-form proofreading", "Test stage ordering.")
        credential = {"identity": "fixture:proofread", "mode": "api_key", "token": "fixture"}
        config = {
            "available": True,
            "binding": credential["identity"],
            "model": "gpt-6.1-sol",
            "reasoning_effort": "high",
        }
        events: dict[str, list[papers.PaperProgressEvent]] = {"one": [], "long": []}
        compile_timings: dict[str, list[float]] = {"one": [], "long": []}
        compile_calls: dict[str, int] = {"one": 0, "long": 0}
        proofreader_calls = 0
        real_compile = papers._compile_pdf

        async def author(package, *_args):
            source = next(item["id"] for item in package["sources"] if item["kind"] == "project")
            return draft(source), config["model"]

        async def long_author(package, _binding, _config, state, _save, *_args, **_kwargs):
            source = next(item["id"] for item in package["sources"] if item["kind"] == "project")
            state["provider_calls"] = 2
            state["provider_calls_total"] = 2
            long_draft = draft(source)
            passages = [
                "The frozen premise identifies the scope of this deterministic review. ",
                "The displayed recurrence is interpreted only under the recorded assumptions. ",
                "The boundary case is retained as an explicit check on the stated implication. ",
                "No additional empirical observation or theorem is inferred from this fixture. ",
            ]
            sections = [
                papers.PaperSection(
                    heading=f"Long-form evidence analysis {section_number}",
                    paragraphs=[
                        f"Case {section_number}.{paragraph_number}: "
                        + passages[(section_number + paragraph_number) % len(passages)] * 6
                        for paragraph_number in range(8)
                    ],
                    claim_ids=["C1"],
                )
                for section_number in range(1, 5)
            ]
            table = papers.PaperTable(
                caption="Long-form fixture assumptions and validation outcomes.",
                headers=["Case", "Assumption", "Outcome"],
                rows=[
                    ["Initial", "Saved value fixed", "Checked"],
                    ["Step", "Recurrence applies", "Conditional"],
                    ["Extension", "No new premise", "Unresolved"],
                ],
                evidence_refs=[source],
                claim_ids=["C1"],
            )
            sections[0] = sections[0].model_copy(update={"tables": [table]})
            long_diagram = papers.PaperDiagram(
                caption="The bounded long-form analysis workflow.",
                nodes=[
                    papers.DiagramNode(id="source", label="Frozen evidence"),
                    papers.DiagramNode(id="analysis", label="Analyze assumptions"),
                    papers.DiagramNode(id="checks", label="Check boundary cases"),
                    papers.DiagramNode(id="limits", label="Record limitations"),
                ],
                edges=[
                    papers.DiagramEdge(source="source", target="analysis"),
                    papers.DiagramEdge(source="analysis", target="checks"),
                    papers.DiagramEdge(source="checks", target="limits"),
                ],
                evidence_refs=[source],
                claim_ids=["C1"],
            )
            return (
                long_draft.model_copy(update={"sections": sections, "diagrams": [long_diagram]}),
                2,
                0,
            )

        async def proofreader(_input, _binding, _config, *, response_model, **_kwargs):
            nonlocal proofreader_calls
            proofreader_calls += 1
            assert response_model is papers.TeXProofreadResult
            return response_model(corrections=[]), config["model"]

        async def run(path: Path, view, key: str, force_long: bool = False):
            async def collect(event: papers.PaperProgressEvent) -> None:
                events[key].append(event)

            def measured_compile(tex: str, **kwargs) -> bytes:
                compile_calls[key] += 1
                compile_number = compile_calls[key]
                if not shutil.which("tectonic"):
                    has_layout_warning = (key == "one" and compile_number in {2, 3, 4}) or (
                        key == "long" and compile_number == 2
                    )
                    if has_layout_warning:
                        kwargs["diagnostics"].append("Overfull \\hbox (10.0pt too wide)")
                    return b"%PDF-fixture"
                started = perf_counter()
                result = real_compile(tex, **kwargs)
                compile_timings[key].append(perf_counter() - started)
                has_layout_warning = (key == "one" and compile_number in {2, 3, 4}) or (
                    key == "long" and compile_number == 2
                )
                if has_layout_warning:
                    kwargs["diagnostics"].append("Overfull \\hbox (10.0pt too wide)")
                return result

            with (
                patch.object(
                    papers, "auth_context", new=lambda: asyncio.sleep(0, result=credential)
                ),
                patch.object(
                    papers, "configuration", new=lambda **_kwargs: asyncio.sleep(0, result=config)
                ),
                patch.object(papers, "_provider", new=author),
                patch.object(papers, "_generate_long_draft", new=long_author),
                patch.object(papers, "_provider_structured", new=proofreader),
                patch.object(papers, "_compile_pdf", new=measured_compile),
                mock_pdf_inspection(),
            ):
                return await papers.generate(
                    str(path),
                    credential["identity"],
                    view.project.id,
                    progress=collect,
                    force_long_form=force_long,
                )

        one = asyncio.run(run(one_path, one_view, "one"))
        long = asyncio.run(run(long_path, long_view, "long", force_long=True))
        expected_proofreader_calls = 0
        for key, result in (("one", one), ("long", long)):
            stages = [
                event["stage"]
                for event in events[key]
                if event["state"] in {"active", "milestone", "complete"}
            ]
            assert (
                stages.index("validation") < stages.index("proofreading") < stages.index("compile")
            )
            assert stages.index("compile") < stages.index("pdf_check") < stages.index("complete")
            check_events = [event for event in events[key] if event["stage"] == "pdf_check"]
            assert len(check_events) >= 1, events[key]
            assert check_events[0]["detail"] == (
                "Checking PDF pass 1 of 3; TeX is authoritative and PDFs are not edited."
            )
            record = papers.get_paper(
                str(one_path if key == "one" else long_path), result["paper_id"]
            )
            assert record["generation"]["proofreading"]["attempted"] is True
            assert record["generation"]["proofreading"]["ai_performed"] is True
            assert (
                1
                <= record["generation"]["proofreading"]["provider_calls_attempted"]
                <= (papers.MAX_PROOFREAD_CALLS)
            )
            expected_proofreader_calls += record["generation"]["proofreading"][
                "provider_calls_attempted"
            ]
            assert (
                record["generation"]["provider_calls_attempted"]
                == record["generation"]["provider_calls_lifetime_total"]
            )
            assert record["generation"]["long_form"] is (key == "long")
            if key == "one":
                assert record["generation"]["pdf_check_final_pass"] == 3
                assert [item["pass"] for item in record["generation"]["pdf_check_passes"]] == [
                    1,
                    2,
                    3,
                ]
                assert len(record["generation"]["layout_repairs"]) == 2
                assert r"\emergencystretch=8em" in record["tex_source"]
                assert record["generation"]["layout_status"] == "needs_review"
                assert record["generation"]["publication_status"] == "needs_review"
                assert any(
                    "within three TeX rendering passes" in warning
                    for warning in record["validation_warnings"]
                )
                assert [
                    event["current"]
                    for event in events[key]
                    if event["stage"] == "pdf_check" and event["state"] == "active"
                ] == [1, 2, 3]
            else:
                assert record["generation"]["pdf_check_final_pass"] == 2
                assert len(record["generation"]["layout_repairs"]) == 1
                assert record["generation"]["layout_status"] == "no_severe_box_warnings_reported"
            pdf = papers.get_pdf(str(one_path if key == "one" else long_path), result["paper_id"])
            assert pdf.startswith(b"%PDF-")
            if key == "long":
                assert not any(
                    "Overfull" in diagnostic
                    for diagnostic in record["generation"]["proofreading"]["unresolved_diagnostics"]
                )
            if shutil.which("tectonic"):
                expected_compiles = 4 if key == "one" else 3
                assert compile_calls[key] == expected_compiles
                print(
                    f"PASS deterministic {key} end-to-end Tectonic path: "
                    f"{len(record['tex_source'].encode())} TeX bytes, {len(pdf)} PDF bytes, "
                    f"{expected_compiles} compiles in {sum(compile_timings[key]):.3f}s, "
                    f"{record['generation']['proofreading']['provider_calls_attempted']} proofreader call(s)"
                )
            else:
                assert compile_timings[key] == []
        assert proofreader_calls == expected_proofreader_calls


def test_strict_paper_schemas_require_all_properties() -> None:
    # Pydantic's default_factory fields are optional in its validation schema;
    # Responses strict JSON rejects them unless they are marked required.
    raw = papers.EvidenceBatchResult.model_json_schema()
    assert "covered_field_refs" not in raw["required"]
    assert "omitted_fields" not in raw["required"]

    for model in (
        papers.PaperDraft,
        papers.EvidenceBatchResult,
        papers.LongPaperPlan,
        papers.LongSectionDraft,
    ):
        schema = papers._paper_response_schema(model)

        def validate(node: Any) -> None:
            if isinstance(node, dict):
                assert "default" not in node
                if node.get("type") == "object" and "properties" in node:
                    assert set(node["required"]) == set(node["properties"])
                    assert node["additionalProperties"] is False
                for value in node.values():
                    validate(value)
            elif isinstance(node, list):
                for item in node:
                    validate(item)

        validate(schema)

    normalized = papers._paper_response_schema(papers.EvidenceBatchResult)
    assert set(normalized["required"]) == set(normalized["properties"])
    # Do not change the application's Pydantic parsing/default semantics.
    parsed = papers.EvidenceBatchResult(notes=[], conflicts_or_gaps=[])
    assert parsed.covered_field_refs == [] and parsed.omitted_fields == []


def test_paper_stage_accepts_completed_chatgpt_stream_with_trailing_usage() -> None:
    """Trailing usage bookkeeping must not invalidate a paid completed stage."""
    stage_text = json.dumps(
        {
            "notes": [],
            "conflicts_or_gaps": [],
            "covered_field_refs": [],
            "omitted_fields": [],
        }
    )
    stage_response = {
        "id": "resp-evidence-fixture",
        "status": "completed",
        "model": "gpt-6.1-sol",
        "output": [],
    }
    events = [
        {
            "type": "response.created",
            "sequence_number": 0,
            "response": {"id": stage_response["id"]},
        },
        {"type": "response.output_text.delta", "sequence_number": 1, "delta": stage_text},
        {"type": "response.completed", "sequence_number": 2, "response": stage_response},
        {
            "type": "response.usage",
            "sequence_number": 3,
            "usage": {"input_tokens": 32, "output_tokens": 17},
        },
    ]
    sent: list[dict[str, Any]] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        sent.append(json.loads(request.content))
        stream = "".join("data: " + json.dumps(event) + "\n\n" for event in events)
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            content=(stream + "data: [DONE]\n\n").encode(),
        )

    real_client = httpx.AsyncClient
    with patch(
        "sigma.papers.httpx.AsyncClient",
        side_effect=lambda **kwargs: real_client(transport=httpx.MockTransport(handler), **kwargs),
    ):
        result, model = asyncio.run(
            papers._provider_structured(
                {"fields": []},
                {"mode": "chatgpt", "token": "fixture"},
                {"model": "gpt-6.1-sol", "reasoning_effort": "high"},
                instructions="Extract a bounded evidence index.",
                schema_name="sigma_paper_evidence_batch",
                response_model=papers.EvidenceBatchResult,
            )
        )

    assert model == "gpt-6.1-sol"
    assert isinstance(result, papers.EvidenceBatchResult)
    assert result.notes == [] and result.covered_field_refs == []
    assert len(sent) == 1
    assert sent[0]["stream"] is True and "max_output_tokens" not in sent[0]
    assert sent[0]["text"]["format"]["strict"] is True


def test_long_tex_compiler_source_bound_is_configurable() -> None:
    with patch("sigma.project_reports.shutil.which", return_value="tectonic-fixture"):
        try:
            papers._compile_pdf("x" * 101, max_source_bytes=100)
        except RuntimeError as exc:
            assert "100 byte source limit" in str(exc)
        else:
            raise AssertionError("The TeX compiler must enforce the configured source bound")


def test_one_shot_draft_is_reused_after_pdf_compilation_failure() -> None:
    with TemporaryDirectory() as temporary:
        path = Path(temporary) / "one-shot-recovery.sigma"
        initialize_project(path, "One-shot recovery", "Preserve this paper draft")
        view = inspect_project(path)
        credential = {"identity": "chatgpt:fixture", "mode": "chatgpt", "token": "fixture"}
        config = {
            "available": True,
            "binding": credential["identity"],
            "model": "gpt-6.1-sol",
            "reasoning_effort": "high",
        }
        provider_calls = 0
        compile_calls = 0
        provider_started = asyncio.Event()
        allow_provider = asyncio.Event()
        first_events: list[papers.PaperProgressEvent] = []
        retry_events: list[papers.PaperProgressEvent] = []

        async def fake_provider(context, *_args):
            nonlocal provider_calls
            provider_calls += 1
            if provider_calls == 1:
                provider_started.set()
                await allow_provider.wait()
            project_source = next(
                source["id"] for source in context["sources"] if source["kind"] == "project"
            )
            authored = draft(project_source)
            table = papers.PaperTable(
                caption="Saved quantitative comparison retained through checkbox changes.",
                headers=["Route", "Evidence"],
                rows=[["Campus", "Frozen"], ["Approved frontier", "Frozen"]],
                evidence_refs=[project_source],
                claim_ids=["C1"],
            )
            figure = papers.PaperDiagram(
                caption="Saved policy decision flow for the frozen project evidence.",
                nodes=[
                    papers.DiagramNode(id="task", label="Research task"),
                    papers.DiagramNode(id="policy", label="Policy gate"),
                ],
                edges=[papers.DiagramEdge(source="task", target="policy", label="classify")],
                evidence_refs=[project_source],
                claim_ids=["C1"],
            )
            authored = authored.model_copy(
                update={
                    "diagrams": [figure],
                    "sections": [
                        authored.sections[0].model_copy(update={"tables": [table]}),
                        authored.sections[1],
                    ],
                }
            )
            return authored, config["model"]

        def fail_compile_visual_and_fallback(_tex, **_kwargs):
            nonlocal compile_calls
            compile_calls += 1
            if compile_calls == 2:
                raise RuntimeError("fixture compiler unavailable for an unrelated reason")
            return b"%PDF-fixture"

        with (
            patch.object(papers, "auth_context", new=lambda: asyncio.sleep(0, result=credential)),
            patch.object(
                papers, "configuration", new=lambda **_kwargs: asyncio.sleep(0, result=config)
            ),
            patch.object(papers, "_provider", new=fake_provider),
            patch.object(papers, "_compile_pdf", new=fail_compile_visual_and_fallback),
            mock_pdf_inspection(),
        ):

            async def first_attempt() -> None:
                async def collect(event: papers.PaperProgressEvent) -> None:
                    first_events.append(event)

                task = asyncio.create_task(
                    papers.generate(
                        str(path), credential["identity"], view.project.id, progress=collect
                    )
                )
                await asyncio.wait_for(provider_started.wait(), timeout=2)
                live = papers.progress_status(str(path))
                assert live is not None and live["status"] == "active", live
                assert live["stage"] == "writing", live
                checkpoint = papers._load_work(str(path))
                assert checkpoint is not None
                assert checkpoint["progress"]["stage"] == "writing"
                await asyncio.sleep(1.05)
                live = papers.progress_status(str(path))
                assert live is not None and live["elapsed_seconds"] >= 1, live
                allow_provider.set()
                try:
                    await task
                except ProjectError as exc:
                    assert "fixture compiler unavailable" in str(exc)
                else:
                    raise AssertionError("The injected compile failure must be surfaced")

            asyncio.run(first_attempt())
            failed_progress = papers.progress_status(str(path))
            assert failed_progress is not None and failed_progress["status"] == "failed"
            assert failed_progress["stage"] == "compile"

            checkpoint = papers._load_work(str(path))
            assert checkpoint is not None and checkpoint["kind"] == "one_shot"
            assert checkpoint["provider_calls"] == 1
            assert checkpoint["one_shot_draft"]["diagrams"]
            assert checkpoint["one_shot_draft"]["sections"][0]["tables"]
            preflight = papers.preflight(
                str(path),
                expected_project_id=view.project.id,
                expected_binding=credential["identity"],
                mode=credential["mode"],
                model=config["model"],
                reasoning_effort=config["reasoning_effort"],
            )
            assert preflight["draft_recovery_available"] is True
            assert preflight["provider_calls_remaining"] == 0
            assert preflight["maximum_provider_calls"] == 0
            with patch.object(
                papers, "_provider", side_effect=AssertionError("cached draft must be reused")
            ):

                async def resume() -> dict:
                    async def collect(event: papers.PaperProgressEvent) -> None:
                        retry_events.append(event)

                    return await papers.generate(
                        str(path),
                        credential["identity"],
                        view.project.id,
                        progress=collect,
                        include_research_details=True,
                        include_diagrams=False,
                    )

                result = asyncio.run(resume())

        saved = papers.get_paper(str(path), result["paper_id"])
        assert provider_calls == 1
        assert compile_calls == 4
        assert saved["generation"]["provider_calls_attempted"] == 3
        assert saved["generation"]["proofreading"]["provider_calls_attempted"] == 2
        assert saved["generation"]["provider_calls_lifetime_total"] == 3
        assert saved["generation"]["include_research_details"] is True
        assert saved["generation"]["include_diagrams_and_tables"] is False
        assert saved["draft"]["diagrams"] == []
        assert all(not section["tables"] for section in saved["draft"]["sections"])
        assert r"\usepackage{tikz}" not in saved["tex_source"]
        assert r"\begin{longtable}" not in saved["tex_source"]
        assert r"\section*{About this paper}" in saved["tex_source"]
        assert papers._load_work(str(path)) is None
        assert len(papers.list_papers(str(path))) == 1
        first_stages = [event["stage"] for event in first_events if event["state"] == "active"]
        assert first_stages.index("validation") < first_stages.index("proofreading")
        assert first_stages.index("proofreading") < first_stages.index("compile")
        assert retry_events[-1]["stage"] == "complete" and retry_events[-1]["state"] == "complete"
        assert retry_events[-1]["elapsed_seconds"] >= first_events[-1]["elapsed_seconds"]


def test_proofreading_option_changes_keep_per_render_and_cumulative_call_counts() -> None:
    """Repeated TeX option changes retain drafts and count each paid call once."""
    with TemporaryDirectory() as temporary:
        path = Path(temporary) / "proofreading-render-call-accounting.sigma"
        initialize_project(path, "Proofreading accounting", "Keep the saved paper draft.")
        view = inspect_project(path)
        credential = {"identity": "fixture:account", "mode": "api_key", "token": "fixture"}
        config = {
            "available": True,
            "binding": credential["identity"],
            "model": "fixture-model",
            "reasoning_effort": "high",
        }
        project_package, _ = papers._snapshot(str(path))
        project_ref = next(
            item["id"] for item in project_package["sources"] if item["kind"] == "project"
        )
        authored = draft(project_ref)
        authored = authored.model_copy(
            update={
                "diagrams": [
                    papers.PaperDiagram(
                        caption="Evidence flow for the saved project.",
                        nodes=[
                            papers.DiagramNode(id="source", label="Source"),
                            papers.DiagramNode(id="claim", label="Claim"),
                        ],
                        edges=[papers.DiagramEdge(source="source", target="claim")],
                        evidence_refs=[project_ref],
                        claim_ids=["C1"],
                    )
                ]
            }
        )
        author_calls = 0
        proofreading_calls = 0
        compile_calls = 0
        diagnostic_sources: list[str] = []

        async def author(_context, *_args):
            nonlocal author_calls
            author_calls += 1
            return authored, config["model"]

        async def proofreader(*_args, **_kwargs):
            nonlocal proofreading_calls
            proofreading_calls += 1
            return papers.TeXProofreadResult(corrections=[]), config["model"]

        def split_tex(tex: str) -> list[tuple[int, int]]:
            middle = len(tex) // 2
            return [(0, middle), (middle, len(tex))]

        def intermittent_compile(tex: str, **_kwargs) -> bytes:
            nonlocal compile_calls
            compile_calls += 1
            if compile_calls % 2:
                diagnostic_sources.append(tex)
                return b"%PDF-diagnostics-fixture"
            if compile_calls in {2, 4}:
                raise RuntimeError("fixture final compile failure; preserve checkpoint")
            return b"%PDF-final-fixture"

        async def run(*, details: bool = False, diagrams: bool = True, notes: bool = False):
            with (
                patch.object(
                    papers, "auth_context", new=lambda: asyncio.sleep(0, result=credential)
                ),
                patch.object(
                    papers, "configuration", new=lambda **_kwargs: asyncio.sleep(0, result=config)
                ),
                patch.object(papers, "_provider", new=author),
                patch.object(papers, "_provider_structured", new=proofreader),
                patch.object(papers, "_tex_chunks", new=split_tex),
                patch.object(papers, "_compile_pdf", new=intermittent_compile),
                mock_pdf_inspection(),
            ):
                return await papers.generate(
                    str(path),
                    credential["identity"],
                    view.project.id,
                    include_research_details=details,
                    include_diagrams=diagrams,
                    include_validation_notes=notes,
                )

        async def exercise() -> dict[str, Any]:
            for options in (
                {"details": False, "diagrams": True},
                {"details": True, "diagrams": False},
            ):
                try:
                    await run(**options)
                except ProjectError as exc:
                    assert "fixture final compile failure" in str(exc)
                else:
                    raise AssertionError("The first two versions must preserve resumable work")
                checkpoint = papers._load_work(str(path))
                assert checkpoint is not None
                assert checkpoint["proofreading"]["provider_calls_attempted"] == 2
                expected_prior = 0 if options["details"] is False else 2
                assert checkpoint["proofreading_calls_prior"] == expected_prior
            preflight = papers.preflight(
                str(path),
                expected_project_id=view.project.id,
                expected_binding=credential["identity"],
                mode=credential["mode"],
                model=config["model"],
                reasoning_effort=config["reasoning_effort"],
            )
            assert preflight["draft_recovery_available"] is True
            assert preflight["provider_calls_attempted"] == 5  # author 1 + proofreader 4
            assert preflight["provider_calls_lifetime_total"] == 5
            return await run(details=False, diagrams=True, notes=True)

        result = asyncio.run(exercise())
        saved = papers.get_paper(str(path), result["paper_id"])
        assert author_calls == 1, "Option changes must reuse the saved authored draft."
        assert proofreading_calls == 6  # two bounded chunks for each TeX rendering
        assert compile_calls == 6
        assert len(diagnostic_sources) == 3 and len(set(diagnostic_sources)) == 3
        assert saved["generation"]["proofreading"]["provider_calls_current_render"] == 2
        assert saved["generation"]["proofreading"]["prior_render_provider_calls"] == 4
        assert saved["generation"]["proofreading"]["provider_calls_attempted"] == 6
        assert saved["generation"]["provider_calls_attempted"] == 7
        assert saved["generation"]["provider_calls_lifetime_total"] == 7
        assert saved["generation"]["include_validation_notes"] is True
        assert saved["generation"]["include_diagrams_and_tables"] is True
        assert papers._load_work(str(path)) is None


def test_diagram_compile_fallback_preserves_evidence_tables_and_provider_accounting() -> None:
    """TikZ fallback preserves accepted proofreading patches and exact PDF source."""
    with TemporaryDirectory() as temporary:
        path = Path(temporary) / "diagram-compile-fallback.json"
        view = initialize_project(path, "Diagram fallback", "Preserve the paper evidence.")
        credential = {"identity": "fixture:account", "mode": "api_key", "token": "fixture"}
        config = {
            "available": True,
            "binding": credential["identity"],
            "model": "fixture-model",
            "reasoning_effort": "high",
        }
        package, snapshot_hash = papers._snapshot(str(path))
        project_ref = next(
            source["id"] for source in package["sources"] if source["kind"] == "project"
        )
        figure = papers.PaperDiagram(
            caption="Illustrative evidence boundary for the saved research.",
            nodes=[
                papers.DiagramNode(id="source", label="Saved source"),
                papers.DiagramNode(id="claim", label="Claim register"),
            ],
            edges=[papers.DiagramEdge(source="source", target="claim", label="supports")],
            evidence_refs=[project_ref],
            claim_ids=["C1"],
        )
        table = papers.PaperTable(
            caption="Bounded evidence summary for the saved project.",
            headers=["Record", "Status", "Note"],
            rows=[["Project question", "Saved", "Frozen"]],
            evidence_refs=[project_ref],
            claim_ids=["C1"],
        )
        authored = draft(project_ref).model_copy(
            update={
                "diagrams": [figure],
                "sections": [
                    draft(project_ref).sections[0].model_copy(update={"tables": [table]}),
                    draft(project_ref).sections[1],
                ],
            }
        )
        provider_calls = 0
        compile_tex: list[str] = []
        successful_tex: list[str] = []
        successful_pdf: list[bytes] = []
        fallback_diagnostics: list[str] = []
        real_compile = papers._compile_pdf
        real_tex = papers._tex

        async def fake_provider(_context, *_args):
            nonlocal provider_calls
            provider_calls += 1
            return authored, config["model"]

        async def fake_proofreader(_context, *_args, **_kwargs):
            if r"\\alpha" not in _context["exact_tex_chunk"]:
                return papers.TeXProofreadResult(corrections=[]), config["model"]
            return (
                papers.TeXProofreadResult(
                    corrections=[
                        papers.TeXCorrection(
                            category="math_notation",
                            find=r"\\alpha",
                            replace=r"\alpha",
                            rationale="Remove an accidental extra escape in math mode.",
                        )
                    ]
                ),
                config["model"],
            )

        def tex_with_mechanical_defect(*args, **kwargs):
            source = real_tex(*args, **kwargs)
            return source.replace(r"\end{document}", r"$\\alpha=3$" + "\n" + r"\end{document}")

        def fail_diagram_then_compile(tex: str, **kwargs):
            compile_tex.append(tex)
            if len(compile_tex) == 1:
                # The pre-proofread temporary compile is intentionally a fixture:
                # the provider receives the generated source next.
                return b"%PDF-initial-diagnostic-fixture"
            if len(compile_tex) == 2:
                assert r"$\alpha=3$" in tex
                assert r"\begin{tikzpicture}" in tex
                if diagnostics := kwargs.get("diagnostics"):
                    diagnostics.append(
                        "error: report.tex: Package pgfkeys Error: TikZ node geometry failed."
                    )
                raise RuntimeError("Package pgfkeys Error: TikZ node geometry failed.")
            assert r"$\alpha=3$" in tex, "fallback must retain accepted math correction"
            assert r"\\alpha" not in tex
            assert r"\begin{tikzpicture}" not in tex
            assert r"\usepackage{tikz}" not in tex
            successful_tex.append(tex)
            kwargs["diagnostics"] = fallback_diagnostics
            pdf = real_compile(tex, **kwargs) if shutil.which("tectonic") else b"%PDF-fixture"
            successful_pdf.append(pdf)
            return pdf

        async def run() -> dict[str, Any]:
            with (
                patch.object(
                    papers, "auth_context", new=lambda: asyncio.sleep(0, result=credential)
                ),
                patch.object(
                    papers, "configuration", new=lambda **_kwargs: asyncio.sleep(0, result=config)
                ),
                patch.object(papers, "_provider", new=fake_provider),
                patch.object(papers, "_provider_structured", new=fake_proofreader),
                patch.object(papers, "_tex", new=tex_with_mechanical_defect),
                patch.object(papers, "_compile_pdf", new=fail_diagram_then_compile),
                mock_pdf_inspection(),
            ):
                return await papers.generate(str(path), credential["identity"], view.project.id)

        result = asyncio.run(run())
        saved = papers.get_paper(str(path), result["paper_id"])
        assert provider_calls == 1
        assert len(compile_tex) == 4
        assert len(successful_tex) == 1
        assert r"$\\alpha=3$" in compile_tex[0]
        assert r"$\alpha=3$" in compile_tex[1]
        assert r"$\alpha=3$" in successful_tex[0]
        assert r"\usepackage{tikz}" in compile_tex[0]
        assert r"\usepackage{tikz}" in compile_tex[1]
        assert r"\usepackage{tikz}" not in successful_tex[0]
        assert all(r"\begin{longtable}" in source for source in compile_tex)
        assert r"\begin{longtable}" in successful_tex[0]
        assert saved["snapshot_sha256"] == snapshot_hash
        assert saved["generation"]["provider_calls_attempted"] == 3
        assert saved["generation"]["proofreading"]["provider_calls_attempted"] == 2
        assert saved["generation"]["proofreading"]["correction_categories"] == ["math_notation"]
        assert saved["draft"]["diagrams"] == []
        assert saved["draft"]["sections"][0]["tables"]
        assert saved["tex_source"] == successful_tex[0]
        assert saved["generation"]["proofreading"]["corrected_tex_sha256"] == (
            papers.hashlib.sha256(compile_tex[1].encode()).hexdigest()
        )
        assert saved["generation"]["proofreading"]["final_tex_sha256"] == (
            papers.hashlib.sha256(saved["tex_source"].encode()).hexdigest()
        )
        assert saved["generation"]["diagram_fallback"]["applied"] is True
        assert saved["generation"]["diagram_fallback"]["removed_diagram_count"] == 1
        archived_pdf = read_project_artifact(
            str(path), f"artifacts/papers/{result['paper_id']}.pdf"
        )
        assert archived_pdf.startswith(b"%PDF-")
        assert archived_pdf == successful_pdf[0]
        if shutil.which("tectonic"):
            assert not any("Overfull" in diagnostic for diagnostic in fallback_diagnostics)
        assert any("text-only PDF fallback" in warning for warning in saved["validation_warnings"])


def test_unrelated_compile_failure_does_not_remove_valid_diagrams() -> None:
    """Only a diagnosed TikZ/PGF error is eligible for the text-only fallback."""
    with TemporaryDirectory() as temporary:
        path = Path(temporary) / "unrelated-compile-failure.json"
        view = initialize_project(path, "Unrelated compile failure", "Keep the diagram.")
        credential = {"identity": "fixture:account", "mode": "api_key", "token": "fixture"}
        config = {
            "available": True,
            "binding": credential["identity"],
            "model": "fixture-model",
            "reasoning_effort": "high",
        }
        package, _ = papers._snapshot(str(path))
        project_ref = next(
            source["id"] for source in package["sources"] if source["kind"] == "project"
        )
        authored = draft(project_ref).model_copy(
            update={
                "diagrams": [
                    papers.PaperDiagram(
                        caption="Illustrative evidence boundary for the saved research.",
                        nodes=[
                            papers.DiagramNode(id="source", label="Saved source"),
                            papers.DiagramNode(id="claim", label="Claim register"),
                        ],
                        edges=[papers.DiagramEdge(source="source", target="claim")],
                        evidence_refs=[project_ref],
                        claim_ids=["C1"],
                    )
                ]
            }
        )
        compile_calls = 0

        async def fake_provider(_context, *_args):
            return authored, config["model"]

        async def fake_proofreader(_context, *_args, **_kwargs):
            return papers.TeXProofreadResult(corrections=[]), config["model"]

        def unrelated_failure(_tex: str, **kwargs):
            nonlocal compile_calls
            compile_calls += 1
            if compile_calls == 1:
                return b"%PDF-initial-fixture"
            if diagnostics := kwargs.get("diagnostics"):
                diagnostics.append("error: report.tex: Missing $ inserted.")
            raise RuntimeError("Tectonic failed: Missing $ inserted.")

        async def run() -> None:
            with (
                patch.object(
                    papers, "auth_context", new=lambda: asyncio.sleep(0, result=credential)
                ),
                patch.object(
                    papers, "configuration", new=lambda **_kwargs: asyncio.sleep(0, result=config)
                ),
                patch.object(papers, "_provider", new=fake_provider),
                patch.object(papers, "_provider_structured", new=fake_proofreader),
                patch.object(papers, "_compile_pdf", new=unrelated_failure),
                mock_pdf_inspection(),
            ):
                await papers.generate(str(path), credential["identity"], view.project.id)

        try:
            asyncio.run(run())
        except ProjectError as exc:
            assert "Missing $ inserted" in str(exc)
        else:
            raise AssertionError("An unrelated TeX error must remain a recoverable failure")
        checkpoint = papers._load_work(str(path))
        assert checkpoint is not None
        assert checkpoint["one_shot_draft"]["diagrams"]
        assert compile_calls == 2, "The unsafe text-only fallback must not be attempted"
        assert papers.list_papers(str(path)) == []


def test_research_details_toggle_preserves_science_and_opt_in_diagnostics() -> None:
    """Extra diagnostics are opt-in; scientific caveats remain in both papers."""
    paper = draft()
    snapshot = "c" * 64
    obligation = [
        {
            "status": "Not listed by author; not presumed resolved",
            "source_refs": ["session:one"],
            "text": "Confirm the missing proof step.",
        }
    ]
    records = [
        {
            "source_ref": "session:one",
            "field": "skeptic_objections",
            "content": "This objection remains unresolved.",
        }
    ]
    opts = {
        "math_style": True,
        "obligation_reconciliation": obligation,
        "integrity_records": records,
    }
    concise = papers._tex(
        paper,
        ["A validator recorded an unsupported citation."],
        snapshot,
        include_research_details=False,
        **opts,
    )
    detailed = papers._tex(
        paper,
        ["A validator recorded an unsupported citation."],
        snapshot,
        include_research_details=True,
        **opts,
    )
    for required in (
        r"\begin{abstract}",
        r"\section{Interpretation}",
        r"\section{Open obligations}",
        r"\section{Verification status and limitations}",
        r"\section{Conclusion}",
        "This paper does not establish a formal proof.",
    ):
        assert required in concise and required in detailed, required
    for diagnostic in (
        "Claim status and evidence",
        "Claims discussed:",
        "Frozen obligation reconciliation",
        "Structured reasoning and review records",
        "Validation warnings",
        "Snapshot SHA-256",
        "Research style:",
        "About this paper",
    ):
        assert diagnostic not in concise, diagnostic
        assert diagnostic in detailed, diagnostic
    assert "Confirm the missing proof step." not in concise
    assert "Confirm the missing proof step." in detailed
    assert r"\section*{Authorship note}" in concise


def test_publication_paragraphs_math_and_bounded_optional_appendix() -> None:
    """Readable PDF prose without losing math or overflowing the evidence appendix."""
    source = " ".join(
        f"This is substantive statement {number}. It advances the argument." for number in range(32)
    )
    paragraphs = papers._publication_paragraphs(source)
    assert len(paragraphs) >= 2
    assert " ".join(paragraphs) == source

    math = papers._latex_prose(r"Use $\sum_{j=1}^k j^2$ and $\omega^3=1$.")
    assert r"$\sum_{j=1}^k j^2$" in math
    assert r"$\omega^3=1$" in math
    assert r"$\sum_{j=1}^k j^2$" in papers._latex_prose(r"$\sum_{j=1}^k j^2$")
    assert r"NF-$\kappa$B" in papers._latex_prose("NF-κB signaling")
    delta = r"$\delta=\beta_{46}-\beta_{40}$"
    integral = r"$P_i=\int_{1}^{6}N_i(t)\,dt$"
    assert delta in papers._latex_prose(delta)
    assert integral in papers._latex_prose(integral)

    paper = draft()
    sections = list(paper.sections)
    sections[0] = sections[0].model_copy(
        update={
            "heading": "3. Counting argument",
            "paragraphs": [
                "The construction satisfies the prescribed boundary condition.",
                "The next step requires a separate supporting argument.",
                source,
            ],
        }
    )
    paper = paper.model_copy(update={"sections": sections})
    integrity = [
        {
            "source_ref": f"session:{index}",
            "field": "proof_obligations",
            "content": {"excerpt": "An unresolved argument remains. " * 120},
        }
        for index in range(28)
    ]
    obligations = [
        {
            "text": f"Check the distinct boundary case {index}.",
            "source_refs": [f"session:{index}"],
            "status": "Not listed by author; not presumed resolved",
        }
        for index in range(28)
    ]
    tex = papers._tex(
        paper,
        [],
        "f" * 64,
        math_style=True,
        include_research_details=True,
        integrity_records=integrity,
        integrity_excerpts=True,
        obligation_reconciliation=obligations,
    )
    assert r"\section{Counting argument}" in tex
    assert r"\section{3. Counting argument}" not in tex
    assert (
        "The construction satisfies the prescribed boundary condition.\n\n"
        "The next step requires a separate supporting argument."
    ) in tex
    assert tex.count(r"\subsection{Research excerpt ") == 16
    assert "further research records" in tex
    assert "further distinct obligations" in tex
    assert r"\begin{longtable}" not in tex
    assert len(tex) < 50_000


def test_snapshot_ignores_elapsed_projection_but_tracks_saved_evidence() -> None:
    export = {
        "project": {"id": "snapshot-project", "title": "Snapshot stability"},
        "research_sessions": [
            {
                "id": "paused-session",
                "status": "paused",
                "elapsed_seconds": 10,
                "updated_at": "2026-10-29T01:00:00+00:00",
                "outcome": {"summary": "Saved outcome"},
                "artifacts": [{"id": "finding-1", "claim": "Saved claim"}],
            }
        ],
        "agentic_runs": [],
    }
    original = json.loads(json.dumps(export))
    with patch("sigma.api.export_project_view", side_effect=[export, export, export]):
        first, first_hash = papers._snapshot("unused")
        first_claim = next(
            source
            for source in first["sources"]
            if source["id"] == "artifact:paused-session:finding-1"
        )["data"]["claim"]
        export["research_sessions"][0]["elapsed_seconds"] = 45
        export["research_sessions"][0]["updated_at"] = "2026-10-29T03:00:00+00:00"
        second, second_hash = papers._snapshot("unused")
        export["research_sessions"][0]["artifacts"][0]["claim"] = "Changed saved claim"
        _third, third_hash = papers._snapshot("unused")

    assert first_hash == second_hash
    assert third_hash != second_hash
    session_source = next(source for source in second["sources"] if source["kind"] == "session")
    assert "elapsed_seconds" not in session_source["data"]
    assert "updated_at" not in session_source["data"]
    assert original["research_sessions"][0]["artifacts"][0]["claim"] == "Saved claim"
    assert first_claim == "Saved claim"


def test_api_disconnect_preserves_running_paper_until_explicit_cancel(path: Path) -> None:
    async def check() -> None:
        started = asyncio.Event()
        cancelled = asyncio.Event()
        credential = {"identity": "chatgpt:fixture", "mode": "chatgpt", "token": "fixture"}
        config = {
            "available": True,
            "binding": credential["identity"],
            "model": "gpt-6.1-sol",
            "reasoning_effort": "high",
        }

        async def slow_provider(*_args):
            started.set()
            try:
                await asyncio.sleep(20)
            finally:
                cancelled.set()

        queue = asyncio.Queue()
        body = {
            "path": str(path),
            "expected_project_id": inspect_project(path).project.id,
            "expected_binding": credential["identity"],
            "expected_snapshot_sha256": papers._snapshot(str(path))[1],
        }
        await queue.put(
            {"type": "http.request", "body": json.dumps(body).encode(), "more_body": False}
        )
        sent = []

        async def send(message):
            sent.append(message)

        scope = {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "POST",
            "scheme": "http",
            "path": "/api/projects/papers",
            "raw_path": b"/api/projects/papers",
            "query_string": b"",
            "root_path": "",
            "headers": [(b"host", b"testserver"), (b"content-type", b"application/json")],
            "server": ("testserver", 80),
            "client": ("127.0.0.1", 1234),
        }
        with (
            patch.object(papers, "auth_context", new=lambda: asyncio.sleep(0, result=credential)),
            patch.object(
                papers, "configuration", new=lambda **_kwargs: asyncio.sleep(0, result=config)
            ),
            patch.object(papers, "_provider", new=slow_provider),
        ):
            serving = asyncio.create_task(app(scope, queue.get, send))
            await asyncio.wait_for(started.wait(), timeout=2)
            await queue.put({"type": "http.disconnect"})
            await asyncio.wait_for(serving, timeout=2)
            assert not cancelled.is_set(), "Browser disconnect must not cancel the provider"
            active_progress = papers.progress_status(str(path))
            assert active_progress is not None and active_progress["status"] == "active"
            # A separate authenticated request, not the SSE connection, cancels.
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://testserver"
            ) as client:
                response = await client.post(
                    "/api/projects/papers/cancel",
                    json={
                        "path": str(path),
                        "expected_project_id": body["expected_project_id"],
                        "expected_binding": credential["identity"],
                    },
                )
            assert response.status_code == 200
            assert response.json()["cancelled"] is True
            await asyncio.wait_for(cancelled.wait(), timeout=2)
            await asyncio.sleep(0)
        assert papers.list_papers(str(path)) == []
        assert not papers._gate.locked()
        cancelled_progress = papers.progress_status(str(path))
        assert cancelled_progress is not None and cancelled_progress["status"] == "cancelled"

    asyncio.run(check())


def test_api_paper_stream_reports_progress_and_completion() -> None:
    async def check() -> None:
        with TemporaryDirectory() as temporary:
            path = Path(temporary) / "streamed.sigma"
            initialize_project(path, "Streamed paper", "A paper question")
            project_id = inspect_project(path).project.id

            async def fake_generate(
                _path,
                _binding,
                _project_id,
                *,
                progress,
                force_long_form,
                expected_snapshot_sha256,
                include_research_details,
                include_claim_details,
                include_validation_notes,
                include_research_excerpts,
                include_diagrams,
            ):
                assert include_research_details is False
                assert include_claim_details is False
                assert include_validation_notes is False
                assert include_research_excerpts is False
                assert include_diagrams is True
                await progress(
                    {
                        "type": "progress",
                        "state": "milestone",
                        "stage": "evidence",
                        "current": 1,
                        "total": 2,
                        "started_at": "2026-01-01T00:00:00+00:00",
                        "elapsed_seconds": 1,
                    }
                )
                await asyncio.sleep(1.1)
                assert force_long_form is False
                assert len(expected_snapshot_sha256) == 64
                return {"paper_id": "fixture-paper"}

            heartbeat = {
                "status": "active",
                "stage": "evidence",
                "current": 1,
                "total": 2,
                "started_at": "2026-01-01T00:00:00+00:00",
                "elapsed_seconds": 2,
            }
            with (
                patch.object(papers, "generate", new=fake_generate),
                patch.object(papers, "progress_status", return_value=heartbeat),
            ):
                async with httpx.AsyncClient(
                    transport=httpx.ASGITransport(app=app), base_url="http://testserver"
                ) as client:
                    response = await client.post(
                        "/api/projects/papers",
                        json={
                            "path": str(path),
                            "expected_project_id": project_id,
                            "expected_binding": "chatgpt:fixture",
                            "expected_snapshot_sha256": "a" * 64,
                        },
                    )
            assert response.status_code == 200
            assert response.headers["content-type"].startswith("text/event-stream")
            assert '"stage":"evidence"' in response.text
            assert '"current":1' in response.text and '"total":2' in response.text
            assert '"type":"heartbeat"' in response.text
            assert '"elapsed_seconds":2' in response.text
            assert '"type": "complete"' in response.text or '"type":"complete"' in response.text

            async def stale_preflight(*_args, **_kwargs):
                raise papers.PaperSnapshotConflict("Research changed after paper preflight.")

            with patch.object(papers, "generate", new=stale_preflight):
                async with httpx.AsyncClient(
                    transport=httpx.ASGITransport(app=app), base_url="http://testserver"
                ) as client:
                    response = await client.post(
                        "/api/projects/papers",
                        json={
                            "path": str(path),
                            "expected_project_id": project_id,
                            "expected_binding": "chatgpt:fixture",
                            "expected_snapshot_sha256": "0" * 64,
                        },
                    )
            assert response.status_code == 200
            assert (
                '"provider_calls_attempted": 0' in response.text
                or '"provider_calls_attempted":0' in response.text
            )

    asyncio.run(check())


def test_paper_progress_endpoint_recovers_interrupted_checkpoint() -> None:
    async def check() -> None:
        with TemporaryDirectory() as temporary:
            path = Path(temporary) / "interrupted.sigma"
            view = initialize_project(path, "Interrupted paper", "Recover saved paper progress")
            state = papers._new_work("a" * 64, view.project.id, "b" * 64, "gpt-fixture", "high")
            state["progress"] = {
                "run_id": "c" * 32,
                "status": "running",
                "stage": "sections",
                "current": 2,
                "total": 4,
                "started_at": "2026-01-01T00:00:00+00:00",
                "updated_at": "2026-01-01T00:00:45+00:00",
                "elapsed_seconds": 45,
            }
            papers._save_work(str(path), state)
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://testserver"
            ) as client:
                response = await client.get(
                    "/api/projects/papers/progress", params={"path": str(path)}
                )
            assert response.status_code == 200, response.text
            assert response.json()["progress"] == {
                "status": "interrupted",
                "stage": "sections",
                "current": 2,
                "total": 4,
                "started_at": "2026-01-01T00:00:00+00:00",
                "elapsed_seconds": 45,
            }

    asyncio.run(check())


def test_restart_uses_current_evidence_and_is_idempotent() -> None:
    """A stale dialog preflight must never trap a confirmed reset."""
    with TemporaryDirectory() as temporary:
        path = Path(temporary) / "stale-restart.sigma"
        view = initialize_project(path, "Stale restart", "Preserve saved research")
        current_snapshot_sha256 = papers._snapshot(str(path))[1]
        old_snapshot_sha256 = "a" * 64
        stale_dialog_sha256 = "b" * 64
        assert current_snapshot_sha256 not in {old_snapshot_sha256, stale_dialog_sha256}

        credential = {"mode": "chatgpt", "identity": "chatgpt:fixture", "token": "fixture"}
        config = {"available": True, "model": "gpt-fixture", "reasoning_effort": "high"}
        old_history = [
            {
                "provider_calls_attempted": 2,
                "snapshot_sha256": "c" * 64,
                "model": "previous-model",
                "reset_at": "2026-10-29T00:00:00+00:00",
            }
        ]
        checkpoint = papers._new_work(
            old_snapshot_sha256,
            view.project.id,
            "d" * 64,
            "previous-model",
            "low",
            provider_calls_total=3,
            prior_runs=old_history,
        )
        checkpoint["provider_calls"] = 1
        checkpoint["next_batch"] = 1
        papers._save_work(str(path), checkpoint)

        async def fake_auth():
            return credential

        async def fake_configuration(**_kwargs):
            return config

        async def check() -> None:
            with (
                patch.object(papers, "auth_context", new=fake_auth),
                patch.object(papers, "configuration", new=fake_configuration),
                patch.object(papers, "_provider", side_effect=AssertionError("no inference")),
                patch.object(
                    papers,
                    "_provider_structured",
                    side_effect=AssertionError("no inference"),
                ),
            ):
                async with httpx.AsyncClient(
                    transport=httpx.ASGITransport(app=app),
                    base_url="http://testserver",
                ) as client:
                    body = {
                        "path": str(path),
                        "expected_project_id": view.project.id,
                        "expected_binding": credential["identity"],
                        "expected_snapshot_sha256": stale_dialog_sha256,
                        "confirm_restart": True,
                        "long_form": True,
                    }
                    wrong_project = await client.post(
                        "/api/projects/papers/restart",
                        json={**body, "expected_project_id": "wrong-project"},
                    )
                    assert wrong_project.status_code != 200
                    unchanged = papers._load_work(str(path))
                    assert unchanged is not None
                    assert unchanged["provider_calls"] == 1

                    response = await client.post("/api/projects/papers/restart", json=body)
                    assert response.status_code == 200, response.text
                    result = response.json()
                    assert result["snapshot_sha256"] == current_snapshot_sha256
                    assert result["evidence_updated_since_preflight"] is True
                    assert result["provider_calls_previous_runs"] == 3
                    assert result["provider_calls_attempted"] == 0

                    reset = papers._load_work(str(path))
                    assert reset is not None
                    assert reset["snapshot_sha256"] == current_snapshot_sha256
                    assert reset["explicit_restart_pending"] is True
                    assert reset["provider_calls"] == 0
                    assert reset["provider_calls_total"] == 3
                    assert len(reset["prior_runs"]) == 2

                    repeated = await client.post("/api/projects/papers/restart", json=body)
                    assert repeated.status_code == 200, repeated.text
                    assert repeated.json()["provider_calls_previous_runs"] == 3
                    reset_again = papers._load_work(str(path))
                    assert reset_again is not None
                    assert len(reset_again["prior_runs"]) == 2
                    assert reset_again["provider_calls_total"] == 3
                    assert reset_again["snapshot_sha256"] == current_snapshot_sha256
                    assert papers.progress_status(str(path)) is None

                    preflight = papers.preflight(
                        str(path),
                        force_long_form=True,
                        expected_project_id=view.project.id,
                        expected_binding=credential["identity"],
                        mode=credential["mode"],
                        model=config["model"],
                        reasoning_effort=config["reasoning_effort"],
                    )
                    assert preflight["resume_available"] is True
                    assert preflight["provider_calls_attempted"] == 0

        asyncio.run(check())


def test_explicit_restart_checkpoint_migrates_and_rebinds_safely() -> None:
    with TemporaryDirectory() as temporary:
        path = Path(temporary) / "restart.sigma"
        view = initialize_project(path, "Restarted paper", "A saved evidence question")
        current_snapshot = papers._snapshot(str(path))[1]
        prior_runs = [
            {
                "provider_calls_attempted": 5,
                "snapshot_sha256": "a" * 64,
                "model": "old-model",
                "reset_at": "2026-10-29T00:00:00+00:00",
            }
        ]
        checkpoint = papers._new_work(
            "b" * 64,
            view.project.id,
            "c" * 64,
            "old-model",
            "low",
            provider_calls_total=5,
            prior_runs=prior_runs,
        )
        checkpoint["explicit_restart_pending"] = True
        papers._save_work(str(path), checkpoint)
        loaded = papers._load_work(str(path))
        assert loaded is not None and loaded["explicit_restart_pending"] is True

        credential = {"identity": "fixture-credential", "mode": "api_key", "token": "unused"}
        config = {
            "available": True,
            "model": "gpt-fixture",
            "reasoning_effort": "high",
        }
        preview = papers.preflight(
            str(path),
            force_long_form=True,
            expected_project_id=view.project.id,
            expected_binding=credential["identity"],
            mode=credential["mode"],
            model=config["model"],
            reasoning_effort=config["reasoning_effort"],
        )
        assert preview["resume_available"] is True
        assert preview["provider_calls_attempted"] == 0
        assert preview["provider_calls_previous_runs"] == 5

        rebound: dict[str, Any] = {}

        async def fake_long_draft(_package, _binding, _config, state, _save_state, *args, **kwargs):
            rebound.update(state)
            return draft(f"project:{view.project.id}"), 0, 0

        async def current_credential():
            return credential

        async def current_configuration(*_args, **_kwargs):
            return config

        with (
            patch.object(papers, "auth_context", new=current_credential),
            patch.object(papers, "configuration", new=current_configuration),
            patch.object(papers, "_generate_long_draft", new=fake_long_draft),
            patch.object(papers, "_compile_pdf", return_value=b"%PDF-fixture"),
            mock_pdf_inspection(),
        ):
            result = asyncio.run(
                papers.generate(
                    str(path),
                    credential["identity"],
                    view.project.id,
                    force_long_form=True,
                    expected_snapshot_sha256=current_snapshot,
                )
            )

        assert result["title"] == "An evidence-bound exploratory note"
        assert rebound["snapshot_sha256"] == current_snapshot
        assert rebound["model"] == config["model"]
        assert rebound["reasoning_effort"] == config["reasoning_effort"]
        assert rebound["provider_calls"] == 0
        assert rebound["provider_calls_total"] == 5
        assert rebound["prior_runs"] == prior_runs
        assert not rebound.get("explicit_restart_pending")
        assert papers._load_work(str(path)) is None


def test_evidence_envelope_budget_resumes_without_repacking() -> None:
    """A batch accepted during packing must be accepted before dispatch too.

    The batch_id field adds a few bytes beyond the 48 KB fields budget.
    Repacking would shift indices after a previously paid checkpoint, so
    preserve the original field groups and next_batch cursor.
    """
    source_ref = "project:fixture"
    fields = [
        {
            "field_ref": f"{i + 1:064x}",
            "source_ref": source_ref,
            "field": f"/data/value{i}",
            "value": "x" * 9_500 if i < 4 else "",
        }
        for i in range(5)
    ]
    batch = {"batch_id": "E2", "fields": fields}
    extra = 48_007 - len(papers._json(batch))
    assert 0 < extra < 12_000
    fields[-1]["value"] = "x" * extra
    assert len(papers._json(batch)) == 48_007
    assert len(papers._json({"fields": fields})) <= papers.MAX_PROVIDER_INPUT_BYTES
    limit = papers._evidence_input_limit(batch)
    assert limit > papers.MAX_PROVIDER_INPUT_BYTES
    assert 48_007 <= limit
    assert len(papers._provider_input_text(batch, "sigma_paper_evidence_batch", limit)) == 48_007

    first_batch = {
        "batch_id": "E1",
        "fields": [
            {
                "field_ref": "0" * 64,
                "source_ref": source_ref,
                "field": "/data/prior",
                "value": "already indexed",
            }
        ],
    }
    package = {
        "schema": "sigma-paper-evidence-v2",
        "project_id": "fixture",
        "sources": [{"id": source_ref, "kind": "project", "data": {"title": "Fixture"}}],
    }
    state = papers._new_work("a" * 64, "fixture", "b" * 64, "fixture-model", "high")
    state["next_batch"] = 1
    state["provider_calls"] = 1
    state["provider_calls_total"] = 1
    seen: list[str] = []

    async def fake_provider(
        input_value, _binding, _config, *, schema_name, max_input_bytes, **_kwargs
    ):
        seen.append(schema_name)
        if schema_name == "sigma_paper_evidence_batch":
            assert input_value is batch  # E1 is not replayed.
            assert max_input_bytes == limit
            return papers.EvidenceBatchResult(
                notes=[],
                conflicts_or_gaps=[],
                covered_field_refs=[field["field_ref"] for field in fields],
                omitted_fields=[],
            ), "fixture-model"
        raise ProjectError("fixture stop before paper planning")

    async def check() -> None:
        with (
            patch.object(papers, "_evidence_batches", return_value=[first_batch, batch]),
            patch.object(papers, "_provider_structured", new=fake_provider),
        ):
            try:
                await papers._generate_long_draft(
                    package,
                    {"identity": "fixture", "token": "fixture", "mode": "chatgpt"},
                    {"model": "fixture-model", "reasoning_effort": "high"},
                    state,
                    lambda _state: None,
                )
            except ProjectError as exc:
                assert "fixture stop before paper planning" in str(exc)
            else:
                raise AssertionError("Fixture must stop after completing E2")

    asyncio.run(check())
    assert seen[:2] == ["sigma_paper_evidence_batch", "sigma_long_paper_plan"]
    assert seen[2] == "sigma_long_paper_section"
    assert state["next_batch"] == 2
    assert state["provider_calls"] == 4  # E1 + E2 + failed plan + first section.
    assert state["plan"]  # Planning failure preserved a local source-linked outline.


def test_long_paper_outline_does_not_duplicate_large_evidence_reference_catalog() -> None:
    notes = [
        papers.EvidenceNote(
            statement=f"Saved evidence note {group:03d}",
            kind="result",
            evidence_refs=[f"{group * 12 + offset:064x}" for offset in range(12)],
        ).model_dump()
        for group in range(180)
    ]
    refs = sorted({reference for note in notes for reference in note["evidence_refs"]})
    plan_input = papers._long_plan_input(
        {"title": "Fixture", "investigation_type": "experimental", "difficulty": "hard"},
        notes,
        len(refs),
        len(notes),
    )
    # This bounded evidence index is valid by itself. The old plan shape copied
    # every 64-byte reference into a second list, pushing the input beyond 220 KB.
    assert len(papers._json(notes)) < papers.MAX_PLANNER_INDEX_BYTES
    legacy_input = {**plan_input, "indexed_source_ids": refs}
    assert len(papers._json(legacy_input)) > 220_000
    assert len(papers._json(plan_input)) <= 220_000
    assert "indexed_source_ids" not in plan_input
    assert {
        reference for note in plan_input["evidence_index"] for reference in note["evidence_refs"]
    } == set(refs)

    async def over_limit() -> None:
        with patch.object(
            papers.httpx,
            "AsyncClient",
            side_effect=AssertionError("oversized input must fail before dispatch"),
        ):
            try:
                await papers._provider_structured(
                    "input exceeds bound",
                    {"mode": "api_key", "token": "fixture"},
                    {"model": "fixture", "reasoning_effort": "high"},
                    instructions="fixture",
                    schema_name="sigma_long_paper_plan",
                    response_model=papers.LongPaperPlan,
                    max_input_bytes=4,
                )
            except ProjectError as exc:
                assert "Paper planning input is 21 bytes" in str(exc), str(exc)
                assert "4-byte bound" in str(exc)
            else:
                raise AssertionError("Oversized paper planning input must be rejected")

    async def rejects_before_counting_a_provider_call() -> None:
        project_id = "fixture-project"
        source_id = f"project:{project_id}"
        package = {
            "schema": "sigma-paper-evidence-v2",
            "project_id": project_id,
            "sources": [{"id": source_id, "kind": "project", "data": {"title": "Fixture"}}],
        }
        state = papers._new_work("a" * 64, project_id, "b" * 64, "fixture", "high")
        state.update(
            {
                "evidence_indexed": True,
                "evidence_notes": [
                    papers.EvidenceNote(
                        statement="A saved evidence note.", kind="result", evidence_refs=[source_id]
                    ).model_dump()
                ],
            }
        )

        async def section_only(input_value, _binding, _config, *, schema_name, **_kwargs):
            assert schema_name == "sigma_long_paper_section"
            return papers.LongSectionDraft(
                paragraphs=["The saved evidence requires additional verification."]
            ), "fixture"

        with (
            patch.object(papers, "_long_plan_input", return_value={"padding": "x" * 220_000}),
            patch.object(papers, "_provider_structured", new=section_only),
        ):
            generated, calls, _ = await papers._generate_long_draft(
                package,
                {"mode": "api_key", "identity": "fixture", "token": "unused"},
                {"model": "fixture", "reasoning_effort": "high"},
                state,
                lambda _state: None,
            )
        assert generated.sections
        assert state["plan"]  # Oversized planning input falls back locally.
        assert calls == len(generated.sections)  # No planning provider call was sent.

    asyncio.run(over_limit())
    asyncio.run(rejects_before_counting_a_provider_call())


def test_long_index_reduction_resumes_and_preserves_session_conflicts() -> None:
    async def check() -> None:
        project_id = "fixture-project"
        package = {
            "schema": "sigma-paper-evidence-v2",
            "project_id": project_id,
            "sources": [
                {"id": f"project:{project_id}", "kind": "project", "data": {"title": "Fixture"}},
                {
                    "id": "session:positive",
                    "kind": "session",
                    "data": {"finding": "Condition A showed regeneration after treatment."},
                },
                {
                    "id": "session:negative",
                    "kind": "session",
                    "data": {"finding": "Condition B showed no regeneration after treatment."},
                },
            ],
        }
        state = papers._new_work("a" * 64, project_id, "b" * 64, "gpt-fixture", "high")
        config = {"model": "gpt-fixture"}
        reductions = 0
        cancel_second_reduction = True
        stage_events: list[tuple[str, int | None, int | None, str]] = []
        batch_count = len(papers._evidence_batches(package))
        assert batch_count == 1

        async def fake_structured(input_value, _binding, _config, *, response_model, **kwargs):
            nonlocal reductions, cancel_second_reduction
            schema_name = kwargs.get("schema_name")
            if response_model is papers.EvidenceBatchResult:
                if schema_name == "sigma_paper_evidence_reduction":
                    reductions += 1
                    if reductions == 2 and cancel_second_reduction:
                        cancel_second_reduction = False
                        raise asyncio.CancelledError()
                    refs = list(
                        dict.fromkeys(ref for note in input_value for ref in note["evidence_refs"])
                    )
                    return (
                        papers.EvidenceBatchResult(
                            notes=[]
                            if "session:negative" in refs
                            else [
                                papers.EvidenceNote(
                                    statement=("Reduced while preserving source identities. " * 12)[
                                        :450
                                    ],
                                    kind="context",
                                    evidence_refs=refs[:12],
                                )
                            ],
                            conflicts_or_gaps=[],
                        ),
                        config["model"],
                    )
                fields = input_value["fields"]
                batch_refs = list(dict.fromkeys(field["source_ref"] for field in fields))
                refs = batch_refs[:3]
                return (
                    papers.EvidenceBatchResult(
                        notes=[
                            papers.EvidenceNote(
                                statement=(f"Distinct saved finding from {ref}. " * 10)[:450],
                                kind="negative" if ref.endswith("negative") else "result",
                                evidence_refs=[ref],
                            )
                            for ref in refs
                        ],
                        conflicts_or_gaps=(
                            [
                                papers.EvidenceConflict(
                                    statement="Separate sessions report positive regeneration and no regeneration under different recorded conditions.",
                                    evidence_refs=["session:positive", "session:negative"],
                                )
                            ]
                            if {"session:positive", "session:negative"}.issubset(batch_refs)
                            else []
                        ),
                        covered_field_refs=[field["field_ref"] for field in fields],
                    ),
                    config["model"],
                )
            if response_model is papers.LongPaperPlan:
                ref = f"project:{project_id}"
                base = draft(ref)
                return (
                    papers.LongPaperPlan(
                        title="Contrasting Session Evidence",
                        abstract=base.abstract,
                        abstract_claim_ids=["C1"],
                        problem_framing=base.problem_framing,
                        problem_framing_claim_ids=["C1"],
                        methods=base.methods,
                        methods_claim_ids=["C1"],
                        claims=base.claims,
                        sections=[
                            papers.LongSectionPlan(
                                heading="Positive session",
                                purpose="Describe the recorded positive finding and its context.",
                                evidence_refs=[ref],
                                claim_ids=["C1"],
                            ),
                            papers.LongSectionPlan(
                                heading="Negative session",
                                purpose="Describe the recorded negative finding and its context.",
                                evidence_refs=[ref],
                                claim_ids=["C1"],
                            ),
                        ],
                        limitations=base.limitations,
                        open_obligations=base.open_obligations,
                        conclusions=base.conclusions,
                        conclusion_claim_ids=["C1"],
                        validation_warnings=[],
                    ),
                    config["model"],
                )
            return papers.LongSectionDraft(
                paragraphs=["Source-linked section fixture prose."]
            ), config["model"]

        saved = []

        async def record_progress(
            stage: papers.PaperProgressStage,
            current: int | None,
            total: int | None,
            state: papers.PaperProgressState = "active",
            *,
            detail: str | None = None,
        ) -> None:
            del detail
            stage_events.append((stage, current, total, state))

        async def run():
            return await papers._generate_long_draft(
                package,
                {"mode": "chatgpt", "identity": "fixture", "token": "unused"},
                config,
                state,
                lambda current: saved.append(json.loads(papers._json(current))),
                record_progress,
            )

        with (
            patch.object(papers, "_provider_structured", new=fake_structured),
            patch.object(papers, "MAX_PLANNER_INDEX_BYTES", 1_000),
            patch.object(papers, "MAX_REDUCTION_GROUP_BYTES", 1_500),
        ):
            try:
                await run()
            except asyncio.CancelledError:
                pass
            else:
                raise AssertionError("The second reduction group should be interrupted")
            assert state["reduction_next_group"] == 1
            extracted = [
                papers.EvidenceNote.model_validate(item) for item in state["reduction_input"]
            ]
            assert any(
                note.kind == "result" and note.evidence_refs == ["session:positive"]
                for note in extracted
            )
            assert any(
                note.kind == "negative" and note.evidence_refs == ["session:negative"]
                for note in extracted
            )
            reductions_before_resume = reductions
            draft_result, calls, _ = await run()
        assert reductions - reductions_before_resume == 1
        assert calls == state["provider_calls"]
        assert state["reduction_source_refs_omitted"] == ["session:negative"]
        assert state["reduction_note_compaction_events"] >= 1
        assert any("potential conflict" in item for item in draft_result.validation_warnings)
        assert any(
            "omitted notes covering 1 saved source" in item
            for item in draft_result.validation_warnings
        )
        assert len(draft_result.sections) == 2
        assert saved
        evidence = [item for item in stage_events if item[0] == "evidence"]
        assert evidence == [("evidence", 1, 1, "active"), ("evidence", 1, 1, "milestone")]
        sections = [item for item in stage_events if item[0] == "sections"]
        assert [item[1:3] for item in sections if item[3] == "active"] == [(1, 2), (2, 2)]
        assert any(item[0] == "planning" and item[3] == "active" for item in stage_events)
        assert any(item[0] == "consolidation" and item[3] == "active" for item in stage_events)
        assert all(item[0] != "index" for item in stage_events)

    asyncio.run(check())


def test_xenopus_sample_long_snapshot_uses_bounded_sections() -> None:
    sample_path = (
        Path(__file__).resolve().parents[1] / "samples/xenopus-tail-regeneration/project.json"
    )
    sample = json.loads(sample_path.read_text(encoding="utf-8"))
    with TemporaryDirectory() as temporary:
        path = Path(temporary) / "xenopus-v2.sigma"
        initialize_project(path, sample["title"] + " v2", sample["problem"])
        project_view = inspect_project(path)
        base_export = {
            "project": {
                "id": project_view.project.id,
                "title": project_view.project.title,
                "problem": sample["problem"],
                "strategies": [],
            },
            "research_sessions": [],
            "agentic_runs": [
                {"run_id": "large-experiment", "steps": [{"step_id": "step-1", "output": ""}]}
            ],
        }
        base_export["research_sessions"] = [
            {
                "id": "session-positive",
                "status": "completed",
                "finding": "A trial group showed tail regeneration under the recorded condition.",
            },
            {
                "id": "session-negative",
                "status": "completed",
                "finding": "A separate trial group showed no tail regeneration under its recorded condition.",
            },
        ]
        with patch("sigma.api.export_project_view", return_value=base_export):
            empty_snapshot, _ = papers._snapshot(str(path))
        target_bytes = 483_485
        filler_size = target_bytes - len(papers._json(empty_snapshot))
        assert filler_size > 0
        base_export["agentic_runs"][0]["steps"][0]["output"] = "x" * filler_size
        with patch("sigma.api.export_project_view", return_value=base_export):
            snapshot, _ = papers._snapshot(str(path))
        assert len(papers._json(snapshot)) == target_bytes
        batch_count = len(papers._evidence_batches(snapshot))
        assert batch_count > 1
        with patch("sigma.api.export_project_view", return_value=base_export):
            preflight = papers.preflight(str(path))
        assert preflight["long_form"] is True
        assert preflight["snapshot_bytes"] == target_bytes
        assert preflight["evidence_batches"] == batch_count

        credential = {"identity": "chatgpt:fixture", "mode": "chatgpt", "token": "fixture"}
        config = {
            "available": True,
            "binding": credential["identity"],
            "model": "gpt-6.1-sol",
            "reasoning_effort": "high",
        }
        with (
            patch("sigma.api.export_project_view", return_value=base_export),
            patch.object(papers, "auth_context", new=lambda: asyncio.sleep(0, result=credential)),
            patch.object(
                papers, "configuration", new=lambda **_kwargs: asyncio.sleep(0, result=config)
            ),
            patch.object(
                papers,
                "_provider_structured",
                side_effect=AssertionError("preflight mismatch must stop before provider use"),
            ),
        ):
            try:
                asyncio.run(
                    papers.generate(
                        str(path),
                        credential["identity"],
                        project_view.project.id,
                        expected_snapshot_sha256="0" * 64,
                    )
                )
            except ProjectError as exc:
                assert "changed after paper preflight" in str(exc)
            else:
                raise AssertionError("Changed research must invalidate the preflight confirmation")
        provider_calls = 0
        batch_invocations: dict[str, int] = {}
        cancel_second_batch_once = True
        fail_first_section = True
        ref = f"project:{project_view.project.id}"

        async def fake_structured(input_value, _binding, _config, *, response_model, **_kwargs):
            nonlocal provider_calls, fail_first_section, cancel_second_batch_once
            provider_calls += 1
            if response_model is papers.EvidenceBatchResult:
                batch_id = input_value["batch_id"]
                batch_invocations[batch_id] = batch_invocations.get(batch_id, 0) + 1
                if input_value.get("batch_id") == "E2" and cancel_second_batch_once:
                    cancel_second_batch_once = False
                    raise asyncio.CancelledError()
                batch_refs = sorted({field["source_ref"] for field in input_value["fields"]})
                batch_fields = input_value["fields"]
                session_refs = [ref for ref in batch_refs if ref.startswith("session:")]
                return (
                    papers.EvidenceBatchResult(
                        notes=[
                            papers.EvidenceNote(
                                statement=f"The saved record in {source_ref} contains a distinct experimental finding.",
                                kind="context",
                                evidence_refs=[source_ref],
                            )
                            for source_ref in batch_refs[:3]
                        ],
                        conflicts_or_gaps=(
                            [
                                papers.EvidenceConflict(
                                    statement="Separate sessions report a positive regeneration finding and a negative no-regeneration finding; retain both conditions and source identities.",
                                    evidence_refs=session_refs[:2],
                                )
                            ]
                            if len(session_refs) > 1
                            else [],
                        )[0],
                        covered_field_refs=[field["field_ref"] for field in batch_fields[1:]],
                        omitted_fields=(
                            [
                                papers.OmittedEvidenceField(
                                    field_ref=batch_fields[0]["field_ref"],
                                    reason="The fixture marks one field as omitted for coverage-ledger regression.",
                                )
                            ]
                            if batch_fields
                            else []
                        ),
                    ),
                    config["model"],
                )
            if response_model is papers.LongPaperPlan:
                base = draft(ref)
                return (
                    papers.LongPaperPlan(
                        title="A Bounded Long-Form Xenopus Research Paper",
                        abstract=base.abstract,
                        abstract_claim_ids=["C1"],
                        problem_framing=base.problem_framing,
                        problem_framing_claim_ids=["C1"],
                        methods=base.methods,
                        methods_claim_ids=["C1"],
                        claims=base.claims,
                        sections=[
                            papers.LongSectionPlan(
                                heading="Evidence inventory",
                                purpose="Describe the saved source records and their scope.",
                                evidence_refs=[ref],
                                claim_ids=["C1"],
                            ),
                            papers.LongSectionPlan(
                                heading="Experimental interpretation",
                                purpose="Explain the supported interpretation and its limits.",
                                evidence_refs=[ref],
                                claim_ids=["C1"],
                            ),
                        ],
                        limitations=base.limitations,
                        open_obligations=base.open_obligations,
                        conclusions=base.conclusions,
                        conclusion_claim_ids=["C1"],
                        validation_warnings=[],
                    ),
                    config["model"],
                )
            if fail_first_section:
                fail_first_section = False
                raise ProjectError("fixture interruption after the outline was saved")
            return (
                papers.LongSectionDraft(
                    paragraphs=["The saved experimental record is discussed with its limitations."]
                ),
                config["model"],
            )

        with (
            patch("sigma.api.export_project_view", return_value=base_export),
            patch.object(papers, "auth_context", new=lambda: asyncio.sleep(0, result=credential)),
            patch.object(
                papers, "configuration", new=lambda **_kwargs: asyncio.sleep(0, result=config)
            ),
            patch.object(papers, "_provider_structured", new=fake_structured),
            patch.object(papers, "_compile_pdf", new=lambda _tex, **_kwargs: b"%PDF-fixture"),
            mock_pdf_inspection(),
        ):
            try:
                asyncio.run(papers.generate(str(path), credential["identity"]))
            except asyncio.CancelledError:
                pass
            else:
                raise AssertionError("The second evidence batch should be cancelled")
            partial_batch_checkpoint = papers._load_work(str(path))
            assert partial_batch_checkpoint is not None
            assert partial_batch_checkpoint["next_batch"] == 1
            completed_batch_calls = partial_batch_checkpoint["provider_calls"]
            try:
                asyncio.run(papers.generate(str(path), credential["identity"]))
            except ProjectError as exc:
                assert "fixture interruption" in str(exc)
            else:
                raise AssertionError("The fixture should interrupt after saving a section plan")
            checkpoint = papers._load_work(str(path))
            assert checkpoint is not None and checkpoint["plan"]
            assert checkpoint["next_batch"] == len(papers._evidence_batches(snapshot))
            assert batch_invocations["E1"] == 1
            assert batch_invocations["E2"] == 2
            assert papers.list_papers(str(path)) == []
            resume = papers.preflight(
                str(path),
                force_long_form=True,
                expected_project_id=project_view.project.id,
                expected_binding=credential["identity"],
                mode=credential["mode"],
                model=config["model"],
                reasoning_effort=config["reasoning_effort"],
            )
            assert resume["resume_available"] is True
            assert resume["completed_batches"] == batch_count
            assert resume["outline_complete"] is True
            assert resume["completed_sections"] == 0
            assert resume["provider_calls_attempted"] == checkpoint["provider_calls"]

            checkpoint["provider_calls"] = papers.MAX_LONG_PAPER_CALLS
            checkpoint["provider_calls_total"] = papers.MAX_LONG_PAPER_CALLS
            papers._save_work(str(path), checkpoint)
            exhausted_call_count = provider_calls
            try:
                asyncio.run(papers.generate(str(path), credential["identity"]))
            except ProjectError as exc:
                assert "bounded provider-call budget" in str(exc)
            else:
                raise AssertionError("An exhausted checkpoint must stop before another call")
            assert provider_calls == exhausted_call_count

            restarted = asyncio.run(
                papers.restart_work(
                    str(path),
                    project_view.project.id,
                    credential["identity"],
                    papers._snapshot(str(path))[1],
                    True,
                )
            )
            assert restarted["provider_calls_previous_runs"] == papers.MAX_LONG_PAPER_CALLS
            reset_preflight = papers.preflight(
                str(path),
                force_long_form=True,
                expected_project_id=project_view.project.id,
                expected_binding=credential["identity"],
                mode=credential["mode"],
                model=config["model"],
                reasoning_effort=config["reasoning_effort"],
            )
            assert reset_preflight["resume_available"] is True
            assert reset_preflight["provider_calls_attempted"] == 0
            assert reset_preflight["provider_calls_previous_runs"] == papers.MAX_LONG_PAPER_CALLS
            calls_at_restart = provider_calls
            compile_attempts = 0

            def fail_compile_once(_tex, **_kwargs):
                nonlocal compile_attempts
                compile_attempts += 1
                if compile_attempts == 1:
                    raise RuntimeError("fixture TeX compilation failure")
                return b"%PDF-fixture"

            try:
                with (
                    patch.object(papers, "_compile_pdf", new=fail_compile_once),
                    mock_pdf_inspection(),
                ):
                    asyncio.run(papers.generate(str(path), credential["identity"]))
            except ProjectError as exc:
                assert "fixture TeX compilation failure" in str(exc)
            else:
                raise AssertionError("The injected TeX compilation failure must be reported")
            calls_after_compile_failure = provider_calls
            authored_checkpoint = papers._load_work(str(path))
            assert authored_checkpoint is not None
            assert len(authored_checkpoint["section_drafts"]) == 2

            try:
                with patch.object(
                    papers, "_save", side_effect=ProjectError("fixture publication failure")
                ):
                    asyncio.run(papers.generate(str(path), credential["identity"]))
            except ProjectError as exc:
                assert "fixture publication failure" in str(exc)
            else:
                raise AssertionError("The injected publication failure must be reported")
            assert provider_calls == calls_after_compile_failure
            assert papers._load_work(str(path)) is not None
            result = asyncio.run(papers.generate(str(path), credential["identity"]))

        saved = papers.get_paper(str(path), result["paper_id"])
        assert saved["snapshot_sha256"] == result["snapshot_sha256"]
        assert len(papers._json(saved["snapshot"])) == target_bytes
        assert saved["generation"]["long_form"] is True
        assert saved["generation"]["call_limit"] == (
            papers.MAX_LONG_PAPER_CALLS + papers.MAX_PROOFREAD_CALLS
        )
        assert saved["generation"]["provider_calls_attempted"] == provider_calls - calls_at_restart
        assert saved["generation"]["evidence_fields_omitted"] == batch_count
        assert len(saved["generation"]["omitted_evidence"]) == batch_count
        assert saved["generation"]["evidence_conflict_note_count"] >= 1
        assert any(
            conflict["evidence_refs"] == ["session:positive", "session:negative"]
            for conflict in saved["generation"]["evidence_conflicts"]
        )
        assert (
            saved["generation"]["provider_calls_lifetime_total"]
            == papers.MAX_LONG_PAPER_CALLS + provider_calls - calls_at_restart
        )
        assert saved["generation"]["provider_calls_prior_runs"] == papers.MAX_LONG_PAPER_CALLS
        assert saved["generation"]["omitted_evidence"][0]["field_ref"]
        assert saved["generation"]["omitted_evidence"][0]["reason"]
        assert saved["generation"]["material_evidence_omissions"]
        assert saved["draft"]["claims"][0]["status"] == "unresolved"
        assert saved["draft"]["abstract"].startswith("IMPORTANT EVIDENCE COVERAGE LIMITATION:")
        assert "exploratory record and its limitations" in saved["draft"]["abstract"]
        assert "provisional" in saved["draft"]["abstract"].casefold()
        assert "were not reviewed" in saved["draft"]["abstract"]
        assert len(saved["draft"]["abstract"]) <= 1600
        assert saved["draft"]["conclusions"][0].startswith("PROVISIONAL —")
        assert (
            "Only claims tied to the recorded snapshot are presented."
            in saved["draft"]["conclusions"][0]
        )
        assert any(
            "IMPORTANT EVIDENCE COVERAGE LIMITATION" in warning
            for warning in saved["author_review_warnings"]
        )
        assert any("potential conflict" in warning for warning in saved["author_review_warnings"])
        assert provider_calls > 3
        assert provider_calls - calls_at_restart > 2
        assert completed_batch_calls < checkpoint["provider_calls"]
        assert provider_calls == calls_after_compile_failure
        assert papers._load_work(str(path)) is None
        assert len(saved["draft"]["sections"]) == 2


def test_structured_fast_index_preserves_math_review_and_bounds_omissions() -> None:
    package, _plan = fast_package()
    notes, _ = papers._structured_evidence_index(package)
    note_text = "\n".join(note.statement for note in notes)
    note_kinds = {note.kind for note in notes}
    source_ids = {source["id"] for source in package["sources"]}
    assert all(note.evidence_refs and set(note.evidence_refs) <= source_ids for note in notes)
    for expected in (
        "empty arrangement has one region",
        "No independent proof checker was run.",
        "negative_findings/1: No effect.",
        "unresolved convexity obligation",
        "Prove every arrangement cell is convex",
        "computed_base_case_n0: 1",
    ):
        assert expected in note_text, expected
    assert {"negative", "question", "result"} <= note_kinds
    assert all(
        note.evidence_refs == ["session:onp-fixture"]
        for note in notes
        if "session:onp-fixture" in note.evidence_refs
    )

    original = papers._research_integrity_records(package)
    excerpts = papers._section_original_excerpts(
        original,
        {"session:onp-fixture"},
        "proof argument skeptic objection contradiction failure obligation results",
        60_000,
    )
    excerpt_text = "\n".join(item["content_excerpt"] for item in excerpts)
    for expected in (
        "For n=0 the empty arrangement has one region",
        "The source argues that separated pieces lie in different old cells",
        "No independent proof checker was run.",
        "investigator calls the argument complete",
        "Prove every arrangement cell is convex",
    ):
        assert expected in excerpt_text, expected
    unresolved = papers._reconcile_obligations(
        draft().model_copy(update={"open_obligations": []}), package
    )
    assert any(
        item["text"]
        == "Prove every arrangement cell is convex and every crossed cell splits into two cells."
        and item["status"] == "Not listed by author; not presumed resolved"
        for item in unresolved
    )
    rendered = papers._tex(
        draft(),
        [],
        "a" * 64,
        math_style=True,
        integrity_records=[
            {
                "source_ref": item["source_ref"],
                "field": item["field"],
                "content": {"excerpt": item["content_excerpt"], "truncated": item["truncated"]},
            }
            for item in excerpts
        ],
        integrity_excerpts=True,
        obligation_reconciliation=unresolved,
    )
    assert r"\section{Frozen obligation reconciliation}" in rendered
    assert r"\section{Selected source-linked research excerpts}" in rendered
    assert "not presumed resolved" in rendered

    large_package, _ = fast_package()
    large_package["sources"][0]["data"] = {}
    large_package["sources"][1]["data"]["findings"] = [
        f"Finding {index}: " + ("This saved result is a limited observation. " * 8)
        for index in range(1_200)
    ]
    bounded, omitted = papers._structured_evidence_index(large_package)
    assert 0 < len(omitted) < 1_200
    assert len({item["field_ref"] for item in omitted}) == len(omitted)
    assert all(item["source_ref"] == "session:onp-fixture" for item in omitted)
    assert all(len(item["field_ref"]) == 64 and item["reason"] for item in omitted)
    assert len(papers._json([item.model_dump() for item in bounded])) <= papers.FAST_INDEX_MAX_BYTES
    assert any("No independent proof checker was run." in item.statement for item in bounded)


def test_bounded_index_keeps_constructive_proof_amid_many_objections() -> None:
    """Large skeptical transcripts must not crowd proof evidence out of the paper."""
    package, _ = fast_package()
    package["sources"][1]["data"] = {
        "objections": [
            f"Objection {number}: " + "An unresolved counterexample requires review. " * 8
            for number in range(900)
        ],
        "proof": (
            "Construct a line arrangement with each new line meeting all earlier "
            "lines at distinct points; it contributes the maximum number of regions."
        ),
    }
    notes, omitted = papers._structured_evidence_index(package)
    assert omitted
    assert len(papers._json([note.model_dump() for note in notes])) <= papers.FAST_INDEX_MAX_BYTES
    assert any(note.kind == "question" for note in notes)
    assert any("Construct a line arrangement" in note.statement for note in notes)
    assert any("unresolved counterexample" in note.statement for note in notes)


def test_fast_planner_preview_bounds_input_and_preserves_source_coverage() -> None:
    """Large index previews stay bounded; section writers retain full research."""
    sources = [f"session:research-{index}" for index in range(1, 6)]
    notes = [
        papers.EvidenceNote(
            statement=(
                f"Source {source}, observation {number}: "
                + ("Evidence is incomplete; the alternative remains plausible. " * 5)
            ),
            kind=("negative" if number % 2 else "result"),
            evidence_refs=[source],
        )
        for number in range(90)
        for source in sources
    ]
    full_size = len(papers._json([note.model_dump() for note in notes]))
    preview, skipped = papers._fast_planner_preview(notes)
    assert full_size > papers.FAST_PLANNER_PREVIEW_BYTES
    assert len(papers._json(preview)) <= papers.FAST_PLANNER_PREVIEW_BYTES
    assert skipped > 0
    assert skipped + len(preview) == len(notes)
    assert {ref for item in preview for ref in item["evidence_refs"]} == set(sources)
    assert {item["kind"] for item in preview} == {"result", "negative"}
    assert len(notes) == 450
    # The preview must not mutate the last indexed research statement.
    assert notes[-1].statement == (
        f"Source {sources[-1]}, observation 89: "
        + ("Evidence is incomplete; the alternative remains plausible. " * 5)
    )


def test_long_paper_can_retrieve_sources_outside_planner_preview() -> None:
    """Preview size cannot remove a source from the full section-writing index."""
    package, plan = fast_package()
    for number in range(6):
        package["sources"].append(
            {
                "id": f"session:additional-{number}",
                "kind": "session",
                "data": {
                    "summary": (
                        f"Session {number} records an independent unresolved proof "
                        "obligation with a conflicting interpretation."
                    )
                },
            }
        )
    state = papers._new_work("a" * 64, "fast-fixture", "b" * 64, "fixture-model", "high")
    additional: list[str] = []
    sections_seen: list[list[dict[str, Any]]] = []

    async def provider(input_value, _binding, _config, *, schema_name, **_kwargs):
        if schema_name == "sigma_long_paper_plan":
            additional.extend(input_value["additional_indexed_source_refs"])
            assert input_value["outline_preview_skipped_notes"] > 0
            assert additional
            targeted_sections = list(plan.sections)
            targeted_sections[0] = targeted_sections[0].model_copy(
                update={"evidence_refs": [additional[0]]}
            )
            return plan.model_copy(update={"sections": targeted_sections}), "fixture-model"
        sections_seen.append(input_value["evidence_notes"])
        return papers.LongSectionDraft(
            paragraphs=["The evidence remains uncertain and source-linked."]
        ), "fixture-model"

    async def check() -> None:
        with (
            patch.object(papers, "FAST_PLANNER_PREVIEW_BYTES", 650),
            patch.object(papers, "_provider_structured", new=provider),
        ):
            output, calls, batches = await papers._generate_long_draft(
                package,
                {"mode": "api_key", "identity": "fixture", "token": "fixture"},
                {"model": "fixture-model", "reasoning_effort": "high"},
                state,
                lambda _state: None,
                structured_fast_path=True,
            )
        assert output.sections and calls == len(plan.sections) + 1 and batches == 0

    asyncio.run(check())
    assert state["evidence_strategy"] == "structured_v1"
    indexed_refs = {ref for note in state["evidence_notes"] for ref in note["evidence_refs"]}
    assert set(additional) <= indexed_refs
    assert all(sections_seen)
    assert any(additional[0] in note["evidence_refs"] for note in sections_seen[0])


def test_research_type_specific_tex_sections_and_authoring_guidance() -> None:
    expected = {
        "biology": ("Introduction and biological context", "cross-species limitations"),
        "mathematical": ("Introduction", "bridges between logical steps"),
        "military": ("Question and operational context", "alternative courses of action"),
    }
    for research_type, (heading, guidance) in expected.items():
        tex = papers._tex(draft(), [], "f" * 64, investigation_type=research_type)
        assert rf"\section{{{heading}}}" in tex
        assert guidance in tex
    math_tex = papers._tex(draft(), [], "f" * 64, math_style=True)
    assert r"\section{Introduction}" in math_tex
    assert r"\section*{Claim status and evidence}" in math_tex


def test_military_style_guidance_reaches_all_authoring_paths() -> None:
    """Genre must guide model writing, not merely TeX section labels."""
    package, plan = fast_package()
    package["sources"][0]["data"]["investigation_type"] = "military"
    package["sources"][0]["data"]["problem"] = "Assess alternative planning assumptions."
    instructions_seen: dict[str, list[str]] = {}

    async def fake_stage(_input, _binding, _config, *, instructions, schema_name, **_kwargs):
        instructions_seen.setdefault(schema_name, []).append(instructions)
        if schema_name == "sigma_long_paper_plan":
            return plan, "fixture-model"
        assert schema_name == "sigma_long_paper_section"
        return papers.LongSectionDraft(
            paragraphs=["The recorded scenario and alternatives remain uncertain."]
        ), "fixture-model"

    state = papers._new_work("a" * 64, "fast-fixture", "b" * 64, "fixture-model", "high")

    async def long_form() -> None:
        with patch.object(papers, "_provider_structured", new=fake_stage):
            result, _calls, batches = await papers._generate_long_draft(
                package,
                {"mode": "api_key", "identity": "fixture", "token": "fixture"},
                {"model": "fixture-model", "reasoning_effort": "high"},
                state,
                lambda _state: None,
                structured_fast_path=True,
            )
        assert result.sections and batches == 0

    asyncio.run(long_form())
    assert "sigma_long_paper_plan" in instructions_seen
    assert "sigma_long_paper_section" in instructions_seen
    for instructions in instructions_seen.values():
        for text in instructions:
            assert "military operational assessment" in text
            assert "alternative courses of action" in text
            assert "The project type is mathematics" not in text

    requests: list[dict[str, Any]] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.content))
        return httpx.Response(400, json={"error": {"code": "invalid_json_schema"}})

    real_client = httpx.AsyncClient
    with patch(
        "sigma.papers.httpx.AsyncClient",
        side_effect=lambda **kwargs: real_client(transport=httpx.MockTransport(handler), **kwargs),
    ):
        try:
            asyncio.run(
                papers._provider(
                    package,
                    {"mode": "api_key", "token": "fixture"},
                    {"model": "fixture-model", "reasoning_effort": "high"},
                )
            )
        except ProjectError as exc:
            assert "HTTP 400" in str(exc)
        else:
            raise AssertionError("Mock provider should reject schema")

    assert len(requests) == 1
    instructions = requests[0]["instructions"]
    assert "military operational assessment" in instructions
    assert "alternative courses of action" in instructions
    assert "The project type is mathematics" not in instructions


def test_fast_long_draft_safe_retry_and_unknown_consumption_checkpoint() -> None:
    package, plan = fast_package()
    state = papers._new_work("a" * 64, "fast-fixture", "b" * 64, "fixture-model", "high")
    attempts: list[str] = []
    retry_progress: list[tuple[str, int | None, int | None, str]] = []

    async def provider(input_value, _binding, _config, *, schema_name, **_kwargs):
        attempts.append(schema_name)
        if schema_name == "sigma_long_paper_plan" and attempts.count(schema_name) == 1:
            raise papers.PaperConnectionFailure("fixture connect failed before dispatch")
        if schema_name == "sigma_long_paper_plan":
            return plan, "fixture-model"
        number = input_value["section_number"]
        return papers.LongSectionDraft(
            paragraphs=[f"Saved section {number} preserves the recorded limitation."]
        ), "fixture-model"

    async def progress(
        stage: papers.PaperProgressStage,
        current: int | None,
        total: int | None,
        state: papers.PaperProgressState = "active",
        *,
        detail: str | None = None,
    ):
        del detail
        retry_progress.append((stage, current, total, state))

    saved_states: list[dict[str, Any]] = []

    async def check_retry() -> None:
        with patch.object(papers, "_provider_structured", new=provider):
            generated, calls, batches = await papers._generate_long_draft(
                package,
                {"identity": "fixture", "mode": "api_key", "token": "fixture"},
                {"model": "fixture-model", "reasoning_effort": "high"},
                state,
                lambda value: saved_states.append(copy.deepcopy(value)),
                progress,
                structured_fast_path=True,
            )
        assert len(generated.sections) == 2
        assert calls == 4  # failed connection + outline + two sections
        assert batches == 0

    asyncio.run(check_retry())
    assert attempts.count("sigma_long_paper_plan") == 2
    assert ("retry", 1, 3, "active") in retry_progress
    assert state["provider_calls_total"] == 4
    assert state["evidence_strategy"] == "structured_v1"
    assert saved_states[-1]["plan"]["title"] == plan.title

    uncertain_state = papers._new_work("c" * 64, "fast-fixture", "d" * 64, "fixture-model", "high")
    uncertain_attempts = 0
    section_attempts = 0

    async def uncertain_provider(_input, _binding, _config, *, schema_name, **_kwargs):
        nonlocal uncertain_attempts, section_attempts
        if schema_name == "sigma_long_paper_plan":
            uncertain_attempts += 1
            raise ProjectError("fixture post-dispatch timeout; consumption is unknown")
        assert schema_name == "sigma_long_paper_section"
        section_attempts += 1
        return papers.LongSectionDraft(
            paragraphs=["The saved research reports an unresolved argument."]
        ), "fixture-model"

    async def check_uncertain() -> None:
        with patch.object(papers, "_provider_structured", new=uncertain_provider):
            generated, calls, _ = await papers._generate_long_draft(
                package,
                {"identity": "fixture", "mode": "api_key", "token": "fixture"},
                {"model": "fixture-model", "reasoning_effort": "high"},
                uncertain_state,
                lambda _value: None,
                structured_fast_path=True,
            )
        assert len(generated.sections) >= 2
        assert calls == 1 + len(generated.sections)
        assert any("planning stage did not" in warning for warning in generated.validation_warnings)

    asyncio.run(check_uncertain())
    assert uncertain_attempts == 1
    assert section_attempts >= 2
    assert uncertain_state["provider_calls"] == 1 + section_attempts
    assert uncertain_state["provider_calls_total"] == 1 + section_attempts
    assert uncertain_state["evidence_indexed"] is True
    assert uncertain_state["plan"]


def test_paper_failure_reason_survives_reopen() -> None:
    """A disconnected browser can still see why the previous stage failed."""
    with TemporaryDirectory() as directory:
        path = Path(directory) / "paper-failure.sigma"
        view = initialize_project(path, "Saved failure", "Why did the planning stage fail?")
        package, fingerprint = papers._snapshot(str(path))
        work = papers._new_work(fingerprint, view.project.id, "b" * 64, "fixture-model", "high")
        work["frozen_package"] = package
        work["progress"] = {
            "run_id": "a" * 32,
            "status": "running",
            "stage": "planning",
            "current": None,
            "total": None,
            "started_at": "2026-10-29T01:00:00+00:00",
            "updated_at": "2026-10-29T01:00:00+00:00",
            "elapsed_seconds": 300,
        }
        papers._save_work(str(path), work)
        reason = "A long-paper stage timed out. No paper was published; retry explicitly."
        papers.finish_progress(str(path), "failed", reason)
        recovered = papers.progress_status(str(path))
        assert recovered is not None
        assert recovered["status"] == "failed"
        assert recovered["stage"] == "planning"
        assert recovered["failure_reason"] == reason
        saved_work = papers._load_work(str(path))
        assert saved_work is not None
        assert saved_work["progress"]["failure_reason"] == reason


def test_failed_planning_checkpoint_continues_without_repeating_paid_plan() -> None:
    """A previously failed Tadpoles-shaped plan can resume with only section calls."""
    package, _ = fast_package()
    state = papers._new_work("a" * 64, "fast-fixture", "b" * 64, "fixture-model", "high")
    state.update(
        {
            "planning_fallback_pending": True,
            "evidence_strategy": "structured_v1",
            "evidence_indexed": True,
            "evidence_notes": [
                papers.EvidenceNote(
                    statement="The saved research contains a recorded observation.",
                    kind="result",
                    evidence_refs=["session:onp-fixture"],
                ).model_dump(),
                papers.EvidenceNote(
                    statement="An important experimental limitation remains unresolved.",
                    kind="limitation",
                    evidence_refs=["session:onp-fixture"],
                ).model_dump(),
            ],
            "provider_calls": 1,
            "provider_calls_total": 1,
            # A new run overwrites the stage before reaching long-form planning.
            "progress": {"stage": "snapshot", "status": "running"},
        }
    )
    dispatched: list[str] = []

    async def provider(input_value, _binding, _config, *, schema_name, **_kwargs):
        dispatched.append(schema_name)
        assert schema_name == "sigma_long_paper_section"
        return papers.LongSectionDraft(
            paragraphs=[f"Saved evidence supports the section {input_value['section_number']}."]
        ), "fixture-model"

    async def check() -> None:
        with patch.object(papers, "_provider_structured", new=provider):
            generated, calls, _ = await papers._generate_long_draft(
                package,
                {"identity": "fixture", "mode": "chatgpt", "token": "fixture"},
                {"model": "fixture-model", "reasoning_effort": "high"},
                state,
                lambda _value: None,
                structured_fast_path=True,
            )
        assert len(generated.sections) >= 2
        assert calls == 1 + len(generated.sections)
        assert state["plan"] is not None
        assert "planning_fallback_pending" not in state
        assert any("planning stage did not" in x for x in generated.validation_warnings)

    asyncio.run(check())
    assert dispatched and set(dispatched) == {"sigma_long_paper_section"}


def test_fast_long_draft_concurrency_ordered_checkpoints_and_resume() -> None:
    package, plan = fast_package(section_count=6)
    state = papers._new_work("e" * 64, "fast-fixture", "f" * 64, "fixture-model", "high")
    active = 0
    maximum_active = 0
    attempt_counts: dict[str, int] = {}
    saves: list[dict[str, Any]] = []
    progress_events: list[tuple[str, int | None, int | None, str]] = []

    async def provider(input_value, _binding, _config, *, schema_name, **_kwargs):
        nonlocal active, maximum_active
        attempt_counts[schema_name] = attempt_counts.get(schema_name, 0) + 1
        if schema_name == "sigma_long_paper_plan":
            return plan, "fixture-model"
        number = input_value["section_number"]
        active += 1
        maximum_active = max(maximum_active, active)
        try:
            await asyncio.sleep((7 - number) * 0.015)
            return papers.LongSectionDraft(
                paragraphs=[f"Durable completion for section {number}."]
            ), "fixture-model"
        finally:
            active -= 1

    async def check() -> tuple[papers.PaperDraft, int]:
        async def progress(
            stage: papers.PaperProgressStage,
            current: int | None,
            total: int | None,
            state: papers.PaperProgressState = "active",
            *,
            detail: str | None = None,
        ):
            del detail
            progress_events.append((stage, current, total, state))

        with patch.object(papers, "_provider_structured", new=provider):
            result, calls, _ = await papers._generate_long_draft(
                package,
                {"identity": "fixture", "mode": "api_key", "token": "fixture"},
                {"model": "fixture-model", "reasoning_effort": "high"},
                state,
                lambda value: saves.append(copy.deepcopy(value)),
                progress=progress,
                structured_fast_path=True,
            )
        return result, calls

    generated, calls = asyncio.run(check())
    assert maximum_active == papers.FAST_SECTION_CONCURRENCY
    assert calls == 7
    assert attempt_counts == {"sigma_long_paper_plan": 1, "sigma_long_paper_section": 6}
    assert [item.heading for item in generated.sections] == [item.heading for item in plan.sections]
    assert [item.paragraphs[0] for item in generated.sections] == [
        f"Durable completion for section {number}." for number in range(1, 7)
    ]
    assert ("evidence", 1, 1, "active") in progress_events
    assert ("evidence", 1, 1, "milestone") in progress_events
    assert ("planning", None, None, "active") in progress_events
    assert ("planning", None, None, "milestone") in progress_events
    section_milestones = [
        item[1:3] for item in progress_events if item[0] == "sections" and item[3] == "milestone"
    ]
    assert section_milestones == [(number, 6) for number in range(1, 7)]
    assert set(state["section_drafts"]) == {str(number) for number in range(1, 7)}
    assert all(
        set(snapshot.get("section_drafts", {})) <= set(state["section_drafts"])
        for snapshot in saves
    )
    assert len(saves) >= 8
    before = dict(attempt_counts)

    async def forbidden(_input, *_args, **_kwargs):
        raise AssertionError("Completed plan and sections must not be replayed")

    async def check_resume() -> None:
        with patch.object(papers, "_provider_structured", new=forbidden):
            result, completed_calls, _ = await papers._generate_long_draft(
                package,
                {"identity": "fixture", "mode": "api_key", "token": "fixture"},
                {"model": "fixture-model", "reasoning_effort": "high"},
                state,
                lambda _value: None,
                structured_fast_path=True,
            )
        assert completed_calls == 7
        assert len(result.sections) == 6

    asyncio.run(check_resume())
    assert attempt_counts == before


def test_fast_checkpoint_resume_replays_only_incomplete_section() -> None:
    package, plan = fast_package(section_count=2)
    project_ref = "project:fast-fixture"
    saved_table = papers.PaperTable(
        caption="A source-backed table completed before interruption.",
        headers=["Record", "Status"],
        rows=[["Investigator", "Saved"]],
        evidence_refs=[project_ref],
        claim_ids=["C1"],
    )
    saved_figure = papers.PaperDiagram(
        caption="A bounded diagram saved before the section interruption.",
        nodes=[
            papers.DiagramNode(id="evidence", label="Saved evidence"),
            papers.DiagramNode(id="claim", label="Paper claim"),
        ],
        edges=[papers.DiagramEdge(source="evidence", target="claim", label="supports")],
        evidence_refs=[project_ref],
        claim_ids=["C1"],
    )
    plan = plan.model_copy(update={"diagrams": [saved_figure]})
    state = papers._new_work("3" * 64, "fast-fixture", "4" * 64, "fixture-model", "high")
    attempts: list[tuple[str, int | None]] = []

    async def first_provider(input_value, _binding, _config, *, schema_name, **kwargs):
        number = input_value.get("section_number")
        attempts.append((schema_name, number))
        if schema_name == "sigma_long_paper_plan":
            assert kwargs["include_diagrams"] is True
            return plan, "fixture-model"
        if number == 1:
            return papers.LongSectionDraft(
                paragraphs=["This completed section is durable."], tables=[saved_table]
            ), "fixture-model"
        await asyncio.sleep(0.05)
        raise ProjectError("fixture section failure after another section was saved")

    async def fail_one_section() -> None:
        with patch.object(papers, "_provider_structured", new=first_provider):
            try:
                await papers._generate_long_draft(
                    package,
                    {"identity": "fixture", "mode": "api_key", "token": "fixture"},
                    {"model": "fixture-model", "reasoning_effort": "high"},
                    state,
                    lambda _value: None,
                    structured_fast_path=True,
                )
            except ProjectError as exc:
                assert "another section was saved" in str(exc)
            else:
                raise AssertionError(
                    "The injected section failure must preserve a partial checkpoint"
                )

    asyncio.run(fail_one_section())
    assert set(state["section_drafts"]) == {"1"}
    assert attempts.count(("sigma_long_paper_plan", None)) == 1
    assert attempts.count(("sigma_long_paper_section", 1)) == 1
    assert attempts.count(("sigma_long_paper_section", 2)) == 1

    async def resume_provider(input_value, _binding, _config, *, schema_name, **kwargs):
        number = input_value.get("section_number")
        assert schema_name == "sigma_long_paper_section" and number == 2
        assert kwargs["include_diagrams"] is False
        schema = papers._paper_response_schema(
            kwargs["response_model"], include_diagrams=kwargs["include_diagrams"]
        )
        assert "tables" not in schema["properties"]
        assert "TABLES:" not in kwargs["instructions"]
        attempts.append((schema_name, number))
        return papers.LongSectionDraft(
            paragraphs=["Only the incomplete section is retried."], tables=[saved_table]
        ), "fixture-model"

    async def resume() -> None:
        with patch.object(papers, "_provider_structured", new=resume_provider):
            result, calls, batches = await papers._generate_long_draft(
                package,
                {"identity": "fixture", "mode": "api_key", "token": "fixture"},
                {"model": "fixture-model", "reasoning_effort": "high"},
                state,
                lambda _value: None,
                structured_fast_path=True,
                include_diagrams=False,
            )
        assert [section.paragraphs[0] for section in result.sections] == [
            "This completed section is durable.",
            "Only the incomplete section is retried.",
        ]
        assert calls == 4  # outline, completed section, uncertain failure, continuation
        assert batches == 0
        assert result.diagrams == []
        assert all(not section.tables for section in result.sections)

    asyncio.run(resume())
    assert attempts.count(("sigma_long_paper_plan", None)) == 1
    assert attempts.count(("sigma_long_paper_section", 1)) == 1
    assert attempts.count(("sigma_long_paper_section", 2)) == 2
    assert set(state["section_drafts"]) == {"1", "2"}
    assert state["plan"]["diagrams"]  # saved paid output stays available for recovery
    assert all(state["section_drafts"][key]["tables"] for key in ("1", "2"))


def test_paper_generation_rejects_concurrent_duplicate_request() -> None:
    with TemporaryDirectory() as temporary:
        path = Path(temporary) / "single-flight.sigma"
        view = initialize_project(path, "Single flight", "Preserve one generation at a time")
        credential = {"identity": "fixture:account", "mode": "api_key", "token": "fixture"}
        config = {
            "available": True,
            "binding": credential["identity"],
            "model": "fixture-model",
            "reasoning_effort": "high",
        }
        started = asyncio.Event()
        release = asyncio.Event()
        provider_calls = 0

        async def blocked_provider(context, *_args):
            nonlocal provider_calls
            provider_calls += 1
            started.set()
            await release.wait()
            source = next(item["id"] for item in context["sources"] if item["kind"] == "project")
            return draft(source), "fixture-model"

        async def credentials():
            return credential

        async def configuration(**_kwargs):
            return config

        async def check() -> None:
            with (
                patch.object(papers, "auth_context", new=credentials),
                patch.object(papers, "configuration", new=configuration),
                patch.object(papers, "_provider", new=blocked_provider),
                patch.object(papers, "_compile_pdf", return_value=b"%PDF-fixture"),
                mock_pdf_inspection(),
            ):
                first = asyncio.create_task(
                    papers.generate(str(path), credential["identity"], view.project.id)
                )
                await asyncio.wait_for(started.wait(), timeout=2)
                try:
                    await papers.generate(str(path), credential["identity"], view.project.id)
                except ProjectError as exc:
                    assert "already active" in str(exc)
                else:
                    raise AssertionError("A concurrent generation must be rejected")
                release.set()
                result = await first
                assert result["title"] == "An evidence-bound exploratory note"

        asyncio.run(check())
        assert provider_calls == 1
        assert len(papers.list_papers(str(path))) == 1
        assert not papers._gate.locked()


def test_two_paper_generators_run_concurrently_and_third_fails_fast() -> None:
    """AI latency in one user's paper must not block another project."""
    with TemporaryDirectory() as temporary:
        paths = [Path(temporary) / f"paper-{index}.sigma" for index in range(3)]
        views = [
            initialize_project(path, f"Paper project {index}", "Independent bounded research")
            for index, path in enumerate(paths)
        ]
        credential = {"identity": "fixture:account", "mode": "api_key", "token": "fixture"}
        config = {
            "available": True,
            "binding": credential["identity"],
            "model": "fixture-model",
            "reasoning_effort": "high",
        }
        both_started = asyncio.Event()
        release = asyncio.Event()
        provider_calls = 0

        async def blocked_provider(context, *_args):
            nonlocal provider_calls
            provider_calls += 1
            if provider_calls == 2:
                both_started.set()
            await release.wait()
            source = next(item["id"] for item in context["sources"] if item["kind"] == "project")
            return draft(source), "fixture-model"

        async def credentials():
            return credential

        async def configuration(**_kwargs):
            return config

        async def check():
            with (
                patch.object(papers, "auth_context", new=credentials),
                patch.object(papers, "configuration", new=configuration),
                patch.object(papers, "_provider", new=blocked_provider),
                patch.object(papers, "_compile_pdf", return_value=b"%PDF-fixture"),
                mock_pdf_inspection(),
            ):
                first, second = [
                    asyncio.create_task(
                        papers.generate(str(path), credential["identity"], view.project.id)
                    )
                    for path, view in zip(paths[:2], views[:2])
                ]
                try:
                    await asyncio.wait_for(both_started.wait(), timeout=2)
                    assert provider_calls == 2, "Both users should reach AI concurrently"
                    assert len(papers._generating_paper_projects) == 2
                    try:
                        await papers.generate(
                            str(paths[2]), credential["identity"], views[2].project.id
                        )
                    except ProjectError as exc:
                        assert "capacity is full" in str(exc)
                    else:
                        raise AssertionError("Third paper must be rejected before provider I/O")
                    assert provider_calls == 2
                finally:
                    release.set()
                results = await asyncio.wait_for(asyncio.gather(first, second), timeout=5)
                assert len(results) == 2
                assert len(papers.list_papers(str(paths[0]))) == 1
                assert len(papers.list_papers(str(paths[1]))) == 1
                assert papers.list_papers(str(paths[2])) == []
                assert not papers._busy_paper_projects
                assert not papers._generating_paper_projects

        asyncio.run(check())


def test_two_papers_reach_compilation_together_and_hold_capacity() -> None:
    """Both admitted papers compile in parallel; no third paper enters mid-compile."""
    with TemporaryDirectory() as temporary:
        paths = [Path(temporary) / f"compile-{index}.sigma" for index in range(3)]
        views = [
            initialize_project(path, f"Compile project {index}", "Compile independently")
            for index, path in enumerate(paths)
        ]
        credential = {"identity": "fixture:account", "mode": "api_key", "token": "fixture"}
        config = {
            "available": True,
            "binding": credential["identity"],
            "model": "fixture-model",
            "reasoning_effort": "high",
        }
        two_compiling = threading.Event()
        finish_compiling = threading.Event()
        count_lock = threading.Lock()
        compilations = 0
        provider_calls = 0

        def blocked_compiler(*_args, **_kwargs):
            nonlocal compilations
            with count_lock:
                compilations += 1
                if compilations == 2:
                    two_compiling.set()
            if not finish_compiling.wait(timeout=10):
                raise AssertionError("An independent PDF compiler was serialized or stranded")
            return b"%PDF-fixture"

        async def provider(context, *_args):
            nonlocal provider_calls
            provider_calls += 1
            source = next(item["id"] for item in context["sources"] if item["kind"] == "project")
            return draft(source), "fixture-model"

        async def credentials():
            return credential

        async def configuration(**_kwargs):
            return config

        async def check() -> None:
            with (
                patch.object(papers, "auth_context", new=credentials),
                patch.object(papers, "configuration", new=configuration),
                patch.object(papers, "_provider", new=provider),
                patch.object(papers, "_compile_pdf", new=blocked_compiler),
                mock_pdf_inspection(),
            ):
                first, second = [
                    asyncio.create_task(
                        papers.generate(str(path), credential["identity"], view.project.id)
                    )
                    for path, view in zip(paths[:2], views[:2])
                ]
                try:
                    assert await asyncio.wait_for(
                        asyncio.to_thread(two_compiling.wait, 8), timeout=9
                    ), "Only one paper reached PDF compilation"
                    assert compilations == 2
                    assert len(papers._generating_paper_projects) == 2
                    try:
                        await papers.generate(
                            str(paths[2]), credential["identity"], views[2].project.id
                        )
                    except ProjectError as exc:
                        assert "capacity is full" in str(exc)
                    else:
                        raise AssertionError("Third paper entered while two compilers were active")
                    assert provider_calls == 2
                    assert compilations == 2
                finally:
                    finish_compiling.set()
                results = await asyncio.wait_for(asyncio.gather(first, second), timeout=6)
                assert len(results) == 2
                assert all(len(papers.list_papers(str(path))) == 1 for path in paths[:2])
                assert papers.list_papers(str(paths[2])) == []
                assert not papers._busy_paper_projects
                assert not papers._generating_paper_projects

        asyncio.run(check())


def test_eight_research_sessions_overlap_two_paper_generators() -> None:
    """Cross-feature smoke: 8 live mock research calls + 2 paper model calls."""
    from contextvars import ContextVar
    from uuid import uuid4

    import research_sessions as research_fixture

    from sigma import research_sessions
    from sigma.projects import create_strategy

    subject: ContextVar[str] = ContextVar("test-concurrency-subject", default="fixture")
    research_ids: set[str] = set()
    research_ready = asyncio.Event()
    paper_ready = asyncio.Event()
    release = asyncio.Event()
    paper_count = 0

    async def credentials():
        return {
            "identity": subject.get(),
            "mode": "api_key",
            "token": "local-fixture-only",
            "status": "connected",
        }

    async def research_configuration(**_kwargs):
        return {
            "available": True,
            "model": research_fixture.MODEL,
            "reasoning_effort": "high",
        }

    async def paper_configuration(**_kwargs):
        return {
            "available": True,
            "binding": subject.get(),
            "model": "fixture-model",
            "reasoning_effort": "high",
        }

    async def research_provider(record, role, _context, timeout_seconds=None, step_id=None):
        del timeout_seconds
        assert isinstance(step_id, str)
        if role == "investigator":
            research_ids.add(record["id"])
            if len(research_ids) == 8:
                research_ready.set()
            await release.wait()
            return research_fixture.investigation(1), {"input_tokens": 120, "output_tokens": 90}
        return research_fixture.skeptic(1, "stop"), {"input_tokens": 120, "output_tokens": 90}

    async def paper_provider(context, *_args):
        nonlocal paper_count
        paper_count += 1
        if paper_count == 2:
            paper_ready.set()
        await release.wait()
        source = next(item["id"] for item in context["sources"] if item["kind"] == "project")
        return draft(source), "fixture-model"

    async def check(root: Path):
        research_projects = []
        for index in range(8):
            path = root / f"research-{index}.sigma"
            view = initialize_project(path, f"Research {index}", "Check independent cases")
            strategy = create_strategy(
                path, "Bounded method", "Investigate an independent research approach"
            ).project.strategies[0]
            research_projects.append((path, view, strategy))
        paper_projects = [
            (path, initialize_project(path, f"Paper {index}", "Independent paper"))
            for index in range(2)
            for path in [root / f"paper-{index}.sigma"]
        ]

        async def start_research(index, path, view, strategy):
            token = subject.set(f"research-user-{index}")
            try:
                return await research_sessions.start_session(
                    str(path), strategy.id, str(uuid4()), view.project.id, subject.get()
                )
            finally:
                subject.reset(token)

        async def start_paper(index, path, view):
            token = subject.set(f"paper-user-{index}")
            try:
                return await papers.generate(str(path), subject.get(), view.project.id)
            finally:
                subject.reset(token)

        with (
            patch.object(research_sessions, "auth_context", new=credentials),
            patch.object(research_sessions, "configuration", new=research_configuration),
            patch.object(research_sessions, "_call", new=research_provider),
            patch.object(research_sessions, "execution_capabilities", return_value=[]),
            patch.object(papers, "auth_context", new=credentials),
            patch.object(papers, "configuration", new=paper_configuration),
            patch.object(papers, "_provider", new=paper_provider),
            patch.object(papers, "_compile_pdf", return_value=b"%PDF-mock"),
            mock_pdf_inspection(),
        ):
            starts = await asyncio.gather(
                *(
                    start_research(i, path, view, strategy)
                    for i, (path, view, strategy) in enumerate(research_projects)
                )
            )
            paper_tasks = []
            try:
                await asyncio.wait_for(research_ready.wait(), 15)
                assert len(research_ids) == 8
                paper_tasks = [
                    asyncio.create_task(start_paper(i, path, view))
                    for i, (path, view) in enumerate(paper_projects)
                ]
                await asyncio.wait_for(paper_ready.wait(), 15)
                assert len(papers._generating_paper_projects) == 2
                assert all(not research_sessions._tasks[row["id"]].done() for row in starts)
                assert paper_count == 2
            finally:
                release.set()
            await asyncio.wait_for(asyncio.gather(*paper_tasks), 15)
            finished = await asyncio.wait_for(
                asyncio.gather(
                    *(
                        research_fixture.wait_for(path, row["id"])
                        for (path, _, _), row in zip(research_projects, starts)
                    )
                ),
                15,
            )
            assert all(row["status"] == "ended" for row in finished)
            assert all(row["tokens_reserved"] == 0 for row in finished)
            assert all(len(papers.list_papers(str(path))) == 1 for path, _ in paper_projects)
            assert not papers._generating_paper_projects

    with TemporaryDirectory() as temporary:
        asyncio.run(check(Path(temporary)))


def test_fast_long_draft_cancellation_keeps_completed_sections() -> None:
    package, plan = fast_package(section_count=5)
    state = papers._new_work("1" * 64, "fast-fixture", "2" * 64, "fixture-model", "high")
    first_section_saved = asyncio.Event()
    blocked_section_started = asyncio.Event()
    active = 0

    async def provider(input_value, _binding, _config, *, schema_name, **_kwargs):
        nonlocal active
        if schema_name == "sigma_long_paper_plan":
            return plan, "fixture-model"
        number = input_value["section_number"]
        active += 1
        try:
            if number == 1:
                return papers.LongSectionDraft(
                    paragraphs=["This section is checkpointed."]
                ), "fixture-model"
            blocked_section_started.set()
            await asyncio.Event().wait()
            raise AssertionError("blocked section should be cancelled")
        finally:
            active -= 1

    def save(value: dict[str, Any]) -> None:
        if "1" in value.get("section_drafts", {}):
            first_section_saved.set()

    async def check() -> None:
        with patch.object(papers, "_provider_structured", new=provider):
            task = asyncio.create_task(
                papers._generate_long_draft(
                    package,
                    {"identity": "fixture", "mode": "api_key", "token": "fixture"},
                    {"model": "fixture-model", "reasoning_effort": "high"},
                    state,
                    save,
                    structured_fast_path=True,
                )
            )
            await asyncio.wait_for(first_section_saved.wait(), timeout=3)
            await asyncio.wait_for(blocked_section_started.wait(), timeout=3)
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            else:
                raise AssertionError("Cancellation must propagate from section writing")

    asyncio.run(check())
    assert active == 0
    assert set(state["section_drafts"]) == {"1"}
    assert state["provider_calls"] >= 2


def test_tadpoles_five_session_mock_provider_to_pdf_timing() -> None:
    sample_path = (
        Path(__file__).resolve().parents[1] / "samples/xenopus-tail-regeneration/project.json"
    )
    sample = json.loads(sample_path.read_text(encoding="utf-8"))
    with TemporaryDirectory() as temporary:
        path = Path(temporary) / "tadpoles-five-session.sigma"
        project_view = initialize_project(
            path,
            sample["title"],
            sample["problem"],
            "biology",
            "gpt-6.1-sol",
            "high",
            "hard",
        )
        project_data = asdict(project_view.project)
        project_data["strategies"] = []
        sessions = [
            {
                "id": f"tadpole-session-{index}",
                "status": "completed",
                "outcome": {
                    "summary": (
                        "A saved exploratory finding compares stage-specific regeneration "
                        "and records limitations; it is not an independent validation."
                    ),
                    "verification_status": "unverified",
                    "open_obligations": [
                        "Validate the candidate interaction on an independent biological cohort."
                    ],
                },
                "findings": [
                    f"Session {index} records a limited observation with no claimed causal mechanism."
                ],
                "negative_findings": [
                    f"Session {index} did not establish an independent replicate."
                ],
                "contradictory_findings": [
                    f"Session {index} contrasts the observed pattern with an alternative explanation."
                ],
                "reasoning_steps": [
                    f"Session {index} separates the recorded observation from a proposed mechanism."
                ],
                "skeptic_objections": [
                    f"Session {index} lacks independent specimens and a falsifying perturbation."
                ],
                "open_obligations": [
                    "Validate the candidate interaction on an independent biological cohort."
                ],
                "artifacts": [
                    {
                        "id": f"artifact-{index}",
                        "title": f"Saved session {index} evidence note",
                        "content": "The complete source record remains archived for inspection.",
                    }
                ],
            }
            for index in range(1, 6)
        ]
        export = {
            "project": project_data,
            "research_sessions": sessions,
            "agentic_runs": [],
        }
        credential = {"identity": "fixture:api-key", "mode": "api_key", "token": "fixture"}
        config = {
            "available": True,
            "binding": credential["identity"],
            "model": "gpt-6.1-sol",
            "reasoning_effort": "high",
        }
        mock_calls: list[str] = []

        async def simulated_provider(input_value, _binding, _config, *, schema_name, **_kwargs):
            mock_calls.append(schema_name)
            if schema_name == "sigma_tex_proofread_patches":
                return papers.TeXProofreadResult(corrections=[]), config["model"]
            if schema_name == "sigma_long_paper_plan":
                refs = sorted(
                    {ref for item in input_value["evidence_index"] for ref in item["evidence_refs"]}
                )
                assert len(refs) > 1
                session_refs = [ref for ref in refs if ref.startswith("session:")]
                assert len(session_refs) == 5
                obligation = (
                    "Validate the candidate interaction on an independent biological cohort."
                )
                return papers.FastLongPaperPlan(
                    title="Five-Session Xenopus Evidence Synthesis",
                    abstract=(
                        "This mock study assembles five saved Xenopus sessions and preserves "
                        "their observations, negative results, contradictions, and limitations. "
                        "It does not claim a validated biological mechanism."
                    ),
                    abstract_claim_ids=["C1"],
                    problem_framing=[
                        "The project asks for a discriminating regeneration mechanism."
                    ],
                    problem_framing_claim_ids=["C1"],
                    methods=["We synthesize only saved source-linked session records."],
                    methods_claim_ids=["C1"],
                    claims=[
                        papers.PaperClaim(
                            id="C1",
                            statement="The five sessions preserve exploratory, unresolved evidence.",
                            status="unresolved",
                            evidence_refs=session_refs,
                            reasoning="Each cited session retains uncertainty and a common validation obligation.",
                        )
                    ],
                    sections=[
                        papers.LongSectionPlan(
                            heading="Recorded observations and uncertainty",
                            purpose="Describe the session evidence without presenting a mechanism as verified.",
                            evidence_refs=session_refs,
                            claim_ids=["C1"],
                        ),
                        papers.LongSectionPlan(
                            heading="Negative evidence and next tests",
                            purpose="Preserve skeptical objections, contradictions, and the next validation obligation.",
                            evidence_refs=session_refs,
                            claim_ids=["C1"],
                        ),
                    ],
                    limitations=[
                        "All five records are synthetic fixtures, not biological findings."
                    ],
                    open_obligations=[obligation],
                    conclusions=[
                        "This is an unresolved mock synthesis, not a validated mechanism."
                    ],
                    conclusion_claim_ids=["C1"],
                    validation_warnings=["No live provider or biological evaluation was used."],
                ), config["model"]
            if schema_name == "sigma_long_paper_section":
                return papers.LongSectionDraft(
                    paragraphs=[
                        "The archived records preserve negative observations, disagreement, and the Skeptic's independent-cohort objection. This deterministic text is a test fixture and makes no biological claim."
                    ]
                ), config["model"]
            raise AssertionError(f"Unexpected provider stage: {schema_name}")

        async def credential_context():
            return credential

        async def model_configuration(**_kwargs):
            return config

        # CI need not install a TeX toolchain to exercise checkpoint-to-saved-PDF
        # plumbing. Machines with Tectonic still compile a real PDF; others use
        # a clearly identified local test stub, not a claimed PDF quality check.
        tectonic_available = shutil.which("tectonic") is not None
        compiler_context = (
            nullcontext()
            if tectonic_available
            else patch.multiple(
                papers,
                _compile_pdf=lambda *_args, **_kwargs: (
                    b"%PDF-1.4\\n" + b"% deterministic test fixture\\n" * 40
                ),
                _pdf_text_bounds_diagnostics=lambda _pdf: (1, []),
            )
        )

        with (
            patch("sigma.api.export_project_view", return_value=export),
            patch.object(papers, "auth_context", new=credential_context),
            patch.object(papers, "configuration", new=model_configuration),
            patch.object(papers, "_provider_structured", new=simulated_provider),
            compiler_context,
        ):
            snapshot_hash = papers._snapshot(str(path))[1]
            started = perf_counter()
            result = asyncio.run(
                papers.generate(
                    str(path),
                    credential["identity"],
                    project_view.project.id,
                    force_long_form=True,
                    expected_snapshot_sha256=snapshot_hash,
                )
            )
            elapsed_seconds = perf_counter() - started

        record = papers.get_paper(str(path), result["paper_id"])
        assert record["pdf_available"] is True
        assert record["pdf_size_bytes"] > 500
        assert record["generation"]["provider_calls_attempted"] == 4
        assert record["generation"]["evidence_batch_count"] == 0
        assert record["generation"]["evidence_fields_omitted"] == 0
        assert (
            len([source for source in record["snapshot"]["sources"] if source["kind"] == "session"])
            == 5
        )
        assert all(
            any(
                source["id"] == f"artifact:tadpole-session-{index}:artifact-{index}"
                for source in record["snapshot"]["sources"]
            )
            for index in range(1, 6)
        )
        assert any(
            item["text"]
            == "Validate the candidate interaction on an independent biological cohort."
            and item["status"] == "Listed as open in paper"
            for item in record["obligation_reconciliation"]
        )
        assert len(mock_calls) == 4
        assert elapsed_seconds < 300
        compiler_label = (
            "real Tectonic compilation" if tectonic_available else "stub PDF (Tectonic unavailable)"
        )
        print(
            f"PASS mocked five-session Tadpoles paper-to-PDF E2E in {elapsed_seconds:.2f}s "
            f"({compiler_label}; deterministic provider; live <5-minute target remains unverified)."
        )


def test_maximum_regions_archived_one_session_stays_fast() -> None:
    """Use the actual archived happy-path evidence layout as a mode-selection gate."""
    archived = (
        Path(__file__).resolve().parents[1]
        / "docs/evaluations/increment_19/exports/maximum-regions-sigma-reexport.json"
    )
    export = json.loads(archived.read_text(encoding="utf-8"))
    assert export["project"]["difficulty"] == "easy"
    assert len(export["research_sessions"]) == 1
    with patch("sigma.api.export_project_view", return_value=export):
        package, _ = papers._snapshot("fixture")
    assert len(package["sources"]) == 5  # project + strategy + session + two artifacts
    assert len(papers._json(package)) <= papers.MAX_ONE_SHOT_CONTEXT_BYTES
    assert papers._paper_long_form(package) is False

    # The old size-only mode switch made one additional research note cause
    # several sequential/parallel AI calls. Keep full original evidence while
    # selecting a single call for this easy one-session investigation.
    augmented = copy.deepcopy(export)
    augmented["research_sessions"][0]["outcome"]["new_saved_finding"] = (
        "Further consideration of the same proof and its open obligations. " * 130
    )
    with patch("sigma.api.export_project_view", return_value=augmented):
        bigger, _ = papers._snapshot("fixture")
    assert papers.MAX_ONE_SHOT_CONTEXT_BYTES < len(papers._json(bigger))
    assert len(papers._json(bigger)) < papers.MAX_EASY_ONE_SHOT_CONTEXT_BYTES
    assert len(bigger["sources"]) == len(package["sources"])
    assert papers._paper_long_form(bigger) is False


def test_easy_paper_avoids_unnecessary_long_form_calls() -> None:
    """An easy one-session paper uses one full-evidence call past the 100 KB cliff."""
    package = {
        "schema": "sigma-paper-evidence-v2",
        "project_id": "easy-fixture",
        "sources": [
            {
                "id": "project:easy-fixture",
                "kind": "project",
                "data": {
                    "id": "easy-fixture",
                    "difficulty": "easy",
                    "investigation_type": "mathematical",
                },
            },
            {
                "id": "session:one",
                "kind": "session",
                "data": {"outcome": {"argument": "A proof candidate. " * 6_500}},
            },
        ],
    }
    snapshot_bytes = len(papers._json(package))
    assert (
        papers.MAX_ONE_SHOT_CONTEXT_BYTES < snapshot_bytes < papers.MAX_EASY_ONE_SHOT_CONTEXT_BYTES
    )
    assert papers._paper_long_form(package) is False
    assert papers._paper_long_form(package, force_long_form=True) is True

    # A paid long-form checkpoint also survives when the snapshot is smaller
    # than the historical 100 KB boundary (e.g. an explicitly long run).
    small_package = copy.deepcopy(package)
    small_package["sources"][1]["data"]["outcome"]["argument"] = "Short proof candidate."
    assert papers._paper_long_form(small_package) is False
    paid_small = papers._new_work(
        papers.hashlib.sha256(papers._json(small_package)).hexdigest(),
        "easy-fixture",
        "b" * 64,
        "fixture-model",
        "high",
    )
    paid_small["provider_calls"] = 1
    assert papers._paper_long_form(small_package, existing=paid_small) is True

    # An earlier, compatible long-form attempt retains its checkpoint. The
    # optimization must never abandon paid outline or section work.
    existing = papers._new_work(
        papers.hashlib.sha256(papers._json(package)).hexdigest(),
        "easy-fixture",
        "a" * 64,
        "fixture-model",
        "high",
    )
    existing["plan"] = {"already_paid": True}
    assert papers._paper_long_form(package, existing=existing) is True
    assert (
        papers._paper_long_form(package, existing={**existing, "snapshot_sha256": "0" * 64})
        is False
    )

    package["sources"].append(
        {"id": "session:two", "kind": "session", "data": {"outcome": "An independent run."}}
    )
    assert papers._paper_long_form(package) is True
    package["sources"].pop()
    package["sources"][0]["data"]["difficulty"] = "hard"
    assert papers._paper_long_form(package) is True
    package["sources"][0]["data"]["difficulty"] = "easy"
    package["sources"][1]["data"]["outcome"]["argument"] *= 2
    assert papers._paper_long_form(package) is True


def test_invalid_planning_claim_reference_is_recoverable() -> None:
    """Repair an inconsistent paid outline without repeating the plan call."""
    package, valid_plan = fast_package()
    invalid_section = valid_plan.sections[0].model_copy(update={"claim_ids": ["C999"]})
    invalid_plan = valid_plan.model_copy(
        update={
            "abstract_claim_ids": ["C999", *valid_plan.abstract_claim_ids],
            "sections": [invalid_section, *valid_plan.sections[1:]],
        }
    )
    state = papers._new_work("a" * 64, "fast-fixture", "b" * 64, "fixture-model", "high")
    planning_calls = 0
    saves: list[dict[str, Any]] = []

    async def provider(input_value, _binding, _config, *, schema_name, **_kwargs):
        nonlocal planning_calls
        if schema_name == "sigma_long_paper_plan":
            planning_calls += 1
            return invalid_plan, "fixture-model"
        assert schema_name == "sigma_long_paper_section"
        return papers.LongSectionDraft(
            paragraphs=[f"Saved section {input_value['section_number']}."]
        ), "fixture-model"

    async def attempt(target: dict[str, Any]) -> tuple[papers.PaperDraft, int, int]:
        with patch.object(papers, "_provider_structured", new=provider):
            return await papers._generate_long_draft(
                package,
                {"identity": "fixture", "mode": "api_key", "token": "fixture"},
                {"model": "fixture-model", "reasoning_effort": "high"},
                target,
                lambda value: saves.append(copy.deepcopy(value)),
                structured_fast_path=True,
            )

    generated, calls, batches = asyncio.run(attempt(state))
    assert planning_calls == 1
    assert calls == 1 + len(valid_plan.sections)
    assert batches == 0
    assert len(generated.sections) == len(valid_plan.sections)
    assert "C999" not in generated.abstract_claim_ids
    assert "C999" not in generated.sections[0].claim_ids
    assert any(
        "unknown or repeated claim links" in item.casefold()
        for item in generated.validation_warnings
    )
    assert state["evidence_indexed"] is True
    assert state["provider_calls_total"] == calls
    assert state["plan"]["abstract_claim_ids"] == valid_plan.abstract_claim_ids
    assert state["plan"]["sections"][0]["claim_ids"] == []
    assert any(item.get("plan") for item in saves)

    # Older versions may already have saved an inconsistent outline.
    # Repair it and reuse the one paid planning call.
    old = papers._new_work("c" * 64, "fast-fixture", "d" * 64, "fixture-model", "high")
    old.update(
        {
            "plan": invalid_plan.model_dump(),
            "evidence_indexed": True,
            "evidence_strategy": "structured_v1",
            "evidence_notes": state["evidence_notes"],
            "provider_calls": 1,
            "provider_calls_total": 1,
        }
    )
    _, old_calls, old_batches = asyncio.run(attempt(old))
    assert planning_calls == 1
    assert old_batches == 0
    assert old_calls == 1 + len(valid_plan.sections)
    assert old["provider_calls_total"] == old_calls
    assert old["plan"]["abstract_claim_ids"] == valid_plan.abstract_claim_ids
    assert old["plan"]["sections"][0]["claim_ids"] == []


def test_easy_paper_start_over_escapes_repeated_paid_planning() -> None:
    """An explicit reset switches eligible research to one call without AI."""
    with TemporaryDirectory() as temporary:
        path = Path(temporary) / "easy-restart.sigma"
        view = initialize_project(path, "Easy paper", "How many regions can n lines form?")
        package = {
            "schema": "sigma-paper-evidence-v2",
            "project_id": view.project.id,
            "sources": [
                {
                    "id": f"project:{view.project.id}",
                    "kind": "project",
                    "data": {"id": view.project.id, "difficulty": "easy"},
                },
                {
                    "id": "session:one",
                    "kind": "session",
                    "data": {"outcome": "An existing mathematical argument. " * 3_500},
                },
            ],
        }
        encoded = papers._json(package)
        assert papers.MAX_ONE_SHOT_CONTEXT_BYTES < len(encoded) < 200_000
        snapshot_hash = papers.hashlib.sha256(encoded).hexdigest()
        identity = "chatgpt:fixture"
        credential = {"identity": identity, "mode": "chatgpt", "token": "fixture"}
        config = {"available": True, "model": "gpt-fixture", "reasoning_effort": "high"}
        binding = papers.hashlib.sha256(("chatgpt\0" + identity).encode()).hexdigest()
        checkpoint = papers._new_work(
            snapshot_hash, view.project.id, binding, "gpt-fixture", "high"
        )
        checkpoint["provider_calls"] = 2
        checkpoint["provider_calls_total"] = 2
        checkpoint["evidence_indexed"] = True
        checkpoint["evidence_strategy"] = "structured_v1"
        papers._save_work(str(path), checkpoint)

        async def fake_auth():
            return credential

        async def fake_configuration(**_kwargs):
            return config

        with (
            patch.object(papers, "_snapshot", return_value=(package, snapshot_hash)),
            patch.object(papers, "auth_context", new=fake_auth),
            patch.object(papers, "configuration", new=fake_configuration),
            patch.object(papers, "_provider", side_effect=AssertionError("no AI on Start over")),
            patch.object(
                papers, "_provider_structured", side_effect=AssertionError("no AI on Start over")
            ),
        ):
            before = papers.preflight(
                str(path),
                expected_project_id=view.project.id,
                expected_binding=identity,
                mode="chatgpt",
                model="gpt-fixture",
                reasoning_effort="high",
            )
            assert before["resume_available"] is True
            assert before["long_form"] is True
            assert before["single_call_restart_available"] is True

            reset = asyncio.run(
                papers.restart_work(
                    str(path),
                    view.project.id,
                    identity,
                    snapshot_hash,
                    confirmed=True,
                    force_long_form=False,
                )
            )
            assert reset["provider_calls_attempted"] == 0
            saved = papers._load_work(str(path))
            assert saved is not None
            assert saved["kind"] == "one_shot"
            assert saved["provider_calls_total"] == 2
            assert len(saved["prior_runs"]) == 1
            assert saved["prior_runs"][0]["provider_calls_attempted"] == 2
            after = papers.preflight(
                str(path),
                expected_project_id=view.project.id,
                expected_binding=identity,
                mode="chatgpt",
                model="gpt-fixture",
                reasoning_effort="high",
            )
            assert after["long_form"] is False
            assert after["maximum_provider_calls"] == 1 + papers.MAX_PROOFREAD_CALLS
            assert after["provider_calls_attempted"] == 0


def test_one_shot_validation_failure_preserves_paid_draft_for_continue() -> None:
    """Local validation errors must not erase a complete paid author response."""
    with TemporaryDirectory() as directory:
        path = Path(directory) / "validation-recovery.sigma"
        view = initialize_project(path, "Paper recovery", "Review the saved objective.")
        account = {"identity": "chatgpt:fixture", "mode": "chatgpt", "token": "fixture"}
        config = {
            "available": True,
            "binding": account["identity"],
            "model": "fixture-model",
            "reasoning_effort": "high",
        }
        provider_calls = 0
        validations = 0
        real_validate = papers._validate

        async def provider(context, _account, _config, *_args):
            nonlocal provider_calls
            provider_calls += 1
            source = next(item["id"] for item in context["sources"] if item["kind"] == "project")
            return draft(source), config["model"]

        def validate(paper, package):
            nonlocal validations
            validations += 1
            if validations == 1:
                raise ProjectError("Transient local claim metadata check failed")
            return real_validate(paper, package)

        async def run() -> None:
            with (
                patch.object(papers, "auth_context", new=lambda: asyncio.sleep(0, result=account)),
                patch.object(
                    papers, "configuration", new=lambda **_kwargs: asyncio.sleep(0, result=config)
                ),
                patch.object(papers, "_provider", new=provider),
                patch.object(papers, "_validate", new=validate),
                patch.object(papers, "_compile_pdf", return_value=b"%PDF-fixture"),
                mock_pdf_inspection(),
            ):
                try:
                    await papers.generate(str(path), account["identity"], view.project.id)
                except ProjectError as exc:
                    assert "metadata check" in str(exc)
                else:
                    raise AssertionError("The first validation was deliberately interrupted")
                saved_work = papers._load_work(str(path))
                assert saved_work is not None
                assert saved_work["provider_calls"] == 1
                assert saved_work["one_shot_draft"] is not None
                result = await papers.generate(str(path), account["identity"], view.project.id)
                assert provider_calls == 1
                saved = papers.get_paper(str(path), result["paper_id"])
                assert saved["pdf_available"] is True
                assert saved["generation"]["provider_calls_attempted"] == 2
                assert papers._load_work(str(path)) is None

        asyncio.run(run())


def test_live_research_change_does_not_discard_completed_paper() -> None:
    """A paper cites its frozen input even when unrelated saved research advances."""
    with TemporaryDirectory() as directory:
        path = Path(directory) / "research-advanced.sigma"
        view = initialize_project(path, "Frozen paper", "Study saved evidence.")
        identity = {"identity": "chatgpt:fixture", "mode": "chatgpt", "token": "fixture"}
        config = {
            "available": True,
            "binding": identity["identity"],
            "model": "fixture-model",
            "reasoning_effort": "high",
        }
        original, original_hash = papers._snapshot(str(path))
        advanced = copy.deepcopy(original)
        advanced["sources"][0]["data"]["title"] = "Research advanced while authoring"
        advanced_hash = papers.hashlib.sha256(papers._json(advanced)).hexdigest()
        assert advanced_hash != original_hash
        calls = 0
        snapshots = 0

        def changing_snapshot(_path):
            nonlocal snapshots
            snapshots += 1
            if snapshots != 1:
                raise AssertionError("Do not recheck changing live evidence after authoring")
            return original, original_hash

        async def provider(_context, *_args):
            nonlocal calls
            calls += 1
            return draft(original["sources"][0]["id"]), config["model"]

        with (
            patch.object(papers, "_snapshot", side_effect=changing_snapshot),
            patch.object(papers, "auth_context", new=lambda: asyncio.sleep(0, result=identity)),
            patch.object(
                papers, "configuration", new=lambda **_kwargs: asyncio.sleep(0, result=config)
            ),
            patch.object(papers, "_provider", new=provider),
            patch.object(papers, "_compile_pdf", return_value=b"%PDF-fixture"),
            mock_pdf_inspection(),
        ):
            completed = asyncio.run(
                papers.generate(str(path), identity["identity"], view.project.id)
            )

        saved = papers.get_paper(str(path), completed["paper_id"])
        assert calls == 1
        assert saved["snapshot_sha256"] == original_hash
        assert saved["snapshot"] == original
        assert snapshots == 1
        assert papers._load_work(str(path)) is None


def test_frozen_evidence_checkpoint_survives_live_research_drift() -> None:
    """Resuming a paid draft must not read new research or require Start over."""
    with TemporaryDirectory() as directory:
        path = Path(directory) / "frozen-checkpoint.sigma"
        view = initialize_project(path, "Frozen paper", "Saved evidence")
        identity = {"identity": "chatgpt:fixture", "mode": "chatgpt", "token": "fixture"}
        config = {
            "available": True,
            "binding": identity["identity"],
            "model": "fixture-model",
            "reasoning_effort": "high",
        }
        package, fingerprint = papers._snapshot(str(path))
        work = papers._new_work(
            fingerprint,
            view.project.id,
            papers.hashlib.sha256(
                (identity["mode"] + "\0" + identity["identity"]).encode()
            ).hexdigest(),
            config["model"],
            config["reasoning_effort"],
            kind="one_shot",
        )
        work["frozen_package"] = package
        work["provider_calls"] = 1
        work["provider_calls_total"] = 1
        work["one_shot_draft"] = draft(package["sources"][0]["id"]).model_dump()
        papers._save_work(str(path), work)

        with (
            patch.object(papers, "_snapshot", side_effect=AssertionError("live evidence re-read")),
            patch.object(papers, "auth_context", new=lambda: asyncio.sleep(0, result=identity)),
            patch.object(
                papers, "configuration", new=lambda **_kwargs: asyncio.sleep(0, result=config)
            ),
            patch.object(
                papers, "_provider", side_effect=AssertionError("paid draft must be reused")
            ),
            patch.object(papers, "_compile_pdf", return_value=b"%PDF-fixture"),
            mock_pdf_inspection(),
        ):
            preflight = papers.preflight(
                str(path),
                expected_project_id=view.project.id,
                expected_binding=identity["identity"],
                mode=identity["mode"],
                model=config["model"],
                reasoning_effort=config["reasoning_effort"],
            )
            assert preflight["resume_available"] is True
            assert preflight["snapshot_sha256"] == fingerprint
            completed = asyncio.run(
                papers.generate(
                    str(path),
                    identity["identity"],
                    view.project.id,
                    expected_snapshot_sha256="0" * 64,
                )
            )
        saved = papers.get_paper(str(path), completed["paper_id"])
        assert saved["snapshot_sha256"] == fingerprint
        assert saved["snapshot"] == package
        assert saved["generation"]["provider_calls_attempted"] == 2
        assert saved["generation"]["proofreading"]["attempted"] is True


def test_one_shot_publishes_with_repaired_claim_links() -> None:
    """A usable completed author draft is a paper, not a paid repair dialogue."""
    with TemporaryDirectory() as directory:
        path = Path(directory) / "one-shot-repair.sigma"
        view = initialize_project(path, "Paper recovery", "Study the saved research.")
        account = {"identity": "chatgpt:fixture", "mode": "chatgpt", "token": "fixture"}
        config = {
            "available": True,
            "binding": account["identity"],
            "model": "fixture-model",
            "reasoning_effort": "high",
        }
        calls = 0

        async def provider(context, _account, _config, *_args):
            nonlocal calls
            calls += 1
            source = next(item["id"] for item in context["sources"] if item["kind"] == "project")
            base = draft(source)
            return base.model_copy(
                update={
                    "abstract_claim_ids": ["C987", "C1"],
                    "claims": [
                        base.claims[0].model_copy(
                            update={"evidence_refs": ["invented:source"], "status": "established"}
                        )
                    ],
                }
            ), config["model"]

        with (
            patch.object(papers, "auth_context", new=lambda: asyncio.sleep(0, result=account)),
            patch.object(
                papers, "configuration", new=lambda **_kwargs: asyncio.sleep(0, result=config)
            ),
            patch.object(papers, "_provider", new=provider),
            patch.object(papers, "_compile_pdf", return_value=b"%PDF-fixture"),
            mock_pdf_inspection(),
        ):
            result = asyncio.run(papers.generate(str(path), account["identity"], view.project.id))

        assert calls == 1
        saved = papers.get_paper(str(path), result["paper_id"])
        assert saved["draft"]["abstract_claim_ids"] == ["C1"]
        assert saved["draft"]["claims"][0]["status"] == "unresolved"
        assert saved["draft"]["claims"][0]["evidence_refs"] == []
        assert saved["generation"]["provider_calls_attempted"] == 2
        assert saved["generation"]["proofreading"]["attempted"] is True
        assert any("not established" in x for x in saved["draft"]["limitations"])
        assert saved["pdf_available"] is True
        assert papers._load_work(str(path)) is None


def test_repair_paper_references_preserves_science_and_downgrades_unsupported_claims() -> None:
    original = draft()
    corrupt = original.model_copy(
        update={
            "abstract_claim_ids": ["C999", "C1", "C1"],
            "claims": [
                original.claims[0].model_copy(
                    update={
                        "evidence_refs": ["project:pid", "invalid:source", "project:pid"],
                        "status": "established",
                    }
                )
            ],
            "sections": [
                original.sections[0].model_copy(update={"claim_ids": ["C999"]}),
                original.sections[1],
            ],
        }
    )
    repaired = papers.PaperDraft.model_validate(
        papers._repair_paper_references(corrupt, {"project:pid"})
    )
    assert repaired.abstract == original.abstract
    assert repaired.sections[0].paragraphs == original.sections[0].paragraphs
    assert repaired.claims[0].status == "unresolved"
    assert repaired.claims[0].evidence_refs == ["project:pid"]
    assert repaired.abstract_claim_ids == ["C1"]
    assert repaired.sections[0].claim_ids == []
    assert any("not established" in limitation for limitation in repaired.limitations)
    assert any("unsupported links were removed" in x for x in repaired.validation_warnings)
    assert papers._validate(
        repaired,
        {"sources": [{"id": "project:pid", "data": {"problem": "Saved objective"}}]},
    )


def test_one_shot_provider_failure_requires_explicit_reset_without_rebilling() -> None:
    """A lost one-call result may be billable; never replay it silently."""
    with TemporaryDirectory() as temporary:
        path = Path(temporary) / "one-shot-uncertain.sigma"
        view = initialize_project(path, "One-call recovery", "Explain the recorded research.")
        snapshot = papers._snapshot(str(path))[1]
        account = {"mode": "chatgpt", "identity": "chatgpt:fixture", "token": "fixture"}
        config = {
            "available": True,
            "binding": account["identity"],
            "model": "fixture-model",
            "reasoning_effort": "high",
        }
        calls = 0
        reject = True

        async def provider(context, _account, settings, *_args, **_kwargs):
            nonlocal calls
            calls += 1
            if reject:
                raise ProjectError("Fixture provider interrupted after request dispatch")
            project_ref = next(
                item["id"] for item in context["sources"] if item["kind"] == "project"
            )
            return draft(project_ref), settings["model"]

        async def check() -> None:
            nonlocal reject
            with (
                patch.object(papers, "auth_context", new=lambda: asyncio.sleep(0, result=account)),
                patch.object(
                    papers,
                    "configuration",
                    new=lambda **_kw: asyncio.sleep(0, result=config),
                ),
                patch.object(papers, "_provider", new=provider),
                patch.object(papers, "_compile_pdf", return_value=b"%PDF-fixture"),
                mock_pdf_inspection(),
            ):
                try:
                    await papers.generate(str(path), account["identity"], view.project.id)
                except ProjectError as exc:
                    assert "interrupted" in str(exc)
                else:
                    raise AssertionError("The first provider attempt should fail")
                checkpoint = papers._load_work(str(path))
                assert checkpoint is not None
                assert checkpoint["kind"] == "one_shot"
                assert checkpoint["provider_calls"] == 1
                assert checkpoint["provider_calls_total"] == 1
                assert checkpoint["one_shot_draft"] is None

                preflight = papers.preflight(
                    str(path),
                    expected_project_id=view.project.id,
                    expected_binding=account["identity"],
                    mode=account["mode"],
                    model=config["model"],
                    reasoning_effort=config["reasoning_effort"],
                )
                assert preflight["resume_available"] is False
                assert preflight["incomplete_one_shot"] is True
                assert preflight["checkpoint_can_restart"] is True
                try:
                    await papers.generate(str(path), account["identity"], view.project.id)
                except ProjectError as exc:
                    assert "Start over explicitly" in str(exc)
                else:
                    raise AssertionError("An uncertain paid request must not replay")
                assert calls == 1

                reset = await papers.restart_work(
                    str(path),
                    view.project.id,
                    account["identity"],
                    snapshot,
                    confirmed=True,
                    force_long_form=False,
                )
                assert reset["provider_calls_attempted"] == 0
                assert calls == 1  # Starting over makes no provider request.
                reject = False
                result = await papers.generate(str(path), account["identity"], view.project.id)
                assert calls == 2
                record = papers.get_paper(str(path), result["paper_id"])
                assert record["generation"]["provider_calls_attempted"] == 2
                assert record["generation"]["provider_calls_prior_runs"] == 1
                assert record["generation"]["provider_calls_lifetime_total"] == 3
                assert papers._load_work(str(path)) is None

        asyncio.run(check())


def test_structured_index_retains_session_narrative_and_original_question() -> None:
    """Unusual saved summaries must not trigger serial AI field extraction."""
    problem = "Find an upper bound and construction for line arrangements."
    package = {
        "schema": "sigma-paper-evidence-v2",
        "project_id": "narrative-fixture",
        "sources": [
            {
                "kind": "project",
                "id": "project:narrative-fixture",
                "data": {
                    "title": "Line arrangements",
                    "problem": problem,
                    "difficulty": "hard",
                    "investigation_type": "mathematical",
                },
            },
            {
                "kind": "session",
                "id": "session:first",
                "data": {
                    "summary": (
                        "A candidate proof derives a recurrence by counting line segments "
                        "and leaves a convexity obligation open."
                    )
                },
            },
            {
                "kind": "session",
                "id": "session:second",
                "data": {
                    "summary": (
                        "A skeptical follow-up identifies an unsupported crossing claim "
                        "and does not establish a proof."
                    )
                },
            },
        ],
    }
    notes, omissions = papers._structured_evidence_index(package)
    assert notes
    assert not omissions
    assert {ref for note in notes for ref in note.evidence_refs} == {
        "project:narrative-fixture",
        "session:first",
        "session:second",
    }
    descriptions = " ".join(item.statement for item in notes)
    assert "candidate proof" in descriptions
    assert "unsupported crossing claim" in descriptions
    plan = papers._long_plan_input(
        package["sources"][0]["data"],
        [note.model_dump() for note in notes],
        len(package["sources"]),
        0,
    )
    assert plan["project_question"] == problem


def test_summary_only_research_uses_zero_paid_evidence_extraction_calls() -> None:
    """An unconventional session field still uses deterministic indexing."""
    package, plan = fast_package()
    package["sources"][1]["data"] = {
        "summary": (
            "The investigator derives a candidate construction for the number "
            "of regions, and the skeptic leaves the convexity proof obligation "
            "unresolved."
        )
    }
    state = papers._new_work("a" * 64, "fast-fixture", "b" * 64, "fixture-model", "high")
    stages: list[str] = []

    async def provider(_input, _binding, _config, *, schema_name, **_kwargs):
        stages.append(schema_name)
        if schema_name == "sigma_long_paper_plan":
            return plan, "fixture-model"
        assert schema_name == "sigma_long_paper_section"
        return papers.LongSectionDraft(
            paragraphs=["The saved research supports this bounded interpretation."]
        ), "fixture-model"

    async def check() -> None:
        with patch.object(papers, "_provider_structured", new=provider):
            paper, calls, batches = await papers._generate_long_draft(
                package,
                {"identity": "fixture", "mode": "api_key", "token": "fixture"},
                {"model": "fixture-model", "reasoning_effort": "high"},
                state,
                lambda _value: None,
                structured_fast_path=True,
            )
        assert paper.sections
        assert batches == 0
        assert calls == len(plan.sections) + 1
        assert stages.count("sigma_long_paper_plan") == 1
        assert stages.count("sigma_long_paper_section") == len(plan.sections)
        assert state["evidence_strategy"] == "structured_v1"

    asyncio.run(check())


def test_long_paper_planning_timeout_is_stage_specific() -> None:
    """Every paper inference stage allows a full hour for high-thinking models."""
    assert papers.CALL_SECONDS == 3600
    assert papers.PLANNING_CALL_SECONDS == 3600
    assert papers._long_paper_call_timeout("sigma_long_paper_plan") == 3600
    assert papers._long_paper_call_timeout("sigma_long_paper_section") == 3600
    assert papers._long_paper_call_timeout("sigma_paper_evidence_batch") == 3600

    observed: list[float | int | httpx.Timeout] = []

    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"error": {"code": "invalid_json_schema"}})

    actual_client = httpx.AsyncClient

    def client_factory(**kwargs: Any) -> httpx.AsyncClient:
        observed.append(kwargs["timeout"])
        return actual_client(transport=httpx.MockTransport(handler), **kwargs)

    async def check() -> None:
        for stage in ("sigma_long_paper_plan", "sigma_long_paper_section"):
            try:
                await papers._provider_structured(
                    {"fixture": "timeout-check"},
                    {"mode": "api_key", "token": "fixture"},
                    {"model": "test-model", "reasoning_effort": "high"},
                    instructions="fixture",
                    schema_name=stage,
                    response_model=papers.PaperDraft,
                )
            except ProjectError as exc:
                assert "HTTP 400" in str(exc)
            else:
                raise AssertionError("Mock rejection should not complete paper authoring")

    with patch("sigma.papers.httpx.AsyncClient", side_effect=client_factory):
        asyncio.run(check())
    assert observed == [3600, 3600]


def test_combined_visual_schema_and_safe_tex_rendering() -> None:
    unchecked = papers._paper_response_schema(papers.PaperDraft)
    checked = papers._paper_response_schema(papers.PaperDraft, include_diagrams=True)
    assert "diagrams" not in unchecked["properties"]
    assert "tables" not in unchecked["$defs"]["PaperSection"]["properties"]
    assert "PaperTable" not in unchecked["$defs"]
    assert "PaperDiagram" not in unchecked["$defs"]
    assert "diagrams" in checked["properties"]
    assert "tables" in checked["$defs"]["PaperSection"]["properties"]
    assert "PaperTable" in checked["$defs"]
    assert "diagrams" not in papers._paper_response_schema(papers.FastLongPaperPlan)["properties"]
    assert (
        "diagrams"
        in papers._paper_response_schema(papers.FastLongPaperPlan, include_diagrams=True)[
            "properties"
        ]
    )
    assert "tables" not in papers._paper_response_schema(papers.LongSectionDraft)["properties"]
    assert (
        "tables"
        in papers._paper_response_schema(papers.LongSectionDraft, include_diagrams=True)[
            "properties"
        ]
    )
    figure = papers.PaperDiagram.model_validate(
        {
            "caption": "Proposed policy-first routing; not an implemented federation.",
            "nodes": [
                {"id": "campus", "label": r"Campus & \input{secret}"},
                {"id": "policy", "label": "Policy gate"},
                {"id": "frontier", "label": "Approved frontier API"},
            ],
            "edges": [
                {"source": "campus", "target": "policy", "label": "request"},
                {"source": "policy", "target": "frontier", "label": "allow only"},
            ],
            "boundaries": [
                {"label": "Proposed campus trust boundary", "node_ids": ["campus", "policy"]}
            ],
            "evidence_refs": ["project:pid"],
            "claim_ids": ["C1"],
        }
    )
    paper = draft()
    table = papers.PaperTable.model_validate(
        {
            "caption": "Evidence-bound comparison of local and approved routes.",
            "headers": ["Route", "Policy", "Evidence"],
            "rows": [
                ["Campus local", "Allowed", "Saved project"],
                ["Frontier", "Approved only", "Saved project"],
            ],
            "evidence_refs": ["project:pid"],
            "claim_ids": ["C1"],
        }
    )
    sections = [
        paper.sections[0].model_copy(update={"tables": [table]}),
        paper.sections[1],
    ]
    paper = paper.model_copy(update={"diagrams": [figure], "sections": sections})
    tex = papers._tex(paper, [], "a" * 64)
    assert tex.index(r"\usepackage{tikz}") < tex.index(r"\begin{document}")
    assert r"\input{secret}" not in tex
    assert r"Campus \&" in tex
    assert "Proposed campus trust boundary" in tex
    assert r"\begin{longtable}" in tex
    assert "Evidence: [project:pid]; claims: C1" in tex
    assert papers._validate(paper, {"sources": [{"id": "project:pid", "data": {}}]})
    visual_free = papers._without_optional_visuals(paper)
    assert visual_free.diagrams == []
    assert all(not section.tables for section in visual_free.sections)
    visual_free_tex = papers._tex(visual_free, [], "a" * 64)
    assert r"\usepackage{tikz}" not in visual_free_tex
    assert r"\begin{longtable}" not in visual_free_tex
    if shutil.which("tectonic"):
        pdf = papers._compile_pdf(tex, timeout_seconds=90)
        assert pdf.startswith(b"%PDF-")


def test_longtable_semantic_signature_normalizes_every_table_preamble() -> None:
    original = r"""\begin{longtable}{p{2cm}p{4cm}}n & $0$\\Claim C1 supports source project:fixture\\\end{longtable}
\begin{longtable}{>{\raggedright}p{3cm}p{5cm}}n & $1$\\Claim C2\\\end{longtable}
\begin{longtable}{p{7cm}p{2cm}}n & $2$\\Claim C3\\\end{longtable}"""
    adjusted = r"""\begin{longtable}{p{1cm}p{5cm}}n & $0$\\Claim C1 supports source project:fixture\\\end{longtable}
\begin{longtable}{>{\raggedleft}p{8cm}p{1cm}}n & $1$\\Claim C2\\\end{longtable}
\begin{longtable}{p{2cm}p{6cm}}n & $2$\\Claim C3\\\end{longtable}"""
    assert papers._tex_semantic_signature(original) == papers._tex_semantic_signature(adjusted)
    escaped_math = original.replace("$0$", r"\$0\$")
    assert papers._tex_semantic_signature(original) == papers._tex_semantic_signature(escaped_math)
    for mutation in (
        adjusted.replace("$2$", "$9$"),
        adjusted.replace("Claim C3", "Claim C8"),
        adjusted.replace("project:fixture", "project:foreign"),
    ):
        assert papers._tex_semantic_signature(original) != papers._tex_semantic_signature(mutation)


def test_pdf_layout_repairs_are_bounded_and_protect_research_semantics() -> None:
    source = (
        "\\documentclass{article}\n"
        + "\\emergencystretch=2em\n"
        + "\\linespread{1.07}\n"
        + r"\begin{document}The result remains 3 units.\end{document}"
    )
    warnings = [r"Overfull \hbox (12.0pt too wide)", r"Overfull \vbox (8.0pt too high)"]
    first = papers._repair_tex_layout(source, warnings)
    assert first is not None
    first_tex, first_detail = first
    assert r"\emergencystretch=4em" in first_tex
    assert r"\linespread{1.0}" in first_tex
    assert "line-breaking stretch" in first_detail and "line spacing" in first_detail
    assert papers._tex_semantic_signature(source) == papers._tex_semantic_signature(first_tex)
    second = papers._repair_tex_layout(first_tex, [warnings[0]])
    assert second is not None and r"\emergencystretch=8em" in second[0]
    assert papers._tex_semantic_signature(first_tex) == papers._tex_semantic_signature(second[0])
    assert papers._repair_tex_layout(second[0], [warnings[0]]) is None
    assert papers._repair_tex_layout(source, [r"Underfull \hbox badness 10000"]) is None


def test_caption_limits_reject_cutoff_and_allow_complete_long_caption() -> None:
    common = {
        "headers": ["Condition", "Outcome"],
        "rows": [["Control", "Recorded"]],
        "evidence_refs": ["project:pid"],
        "claim_ids": ["C1"],
    }
    truncated = "A" * 296 + " or "
    assert len(truncated) == 300
    try:
        papers.PaperTable.model_validate({**common, "caption": truncated})
    except papers.ValidationError as exc:
        assert "appears incomplete" in str(exc)
    else:
        raise AssertionError("A caption cut at the old schema boundary must be rejected")
    complete = "A source-grounded caption describing the table and its caveat. " + "x" * 275
    parsed = papers.PaperTable.model_validate({**common, "caption": complete})
    assert len(parsed.caption) > 300


def test_real_tadpole_onp_and_math_table_pdfs() -> None:
    """Compile realistic fixture PDFs and gate on width/layout warnings."""
    if not shutil.which("tectonic"):
        return
    source_map = {"project:pid": "Project overview", "session:sid": "Research session 1"}
    mathematical = draft("project:pid")
    math_table = papers.PaperTable(
        caption="Small cases for the region count M(n), with symbols typeset as mathematics.",
        headers=["Input n", "Added regions", "Maximum M(n)"],
        rows=[
            ["$0$", "$0$", "$1$"],
            ["$1$", "$1$", "$2$"],
            ["$2$", "$2$", "$4$"],
            ["$3$", "$3$", "$7$"],
        ],
        evidence_refs=["project:pid"],
        claim_ids=["C1"],
    )
    mathematical = mathematical.model_copy(
        update={
            "title": "Maximum Regions Mathematical Table Fixture",
            "sections": [
                mathematical.sections[0].model_copy(update={"tables": [math_table]}),
                mathematical.sections[1],
            ],
        }
    )

    tadpole_caption = (
        "Candidate stage–time dependency map: arrows indicate hypotheses about the sequence "
        "from injury response to later epidermal activation and matrix remodeling. These are "
        "candidate relationships, not measured or validated mechanisms."
    )
    tadpole_diagram = papers.PaperDiagram(
        caption=tadpole_caption,
        nodes=[
            papers.DiagramNode(id="injury", label="Amputation injury and early wound response"),
            papers.DiagramNode(id="ric", label="RIC formation and basal epidermal response"),
            papers.DiagramNode(id="matrix", label="Extracellular matrix remodeling"),
            papers.DiagramNode(id="stage40", label="Stage 40: competent condition"),
            papers.DiagramNode(id="stage46", label="Stage 46: refractory condition"),
            papers.DiagramNode(id="regrowth", label="Observed regeneration outcome"),
        ],
        edges=[
            papers.DiagramEdge(source="injury", target="ric", label="candidate input"),
            papers.DiagramEdge(source="ric", target="matrix", label="candidate coupling"),
            papers.DiagramEdge(source="matrix", target="regrowth", label="candidate relation"),
            papers.DiagramEdge(source="stage40", target="ric", label="comparison condition"),
            papers.DiagramEdge(source="stage46", target="ric", label="comparison condition"),
        ],
        boundaries=[
            papers.DiagramBoundary(
                label="Proposed intermediate process", node_ids=["ric", "matrix"]
            )
        ],
        evidence_refs=["session:sid"],
        claim_ids=["C1"],
    )
    tadpole_table = papers.PaperTable(
        caption="Candidate transcriptomic contrasts and the inferential limitation for each proposed comparison.",
        headers=["Stage and time", "Candidate contrast", "Interpretive limit"],
        rows=[
            ["Stage 40, 0 h", "Baseline after sham handling", "Specimen links are unverified"],
            ["Stage 40, 0.5 h", "Early injury response", "Does not establish later dependency"],
            ["Stage 40, 6 h", "Intermediate response", "Biological replication is unverified"],
            ["Stage 46, 3 d", "Later regeneration program", "No animal-level pairing is supplied"],
        ],
        evidence_refs=["project:pid", "session:sid"],
        claim_ids=["C1"],
    )
    tadpole = draft("project:pid").model_copy(
        update={
            "title": "Tadpoles Publication Layout Fixture",
            "diagrams": [tadpole_diagram],
            "sections": [
                draft("project:pid").sections[0].model_copy(update={"tables": [tadpole_table]}),
                draft("project:pid").sections[1],
            ],
        }
    )

    onp_nodes = [
        papers.DiagramNode(
            id=f"actor{index}",
            label=f"Actor {index}: sovereign decision authority and operational constraint",
        )
        for index in range(1, 9)
    ]
    onp_edges = [
        papers.DiagramEdge(
            source=onp_nodes[index % 8].id,
            target=onp_nodes[(index + 1) % 8].id,
            label=f"conditional action {index + 1}",
        )
        for index in range(12)
    ]
    onp_diagram = papers.PaperDiagram(
        caption="Long-label scenario map — the links identify conditional dependencies, not asserted control over another sovereign actor.",
        nodes=onp_nodes,
        edges=onp_edges,
        boundaries=[
            papers.DiagramBoundary(
                label="National decision authority", node_ids=["actor1", "actor2", "actor3"]
            )
        ],
        evidence_refs=["project:pid"],
        claim_ids=["C1"],
    )
    onp_rows = [
        [
            f"Course {index + 1}",
            "Preserve personnel safety while establishing whether access is physically available",
            "Requires confirmed receipt and observed unit compliance before treating the pause as operative",
            "Conditional on timely medical and engineering assessments",
            "Does not establish legal authority or control over escalation",
        ]
        for index in range(12)
    ]
    onp_table = papers.PaperTable(
        caption="Five-column conditional course comparison. All criteria remain uncertain where the scenario supplies no validated evidence.",
        headers=[
            "Course",
            "Personnel objective",
            "Operational dependency",
            "Feasibility condition",
            "Unresolved limit",
        ],
        rows=onp_rows,
        evidence_refs=["project:pid"],
        claim_ids=["C1"],
    )
    onp = draft("project:pid").model_copy(
        update={
            "title": "Operation Narrow Passage Layout Fixture",
            "diagrams": [onp_diagram],
            "sections": [
                draft("project:pid").sections[0].model_copy(update={"tables": [onp_table]}),
                draft("project:pid").sections[1],
            ],
        }
    )

    graph_nodes = [
        papers.DiagramNode(id="evidence", label="Saved evidence"),
        papers.DiagramNode(id="author", label="Author review"),
        papers.DiagramNode(id="skeptic", label="Skeptic review"),
        papers.DiagramNode(id="finding", label="Qualified finding"),
    ]
    graph_edges = [
        papers.DiagramEdge(source="evidence", target="author", label="supports"),
        papers.DiagramEdge(source="evidence", target="skeptic", label="challenges"),
        papers.DiagramEdge(source="author", target="finding", label="accepted with caveat"),
        papers.DiagramEdge(source="skeptic", target="finding", label="obligation remains"),
    ]
    graph_diagram = papers.PaperDiagram(
        caption="Source-grounded review flow; the remaining obligation qualifies the finding.",
        nodes=graph_nodes,
        edges=graph_edges,
        boundaries=[
            papers.DiagramBoundary(label="Independent review", node_ids=["author", "skeptic"])
        ],
        evidence_refs=["session:sid"],
        claim_ids=["C1"],
    )
    graph = draft("project:pid").model_copy(
        update={"title": "Readable Graph Layout Fixture", "diagrams": [graph_diagram]}
    )

    fixtures = [
        ("Maximum Regions", mathematical),
        ("Tadpoles", tadpole),
        ("ONP", onp),
        ("Diagram", graph),
    ]
    with TemporaryDirectory():
        for name, value in fixtures:
            warnings: list[str] = []
            tex = papers._tex(
                value,
                warnings,
                "f" * 64,
                source_reference_map=source_map,
            )
            assert "project:pid" not in tex and "session:sid" not in tex
            if name == "Maximum Regions":
                assert r"\textbf{Input n}" in tex and r"\textbf{Maximum M(n)}" in tex
                assert r"$0$ & $0$ & $1$" in tex
                assert r"M(n)" in tex
                assert r"\$0\$" not in tex
            if name == "Tadpoles":
                assert r"Candidate stage\textendash{}time dependency map" in tex
                assert r"\textendash{}" in tex
                assert "Diagram (readable relationship list)." in tex
                for node in tadpole_diagram.nodes:
                    assert node.label in tex
                for edge in tadpole_diagram.edges:
                    assert edge.label in tex
                assert "Proposed intermediate process" in tex
            if name == "ONP":
                assert r"\begin{landscape}" in tex and r"\endlastfoot" in tex
                assert "Diagram (readable relationship list)." in tex
                assert len(onp_rows) == 12
            diagnostics: list[str] = []
            pdf = papers._compile_pdf(
                tex,
                timeout_seconds=120,
                diagnostics=diagnostics,
                max_pdf_bytes=40_000_000,
            )
            assert pdf.startswith(b"%PDF-"), f"{name} did not yield a real PDF"
            assert not papers._publication_layout_warnings(diagnostics), (name, diagnostics)
            assert len(pdf) > 5_000
            document = pypdfium2.PdfDocument(pdf)
            inspected_page_count, pdf_diagnostics = papers._pdf_text_bounds_diagnostics(pdf)
            assert inspected_page_count == len(document)
            assert pdf_diagnostics == [], (name, pdf_diagnostics)
            pages = [document[index] for index in range(len(document))]
            extracted = "\n".join(page.get_textpage().get_text_range() for page in pages)
            normalized_text = unicodedata.normalize("NFKC", " ".join(extracted.split()))
            assert len(document) >= 2
            for page in pages:
                bounds = (
                    (page.get_height(), page.get_width())
                    if page.get_rotation() in {90, 270}
                    else (page.get_width(), page.get_height())
                )
                textpage = page.get_textpage()
                for character_index in range(textpage.count_chars()):
                    char_bounds = textpage.get_charbox(character_index)
                    assert char_bounds is not None, (name, character_index)
                    x0, y0, x1, y1 = char_bounds
                    assert -1 <= x0 <= x1 <= bounds[0] + 1 and -1 <= y0 <= y1 <= bounds[1] + 1, (
                        name,
                        textpage.get_text_range(character_index, 1),
                        char_bounds,
                        bounds,
                    )
                rendered_page = page.render(scale=1).to_pil()
                assert rendered_page.width > 500 and rendered_page.height > 500
            if name == "Maximum Regions":
                table_page = next(
                    page.get_textpage().get_text_range()
                    for page in pages
                    if "Table 1:" in page.get_textpage().get_text_range()
                )
                assert "$0$" not in table_page and "$1$" not in table_page
                assert all(value in table_page for value in ("0", "1", "2", "4", "7", "M(n)"))
            if name == "Tadpoles":
                assert "stage–time" in extracted
                assert "not measured or validated mechanisms" in normalized_text
                assert "Research session 1" in normalized_text and "session:sid" not in extracted
                assert all(
                    " ".join(node.label.split()) in normalized_text
                    for node in tadpole_diagram.nodes
                )
                assert all(
                    " ".join(edge.label.split()) in normalized_text
                    for edge in tadpole_diagram.edges
                )
                assert "Proposed intermediate process" in normalized_text
            if name == "ONP":
                assert normalized_text.count("Course") >= 2  # repeated header on continuation page
                assert all(f"Course {index}" in normalized_text for index in range(1, 13))
                assert (
                    "Does not establish legal authority or control over escalation"
                    in normalized_text
                )
                assert "Diagram (readable relationship list)." in normalized_text
                assert all(" ".join(node.label.split()) in normalized_text for node in onp_nodes)
                assert all(" ".join(edge.label.split()) in normalized_text for edge in onp_edges)
                assert "project:pid" not in extracted
            if name == "Diagram":
                assert papers._diagram_layout(graph_diagram) is not None
                assert "edge badge" in tex and "minimum height=" in tex
                assert "Independent review" in normalized_text
                assert all(node.label in normalized_text for node in graph_nodes)
                assert all(edge.label in normalized_text for edge in graph_edges)
            print(
                f"PASS real {name} PDF layout: {len(document)} pages, "
                f"{len(tex.encode())} TeX bytes, "
                f"{len(pdf)} PDF bytes, {len(diagnostics)} compiler diagnostics"
            )

    overlap_tex = papers._tex(draft(), [], "f" * 64, source_reference_map=source_map).replace(
        r"\end{document}",
        r"\par\noindent OVERLAP CONTROL\llap{OBSCURED CONTROL}\par" + "\n" + r"\end{document}",
    )
    overlap_pdf = papers._compile_pdf(
        overlap_tex,
        timeout_seconds=120,
        max_pdf_bytes=40_000_000,
    )
    _, overlap_warnings = papers._pdf_text_bounds_diagnostics(overlap_pdf)
    assert any("substantially overlap" in item for item in overlap_warnings), overlap_warnings
    assert papers._repair_tex_layout(overlap_tex, overlap_warnings) is None
    print("PASS real overprint negative control: overlapping glyph boxes require layout review")


def test_fast_long_draft_obeys_combined_diagram_and_table_preference() -> None:
    package, plan = fast_package()
    plan = plan.model_copy(
        update={
            "diagrams": [
                papers.PaperDiagram(
                    caption="Saved proof candidate and its recorded unresolved check.",
                    nodes=[
                        papers.DiagramNode(id="candidate", label="Candidate argument"),
                        papers.DiagramNode(id="skeptic", label="Skeptic obligation"),
                    ],
                    edges=[
                        papers.DiagramEdge(
                            source="candidate", target="skeptic", label="requires review"
                        )
                    ],
                    evidence_refs=["session:onp-fixture"],
                    claim_ids=["C1"],
                )
            ]
        }
    )
    state = papers._new_work("a" * 64, "fast-fixture", "b" * 64, "fixture-model", "high")
    observed: list[tuple[str, bool | None]] = []
    checked_details: list[tuple[str, dict, str]] = []

    async def provider(input_value, _binding, _config, *, schema_name, **kwargs):
        observed.append((schema_name, kwargs.get("include_diagrams")))
        schema = papers._paper_response_schema(
            kwargs["response_model"], include_diagrams=kwargs["include_diagrams"]
        )
        checked_details.append((schema_name, schema, kwargs["instructions"]))
        if schema_name == "sigma_long_paper_plan":
            assert kwargs["include_diagrams"] is True
            assert "diagrams" in schema["properties"]
            assert "VISUALS" in kwargs["instructions"]
            assert "tables" in kwargs["instructions"]
            return plan, "fixture-model"
        assert kwargs["include_diagrams"] is True
        assert "tables" in schema["properties"]
        assert "TABLES:" in kwargs["instructions"]
        return (
            papers.LongSectionDraft(
                paragraphs=["The section preserves the source-linked candidate and limitation."],
                tables=[
                    papers.PaperTable(
                        caption="Evidence types represented in this section.",
                        headers=["Record", "Finding"],
                        rows=[
                            ["Investigator", "Candidate construction"],
                            ["Skeptic", "Open obligation"],
                        ],
                        evidence_refs=["session:onp-fixture"],
                        claim_ids=["C1"],
                    )
                ],
            ),
            "fixture-model",
        )

    async def check() -> None:
        with patch.object(papers, "_provider_structured", new=provider):
            result, calls, batches = await papers._generate_long_draft(
                package,
                {"identity": "fixture", "mode": "api_key", "token": "fixture"},
                {"model": "fixture-model", "reasoning_effort": "high"},
                state,
                lambda _state: None,
                structured_fast_path=True,
            )
        assert result.diagrams == plan.diagrams
        assert all(section.tables for section in result.sections)
        assert all(
            set(table.evidence_refs) <= {"session:onp-fixture"} and set(table.claim_ids) == {"C1"}
            for section in result.sections
            for table in section.tables
        )
        assert calls == 1 + len(result.sections)
        assert batches == 0

    asyncio.run(check())
    assert observed[0] == ("sigma_long_paper_plan", True)
    assert all(name == "sigma_long_paper_section" for name, _ in observed[1:])
    assert "diagrams" in checked_details[0][1]["properties"]
    assert "VISUALS" in checked_details[0][2]
    assert all(
        "tables" in schema["properties"] and "TABLES:" in instructions
        for name, schema, instructions in checked_details[1:]
        if name == "sigma_long_paper_section"
    )
    assert state["plan"]["diagrams"][0]["evidence_refs"] == ["session:onp-fixture"]

    unchecked_state = papers._new_work("b" * 64, "fast-fixture", "c" * 64, "fixture-model", "high")
    unchecked_calls: list[tuple[str, bool | None]] = []
    unchecked_details: list[tuple[dict, str]] = []

    async def unchecked_provider(input_value, _binding, _config, *, schema_name, **kwargs):
        unchecked_calls.append((schema_name, kwargs.get("include_diagrams")))
        schema = papers._paper_response_schema(
            kwargs["response_model"], include_diagrams=kwargs["include_diagrams"]
        )
        unchecked_details.append((schema, kwargs["instructions"]))
        if schema_name == "sigma_long_paper_plan":
            assert kwargs["include_diagrams"] is False
            return plan.model_copy(update={"diagrams": []}), "fixture-model"
        return papers.LongSectionDraft(
            paragraphs=["Saved prose remains available."],
            tables=[
                papers.PaperTable(
                    caption="A prior section table that must stay out of unchecked output.",
                    headers=["Record", "Finding"],
                    rows=[["Investigator", "Saved"]],
                    evidence_refs=["session:onp-fixture"],
                    claim_ids=["C1"],
                )
            ],
        ), "fixture-model"

    async def check_unchecked() -> None:
        with patch.object(papers, "_provider_structured", new=unchecked_provider):
            result, calls, _ = await papers._generate_long_draft(
                package,
                {"identity": "fixture", "mode": "api_key", "token": "fixture"},
                {"model": "fixture-model", "reasoning_effort": "high"},
                unchecked_state,
                lambda _state: None,
                structured_fast_path=True,
                include_diagrams=False,
            )
        assert result.diagrams == []
        assert all(not section.tables for section in result.sections)
        assert calls == 1 + len(result.sections)

    asyncio.run(check_unchecked())
    assert unchecked_calls[0] == ("sigma_long_paper_plan", False)
    assert all(value is False for _, value in unchecked_calls)
    assert all(
        "diagrams" not in schema["properties"]
        and "tables" not in schema["properties"]
        and "VISUALS" not in instructions
        and "TABLES:" not in instructions
        for schema, instructions in unchecked_details
    )


def main() -> None:
    test_tex_proofreading_preserves_science_and_checkpoints_provider_work()
    test_tex_proofreader_three_passes_with_early_convergence()
    test_tex_diagnostics_allow_geometry_fixes_but_protect_visual_data()
    test_tex_proofreader_rejects_scientific_edits_and_does_not_replay_uncertain_calls()
    test_longtable_semantic_signature_normalizes_every_table_preamble()
    test_pdf_layout_repairs_are_bounded_and_protect_research_semantics()
    test_caption_limits_reject_cutoff_and_allow_complete_long_caption()
    test_real_tadpole_onp_and_math_table_pdfs()
    test_one_shot_and_long_form_both_proofread_before_compiling()
    test_combined_visual_schema_and_safe_tex_rendering()
    test_fast_long_draft_obeys_combined_diagram_and_table_preference()
    test_diagram_compile_fallback_preserves_evidence_tables_and_provider_accounting()
    test_unrelated_compile_failure_does_not_remove_valid_diagrams()
    test_research_details_toggle_preserves_science_and_opt_in_diagnostics()
    test_publication_paragraphs_math_and_bounded_optional_appendix()
    test_summary_only_research_uses_zero_paid_evidence_extraction_calls()
    test_one_shot_provider_failure_requires_explicit_reset_without_rebilling()
    test_structured_index_retains_session_narrative_and_original_question()
    test_easy_paper_start_over_escapes_repeated_paid_planning()
    test_maximum_regions_archived_one_session_stays_fast()
    test_easy_paper_avoids_unnecessary_long_form_calls()
    test_invalid_planning_claim_reference_is_recoverable()
    test_repair_paper_references_preserves_science_and_downgrades_unsupported_claims()
    test_one_shot_publishes_with_repaired_claim_links()
    test_live_research_change_does_not_discard_completed_paper()
    test_frozen_evidence_checkpoint_survives_live_research_drift()
    test_one_shot_validation_failure_preserves_paid_draft_for_continue()
    test_long_paper_planning_timeout_is_stage_specific()
    test_structured_evidence_short_tail_does_not_crash()
    test_unexpected_paper_exception_yields_sanitized_sse_error()
    test_incomplete_chatgpt_paper_stream_is_rejected()
    test_api_provider_failure_classification_is_safe_and_actionable()
    test_chatgpt_schema_rejection_is_actionable_and_redacted()
    test_visual_preference_controls_one_shot_and_long_paper_wire_schemas()
    test_strict_paper_schemas_require_all_properties()
    test_paper_stage_accepts_completed_chatgpt_stream_with_trailing_usage()
    test_long_tex_compiler_source_bound_is_configurable()
    test_one_shot_draft_is_reused_after_pdf_compilation_failure()
    test_proofreading_option_changes_keep_per_render_and_cumulative_call_counts()
    test_snapshot_ignores_elapsed_projection_but_tracks_saved_evidence()
    test_api_paper_stream_reports_progress_and_completion()
    test_paper_progress_endpoint_recovers_interrupted_checkpoint()
    test_restart_uses_current_evidence_and_is_idempotent()
    test_explicit_restart_checkpoint_migrates_and_rebinds_safely()
    test_evidence_envelope_budget_resumes_without_repacking()
    test_long_paper_outline_does_not_duplicate_large_evidence_reference_catalog()
    test_long_index_reduction_resumes_and_preserves_session_conflicts()
    test_structured_fast_index_preserves_math_review_and_bounds_omissions()
    test_bounded_index_keeps_constructive_proof_amid_many_objections()
    test_fast_planner_preview_bounds_input_and_preserves_source_coverage()
    test_long_paper_can_retrieve_sources_outside_planner_preview()
    test_research_type_specific_tex_sections_and_authoring_guidance()
    test_military_style_guidance_reaches_all_authoring_paths()
    test_fast_long_draft_safe_retry_and_unknown_consumption_checkpoint()
    test_failed_planning_checkpoint_continues_without_repeating_paid_plan()
    test_paper_failure_reason_survives_reopen()
    test_fast_long_draft_concurrency_ordered_checkpoints_and_resume()
    test_fast_checkpoint_resume_replays_only_incomplete_section()
    test_fast_long_draft_cancellation_keeps_completed_sections()
    test_paper_generation_rejects_concurrent_duplicate_request()
    test_two_paper_generators_run_concurrently_and_third_fails_fast()
    test_two_papers_reach_compilation_together_and_hold_capacity()
    test_eight_research_sessions_overlap_two_paper_generators()
    test_tadpoles_five_session_mock_provider_to_pdf_timing()
    with TemporaryDirectory() as temporary:
        cancelled_path = Path(temporary) / "cancelled.sigma"
        initialize_project(cancelled_path, "Cancelled paper", "A bounded saved question")
        test_api_disconnect_preserves_running_paper_until_explicit_cancel(cancelled_path)

    class StreamResponse:
        def __init__(self, content: bytes):
            self.headers = {"content-type": "text/event-stream"}
            self.content = content

        async def aiter_bytes(self):
            yield self.content

    assert papers.MAX_CHATGPT_STREAM_BYTES == 16_000_000
    large_event = (
        b'data: {"type":"response.created","sequence_number":0,"response":{"id":"r"},"padding":"'
        + b"x" * 4_100_000
        + b'"}\n\n'
        + b'data: {"type":"response.completed","sequence_number":1,"response":{"id":"r","status":"completed","output":[]}}\n\n'
    )
    parsed_stream = asyncio.run(
        completed(
            cast(httpx.Response, StreamResponse(large_event)),
            max_stream_bytes=papers.MAX_CHATGPT_STREAM_BYTES,
        )
    )
    assert parsed_stream["status"] == "completed"
    try:
        asyncio.run(
            completed(
                cast(httpx.Response, StreamResponse(large_event)),
                max_stream_bytes=papers.MAX_RESPONSE_BYTES,
                overflow_message="ChatGPT paper response exceeded the 1 MB stream limit. No paper was saved.",
            )
        )
    except ProjectError as exc:
        assert "ChatGPT paper response" in str(exc) and "No paper was saved" in str(exc)
        assert "strategy" not in str(exc)
    else:
        raise AssertionError("Paper stream byte limit must be enforced with paper-specific error")

    evidence_export = {
        "project": {
            "id": "pid",
            "title": "A project",
            "strategies": [{"id": "strat-1", "approach": "A saved strategy."}],
        },
        "research_sessions": [
            {
                "id": "session-1",
                "outcome": {
                    "summary": "A partial, agent-reviewed result.",
                    "conclusion": "## Conditional conclusion\nThe result holds under assumption A.",
                    "caveats": ["The argument remains unverified."],
                    "solution_review": {
                        "status": "partial",
                        "limitations": ["The base case has not been independently checked."],
                        "reasoning_steps": [
                            {
                                "number": 1,
                                "argument": "The recurrence follows under assumption A.",
                                "epistemic_status": "assumption",
                                "review": {
                                    "disposition": "challenged",
                                    "rationale": "The cited artifact does not cover the base case.",
                                    "objection": "Check the base case.",
                                },
                            }
                        ],
                        "reasoning_assessments": [
                            {
                                "step_number": 1,
                                "disposition": "challenged",
                                "rationale": "The base case is not included.",
                                "objection": "Check the base case.",
                            }
                        ],
                        "unresolved_objections": ["Check the base case."],
                        "basis_artifact_ids": ["artifact-1"],
                    },
                },
                "artifacts": [
                    {
                        "id": "artifact-1",
                        "claim": "A saved finding.",
                        "reasoning_steps": [
                            {
                                "argument": "The recurrence follows under assumption A.",
                                "epistemic_status": "assumption",
                            }
                        ],
                        "skeptic_response": "The base case remains unresolved.",
                        "objections": ["Check the base case."],
                        "open_obligations": ["Verify the base case."],
                    }
                ],
            }
        ],
        "agentic_runs": [
            {
                "run_id": "run-1",
                "steps": [{"step_id": "step-1", "output": "A saved step."}],
            }
        ],
    }
    with patch("sigma.api.export_project_view", return_value=evidence_export):
        normalized, fingerprint = papers._snapshot("unused")
    source_map = {source["id"]: source for source in normalized["sources"]}
    assert source_map["project:pid"]["data"] == {"id": "pid", "title": "A project"}
    assert source_map["strategy:strat-1"]["data"] == evidence_export["project"]["strategies"][0]
    session_source = source_map["session:session-1"]["data"]
    assert session_source == {
        "id": "session-1",
        "outcome": evidence_export["research_sessions"][0]["outcome"],
    }
    assert (
        source_map["artifact:session-1:artifact-1"]["data"]
        == evidence_export["research_sessions"][0]["artifacts"][0]
    )
    assert source_map["run:run-1"]["data"] == {"run_id": "run-1"}
    assert source_map["step:run-1:step-1"]["data"] == evidence_export["agentic_runs"][0]["steps"][0]
    assert normalized["schema"] == "sigma-paper-evidence-v2" and len(fingerprint) == 64
    outcome_records = papers._research_integrity_records(normalized)
    session_outcome = next(
        item
        for item in outcome_records
        if item["source_ref"] == "session:session-1" and item["field"] == "outcome"
    )
    assert session_outcome["content"] == evidence_export["research_sessions"][0]["outcome"]
    # The frozen integrity records retain every source detail. The opt-in
    # publication appendix is intentionally bounded and only selects excerpts.
    outcome_json = json.dumps(outcome_records, ensure_ascii=False)
    for outcome_text in (
        "Conditional conclusion",
        "The result holds under assumption A.",
        "The argument remains unverified.",
        "The base case is not included.",
        "Check the base case.",
        "Verify the base case.",
    ):
        assert outcome_text in outcome_json
    outcome_tex = papers._tex(draft(), [], "c" * 64, integrity_records=[session_outcome])
    assert r"\section{Structured reasoning and review records}" in outcome_tex
    assert "Conditional conclusion" in outcome_tex
    assert "The argument remains unverified." in outcome_tex

    without_conclusion = json.loads(json.dumps(evidence_export))
    without_conclusion["research_sessions"][0]["outcome"].pop("conclusion")
    with patch("sigma.api.export_project_view", return_value=without_conclusion):
        normalized_without_conclusion, _ = papers._snapshot("unused")
    saved_outcome = next(
        source["data"]["outcome"]
        for source in normalized_without_conclusion["sources"]
        if source["id"] == "session:session-1"
    )
    assert saved_outcome == without_conclusion["research_sessions"][0]["outcome"]
    assert "conclusion" not in saved_outcome

    # Cross-domain contract fixture: the paper retains the published reasoning
    # and review shape from PR #70, alongside experimental negative findings.
    fidelity_package = {
        "sources": [
            {
                "id": "artifact:math-session:proof",
                "kind": "artifact",
                "data": {
                    "reasoning_steps": [
                        {
                            "number": 1,
                            "title": "Upper bound",
                            "argument": "Each inserted line splits at most k existing regions.",
                            "epistemic_status": "deduction",
                            "basis_artifact_ids": ["proof"],
                            "review": {
                                "disposition": "challenged",
                                "rationale": "The argument does not establish the required general position.",
                                "objection": "The construction case remains unresolved.",
                                "basis_artifact_ids": ["skeptic-note"],
                            },
                        }
                    ],
                    "objective_review": {
                        "status": "partial",
                        "argument_steps": [
                            {
                                "argument": "The induction step follows from the recorded recurrence.",
                                "review": {"disposition": "unresolved"},
                            }
                        ],
                        "unresolved_objections": ["Prove attainment in general position."],
                    },
                    "skeptic_output": {
                        "reasoning_assessments": [
                            {
                                "step_number": 1,
                                "disposition": "challenged",
                                "rationale": "A boundary case is missing.",
                                "objection": "Check the base case.",
                            }
                        ]
                    },
                    "failed_approaches": ["The first construction violates general position."],
                },
            },
            {
                "id": "session:xenopus-negative",
                "kind": "session",
                "data": {
                    "findings": ["Late-inhibition cohort showed zero observed regeneration."],
                    "negative_findings": [
                        "No regeneration was observed in the late-inhibition cohort."
                    ],
                    "contradictions": [
                        "The early-inhibition session reports regeneration under a different dose."
                    ],
                },
            },
            {
                "id": "session:xenopus-positive",
                "kind": "session",
                "data": {
                    "findings": [
                        "Early-inhibition cohort showed tail regeneration under the lower dose."
                    ]
                },
            },
        ]
    }
    integrity_records = papers._long_paper_integrity_records(
        fidelity_package,
        {
            "preserved_evidence_notes": [
                {
                    "kind": "negative",
                    "statement": "The replicate did not restore tail growth.",
                    "evidence_refs": ["session:xenopus-negative"],
                }
            ],
            "conflict_notes": [
                {
                    "statement": "Sessions disagree across dose conditions.",
                    "evidence_refs": ["session:xenopus-negative", "session:xenopus-positive"],
                }
            ],
        },
    )
    integrity_json = json.dumps(integrity_records, ensure_ascii=False)
    for required in (
        "Upper bound",
        "deduction",
        "challenged",
        "general position",
        "reasoning_assessments",
        "No regeneration was observed",
        "Early-inhibition cohort showed tail regeneration",
        "Sessions disagree across dose conditions",
    ):
        assert required in integrity_json
    integrity_tex = papers._tex(
        draft(),
        [],
        "b" * 64,
        integrity_records=integrity_records,
        material_omissions=[
            {"field": "data/negative_findings", "source_ref": "session:xenopus-negative"}
        ],
        include_research_excerpts=True,
    )
    assert r"\section{Structured reasoning and review records}" in integrity_tex
    assert r"\section*{Evidence coverage limitation}" in integrity_tex
    opening_heading = papers._paper_style("default")[0]
    assert integrity_tex.index("Evidence coverage limitation") < integrity_tex.index(
        r"\section{" + opening_heading + "}"
    )
    material = papers._material_evidence_omissions(
        [
            {"field": "data/id", "source_ref": "artifact:math-session:proof"},
            {
                "field": "data/reasoning_steps/0/argument",
                "source_ref": "artifact:math-session:proof",
            },
        ]
    )
    assert len(material) == 1
    substantive = draft().model_copy(deep=True)
    original_abstract = substantive.abstract
    original_conclusions = list(substantive.conclusions)
    limited = papers._apply_omission_limits(substantive, material)
    # Coverage is disclosed without rewriting unrelated claims or the abstract.
    assert limited.claims[0].status == substantive.claims[0].status
    assert limited.abstract == original_abstract
    assert limited.conclusions == original_conclusions
    assert any("Evidence indexing omitted" in warning for warning in limited.validation_warnings)
    limited_math_tex = papers._tex(
        limited, [], "d" * 64, math_style=True, material_omissions=material
    )
    assert "Evidence coverage limitation" in limited_math_tex
    assert "were not reviewed for this paper" in limited_math_tex
    assert original_abstract in limited_math_tex
    assert original_conclusions[0] in limited_math_tex

    large_export = {
        "project": {"id": "pid", "problem": "x" * 81_900},
        "research_sessions": [],
        "agentic_runs": [],
    }
    with patch("sigma.api.export_project_view", return_value=large_export):
        large_snapshot, _ = papers._snapshot("unused")
    assert len(papers._json(large_snapshot)) > 65_000
    assert len(papers._json(large_snapshot)) <= papers.MAX_CONTEXT_BYTES
    with (
        patch("sigma.api.export_project_view", return_value=evidence_export),
        patch.object(papers, "MAX_CONTEXT_BYTES", 10),
    ):
        try:
            papers._snapshot("unused")
        except ProjectError as exc:
            assert "bytes" in str(exc) and "No evidence was omitted" in str(exc)
        else:
            raise AssertionError("Oversized complete evidence snapshots must be rejected")

    package = {"sources": [{"id": "project:pid", "data": {"problem": "A question"}}]}
    parsed = draft()
    warnings = papers._validate(parsed, package)
    assert any("not independent formal verification" in item for item in warnings)
    adversarial = parsed.model_copy(
        update={
            "claims": [
                parsed.claims[0].model_copy(
                    update={"status": "established", "evidence_refs": ["artifact:s1:a1"]}
                )
            ],
            "sections": [
                parsed.sections[0].model_copy(
                    update={"paragraphs": ["Prior work (Smith et al., 2024) confirms the result."]}
                ),
                parsed.sections[1],
            ],
            "open_obligations": [],
        }
    )
    adversarial_warnings = papers._validate(
        adversarial,
        {
            "sources": [
                {
                    "id": "artifact:s1:a1",
                    "data": {
                        "evidence_status": "incomplete, unverified",
                        "claim": "A counterexample contradicts the proposed result.",
                        "open_obligations": ["Resolve the counterexample and prove the bound."],
                    },
                }
            ]
        },
    )
    assert any("labeled established" in item for item in adversarial_warnings)
    assert any("counterexample or contradiction" in item for item in adversarial_warnings)
    assert any("Citation-like external references" in item for item in adversarial_warnings)
    assert any("open proof/research obligation" in item for item in adversarial_warnings)
    frozen_obligations = {
        "sources": [
            {
                "id": "artifact:max-regions:proof",
                "data": {"open_obligations": [f"Frozen obligation {index}" for index in range(12)]},
            }
        ]
    }
    reconciliation = papers._reconcile_obligations(
        parsed.model_copy(update={"open_obligations": []}), frozen_obligations
    )
    assert len(reconciliation) == 12
    assert all(
        item["source_refs"] == ["artifact:max-regions:proof:open_obligations"]
        for item in reconciliation
    )
    assert all(
        item["status"] == "Not listed by author; not presumed resolved" for item in reconciliation
    )
    reconciled_tex = papers._tex(
        parsed,
        [],
        "a" * 64,
        obligation_reconciliation=reconciliation,
    )
    assert r"\section{Frozen obligation reconciliation}" in reconciled_tex
    assert "Frozen obligation 11" in reconciled_tex
    listed = papers._reconcile_obligations(
        parsed.model_copy(update={"open_obligations": ["  Frozen   obligation 0 "]}),
        frozen_obligations,
    )
    assert listed[0]["status"] == "Listed as open in paper"
    assert listed[1]["status"] == "Not listed by author; not presumed resolved"
    try:
        papers._validate(draft("artifact:unknown"), package)
    except ProjectError as exc:
        assert "unknown evidence IDs" in str(exc)
    else:
        raise AssertionError("Unknown evidence references must be rejected")
    tex = papers._tex(parsed, warnings, "a" * 64)
    assert r"AI-generated research synthesis \textperiodcentered{} SIGMA" in tex
    assert r"\section*{About this paper}" in tex
    about_start = tex.index(r"\section*{About this paper}")
    assert about_start < tex.index(r"\section{" + papers._paper_style("default")[0] + "}")
    assert (
        "This paper was generated by SIGMA, an AI-assisted research system, from the project's recorded investigations, findings, and supporting evidence."
        in tex
    )
    assert "The analysis and conclusions reflect an automated synthesis of that research." in tex
    assert (
        "Readers should evaluate its arguments, supporting evidence, and stated limitations before relying on its conclusions."
        in tex
    )
    assert r"\frac{n(n+1)}{2}" in tex
    assert r"\textbackslash{}input" not in tex
    notation = papers._latex_prose(r"Let $R(\mathcal{A})$ denote the region count.")
    assert r"$R(\mathcal{A})$" in notation
    assert r"\textbackslash{}mathcal" not in notation
    formula_draft = parsed.model_copy(
        update={
            "claims": [
                parsed.claims[0].model_copy(
                    update={
                        "statement": r"The count is $R(n)=1+\sum_{j=1}^n j²$.",
                        "reasoning": r"The line family lies in $\mathbb{R}^2$.",
                    }
                )
            ]
        }
    )
    formula_tex = papers._tex(formula_draft, warnings, "a" * 64, math_style=True)
    assert r"$R(n)=1+\sum_{j=1}^n j^{2}$" in formula_tex
    assert r"$\mathbb{R}^2$" in formula_tex
    assert r"\textbackslash{}sum" not in formula_tex
    assert r"\textbackslash{}mathbb" not in formula_tex
    unicode_superscript = papers._latex_prose("The saved construction uses j².")
    assert "$j^{2}$" in unicode_superscript
    math_tex = papers._tex(parsed, warnings, "a" * 64, math_style=True)
    math_opening, math_methods, _, _ = papers._paper_style("mathematical")
    assert r"\section{" + math_opening + "}" in math_tex
    assert r"\section{" + math_methods + "}" in math_tex
    assert r"\section{Verification status and limitations}" in math_tex
    assert r"\section{Conclusion}" in math_tex
    assert math_tex.index(r"\section{Conclusion}") < math_tex.index(
        r"\section*{Claim status and evidence}"
    )
    injected_section = parsed.sections[0].model_copy(
        update={"paragraphs": [r"Run \input{host-file} now."]}
    )
    injected = parsed.model_copy(update={"sections": [injected_section, *parsed.sections[1:]]})
    injected_tex = papers._tex(injected, warnings, "a" * 64)
    assert r"\textbackslash{}input" in injected_tex
    assert "host-file" in injected_tex
    assert r"\section{Open obligations}" in tex

    with TemporaryDirectory() as temporary:
        path = Path(temporary) / "fixture.sigma"
        initialize_project(path, "Fixture", "Investigate the saved question")
        credential = {"identity": "chatgpt:fixture", "mode": "chatgpt", "token": "fixture"}
        config = {
            "available": True,
            "binding": credential["identity"],
            "model": "gpt-6.1-sol",
            "reasoning_effort": "high",
        }

        async def fake_provider(context, *_args):
            project_source = next(
                item["id"] for item in context["sources"] if item["kind"] == "project"
            )
            return draft(project_source), config["model"]

        with (
            patch.object(papers, "auth_context", new=lambda: asyncio.sleep(0, result=credential)),
            patch.object(
                papers, "configuration", new=lambda **kwargs: asyncio.sleep(0, result=config)
            ),
            patch.object(papers, "_provider", new=fake_provider),
            patch.object(papers, "_compile_pdf", new=lambda *_args, **_kwargs: b"%PDF-fixture"),
            mock_pdf_inspection(),
        ):
            first = asyncio.run(papers.generate(str(path), credential["identity"]))
            second = asyncio.run(papers.generate(str(path), credential["identity"]))
        assert first["paper_id"] != second["paper_id"]
        assert len(papers.list_papers(str(path))) == 2
        record = papers.get_paper(str(path), first["paper_id"])
        assert record["snapshot_sha256"] == first["snapshot_sha256"]
        assert record["tex_source"].startswith(r"\documentclass")
        assert r"\end{document}" in record["tex_source"]
        assert papers.paper_tex(str(path), first["paper_id"]) == record["tex_source"]
        # Default publication mode omits opt-in research-system frontmatter.
        assert r"\section*{About this paper}" not in record["tex_source"]
        assert "AI-generated research synthesis" not in record["tex_source"]
        assert "SIGMA AI-assisted research synthesis" in record["tex_source"]
        assert record["generation"]["call_limit"] == 1 + papers.MAX_PROOFREAD_CALLS
        assert papers.get_pdf(str(path), first["paper_id"]).startswith(b"%PDF-")
        saved_text = papers.paper_text(str(path), first["paper_id"])
        assert saved_text.startswith("An evidence-bound exploratory note\n")
        assert (
            "Abstract" in saved_text
            and "This paper does not establish a formal proof." in saved_text
        )
        assert record["snapshot"]["sources"][0]["id"] == "project:" + record["project_id"]
        assert len(inspect_project(path).project.events) == 1
        papers.delete_paper(str(path), first["paper_id"])
        assert [item["paper_id"] for item in papers.list_papers(str(path))] == [second["paper_id"]]
        assert not (path.parent / "papers" / f"{first['paper_id']}.json").exists()
        assert not (path.parent / "papers" / f"{first['paper_id']}.pdf").exists()
        assert len(inspect_project(path).project.events) == 1

        exploratory_path = Path(temporary) / "unresolved.sigma"
        initialize_project(
            exploratory_path,
            "Unresolved question",
            "Determine whether this open question is tractable",
        )

        async def exploratory_provider(context, *_args):
            project_source = next(
                item["id"] for item in context["sources"] if item["kind"] == "project"
            )
            return papers.PaperDraft.model_validate(
                {
                    "title": "An Exploratory Record with Open Questions",
                    "abstract": "The saved project defines an open question but contains no research session or findings. This paper therefore records an exploratory state and identifies the evidence needed for future work, without forcing the material into a theorem-proof narrative.",
                    "abstract_claim_ids": ["C1"],
                    "problem_framing": [
                        "The project objective is recorded without a saved result."
                    ],
                    "problem_framing_claim_ids": ["C1"],
                    "methods": [
                        "We inspected the complete project snapshot; no research session or experiment was recorded."
                    ],
                    "methods_claim_ids": ["C1"],
                    "claims": [
                        {
                            "id": "C1",
                            "statement": "The saved project contains the stated research objective.",
                            "status": "established",
                            "evidence_refs": [project_source],
                            "reasoning": "This is directly present in the snapshot.",
                        }
                    ],
                    "sections": [
                        {
                            "heading": "Available evidence",
                            "paragraphs": [
                                "There are no saved research findings in this snapshot."
                            ],
                            "claim_ids": ["C1"],
                        },
                        {
                            "heading": "Research remains open",
                            "paragraphs": ["No substantive conclusion is supported yet."],
                            "claim_ids": [],
                        },
                    ],
                    "limitations": ["No research session or experimental result is available."],
                    "open_obligations": [
                        "Conduct and persist an investigation before drawing a substantive conclusion."
                    ],
                    "conclusions": ["This is an exploratory note, not a theorem-proof paper."],
                    "conclusion_claim_ids": ["C1"],
                    "validation_warnings": [],
                }
            ), config["model"]

        with (
            patch.object(papers, "auth_context", new=lambda: asyncio.sleep(0, result=credential)),
            patch.object(
                papers, "configuration", new=lambda **kwargs: asyncio.sleep(0, result=config)
            ),
            patch.object(papers, "_provider", new=exploratory_provider),
            patch.object(papers, "_compile_pdf", new=lambda *_args, **_kwargs: b"%PDF-fixture"),
            mock_pdf_inspection(),
        ):
            exploratory = asyncio.run(papers.generate(str(exploratory_path)))
        exploratory_record = papers.get_paper(str(exploratory_path), exploratory["paper_id"])
        assert exploratory_record["draft"]["title"] == "An Exploratory Record with Open Questions"
        assert not any(
            item["kind"] == "session" for item in exploratory_record["snapshot"]["sources"]
        )
    print(
        "Paper snapshots, provenance/obligation fidelity, bounded fast indexing, retry, "
        "concurrent checkpoints, resume, cancellation, TeX styles, and version retention passed."
    )


if __name__ == "__main__":
    # Fixture credentials must never reach the real model service. Provider
    # protocol tests install their own MockTransport; all other client calls
    # receive a local response so the engineering suite cannot incur charges.
    real_async_client = httpx.AsyncClient

    def offline_async_client(*args, **kwargs):
        if "transport" not in kwargs:
            kwargs["transport"] = httpx.MockTransport(
                lambda _request: httpx.Response(
                    503,
                    json={"error": {"code": "offline_test_fixture", "message": "offline"}},
                )
            )
        return real_async_client(*args, **kwargs)

    httpx.AsyncClient = offline_async_client  # type: ignore[assignment]
    try:
        main()
    finally:
        httpx.AsyncClient = real_async_client
