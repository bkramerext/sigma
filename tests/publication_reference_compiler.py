"""Deterministic publication-reference compiler acceptance checks (Issue #487)."""

from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from sigma import paper_writing_sources, papers
from sigma import publication_reference_compiler as compiler
from sigma.projects import initialize_project


def _source(url: str, digest: str = "a" * 64) -> dict[str, str]:
    return {
        "title": "Editorial standards",
        "url": url,
        "tier": "discipline",
        "sha256": digest,
        "reference_set_sha256": "b" * 64,
        "excerpt": "Publication guidance. " * 35,
    }


def test_project_scoped_compilation_reuse_and_selection_invalidation() -> None:
    async def exercise(path: Path) -> None:
        sources = [_source("https://example.org/style"), _source("https://example.org/other")]
        invocations: list[str] = []

        async def compile_once(_sources, kind):
            invocations.append(kind)
            return {
                "retained_urls": [sources[0]["url"]],
                "omitted_urls": [sources[1]["url"]],
                "checklist": ["State the result and its limits in the abstract."],
                "rationale": "Second source is irrelevant.",
            }

        original = await compiler.ensure(path, "project-1", "mathematics", sources, compile_once)
        assert original["status"] == "completed"
        assert original["omitted_urls"] == [sources[1]["url"]]
        assert original["checklist_sha256"]
        assert compiler.guidance(original, sources) == [
            {"writing_guidance": "State the result and its limits in the abstract."}
        ]
        identical = await compiler.ensure(path, "project-1", "mathematics", sources, compile_once)
        assert identical == original
        assert invocations == ["mathematics"]

        revised = [dict(s) for s in sources]
        revised[0]["sha256"] = "c" * 64
        changed = await compiler.ensure(path, "project-1", "mathematics", revised, compile_once)
        assert changed["status"] == "completed"
        assert invocations == ["mathematics", "mathematics"]

        new_type = await compiler.ensure(path, "project-1", "physics", revised, compile_once)
        assert new_type["status"] == "completed"
        assert invocations == ["mathematics", "mathematics", "physics"]

        # An unchanged source list does not authorize checklist reuse when
        # the frozen paper goal or publication context changes.
        context = {"paper_goal": "Analyze the first question", "paper_format": "one_shot"}
        contextual = await compiler.ensure(
            path,
            "project-1",
            "physics",
            revised,
            compile_once,
            compilation_context=context,
        )
        assert contextual["status"] == "completed"
        assert len(invocations) == 4
        reused_context = await compiler.ensure(
            path,
            "project-1",
            "physics",
            revised,
            compile_once,
            compilation_context=context,
        )
        assert reused_context == contextual
        other_context = await compiler.ensure(
            path,
            "project-1",
            "physics",
            revised,
            compile_once,
            compilation_context={**context, "paper_goal": "Analyze a revised question"},
        )
        assert other_context["status"] == "completed"
        assert len(invocations) == 5

        # Selection changes invalidate even when fetching produces no excerpts.
        before = compiler.fingerprint("pid", "other", [], "a" * 64)
        after = compiler.fingerprint("pid", "other", [], "b" * 64)
        assert before != after

    with tempfile.TemporaryDirectory() as temp:
        asyncio.run(exercise(Path(temp) / "publication.json"))


def test_interrupted_attempt_never_replayed_and_falls_back_to_original_excerpts() -> None:
    async def exercise(path: Path) -> None:
        sources = [_source("https://example.org/style")]
        key = compiler.fingerprint("pid", "biology", sources)
        pending = {
            "schema": compiler.SCHEMA,
            "fingerprint": key,
            "status": "running",
            "retained_urls": [sources[0]["url"]],
            "omitted_urls": [],
            "checklist": [],
            "checklist_sha256": compiler._hash([]),
            "rationale": "",
            "started_at": "2026-11-02T00:00:00+00:00",
            "finished_at": None,
            "provider_calls_attempted": 1,
            "usage_status": "pending",
            "provider_usage": None,
        }
        compiler.save(path, pending)

        async def forbidden(*_args):
            raise AssertionError("Previously dispatched compilation was replayed")

        recovered = await compiler.ensure(path, "pid", "biology", sources, forbidden)
        assert recovered["status"] == "fallback"
        assert recovered["failure_reason"] == "uncertain_dispatched_call"
        assert (
            compiler.guidance(recovered, sources)[0]["writing_guidance_excerpt"]
            == (sources[0]["excerpt"])
        )

    with tempfile.TemporaryDirectory() as temp:
        asyncio.run(exercise(Path(temp) / "publication.json"))


def test_compilation_failure_and_malformed_response_do_not_stop_paper() -> None:
    async def exercise(path: Path) -> None:
        sources = [_source("https://example.org/style")]

        async def failing(*_args):
            raise RuntimeError("provider unavailable")

        fallback = await compiler.ensure(path, "pid", "math", sources, failing)
        assert fallback["status"] == "fallback"
        assert fallback["failure_reason"] == "RuntimeError"
        assert compiler.guidance(fallback, sources)[0]["writing_guidance_excerpt"]

        async def invalid(*_args):
            return {
                "retained_urls": ["https://fake.invalid"],
                "omitted_urls": [],
                "checklist": ["Invalid origin"],
                "rationale": "",
            }

        malformed = await compiler.ensure(path, "pid", "physics", sources, invalid)
        assert malformed["status"] == "fallback"

        no_sources = await compiler.ensure(path, "pid", "physics", [], failing)
        assert no_sources["status"] == "skipped"
        assert no_sources["provider_calls_attempted"] == 0

    with tempfile.TemporaryDirectory() as temp:
        asyncio.run(exercise(Path(temp) / "publication.json"))


def test_all_sources_omitted_never_feed_writing_guidance() -> None:
    async def exercise(path: Path) -> None:
        sources = [_source("https://example.org/irrelevant")]

        async def discard_all(*_args):
            return {
                "retained_urls": [],
                "omitted_urls": [sources[0]["url"]],
                "checklist": ["Generic advice must not reach authoring."],
                "rationale": "Irrelevant publication standard.",
            }

        result = await compiler.ensure(path, "pid", "physics", sources, discard_all)
        assert result["status"] == "skipped"
        assert result["omitted_urls"] == [sources[0]["url"]]
        assert result["checklist"] == []
        assert compiler.guidance(result, sources) == []
        assert compiler.read(path, compiler.fingerprint("pid", "physics", sources)) == result

    with tempfile.TemporaryDirectory() as temp:
        asyncio.run(exercise(Path(temp) / "publication.json"))


def test_compiler_funding_guard_preserves_first_writer_call() -> None:
    async def exercise(path: Path) -> None:
        sources = [_source("https://example.org/style")]

        async def forbidden(*_args):
            raise AssertionError("Unfunded optional compilation dispatched")

        result = await compiler.ensure(
            path, "pid", "mathematics", sources, forbidden, allow_paid_call=False
        )
        assert result["status"] == "fallback"
        assert result["provider_calls_attempted"] == 0
        assert result["failure_reason"] == "insufficient_writing_headroom"
        assert compiler.read(path, compiler.fingerprint("pid", "mathematics", sources)) == result
        assert compiler.guidance(result, sources)[0]["writing_guidance_excerpt"]

    with tempfile.TemporaryDirectory() as temp:
        asyncio.run(exercise(Path(temp) / "publication.json"))


def test_tampered_checklist_is_not_accepted() -> None:
    async def exercise(path: Path) -> None:
        sources = [_source("https://example.org/style")]

        async def compile_once(*_args):
            return {
                "retained_urls": [sources[0]["url"]],
                "omitted_urls": [],
                "checklist": ["Use explicit limitations."],
                "rationale": "",
            }

        saved = await compiler.ensure(path, "pid", "math", sources, compile_once)
        saved["checklist"] = ["Fabricated item"]
        # Modify the on-disk bytes without letting save() recompute the seal.
        path.write_text(json.dumps(saved))
        assert compiler.read(path, compiler.fingerprint("pid", "math", sources)) is None

    with tempfile.TemporaryDirectory() as temp:
        asyncio.run(exercise(Path(temp) / "publication.json"))


def test_corrupt_cache_is_not_replayed_or_trusted() -> None:
    async def exercise(path: Path) -> None:
        sources = [_source("https://example.org/style")]
        calls = 0

        async def compile_once(*_args):
            nonlocal calls
            calls += 1
            return {
                "retained_urls": [sources[0]["url"]],
                "omitted_urls": [],
                "checklist": ["Report uncertainty."],
                "rationale": "Relevant style guidance.",
            }

        saved = await compiler.ensure(path, "pid", "physics", sources, compile_once)
        assert calls == 1
        assert saved["status"] == "completed"

        for tampered in (
            {**saved, "retained_urls": [], "omitted_urls": [sources[0]["url"]]},
            {**saved, "provider_usage": {"input_tokens": -1}},
        ):
            # Neither an altered classification nor malformed usage can
            # authorize an additional charge when the old call is uncertain.
            path.write_text(json.dumps(tampered))
            recovered = await compiler.ensure(path, "pid", "physics", sources, compile_once)
            assert recovered["status"] == "fallback"
            assert recovered["failure_reason"] == "invalid_saved_cache_no_replay"
            assert recovered["provider_calls_attempted"] == 1
            assert calls == 1
            # Recreate the original for the next corruption variant.
            compiler.save(path, saved)

        # A *valid* cache under a changed source selection may compile again.
        revised = [dict(sources[0], excerpt="New editorial guidance. " * 35)]
        changed = await compiler.ensure(path, "pid", "physics", revised, compile_once)
        assert changed["status"] == "completed"
        assert calls == 2
        assert compiler.fingerprint("pid", "physics", sources) != compiler.fingerprint(
            "pid", "physics", revised
        )

    with tempfile.TemporaryDirectory() as temp:
        asyncio.run(exercise(Path(temp) / "publication.json"))


def test_invalid_metering_does_not_corrupt_checkpoint_or_replay() -> None:
    async def exercise(path: Path) -> None:
        sources = [_source("https://example.org/style")]
        calls = 0

        async def compile_once(*_args):
            nonlocal calls
            calls += 1
            return {
                "retained_urls": [sources[0]["url"]],
                "omitted_urls": [],
                "checklist": ["Cite limitations."],
                "rationale": "Included.",
                "provider_usage": {
                    "input_tokens": 10,
                    "cached_input_tokens": 12,
                    "output_tokens": 20,
                    "estimated_cost_usd": 0.01,
                },
            }

        completed = await compiler.ensure(path, "pid", "physics", sources, compile_once)
        assert completed["status"] == "completed"
        assert completed["usage_status"] == "unknown"
        assert completed["provider_usage"] is None
        assert compiler.read(path, compiler.fingerprint("pid", "physics", sources)) == completed
        assert await compiler.ensure(path, "pid", "physics", sources, compile_once) == completed
        assert calls == 1

    with tempfile.TemporaryDirectory() as temp:
        asyncio.run(exercise(Path(temp) / "publication.json"))


def test_budget_floor_quotes_both_compiler_and_first_writer() -> None:
    """An optional compiler cannot consume the quoted first-writing floor."""
    package = {"sources": [{"id": "project:p", "kind": "project", "data": {}}]}
    funding = {
        "remaining_usd": 0.21,
        "global_remaining_usd": 0.21,
        "user_reserved_or_observed_tokens": 0,
    }

    def quote(_model, _input_bytes, output_tokens):
        return (0.10, 37_000) if output_tokens == 4_000 else (0.15, 236_000)

    with (
        patch.object(papers.cloud_research, "billing_enabled", return_value=True),
        patch.object(papers.cloud_research, "snapshot", return_value=funding),
        patch.object(papers.cloud_research, "standalone_call_reservation", side_effect=quote),
        patch.object(papers.cloud_research, "_admin_has_unlimited_spend", return_value=False),
        patch.object(papers.cloud_research, "_positive_int", return_value=300_000),
    ):
        assert not papers._publication_compiler_has_writing_headroom(
            "fixture-model", package, long_form=True
        )
        funding["remaining_usd"] = 0.40
        funding["global_remaining_usd"] = 0.40
        assert papers._publication_compiler_has_writing_headroom(
            "fixture-model", package, long_form=True
        )
        funding["user_reserved_or_observed_tokens"] = 50_000
        assert not papers._publication_compiler_has_writing_headroom(
            "fixture-model", package, long_form=True
        )


def test_mock_paper_author_receives_compiled_guidance_and_reuses_project_cache() -> None:
    """Exercise actual paper generation, TeX proofreading and version reuse offline."""

    async def run(root: Path) -> None:
        path = root / "publication-compiler.sigma"
        view = initialize_project(
            path,
            "Publication compiler",
            "A bounded offline writing test.",
            research_mode="mathematical",
        )
        credential = {"identity": "fixture:publication", "mode": "api_key", "token": "offline"}
        config = {
            "available": True,
            "binding": credential["identity"],
            "model": "gpt-6.1-sol",
            "reasoning_effort": "high",
        }
        selected = _source("https://example.org/editorial")
        selected["type"] = "mathematical"
        selected["branch"] = "project_type"
        selected["excerpt"] = "Original editorial advice. " * 35
        selected["sha256"] = compiler._hash(selected["excerpt"])
        checklist = "Make evidence limitations explicit in the conclusions."
        compiler_calls = 0
        interrupt_next_compiler = False
        writing_packets = []
        proofread_packets = []
        progress_stages = []
        persisted_checkpoints = []
        real_save_work = papers._save_work

        def save_and_verify_checkpoint(project_path, state):
            # Every persisted checkpoint must be readable on a fresh process.
            assert state.get("schema_version") == 2
            assert state.get("project_id") == view.project.id
            assert state.get("frozen_package")
            real_save_work(project_path, state)
            reloaded = papers._load_work(project_path)
            assert reloaded is not None
            assert reloaded["snapshot_sha256"] == state["snapshot_sha256"]
            persisted_checkpoints.append(reloaded)

        async def select_sources(*_args, **_kwargs):
            return [dict(selected)], "selected"

        async def fake_structured(
            value, _binding, _config, *, schema_name, response_model, **_kwargs
        ):
            nonlocal compiler_calls, interrupt_next_compiler
            if schema_name == "sigma_publication_reference_compilation":
                compiler_calls += 1
                assert response_model is papers.PublicationChecklist
                assert value["publication_sources"][0]["url"] == selected["url"]
                assert value["publication_context"]["paper_goal"] == (
                    "A bounded offline writing test."
                )
                assert value["publication_context"]["paper_format"] == "one_shot"
                if interrupt_next_compiler:
                    interrupt_next_compiler = False
                    raise asyncio.CancelledError
                return papers.PublicationChecklist(
                    retained_urls=[selected["url"]],
                    omitted_urls=[],
                    checklist=[checklist],
                    rationale="Relevant editorial guidance.",
                ), config["model"]
            assert response_model is papers.TeXProofreadResult
            assert schema_name == "sigma_tex_proofread_patches"
            proofread_packets.append(value["editorial_checklist"])
            return papers.TeXProofreadResult(corrections=[]), config["model"]

        async def fake_author(packet, *_args):
            writing_packets.append(packet["paper_writing_methodology"])
            project_ref = next(
                source["id"] for source in packet["sources"] if source["kind"] == "project"
            )
            return papers.PaperDraft.model_validate(
                {
                    "title": "A bounded editorial test",
                    "abstract": (
                        "The project has a defined objective but no independently verified "
                        "scientific findings; this paper records the saved objective, explains "
                        "the evidence boundary, and identifies next steps."
                    ),
                    "abstract_claim_ids": ["C1"],
                    "problem_framing": ["This paper covers the frozen objective."],
                    "problem_framing_claim_ids": ["C1"],
                    "methods": ["We inspected the saved objective."],
                    "methods_claim_ids": ["C1"],
                    "claims": [
                        {
                            "id": "C1",
                            "statement": "The project records an objective.",
                            "status": "established",
                            "evidence_refs": [project_ref],
                            "reasoning": "The objective appears in the saved project.",
                        }
                    ],
                    "sections": [
                        {
                            "heading": "Evidence",
                            "paragraphs": ["Only the objective was saved."],
                            "claim_ids": ["C1"],
                        },
                        {
                            "heading": "Limits",
                            "paragraphs": ["No independent result was established."],
                            "claim_ids": ["C1"],
                        },
                    ],
                    "limitations": ["No verified experiment or proof was recorded."],
                    "open_obligations": ["Perform a full investigation."],
                    "conclusions": ["The project has an objective, not a conclusion."],
                    "conclusion_claim_ids": ["C1"],
                    "validation_warnings": [],
                }
            ), config["model"]

        async def collect(event):
            progress_stages.append(event["stage"])

        with (
            patch.object(
                papers,
                "auth_context",
                new=lambda: asyncio.sleep(0, result=credential),
            ),
            patch.object(
                papers,
                "configuration",
                new=lambda **_kw: asyncio.sleep(0, result=config),
            ),
            patch.object(papers.paper_writing_sources, "select", new=select_sources),
            patch.object(papers, "_provider_structured", new=fake_structured),
            patch.object(papers, "_provider", new=fake_author),
            patch.object(papers, "_save_work", new=save_and_verify_checkpoint),
            patch.object(papers, "_compile_pdf", new=lambda *_a, **_kw: b"%PDF-fixture"),
            patch.object(papers, "_pdf_text_bounds_diagnostics", return_value=(1, [])),
        ):
            first = await papers.generate(
                str(path),
                credential["identity"],
                view.project.id,
                progress=collect,
                include_research_details=True,
                include_validation_notes=True,
            )
            saved = papers.get_paper(str(path), first["paper_id"])
            assert saved["generation"]["publication_compilation"]["status"] == "completed"
            assert saved["generation"]["publication_compiler_calls"] == 1
            assert saved["generation"]["publication_references_used"][0]["url"] == selected["url"]
            assert selected["url"] in saved["tex_source"]
            assert r"\section{Publication references used}" in saved["tex_source"]
            assert writing_packets[-1] == [{"writing_guidance": checklist}]
            assert proofread_packets and all(
                packet == [{"writing_guidance": checklist}] for packet in proofread_packets
            )
            assert progress_stages.index("publication_compilation") < progress_stages.index(
                "writing"
            )

            # Same selected material is a project-wide cache hit for a new paper.
            second = await papers.generate(
                str(path),
                credential["identity"],
                view.project.id,
                include_research_details=True,
                include_validation_notes=True,
            )
            after_reuse = papers.get_paper(str(path), second["paper_id"])
            assert after_reuse["generation"]["publication_compiler_calls"] == 0
            assert compiler_calls == 1
            assert writing_packets[-1] == [{"writing_guidance": checklist}]

            # Changed selection must compile anew, not replay stale guidance.
            selected["url"] = "https://example.org/revised"
            selected["excerpt"] = "Updated editorial instructions. " * 35
            selected["sha256"] = compiler._hash(selected["excerpt"])
            third = await papers.generate(
                str(path),
                credential["identity"],
                view.project.id,
                include_research_details=True,
                include_validation_notes=True,
            )
            changed = papers.get_paper(str(path), third["paper_id"])
            assert changed["generation"]["publication_compiler_calls"] == 1
            assert changed["generation"]["publication_references_used"][0]["url"] == selected["url"]
            assert compiler_calls == 2
            assert persisted_checkpoints, "No durable paper checkpoints were written"

            # An interrupted compiler is NOT replayed. The saved work stays
            # readable and Continue falls back to original editorial excerpts.
            selected["url"] = "https://example.org/next"
            selected["excerpt"] = "Fallback original editorial evidence. " * 35
            selected["sha256"] = compiler._hash(selected["excerpt"])
            interrupt_next_compiler = True
            try:
                await papers.generate(
                    str(path),
                    credential["identity"],
                    view.project.id,
                    include_research_details=True,
                    include_validation_notes=True,
                )
            except asyncio.CancelledError:
                pass
            else:
                raise AssertionError("Expected cancellation during publication compilation")
            interrupted = papers._load_work(str(path))
            assert interrupted is not None
            assert interrupted["provider_calls"] == 0
            assert interrupted["publication_compiler_calls"] == 1
            assert interrupted["writing_sources"][0]["url"] == selected["url"]
            assert compiler_calls == 3
            # Damage in optional compiler metadata must not erase valid
            # authored work or the conservative dispatch counter.
            interrupted["publication_compilation"] = {
                "fingerprint": "corrupted",
                "status": "completed",
            }
            papers._save_work(str(path), interrupted)
            sanitized = papers._load_work(str(path))
            assert sanitized is not None
            assert "publication_compilation" not in sanitized
            assert sanitized["publication_compiler_calls"] == 1
            # Simulate cache loss after the provider may already have received
            # the request. The independent paper checkpoint must prohibit replay.
            compiler_cache_path = (
                papers._paper_dir(str(path)) / ".publication-reference-compilation.json"
            )
            assert compiler_cache_path.is_file()
            compiler_cache_path.unlink()
            recovered = await papers.generate(
                str(path),
                credential["identity"],
                view.project.id,
                include_research_details=True,
                include_validation_notes=True,
            )
            resumed = papers.get_paper(str(path), recovered["paper_id"])
            assert resumed["generation"]["publication_compilation"]["status"] == "fallback"
            assert resumed["generation"]["publication_compilation"]["failure_reason"] == (
                "uncertain_previous_attempt_cache_missing"
            )
            assert resumed["generation"]["publication_compiler_calls"] == 1
            assert compiler_calls == 3, "Uncertain compilation was replayed"
            assert writing_packets[-1][0]["writing_guidance_excerpt"] == selected["excerpt"]

    with tempfile.TemporaryDirectory() as temp:
        asyncio.run(run(Path(temp)))


def test_large_frozen_snapshot_preserves_complete_evidence() -> None:
    """The complete archive survives restart without ballooning checkpoint files."""
    from hashlib import sha256
    from uuid import uuid4

    evidence = "E" * 33_349_757
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "large-evidence.sigma"
        view = initialize_project(path, "Large archive", "Retain all research.")
        package = {
            "schema": "sigma-paper-evidence-v2",
            "project_id": view.project.id,
            "sources": [
                {
                    "id": f"project:{view.project.id}",
                    "kind": "project",
                    "data": {"title": "Large archive"},
                },
                {"id": "session:long", "kind": "session", "data": {"evidence": evidence}},
            ],
        }
        encoded = papers._json(package)
        assert len(encoded) > 20_000_000
        _, digest = papers._validate_frozen_snapshot(package, view.project.id)
        assert digest == sha256(encoded).hexdigest()
        work = papers._new_work(
            digest, view.project.id, sha256(b"binding").hexdigest(), "model", "high"
        )
        work["frozen_package"] = package
        papers._save_work(str(path), work)
        assert papers._work_file(str(path), create=False).stat().st_size < 100_000
        restored = papers._load_work(str(path))
        assert restored is not None
        assert restored["frozen_package"] == package
        assert restored["frozen_package_ref"] == digest

        record = {
            "paper_id": uuid4().hex,
            "paper_version": 1,
            "project_id": view.project.id,
            "snapshot_sha256": digest,
            "snapshot": package,
        }
        papers._save(str(path), record, b"%PDF-fixture")
        assert (papers._paper_dir(str(path)) / f"{record['paper_id']}.json").stat().st_size < (
            100_000
        )
        saved = papers._read_one(str(path), record["paper_id"])
        assert saved["snapshot"] == package
        assert saved["snapshot_ref"] == digest

        archive = papers._snapshot_archive_file(str(path), digest, create=False)
        archive.write_bytes(b"invalid compressed archive")
        try:
            papers._read_one(str(path), record["paper_id"])
        except papers.ProjectError as exc:
            assert "archive" in str(exc)
        else:
            raise AssertionError("Corrupted frozen evidence was accepted")


def test_unavailable_publication_links_have_a_total_time_budget() -> None:
    """A long list of 403/404 references must not stall paper preparation."""
    urls = [
        {"name": f"Unreachable guide {index}", "url": f"https://example.org/guide-{index}"}
        for index in range(30)
    ]
    attempted: list[str] = []

    async def unavailable(url: str) -> None:
        attempted.append(url)
        return None

    async def exercise() -> None:
        with patch.object(
            paper_writing_sources, "monotonic", side_effect=[0.0, 1.0, 12.1]
        ):
            selected, status = await paper_writing_sources.select(
                {"publication_references": urls, "investigation_type": "engineering"},
                fetch=unavailable,
            )
        assert selected == [] and status == "unavailable"
        assert len(attempted) == 1

    asyncio.run(exercise())


if __name__ == "__main__":
    test_unavailable_publication_links_have_a_total_time_budget()
    test_large_frozen_snapshot_preserves_complete_evidence()
    test_project_scoped_compilation_reuse_and_selection_invalidation()
    test_interrupted_attempt_never_replayed_and_falls_back_to_original_excerpts()
    test_compilation_failure_and_malformed_response_do_not_stop_paper()
    test_tampered_checklist_is_not_accepted()
    test_all_sources_omitted_never_feed_writing_guidance()
    test_compiler_funding_guard_preserves_first_writer_call()
    test_corrupt_cache_is_not_replayed_or_trusted()
    test_invalid_metering_does_not_corrupt_checkpoint_or_replay()
    test_mock_paper_author_receives_compiled_guidance_and_reuses_project_cache()
    test_budget_floor_quotes_both_compiler_and_first_writer()
    print("Publication-reference compiler persistence, reuse, recovery and validation passed.")
