# ruff: noqa: F401, F821
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


def main_part1() -> None:
    test_review_proofreader_accepts_safe_patch_but_rejects_mutation()
    test_review_fallback_question_and_tex_safety()
    test_publication_preserves_failed_final_skeptic_as_research_limitation()
    test_review_fallback_rejects_process_text_as_claim()
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
    test_fallback_planner_ranks_complete_research_notes_over_operational_fields()
    test_frozen_snapshot_generation_gate_checks_identity_hash_and_source_uniqueness()
    test_invalid_planning_claim_reference_is_recoverable()
    test_repair_paper_references_preserves_science_and_downgrades_unsupported_claims()
    test_repair_coalesces_only_exact_duplicate_propositions()
    test_one_shot_publishes_with_repaired_claim_links()
    test_live_research_change_does_not_discard_completed_paper()
    test_frozen_evidence_checkpoint_survives_live_research_drift()
    test_one_shot_validation_failure_preserves_paid_draft_for_continue()
    test_long_paper_planning_timeout_is_stage_specific()
    test_structured_evidence_short_tail_does_not_crash()
    test_readable_paper_download_names_keep_stable_versions_and_server_headers()
    test_unexpected_paper_exception_yields_sanitized_sse_error()
    test_paper_sse_accepts_standard_line_endings_across_byte_chunks()
    test_paper_terminal_sse_event_without_final_separator()
    test_incomplete_chatgpt_paper_stream_is_rejected()
    test_api_provider_failure_classification_is_safe_and_actionable()
    test_chatgpt_schema_rejection_is_actionable_and_redacted()
    test_visual_preference_controls_one_shot_and_long_paper_wire_schemas()
    test_strict_paper_schemas_require_all_properties()
    test_paper_stage_accepts_completed_chatgpt_stream_with_trailing_usage()
    test_paper_sse_bounds_generated_text_not_redundant_transport()
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
    test_math_and_physics_methodology_reaches_every_authoring_path()
    test_writing_source_selection_reuses_complete_prior_set_and_skips_failures()
    test_paper_pdf_source_reader_accepts_only_substantial_extractable_text()
    test_writing_guidance_is_listed_in_paper_tex_without_becoming_evidence()
    test_fast_long_draft_safe_retry_and_unknown_consumption_checkpoint()
    test_transient_paper_failures_keep_other_sections_and_publish_labeled_fallback()
    test_paper_transient_error_classification_excludes_permanent_rejections()
    test_failed_planning_checkpoint_continues_without_repeating_paid_plan()
    test_paper_failure_reason_survives_reopen()
    test_paper_progress_counts_keep_generation_resumable()
    test_fast_long_draft_concurrency_ordered_checkpoints_and_resume()
    test_parallel_section_failure_drains_dispatched_siblings()
    test_fast_checkpoint_resume_replays_only_incomplete_section()
    test_fast_long_draft_cancellation_keeps_completed_sections()
    test_paper_generation_rejects_concurrent_duplicate_request()
    test_three_paper_generators_run_concurrently_and_fourth_fails_fast()
    test_three_papers_reach_compilation_together_and_hold_capacity()
    test_eight_research_sessions_overlap_three_paper_generators()
    test_tadpoles_five_session_mock_provider_to_pdf_timing()


def main_part2() -> None:
    with TemporaryDirectory() as temporary:
        cancelled_path = Path(temporary) / "cancelled.sigma"
        initialize_project(
            cancelled_path,
            "Cancelled paper",
            "A bounded saved question",
            research_mode="mathematical",
        )
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
    project_source = source_map["project:pid"]["data"]
    assert project_source["id"] == "pid" and project_source["title"] == "A project"
    assert project_source["publication_reference_urls"] == [
        reference["url"] for reference in project_source["publication_references"]
    ]
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
    outcome_tex = papers._tex(
        draft(),
        [],
        "c" * 64,
        integrity_records=[session_outcome],
        include_research_excerpts=True,
    )
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
    # Coverage is disclosed as short manuscript prose, not as a standalone
    # boilerplate section ahead of the research question.
    notice = "Unreviewed records could affect its conclusions"
    assert notice in integrity_tex
    methods_heading = papers._paper_style("default")[1]
    assert integrity_tex.index(r"\section{" + methods_heading + "}") < integrity_tex.index(notice)
    assert "Evidence coverage limitation" not in integrity_tex
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
    assert "Unreviewed records could affect its conclusions" in limited_math_tex
    assert "full omission ledger remains available with the generation record" in limited_math_tex
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
    # Frozen evidence is not artificially capped by provider input limits.
    assert large_snapshot["sources"][0]["data"]["problem"] == large_export["project"]["problem"]

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
        include_validation_notes=True,
    )
    assert r"\section{Issues found (diagnostic data)}" in reconciled_tex
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
    tex = papers._tex(parsed, warnings, "a" * 64, include_validation_notes=True)
    assert r"AI-generated research synthesis \textperiodcentered{} SIGMA" in tex
    assert r"\section*{Evidence and authorship note}" in tex
    assert r"Snapshot SHA-256:" in tex
    assert "This document is not independent verification." in tex
    assert tex.index(r"\section{" + papers._paper_style("default")[0] + "}") < tex.index(
        r"\section*{Evidence and authorship note}"
    )
    assert r"\frac{n(n+1)}{2}" in tex
    assert r"\textbackslash{}input" not in tex
    notation = papers._latex_prose(r"Let $R(\mathcal{A})$ denote the region count.")
    assert r"$R(\mathcal{A})$" in notation
    assert r"\textbackslash{}mathcal" not in notation
    # Render formulas from the reader-facing article, not from the opt-in
    # claim ledger. Claim reasoning is retained in the paper record.
    formula_draft = parsed.model_copy(
        update={
            "sections": [
                parsed.sections[0].model_copy(
                    update={
                        "paragraphs": [
                            (
                                r"The count is $R(n)=1+\sum_{j=1}^n j²$. "
                                r"The line family lies in $\mathbb{R}^2$."
                            )
                        ]
                    }
                ),
                *parsed.sections[1:],
            ],
            "claims": [
                parsed.claims[0].model_copy(
                    update={
                        "statement": r"The count is $R(n)=1+\sum_{j=1}^n j²$.",
                        "reasoning": r"The line family lies in $\mathbb{R}^2$.",
                    }
                )
            ],
        }
    )
    formula_tex = papers._tex(formula_draft, warnings, "a" * 64, math_style=True)
    assert r"\section{Claim and source notes}" not in formula_tex
    assert r"$R(n)=1+\sum_{j=1}^n j^{2}$" in formula_tex
    assert r"$\mathbb{R}^2$" in formula_tex
    assert r"\textbackslash{}sum" not in formula_tex
    assert r"\textbackslash{}mathbb" not in formula_tex
    unicode_superscript = papers._latex_prose("The saved construction uses j².")
    assert "$j^{2}$" in unicode_superscript
    math_tex = papers._tex(parsed, warnings, "a" * 64, math_style=True, include_claim_details=True)
    math_opening, math_methods, _, _ = papers._paper_style("mathematical")
    assert r"\section{" + math_opening + "}" in math_tex
    assert r"\section{" + math_methods + "}" in math_tex
    assert r"\section{Verification status and limitations}" in math_tex
    assert r"\section{Conclusion}" in math_tex
    assert math_tex.index(r"\section{Conclusion}") < math_tex.index(
        r"\section{Claim and source notes}"
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
        initialize_project(
            path, "Fixture", "Investigate the saved question", research_mode="mathematical"
        )
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
            research_mode="mathematical",
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
