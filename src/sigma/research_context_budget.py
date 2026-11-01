"""Non-destructive research-context compaction for long-running sessions.

Saved research records are authoritative. This module changes only the model
dispatch packet and never alters a saved artifact or treats an omitted extract
as verified evidence.
"""
from __future__ import annotations

import json
from typing import Any


def _bytes(value: Any) -> int:
    return len(json.dumps(value, ensure_ascii=False).encode("utf-8"))


def compact_dispatch_context(context: dict[str, Any], *, limit: int) -> bool:
    """Compact repeated and older context before the hard dispatch byte guard.

    Return True when the context fits. A genuinely oversized active question,
    approved source packet, current Investigator output or human intervention
    is deliberately NOT truncated: callers must still enforce the hard limit.
    """
    if _bytes(context) <= limit:
        return True
    manifest = context.get("context_manifest")
    if not isinstance(manifest, dict):
        return False

    # This exact list is derivable from the ledger and often repeats long
    # obligations; do not remove the obligations themselves.
    if isinstance(context.get("obligation_ledger"), list):
        context.pop("outstanding_obligations", None)
        manifest["outstanding_obligations_location"] = "obligation_ledger"
        if _bytes(context) <= limit:
            return True

    compacted: dict[str, int] = {}
    pointers: dict[str, list[str]] = {}
    for field, id_field in (
        ("prior_artifacts", "id"),
        ("prior_session_findings", "id"),
        ("other_strategy_evidence", "artifact_id"),
    ):
        entries = context.get(field)
        if not isinstance(entries, list):
            continue
        # Earlier entries are the oldest within their selection groups.
        for index, entry in enumerate(entries):
            if _bytes(context) <= limit:
                break
            if not isinstance(entry, dict) or not isinstance(entry.get(id_field), str):
                continue
            marker = {
                id_field: entry[id_field],
                "evidence_availability": "pointer_only_original_not_supplied",
                "note": "Saved original retained; not included or verified in this agent request.",
            }
            if field == "prior_artifacts":
                for key in ("strategy_id", "session_id", "sequence"):
                    if key in entry:
                        marker[key] = entry[key]
                marker["extract_truncated_fields"] = ["budget_compacted_original_not_supplied"]
            if _bytes(marker) >= _bytes(entry):
                continue
            entries[index] = marker
            compacted[field] = compacted.get(field, 0) + 1
            pointers.setdefault(field, []).append(entry[id_field])

    # Source completeness must reflect the *final* delivered packet rather
    # than the earlier, pre-compaction selection.
    supplied = {
        entry.get("id"): entry
        for entry in context.get("prior_artifacts", [])
        if isinstance(entry, dict)
    }
    for obligation in context.get("obligation_ledger", []):
        if not isinstance(obligation, dict):
            continue
        if any(
            supplied.get(sid, {}).get("evidence_availability")
            == "pointer_only_original_not_supplied"
            for sid in obligation.get("supplied_source_artifact_ids", [])
        ):
            obligation["source_artifact_availability"] = "incomplete_extract_original_not_supplied"

    if _bytes(context) > limit:
        # These are optional historical/portfolio displays, not the accepted
        # active strategy, live question, or authoritative obligation ledger.
        for field, id_field in (
            ("prior_session_failures", "attempt_id"),
            ("project_strategy_snapshot", "id"),
        ):
            entries = context.get(field)
            if not isinstance(entries, list):
                continue
            while entries and _bytes(context) > limit:
                entry = entries.pop()
                compacted[field] = compacted.get(field, 0) + 1
                if isinstance(entry, dict) and isinstance(entry.get(id_field), str):
                    pointers.setdefault(field, []).append(entry[id_field])

    if compacted:
        manifest["dispatch_budget_compaction"] = {
            "counts": compacted,
            "ids": {field: ids[:16] for field, ids in pointers.items()},
            "unlisted_id_counts": {
                field: max(0, len(ids) - 16) for field, ids in pointers.items()
            },
            "qualification": (
                "Saved originals are intact. Pointers do not establish that "
                "omitted evidence was read, verified, or resolved."
            ),
        }
        for group in manifest.get("sources", []):
            if (
                isinstance(group, dict)
                and group.get("status") == "selected"
                and group.get("category") in {
                    "current_session_material_evidence",
                    "current_session_history",
                    "prior_session_finding",
                    "peer_strategy_evidence",
                }
            ):
                group["representation"] = "bounded_extract_or_pointer_only"

    return _bytes(context) <= limit
