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


def test_readable_paper_download_names_keep_stable_versions_and_server_headers() -> None:
    """Saved names stay readable and attached to each paper version after edits/deletion."""
    from concurrent.futures import ThreadPoolExecutor

    from sigma import api, project_bundle

    def save_fixture(path: Path, project_id: str, paper_id: str, created_at: str) -> None:
        record = {
            "schema_version": 1,
            "paper_id": paper_id,
            "project_id": project_id,
            "created_at": created_at,
            "snapshot_sha256": "a" * 64,
            "draft": {"title": "A saved paper"},
            "generation": {},
            "validation_warnings": [],
            "tex_source": r"\documentclass{article}\begin{document}Fixture\end{document}",
        }
        papers._save(str(path), record, b"%PDF-fixture")

    with TemporaryDirectory() as temporary:
        root = Path(temporary)
        path = root / "readable-paper.sigma"
        view = initialize_project(path, "  Étoile / Math: Sums!  ", "Count a saved example.")
        first_id, second_id = "a" * 32, "b" * 32
        save_fixture(path, view.project.id, first_id, "2026-10-01T00:00:00+00:00")
        save_fixture(path, view.project.id, second_id, "2026-10-02T00:00:00+00:00")
        papers_found = papers.list_papers(str(path))
        assert [(item["paper_version"], item["download_basename"]) for item in papers_found] == [
            (2, "étoile-math-sums-v2"),
            (1, "étoile-math-sums-v1"),
        ]
        assert papers.paper_download_basename(str(path), first_id) == "étoile-math-sums-v1"
        for endpoint, extension in (
            (api.paper_pdf_view, "pdf"),
            (api.paper_txt_view, "txt"),
            (api.paper_tex_view, "tex"),
        ):
            response = endpoint(first_id, str(path))
            disposition = response.headers["content-disposition"]
            assert f"filename*=UTF-8''%C3%A9toile-math-sums-v1.{extension}" in disposition
            assert first_id not in disposition
        inline = api.paper_pdf_view(first_id, str(path), open_in_browser=True)
        assert inline.headers["content-disposition"].startswith("inline;")
        assert (
            "filename*=UTF-8''%C3%A9toile-math-sums-v1.pdf" in inline.headers["content-disposition"]
        )

        papers.delete_paper(str(path), second_id)
        assert papers.paper_download_basename(str(path), first_id) == "étoile-math-sums-v1"
        third_id = "c" * 32
        save_fixture(path, view.project.id, third_id, "2026-10-03T00:00:00+00:00")
        assert papers.paper_download_basename(str(path), third_id) == "étoile-math-sums-v3"

        # Exercise the portable JSON-project format separately from the legacy
        # directory format; its sequence must travel inside the project bundle.
        source_document = (path / "project.json").read_bytes()
        json_source = root / "editable.json"
        project_bundle.import_bundle(
            project_bundle.portable_bundle({"project.json": source_document}), json_source
        )
        json_id = "d" * 32
        save_fixture(json_source, view.project.id, json_id, "2026-10-04T00:00:00+00:00")
        json_export = json.loads(project_bundle.download_bytes(str(json_source)))
        imported_path = root / "round-trip.json"
        project_bundle.import_bundle(json_export, imported_path)
        fifth_id = "e" * 32
        save_fixture(imported_path, view.project.id, fifth_id, "2026-10-05T00:00:00+00:00")
        assert papers.paper_download_basename(str(imported_path), json_id) == "étoile-math-sums-v1"
        assert papers.paper_download_basename(str(imported_path), fifth_id) == "étoile-math-sums-v2"
        assert papers._paper_filename_slug("/// !!!") == "sigma-paper"
        assert not any(
            paper_id in papers.paper_download_basename(str(path), paper_id)
            for paper_id in (first_id, third_id)
        )

        concurrent_path = root / "concurrent-paper.sigma"
        concurrent_view = initialize_project(
            concurrent_path, "Concurrent Paper", "Allocate distinct stable versions."
        )
        concurrent_ids = [f"{index:032x}" for index in range(1, 13)]
        with ThreadPoolExecutor(max_workers=12) as executor:
            list(
                executor.map(
                    lambda item: save_fixture(
                        concurrent_path,
                        concurrent_view.project.id,
                        item,
                        "2026-10-01T00:00:00+00:00",
                    ),
                    concurrent_ids,
                )
            )
        assert sorted(
            item["paper_version"] for item in papers.list_papers(str(concurrent_path))
        ) == list(range(1, len(concurrent_ids) + 1))


def test_unexpected_paper_exception_yields_sanitized_sse_error() -> None:
    """An unexpected crash must not terminate HTTP 200 without an SSE error."""

    async def check() -> None:
        with TemporaryDirectory() as temporary:
            path = Path(temporary) / "paper-error.sigma"
            view = initialize_project(
                path, "Paper error test", "Verify SSE error recovery", research_mode="mathematical"
            )

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


def test_paper_sse_accepts_standard_line_endings_across_byte_chunks() -> None:
    """CR, CRLF and LF SSE frames must all preserve a terminal completion."""
    events = [
        {"type": "response.created", "sequence_number": 0, "response": {"id": "paper-cr"}},
        {"type": "response.output_text.delta", "sequence_number": 1, "delta": "café"},
        {
            "type": "response.completed",
            "sequence_number": 2,
            "response": {"id": "paper-cr", "status": "completed", "output": []},
        },
    ]

    class BytewiseStream:
        def __init__(self, content: bytes) -> None:
            self.headers = {"content-type": "text/event-stream"}
            self.content = content

        async def aiter_bytes(self):
            for value in self.content:
                yield bytes((value,))

    observed_output: list[str] = []

    async def saw_output() -> None:
        observed_output.append("delta")

    for line_break in ("\n", "\r\n", "\r"):
        for last_separator in (True, False):
            separator = line_break * 2
            frames = ["data: " + json.dumps(event, ensure_ascii=False) for event in events]
            stream_text = "\ufeff" + separator.join(frames)
            if last_separator:
                stream_text += separator
            content = stream_text.encode("utf-8")
            observed_output.clear()
            result = asyncio.run(
                completed(
                    cast(httpx.Response, BytewiseStream(content)),
                    max_stream_bytes=None,
                    max_event_chars=4_000_000,
                    max_text_bytes=papers.MAX_RESPONSE_BYTES,
                    on_output_delta=saw_output,
                )
            )
            assert observed_output == ["delta"]
            assert result["status"] == "completed"
            assert result["output"][0]["content"][0]["text"] == "café"


def test_long_paper_json_whitespace_guard_respects_strings_and_chunks() -> None:
    """Legitimate whitespace in strings is never treated as JSON formatting."""
    from sigma.paper_stream_guard import JSONWhitespaceGuard, JSONWhitespaceStall

    safe = JSONWhitespaceGuard(limit=64)
    for delta in (
        '{"paragraphs":["This is a prose value ', " " * 5000,
        ' still inside string"],"tables":[],"examples":[]}',
    ):
        safe.observe(delta)
    assert not safe.in_string and safe.consecutive == 0

    runaway = JSONWhitespaceGuard(limit=64)
    runaway.observe('{"paragraphs":["Finished prose."],"tables":[]')
    try:
        for _ in range(100):
            runaway.observe(" \n")
    except JSONWhitespaceStall:
        assert runaway.consecutive == 65
    else:
        raise AssertionError("A whitespace-output stall was not detected")


def test_long_paper_section_provider_stops_runaway_without_paid_replay() -> None:
    """A 2,049-character whitespace suffix is not a completed paper section."""
    from sigma.paper_stream_guard import JSONWhitespaceStall

    events = [
        {"type": "response.created", "sequence_number": 0, "response": {"id": "paper-loop"}},
        {"type": "response.output_text.delta", "sequence_number": 1,
         "delta": '{"paragraphs":["A complete, evidence-linked paragraph."],"tables":[]'},
        *[
            {"type": "response.output_text.delta", "sequence_number": n,
             "delta": " \n" * 80}
            for n in range(2, 25)
        ],
    ]
    dispatched: list[dict[str, Any]] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        dispatched.append(json.loads(request.content))
        stream = "".join("data: " + json.dumps(event) + "\n\n" for event in events)
        return httpx.Response(
            200, headers={"content-type": "text/event-stream"}, content=stream.encode()
        )

    actual_client = httpx.AsyncClient
    with patch(
        "sigma.papers.httpx.AsyncClient",
        side_effect=lambda **kw: actual_client(transport=httpx.MockTransport(handler), **kw),
    ):
        try:
            asyncio.run(
                papers._provider_structured(
                    {"section_number": 2},
                    {"mode": "chatgpt", "token": "fixture"},
                    {"model": "gpt-6.1-sol", "reasoning_effort": "medium"},
                    instructions="Write this paper section.",
                    schema_name="sigma_long_paper_section",
                    response_model=papers.LongSectionDraft,
                )
            )
        except JSONWhitespaceStall as exc:
            assert "No automatic paid retry" in str(exc)
        else:
            raise AssertionError("Runaway section incorrectly accepted as complete")

    assert len(dispatched) == 1
    assert "max_output_tokens" not in dispatched[0]


def test_long_paper_section_provider_accepts_large_quoted_whitespace() -> None:
    """A substantial quoted paragraph must pass the same guarded SSE path."""
    body = json.dumps(
        {"paragraphs": ["The result is " + " " * 5000 + "supported."],
         "tables": [], "examples": []}
    )
    events = [
        {"type": "response.created", "sequence_number": 0, "response": {"id": "normal"}},
        {"type": "response.output_text.delta", "sequence_number": 1, "delta": body},
        {"type": "response.completed", "sequence_number": 2,
         "response": {"id": "normal", "status": "completed", "output": []}},
    ]

    async def handler(_request: httpx.Request) -> httpx.Response:
        stream = "".join("data: " + json.dumps(event) + "\n\n" for event in events)
        return httpx.Response(
            200, headers={"content-type": "text/event-stream"}, content=stream.encode()
        )

    actual_client = httpx.AsyncClient
    with patch(
        "sigma.papers.httpx.AsyncClient",
        side_effect=lambda **kw: actual_client(transport=httpx.MockTransport(handler), **kw),
    ):
        parsed, _ = asyncio.run(
            papers._provider_structured(
                {"section_number": 2},
                {"mode": "chatgpt", "token": "fixture"},
                {"model": "gpt-6.1-sol", "reasoning_effort": "medium"},
                instructions="Write this paper section.",
                schema_name="sigma_long_paper_section",
                response_model=papers.LongSectionDraft,
            )
        )
    assert parsed.paragraphs[0].endswith("supported.")


def test_paper_terminal_sse_event_without_final_separator() -> None:
    """A complete EOF terminal is valid; a truncated final JSON is not."""
    created = (
        b'data: {"type":"response.created","sequence_number":0,"response":{"id":"paper-test"}}\n\n'
    )
    delta = (
        b'data: {"type":"response.output_text.delta","sequence_number":1,'
        b'"delta":"finished section"}\n\n'
    )
    terminal = (
        b'data: {"type":"response.completed","sequence_number":2,'
        b'"response":{"id":"paper-test","status":"completed","output":[]}}'
    )

    class EOFStream:
        def __init__(self, tail: bytes) -> None:
            self.headers = {"content-type": "text/event-stream"}
            self.tail = tail

        async def aiter_bytes(self):
            yield created
            yield delta
            yield self.tail

    for tail in (terminal, terminal + b"\n", terminal + b"\r\n"):
        result = asyncio.run(
            completed(
                cast(httpx.Response, EOFStream(tail)),
                max_stream_bytes=None,
                max_event_chars=4_000_000,
                max_text_bytes=papers.MAX_RESPONSE_BYTES,
            )
        )
        assert result["status"] == "completed"
        assert result["output"][0]["content"][0]["text"] == "finished section"

    # A partially delivered terminal must never certify paid work as complete.
    truncated = terminal[:-9]
    try:
        asyncio.run(
            completed(
                cast(httpx.Response, EOFStream(truncated)),
                max_stream_bytes=None,
                incomplete_message="Paper stream ended before a valid response.completed.",
            )
        )
    except ProjectError as exc:
        assert "before a valid response.completed" in str(exc)
        assert "SSE events: 2" in str(exc)
        assert "last event: response.output_text.delta" in str(exc)
        assert "response started: yes" in str(exc)
        assert "finished section" not in str(exc)
    else:
        raise AssertionError("A truncated terminal must not be accepted")


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
        except papers.PaperTransientFailure as exc:
            assert "Temporary paper-provider failure" in str(exc)
            assert isinstance(exc.__cause__, ProjectError)
            assert "before a valid response.completed" in str(exc.__cause__)
            assert "Completed work is saved" in str(exc.__cause__)
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
        initialize_project(
            checkpoint_path,
            "Proofreading fixture",
            "Preserve authored TeX.",
            research_mode="mathematical",
        )
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
        view = initialize_project(
            path, "Three-pass fixture", "Convergent corrections.", research_mode="mathematical"
        )
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
        view = initialize_project(
            path,
            "Proofreading recovery",
            "Preserve an authored conclusion.",
            research_mode="mathematical",
        )
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
        one_view = initialize_project(
            one_path, "One-shot proofreading", "Test stage ordering.", research_mode="mathematical"
        )
        long_view = initialize_project(
            long_path,
            "Long-form proofreading",
            "Test stage ordering.",
            research_mode="mathematical",
        )
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
                patch(
                    "sigma.paper_scores.score_paper",
                    new=lambda *_args, **_kwargs: asyncio.sleep(0, result={"total": 76}),
                ),
                # This test exercises TeX stage ordering, not external
                # publication compilation. Keep the optional source set empty.
                patch.object(
                    papers.paper_writing_sources,
                    "select",
                    new=lambda *_args, **_kwargs: asyncio.sleep(0, result=([], "unavailable")),
                ),
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
            assert (
                stages.index("compile")
                < stages.index("pdf_check")
                < stages.index("scoring")
                < stages.index("complete")
            )
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


def test_long_section_wire_schema_finishes_with_primary_prose() -> None:
    """Keep the simple typed contract established by the isolated live probe.

    With prose first, Sol/Medium twice generated a complete paragraphs array,
    then tables=[], followed by unbounded formatting whitespace before the
    required examples field. Emitting supporting fields first completed cleanly.
    """
    with_visuals = papers._paper_response_schema(
        papers.LongSectionDraft, include_diagrams=True
    )
    without_visuals = papers._paper_response_schema(
        papers.LongSectionDraft, include_diagrams=False
    )
    assert list(with_visuals["properties"]) == ["tables", "examples", "paragraphs"]
    assert with_visuals["required"] == list(with_visuals["properties"])
    assert list(without_visuals["properties"]) == ["examples", "paragraphs"]
    assert without_visuals["required"] == list(without_visuals["properties"])
    assert "PaperTable" in with_visuals.get("$defs", {})
    assert "PaperTable" not in without_visuals.get("$defs", {})

    # Persisted drafts and explicitly authored examples remain ordinary
    # validated models, with no synthesized or discarded content.
    draft = papers.LongSectionDraft(
        paragraphs=["An evidence-linked section explains the result."],
        tables=[
            papers.PaperTable(
                caption="Source-linked comparison of allowed and denied requests",
                headers=["Decision", "Outcome"],
                rows=[["Allowed", "Admitted"], ["Denied", "Rejected"]],
                evidence_refs=["source:R1"],
                claim_ids=["C3"],
            )
        ],
        examples=[
            papers.PaperExample(
                title="Illustration",
                text="This is a concrete, source-linked illustrative example.",
                claim_ids=["C3"],
                after_paragraph=1,
            )
        ],
    )
    restored = papers.LongSectionDraft.model_validate_json(draft.model_dump_json())
    assert restored == draft
    assert len(restored.tables) == len(restored.examples) == 1
    assert list(json.loads(draft.model_dump_json())) == ["tables", "examples", "paragraphs"]


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
        initialize_project(
            path, "One-shot recovery", "Preserve this paper draft", research_mode="mathematical"
        )
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
            if compile_calls in {2, 3}:
                # Neither original visuals nor the bounded text-only recovery
                # can compile in this fixture, so resume must remain possible.
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
                    assert "safe visual fallback could not compile" in str(exc)
                else:
                    raise AssertionError("The unrecoverable compile failure must be surfaced")

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
        assert compile_calls == 5
        assert saved["generation"]["provider_calls_attempted"] == 3
        assert saved["generation"]["proofreading"]["provider_calls_attempted"] == 2
        assert saved["generation"]["provider_calls_lifetime_total"] == 3
        assert saved["generation"]["include_research_details"] is True
        assert saved["generation"]["include_diagrams_and_tables"] is False
        assert saved["draft"]["diagrams"] == []
        assert all(not section["tables"] for section in saved["draft"]["sections"])
        assert r"\usepackage{tikz}" not in saved["tex_source"]
        assert r"\begin{longtable}" not in saved["tex_source"]
        assert r"\begin{abstract}" in saved["tex_source"]
        assert papers._load_work(str(path)) is None
        assert len(papers.list_papers(str(path))) == 1
        # A one-shot provider response has no known partial section total.
        # Once the complete draft is saved, the real total appears before
        # validation and survives a failed PDF compilation.
        writing = next(item for item in first_events if item["stage"] == "writing")
        assert writing["current"] is None and writing["total"] is None
        sections = [item for item in first_events if item["stage"] == "sections"]
        assert len(sections) == 1
        assert sections[0]["current"] == sections[0]["total"] == len(saved["draft"]["sections"])
        assert sections[0].get("sections_total") == len(saved["draft"]["sections"])
        assert failed_progress["sections_total"] == len(saved["draft"]["sections"])
        resumed_sections = [item for item in retry_events if item["stage"] == "sections"]
        assert len(resumed_sections) == 1
        assert resumed_sections[0]["current"] == resumed_sections[0]["total"]
        first_stages = [event["stage"] for event in first_events if event["state"] == "active"]
        assert first_stages.index("validation") < first_stages.index("proofreading")
        assert first_stages.index("proofreading") < first_stages.index("compile")
        assert retry_events[-3]["stage"] in {"score_failed", "scoring"}
        assert retry_events[-2]["stage"] == "finishing"
        assert retry_events[-1]["stage"] == "complete"
        assert retry_events[-1]["state"] == "complete"
        assert retry_events[-1]["elapsed_seconds"] >= first_events[-1]["elapsed_seconds"]


def test_proofreading_option_changes_keep_per_render_and_cumulative_call_counts() -> None:
    """Repeated TeX option changes retain drafts and count each paid call once."""
    with TemporaryDirectory() as temporary:
        path = Path(temporary) / "proofreading-render-call-accounting.sigma"
        initialize_project(
            path,
            "Proofreading accounting",
            "Keep the saved paper draft.",
            research_mode="mathematical",
        )
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
                    assert "PDF compilation failed" in str(exc)
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
        view = initialize_project(
            path, "Diagram fallback", "Preserve the paper evidence.", research_mode="mathematical"
        )
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
            # Exercise the longtable fallback rather than the compact-table path.
            rows=[[f"Project question {index}", "Saved", "Frozen"] for index in range(6)],
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
            if len(compile_tex) <= 2:
                # Each proofreading pass compiles a temporary diagnostic fixture:
                # the provider receives the generated source next.
                return b"%PDF-initial-diagnostic-fixture"
            if len(compile_tex) == 3:
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
        assert r"$\alpha=3$" in compile_tex[2]
        assert r"$\alpha=3$" in successful_tex[0]
        assert r"\usepackage{tikz}" in compile_tex[0]
        assert r"\usepackage{tikz}" in compile_tex[1]
        assert r"\usepackage{tikz}" in compile_tex[2]
        assert r"\usepackage{tikz}" not in successful_tex[0]
        assert all(r"\begin{longtable}" in source for source in compile_tex)
        assert r"\begin{longtable}" in successful_tex[0]
        assert saved["snapshot_sha256"] == snapshot_hash
        assert saved["generation"]["provider_calls_attempted"] == (
            3 + saved["generation"]["publication_compiler_calls"]
        )
        assert saved["generation"]["proofreading"]["provider_calls_attempted"] == 2
        assert saved["generation"]["proofreading"]["correction_categories"] == ["math_notation"]
        assert saved["draft"]["diagrams"] == []
        assert saved["draft"]["sections"][0]["tables"]
        assert saved["tex_source"] == successful_tex[0]
        assert saved["generation"]["proofreading"]["corrected_tex_sha256"] == (
            papers.hashlib.sha256(compile_tex[2].encode()).hexdigest()
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
        view = initialize_project(
            path, "Unrelated compile failure", "Keep the diagram.", research_mode="mathematical"
        )
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
            assert "PDF compilation failed" in str(exc)
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
        include_claim_details=True,
        include_validation_notes=True,
        include_research_excerpts=True,
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
        r"\section{Claim and source notes}",
        r"\section{Issues found (diagnostic data)}",
        r"\section{Structured reasoning and review records}",
        r"\section{Publication references used}",
        "Validation:",
        "Snapshot SHA-256",
        r"\section*{Evidence and authorship note}",
    ):
        assert diagnostic not in concise, diagnostic
        assert diagnostic in detailed, diagnostic
    assert "Confirm the missing proof step." not in concise
    assert "Confirm the missing proof step." in detailed
    assert r"\section*{Evidence and authorship note}" not in concise


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
        include_validation_notes=True,
        include_research_excerpts=True,
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
            initialize_project(
                path, "Streamed paper", "A paper question", research_mode="mathematical"
            )
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
                include_sigma_issues,
                authorized_recovery_section,
            ):
                assert authorized_recovery_section is None
                assert include_sigma_issues is False
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
            view = initialize_project(
                path,
                "Interrupted paper",
                "Recover saved paper progress",
                research_mode="mathematical",
            )
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
            progress = response.json()["progress"]
            assert progress.pop("detail").startswith("The backend restarted")
            assert progress == {
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
        view = initialize_project(
            path, "Stale restart", "Preserve saved research", research_mode="mathematical"
        )
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

                    assert papers._load_work(str(path)) is None
                    reset = papers._read_reset_ledger(str(path))
                    assert reset is not None
                    assert reset["snapshot_sha256"] == current_snapshot_sha256
                    assert reset["attempt_started"] is False
                    assert reset["provider_calls_total"] == 3
                    assert len(reset["prior_runs"]) == 2

                    repeated = await client.post("/api/projects/papers/restart", json=body)
                    assert repeated.status_code == 200, repeated.text
                    assert repeated.json()["provider_calls_previous_runs"] == 3
                    assert papers._load_work(str(path)) is None
                    reset_again = papers._read_reset_ledger(str(path))
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
                    assert preflight["resume_available"] is False
                    assert preflight["checkpoint_exists"] is False
                    assert preflight["restart_ready"] is True
                    assert preflight["provider_calls_attempted"] == 0

        asyncio.run(check())


def test_explicit_restart_checkpoint_migrates_and_rebinds_safely() -> None:
    with TemporaryDirectory() as temporary:
        path = Path(temporary) / "restart.sigma"
        view = initialize_project(
            path, "Restarted paper", "A saved evidence question", research_mode="mathematical"
        )
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
        assert [item[1:3] for item in sections if item[3] == "active"] == [(0, 2), (1, 2)]
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
        initialize_project(
            path, sample["title"] + " v2", sample["problem"], research_mode="mathematical"
        )
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
            assert reset_preflight["resume_available"] is False
            assert reset_preflight["checkpoint_exists"] is False
            assert reset_preflight["restart_ready"] is True
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
        include_research_excerpts=True,
        include_validation_notes=True,
        obligation_reconciliation=unresolved,
    )
    assert r"\section{Issues found (diagnostic data)}" in rendered
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
        "biology": ("Introduction and biological context", "cross-species limits"),
        "mathematical": ("Introduction", "bridges between logical steps"),
        "military": ("Question and operational context", "alternative courses of action"),
    }
    for research_type, (heading, guidance) in expected.items():
        tex = papers._tex(draft(), [], "f" * 64, investigation_type=research_type)
        assert rf"\section{{{heading}}}" in tex
        # Writing instructions guide generation; they must not leak into the
        # reader-facing paper as a boilerplate paragraph.
        assert guidance in papers._paper_style(research_type)[3]
        assert guidance not in tex
    math_tex = papers._tex(draft(), [], "f" * 64, math_style=True, include_claim_details=True)
    assert r"\section{Introduction}" in math_tex
    assert r"\section{Claim and source notes}" in math_tex


def test_writing_source_selection_reuses_complete_prior_set_and_skips_failures() -> None:
    """Only resolved Project Types publication links may reach the paper writer."""
    from sigma import paper_writing_sources, project_types

    # Reference usage is user-scoped. This multi-source fixture must not
    # inherit the logged-in developer's enabled/disabled reference switches
    # or their private additions to the curated catalog.
    with (
        patch.object(project_types, "reference_preferences", return_value={}),
        patch.object(
            project_types,
            "common_custom_references",
            return_value={field: [] for field in project_types.REFERENCE_FIELDS},
        ),
        patch.object(project_types, "builtin_custom_references", return_value={}),
    ):
        common = project_types.common_references()["publication_standards_references"]
        resolved = project_types.get_type("mathematical")
    assert resolved is not None
    official = list(resolved.publication_standards_references)
    assert len(common) == 2
    assert len(official) == 3
    math_only = {item["url"] for item in official} - {item["url"] for item in common}
    assert math_only
    project = {
        "investigation_type": "mathematical",
        "title": "Nonconsecutive Subset Sums Modulo 3",
        "publication_references": official,
        "research_standards_references": [
            {
                "name": "Research should not be read as publication guidance",
                "url": "https://example.org/research-only",
            }
        ],
    }
    calls: list[str] = []

    async def fetch(url: str) -> str | None:
        calls.append(url)
        return "Readable, relevant scientific writing guidance. " * 20

    async def unavailable(_url: str) -> None:
        raise RuntimeError("unavailable writing source")

    async def check() -> None:
        chosen, status = await paper_writing_sources.select(project, fetch=fetch)
        assert status == "selected" and len(chosen) == 3
        assert {item["url"] for item in chosen} == {item["url"] for item in official}
        assert chosen[0]["url"] in math_only
        assert "https://example.org/research-only" not in calls
        assert all(len(item["excerpt"]) >= 450 for item in chosen)
        assert all(item["type"] == "mathematical" for item in chosen)

        count = len(calls)
        reused, mode = await paper_writing_sources.select(project, chosen, fetch=fetch)
        assert mode == "reused" and reused == chosen and len(calls) == count

        tampered = [dict(item) for item in chosen]
        tampered[0]["sha256"] = "0" * 64
        updated, mode = await paper_writing_sources.select(project, tampered, fetch=fetch)
        assert mode == "selected" and updated == chosen

        changed = {
            **project,
            "publication_references": [
                *official,
                {"name": "New official journal", "url": "https://example.org/new-official-methods"},
            ],
        }
        count = len(calls)
        refreshed, mode = await paper_writing_sources.select(changed, chosen, fetch=fetch)
        assert mode == "selected" and len(calls) > count
        assert refreshed[0]["reference_set_sha256"] != chosen[0]["reference_set_sha256"]

        no_config, mode = await paper_writing_sources.select(
            {
                "investigation_type": "mathematical",
                "title": "No official references",
                "research_standards_references": official,
            },
            fetch=fetch,
        )
        assert mode == "unavailable" and no_config == []

        unavailable_items, mode = await paper_writing_sources.select(project, fetch=unavailable)
        assert mode == "unavailable" and unavailable_items == []

        # One inaccessible document cannot block valid writing guidance.
        async def partial_fetch(url: str) -> str | None:
            return None if url == official[0]["url"] else "Valid editorial guidance. " * 35

        partial, mode = await paper_writing_sources.select(project, fetch=partial_fetch)
        assert mode == "selected" and len(partial) == 2
        unchanged, mode = await paper_writing_sources.select(project, partial, fetch=unavailable)
        assert mode == "reused" and unchanged == partial

    asyncio.run(check())

    # The old catalog is absent, and explicit unsafe URLs are never contacted.
    assert not hasattr(paper_writing_sources, "CATALOG")
    for bad in (
        "http://127.0.0.1/internal",
        "http://169.254.169.254/latest/meta-data/",
        "http://[::1]/internal",
        "http://user:password@example.org/private",
        "http://example.org:8080/admin",
        "file:///etc/passwd",
        "https://example.org:abc/path",
        "https://example.org/path\nx",
    ):
        assert not paper_writing_sources._valid_public_url(bad)
    assert paper_writing_sources._valid_public_url("https://example.org/guide.pdf")


def test_literature_paper_prompts_are_literary_and_preserve_citations() -> None:
    """Both the long-form and single-shot writers use the built-in style/method lens."""
    heading, method_heading, result_heading, style = papers._paper_style("literature")
    assert heading == "Introduction and literary context"
    assert method_heading == "Interpretive approach and sources"
    assert result_heading == "Close readings and interpretations"
    assert "source-grounded literary interpretation" in style
    instructions = papers._subject_methodology("literature")
    assert "literary-critical essay, not a proof" in instructions
    assert "Quote a literary passage only when its actual words are present" in instructions
    assert "structured\nclaim IDs, evidence references" in instructions
    assert "External scholarship is citable only when actually" in instructions
    assert "Interpretive exploration is welcome" in instructions
    assert "Make important conjectural leaps visible in natural prose" in instructions
    assert 'repeatedly write "speculation" or "speculative"' in instructions
    assert "Never present\nimagined authorial intentions" in instructions
    assert "qualified, text-grounded" in style
    assert papers._subject_methodology("mathematical") == papers.MATHEMATICS_INSTRUCTIONS
    assert papers._subject_methodology("physics") == papers.PHYSICS_INSTRUCTIONS
    assert papers._subject_methodology("default") == ""


if __name__ == "__main__":
    from papers_split_runner import run

    run(1)
