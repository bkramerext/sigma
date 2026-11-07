# ruff: noqa: F401
# pyright: reportUndefinedVariable=false
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

if __package__:
    from .papers_part1 import draft, fast_package, mock_pdf_inspection
else:
    from papers_part1 import draft, fast_package, mock_pdf_inspection


def test_paper_pdf_source_reader_accepts_only_substantial_extractable_text() -> None:
    """A real repository PDF can be parsed; short/invalid material is skipped."""
    from sigma import paper_writing_sources

    example = Path("tests/fixtures/sigma-valid-sample-paper.pdf").read_bytes()
    extracted = paper_writing_sources._pdf_excerpt(example)
    assert extracted is None or isinstance(extracted, str)
    assert paper_writing_sources._pdf_excerpt(b"not a PDF") is None
    assert paper_writing_sources.readable("please sign in") is None


def test_writing_guidance_is_listed_in_paper_tex_without_becoming_evidence() -> None:
    source = {
        "title": "Writing Mathematics",
        "url": "https://example.org/writing-math",
        "tier": "discipline",
        "type": "mathematical",
        "branch": "general",
        "excerpt": "A source excerpt used only for writing.",
        "sha256": "a" * 64,
    }
    # Editorial sources are recorded but omitted from PDFs without details.
    default_tex = papers._tex(draft(), [], "f" * 64, writing_sources=[source])
    assert r"\section{Publication references used}" not in default_tex
    assert "Writing Mathematics" not in default_tex

    # When validation notes are explicitly requested, sources are disclosed as
    # writing-method guidance and distinguished from scientific evidence.
    tex = papers._tex(
        draft(), [], "f" * 64, writing_sources=[source], include_validation_notes=True
    )
    assert r"\section{Publication references used}" in tex
    assert "Writing Mathematics" in tex
    assert r"\url{https://example.org/writing-math}" in tex
    assert "not the scientific evidence or findings" in tex
    comparison = papers.reference_efficiency.compare(
        {"paper_writing_methodology": [{"writing_guidance_excerpt": "a" * 1600}]},
        {"paper_writing_methodology": [{"writing_guidance": "short guidance"}]},
    )
    assert comparison["original_estimated_tokens"] > comparison["compiled_estimated_tokens"]
    with_metrics = papers._tex(
        draft(),
        [],
        "f" * 64,
        include_validation_notes=True,
        writing_sources=[source],
        reference_comparison=comparison,
    )
    assert r"\subsection{Reference compilation efficiency (estimated)}" in with_metrics
    assert "not provider-measured billable tokens" in with_metrics
    assert str(comparison["original_estimated_tokens"]) in with_metrics
    no_diagnostics = papers._tex(draft(), [], "f" * 64, reference_comparison=comparison)
    assert "Reference compilation efficiency" not in no_diagnostics
    empty_tex = papers._tex(draft(), [], "f" * 64, include_validation_notes=True)
    assert "No external writing-guidance sources were recorded." in empty_tex


def test_math_and_physics_methodology_reaches_every_authoring_path() -> None:
    """Each project type gets general, evidence-specific genre instructions."""

    def check_case(project_type: str, marker: str, second_marker: str, excluded: str) -> None:
        package, plan = fast_package()
        package["sources"][0]["data"]["investigation_type"] = project_type
        package["sources"][0]["data"]["problem"] = "Study the stated research question."
        seen: dict[str, list[str]] = {}
        frozen_checklist = "State the unverified proof obligations explicitly."

        async def fake_stage(_input, _binding, _config, *, instructions, schema_name, **_kwargs):
            seen.setdefault(schema_name, []).append(instructions)
            assert _input["paper_writing_methodology"] == [{"writing_guidance": frozen_checklist}]
            if schema_name == "sigma_long_paper_plan":
                return plan, "fixture-model"
            assert schema_name == "sigma_long_paper_section"
            return papers.LongSectionDraft(
                paragraphs=["The bounded source analysis supports a conditional result."]
            ), "fixture-model"

        state = papers._new_work("a" * 64, "fast-fixture", "b" * 64, "fixture-model", "high")
        state["publication_compilation"] = {
            "status": "completed",
            "checklist": [frozen_checklist],
        }

        async def write_long() -> None:
            with patch.object(papers, "_provider_structured", new=fake_stage):
                draft_value, _calls, _batches = await papers._generate_long_draft(
                    package,
                    {"mode": "api_key", "identity": "fixture", "token": "fixture"},
                    {"model": "fixture-model", "reasoning_effort": "high"},
                    state,
                    lambda _state: None,
                    structured_fast_path=True,
                )
            assert draft_value.sections

        asyncio.run(write_long())
        assert set(seen) == {"sigma_long_paper_plan", "sigma_long_paper_section"}
        for value in seen.values():
            for instructions in value:
                assert marker in instructions
                assert second_marker in instructions
                assert excluded not in instructions

        requests: list[dict[str, Any]] = []

        async def handler(request: httpx.Request) -> httpx.Response:
            requests.append(json.loads(request.content))
            return httpx.Response(400, json={"error": {"code": "invalid_json_schema"}})

        real_client = httpx.AsyncClient
        with patch(
            "sigma.papers.httpx.AsyncClient",
            side_effect=lambda **kwargs: real_client(
                transport=httpx.MockTransport(handler), **kwargs
            ),
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
        assert marker in requests[0]["instructions"]
        assert second_marker in requests[0]["instructions"]
        assert excluded not in requests[0]["instructions"]

        opening, methods, _, _ = papers._paper_style(project_type)
        tex = papers._tex(draft(), [], "f" * 64, investigation_type=project_type)
        assert rf"\section{{{opening}}}" in tex
        assert rf"\section{{{methods}}}" in tex
        assert marker not in papers._paper_style("default")[3]

    check_case(
        "mathematical",
        "lemmas by logical dependency",
        "a universal proof",
        "chosen metric or field ansatz",
    )
    check_case(
        "physics",
        "theoretical derivation",
        "A chosen metric or field ansatz",
        "Finite enumeration or numerical pattern matching",
    )


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


def test_pre_stream_http_503_has_bounded_retry_without_replaying_partial_output() -> None:
    """An explicit unavailable HTTP response is not an ambiguous SSE failure."""
    package, plan = fast_package(section_count=2)
    state = papers._new_work("1" * 64, "fast-fixture", "2" * 64, "fixture-model", "medium")
    attempts: dict[int, int] = {}
    events: list[tuple[str, int | None, int | None]] = []

    async def provider(input_value, _binding, _config, *, schema_name, **_kwargs):
        if schema_name == "sigma_long_paper_plan":
            return plan, "fixture-model"
        number = input_value["section_number"]
        attempts[number] = attempts.get(number, 0) + 1
        if number == 1 and attempts[number] == 1:
            raise papers.PaperServiceUnavailable("HTTP 503 before any output")
        return papers.LongSectionDraft(
            paragraphs=[f"Evidence-supported section {number}."]
        ), "fixture-model"

    async def progress(stage, current, total, state="active", *, detail=None):
        del state, detail
        events.append((stage, current, total))

    async def run():
        with patch.object(papers, "_provider_structured", new=provider):
            result, calls, batches = await papers._generate_long_draft(
                package,
                {"identity": "fixture", "mode": "api_key", "token": "fixture"},
                {"model": "fixture-model", "reasoning_effort": "medium"},
                state,
                lambda _checkpoint: None,
                progress,
                structured_fast_path=True,
            )
        assert len(result.sections) == 2
        assert calls == 4  # plan + rejected 503 + retried section + sibling section
        assert batches == 0

    asyncio.run(run())
    assert attempts == {1: 2, 2: 1}
    assert state["provider_calls_total"] == 4
    assert set(state["section_drafts"]) == {"1", "2"}
    assert ("retry", 1, 3) in events

    # The real adapter must classify only an explicit HTTP 503 as safe;
    # quota-coded 503s and post-200 partial streams remain non-replayable.
    real_client = httpx.AsyncClient

    async def check_http_error(code):
        async def handler(_request):
            return httpx.Response(503, json={"error": {"code": code}})

        with (
            patch.object(papers.cloud_workspaces, "enabled", return_value=False),
            patch.object(
                papers.httpx,
                "AsyncClient",
                side_effect=lambda **kwargs: real_client(
                    transport=httpx.MockTransport(handler), **kwargs
                ),
            ),
        ):
            try:
                await papers._provider_structured(
                    {"section_number": 1, "evidence_notes": []},
                    {"mode": "chatgpt", "token": "fixture"},
                    {"model": "gpt-6.1-sol", "reasoning_effort": "medium"},
                    instructions="Write a factual section using saved evidence only.",
                    schema_name="sigma_long_paper_section",
                    response_model=papers.LongSectionDraft,
                )
            except papers.PaperServiceUnavailable:
                return "safe"
            except ProjectError:
                return "blocked"
        raise AssertionError("HTTP error must never produce a section")

    assert asyncio.run(check_http_error("server_error")) == "safe"
    assert asyncio.run(check_http_error("insufficient_quota")) == "blocked"


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


def test_verbose_paper_output_diagnostics_are_opt_in() -> None:
    """Keep high-frequency output counters silent by default without hiding outcomes."""
    package, plan = fast_package(section_count=2)

    async def provider(input_value, _binding, _config, *, schema_name, on_output_delta=None, **_kwargs):
        if schema_name == "sigma_long_paper_plan":
            return plan, "fixture-model"
        assert schema_name == "sigma_long_paper_section"
        if on_output_delta is not None:
            await on_output_delta()
        return papers.LongSectionDraft(
            paragraphs=[f"Supported argument for section {input_value['section_number']}."]
        ), "fixture-model"

    async def on_output_delta(_number: int) -> None:
        return None

    async def run(enabled: bool) -> list[str]:
        state = papers._new_work("d" * 64, "fast-fixture", "e" * 64, "fixture-model", "high")
        with (
            patch.object(papers, "_provider_structured", new=provider),
            patch.object(papers, "_PAPER_VERBOSE_DIAGNOSTICS", enabled),
            patch.object(papers.logging.getLogger("sigma.lifecycle"), "info") as info_log,
        ):
            generated, _, _ = await papers._generate_long_draft(
                package,
                {"identity": "fixture", "mode": "api_key", "token": "fixture"},
                {"model": "fixture-model", "reasoning_effort": "high"},
                state,
                lambda _value: None,
                structured_fast_path=True,
                on_output_delta=on_output_delta,
            )
            assert len(generated.sections) == 2
        return [call.args[0] for call in info_log.call_args_list if call.args]

    quiet, verbose = asyncio.run(run(False)), asyncio.run(run(True))
    assert not any(name.startswith("paper.provider_output ") for name in quiet)
    assert any(name.startswith("paper.provider_output ") for name in verbose)
    assert any(name.startswith("paper.provider_attempt_ended ") for name in quiet)
    assert any(name.startswith("paper.section_saved ") for name in quiet)


def test_long_paper_section_retries_share_one_hour_budget() -> None:
    """A slow failed call cannot silently earn two more one-hour attempts."""
    package, plan = fast_package(section_count=2)
    state = papers._new_work("3" * 64, "fast-fixture", "4" * 64, "fixture-model", "high")
    simulated_seconds = [0.0]
    attempts: dict[int, int] = {}
    second_section_started = asyncio.Event()

    async def provider(input_value, _binding, _config, *, schema_name, **_kwargs):
        if schema_name == "sigma_long_paper_plan":
            return plan, "fixture-model"
        number = input_value["section_number"]
        attempts[number] = attempts.get(number, 0) + 1
        if number == 1:
            # Ensure the sibling has begun before the simulated failure,
            # so this test actually verifies checkpointed concurrent work.
            await second_section_started.wait()
            simulated_seconds[0] += papers.CALL_SECONDS
            raise papers.PaperTransientFailure("fixture slow response ended")
        second_section_started.set()
        return papers.LongSectionDraft(paragraphs=[f"Saved section {number}."]), "fixture-model"

    async def generate() -> None:
        with (
            patch.object(papers, "_provider_structured", new=provider),
            patch.object(papers, "monotonic", side_effect=lambda: simulated_seconds[0]),
        ):
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
                assert "Paper section 1" in str(exc)
                assert "did not finish" in str(exc)
            else:
                raise AssertionError("Exhausted section must not become an editorial placeholder")

    with patch.object(papers.logging.getLogger("sigma.lifecycle"), "info") as info_log:
        asyncio.run(generate())
    event_names = [call.args[0] for call in info_log.call_args_list if call.args]
    assert any(name.startswith("paper.section_queue ") for name in event_names)
    assert any(name.startswith("paper.section_slot_acquired ") for name in event_names)
    assert any(name.startswith("paper.section_input_prepared ") for name in event_names)
    assert any(name.startswith("paper.section_saved ") for name in event_names)
    assert attempts == {1: 1, 2: 1}
    assert "1" not in state["section_drafts"]
    assert state["section_drafts"]["2"]["paragraphs"] == ["Saved section 2."]
    assert state["provider_calls_total"] == 3


def test_transient_paper_failures_preserve_authored_sections_and_block_publication() -> None:
    """A failed in-flight section must not be replayed or published as prose."""
    package, plan = fast_package(section_count=5)
    state = papers._new_work("e" * 64, "fast-fixture", "f" * 64, "fixture-model", "high")
    attempts: dict[int, int] = {}
    retry_details: list[str] = []

    async def provider(input_value, _binding, _config, *, schema_name, **_kwargs):
        if schema_name == "sigma_long_paper_plan":
            return plan, "fixture-model"
        number = input_value["section_number"]
        attempts[number] = attempts.get(number, 0) + 1
        if number == 1:
            raise papers.PaperTransientFailure("fixture stream ended without completion")
        return papers.LongSectionDraft(paragraphs=[f"Saved section {number}."]), "fixture-model"

    async def progress(
        stage: papers.PaperProgressStage,
        current: int | None,
        total: int | None,
        state: papers.PaperProgressState = "active",
        *,
        detail: str | None = None,
    ) -> None:
        if stage == "retry" and detail:
            retry_details.append(detail)

    async def generate() -> None:
        with patch.object(papers, "_provider_structured", new=provider):
            try:
                await papers._generate_long_draft(
                    package,
                    {"identity": "fixture", "mode": "api_key", "token": "fixture"},
                    {"model": "fixture-model", "reasoning_effort": "high"},
                    state,
                    lambda _value: None,
                    progress,
                    structured_fast_path=True,
                )
            except ProjectError as exc:
                assert "Paper section 1" in str(exc)
                assert "did not finish" in str(exc)
            else:
                raise AssertionError("Failed section must block publication")

    asyncio.run(generate())
    assert attempts[1] == 1
    assert "1" not in state["section_drafts"]
    assert all(
        item["paragraphs"] == [f"Saved section {number}."]
        for number, item in ((int(key), value) for key, value in state["section_drafts"].items())
    )
    assert all(
        "Editorial notice" not in paragraph
        for value in state["section_drafts"].values()
        for paragraph in value["paragraphs"]
    )
    assert retry_details == []
    calls_before = state["provider_calls"]

    async def no_repeat(*_args, **_kwargs):
        raise AssertionError("No ambiguous paid section may be replayed on Resume")

    async def resume() -> None:
        with patch.object(papers, "_provider_structured", new=no_repeat):
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
                assert "no authored text" in str(exc)
                assert "1 (" in str(exc)
            else:
                raise AssertionError("Resume must not invent a missing section")

    asyncio.run(resume())
    assert state["provider_calls"] == calls_before


def test_unreadable_authored_control_bytes_compile_with_visible_review_marks() -> None:
    source = "\\documentclass{article}\\begin{document}$i=1,\x02ldots,n$ and $R\x1c1+\x1a_{k=1}^n k$\\end{document}"
    repaired, codes = papers._visible_invalid_tex_controls(source)
    assert codes == ["U+0002", "U+001A", "U+001C"]
    assert "[U+0002]" in repaired and "[U+001C]" in repaired
    assert "\x02" in source and "\x02" not in repaired


def manual_tectonic_control_byte_pdf_compilation() -> None:
    """Optional Tectonic integration check; deliberately not in the routine test driver."""
    source = (
        "\\documentclass{article}\\begin{document}"
        "$i=1,\x02ldots,n$ and $R\x1c1+\x1a_{k=1}^n k$"
        "\\end{document}"
    )
    repaired, codes = papers._visible_invalid_tex_controls(source)
    assert codes == ["U+0002", "U+001A", "U+001C"]
    pdf = papers._compile_pdf(repaired)
    assert pdf.startswith(b"%PDF-")


def test_paper_diagram_layout_selection_and_vector_rendering() -> None:
    """Choose diagram semantics once, then render them without paid providers."""
    nodes = [
        papers.DiagramNode(id="source", label="Evidence collection"),
        papers.DiagramNode(id="review", label="Independent review"),
        papers.DiagramNode(id="result", label="Qualified conclusion"),
    ]
    steps = [
        papers.DiagramEdge(source="source", target="review", label="precedes"),
        papers.DiagramEdge(source="review", target="result", label="precedes"),
    ]
    base = papers.PaperDiagram(
        caption="Evidence-based sequence from collection to qualified conclusion.",
        nodes=nodes,
        edges=steps,
        claim_ids=["C1"],
    )
    # Legacy saved diagrams have no layout property; auto is backward-compatible.
    assert (
        papers.PaperDiagram.model_validate(
            {key: value for key, value in base.model_dump().items() if key != "layout"}
        ).layout
        == "auto"
    )
    assert papers._diagram_selected_layout(base) == ("hierarchical", None)
    assert (
        "layout"
        in papers._paper_response_schema(papers.PaperDraft, include_diagrams=True)["$defs"][
            "PaperDiagram"
        ]["properties"]
    )

    def render(diagram: papers.PaperDiagram) -> tuple[str, list[str]]:
        warnings: list[str] = []
        value = draft("project:pid").model_copy(update={"diagrams": [diagram]})
        return papers._tex(value, warnings, "f" * 64), warnings

    hierarchical, errors = render(base.model_copy(update={"layout": "hierarchical"}))
    assert r"\begin{tikzpicture}" in hierarchical
    assert "Diagram (readable relationship list)." not in hierarchical
    assert not errors

    timeline, errors = render(base.model_copy(update={"layout": "timeline"}))
    assert r"\node[timeline node]" in timeline
    assert timeline.count(r"\node[timeline marker]") == 3
    assert timeline.count(r"\draw[->,thick,blue!65]") == 2
    assert all(node.label in timeline for node in nodes)
    assert all(edge.label in timeline for edge in steps)
    assert not errors

    # A timeline is a semantic authorial claim; branching is not chronology.
    branching = base.model_copy(
        update={
            "edges": [
                papers.DiagramEdge(source="source", target="review", label="supports"),
                papers.DiagramEdge(source="source", target="result", label="supports"),
            ],
            "layout": "timeline",
        }
    )
    assert papers._diagram_selected_layout(branching)[0] == "hierarchical"
    _, errors = render(branching)
    assert any("timeline" in warning for warning in errors)

    cyclic = base.model_copy(
        update={
            "edges": [
                *steps,
                papers.DiagramEdge(source="result", target="source", label="feedback loop"),
            ],
            "layout": "auto",
        }
    )
    assert papers._diagram_selected_layout(cyclic) == ("network", None)
    network, errors = render(cyclic)
    assert r"\node[network node]" in network
    assert network.count(r"\draw[->,blue!65,thin]") == 3
    assert "feedback loop" in network
    assert "Diagram (readable relationship list)." not in network
    assert not errors

    forced_dag = cyclic.model_copy(update={"layout": "hierarchical"})
    assert papers._diagram_selected_layout(forced_dag)[0] == "network"
    _, errors = render(forced_dag)
    assert any("cyclic" in warning for warning in errors)

    boundary = papers.DiagramBoundary(label="Review authority", node_ids=["source", "review"])
    architecture = base.model_copy(update={"layout": "architecture", "boundaries": [boundary]})
    assert papers._diagram_selected_layout(architecture) == ("architecture", None)
    block, errors = render(architecture)
    assert r"\begin{tikzpicture}" in block
    assert r"\node[boundary,fit=" in block
    assert "Review authority" in block
    assert all(node.label in block for node in nodes)
    assert not errors

    # Safety: a network cannot silently omit an authored trust boundary.
    unsuitable = cyclic.model_copy(update={"layout": "network", "boundaries": [boundary]})
    assert papers._diagram_selected_layout(unsuitable)[0] == "architecture"
    _, errors = render(unsuitable)
    assert any("trust boundaries" in warning for warning in errors)


def test_graph_atlas_sample_has_four_exact_research_diagrams() -> None:
    """The shipped CS sample is a real editable project with saved fixture evidence."""
    from sigma import recents, research_sessions, samples

    identifier = "graph-atlas-research-gateway"
    raw, template = samples._load(identifier)
    assert template.investigation_type == "computer_science"
    assert template.title == "Graph Atlas: Four Views of a Computing System"
    evidence = samples._sample_evidence(identifier)
    assert len(evidence["research_sessions"]) == 1
    session = evidence["research_sessions"][0]
    assert session["status"] == "ended"
    assert len(session["artifacts"]) == 4
    assert all(
        artifact["reasoning_steps"] == [] and len(artifact["design_notes"]) == 4
        for artifact in session["artifacts"]
    )
    assert "four" in raw["problem"].lower()
    assert "independently validated" not in raw["problem"].lower()

    expected = {"hierarchical", "architecture", "network", "timeline"}
    specs = [artifact["diagram_spec"] for artifact in session["artifacts"]]
    diagrams = [papers.PaperDiagram.model_validate(item) for item in specs]
    assert {diagram.layout for diagram in diagrams} == expected
    assert all(diagram.nodes and diagram.edges for diagram in diagrams)
    assert all(diagram.caption and diagram.claim_ids for diagram in diagrams)
    for diagram in diagrams:
        selected, warning = papers._diagram_selected_layout(diagram)
        assert (selected, warning) == (diagram.layout, None)
    assert next(item for item in diagrams if item.layout == "architecture").boundaries
    assert (
        papers._diagram_is_acyclic(next(item for item in diagrams if item.layout == "network"))
        is False
    )

    # Both one-shot and long-form authoring accept multiple useful figures.
    one_shot = draft("project:pid")
    papers.PaperDraft.model_validate(
        {**one_shot.model_dump(), "diagrams": [item.model_dump() for item in diagrams]}
    )
    _, plan = fast_package()
    papers.LongPaperPlan.model_validate(
        {**plan.model_dump(), "diagrams": [item.model_dump() for item in diagrams]}
    )
    assert "proactively include" in papers.VISUAL_AUTHORING_INSTRUCTIONS
    assert "actual findings" in papers.VISUAL_AUTHORING_INSTRUCTIONS

    paper = draft("project:pid").model_copy(update={"diagrams": diagrams})
    render_warnings: list[str] = []
    tex = papers._tex(paper, render_warnings, "f" * 64)
    assert tex.count(r"\begin{tikzpicture}") == 4
    assert "step/.style" not in tex
    assert "timeline marker/.style" in tex
    assert "Diagram (readable relationship list)." not in tex
    assert not render_warnings

    # Open through the normal Samples copy path, including session re-binding.
    with (
        TemporaryDirectory() as temp,
        patch.object(samples, "projects_root", return_value=Path(temp)),
        patch.object(recents, "record_access"),
    ):
        view = samples.open_sample_project(identifier)
        copies = research_sessions.list_sessions(view.path)
        assert len(copies) == 1
        assert copies[0]["project_id"] == view.project.id
        assert copies[0]["status"] == "ended"
        assert len(copies[0]["artifacts"]) == 4
        assert copies[0]["outcome"]["assessment"] != "positive"
        assert all(item["project_id"] == view.project.id for item in copies[0]["artifacts"])
        package, _ = papers._snapshot(view.path)
        assert sum(item["kind"] == "artifact" for item in package["sources"]) == 4
        assert papers._paper_long_form(package) is False


def test_sov_ai_structured_graph_uses_vector_layout_not_relationship_list() -> None:
    """The eight-node campus policy DAG is visual, not a prose-only fallback."""
    nodes = [
        ("operation", "Immutable operation envelope"),
        ("authority", "Home-campus identity, policy and classification authority"),
        ("gate", "Fail-closed eligibility and revocation gate"),
        ("liability", "Durable liability admission"),
        ("ranking", "Rank approved destinations"),
        ("local", "Approved local inference"),
        ("partner", "Hypothetical approved partner-campus service"),
        ("frontier", "Hypothetical approved frontier path"),
    ]
    edges = [
        ("operation", "gate", "Bound identity, data dependencies and destination"),
        ("authority", "gate", "Authoritative permission"),
        ("gate", "liability", "Only eligible operations proceed"),
        ("liability", "ranking", "Only covered liability proceeds"),
        ("ranking", "local", "Local policy eligibility"),
        ("ranking", "partner", "Cross-campus approval"),
        ("ranking", "frontier", "Separate provider approval"),
    ]
    diagram = papers.PaperDiagram(
        caption="Policy-first control path with two hypothetical processing domains.",
        nodes=[papers.DiagramNode(id=node_id, label=label) for node_id, label in nodes],
        edges=[
            papers.DiagramEdge(source=source, target=target, label=label)
            for source, target, label in edges
        ],
        boundaries=[
            papers.DiagramBoundary(
                label="Origin campus", node_ids=[node_id for node_id, _ in nodes[:6]]
            ),
            papers.DiagramBoundary(label="Partner campus", node_ids=["partner"]),
            papers.DiagramBoundary(label="Provider domain", node_ids=["frontier"]),
        ],
        claim_ids=["C1"],
    )
    assert papers._diagram_layout(diagram) is None
    paper = draft("project:pid").model_copy(update={"diagrams": [diagram]})
    warnings: list[str] = []
    tex = papers._tex(paper, warnings, "f" * 64)
    assert r"\begin{tikzpicture}" in tex
    assert "Diagram (readable relationship list)." not in tex
    assert tex.count(r"\draw[->,thin,blue!65]") == 7
    assert tex.count(r"\node[main node]") == 8
    assert tex.count(r"\node[boundary,fit=") == 3
    assert all(label in tex for _, label in nodes)
    assert all(label in tex for _, _, label in edges)
    assert not any("could not be laid out" in warning for warning in warnings)


def test_authorized_section_recovery_reuses_saved_siblings_and_preserves_dispatches() -> None:
    """One explicit paid recovery may write only the missing section."""
    package, plan = fast_package(section_count=4)
    state = papers._new_work("a" * 64, "fast-fixture", "b" * 64, "fixture-model", "medium")
    attempts: list[int] = []

    async def initial(input_value, _binding, _config, *, schema_name, **_kwargs):
        if schema_name == "sigma_long_paper_plan":
            return plan, "fixture-model"
        number = input_value["section_number"]
        attempts.append(number)
        if number == 1:
            # Let the other three dispatched requests finish their valid drafts
            # before the first section reports its provider failure.
            await asyncio.sleep(0.03)
            raise papers.PaperTransientFailure("HTTP 503 before section authorship")
        await asyncio.sleep(0.01)
        return papers.LongSectionDraft(
            paragraphs=[f"Authored and durably saved section {number}."]
        ), "fixture-model"

    async def first_run():
        with patch.object(papers, "_provider_structured", new=initial):
            try:
                await papers._generate_long_draft(
                    package,
                    {"identity": "fixture", "mode": "api_key", "token": "fixture"},
                    {"model": "fixture-model", "reasoning_effort": "medium"},
                    state,
                    lambda _value: None,
                    structured_fast_path=True,
                )
            except ProjectError as exc:
                assert "Paper section 1" in str(exc)
            else:
                raise AssertionError("Missing section should block publication")

    asyncio.run(first_run())
    assert set(state["section_drafts"]) == {"2", "3", "4"}
    assert papers._recoverable_dispatched_sections(state) == [1]
    original_drafts = copy.deepcopy(state["section_drafts"])
    original_dispatches = copy.deepcopy(state["section_dispatches"])
    call_count = state["provider_calls_total"]
    assert attempts.count(1) == 1

    async def recovered(input_value, _binding, _config, *, schema_name, **_kwargs):
        assert schema_name == "sigma_long_paper_section"
        number = input_value["section_number"]
        attempts.append(number)
        assert number == 1, "Saved siblings must never be requested again"
        return papers.LongSectionDraft(
            paragraphs=["Recovered first section, supported by the frozen research."]
        ), "fixture-model"

    async def attempt(authorization):
        with patch.object(papers, "_provider_structured", new=recovered):
            return await papers._generate_long_draft(
                package,
                {"identity": "fixture", "mode": "api_key", "token": "fixture"},
                {"model": "fixture-model", "reasoning_effort": "medium"},
                state,
                lambda _value: None,
                structured_fast_path=True,
                authorized_recovery_section=authorization,
            )

    for authorization in (None, 2):
        try:
            asyncio.run(attempt(authorization))
        except ProjectError as exc:
            assert "no authored text" in str(exc)
        else:
            raise AssertionError("Unsanctioned or wrong-section replay must be rejected")
        assert state["provider_calls_total"] == call_count
        assert state["section_drafts"] == original_drafts
        assert state["section_dispatches"] == original_dispatches

    paper, total_calls, batches = asyncio.run(attempt(1))
    assert len(paper.sections) == 4
    assert batches == 0
    assert total_calls == call_count + 1
    assert state["provider_calls_total"] == call_count + 1
    assert set(state["section_drafts"]) == {"1", "2", "3", "4"}
    assert all(state["section_drafts"][key] == value for key, value in original_drafts.items())
    assert state["section_dispatches"]["1"] == [*original_dispatches["1"], call_count + 1]
    assert all(
        state["section_dispatches"][key] == original_dispatches[key] for key in ("2", "3", "4")
    )
    assert attempts.count(1) == 2
    assert attempts.count(2) == attempts.count(3) == attempts.count(4) == 1
    assert papers._recoverable_dispatched_sections(state) == []
    try:
        asyncio.run(attempt(1))
    except ProjectError as exc:
        assert "authorization is stale" in str(exc)
    else:
        raise AssertionError("Already-completed recovery cannot be replayed")


def test_interrupted_section_dispatch_records_block_ambiguous_resume() -> None:
    package, plan = fast_package(section_count=5)
    state = papers._new_work("e" * 64, "fast-fixture", "f" * 64, "fixture-model", "high")

    async def provider(input_value, _binding, _config, *, schema_name, **_kwargs):
        if schema_name == "sigma_long_paper_plan":
            return plan, "fixture-model"
        return papers.LongSectionDraft(
            paragraphs=[f"Saved {input_value['section_number']}."]
        ), "fixture-model"

    async def first_run() -> None:
        with patch.object(papers, "_provider_structured", new=provider):
            await papers._generate_long_draft(
                package,
                {"identity": "fixture", "mode": "api_key", "token": "fixture"},
                {"model": "fixture-model", "reasoning_effort": "high"},
                state,
                lambda _value: None,
                structured_fast_path=True,
            )

    asyncio.run(first_run())
    original = copy.deepcopy(state)
    for prior_status in ("cancelled", "failed", "paused", "running"):
        resumed = copy.deepcopy(original)
        saved = copy.deepcopy(resumed["section_drafts"])
        resumed["section_drafts"].pop("3")
        resumed["section_drafts"].pop("5")
        # Section 3 was dispatched; section 5 was not. Neither may be silently
        # published or retried before the user reviews the uncertain paid call.
        resumed["section_dispatches"].pop("5")
        resumed["progress"] = {"stage": "retry", "status": prior_status}
        calls_before = resumed["provider_calls"]

        async def no_paid_call(*_args, **_kwargs):
            raise AssertionError("Ambiguous Resume must not dispatch another provider call")

        async def resume(checkpoint=resumed) -> None:
            with patch.object(papers, "_provider_structured", new=no_paid_call):
                try:
                    await papers._generate_long_draft(
                        package,
                        {"identity": "fixture", "mode": "api_key", "token": "fixture"},
                        {"model": "fixture-model", "reasoning_effort": "high"},
                        checkpoint,
                        lambda _value: None,
                        structured_fast_path=True,
                    )
                except ProjectError as exc:
                    assert "3 (" in str(exc)
                    assert "no authored text" in str(exc)
                else:
                    raise AssertionError("Resume must reject the unsaved paid section")

        asyncio.run(resume())
        assert resumed["provider_calls"] == calls_before
        assert resumed["section_drafts"] == {
            key: value for key, value in saved.items() if key not in {"3", "5"}
        }


def test_legacy_retry_checkpoint_requires_recovery_for_logged_section() -> None:
    package, plan = fast_package(section_count=5)
    state = papers._new_work("e" * 64, "fast-fixture", "f" * 64, "fixture-model", "high")
    state["plan"] = plan.model_dump()
    state["evidence_indexed"] = True
    state["evidence_strategy"] = "structured_v1"
    state["section_drafts"] = {
        str(number): papers.LongSectionDraft(paragraphs=[f"Saved {number}."]).model_dump()
        for number in (1, 2, 4, 5)
    }
    state.pop("section_dispatches")
    state["progress"] = {
        "stage": "retry",
        "status": "failed",
        "detail": "Retrying section 3 (attempt 2 of 3).",
    }
    assert papers._legacy_ambiguous_sections(state) == {"3"}
    state["legacy_ambiguous_sections"] = ["3"]
    state["progress"] = {"stage": "publication_compilation", "status": "running"}

    async def never_call(*_args, **_kwargs):
        raise AssertionError("Legacy uncertain section must not be replayed")

    async def resume() -> None:
        with patch.object(papers, "_provider_structured", new=never_call):
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
                assert "3 (" in str(exc) and "no authored text" in str(exc)
            else:
                raise AssertionError("Legacy uncertain section must block publication")

    asyncio.run(resume())
    assert set(state["section_drafts"]) == {"1", "2", "4", "5"}


def test_legacy_unknown_section_dispatch_stops_before_paid_replay() -> None:
    package, plan = fast_package(section_count=5)
    state = papers._new_work("e" * 64, "fast-fixture", "f" * 64, "fixture-model", "high")
    state["plan"] = plan.model_dump()
    state["evidence_indexed"] = True
    state["evidence_strategy"] = "structured_v1"
    state["section_drafts"] = {"1": papers.LongSectionDraft(paragraphs=["Saved 1."]).model_dump()}
    state.pop("section_dispatches")
    state["progress"] = {"stage": "sections", "status": "paused"}

    async def never_call(*_args, **_kwargs):
        raise AssertionError("Unknown legacy dispatch must not be replayed")

    async def resume() -> None:
        with patch.object(papers, "_provider_structured", new=never_call):
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
                assert "lacks section dispatch records" in str(exc)
            else:
                raise AssertionError("Unknown legacy dispatch should stop before a provider call")

    asyncio.run(resume())
    assert set(state["section_drafts"]) == {"1"}
    assert state["provider_calls"] == 0


def test_oversized_section_stream_blocks_publication_without_retry() -> None:
    package, plan = fast_package(section_count=5)
    state = papers._new_work("e" * 64, "fast-fixture", "f" * 64, "fixture-model", "high")
    attempts: dict[int, int] = {}

    async def provider(input_value, _binding, _config, *, schema_name, **_kwargs):
        if schema_name == "sigma_long_paper_plan":
            return plan, "fixture-model"
        number = input_value["section_number"]
        attempts[number] = attempts.get(number, 0) + 1
        if number == 3:
            raise ProjectError("Provider generated text exceeds the bounded response capacity.")
        return papers.LongSectionDraft(paragraphs=[f"Saved {number}."]), "fixture-model"

    async def run() -> None:
        with patch.object(papers, "_provider_structured", new=provider):
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
                assert "Paper section 3" in str(exc)
                assert "did not finish" in str(exc)
            else:
                raise AssertionError("Oversized failed section must not be published")

    asyncio.run(run())
    assert attempts[3] == 1
    assert "3" not in state["section_drafts"]
    assert not any(
        "Editorial notice" in paragraph
        for value in state["section_drafts"].values()
        for paragraph in value["paragraphs"]
    )


def test_paper_section_invalid_optional_table_is_dropped_without_losing_text() -> None:
    package, plan = fast_package()
    state = papers._new_work("a" * 64, "fast-fixture", "b" * 64, "fixture-model", "high")

    async def provider(input_value, _binding, _config, *, schema_name, **_kwargs):
        if schema_name == "sigma_long_paper_plan":
            return plan, "fixture-model"
        number = input_value["section_number"]
        invalid_table = papers.PaperTable(
            caption="Table with a link outside the section evidence index",
            headers=["Name", "Value"],
            rows=[["Source", "Observed"]],
            evidence_refs=["unknown-source-reference"],
            claim_ids=[plan.sections[number - 1].claim_ids[0]],
        )
        return papers.LongSectionDraft(
            paragraphs=[f"Kept verified section {number} prose."], tables=[invalid_table]
        ), "fixture-model"

    async def generate() -> papers.PaperDraft:
        with patch.object(papers, "_provider_structured", new=provider):
            result, _, _ = await papers._generate_long_draft(
                package,
                {"identity": "fixture", "mode": "api_key", "token": "fixture"},
                {"model": "fixture-model", "reasoning_effort": "high"},
                state,
                lambda _value: None,
                structured_fast_path=True,
                include_diagrams=True,
            )
        return result

    result = asyncio.run(generate())
    assert all(not section.tables for section in result.sections)
    assert all("Kept verified section" in section.paragraphs[0] for section in result.sections)
    assert any("invalid source or claim links" in issue for issue in state["generation_issues"])


def test_paper_section_permanent_provider_rejection_does_not_publish_placeholder() -> None:
    package, plan = fast_package()
    state = papers._new_work("a" * 64, "fast-fixture", "b" * 64, "fixture-model", "high")

    async def provider(input_value, _binding, _config, *, schema_name, **_kwargs):
        if schema_name == "sigma_long_paper_plan":
            return plan, "fixture-model"
        raise ProjectError("Provider declined a long-paper stage")

    async def generate() -> None:
        with patch.object(papers, "_provider_structured", new=provider):
            await papers._generate_long_draft(
                package,
                {"identity": "fixture", "mode": "api_key", "token": "fixture"},
                {"model": "fixture-model", "reasoning_effort": "high"},
                state,
                lambda _value: None,
                structured_fast_path=True,
            )

    try:
        asyncio.run(generate())
    except ProjectError as exc:
        assert "Provider declined" in str(exc)
    else:
        raise AssertionError("A provider refusal must not be turned into authored content")
    assert not state.get("section_drafts")


def test_paper_transient_error_classification_excludes_permanent_rejections() -> None:
    from sigma.plan_stream import ChatGPTProviderRejection

    assert papers._retryable_paper_response_failure(
        ProjectError("Paper stream ended before a valid response.completed. (SSE events: 3)")
    )
    assert papers._retryable_paper_response_failure(
        ProjectError("OpenAI API request failed (HTTP 503): temporary provider outage")
    )
    assert not papers._retryable_paper_response_failure(
        ProjectError("OpenAI API request failed (HTTP 400): invalid schema")
    )
    assert not papers._retryable_paper_response_failure(
        ChatGPTProviderRejection(
            "Plan allowance exhausted",
            state="limited",
            code="subscription_sharing_usage_limit_exceeded",
            http_status=429,
            streamed=True,
        )
    )
    assert papers._retryable_paper_response_failure(
        ChatGPTProviderRejection(
            "Provider rate limit",
            state="limited",
            code=None,
            http_status=429,
            streamed=False,
        )
    )


def test_paper_failure_reason_survives_reopen() -> None:
    """A disconnected browser can still see why the previous stage failed."""
    with TemporaryDirectory() as directory:
        path = Path(directory) / "paper-failure.sigma"
        view = initialize_project(
            path, "Saved failure", "Why did the planning stage fail?", research_mode="mathematical"
        )
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


def test_active_paper_progress_poll_avoids_checkpoint_deserialization() -> None:
    """High-frequency browser heartbeats must not reload large active drafts."""
    with TemporaryDirectory() as directory:
        path = Path(directory) / "active-progress.sigma"
        initialize_project(
            path, "Active paper", "A mathematical question", research_mode="mathematical"
        )
        key = str(papers.project_path(str(path)).resolve())
        progress = {
            "run_id": "d" * 32,
            "status": "running",
            "stage": "sections",
            "current": 1,
            "total": 5,
            "started_at": papers._now(),
            "updated_at": papers._now(),
            "elapsed_seconds": 3,
            "last_progress_at": papers._now(),
            "output_delta_count": 123,
        }
        papers._write_progress_status(str(path), progress)
        with (
            patch.dict(papers._active_progress, {key: progress}),
            patch.object(
                papers,
                "_load_work",
                side_effect=AssertionError("Do not read checkpoints during active polling"),
            ),
        ):
            status = papers.progress_status(str(path))
        assert status is not None
        assert status["status"] == "active"
        assert status["stage"] == "sections"
        assert (status["current"], status["total"]) == (1, 5)
        assert status["last_progress_at"] == progress["last_progress_at"]
        assert status["output_delta_count"] == 123
        # A backend restart cannot convert persisted output evidence into live
        # generation. The snapshot remains visible but its state is interrupted.
        recovered = papers.progress_status(str(path))
        assert recovered is not None
        assert recovered["status"] == "interrupted"
        assert recovered["last_progress_at"] == progress["last_progress_at"]
        assert recovered["output_delta_count"] == 123


def test_paper_browser_presence_gates_new_paid_attempts() -> None:
    """No viewer means no new paid attempt, including transient retries."""
    from sigma import research_preferences, research_presence

    with (
        patch.object(
            research_preferences, "allow_unattended_background_execution", return_value=False
        ),
        patch.object(research_presence, "has_live_viewer", return_value=False) as viewer_check,
    ):
        # Programmatic callers must not inherit browser-only lease requirements.
        papers._require_browser_presence("unrelated-project.sigma", False)
        assert viewer_check.call_count == 0
        try:
            papers._require_browser_presence("unrelated-project.sigma", True)
        except papers.PaperBrowserPaused:
            pass
        else:
            raise AssertionError("Disconnected browser generation should pause")

    with (
        patch.object(
            research_preferences, "allow_unattended_background_execution", return_value=True
        ),
        patch.object(
            research_presence,
            "has_live_viewer",
            side_effect=AssertionError("Unattended-enabled runs need no active viewer"),
        ),
    ):
        papers._require_browser_presence("unrelated-project.sigma", True)


def test_paper_paused_progress_preserves_disconnect_reason() -> None:
    """Browser disconnection pauses cleanly, not as a falsely reported restart."""
    with TemporaryDirectory() as directory:
        path = Path(directory) / "browser-paused.sigma"
        view = initialize_project(
            path, "Paused paper", "Persist a viewer-lease pause", research_mode="mathematical"
        )
        work = papers._new_work("a" * 64, view.project.id, "b" * 64, "fixture-model", "high")
        work["progress"] = {
            "run_id": "c" * 32,
            "status": "running",
            "stage": "planning",
            "current": 1,
            "total": 3,
            "started_at": "2026-10-29T01:00:00+00:00",
            "updated_at": "2026-10-29T01:01:00+00:00",
            "elapsed_seconds": 60,
        }
        papers._save_work(str(path), work)
        reason = "Paper generation paused because the browser disconnected."
        papers.finish_progress(str(path), "paused", reason)
        saved = papers.progress_status(str(path))
        assert saved is not None
        assert saved["status"] == "interrupted"
        assert saved["stage"] == "planning"
        assert saved["detail"] == reason
        assert "restarted" not in saved["detail"]
        saved_work = papers._load_work(str(path))
        assert saved_work is not None
        assert saved_work["progress"]["status"] == "paused"

        # Explicit Stop preserves durable provider accounting as well.
        saved_work["progress"]["status"] = "running"
        saved_work["progress"]["stage"] = "retry"
        saved_work["progress"]["detail"] = "Retrying section 3 (attempt 2 of 3)."
        papers._save_work(str(path), saved_work)
        papers.finish_progress(str(path), "cancelled")
        cancelled = papers._load_work(str(path))
        assert cancelled is not None and cancelled["progress"]["status"] == "cancelled"
        cancelled_progress = papers.progress_status(str(path))
        assert cancelled_progress is not None
        assert cancelled_progress["status"] == "cancelled"
        assert "Retrying" not in cancelled_progress["detail"]


def test_stopped_paper_checkpoint_remains_valid_on_resume() -> None:
    """A stopped new paper is resumable; progress presentation cannot invalidate it."""
    with TemporaryDirectory() as directory:
        path = Path(directory) / "stopped-progress.sigma"
        view = initialize_project(
            path, "Paper stop", "Resume a paper after Stop", research_mode="mathematical"
        )
        work = papers._new_work("a" * 64, view.project.id, "b" * 64, "fixture-model", "high")
        work["provider_calls"] = 1
        work["provider_calls_total"] = 1
        work["progress"] = {
            "run_id": "c" * 32,
            "status": "running",
            "stage": "writing",
            "current": None,
            "total": None,
            "started_at": "2026-11-05T01:00:00+00:00",
            "updated_at": "2026-11-05T01:01:00+00:00",
            "elapsed_seconds": 60,
        }
        papers._save_work(str(path), work)
        papers.finish_progress(str(path), "paused", "Paper stopped; saved work remains.")
        loaded = papers._load_work(str(path))
        assert loaded is not None
        assert loaded["progress"]["status"] == "paused"
        assert loaded["provider_calls"] == loaded["provider_calls_total"] == 1
        paused_progress = papers.progress_status(str(path))
        assert paused_progress is not None
        assert paused_progress["status"] == "interrupted"
        # The same validation must accept a queued checkpoint that was stopped
        # before an AI stage started, without changing its provider accounting.
        loaded["progress"]["stage"] = "queued"
        loaded["progress"]["status"] = "cancelled"
        papers._save_work(str(path), loaded)
        queued_work = papers._load_work(str(path))
        assert queued_work is not None
        assert queued_work["progress"]["status"] == "cancelled"


def test_paper_progress_counts_keep_generation_resumable() -> None:
    """Zero sections is legitimate; bad display counts must not discard paid work."""
    with TemporaryDirectory() as directory:
        path = Path(directory) / "progress-recovery.sigma"
        view = initialize_project(
            path, "Paper progress", "A saved paper question", research_mode="mathematical"
        )
        package, fingerprint = papers._snapshot(str(path))
        work = papers._new_work(fingerprint, view.project.id, "b" * 64, "fixture-model", "high")
        work["frozen_package"] = package
        work["provider_calls"] = 2
        work["provider_calls_total"] = 2
        work["progress"] = {
            "run_id": "a" * 32,
            "status": "running",
            "stage": "sections",
            "current": 0,
            "total": 6,
            "sections_total": 6,
            "started_at": "2026-11-04T01:00:00+00:00",
            "updated_at": "2026-11-04T01:00:00+00:00",
            "elapsed_seconds": 10,
        }
        papers._save_work(str(path), work)
        loaded = papers._load_work(str(path))
        assert loaded is not None
        assert (loaded["progress"]["current"], loaded["progress"]["total"]) == (0, 6)
        assert loaded["provider_calls"] == loaded["provider_calls_total"] == 2
        assert loaded.get("generation_issues") is None
        status = papers.progress_status(str(path))
        assert status is not None and status["current"] == 0 and status["total"] == 6
        assert status["sections_total"] == 6

        # Only progress-display metadata is recoverable; real accounting is unchanged.
        for current, total in [(-1, 6), (7, 6), (0, 0), (None, 6), (True, 6)]:
            work["progress"]["current"] = current
            work["progress"]["total"] = total
            papers._save_work(str(path), work)
            recovered = papers._load_work(str(path))
            assert recovered is not None
            assert recovered["progress"]["current"] is None
            assert recovered["progress"]["total"] is None
            assert recovered["provider_calls"] == recovered["provider_calls_total"] == 2
            assert recovered["generation_issues"] == [papers._PAPER_PROGRESS_RECOVERY_ISSUE]
            papers._save_work(str(path), recovered)
            reopened = papers._load_work(str(path))
            assert (
                reopened is not None
                and reopened["generation_issues"] == recovered["generation_issues"]
            )
            status_after = papers.progress_status(str(path))
            assert status_after is not None and status_after["current"] is None

        tex = r"""\documentclass{article}
\begin{document}
Body
\end{document}"""
        appendix = papers._append_sigma_issues(tex, recovered["generation_issues"])
        assert r"\section{Issues and Bugs}" in appendix
        assert "recovered inconsistent paper-generation progress counters" in appendix
        assert r"\section{Issues and Bugs}" not in tex


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
    assert ("sections", 0, 6, "active") in progress_events
    section_milestones = [
        item[1:3] for item in progress_events if item[0] == "sections" and item[3] == "milestone"
    ]
    assert section_milestones == [(number, 6) for number in range(1, 7)]
    # Sections finish in reverse order here; progress is completed-count,
    # not the latest section number, and does not erase saved work.
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


def test_seven_section_writer_advances_after_two_with_slow_siblings() -> None:
    """A displayed 2/7 must not deadlock queued work behind four live sections."""
    package, plan = fast_package(section_count=7)
    state = papers._new_work("9" * 64, "fast-fixture", "a" * 64, "fixture-model", "medium")
    two_saved = asyncio.Event()
    release_slow = asyncio.Event()
    started: list[int] = []
    inflight = 0
    peak = 0
    milestones: list[int] = []

    async def provider(input_value, _binding, _config, *, schema_name, **_kwargs):
        nonlocal inflight, peak
        if schema_name == "sigma_long_paper_plan":
            return plan, "fixture-model"
        number = input_value["section_number"]
        started.append(number)
        inflight += 1
        peak = max(peak, inflight)
        try:
            if number > 2:
                await release_slow.wait()
            return papers.LongSectionDraft(
                paragraphs=[f"Authored and saved section {number}."]
            ), "fixture-model"
        finally:
            inflight -= 1

    async def progress(
        stage: papers.PaperProgressStage,
        current: int | None,
        total: int | None,
        state: papers.PaperProgressState = "active",
        *,
        detail: str | None = None,
    ) -> None:
        del detail
        if stage == "sections" and state == "milestone":
            assert total == 7
            assert current is not None
            milestones.append(current)
            if current == 2:
                two_saved.set()

    async def exercise() -> None:
        async def generate() -> tuple[papers.PaperDraft, int, int]:
            with patch.object(papers, "_provider_structured", new=provider):
                return await papers._generate_long_draft(
                    package,
                    {"identity": "fixture", "mode": "api_key", "token": "fixture"},
                    {"model": "fixture-model", "reasoning_effort": "medium"},
                    state,
                    lambda _value: None,
                    progress,
                    structured_fast_path=True,
                )

        task = asyncio.create_task(generate())
        try:
            await asyncio.wait_for(two_saved.wait(), timeout=2)
            assert set(state["section_drafts"]) == {"1", "2"}
            assert not task.done()
            await asyncio.sleep(0)
            assert peak <= papers.FAST_SECTION_CONCURRENCY
            assert len(started) >= 4
            release_slow.set()
            result, calls, _ = await asyncio.wait_for(task, timeout=2)
            assert len(result.sections) == 7
            assert calls == 8  # one plan and seven actual section calls
        finally:
            release_slow.set()
            if not task.done():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    asyncio.run(exercise())
    assert set(state["section_drafts"]) == {str(number) for number in range(1, 8)}
    assert milestones == list(range(1, 8))
    assert peak == papers.FAST_SECTION_CONCURRENCY
    assert sorted(started) == list(range(1, 8))


def test_parallel_section_failure_drains_dispatched_siblings() -> None:
    """One broken stream must not cancel other paid work or fabricate its section."""
    package, plan = fast_package(section_count=5)
    state = papers._new_work("a" * 64, "fast-fixture", "b" * 64, "fixture-model", "high")
    dispatched: list[int] = []
    saves: list[set[str]] = []

    async def provider(input_value, _binding, _config, *, schema_name, **_kwargs):
        if schema_name == "sigma_long_paper_plan":
            return plan, "fixture-model"
        assert schema_name == "sigma_long_paper_section"
        number = input_value["section_number"]
        dispatched.append(number)
        if number == 1:
            await asyncio.sleep(0.01)
            raise ProjectError("fixture incomplete SSE terminal")
        if number == 5:
            raise AssertionError("Queued section dispatched after a known failure")
        await asyncio.sleep(0.05)
        return papers.LongSectionDraft(
            paragraphs=[f"Saved independent section {number}."]
        ), "fixture-model"

    async def first_attempt() -> None:
        with patch.object(papers, "_provider_structured", new=provider):
            try:
                await papers._generate_long_draft(
                    package,
                    {"identity": "fixture", "mode": "api_key", "token": "fixture"},
                    {"model": "fixture-model", "reasoning_effort": "high"},
                    state,
                    lambda value: saves.append(set(value.get("section_drafts", {}))),
                    structured_fast_path=True,
                )
            except ProjectError as exc:
                assert "incomplete SSE terminal" in str(exc)
            else:
                raise AssertionError("The broken stream must stop publication")

    asyncio.run(first_attempt())
    assert set(dispatched) == {1, 2, 3, 4}
    assert set(state["section_drafts"]) == {"2", "3", "4"}
    assert {"2", "3", "4"} in saves
    assert state["provider_calls"] == 5

    async def no_repeat(*_args, **_kwargs):
        raise AssertionError("Resume must not replay ambiguous calls or dispatch new ones")

    async def resume() -> None:
        with patch.object(papers, "_provider_structured", new=no_repeat):
            try:
                await papers._generate_long_draft(
                    package,
                    {"identity": "fixture", "mode": "api_key", "token": "fixture"},
                    {"model": "fixture-model", "reasoning_effort": "high"},
                    state,
                    lambda value: saves.append(set(value.get("section_drafts", {}))),
                    structured_fast_path=True,
                )
            except ProjectError as exc:
                assert "1 (" in str(exc) and "no authored text" in str(exc)
            else:
                raise AssertionError("Unwritten section must not be published")

    asyncio.run(resume())
    assert set(state["section_drafts"]) == {"2", "3", "4"}
    assert dispatched.count(2) == dispatched.count(3) == dispatched.count(4) == 1


def test_fast_checkpoint_resume_preserves_ambiguous_section_without_replay() -> None:
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
                raise AssertionError("First failure must preserve a partial checkpoint")

    asyncio.run(fail_one_section())
    assert set(state["section_drafts"]) == {"1"}
    assert attempts.count(("sigma_long_paper_plan", None)) == 1
    assert attempts.count(("sigma_long_paper_section", 1)) == 1
    assert attempts.count(("sigma_long_paper_section", 2)) == 1

    async def no_repeat(*_args, **_kwargs):
        raise AssertionError("An ambiguous paid section call must not be replayed")

    async def resume() -> None:
        with patch.object(papers, "_provider_structured", new=no_repeat):
            try:
                await papers._generate_long_draft(
                    package,
                    {"identity": "fixture", "mode": "api_key", "token": "fixture"},
                    {"model": "fixture-model", "reasoning_effort": "high"},
                    state,
                    lambda _value: None,
                    structured_fast_path=True,
                    include_diagrams=False,
                )
            except ProjectError as exc:
                assert "2 (" in str(exc)
                assert "no authored text" in str(exc)
            else:
                raise AssertionError("Resume must stop before false completion")

    lifecycle_logger = papers.logging.getLogger("sigma.lifecycle")
    with (
        patch.object(lifecycle_logger, "info") as info_log,
        patch.object(lifecycle_logger, "warning") as warning_log,
    ):
        asyncio.run(resume())
    assert any(
        call.args and call.args[0].startswith("paper.section_checkpoint ")
        for call in info_log.call_args_list
    )
    assert not any(
        call.args and call.args[0].startswith("paper.section_checkpoint_fallback ")
        for call in warning_log.call_args_list
    )
    assert attempts.count(("sigma_long_paper_plan", None)) == 1
    assert attempts.count(("sigma_long_paper_section", 1)) == 1
    assert attempts.count(("sigma_long_paper_section", 2)) == 1
    assert set(state["section_drafts"]) == {"1"}
    assert state["plan"]["diagrams"]
    assert state["section_drafts"]["1"]["tables"]

    # Older checkpoints containing editorial filler must not count it as
    # authorship even if the previous version marked it completed.
    state["section_drafts"]["2"] = papers.LongSectionDraft(
        paragraphs=["Editorial notice: The writing for this section was interrupted or invalid."]
    ).model_dump()
    asyncio.run(resume())
    assert set(state["section_drafts"]) == {"1", "2"}


def test_paper_generation_rejects_concurrent_duplicate_request() -> None:
    with TemporaryDirectory() as temporary:
        path = Path(temporary) / "single-flight.sigma"
        view = initialize_project(
            path, "Single flight", "Preserve one generation at a time", research_mode="mathematical"
        )
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


def test_three_paper_generators_run_concurrently_and_fourth_fails_fast() -> None:
    """Paper generators queue FIFO instead of starting expensive work together."""
    with TemporaryDirectory() as temporary:
        paths = [Path(temporary) / f"paper-{index}.sigma" for index in range(4)]
        views = [
            initialize_project(
                path,
                f"Paper project {index}",
                "Independent bounded research",
                research_mode="mathematical",
            )
            for index, path in enumerate(paths)
        ]
        credential = {"identity": "fixture:account", "mode": "api_key", "token": "fixture"}
        config = {
            "available": True,
            "binding": credential["identity"],
            "model": "fixture-model",
            "reasoning_effort": "high",
        }
        first_started = asyncio.Event()
        release = asyncio.Event()
        provider_calls = 0

        async def blocked_provider(context, *_args):
            nonlocal provider_calls
            provider_calls += 1
            first_started.set()
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
                tasks = [
                    asyncio.create_task(
                        papers.generate(str(path), credential["identity"], view.project.id)
                    )
                    for path, view in zip(paths, views)
                ]
                try:
                    await asyncio.wait_for(first_started.wait(), timeout=3)
                    await asyncio.sleep(0.05)
                    assert provider_calls == 1
                    assert len(papers._generating_paper_projects) == 1
                    assert len(papers._paper_waiters) == 3
                    assert [papers.activity_status(str(path)) for path in paths] == [
                        "active",
                        "queued",
                        "queued",
                        "queued",
                    ]
                finally:
                    release.set()
                results = await asyncio.wait_for(asyncio.gather(*tasks), timeout=20)
                assert len(results) == 4
                assert provider_calls == 4
                assert all(len(papers.list_papers(str(path))) == 1 for path in paths)
                assert not papers._busy_paper_projects
                assert not papers._paper_waiters
                assert not papers._generating_paper_projects

        asyncio.run(check())


def test_three_papers_reach_compilation_together_and_hold_capacity() -> None:
    """The queue remains serial through PDF compilation, not just AI calls."""
    with TemporaryDirectory() as temporary:
        paths = [Path(temporary) / f"compile-{index}.sigma" for index in range(4)]
        views = [
            initialize_project(
                path,
                f"Compile project {index}",
                "Compile independently",
                research_mode="mathematical",
            )
            for index, path in enumerate(paths)
        ]
        credential = {"identity": "fixture:account", "mode": "api_key", "token": "fixture"}
        config = {
            "available": True,
            "binding": credential["identity"],
            "model": "fixture-model",
            "reasoning_effort": "high",
        }
        first_compiling = threading.Event()
        finish_compiling = threading.Event()
        compilations = 0
        provider_calls = 0

        def blocked_compiler(*_args, **_kwargs):
            nonlocal compilations
            compilations += 1
            first_compiling.set()
            if not finish_compiling.wait(timeout=10):
                raise AssertionError("A PDF compiler remained blocked after release")
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
                tasks = [
                    asyncio.create_task(
                        papers.generate(str(path), credential["identity"], view.project.id)
                    )
                    for path, view in zip(paths, views)
                ]
                try:
                    assert await asyncio.wait_for(
                        asyncio.to_thread(first_compiling.wait, 8), timeout=9
                    ), "The first paper did not reach PDF compilation"
                    await asyncio.sleep(0.05)
                    assert compilations == 1
                    assert provider_calls == 1
                    assert len(papers._generating_paper_projects) == 1
                    assert len(papers._paper_waiters) == 3
                finally:
                    finish_compiling.set()
                results = await asyncio.wait_for(asyncio.gather(*tasks), timeout=20)
                assert len(results) == 4
                assert provider_calls == 4, f"Expected four provider calls, got {provider_calls}"
                assert compilations == 8, (
                    f"Expected two PDF compilations per paper, got {compilations}"
                )
                assert all(len(papers.list_papers(str(path))) == 1 for path in paths)
                assert not papers._busy_paper_projects
                assert not papers._paper_waiters
                assert not papers._generating_paper_projects

        asyncio.run(check())


def test_eight_research_sessions_overlap_three_paper_generators() -> None:
    """Cross-feature smoke: 8 live mock research calls + 3 paper model calls."""
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
        if paper_count == 1:
            paper_ready.set()
        await release.wait()
        source = next(item["id"] for item in context["sources"] if item["kind"] == "project")
        return draft(source), "fixture-model"

    async def check(root: Path):
        research_projects = []
        for index in range(8):
            path = root / f"research-{index}.sigma"
            view = initialize_project(
                path, f"Research {index}", "Check independent cases", research_mode="mathematical"
            )
            strategy = create_strategy(
                path, "Bounded method", "Investigate an independent research approach"
            ).project.strategies[0]
            research_projects.append((path, view, strategy))
        paper_projects = [
            (
                path,
                initialize_project(
                    path, f"Paper {index}", "Independent paper", research_mode="mathematical"
                ),
            )
            for index in range(3)
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
                assert len(papers._generating_paper_projects) == 1
                assert len(papers._paper_waiters) == 2
                assert all(not research_sessions._tasks[row["id"]].done() for row in starts)
                assert paper_count == 1
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


def test_fallback_planner_ranks_complete_research_notes_over_operational_fields() -> None:
    session = "session:fixture"
    result_a = "artifact:result-a"
    result_b = "artifact:result-b"
    skeptic = "artifact:skeptic"
    complete_proof_ref = "artifact:complete-proof"
    truncated_ref = "artifact:truncated"
    obligation = "artifact:obligation"
    long_proof = (
        "P" * 430 + " and therefore this final step follows only if the earlier premises hold."
    )
    complete_proof = (
        "The derivation starts from the stated assumptions. "
        + "The intermediate step preserves the same invariant. " * 10
        + "The complete final implication follows under those assumptions."
    )
    truncated_text = "This imported field ends abruptly without a complete claim"
    obligation_text = "Determine whether the effect record remains durable after a process restart?"
    complete_chunk_size = papers.FAST_NOTE_TEXT_LENGTH - len("complete_proof") - 3
    complete_chunks = [
        complete_proof[index : index + complete_chunk_size]
        for index in range(0, len(complete_proof), complete_chunk_size)
    ]
    notes = [
        papers.EvidenceNote(
            statement="events/4/project_change/previous/reasoning_effort: high",
            kind="result",
            evidence_refs=[session],
        ),
        papers.EvidenceNote(
            statement="events/10/failure_kind: preflight_error",
            kind="negative",
            evidence_refs=[session],
        ),
        papers.EvidenceNote(
            statement="finding: The saved comparison supports a stable difference between the two measured conditions.",
            kind="result",
            evidence_refs=[result_a],
        ),
        papers.EvidenceNote(
            statement="finding: An independent comparison reports no stable difference between the two measured conditions.",
            kind="result",
            evidence_refs=[result_b],
        ),
        papers.EvidenceNote(
            statement="failure_analysis: The saved retry failure shows that an acknowledged operation can still lack a durable effect record.",
            kind="negative",
            evidence_refs=[skeptic],
        ),
        papers.EvidenceNote(
            statement="proof: and therefore this final step follows only if the earlier premises hold.",
            kind="result",
            evidence_refs=[skeptic],
        ),
        *[
            papers.EvidenceNote(
                statement=f"complete_proof: {chunk}",
                kind="result",
                evidence_refs=[complete_proof_ref],
            )
            for chunk in complete_chunks
        ],
        papers.EvidenceNote(
            statement=f"open_obligation: {obligation_text}",
            kind="question",
            evidence_refs=[obligation],
        ),
        papers.EvidenceNote(
            statement=f"truncated_capture: {truncated_text}",
            kind="result",
            evidence_refs=[truncated_ref],
        ),
    ]
    sources = [
        {
            "id": session,
            "kind": "session",
            "data": {
                "events": [
                    {"project_change": {"previous": {"reasoning_effort": "high"}}},
                    {"failure_kind": "preflight_error"},
                ]
            },
        },
        {
            "id": result_a,
            "kind": "artifact",
            "data": {"finding": notes[2].statement.removeprefix("finding: ")},
        },
        {
            "id": result_b,
            "kind": "artifact",
            "data": {"finding": notes[3].statement.removeprefix("finding: ")},
        },
        {
            "id": skeptic,
            "kind": "artifact",
            "data": {
                "failure_analysis": notes[4].statement.removeprefix("failure_analysis: "),
                "proof": long_proof,
            },
        },
        {"id": complete_proof_ref, "kind": "artifact", "data": {"complete_proof": complete_proof}},
        {"id": truncated_ref, "kind": "artifact", "data": {"truncated_capture": truncated_text}},
        {
            "id": obligation,
            "kind": "artifact",
            "data": {"open_obligation": obligation_text},
        },
    ]
    plan = papers._evidence_based_long_plan(
        {"title": "Fixture project", "problem": "What changes across conditions?"},
        notes,
        {session, result_a, result_b, skeptic, complete_proof_ref, truncated_ref, obligation},
        sources,
    )
    assert all("events/" not in claim.statement for claim in plan.claims)
    assert all("proof:" not in claim.statement for claim in plan.claims)
    result_claim = next(
        claim for claim in plan.claims if "supports a stable difference" in claim.statement
    )
    contrary_claim = next(
        claim for claim in plan.claims if "reports no stable difference" in claim.statement
    )
    assert result_claim.id != contrary_claim.id
    assert result_claim.evidence_refs == [result_a]
    assert contrary_claim.evidence_refs == [result_b]
    assert any("retry failure" in claim.statement for claim in plan.claims)
    assert any("Source-index classification: result." in claim.reasoning for claim in plan.claims)
    full_proof_claim = next(
        claim for claim in plan.claims if "derivation starts" in claim.statement
    )
    assert "complete final implication" in full_proof_claim.statement
    assert complete_proof_ref in full_proof_claim.evidence_refs
    assert all("ends abruptly" not in claim.statement for claim in plan.claims)
    assert all(
        set(claim.evidence_refs)
        <= {session, result_a, result_b, skeptic, complete_proof_ref, truncated_ref, obligation}
        for claim in plan.claims
    )
    assert all(session not in section.evidence_refs for section in plan.sections)
    assert any("process restart" in obligation for obligation in plan.open_obligations)
    conclusion = " ".join(plan.conclusions)
    assert "stable difference" in conclusion and "no stable difference" in conclusion
    assert "process restart" in conclusion
    # Fallback conclusions must not dump long unrelated source fields.
    assert max(map(len, plan.conclusions)) < 1000


def test_fallback_abstract_uses_complete_result_and_keeps_proposals_out_of_findings() -> None:
    result_ref = "artifact:conditional-result"
    proposal_ref = "artifact:proposed-pilot"
    result = (
        "Under the stated partition model, cached approval cannot guarantee immediate "
        "revocation while preserving disconnected admission. This limitation applies only "
        "when the replica has neither authoritative information nor an earlier grant. "
        + "Additional source detail supports the same conditional result. "
        * 5
    )
    proposal = "Use matched campus cohorts and report clustered uncertainty at the end."
    notes = [
        papers.EvidenceNote(
            statement=f"claim_or_question: {result}",
            kind="result",
            evidence_refs=[result_ref],
        ),
        papers.EvidenceNote(
            statement=f"argument: {proposal}",
            kind="result",
            evidence_refs=[proposal_ref],
        ),
    ]
    sources = [
        {
            "id": result_ref,
            "kind": "artifact",
            "data": {"claim_or_question": result},
        },
        {
            "id": proposal_ref,
            "kind": "artifact",
            "data": {"investigator_output": {"reasoning_steps": [{"argument": proposal}]}},
        },
    ]
    plan = papers._evidence_based_long_plan(
        {
            "title": "A partition and policy analysis",
            "problem": "When can remote access remain safe?",
        },
        notes,
        {result_ref, proposal_ref},
        sources,
    )
    assert "cached approval cannot guarantee immediate revocation" in plan.abstract
    assert "does not establish an independently verified resolution" not in plan.abstract
    assert "Use matched campus cohorts" not in plan.abstract
    assert "Use matched campus cohorts" not in " ".join(
        claim.statement for claim in plan.claims if claim.id in plan.sections[0].claim_ids
    )
    proposed_claim = next(claim for claim in plan.claims if claim.statement == proposal)
    methods = next(
        section
        for section in plan.sections
        if section.heading == "Research methods and proposed approaches"
    )
    assert proposed_claim.id in methods.claim_ids
    assert plan.abstract_claim_ids == [
        next(claim.id for claim in plan.claims if claim.statement == result)
    ]


def test_paper_checkpoint_portability_keeps_saved_sections_and_call_history() -> None:
    """Provider changes reuse the exact frozen paper, not a new charged draft."""
    import hashlib

    with TemporaryDirectory() as temporary:
        path = Path(temporary) / "portable-paper.sigma"
        project = initialize_project(
            path,
            "Portable paper",
            "A bounded mathematical question.",
            research_mode="mathematical",
        ).project
        package, snapshot_sha = papers._snapshot(str(path))
        original = papers._new_work(
            snapshot_sha,
            project.id,
            "a" * 64,
            "old-model",
            "high",
            kind="long_form",
        )
        original["frozen_package"] = package
        original["provider_calls"] = 2
        original["provider_calls_total"] = 2
        original["section_drafts"] = {
            "1": papers.LongSectionDraft(paragraphs=["Saved section."]).model_dump()
        }
        original["section_dispatches"] = {"2": [2]}
        papers._save_work(str(path), original)
        binding = "chatgpt:replacement"
        preflight = papers.preflight(
            str(path),
            force_long_form=True,
            expected_project_id=project.id,
            expected_binding=binding,
            mode="chatgpt",
            model="replacement-model",
            reasoning_effort="medium",
        )
        assert preflight["resume_available"] is True
        assert preflight["completed_sections"] == 1
        assert preflight["provider_calls_attempted"] == 2
        new_fingerprint = hashlib.sha256(("chatgpt" + "\0" + binding).encode()).hexdigest()
        checkpoint = papers._load_work(str(path))
        assert checkpoint is not None
        old_drafts = copy.deepcopy(checkpoint["section_drafts"])
        old_dispatches = copy.deepcopy(checkpoint["section_dispatches"])
        assert papers._rebind_paper_checkpoint_provider(
            checkpoint, new_fingerprint, "replacement-model", "medium"
        )
        papers._save_work(str(path), checkpoint)
        saved = papers._load_work(str(path))
        assert saved is not None
        assert saved["section_drafts"] == old_drafts
        assert saved["section_dispatches"] == old_dispatches
        assert saved["provider_calls_total"] == 2
        assert saved["provider_calls"] == 2
        assert saved["snapshot_sha256"] == snapshot_sha
        assert len(saved["provider_change_history"]) == 1
        assert not papers._rebind_paper_checkpoint_provider(
            saved, new_fingerprint, "replacement-model", "medium"
        )

        # A dispatched one-shot request with no saved draft stays nonreplayable.
        uncertain = papers._new_work(
            snapshot_sha,
            project.id,
            "a" * 64,
            "old-model",
            "high",
            kind="one_shot",
        )
        uncertain["frozen_package"] = package
        uncertain["provider_calls"] = 1
        uncertain["provider_calls_total"] = 1
        papers._save_work(str(path), uncertain)
        preview = papers.preflight(
            str(path),
            expected_project_id=project.id,
            expected_binding=binding,
            mode="chatgpt",
            model="replacement-model",
            reasoning_effort="medium",
        )
        assert preview["resume_available"] is False
        assert preview["incomplete_one_shot"] is True


def test_frozen_snapshot_generation_gate_checks_identity_hash_and_source_uniqueness() -> None:
    package = {
        "schema": "sigma-paper-evidence-v2",
        "project_id": "frozen-project",
        "sources": [{"id": "project:frozen-project", "kind": "project", "data": {}}],
    }
    validated, digest = papers._validate_frozen_snapshot(package, "frozen-project")
    assert validated is package
    assert len(digest) == 64
    duplicate = {**package, "sources": [*package["sources"], *package["sources"]]}
    for invalid, project_id, expected in (
        (package, "other-project", "another project"),
        (duplicate, "frozen-project", "duplicate"),
    ):
        try:
            papers._validate_frozen_snapshot(invalid, project_id)
        except papers.ProjectError as exc:
            assert expected in str(exc)
        else:
            raise AssertionError(f"Invalid frozen snapshot was accepted: {expected}")


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
        view = initialize_project(
            path, "Easy paper", "How many regions can n lines form?", research_mode="mathematical"
        )
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
            # Start over keeps only small attempt accounting, not a restartable
            # checkpoint or a stale terminal progress sidecar.
            assert papers._load_work(str(path)) is None
            assert papers._read_progress_status(str(path)) is None
            assert papers.progress_status(str(path)) is None
            ledger = papers._read_reset_ledger(str(path))
            assert ledger is not None and ledger["attempt_started"] is False
            assert ledger["provider_calls_total"] == 2
            assert len(ledger["prior_runs"]) == 1
            assert ledger["prior_runs"][0]["provider_calls_attempted"] == 2
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
            assert after["checkpoint_exists"] is False
            assert after["checkpoint_can_restart"] is False
            assert after["restart_ready"] is True


def test_one_shot_local_validation_retries_without_stopping_or_rebilling() -> None:
    """A transient local check retries in the same run with its paid draft intact."""
    with TemporaryDirectory() as directory:
        path = Path(directory) / "validation-recovery.sigma"
        view = initialize_project(
            path, "Paper recovery", "Review the saved objective.", research_mode="mathematical"
        )
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
                result = await papers.generate(str(path), account["identity"], view.project.id)
                assert provider_calls == 1
                assert validations >= 2
                saved = papers.get_paper(str(path), result["paper_id"])
                assert saved["pdf_available"] is True
                assert saved["generation"]["provider_calls_attempted"] == 2
                assert any(
                    "recovered a local paper-validation failure" in issue
                    for issue in saved["generation"]["sigma_issues"]
                )
                assert papers._load_work(str(path)) is None

        asyncio.run(run())


def test_table_cross_section_claim_is_omitted_without_losing_authored_prose() -> None:
    """An out-of-section citation is an optional table defect, not a fatal paper."""
    original = draft()
    claim = original.claims[0]
    second = claim.model_copy(
        update={"id": "C2", "statement": "A distinct hypothesis concerns a different section."}
    )
    table = papers.PaperTable.model_validate(
        {
            "caption": "Candidate discriminator with a misplaced paper-wide claim.",
            "headers": ["Candidate", "Status"],
            "rows": [["Stage coupling", "Needs additional evidence"]],
            "claim_ids": ["C2"],
            "evidence_refs": ["project:pid"],
        }
    )
    corrupt = original.model_copy(
        update={
            "claims": [claim, second],
            "sections": [
                original.sections[0].model_copy(update={"tables": [table]}),
                original.sections[1].model_copy(update={"claim_ids": ["C2"]}),
            ],
        }
    )
    repaired = papers.PaperDraft.model_validate(
        papers._repair_paper_references(corrupt, {"project:pid"})
    )
    assert repaired.sections[0].tables == []
    assert repaired.sections[0].paragraphs == original.sections[0].paragraphs
    assert repaired.sections[0].claim_ids == original.sections[0].claim_ids
    assert repaired.sections[1].claim_ids == ["C2"]
    assert any(
        "referenced claims outside its section" in message
        for message in repaired.validation_warnings
    )
    assert papers._validate(repaired, {"sources": [{"id": "project:pid", "data": {}}]})


def test_optional_table_tex_failure_keeps_paper_and_publishes_text_pdf() -> None:
    """Broken optional table typesetting must not discard paid scientific prose."""
    with TemporaryDirectory() as directory:
        path = Path(directory) / "table-render-recovery.sigma"
        view = initialize_project(
            path, "Table recovery", "Review the saved objective.", research_mode="mathematical"
        )
        credential = {"identity": "chatgpt:fixture", "mode": "chatgpt", "token": "fixture"}
        config = {
            "available": True,
            "binding": credential["identity"],
            "model": "fixture-model",
            "reasoning_effort": "high",
        }
        author_calls = 0
        compile_attempts = 0

        async def author(context, _account, _config, *_args):
            nonlocal author_calls
            author_calls += 1
            source = next(item["id"] for item in context["sources"] if item["kind"] == "project")
            paper = draft(source)
            table = papers.PaperTable(
                caption="The optional candidate-discriminator comparison.",
                headers=["Candidate", "Status"],
                rows=[["Temporal coupling", "Not independently verified"]],
                evidence_refs=[source],
                claim_ids=["C1"],
            )
            return paper.model_copy(
                update={
                    "sections": [
                        paper.sections[0].model_copy(update={"tables": [table]}),
                        paper.sections[1],
                    ]
                }
            ), config["model"]

        def compile_tex(tex, **_kwargs):
            nonlocal compile_attempts
            compile_attempts += 1
            if r"\begin{tabular}" in tex or r"\begin{longtable}" in tex:
                raise RuntimeError("Fixture table alignment failure")
            return b"%PDF-fixture"

        with (
            patch.object(papers, "auth_context", new=lambda: asyncio.sleep(0, result=credential)),
            patch.object(
                papers, "configuration", new=lambda **_kwargs: asyncio.sleep(0, result=config)
            ),
            patch.object(papers, "_provider", new=author),
            patch.object(papers, "_compile_pdf", new=compile_tex),
            mock_pdf_inspection(),
        ):
            result = asyncio.run(
                papers.generate(str(path), credential["identity"], view.project.id)
            )

        saved = papers.get_paper(str(path), result["paper_id"])
        assert author_calls == 1
        assert compile_attempts >= 2
        assert saved["pdf_available"] is True
        assert all(not section["tables"] for section in saved["draft"]["sections"])
        assert r"\begin{tabular}" not in saved["tex_source"]
        assert saved["generation"]["publication_status"] == "needs_review"
        assert any("text-only rendering" in issue for issue in saved["generation"]["sigma_issues"])
        assert papers._load_work(str(path)) is None


def test_persistent_invalid_paper_validation_still_blocks_publication() -> None:
    """A repeatable integrity error is not silently downgraded to an accepted paper."""
    original = draft()
    with patch.object(papers, "_validate", side_effect=ProjectError("Invalid provenance")) as check:
        try:
            papers._validate_with_local_recovery(
                original, {"sources": [{"id": "project:pid", "data": {}}]}, {}
            )
        except ProjectError as exc:
            assert "Invalid provenance" in str(exc)
        else:
            raise AssertionError("Unsupported paper provenance must not be accepted")
    assert check.call_count == 2


def test_live_research_change_does_not_discard_completed_paper() -> None:
    """A paper cites its frozen input even when unrelated saved research advances."""
    with TemporaryDirectory() as directory:
        path = Path(directory) / "research-advanced.sigma"
        view = initialize_project(
            path, "Frozen paper", "Study saved evidence.", research_mode="mathematical"
        )
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
        view = initialize_project(
            path, "Frozen paper", "Saved evidence", research_mode="mathematical"
        )
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
        view = initialize_project(
            path, "Paper recovery", "Study the saved research.", research_mode="mathematical"
        )
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


def test_repair_coalesces_only_exact_duplicate_propositions() -> None:
    original = draft()
    first = original.claims[0]
    duplicate = first.model_copy(update={"id": "C2"})
    extra = first.model_copy(
        update={
            "id": "C3",
            "statement": "A distinct conditional counterexample changes the conclusion.",
        }
    )
    outline = original.model_copy(
        update={
            "claims": [first, duplicate, extra],
            "abstract_claim_ids": ["C2", "C3"],
            "sections": [
                original.sections[0].model_copy(update={"claim_ids": ["C2", "C3"]}),
                original.sections[1],
            ],
        }
    )
    repaired = papers.PaperDraft.model_validate(
        papers._repair_paper_references(outline, {"project:pid"})
    )
    assert [claim.id for claim in repaired.claims] == ["C1", "C3"]
    assert repaired.abstract_claim_ids == ["C1", "C3"]
    assert repaired.sections[0].claim_ids == ["C1", "C3"]
    assert repaired.claims[0].evidence_refs == first.evidence_refs
    assert repaired.claims[1].statement == extra.statement
    assert any("Duplicate proposition C2" in x for x in repaired.validation_warnings)


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
        view = initialize_project(
            path,
            "One-call recovery",
            "Explain the recorded research.",
            research_mode="mathematical",
        )
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
                assert papers._load_work(str(path)) is None
                assert papers._read_progress_status(str(path)) is None
                assert papers._read_reset_ledger(str(path)) is not None
                reject = False
                result = await papers.generate(str(path), account["identity"], view.project.id)
                assert calls == 2
                record = papers.get_paper(str(path), result["paper_id"])
                assert record["generation"]["provider_calls_attempted"] == 2
                assert record["generation"]["provider_calls_prior_runs"] == 1
                assert record["generation"]["provider_calls_lifetime_total"] == 3
                assert papers._load_work(str(path)) is None
                assert papers._read_reset_ledger(str(path)) is None
                status = papers._read_progress_status(str(path))
                assert status is not None
                assert status["status"] == "complete"
                assert status["stage"] == "complete"
                assert "scoring did not finish" in status.get("detail", "")
                assert papers.get_pdf(str(path), result["paper_id"]) == b"%PDF-fixture"

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
    assert r"\node[boundary,fit=(campus)(policy)" in tex
    assert r"\begin{tabular}{" in tex
    assert r"\begin{longtable}" not in tex
    assert "Evidence: [project:pid]; claims: C1" in tex
    # Larger comparisons must still use the multipage table path and preserve
    # the same source attribution as compact tables.
    long_table = table.model_copy(update={"rows": table.rows * 3})
    long_paper = paper.model_copy(
        update={
            "sections": [
                paper.sections[0].model_copy(update={"tables": [long_table]}),
                paper.sections[1],
            ]
        }
    )
    long_tex = papers._tex(long_paper, [], "a" * 64)
    assert r"\begin{longtable}{" in long_tex
    assert "Evidence: [project:pid]; claims: C1" in long_tex
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


def test_table_cell_math_escaping_and_currency_regression() -> None:
    """Table math must survive doubled escapes and wrapped author text."""
    math = r"$A \rightarrow R \rightarrow T$"
    doubled = r"$A \\rightarrow R \\rightarrow T$"
    expected = r"$A \rightarrow R \rightarrow T$"
    assert papers._latex_table_cell(math) == expected
    assert papers._latex_table_cell(doubled) == expected
    assert papers._latex_table_cell("$A \\\\rightarrow\n R \\\\rightarrow T$") == expected
    assert papers._latex_table_cell("Path " + doubled + " approved") == (
        "Path " + expected + " approved"
    )
    assert papers._latex_table_cell("Costs $5 and $10.") == r"Costs \$5 and \$10."
    assert papers._latex_table_cell("Price $5, formula " + math) == (
        r"Price \$5, formula " + expected
    )
    assert papers._latex_table_cell(r"$A \\input{secrets} B$").count(r"\textbackslash") >= 1

    paper = draft("project:pid")
    table = papers.PaperTable(
        caption="Constructed history and transfer-contract comparison for approval.",
        headers=[
            "Constructed history",
            "Authorization-time contract",
            "Transfer-start contract",
            "Expressly approved lease",
        ],
        rows=[
            [doubled, "Approved under " + math, "Cost $5 and $10", "Ordinary prose"],
            [
                "$R \\\\rightarrow\n A \\\\rightarrow T$",
                "Keep $1,000 literal",
                "No change",
                "Agreed",
            ],
        ],
        evidence_refs=["project:pid"],
        claim_ids=["C1"],
    )
    modified = paper.model_copy(
        update={
            "sections": [
                paper.sections[0].model_copy(update={"tables": [table]}),
                paper.sections[1],
            ]
        }
    )
    tex = papers._tex(modified, [], "a" * 64)
    assert r"\begin{longtable}{" in tex
    assert expected in tex
    assert r"$R \rightarrow A \rightarrow T$" in tex
    assert r"Cost \$5 and \$10" in tex
    assert r"Keep \$1,000 literal" in tex
    assert r"\\rightarrow" not in tex
    assert r"\$A" not in tex
    assert papers._latex_prose(r"Body $A \rightarrow T$") == r"Body $A \rightarrow T$"
    assert table.rows[0][0] == doubled  # no mutation of the authored source

    compact = table.model_copy(
        update={
            "headers": ["History", "Contract", "Price"],
            "rows": [[doubled, "Approved", "Costs $5 and $10"]],
        }
    )
    compact_draft = paper.model_copy(
        update={
            "sections": [
                paper.sections[0].model_copy(update={"tables": [compact]}),
                paper.sections[1],
            ]
        }
    )
    compact_tex = papers._tex(compact_draft, [], "a" * 64)
    assert r"\begin{tabular}{" in compact_tex
    assert expected in compact_tex
    assert r"Costs \$5 and \$10" in compact_tex
    if shutil.which("tectonic"):
        pdf = papers._compile_pdf(tex, timeout_seconds=90)
        assert pdf.startswith(b"%PDF-")


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
                assert r"Candidate stage\textendash{}\allowbreak{}time dependency map" in tex
                assert r"\textendash{}" in tex
                assert (
                    "Diagram (readable relationship list)." in tex or r"\begin{tikzpicture}" in tex
                )
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


def test_publication_preserves_failed_final_skeptic_as_research_limitation() -> None:
    session = {
        "id": "session-failed-final",
        "kind": "session",
        "data": {
            "id": "failed-final",
            "status": "ended",
            "terminal_reason": "Research stopped early. Research is incomplete.",
            "termination_reason_code": "provider_or_strategy_failure",
            "steps": [
                {
                    "call_number": 18,
                    "role": "skeptic",
                    "status": "failed",
                    "failure_kind": "provider_error",
                }
            ],
        },
    }
    healthy = {
        "id": "session-complete",
        "kind": "session",
        "data": {"id": "complete", "status": "ended", "termination_reason_code": "completed"},
    }
    frozen = {"sources": [session, healthy]}
    notes = papers._research_completion_limitations(frozen)
    assert len(notes) == 1
    assert "failed-final" in notes[0]
    assert "call 18 (skeptic)" in notes[0]
    assert "Earlier findings remain available" in notes[0]
    result = papers._annotate_research_completion(draft(), frozen)
    assert any("call 18 (skeptic)" in item for item in result.limitations)
    assert len(result.limitations) == len(draft().limitations) + 1
    assert len(papers._annotate_research_completion(result, frozen).limitations) == len(
        result.limitations
    )
    assert papers._research_completion_limitations({"sources": [healthy]}) == []


def test_review_fallback_question_and_tex_safety() -> None:
    """Phase-1 writing fixes must preserve the problem and scientific notation."""
    question = (
        "Can a gateway improve authorized research completion? "
        + "The project also includes background and long source references. " * 20
        + "https://mindrouter.ai/documentation"
    )
    plan = papers._evidence_based_long_plan(
        {"title": "Conditional gateway research", "problem": question},
        [],
        {"project:gateway"},
        [{"id": "project:gateway", "kind": "project", "data": {"problem": question}}],
    )
    assert "Can a gateway improve authorized research completion?" in plan.problem_framing[0]
    assert "https://mindrouter.ai/documen" not in plan.problem_framing[0]
    assert "… " not in plan.problem_framing[0]
    assert r"$\eta$" in papers._latex_prose("Error allowance η")
    assert r"$\rho$" in papers._latex_prose("Density ρ")
    rendered = papers._latex_prose("See https://mindrouter.ai/documentation.html for reference.")
    assert r"\url{https://mindrouter.ai/documentation.html}" in rendered
    wrapped = papers._latex_prose("Recorded at portfolio_decision/cross_strategy_reviews/2.")
    assert r"portfolio\_\allowbreak{}decision" in wrapped
    assert r"\usepackage[hyphens]{url}" in papers._tex(
        draft(), [], "e" * 64, include_research_details=False
    )
    tex = papers._tex(
        draft(),
        [],
        "a" * 64,
        integrity_records=[{"kind": "research", "description": "Saved private artifact"}],
        include_research_details=True,
        include_research_excerpts=False,
    )
    assert r"\section{Selected source-linked research excerpts}" not in tex
    assert r"\section{Structured reasoning and review records}" not in tex
    # Research detail is not permission to append the claim audit ledger.
    assert r"\section{Claim and source notes}" not in tex
    assert r"\section*{Evidence and authorship note}" not in tex
    with_claims = papers._tex(
        draft(),
        [],
        "a" * 64,
        integrity_records=[{"kind": "research", "description": "Saved private artifact"}],
        include_research_details=True,
        include_claim_details=True,
        include_research_excerpts=False,
    )
    assert r"\section{Claim and source notes}" in with_claims
    assert r"\begin{sloppypar}" in with_claims
    assert r"\end{sloppypar}" in with_claims


def test_review_fallback_rejects_process_text_as_claim() -> None:
    research = "The bounded comparison leaves the remote policy condition unresolved."
    scaffolding = "Structured argument steps are recorded; review their evidence and objections."
    notes = [
        papers.EvidenceNote(
            statement="findings: " + scaffolding,
            kind="result",
            evidence_refs=["artifact:meta"],
        ),
        papers.EvidenceNote(
            statement="findings: " + research,
            kind="result",
            evidence_refs=["artifact:research"],
        ),
    ]
    plan = papers._evidence_based_long_plan(
        {"title": "Policy comparison", "problem": "Can the policy remain enforceable?"},
        notes,
        {"artifact:meta", "artifact:research"},
        [
            {"id": "artifact:meta", "kind": "artifact", "data": {"findings": scaffolding}},
            {"id": "artifact:research", "kind": "artifact", "data": {"findings": research}},
        ],
    )
    assert any(research in claim.statement for claim in plan.claims)
    assert all(scaffolding not in claim.statement for claim in plan.claims)
    assert scaffolding not in plan.abstract
    assert all(not paragraph.startswith("Recorded result:") for paragraph in plan.conclusions)


def test_review_proofreader_accepts_safe_patch_but_rejects_mutation() -> None:
    """One unsafe suggestion must not discard an unrelated safe layout repair."""
    with TemporaryDirectory() as temporary:
        path = Path(temporary) / "mixed-proofread.sigma"
        view = initialize_project(path, "Mixed proofreading", "Protect research claims")
        state = papers._new_work(
            "c" * 64, view.project.id, "d" * 64, "fixture", "high", kind="one_shot"
        )
        tex = (
            "\\documentclass{article}\n\\emergencystretch=2em\n"
            "\\begin{document}\nThe result is 3.\n\\end{document}\n"
        )

        async def provider(_input, _binding, _config, *, response_model, **_kwargs):
            return response_model(
                corrections=[
                    papers.TeXCorrection(
                        category="spacing",
                        find=r"\emergencystretch=2em",
                        replace=r"\emergencystretch=4em",
                        rationale="Safe line breaking adjustment.",
                    ),
                    papers.TeXCorrection(
                        category="spacing",
                        find="result is 3",
                        replace="result is 4",
                        rationale="Unsafe scientific alteration fixture.",
                    ),
                ]
            ), "fixture"

        async def report(*_args, **_kwargs):
            return None

        with (
            patch.object(papers, "_compile_pdf", return_value=b"%PDF-fixture"),
            patch.object(papers, "_provider_structured", new=provider),
        ):
            corrected, result = asyncio.run(
                papers._proofread_tex(
                    tex,
                    state,
                    binding={"identity": "fixture", "mode": "api_key", "token": "fixture"},
                    config={"model": "fixture", "reasoning_effort": "high"},
                    project_id=view.project.id,
                    project_path_value=str(path),
                    report=report,
                )
            )
        assert r"\emergencystretch=4em" in corrected
        assert "The result is 3" in corrected and "The result is 4" not in corrected
        assert result["status"] == "fallback"
        assert result["corrections"] == ["spacing"]
        assert "changed protected scientific" in result["fallback_reason"]


def test_paper_sse_bounds_generated_text_not_redundant_transport() -> None:
    """Large streams of progress frames must not require large in-memory output."""

    class ProgressStream:
        def __init__(self) -> None:
            self.headers = {"content-type": "text/event-stream"}

        async def aiter_bytes(self):
            yield (
                b'data: {"type":"response.created","sequence_number":0,'
                b'"response":{"id":"paper"}}\n\n'
            )
            for index in range(1, 810):
                event = {
                    "type": "response.in_progress",
                    "sequence_number": index,
                    "response": {"id": "paper", "padding": "p" * 21_000},
                }
                yield ("data: " + json.dumps(event) + "\n\n").encode()
            yield (
                b'data: {"type":"response.output_text.delta","sequence_number":810,'
                b'"delta":"small section"}\n\n'
            )
            yield (
                b'data: {"type":"response.completed","sequence_number":811,'
                b'"response":{"id":"paper","status":"completed","output":[]}}\n\n'
            )

    events: list[tuple[str, int]] = []
    result = asyncio.run(
        completed(
            cast(httpx.Response, ProgressStream()),
            max_stream_bytes=None,
            max_event_chars=4_000_000,
            max_events=100_000,
            max_text_bytes=papers.MAX_RESPONSE_BYTES,
            on_event_observed=lambda kind, n: events.append((kind, n)),
        )
    )
    assert events[0] == ("response.created", 0)
    assert events[-2:] == [
        ("response.output_text.delta", len("small section")),
        ("response.completed", 0),
    ]
    assert len(events) == 812
    assert result["status"] == "completed"
    assert result["output"][0]["content"][0]["text"] == "small section"

    class TruncatedStream:
        def __init__(self) -> None:
            self.headers = {"content-type": "text/event-stream"}

        async def aiter_bytes(self):
            yield (
                b'data: {"type":"response.created","sequence_number":0,'
                b'"response":{"id":"paper"}}\n\n'
            )
            yield (
                b'data: {"type":"response.output_text.delta","sequence_number":1,'
                b'"delta":"partial"}\n\n'
            )

    try:
        asyncio.run(
            completed(
                cast(httpx.Response, TruncatedStream()),
                max_stream_bytes=None,
                max_event_chars=4_000_000,
                max_events=100_000,
                max_text_bytes=papers.MAX_RESPONSE_BYTES,
                incomplete_message="Paper stream ended without completion; saved sections remain.",
            )
        )
    except ProjectError as exc:
        assert "saved sections remain" in str(exc)
        assert "strategy" not in str(exc)
    else:
        raise AssertionError("Truncated SSE completion was accepted")

    class ExcessiveTextStream:
        def __init__(self) -> None:
            self.headers = {"content-type": "text/event-stream"}

        async def aiter_bytes(self):
            yield (
                b'data: {"type":"response.created","sequence_number":0,'
                b'"response":{"id":"paper"}}\n\n'
            )
            yield (
                b'data: {"type":"response.output_text.delta","sequence_number":1,'
                b'"delta":"this text exceeds the small test bound"}\n\n'
            )

    try:
        asyncio.run(
            completed(
                cast(httpx.Response, ExcessiveTextStream()),
                max_stream_bytes=None,
                max_event_chars=4_000_000,
                max_events=100_000,
                max_text_bytes=10,
            )
        )
    except ProjectError as exc:
        assert "bounded response capacity" in str(exc)
    else:
        raise AssertionError("Oversized generated text was accepted")


if __name__ == "__main__":
    from papers_split_runner import run

    run(2)
