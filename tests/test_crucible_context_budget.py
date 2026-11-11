"""Provider-free regression for Crucible #4 multi-round context growth."""

from __future__ import annotations

import asyncio
import json
from copy import deepcopy
from typing import Any
from unittest.mock import patch

from sigma import research_sessions
from sigma.projects import ProjectError
from sigma.research_context_budget import (
    compact_dispatch_context,
    restrict_obligation_citations_to_supplied_context,
)

LIMIT = 256_000


def _size(value: object) -> int:
    return len(json.dumps(value, ensure_ascii=False).encode("utf-8"))


def _obligation(index: int, *, unique_scope: bool = False) -> dict[str, Any]:
    group = index if unique_scope else index // 12
    assumptions = [f"Shared assumption {group} / {number}: " + "a" * 180 for number in range(6)]
    artifact_id = f"research-artifact-{index // 3}"
    return {
        "obligation_id": f"o{index}",
        "status": "unresolved" if index % 9 else "retracted",
        "text": f"Check obligation {index} before accepting the inference: " + "x" * 570,
        "text_complete": True,
        "scope_assumptions": assumptions,
        "source_artifact_ids": [artifact_id],
        "supplied_source_artifact_ids": [artifact_id],
        "source_refs": [
            {
                "project_id": "project",
                "session_id": "saved-session",
                "strategy_id": f"strategy-{index % 3}",
                "artifact_id": artifact_id,
                "sequence": index // 3,
            }
        ],
        "source_artifact_count": 1,
    }


def _context(count: int, *, unique_scope: bool = False) -> dict[str, Any]:
    ledger = [_obligation(i, unique_scope=unique_scope) for i in range(count)]
    return {
        "scheduler_version": 2,
        "problem": "Crucible literary interpretation with strict evidence provenance.",
        "question": "Test the latest counterclaim and unresolved obligations.",
        "strategy": {"id": "strategy-0", "approach": "Investigate counterexamples."},
        "obligation_ledger": ledger,
        "outstanding_obligations": [entry["text"] for entry in ledger],
        "obligation_ledger_omitted_count": 0,
        "obligation_ledger_omitted_ids": [],
        "prior_session_findings": [
            {"id": f"prior-{i}", "method": "historical provenance " + "p" * 14500} for i in range(2)
        ],
        "prior_session_artifact_ids": ["prior-0", "prior-1"],
        "prior_artifacts": [
            {
                "id": f"saved-{i}",
                "strategy_id": "strategy-0",
                "method": "saved argument " + "m" * 12000,
            }
            for i in range(8)
        ],
        "context_artifact_ids": [f"saved-{i}" for i in range(8)],
        "context_manifest": {
            "sources": [
                {
                    "category": "current_session_material_evidence",
                    "status": "selected",
                    "source_ids": ["saved-0", "saved-7"],
                }
            ],
            "omitted_obligations": {"count": 0, "obligation_ids": []},
        },
    }


def test_crucible_three_rounds_growth_preserves_saved_research() -> None:
    """Exercise nine accumulating turn packets, not merely a single overflow."""
    counts = [18, 30, 44, 58, 72, 86, 100, 114, 128]
    any_omitted = False
    for turn, count in enumerate(counts, start=1):
        source = _context(count)
        saved = deepcopy(source)
        dispatch = deepcopy(source)
        dispatch["research_round"] = (turn - 1) // 3 + 1
        dispatch["paired_turn_in_round"] = (turn - 1) % 3 + 1
        dispatch["other_strategy_evidence"] = [
            {
                "artifact_id": f"peer-{index}",
                "claim_or_question": f"Peer claim {index}: " + "e" * 2800,
            }
            for index in range(min(12, 2 * turn))
        ]
        assert compact_dispatch_context(dispatch, limit=LIMIT), (turn, _size(dispatch))
        restrict_obligation_citations_to_supplied_context(dispatch)
        assert _size(dispatch) <= LIMIT
        assert source == saved  # All authoritative originals remain intact.
        assert dispatch["question"] == source["question"]
        assert dispatch["problem"] == source["problem"]
        selected = dispatch["obligation_ledger"]
        selected_ids = {item["obligation_id"] for item in selected}
        omitted = [
            item
            for item in source["obligation_ledger"]
            if item["obligation_id"] not in selected_ids
        ]
        assert dispatch["obligation_ledger_omitted_count"] == len(omitted)
        if omitted:
            any_omitted = True
            metadata = dispatch["context_manifest"]["omitted_obligations"]
            assert metadata["count"] == len(omitted)
            assert "unresolved" in metadata["reason"]
            assert set(dispatch["obligation_ledger_omitted_ids"]) <= {
                item["obligation_id"] for item in omitted
            }
        dictionary = dispatch.get("obligation_ledger_dictionary")
        if dictionary is not None:
            for entry in selected:
                for field in ("scope_assumptions", "source_refs"):
                    index_key = f"{field}_set_index"
                    if index_key in entry:
                        original = next(
                            item
                            for item in source["obligation_ledger"]
                            if item["obligation_id"] == entry["obligation_id"]
                        )
                        assert dictionary[field][entry[index_key]] == original[field]
        # Final dispatch phase adds peer/tool/human data after initial assembly.
        dispatch["human_guidance"] = [{"intervention_id": "user-guidance", "text": "g" * 9000}]
        dispatch["execution_tools"] = [{"name": "python", "bounds": "strict"}]
        assert compact_dispatch_context(dispatch, limit=LIMIT)
        assert _size(dispatch) <= LIMIT
        assert source == saved
    assert any_omitted


def test_unique_scopes_have_bounded_explicit_omission_accounting() -> None:
    source = _context(128, unique_scope=True)
    context = deepcopy(source)
    assert _size(context) > LIMIT
    assert compact_dispatch_context(context, limit=LIMIT)
    assert _size(context) <= LIMIT
    selected = context["obligation_ledger"]
    assert 0 < len(selected) < len(source["obligation_ledger"])
    assert context["obligation_ledger_omitted_count"] == 128 - len(selected)
    assert len(context["obligation_ledger_omitted_ids"]) <= 32
    assert source["obligation_ledger"][-1]["status"] == "unresolved"
    assert any(entry["obligation_id"] == "o127" for entry in selected)
    # A recent retracted obligation is material negative evidence, not optional prose.
    assert any(entry["obligation_id"] == "o126" for entry in selected)
    assert source["outstanding_obligations"]  # Saved original was not modified.


def test_legacy_context_and_oversized_question_remain_fail_closed() -> None:
    source = _context(128, unique_scope=True)
    legacy = deepcopy(source)
    legacy.pop("scheduler_version")
    original_ledger = deepcopy(legacy["obligation_ledger"])
    compact_dispatch_context(legacy, limit=LIMIT)
    assert legacy["obligation_ledger"] == original_ledger
    oversized = {
        "scheduler_version": 2,
        "problem": "q" * (LIMIT + 1),
        "obligation_ledger": [_obligation(0)],
        "context_manifest": {"sources": []},
    }
    assert not compact_dispatch_context(oversized, limit=LIMIT)
    assert len(oversized["problem"]) == LIMIT + 1


def test_omitted_obligations_cannot_be_closed_by_skeptic() -> None:
    context = _context(128, unique_scope=True)
    assert compact_dispatch_context(context, limit=LIMIT)
    omitted_id = context["obligation_ledger_omitted_ids"][0]
    review = {
        "obligation_id": omitted_id,
        "basis_artifact_ids": [],
        "basis_step_ids": [],
    }
    try:
        research_sessions._validate_obligation_review_basis(context, review)
    except ProjectError as exc:
        assert "not supplied" in str(exc) and omitted_id in str(exc)
    else:
        raise AssertionError("An omitted obligation was accepted for review")
    allowed_id = context["obligation_ledger"][0]["obligation_id"]
    research_sessions._validate_obligation_review_basis(
        context, {**review, "obligation_id": allowed_id}
    )


def test_context_limit_byte_diagnostics_are_safe_and_actionable() -> None:
    context = {
        "scheduler_version": 2,
        "problem": "private prose must never appear in the byte breakdown",
        "obligation_ledger": [{"obligation_id": "o1", "text": "unverified evidence"}],
        "context_manifest": {"sources": []},
    }
    message = research_sessions._context_byte_breakdown(context)
    assert "Context size:" in message
    assert f"limit {research_sessions.MAX_AGENT_CONTEXT_BYTES}B" in message
    assert "phase=context_assembly" in message
    assert "problem=" in message
    assert "obligation_ledger=" in message
    assert "context_manifest=" in message
    assert "private prose" not in message
    assert "unverified evidence" not in message


def test_context_diagnostics_include_bounded_execution_identity() -> None:
    context = {
        "secret_project_name": "confidential text " * 100,
        "obligation_ledger": [{"text": "do-not-log-evidence"}],
        "context_manifest": {},
    }
    message = research_sessions._context_byte_breakdown(
        context,
        phase="portfolio_dispatch",
        strategy_id="strategy-1234",
        role="skeptic",
    )
    assert "phase=portfolio_dispatch" in message
    assert "strategy=strategy-1234" in message
    assert "role=skeptic" in message
    assert f"limit {LIMIT}B" in message
    assert "do-not-log-evidence" not in message
    assert "confidential text" not in message
    assert len(message) < 700
    assert "strategy=unknown" in research_sessions._context_byte_breakdown(
        context, strategy_id="private narrative: " + "z" * 100, role="skeptic"
    )


def test_both_roles_reconstruct_pooled_ledger_and_reject_omitted_reviews() -> None:
    source = _context(128)
    saved = deepcopy(source)
    original_by_id = {row["obligation_id"]: row for row in source["obligation_ledger"]}
    for role in ("investigator", "skeptic"):
        dispatch = deepcopy(source)
        dispatch["role"] = role
        assert compact_dispatch_context(dispatch, limit=LIMIT)
        dictionary = dispatch["obligation_ledger_dictionary"]
        assert dictionary["index_base"] == 0
        selected_ids = set()
        for item in dispatch["obligation_ledger"]:
            original = original_by_id[item["obligation_id"]]
            selected_ids.add(item["obligation_id"])
            reconstructed = dict(item)
            for field in ("scope_assumptions", "source_refs"):
                index_key = f"{field}_set_index"
                if index_key in reconstructed:
                    exact_values = dictionary[field][reconstructed.pop(index_key)]
                    reconstructed[field] = exact_values
                assert reconstructed[field] == original[field]
            assert reconstructed == original
        omitted = set(original_by_id) - selected_ids
        assert omitted  # This fixture must actually test the omission barrier.
        assert dispatch["obligation_ledger_omitted_count"] == len(omitted)
        # Evidence admission may narrow citable IDs, without altering pooled
        # assumptions and provenance or the authoritative originals.
        restrict_obligation_citations_to_supplied_context(dispatch)
        for item in dispatch["obligation_ledger"]:
            original = original_by_id[item["obligation_id"]]
            for field in ("scope_assumptions", "source_refs"):
                key = f"{field}_set_index"
                actual_values = dictionary[field][item[key]] if key in item else item[field]
                assert actual_values == original[field]
        if role == "skeptic":
            allowed_artifact = dispatch["context_artifact_ids"][0]
            common_review = {
                "status": "retracted",
                "basis_artifact_ids": [allowed_artifact],
                "basis_step_ids": [],
                "rationale": "The cited source contains material negative evidence.",
            }
            supported = research_sessions.ObligationReview.model_validate(
                {**common_review, "obligation_id": next(iter(selected_ids))}
            ).model_dump()
            research_sessions._validate_obligation_review_basis(dispatch, supported)
            omitted_review = research_sessions.ObligationReview.model_validate(
                {**common_review, "obligation_id": next(iter(omitted))}
            ).model_dump()
            try:
                research_sessions._validate_obligation_review_basis(dispatch, omitted_review)
            except ProjectError as exc:
                assert "not supplied" in str(exc)
            else:
                raise AssertionError("A syntactically valid review resolved an omitted item")
    assert source == saved


def test_recent_negative_evidence_and_unresolved_win_over_old_unresolved() -> None:
    source = _context(128, unique_scope=True)
    for item in source["obligation_ledger"]:
        item["status"] = "unresolved"
    source["obligation_ledger"][126]["status"] = "retracted"
    source["obligation_ledger"][126]["text"] = (
        "Recent negative evidence disproves a previously accepted conclusion. " + "n" * 570
    )
    original = deepcopy(source)
    dispatch = deepcopy(source)
    assert compact_dispatch_context(dispatch, limit=LIMIT)
    assert _size(dispatch) <= LIMIT
    selected = {row["obligation_id"]: row for row in dispatch["obligation_ledger"]}
    assert len(selected) < 128
    assert "o126" in selected  # Recent retraction is not displaced by old obligations.
    assert "o127" in selected  # Recent unresolved outranks older unresolved work.
    assert "o0" not in selected
    assert selected["o126"]["status"] == "retracted"
    assert selected["o126"]["text"] == original["obligation_ledger"][126]["text"]
    assert dispatch["obligation_ledger_omitted_count"] == 128 - len(selected)
    assert source == original


def test_post_assembly_guard_rejects_oversized_mandatory_human_input() -> None:
    original = _context(128, unique_scope=True)
    dispatch = deepcopy(original)
    assert compact_dispatch_context(dispatch, limit=LIMIT)
    selected_before = len(dispatch["obligation_ledger"])
    omitted_before = dispatch["obligation_ledger_omitted_count"]
    # Mimics additions after the first assembly, while retaining all saved evidence.
    dispatch["human_guidance"] = [
        {
            "intervention_id": "human-live-input",
            "text": "MANDATORY-LIVE-EVIDENCE-" + "z" * (LIMIT + 25_000),
        }
    ]
    dispatch["execution_tools"] = [{"name": "python", "capability": "read-only"}]
    dispatch["other_strategy_evidence"] = [
        {"artifact_id": "peer-negative", "claim_or_question": "Recent counterexample"}
    ]
    assert not compact_dispatch_context(dispatch, limit=LIMIT)
    assert _size(dispatch) > LIMIT
    assert dispatch["human_guidance"][0]["text"].startswith("MANDATORY-LIVE-EVIDENCE-")
    assert len(dispatch["human_guidance"][0]["text"]) > LIMIT
    assert len(dispatch["obligation_ledger"]) == selected_before
    assert dispatch["obligation_ledger_omitted_count"] == omitted_before
    manifest = dispatch["context_manifest"]["omitted_obligations"]
    assert manifest["count"] == omitted_before
    assert original == _context(128, unique_scope=True)


def test_sigma_dispatch_byte_guard_reports_model_as_diagnostic_not_cause() -> None:
    context = {
        "problem": "sensitive-evidence-" * 16000,
        "context_manifest": {"sources": []},
    }
    record = {"model": "gpt-6-luna", "reasoning_effort": "low"}
    message = str(
        research_sessions._research_context_guard_error(
            context,
            record=record,
            phase="portfolio_dispatch",
            strategy_id="strategy-1",
            role="investigator",
        )
    )
    assert "SIGMA's 256,000-byte UTF-8 dispatch guard" in message
    assert "not the provider model's token context window" in message
    assert "Context size:" in message
    assert "limit 256000B" in message
    assert "selected_model=gpt-6-luna" in message
    assert "thinking" not in message
    assert "phase=portfolio_dispatch" in message
    assert "sensitive-evidence" not in message
    assert "No provider call was made" in message


def test_sigma_context_guard_never_echoes_unknown_model_or_thinking() -> None:
    context = {"problem": "private", "context_manifest": {"sources": []}}
    message = str(
        research_sessions._research_context_guard_error(
            context,
            record={"model": "private-model-value", "reasoning_effort": "private-thinking"},
            phase="agent_assembly",
        )
    )
    assert "selected_model=unknown" in message
    assert "thinking" not in message
    assert "private-model-value" not in message
    assert "private-thinking" not in message
    assert "private" not in message


def test_sigma_manifest_storage_guard_is_not_confused_with_model_window() -> None:
    context = {"context_manifest": {"sources": ["x" * 12_001]}}
    message = str(research_sessions._research_context_manifest_guard_error(context))
    assert "SIGMA context manifest requires" in message
    assert "limit 12,000 bytes" in message
    assert "No provider call was made" in message
    assert "x" * 100 not in message


def test_context_manifest_errors_remain_recoverable_guards() -> None:
    error = research_sessions._research_context_manifest_guard_error(
        {"context_manifest": {"sources": ["z" * 12_001]}}
    )
    assert isinstance(error, research_sessions.ResearchContextLimitError)
    assert research_sessions._is_guard_failure(str(error))


def test_public_recovery_guidance_prioritizes_internal_context_guard_over_model() -> None:
    message = str(
        research_sessions._research_context_guard_error(
            {"problem": "mandatory" * 40_000, "context_manifest": {"sources": []}},
            record={"model": "gpt-6-luna", "reasoning_effort": "low"},
            phase="portfolio_dispatch",
        )
    )
    record = {
        "status": "paused",
        "message": message,
        "mode": "chatgpt",
        "steps": [],
        "artifacts": [],
        "strategy_runs": [],
        "calls_used": 0,
        "call_limit": 2,
    }
    guidance = research_sessions._public(record)["next_step_guidance"]
    assert "256,000-byte UTF-8 dispatch guard" in guidance
    assert "independent of the selected model" in guidance
    assert "thinking" not in guidance.lower()
    assert "Check that the current connection supports" not in guidance


def test_source_material_overflow_reports_exact_pre_dispatch_limit() -> None:
    """A 0-call source overflow needs a specific remedy, not model switching."""
    source = {"id": "saved-source", "excerpt": "x" * 60_001}
    source_before = source.copy()
    try:
        research_sessions._bounded_supplied_evidence([source])
    except ValueError as exc:
        message = str(exc)
    else:
        raise AssertionError("Oversized Source Material was accepted")
    assert "Source Material contains 60,001 extracted characters" in message
    assert "at most 60,000" in message
    assert source == source_before, "Failed preflight mutated saved source evidence"
    record = {
        "status": "paused",
        "current_action": "Paused · source material exceeds context limit",
        "message": message,
        "mode": "chatgpt",
        "steps": [],
        "artifacts": [],
        "strategy_runs": [],
        "calls_used": 0,
        "call_limit": 126,
    }
    guidance = research_sessions._public(record)["next_step_guidance"]
    assert "extracted-text limit" in guidance
    assert "before an Investigator/Skeptic call" in guidance
    assert "switching models or Thinking levels" in guidance
    assert not record["steps"] and record["calls_used"] == 0


def _preflight_record(question: str, *, source: str = "premise") -> dict[str, Any]:
    return {
        "id": "context-791",
        "status": "running",
        "model": "gpt-6.1-sol",
        "problem": "Research the frozen project evidence.",
        "uploaded_project_evidence": [{"id": "source-a", "excerpt": source}],
        "strategy_runs": [
            {
                "strategy_id": "strategy-a",
                "strategy_title": "Evidence",
                "strategy_text": "Test the supplied premises.",
                "current_question": question,
                "status": "queued",
            }
        ],
        "reference_compilation": {"status": "pending", "attempts": []},
        "calls_used": 0,
        "steps": [],
        "artifacts": [],
        "events": [],
    }


def test_mandatory_packet_lower_bound_prevents_spending_on_impossible_sources() -> None:
    """59k extracted Unicode chars fit source policy but may exceed byte policy."""
    record = _preflight_record("q" * 30_000, source="🧪" * 59_000)
    original = deepcopy(record)
    packet = research_sessions._mandatory_dispatch_lower_bound(record, record["strategy_runs"][0])
    assert len(record["uploaded_project_evidence"][0]["excerpt"]) < 60_000
    assert _size(packet) > LIMIT
    assert packet["uploaded_project_evidence"] == original["uploaded_project_evidence"]
    assert record == original

    stored = deepcopy(record)
    writes: list[dict[str, Any]] = []

    def read(_path: str, _id: str) -> dict[str, Any]:
        return deepcopy(stored)

    def save(_path: str, updated: dict[str, Any]) -> None:
        nonlocal stored
        stored = deepcopy(updated)
        writes.append(deepcopy(updated))

    with (
        patch.object(research_sessions, "_read", side_effect=read),
        patch.object(research_sessions, "_save", side_effect=save),
    ):
        assert not asyncio.run(
            research_sessions._ensure_mandatory_dispatch_preflight("context-791", "test")
        )
    assert len(writes) == 1
    assert stored["status"] == "paused"
    assert stored["strategy_runs"][0]["status"] == "paused"
    assert stored["termination_reason_code"] == "context_limit"
    assert "mandatory_preflight" in stored["message"]
    assert "SIGMA's 256,000-byte UTF-8 dispatch guard" in stored["message"]
    assert "59,000" not in stored["message"]  # No raw source content or characters disclosed
    assert "🧪" not in stored["message"]
    assert stored["calls_used"] == 0
    assert stored["steps"] == []
    assert stored["reference_compilation"] == original["reference_compilation"]
    assert stored["uploaded_project_evidence"] == original["uploaded_project_evidence"]
    assert stored["events"][-1]["kind"] == "research.context_blocked"
    # Re-evaluation of the original frozen inputs cannot trigger provider work.
    assert (
        _size(
            research_sessions._mandatory_dispatch_lower_bound(
                original, original["strategy_runs"][0]
            )
        )
        > LIMIT
    )


def test_mandatory_preflight_does_not_block_viable_portfolio_peers() -> None:
    record = _preflight_record("q" * (LIMIT + 1000))
    record["strategy_runs"].append(
        {
            "strategy_id": "strategy-b",
            "strategy_title": "Independent approach",
            "strategy_text": "Proceed with the bounded inputs.",
            "current_question": "Check a short counterexample.",
            "status": "queued",
        }
    )
    original = deepcopy(record)
    assert (
        _size(research_sessions._mandatory_dispatch_lower_bound(record, record["strategy_runs"][0]))
        > LIMIT
    )
    assert (
        _size(research_sessions._mandatory_dispatch_lower_bound(record, record["strategy_runs"][1]))
        < LIMIT
    )

    with (
        patch.object(research_sessions, "_read", return_value=record),
        patch.object(research_sessions, "_save") as save,
    ):
        assert asyncio.run(
            research_sessions._ensure_mandatory_dispatch_preflight("context-791", "test")
        )
    save.assert_not_called()
    assert record == original


def test_no_runnable_strategy_cannot_start_optional_compilation() -> None:
    record = _preflight_record("An already paused question")
    record["strategy_runs"][0]["status"] = "paused"
    original = deepcopy(record)
    with (
        patch.object(research_sessions, "_read", return_value=record),
        patch.object(research_sessions, "_save") as save,
    ):
        assert not asyncio.run(
            research_sessions._ensure_mandatory_dispatch_preflight(
                "context-791-no-runnable", "test"
            )
        )
    save.assert_not_called()
    assert record == original
