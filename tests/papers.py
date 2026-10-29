"""Bounded paper evidence validation, rendering safety and durable version scenarios."""

from __future__ import annotations

import asyncio
import copy
import json
import shutil
from contextlib import nullcontext
from dataclasses import asdict
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter
from typing import Any, cast
from unittest.mock import patch

import httpx

from sigma import papers
from sigma.api import app
from sigma.plan_stream import completed, failure
from sigma.projects import ProjectError, initialize_project, inspect_project


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


def test_one_shot_and_long_paper_requests_report_mocked_schema_rejection_once() -> None:
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

    assert len(requests) == 3  # one attempt per path/stage; no retry/fallback
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
            return draft(project_source), config["model"]

        def fail_compile_once(_tex, **_kwargs):
            nonlocal compile_calls
            compile_calls += 1
            if compile_calls == 1:
                raise RuntimeError("fixture compiler unavailable")
            return b"%PDF-fixture"

        with (
            patch.object(papers, "auth_context", new=lambda: asyncio.sleep(0, result=credential)),
            patch.object(
                papers, "configuration", new=lambda **_kwargs: asyncio.sleep(0, result=config)
            ),
            patch.object(papers, "_provider", new=fake_provider),
            patch.object(papers, "_compile_pdf", new=fail_compile_once),
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
                        str(path), credential["identity"], view.project.id, progress=collect
                    )

                result = asyncio.run(resume())

        saved = papers.get_paper(str(path), result["paper_id"])
        assert provider_calls == 1
        assert compile_calls == 2
        assert saved["generation"]["provider_calls_attempted"] == 1
        assert saved["generation"]["provider_calls_lifetime_total"] == 1
        assert papers._load_work(str(path)) is None
        assert len(papers.list_papers(str(path))) == 1
        assert [event["stage"] for event in first_events if event["state"] == "active"] == [
            "snapshot",
            "writing",
            "validation",
            "compile",
        ]
        assert retry_events[-1]["stage"] == "complete" and retry_events[-1]["state"] == "complete"
        assert retry_events[-1]["elapsed_seconds"] >= first_events[-1]["elapsed_seconds"]


def test_snapshot_ignores_elapsed_projection_but_tracks_saved_evidence() -> None:
    export = {
        "project": {"id": "snapshot-project", "title": "Snapshot stability"},
        "research_sessions": [
            {
                "id": "paused-session",
                "status": "paused",
                "elapsed_seconds": 10,
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
        second, second_hash = papers._snapshot("unused")
        export["research_sessions"][0]["artifacts"][0]["claim"] = "Changed saved claim"
        _third, third_hash = papers._snapshot("unused")

    assert first_hash == second_hash
    assert third_hash != second_hash
    session_source = next(source for source in second["sources"] if source["kind"] == "session")
    assert "elapsed_seconds" not in session_source["data"]
    assert original["research_sessions"][0]["artifacts"][0]["claim"] == "Saved claim"
    assert first_claim == "Saved claim"


def test_api_disconnect_cancels_paper_before_publication(path: Path) -> None:
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
        assert papers.list_papers(str(path)) == []
        assert cancelled.is_set()
        assert not papers._gate.locked()

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
            ):
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
    assert seen == ["sigma_paper_evidence_batch", "sigma_long_paper_plan"]
    assert state["next_batch"] == 2
    assert state["provider_calls"] == 3  # Prior E1 + E2 + blocked planning attempt.


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
        with (
            patch.object(papers, "_long_plan_input", return_value={"padding": "x" * 220_000}),
            patch.object(
                papers,
                "_provider_structured",
                side_effect=AssertionError("oversized planning input must not dispatch"),
            ),
        ):
            try:
                await papers._generate_long_draft(
                    package,
                    {"mode": "api_key", "identity": "fixture", "token": "unused"},
                    {"model": "fixture", "reasoning_effort": "high"},
                    state,
                    lambda _state: None,
                )
            except ProjectError as exc:
                assert "Paper planning input" in str(exc), str(exc)
            else:
                raise AssertionError("Oversized planning input must be rejected")
        assert state["provider_calls"] == 0

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

        async def record_progress(stage, current, total, state) -> None:
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
                with patch.object(papers, "_compile_pdf", new=fail_compile_once):
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
        assert saved["generation"]["call_limit"] == papers.MAX_LONG_PAPER_CALLS
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


def test_research_type_specific_tex_sections_and_authoring_guidance() -> None:
    expected = {
        "biology": ("Introduction and biological context", "cross-species limitations"),
        "mathematical": ("Introduction", "bridges between logical steps"),
        "military": ("Question and operational context", "alternative interpretations"),
    }
    for research_type, (heading, guidance) in expected.items():
        tex = papers._tex(draft(), [], "f" * 64, investigation_type=research_type)
        assert rf"\section{{{heading}}}" in tex
        assert guidance in tex
    math_tex = papers._tex(draft(), [], "f" * 64, math_style=True)
    assert r"\section{Introduction}" in math_tex
    assert r"\section*{Claim status and evidence}" in math_tex


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

    async def progress(stage, current, total, activity):
        retry_progress.append((stage, current, total, activity))

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

    async def uncertain_provider(_input, _binding, _config, *, schema_name, **_kwargs):
        nonlocal uncertain_attempts
        uncertain_attempts += 1
        assert schema_name == "sigma_long_paper_plan"
        raise ProjectError("fixture post-dispatch timeout; consumption is unknown")

    async def check_uncertain() -> None:
        with patch.object(papers, "_provider_structured", new=uncertain_provider):
            try:
                await papers._generate_long_draft(
                    package,
                    {"identity": "fixture", "mode": "api_key", "token": "fixture"},
                    {"model": "fixture-model", "reasoning_effort": "high"},
                    uncertain_state,
                    lambda _value: None,
                    structured_fast_path=True,
                )
            except ProjectError as exc:
                assert "consumption is unknown" in str(exc)
            else:
                raise AssertionError("Unknown-consumption failures must remain visible")

    asyncio.run(check_uncertain())
    assert uncertain_attempts == 1
    assert uncertain_state["provider_calls"] == 1
    assert uncertain_state["provider_calls_total"] == 1
    assert uncertain_state["evidence_indexed"] is True


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
        async def progress(stage, current, total, activity):
            progress_events.append((stage, current, total, activity))

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
    state = papers._new_work("3" * 64, "fast-fixture", "4" * 64, "fixture-model", "high")
    attempts: list[tuple[str, int | None]] = []

    async def first_provider(input_value, _binding, _config, *, schema_name, **_kwargs):
        number = input_value.get("section_number")
        attempts.append((schema_name, number))
        if schema_name == "sigma_long_paper_plan":
            return plan, "fixture-model"
        if number == 1:
            return papers.LongSectionDraft(
                paragraphs=["This completed section is durable."]
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

    async def resume_provider(input_value, _binding, _config, *, schema_name, **_kwargs):
        number = input_value.get("section_number")
        assert schema_name == "sigma_long_paper_section" and number == 2
        attempts.append((schema_name, number))
        return papers.LongSectionDraft(
            paragraphs=["Only the incomplete section is retried."]
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
            )
        assert [section.paragraphs[0] for section in result.sections] == [
            "This completed section is durable.",
            "Only the incomplete section is retried.",
        ]
        assert calls == 4  # outline, completed section, uncertain failure, continuation
        assert batches == 0

    asyncio.run(resume())
    assert attempts.count(("sigma_long_paper_plan", None)) == 1
    assert attempts.count(("sigma_long_paper_section", 1)) == 1
    assert attempts.count(("sigma_long_paper_section", 2)) == 2
    assert set(state["section_drafts"]) == {"1", "2"}


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
            else patch.object(
                papers,
                "_compile_pdf",
                return_value=b"%PDF-1.4\\n" + b"% deterministic test fixture\\n" * 40,
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
        assert record["generation"]["provider_calls_attempted"] == 3
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
        assert len(mock_calls) == 3
        assert elapsed_seconds < 300
        compiler_label = (
            "real Tectonic compilation"
            if tectonic_available
            else "stub PDF (Tectonic unavailable)"
        )
        print(
            f"PASS mocked five-session Tadpoles paper-to-PDF E2E in {elapsed_seconds:.2f}s "
            f"({compiler_label}; deterministic provider; live <5-minute target remains unverified)."
        )



def test_long_paper_planning_timeout_is_stage_specific() -> None:
    """Only the complex planning call receives the longer provider allowance."""
    assert papers._long_paper_call_timeout("sigma_long_paper_plan") == 300
    assert papers._long_paper_call_timeout("sigma_long_paper_section") == papers.CALL_SECONDS
    assert papers._long_paper_call_timeout("sigma_paper_evidence_batch") == papers.CALL_SECONDS

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
    assert observed == [300, papers.CALL_SECONDS]



def main() -> None:
    test_long_paper_planning_timeout_is_stage_specific()
    test_structured_evidence_short_tail_does_not_crash()
    test_unexpected_paper_exception_yields_sanitized_sse_error()
    test_incomplete_chatgpt_paper_stream_is_rejected()
    test_api_provider_failure_classification_is_safe_and_actionable()
    test_chatgpt_schema_rejection_is_actionable_and_redacted()
    test_one_shot_and_long_paper_requests_report_mocked_schema_rejection_once()
    test_strict_paper_schemas_require_all_properties()
    test_paper_stage_accepts_completed_chatgpt_stream_with_trailing_usage()
    test_long_tex_compiler_source_bound_is_configurable()
    test_one_shot_draft_is_reused_after_pdf_compilation_failure()
    test_snapshot_ignores_elapsed_projection_but_tracks_saved_evidence()
    test_api_paper_stream_reports_progress_and_completion()
    test_paper_progress_endpoint_recovers_interrupted_checkpoint()
    test_restart_uses_current_evidence_and_is_idempotent()
    test_explicit_restart_checkpoint_migrates_and_rebinds_safely()
    test_evidence_envelope_budget_resumes_without_repacking()
    test_long_paper_outline_does_not_duplicate_large_evidence_reference_catalog()
    test_long_index_reduction_resumes_and_preserves_session_conflicts()
    test_structured_fast_index_preserves_math_review_and_bounds_omissions()
    test_research_type_specific_tex_sections_and_authoring_guidance()
    test_fast_long_draft_safe_retry_and_unknown_consumption_checkpoint()
    test_fast_long_draft_concurrency_ordered_checkpoints_and_resume()
    test_fast_checkpoint_resume_replays_only_incomplete_section()
    test_fast_long_draft_cancellation_keeps_completed_sections()
    test_paper_generation_rejects_concurrent_duplicate_request()
    test_tadpoles_five_session_mock_provider_to_pdf_timing()
    with TemporaryDirectory() as temporary:
        cancelled_path = Path(temporary) / "cancelled.sigma"
        initialize_project(cancelled_path, "Cancelled paper", "A bounded saved question")
        test_api_disconnect_cancels_paper_before_publication(cancelled_path)

    class StreamResponse:
        def __init__(self, content: bytes):
            self.headers = {"content-type": "text/event-stream"}
            self.content = content

        async def aiter_bytes(self):
            yield self.content

    large_event = (
        b'data: {"type":"response.created","sequence_number":0,"response":{"id":"r"},"padding":"'
        + b"x" * 1_100_000
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
    outcome_tex = papers._tex(draft(), [], "c" * 64, integrity_records=outcome_records)
    for outcome_text in (
        "Conditional conclusion",
        "The result holds under assumption A.",
        "The argument remains unverified.",
        "The base case is not included.",
        "Check the base case.",
        "Verify the base case.",
    ):
        assert outcome_text in outcome_tex

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
    )
    assert r"\section{Structured reasoning and review records}" in integrity_tex
    assert r"\section*{Important evidence coverage limitation}" in integrity_tex
    opening_heading = papers._paper_style("default")[0]
    assert integrity_tex.index("Important evidence coverage limitation") < integrity_tex.index(
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
    assert limited.claims[0].status == "unresolved"
    assert limited.abstract.startswith("IMPORTANT EVIDENCE COVERAGE LIMITATION:")
    assert original_abstract in limited.abstract
    assert "Provisional synthesis from covered evidence only" in limited.abstract
    assert "were not reviewed for this paper" in limited.abstract
    assert limited.conclusions[0].startswith("PROVISIONAL —")
    assert original_conclusions[0] in limited.conclusions[0]
    assert "omitted material was not reviewed" in limited.conclusions[0]
    assert "IMPORTANT EVIDENCE COVERAGE LIMITATION" in limited.limitations[0]
    assert "IMPORTANT EVIDENCE COVERAGE LIMITATION" in limited.validation_warnings[0]
    limited_math_tex = papers._tex(
        limited, [], "d" * 64, math_style=True, material_omissions=material
    )
    assert "C1 -- Unresolved" in limited_math_tex
    assert "Important evidence coverage limitation" in limited_math_tex
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
        assert record["tex_source"].count(r"\section*{About this paper}") == 1
        assert "AI-generated research synthesis" in record["tex_source"]
        assert record["generation"]["call_limit"] == 1
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
    main()
