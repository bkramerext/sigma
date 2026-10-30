"""Bounded paper evidence validation, rendering safety and durable version scenarios."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import cast
from unittest.mock import patch

import httpx
from pydantic import ValidationError

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


def test_strict_paper_response_schemas_require_every_property() -> None:
    response_models = (
        papers.PaperClaim,
        papers.PaperSection,
        papers.PaperDraft,
        papers.EvidenceNote,
        papers.OmittedEvidenceField,
        papers.EvidenceConflict,
        papers.EvidenceBatchResult,
        papers.LongSectionPlan,
        papers.LongPaperPlan,
        papers.LongSectionDraft,
    )

    def check(node: object, path: str) -> None:
        if not isinstance(node, dict):
            return
        properties = node.get("properties")
        if isinstance(properties, dict):
            assert node.get("additionalProperties") is False, path
            assert set(properties) == set(node.get("required", [])), path
            for name, child in properties.items():
                check(child, f"{path}.{name}")
        items = node.get("items")
        if isinstance(items, dict):
            check(items, f"{path}.items")
        definitions = node.get("$defs")
        if isinstance(definitions, dict):
            for name, child in definitions.items():
                check(child, f"{path}.$defs.{name}")
        for keyword in ("anyOf", "oneOf", "allOf"):
            variants = node.get(keyword)
            if isinstance(variants, list):
                for index, child in enumerate(variants):
                    check(child, f"{path}.{keyword}[{index}]")

    for response_model in response_models:
        check(response_model.model_json_schema(), response_model.__name__)


def test_unclassified_evidence_fields_are_conservatively_omitted() -> None:
    covered = "a" * 64
    unclassified = "b" * 64
    result = papers.EvidenceBatchResult(
        notes=[],
        conflicts_or_gaps=[],
        covered_field_refs=[covered],
        omitted_fields=[],
    )
    assert papers._complete_evidence_field_partition({covered, unclassified}, result) == 1
    assert result.covered_field_refs == [covered]
    assert len(result.omitted_fields) == 1
    assert result.omitted_fields[0].field_ref == unclassified
    assert "conservatively omitted" in result.omitted_fields[0].reason


def test_provider_validation_diagnostic_omits_rejected_values() -> None:
    try:
        papers.EvidenceBatchResult.model_validate(
            {
                "notes": [],
                "conflicts_or_gaps": [],
                "covered_field_refs": [],
                "omitted_fields": [],
                "private_unrecognized_field": "private-response-value",
            }
        )
    except ValidationError as exc:
        summary = papers._safe_schema_validation_summary(papers.EvidenceBatchResult, exc)
    else:
        raise AssertionError("Unexpected response fields must fail local validation")
    assert "extra_forbidden" in summary
    assert "<unknown>" in summary
    assert "private-response-value" not in summary
    assert "private_unrecognized_field" not in summary


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


def test_one_shot_and_long_paper_requests_report_mocked_schema_rejection_once() -> None:
    requests: list[dict] = []
    client_timeouts: list[float] = []

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

    def make_client(**kwargs):
        client_timeouts.append(kwargs["timeout"])
        return real_client(transport=httpx.MockTransport(handler), **kwargs)

    with patch(
        "sigma.papers.httpx.AsyncClient",
        side_effect=make_client,
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

    assert len(requests) == 2  # one attempt per path; no retry/fallback
    assert client_timeouts == [papers.CALL_SECONDS, papers.LONG_PAPER_STAGE_SECONDS]
    for request in requests:
        assert request["model"] == "gpt-6.1-sol"
        assert request["reasoning"] == {"effort": "high"}
        assert request["store"] is False
        assert request["max_output_tokens"] == 12000
        assert request["text"]["format"]["type"] == "json_schema"
        assert request["text"]["format"]["strict"] is True
        assert request["text"]["format"]["schema"]


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

        async def fake_provider(context, *_args):
            nonlocal provider_calls
            provider_calls += 1
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
            try:
                asyncio.run(papers.generate(str(path), credential["identity"], view.project.id))
            except ProjectError as exc:
                assert "fixture compiler unavailable" in str(exc)
            else:
                raise AssertionError("The injected compile failure must be surfaced")

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
                result = asyncio.run(
                    papers.generate(str(path), credential["identity"], view.project.id)
                )

        saved = papers.get_paper(str(path), result["paper_id"])
        assert provider_calls == 1
        assert compile_calls == 2
        assert saved["generation"]["provider_calls_attempted"] == 1
        assert saved["generation"]["provider_calls_lifetime_total"] == 1
        assert papers._load_work(str(path)) is None
        assert len(papers.list_papers(str(path))) == 1


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
                await progress("evidence", 1, 2)
                assert force_long_form is False
                assert len(expected_snapshot_sha256) == 64
                return {"paper_id": "fixture-paper"}

            with patch.object(papers, "generate", new=fake_generate):
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
                            covered_field_refs=[],
                            omitted_fields=[],
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
                        omitted_fields=[],
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

        async def run():
            return await papers._generate_long_draft(
                package,
                {"mode": "chatgpt", "identity": "fixture", "token": "unused"},
                config,
                state,
                lambda current: saved.append(json.loads(papers._json(current))),
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


def main() -> None:
    test_strict_paper_response_schemas_require_every_property()
    test_unclassified_evidence_fields_are_conservatively_omitted()
    test_provider_validation_diagnostic_omits_rejected_values()
    test_incomplete_chatgpt_paper_stream_is_rejected()
    test_long_tex_compiler_source_bound_is_configurable()
    test_one_shot_draft_is_reused_after_pdf_compilation_failure()
    test_snapshot_ignores_elapsed_projection_but_tracks_saved_evidence()
    test_api_paper_stream_reports_progress_and_completion()
    test_long_index_reduction_resumes_and_preserves_session_conflicts()
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
    assert integrity_tex.index("Important evidence coverage limitation") < integrity_tex.index(
        r"\section{Problem framing}"
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
    assert about_start < tex.index(r"\section{Problem framing}")
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
    assert r"\section{Introduction}" in math_tex
    assert r"\section{Evidence and scope}" in math_tex
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
    print("Paper snapshots, citation validation, version retention and bounded rendering passed.")


if __name__ == "__main__":
    main()
