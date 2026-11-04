# ruff: noqa: F401, F821
# pyright: reportUndefinedVariable=false
"""Persistent A17 sessions use deterministic provider fixtures only."""

import asyncio
import json
import os
import shutil
import subprocess
import sys
import time
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from html import escape
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import httpx

from sigma import agentic, papers, proposals, python_sandbox, research_sessions, text_views
from sigma.projects import (
    ProjectError,
    create_strategy,
    edit_strategy,
    initialize_project,
    inspect_project,
    project_path,
    set_strategy_enabled,
    update_project,
)
from sigma.research_budget import (
    BudgetExceeded,
    authorize_independent_review_after_unknown,
    increase_call_limit,
    mark_unknown,
    new_ledger,
    reserve_before_dispatch,
    settle_after_response,
    settle_rejected,
    totals,
)

# Legacy role-only fixtures deliberately leave the new compiler off.
# tests/reference_compiler_integration.py explicitly enables and tests it.
os.environ.setdefault("SIGMA_REFERENCE_COMPILATION_ENABLED", "false")

MODEL = "gpt-6.1-sol"
REAL_CLIENT = httpx.AsyncClient


def main(part: int = 1):
    # The project test driver invokes provider-free scientific Outcome
    # regressions directly; this repository does not use pytest discovery.
    import test_outcome_policy

    if part == 1:
        for name, check in vars(test_outcome_policy).items():
            if name.startswith("test_") and callable(check):
                check()
    test_paired_round_defaults_and_enabled_call_ceiling()
    test_paired_round_positions_are_explicit_and_legacy_is_unchanged()
    test_paired_round_protocol_requires_every_accepted_role()
    test_paired_round_pipeline_orders_roles_without_paid_calls()
    test_paired_round_scheduler_budget_rotates_and_keeps_partial_pairs()
    print("PASS five paired-round scheduler regressions (no provider calls)")
    print("PASS provider-free scientific Outcome policy regressions")
    test_reference_compilation_is_bounded_and_source_attributed()
    test_backend_build_is_pinned_at_backend_start()
    test_project_cost_denial_reports_affordable_first_call()
    test_outcome_includes_derived_execution_provenance()
    test_cost_limit_outcome_preserves_partial_cycle_reason()
    test_unknown_provider_attempt_keeps_held_session_cost()
    test_sponsored_unlimited_cost_still_reserves_global_call_spend()
    test_rejected_call_releases_hard_tokens_but_counts_attempt()
    test_transient_provider_failure_classes_are_bounded_and_permanent_errors_not_retried()
    test_portfolio_termination_does_not_promote_scheduler_terminal_to_research_success()
    test_sponsorship_does_not_shorten_project_duration()
    test_context_manifest_compaction_preserves_omission_accounting()
    test_obligation_dispatch_citations_exclude_withheld_history()
    test_obligation_dispatch_request_contains_only_supplied_citations()
    test_terminal_protocol_completion_plan_preserves_attempt_history()
    test_e004_e005_e006_e009_e010_e011_saved_protocol_recovery_plans()
    test_protocol_completion_rejects_invalid_or_duplicate_accepted_slots()
    test_terminal_protocol_completion_allows_known_invalid_response_replacement()
    test_protocol_recovery_context_is_a_new_final_provider_input()
    with TemporaryDirectory() as temporary:
        asyncio.run(
            test_provider_limit_unsafe_fallback_cannot_resume(
                Path(temporary) / "unsafe-provider-fallback.sigma"
            )
        )
        asyncio.run(
            test_restart_missing_provider_reservation_is_durably_blocked(
                Path(temporary) / "missing-provider-reservation.sigma"
            )
        )
        asyncio.run(
            test_restart_matching_provider_reservation_is_recoverable(
                Path(temporary) / "matching-provider-reservation.sigma"
            )
        )
        asyncio.run(
            test_explicit_budget_and_duration_consent_preserves_saved_state(
                Path(temporary) / "explicit-recovery-consent.sigma"
            )
        )
        asyncio.run(
            test_terminal_time_expiry_requires_separate_confirmation(
                Path(temporary) / "expired-session-consent.sigma"
            )
        )
        asyncio.run(
            test_terminal_protocol_resume_extends_only_exact_shortfall(
                Path(temporary) / "protocol-resume.sigma"
            )
        )
        asyncio.run(
            test_legacy_compiler_checkpoint_resumes_after_account_change(
                Path(temporary) / "legacy-compiler-resume.sigma"
            )
        )
        asyncio.run(
            test_resume_repeated_unknown_provider_failures_retains_session(
                Path(temporary) / "repeated-provider-resume.sigma"
            )
        )
        asyncio.run(
            test_e009_stopped_unknown_investigator_explicit_repair(
                Path(temporary) / "unknown-investigator-repair.sigma"
            )
        )
        asyncio.run(
            test_terminal_protocol_resume_extends_only_exact_shortfall(
                Path(temporary) / "protocol-unknown-resume.sigma", unknown_skeptic=True
            )
        )
    test_context_compaction_preserves_obligation_count_for_portfolio_dispatch()
    test_dispatch_budget_compacts_historical_evidence_not_live_inputs()
    # Explicit driver; this repository does not discover tests with pytest.
    import test_crucible_context_budget

    if part == 1:
        for name, check in vars(test_crucible_context_budget).items():
            if name.startswith("test_") and callable(check):
                check()
    test_rate_limit_retry_observes_provider_retry_after_and_minimum_backoff()
    test_parallel_funding_uses_estimates_without_changing_provider_request()
    test_portfolio_capacity_tracks_strategies_not_billing_mode()
    test_epistemic_presentation_is_conservative_and_read_only()
    test_source_readiness_distinguishes_content_from_verification()
    test_saved_followup_question_selection()
    test_request_audit_truncation_tokens_and_reconciliation()
    with TemporaryDirectory() as temporary:
        root = Path(temporary)
        asyncio.run(
            test_unlimited_duration_completes_without_session_deadline(root / "unlimited.sigma")
        )
        asyncio.run(test_transient_timeout_retries_as_a_new_accounted_turn(root / "retry.sigma"))
        asyncio.run(
            test_repeated_transient_failures_are_isolated_and_explained(root / "repeat.sigma")
        )
        asyncio.run(
            test_last_affordable_provider_failure_names_failure_and_exhaustion(
                root / "last-turn.sigma"
            )
        )
        asyncio.run(
            test_last_shared_turn_failure_survives_terminal_sibling_finalization(
                root / "last-shared-turn-multistrategy.sigma"
            )
        )
        asyncio.run(
            test_expired_deadline_preserves_sibling_partial_artifacts(
                root / "deadline-scheduler.sigma"
            )
        )
        asyncio.run(test_portfolio_retry_wrapper_has_a_hard_attempt_bound())
        test_project_concurrency_max_four_and_legacy_read(root)
        asyncio.run(test_disabled_strategy_never_starts_a_run(root / "disabled.sigma"))
        asyncio.run(
            test_project_concurrent_session_limit_is_atomic(root / "concurrency-limit.sigma")
        )
        asyncio.run(test_distinct_portfolio_sessions_dispatch_simultaneously(root))
        asyncio.run(
            test_stop_one_session_does_not_cancel_sibling_and_resume_keeps_work(
                root / "sibling-stop-resume.sigma"
            )
        )
        asyncio.run(
            test_foreign_worker_lock_blocks_resume_and_removal(root / "foreign-worker-owner.sigma")
        )
        asyncio.run(test_three_cycles_and_idempotency(root / "cycles.sigma"))
        asyncio.run(
            test_legacy_worker_aggregates_usage_and_audits_inputs(root / "legacy-worker.sigma")
        )
        asyncio.run(
            test_legacy_background_disconnect_after_gate_wait(root / "legacy-presence.sigma")
        )
        asyncio.run(test_investigator_python_is_run_and_reviewed(root / "python-review.sigma"))
        asyncio.run(test_recovery_reuses_saved_python_execution(root / "python-recovery.sigma"))
        asyncio.run(test_restart_during_python_has_no_automatic_rerun(root / "python-crash.sigma"))
        asyncio.run(test_failed_experiment_is_reused_then_revised(root / "python-revision.sigma"))
        asyncio.run(test_portfolio_python_queue_and_stop(root / "python-queue.sigma"))
        asyncio.run(
            test_stop_during_python_execution_preserves_provenance(root / "python-stop.sigma")
        )
        asyncio.run(test_new_session_receives_prior_saved_findings(root / "continuation.sigma"))
        asyncio.run(
            test_saved_followup_question_reaches_real_dispatch(
                root / "saved-question-continuation.sigma"
            )
        )
        asyncio.run(test_cross_domain_continuation_dispatch_with_offline_roles(root))
        asyncio.run(
            test_failed_attempt_guides_next_session_with_provenance(
                root / "failed-continuation.sigma"
            )
        )
        test_prior_session_failure_history_prioritizes_newest_attempts(
            root / "failure-recency.sigma"
        )
        test_continuation_context_is_bounded(root / "continuation-stress.sigma")
        test_t37_context_selection_is_stable_and_loss_visible(root / "t37-context.sigma")
        test_project_compact_obligation_ids_preserve_legacy_references(
            root / "compact-obligation-ids.sigma"
        )
        test_t37_obligation_identity_lifecycle_and_history(root / "t37-obligation-review.sigma")
        asyncio.run(test_t37_mandatory_context_blocks_before_provider(root / "t37-blocked.sigma"))
        asyncio.run(test_pause_counts_interrupted_call(root / "pause.sigma"))
        test_protocol_completion_label_requires_every_configured_role_turn()
        test_worker_cancel_before_dispatch_does_not_claim_provider_call()
        test_worker_cancel_with_running_call_preserves_dispatch_uncertainty()
        asyncio.run(test_malformed_output_and_restart(root / "recovery.sigma"))
        asyncio.run(
            test_clipped_investigator_automatically_recovers(root / "clipped-auto-recovery.sigma")
        )
        asyncio.run(
            test_legacy_ended_clipped_response_can_resume(root / "clipped-legacy-resume.sigma")
        )
        asyncio.run(test_chatgpt_stream(root / "chatgpt.sigma"))
        asyncio.run(
            test_portfolio_stops_after_chatgpt_usage_limit(root / "chatgpt-http-limit.sigma")
        )
        asyncio.run(
            test_portfolio_stops_after_chatgpt_usage_limit(
                root / "chatgpt-sse-limit.sigma", streamed=True
            )
        )
        asyncio.run(
            test_portfolio_stops_after_chatgpt_usage_limit(
                root / "chatgpt-sse-error-event.sigma", streamed=True, sse_error_event=True
            )
        )
        asyncio.run(
            test_chatgpt_usage_limit_recovers_only_after_explicit_resume(
                root / "chatgpt-limit-resume.sigma"
            )
        )
        asyncio.run(
            test_invalid_completed_response_is_not_marked_dispatch_unknown(
                root / "invalid-completed-response.sigma"
            )
        )
        test_provider_limit_v2_40_of_54_offers_ordinary_resume_and_correct_progress()
        asyncio.run(
            test_provider_limit_recovery_completes_full_v2_protocol(
                root / "provider-limit-full-recovery.sigma"
            )
        )
        test_provider_limit_recovery_requires_known_dispatch_and_enough_turns()
        asyncio.run(
            test_session_deadline_bounds_generous_call_timeout(
                root / "generous-call-deadline.sigma"
            )
        )
        asyncio.run(test_limits_snapshot_and_usage_cost(root / "limits.sigma"))
        asyncio.run(
            test_prior_obligation_reference_compaction_keeps_text_and_traceability(
                root / "prior-obligation-compaction.sigma"
            )
        )
        asyncio.run(
            test_aggregate_prior_obligation_snapshot_retains_all_under_64kb(
                root / "prior-obligation-aggregate.sigma"
            )
        )
        asyncio.run(
            test_prior_obligation_overflow_allows_repeatable_bounded_research(
                root / "prior-obligation-overflow.sigma"
            )
        )
        test_limits_validation(root / "invalid-limits.sigma")
        test_contradictory_skeptic_counterexample_does_not_cancel_continuation()
        test_coordinator_obligations_do_not_multiply_across_rounds()
        test_shared_turn_schedule_accepts_strategy_count_changes()
        asyncio.run(
            test_pending_skeptic_uses_final_turn_and_deferred_outcome_is_specific(
                root / "portfolio-final-skeptic-turn.sigma"
            )
        )
        asyncio.run(
            test_adversarial_achieved_reviews_never_publish_unsupported_solution(
                root / "adversarial-achievement.sigma"
            )
        )
        asyncio.run(test_legacy_limits_are_preserved(root / "legacy-limits.sigma"))
        asyncio.run(test_single_project_admission(root / "single-session.sigma"))
        asyncio.run(
            test_remove_running_session_cancels_execution_and_releases_slot(
                root / "remove-running.sigma"
            )
        )
        asyncio.run(
            test_remove_racing_with_completion_is_idempotently_terminal(
                root / "remove-completion-race.sigma"
            )
        )
        asyncio.run(
            test_project_deletion_stops_all_active_sessions_first(
                root / "project-delete-active.sigma"
            )
        )
        asyncio.run(test_response_transport_and_parsed_bounds(root / "parsed.sigma"))
        asyncio.run(
            test_project_edits_do_not_pause_research_but_account_changes_do(root / "binding.sigma")
        )
        asyncio.run(test_storage_limit_pauses_without_artifact(root / "storage.sigma"))
        asyncio.run(test_remove_terminal_and_monotonic_number(root / "removal.sigma"))
        test_deliberate_argument_gap_is_preserved_and_not_complete()
        test_e1_peer_inspection_does_not_hide_complete_unverified_candidate()
        asyncio.run(
            test_maximum_regions_solution_and_frozen_attribution(root / "maximum-regions.sigma")
        )
        asyncio.run(
            test_answer_free_maximum_regions_prompt(root / "maximum-regions-answer-free.sigma")
        )
        asyncio.run(
            test_maximum_regions_false_candidate_is_rejected(
                root / "maximum-regions-counterexample.sigma"
            )
        )
        asyncio.run(
            test_strategy_skeptic_does_not_wait_for_sibling_investigator(
                root / "strategy-parallel-421.sigma"
            )
        )
        asyncio.run(
            test_duplicate_strategy_dispatch_is_fenced_during_provider_call(
                root / "duplicate-strategy-dispatch.sigma"
            )
        )
        asyncio.run(
            test_preflight_failure_isolates_branch_and_commits_sibling(
                root / "fault-isolation-421.sigma"
            )
        )
        asyncio.run(
            test_stop_is_responsive_during_slow_provider_preflight(
                root / "stop-during-preflight-421.sigma"
            )
        )
        asyncio.run(test_provider_gate_fairness_and_cancelled_waiter())
        test_backend_global_provider_file_slots_are_bounded(root)
        asyncio.run(test_global_inflight_limit_bounds_multiple_strategy_sessions(root))
        asyncio.run(test_concurrent_strategy_portfolio(root / "portfolio.sigma"))
        asyncio.run(
            test_session7_context_pause_recovers_original_18_turn_research(
                root / "session7-context-resume.sigma"
            )
        )
        asyncio.run(
            test_three_strategies_reach_18_turns_each_after_transport_failure_at_turn_14(
                root / "portfolio-54-turns.sigma"
            )
        )
        asyncio.run(
            test_parallel_budget_pressure_defers_without_ending_research(
                root / "budget-pressure-deferral.sigma"
            )
        )
        test_parallel_schedule_preserves_research_semantics(root)
        asyncio.run(
            test_portfolio_cross_strategy_reviews_ground_synthesis_in_peer_evidence(
                root / "portfolio-cross-review.sigma"
            )
        )
        asyncio.run(
            test_peer_finding_changes_target_investigator_after_stop_and_resume(
                root / "portfolio-peer-handoff.sigma"
            )
        )
        asyncio.run(
            test_portfolio_marks_unsuccessful_approach_without_mutating_strategy_pool(
                root / "portfolio-unsuccessful.sigma"
            )
        )
        asyncio.run(
            test_ten_strategy_portfolio_respects_concurrency_and_budget(
                root / "portfolio-ten.sigma"
            )
        )
        asyncio.run(
            test_forked_strategy_followup_preserves_parent_comparison(
                root / "portfolio-followup.sigma"
            )
        )
        asyncio.run(
            test_stop_concurrent_portfolio_preserves_completed_boundary(
                root / "portfolio-stop.sigma"
            )
        )
        asyncio.run(
            test_stop_reconciles_queued_portfolio_branches(root / "portfolio-stop-queued.sigma")
        )
        asyncio.run(
            test_portfolio_preflight_failure_terminates_instead_of_spinning(
                root / "portfolio-preflight-failure.sigma"
            )
        )
        asyncio.run(
            test_start_preflight_does_not_hold_project_or_global_admission_locks(
                root / "admission-preflight-locks.sigma"
            )
        )
        asyncio.run(
            test_start_preserves_frozen_inputs_after_slow_preflight(
                root / "admission-preflight-revalidation.sigma"
            )
        )
        asyncio.run(
            test_portfolio_audits_mixed_preflight_failure_and_sibling_success(
                root / "portfolio-preflight-mixed-wave.sigma"
            )
        )
        asyncio.run(
            test_portfolio_preflight_timeout_pauses_without_spending_calls_and_recovers(
                root / "portfolio-preflight-timeout.sigma"
            )
        )
        asyncio.run(
            test_resume_limits_reconcile_portfolio_terminal_state(
                root / "portfolio-resume-limits.sigma"
            )
        )
        asyncio.run(
            test_portfolio_isolates_one_strategy_provider_failure(
                root / "portfolio-isolated-failure.sigma"
            )
        )
        asyncio.run(
            test_portfolio_timeout_is_not_misclassified_as_strategy_failure(
                root / "portfolio-timeout.sigma"
            )
        )
        asyncio.run(
            test_portfolio_rejects_fabricated_cross_strategy_references(
                root / "portfolio-fabricated-reference.sigma"
            )
        )
        test_portfolio_requires_reciprocal_complement_and_surfaces_conflicts()
        test_peer_handoff_noop_and_domain_mismatch_controls()
        test_peer_handoff_queue_defers_without_silent_loss()
        test_peer_handoff_deferred_storage_is_bounded_and_reports_overflow()
        asyncio.run(
            test_concurrent_human_guidance_is_delivered_and_attributed(
                root / "human-intervention-concurrent.sigma"
            )
        )
        asyncio.run(
            test_intervention_delivery_pause_resume_keeps_attempt_provenance(
                root / "human-intervention-resume.sigma"
            )
        )
        test_intervention_recovery_supersession_and_rejection(
            root / "human-intervention-recovery.sigma"
        )
        asyncio.run(
            test_portfolio_budget_too_small_for_next_pair_is_finalized(
                root / "portfolio-tight-budget.sigma"
            )
        )
        asyncio.run(
            test_three_strategies_launch_under_three_turn_shared_ceiling(
                root / "portfolio-three-turns.sigma"
            )
        )
        test_portfolio_round_ceiling_not_mislabeled_as_funding_shortage()
        asyncio.run(
            test_eighteen_turns_survive_project_edits_and_bounded_context(
                root / "portfolio-eighteen-turns.sigma"
            )
        )
        asyncio.run(
            test_incomplete_productive_stop_uses_remaining_round(
                root / "portfolio-incomplete-stop.sigma"
            )
        )
        asyncio.run(
            test_e004_unsupported_achieved_no_progress_reaches_configured_rounds(
                root / "e004-claimed-convergence.sigma"
            )
        )
        asyncio.run(
            test_e004_unsupported_achieved_no_progress_reaches_configured_rounds(
                root / "e004-unproductive.sigma", unproductive_no_progress=True
            )
        )
        asyncio.run(
            test_configured_cost_cap_reports_second_call_refusal(
                root / "portfolio-cost-cap-second-call.sigma"
            )
        )
        asyncio.run(
            test_session_token_and_hard_ledger_stops_are_diagnostic(
                root / "portfolio-token-hard-limit.sigma"
            )
        )
        asyncio.run(test_generic_objective_review_on_binary_strings(root / "binary-strings.sigma"))
        test_outcome_classification()
        test_session_listing_ignores_sequence_metadata(root / "session-sequence-metadata.sigma")
        test_outcome_conclusions_are_bounded_honest_and_synthesized(
            root / "outcome-conclusion.sigma"
        )
        test_outcome_metrics_from_persisted_evidence(root / "outcome-metrics.sigma")
        assert research_sessions.coordinate_decision(
            "stop", "recoverable_objection", "Test the omitted boundary case", [], 1, 3, 2, 6
        ) == ("revise", "Test the omitted boundary case")
        assert research_sessions.coordinate_decision(
            "stop", "decisive_counterexample", "", [], 1, 3, 2, 6
        ) == ("stop_decisive_counterexample", "")
        assert research_sessions.coordinate_decision("stop", "no_progress", "", [], 1, 3, 2, 6) == (
            "stop_no_progress",
            "",
        )
        assert research_sessions.coordinate_decision(
            "stop", "productive_conclusion", "", [], 1, 3, 2, 6
        ) == ("stop_productive_conclusion", "")
        assert research_sessions.coordinate_decision(
            "continue", "recoverable_objection", "Next test", [], 3, 3, 6, 6
        ) == ("stop_budget_exhausted", "")
    print("Persistent research session scenarios passed.")  # CI retrigger


def test_e001_research_reference_content_frozen_and_in_both_role_requests(monkeypatch):
    """No provider usage: retrieved excerpts are frozen, hashed and auditable."""
    import hashlib

    from sigma import research_method_sources, research_reference_content

    calls = []

    def fake_read(url):
        calls.append(url)
        page = (
            "<html><nav>ignore the navigation</nav><main><h1>Method</h1>"
            "<p>Check the observed physical quantity and specify assumptions. "
            "Validate calculations separately from empirical measurement. "
            "Document uncertainty and sensitivity of each inference.</p></main></html>"
        )
        return 200, "text/html; charset=utf-8", page.encode(), None

    monkeypatch.setattr(research_reference_content, "_read_remote", fake_read)
    selected = research_method_sources.select_method_sources(
        "physics", "Warp", "A warp geometry", (), (), fetch_content=True
    )
    assert selected["retrieval_summary"] == {
        "retrieved": len(selected["sources"]),
        "unavailable": 0,
    }
    assert calls
    for source in selected["sources"]:
        result = source["retrieval"]
        assert result["status"] == "retrieved"
        assert result["content_sha256"] and result["excerpt_sha256"]
        assert "observed physical quantity" in result["excerpt"]
        assert "ignore the navigation" not in result["excerpt"]
        assert hashlib.sha256(result["excerpt"].encode()).hexdigest() == result["excerpt_sha256"]
    # Stable provenance: no refetch when selection is reused in the next session.
    repeated = research_method_sources.select_method_sources(
        "physics",
        "Warp",
        "A warp geometry",
        (),
        ({"id": "prior", "research_method_sources": selected},),
        fetch_content=True,
    )
    assert repeated["sources"] == selected["sources"]
    assert repeated["status"] == "reused"
    assert len(calls) == len(selected["sources"])
    assert research_method_sources.methodology_digest(repeated) == (
        research_method_sources.methodology_digest(selected)
    )
    context = {
        "problem": "Evaluate physical feasibility.",
        "research_method_version": research_sessions.RESEARCH_METHOD_VERSION,
        "methodology_source_catalog_version": selected["version"],
        "methodology_source_material": selected["sources"],
    }
    record = {"mode": "chatgpt", "model": MODEL, "reasoning_effort": "high"}
    for role in ("investigator", "skeptic"):
        request = research_sessions._role_request_payload(record, role, context)
        assert request["model"] == MODEL
        assert request["reasoning"] == {"effort": "high"}
        assert "observed physical quantity" in request["input"][0]["content"]
        assert "frozen, bounded excerpt" in request["instructions"]
        audit = research_sessions._role_input_audit(record, role, context, None)
        research_sessions._expand_role_input_audit(audit)
        assert audit["request_body"] == request


def test_e001_reference_fetch_failure_is_honest_and_nonblocking(monkeypatch):
    from sigma import research_method_sources, research_reference_content

    def fail(_url):
        return 403, "text/html", b"", None

    monkeypatch.setattr(research_reference_content, "_read_remote", fail)
    selection = research_method_sources.select_method_sources(
        "physics", "Warp", "", (), (), fetch_content=True
    )
    assert selection["retrieval_summary"] == {
        "retrieved": 0,
        "unavailable": len(selection["sources"]),
    }
    assert all(item["retrieval"]["status"] == "unavailable" for item in selection["sources"])
    assert all(item["retrieval"]["excerpt"] is None for item in selection["sources"])
    assert all(item["retrieval"]["reason"] == "http_403" for item in selection["sources"])


def test_e001_reference_fetch_rejects_private_hosts_and_downgrade(monkeypatch):
    import socket

    from sigma import research_reference_content as reference

    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda host, port, type: [(socket.AF_INET, socket.SOCK_STREAM, 0, "", ("127.0.0.1", port))],
    )
    assert (
        reference.freeze_reference_content("https://localhost/private")["status"] == "unavailable"
    )
    assert reference.freeze_reference_content("https://localhost/private")["reason"] == (
        "private_or_unroutable_address"
    )
    assert reference.freeze_reference_content("http://example.com/unsafe")["reason"] == (
        "non_https_or_credential_url"
    )
    assert reference.freeze_reference_content("https://user:password@example.com/")["status"] == (
        "unavailable"
    )
    # The new provider stage is tested separately with the feature explicitly
    # enabled, so the long-standing role protocol fixtures remain unchanged.
    subprocess.run(
        [sys.executable, str(Path(__file__).parent / "reference_compiler_integration.py")],
        check=True,
    )
