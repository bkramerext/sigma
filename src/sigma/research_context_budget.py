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
        # Compact optional extracts before material evidence, then older
        # entries before newer ones within each priority class.
        material_ids = (
            {
                source_id
                for group in manifest.get("sources", [])
                if isinstance(group, dict)
                and group.get("category") == "current_session_material_evidence"
                and group.get("status") == "selected"
                for source_id in group.get("source_ids", [])
                if isinstance(source_id, str)
            }
            if field == "prior_artifacts"
            else set()
        )

        # Bind per-field locals before the sort key: no loop-variable capture.
        rows: list[Any] = entries
        field_name = id_field
        material: set[str] = material_ids

        def is_material(
            index: int, *, items: list[Any] = rows, key: str = field_name, ids: set[str] = material
        ) -> bool:
            item = items[index]
            return isinstance(item, dict) and item.get(key) in ids

        indices = sorted(range(len(rows)), key=lambda i: (is_material(i), i))
        for index in indices:
            entry = entries[index]
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

    # A pointer is discoverable history, not a supplied source suitable as
    # evidence for an argument, cross-strategy link or obligation closure.
    # Keep citation allowlists synchronized with the final dispatch packet.
    pointers_by_field: dict[str, set[str]] = {}
    for field, id_field in (
        ("prior_artifacts", "id"),
        ("prior_session_findings", "id"),
        ("other_strategy_evidence", "artifact_id"),
    ):
        pointers_by_field[field] = {
            item[id_field]
            for item in context.get(field, [])
            if isinstance(item, dict)
            and isinstance(item.get(id_field), str)
            and item.get("evidence_availability") == "pointer_only_original_not_supplied"
        }
    pointer_artifacts = pointers_by_field["prior_artifacts"]
    pointer_findings = pointers_by_field["prior_session_findings"]
    if pointer_artifacts:
        context["context_artifact_ids"] = [
            item_id
            for item_id in context.get("context_artifact_ids", [])
            if item_id not in pointer_artifacts
        ]
    if pointer_findings:
        approved = context.get("approved_continuation")
        approved_ids = (
            {
                item["artifact_id"]
                for item in approved.get("sources", [])
                if isinstance(item, dict) and isinstance(item.get("artifact_id"), str)
            }
            if isinstance(approved, dict)
            else set()
        )
        context["prior_session_artifact_ids"] = [
            item_id
            for item_id in context.get("prior_session_artifact_ids", [])
            if item_id not in pointer_findings or item_id in approved_ids
        ]
    for obligation in context.get("obligation_ledger", []):
        if not isinstance(obligation, dict):
            continue
        supplied_ids = obligation.get("supplied_source_artifact_ids", [])
        if not isinstance(supplied_ids, list):
            continue
        missing_ids = [
            item_id
            for item_id in supplied_ids
            if item_id in pointer_artifacts or item_id in pointer_findings
        ]
        if missing_ids:
            obligation["supplied_source_artifact_ids"] = [
                item_id for item_id in supplied_ids if item_id not in missing_ids
            ]
            obligation["pointer_source_artifact_ids"] = missing_ids
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
        # Called after multiple assembly phases. Keep previous compaction
        # accounting when later peer/guidance fields require another pass.
        previous = manifest.get("dispatch_budget_compaction", {})
        prior_counts = previous.get("counts", {}) if isinstance(previous, dict) else {}
        prior_ids = previous.get("ids", {}) if isinstance(previous, dict) else {}
        prior_unlisted = (
            previous.get("unlisted_id_counts", {}) if isinstance(previous, dict) else {}
        )
        counts = dict(prior_counts)
        ids = {field: list(values) for field, values in prior_ids.items()}
        unlisted = dict(prior_unlisted)
        for field, count in compacted.items():
            counts[field] = counts.get(field, 0) + count
        for field, new_ids in pointers.items():
            merged = ids.get(field, []) + new_ids
            ids[field] = merged[:4]
            unlisted[field] = unlisted.get(field, 0) + max(0, len(merged) - 4)
        manifest["dispatch_budget_compaction"] = {
            "counts": counts,
            "ids": ids,
            "unlisted_id_counts": unlisted,
            "qualification": (
                "Saved originals are intact. Pointers do not establish that "
                "omitted evidence was read, verified, or resolved."
            ),
        }
        for group in manifest.get("sources", []):
            if (
                isinstance(group, dict)
                and group.get("status") == "selected"
                and group.get("category")
                in {
                    "current_session_material_evidence",
                    "current_session_history",
                    "prior_session_finding",
                    "peer_strategy_evidence",
                }
            ):
                group["representation"] = "bounded_extract_or_pointer_only"

    return _bytes(context) <= limit
