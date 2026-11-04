"""Provider-free regression for Crucible #4 multi-round context growth."""

from __future__ import annotations

import json
from copy import deepcopy

from sigma import research_sessions
from sigma.projects import ProjectError
from sigma.research_context_budget import (
    compact_dispatch_context,
    restrict_obligation_citations_to_supplied_context,
)

LIMIT = 256_000


def _size(value: object) -> int:
    return len(json.dumps(value, ensure_ascii=False).encode("utf-8"))


def _obligation(index: int, *, unique_scope: bool = False) -> dict[str, object]:
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


def _context(count: int, *, unique_scope: bool = False) -> dict[str, object]:
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
