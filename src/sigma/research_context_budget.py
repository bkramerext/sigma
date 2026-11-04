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


def _bounded_excerpt(value: str, limit: int) -> str:
    """An explicitly incomplete head/tail extract, never an exact quotation."""
    if len(value) <= limit:
        return value
    half = max(1, (limit - 72) // 2)
    return (
        value[:half]
        + " [INCOMPLETE EXTRACT: omitted middle; saved original not supplied] "
        + value[-half:]
    )


def _compact_inflight_investigator(context: dict[str, Any]) -> bool:
    """Avoid losing a Skeptic turn to an unusually verbose Investigator.

    This modifies the dispatch-only copy. The unmodified Investigator response
    remains durably stored for later inspection. Any omitted derivation or
    computation must NOT be treated as reviewed, verified, or disproved.
    """
    original = context.get("investigator_output")
    if not isinstance(original, dict):
        return False
    excerpt: dict[str, Any] = dict(original)
    shortened: list[str] = []
    method = original.get("method")
    if isinstance(method, str) and len(method) > 3600:
        excerpt["method"] = _bounded_excerpt(method, 3600)
        shortened.append("method")
    steps = original.get("reasoning_steps")
    if isinstance(steps, list):
        # Head/tail-only compaction can omit *every* middle proof premise.
        # Sample across the whole argument while explicitly preserving the
        # original positions; this remains incomplete evidence, never a proof.
        if len(steps) > 4:
            indices = sorted({0, (len(steps) - 1) // 3, 2 * (len(steps) - 1) // 3, len(steps) - 1})
        else:
            indices = list(range(len(steps)))
        selected_steps = [steps[index] for index in indices]
        selected: list[Any] = []
        for step in selected_steps:
            if not isinstance(step, dict):
                selected.append(step)
                continue
            bounded = dict(step)
            for field in ("argument", "rationale", "objection"):
                value = bounded.get(field)
                if isinstance(value, str) and len(value) > 1300:
                    bounded[field] = _bounded_excerpt(value, 1300)
                    if "reasoning_steps" not in shortened:
                        shortened.append("reasoning_steps")
            selected.append(bounded)
        if len(steps) > len(selected_steps):
            if "reasoning_steps" not in shortened:
                shortened.append("reasoning_steps")
            excerpt["reasoning_steps_total"] = len(steps)
            excerpt["reasoning_steps_omitted"] = len(steps) - len(selected_steps)
            # Positions refer to the *saved original* (one-based). Review
            # indices in this reduced list still follow the supplied order.
            excerpt["reasoning_step_original_positions_supplied"] = [index + 1 for index in indices]
            excerpt["reasoning_step_original_positions_omitted"] = [
                index + 1 for index in range(len(steps)) if index not in indices
            ]
        excerpt["reasoning_steps"] = selected
    for field in ("assumptions", "open_obligations"):
        entries = original.get(field)
        if isinstance(entries, list):
            selected = entries[:6] + entries[-2:] if len(entries) > 8 else entries
            bounded = [
                _bounded_excerpt(item, 650) if isinstance(item, str) else item for item in selected
            ]
            if bounded != entries:
                excerpt[field] = bounded
                excerpt[f"{field}_omitted_count"] = len(entries) - len(selected)
                shortened.append(field)
    for field in ("python_execution", "sage_execution"):
        execution = original.get(field)
        if isinstance(execution, dict) and _bytes(execution) > 5000:
            excerpt[field] = {
                key: execution[key]
                for key in (
                    "id",
                    "execution_id",
                    "status",
                    "sha256",
                    "stdout_sha256",
                    "stderr_sha256",
                    "exit_code",
                )
                if key in execution
            } | {
                "evidence_availability": "pointer_only_original_not_supplied",
                "note": "Saved complete execution retained; stdout/stderr not supplied for review.",
            }
            shortened.append(field)
    if not shortened:
        return False
    excerpt["extract_truncated_fields"] = shortened
    excerpt["extract_complete"] = False
    excerpt["evidence_availability"] = "incomplete_extract_original_not_supplied"
    excerpt["note"] = (
        "This current Investigator output is a bounded incomplete extract. "
        "The full output remains saved, but omitted material was not reviewed here."
    )
    if _bytes(excerpt) >= _bytes(original):
        return False
    context["investigator_output"] = excerpt
    context["investigator_output_extract_complete"] = False
    context["context_manifest"]["inflight_investigator_extract"] = {
        "source_step_id": context.get("investigator_step_id"),
        "original_bytes": _bytes(original),
        "supplied_bytes": _bytes(excerpt),
        "truncated_fields": shortened,
        "qualification": "Saved original retained; omitted arguments and computation output cannot be certified or used as reviewed evidence.",
    }
    return True


def _bound_v2_obligation_ledger(context: dict[str, Any], *, limit: int) -> None:
    """Bound the *dispatch-only* ledger without resolving omitted obligations.

    A count cap is insufficient: each current obligation may repeat its scope
    assumptions and provenance. Intern shared sets first, then retain the most
    recent unresolved/material obligations if the packet is still oversized.
    Saved artifacts and the authoritative ledger are never modified.
    """
    if context.get("scheduler_version") != 2:
        return
    ledger = context.get("obligation_ledger")
    manifest = context.get("context_manifest")
    if not isinstance(ledger, list) or not isinstance(manifest, dict) or not ledger:
        return
    if "obligation_ledger_dictionary" in context:
        return  # Already projected during an earlier dispatch assembly phase.

    budget = min(64_000, max(2_048, limit // 4))
    if _bytes(ledger) <= budget:
        return

    def project(indices: list[int]) -> tuple[list[Any], dict[str, Any] | None, int]:
        selected = [
            dict(ledger[index]) if isinstance(ledger[index], dict) else ledger[index]
            for index in sorted(indices)
        ]
        dictionary: dict[str, Any] = {
            "scope_assumptions": [],
            "source_refs": [],
            "index_base": 0,
            "note": (
                "Each *_set_index in an obligation selects the complete exact "
                "list from the corresponding dictionary. These are shared "
                "dispatch representations, not verified evidence."
            ),
        }
        for field in ("scope_assumptions", "source_refs"):
            indexes: dict[str, int] = {}
            for item in selected:
                if not isinstance(item, dict):
                    continue
                values = item.get(field)
                if not isinstance(values, list) or not values:
                    continue
                identity = json.dumps(values, sort_keys=True, ensure_ascii=False)
                position = indexes.get(identity)
                if position is None:
                    position = len(dictionary[field])
                    dictionary[field].append(values)
                    indexes[identity] = position
                item.pop(field)
                item[f"{field}_set_index"] = position
        raw = [ledger[index] for index in sorted(indices)]
        raw_size = _bytes({"obligation_ledger": raw})
        pooled_size = _bytes(
            {"obligation_ledger": selected, "obligation_ledger_dictionary": dictionary}
        )
        if pooled_size >= raw_size:
            return raw, None, raw_size
        return selected, dictionary, pooled_size

    def priority_for(index: int) -> tuple[int, int]:
        item = ledger[index]
        status = item.get("status") if isinstance(item, dict) else None
        tier = 0 if status == "unresolved" else 1 if status == "retracted" else 2
        return tier, -index

    priority = sorted(range(len(ledger)), key=priority_for)
    rows, dictionary, byte_count = project(priority)
    kept = priority
    if byte_count > budget:
        # Monotonic prefix search limits repeated JSON serialization. Never
        # substitute an arbitrary text slice for an intact obligation.
        low, high = 0, len(priority)
        while low < high:
            mid = (low + high + 1) // 2
            if project(priority[:mid])[2] <= budget:
                low = mid
            else:
                high = mid - 1
        if low == 0:
            return  # A single mandatory item is genuinely oversized.
        kept = priority[:low]
        rows, dictionary, byte_count = project(kept)

    kept_indices = set(kept)
    omitted = [
        item
        for index, item in enumerate(ledger)
        if index not in kept_indices and isinstance(item, dict)
    ]
    context["obligation_ledger"] = rows
    if dictionary is not None:
        context["obligation_ledger_dictionary"] = dictionary
    # The duplicate text list must never make an omitted obligation appear
    # available for Skeptic review.
    if isinstance(context.get("outstanding_obligations"), list):
        context.pop("outstanding_obligations")
        manifest["outstanding_obligations_location"] = "obligation_ledger"
    if not omitted:
        return

    omitted_ids = [
        item["obligation_id"] for item in omitted if isinstance(item.get("obligation_id"), str)
    ]
    previous = context.get("obligation_ledger_omitted_count", 0)
    context["obligation_ledger_omitted_count"] = (previous if type(previous) is int else 0) + len(
        omitted
    )
    prior_ids = context.get("obligation_ledger_omitted_ids", [])
    if not isinstance(prior_ids, list):
        prior_ids = []
    context["obligation_ledger_omitted_ids"] = list(dict.fromkeys([*prior_ids, *omitted_ids]))[:32]
    previous_manifest = manifest.get("omitted_obligations", {})
    if not isinstance(previous_manifest, dict):
        previous_manifest = {}
    manifest["omitted_obligations"] = {
        **previous_manifest,
        "count": context["obligation_ledger_omitted_count"],
        "obligation_ids": context["obligation_ledger_omitted_ids"],
        "reason": (
            "Dispatch byte budget: older obligations remain unresolved in "
            "saved research but were not supplied for this review; their "
            "absence is not a disposition or evidence of closure."
        ),
    }
    manifest["dispatch_obligation_budget"] = {
        "budget_bytes": budget,
        "supplied_count": len(rows),
        "newly_omitted_count": len(omitted),
        "supplied_representation_bytes": byte_count,
        "qualification": (
            "No omitted obligation may be treated as reviewed or resolved; "
            "original evidence and provenance remain saved."
        ),
    }


def compact_dispatch_context(context: dict[str, Any], *, limit: int) -> bool:
    """Compact repeated and older context before the hard dispatch byte guard.

    Return True when the context fits. An oversized current Investigator
    output receives an explicitly incomplete dispatch-only extract; its full
    original remains saved. A genuinely oversized active question, approved
    source packet or human intervention is never silently truncated.
    """
    # v2 ledgers grow across rounds even when the total packet initially fits.
    # Bound them proactively rather than waiting for the 256 KB failure edge.
    _bound_v2_obligation_ledger(context, limit=limit)
    if _bytes(context) <= limit:
        return True
    manifest = context.get("context_manifest")
    if not isinstance(manifest, dict):
        return False

    # Method references are optional secondary guidance. Never let a bulky
    # methods packet prevent a real Investigator/Skeptic turn, or cause a
    # proof premise to be discarded sooner than necessary. The full frozen
    # pre-turn selection remains in the authoritative saved session.
    methods = context.get("methodology_source_material")
    compiled_methods = (
        isinstance(methods, list)
        and len(methods) == 1
        and isinstance(methods[0], dict)
        and methods[0].get("id") == "compiled-methodology-guide"
    )
    # Compiled guidance is a frozen session-wide invariant. Compact optional
    # research history first rather than silently omitting the guide from
    # late-round Investigator/Skeptic turns.
    if _bytes(context) > limit and methods and not compiled_methods:
        selected = context.pop("methodology_source_material")
        context["methodology_source_status"] = "omitted_due_to_context_limit"
        manifest["methodology_sources_not_supplied"] = {
            "count": len(selected) if isinstance(selected, list) else 0,
            "reason": "Optional method notes omitted to preserve actual research evidence in the model context; full selection remains in saved session.",
        }
        if _bytes(context) <= limit:
            return True

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

    # Even one valid Investigator can emit 24 long reasoning steps, exceeding
    # the 256 KB packet limit before any historical context is added. Prefer
    # a visibly incomplete current-turn extract to stopping all research.
    if _bytes(context) > limit:
        _compact_inflight_investigator(context)

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


def restrict_obligation_citations_to_supplied_context(context: dict[str, Any]) -> None:
    """Keep dispatch-only obligation references inside the actual evidence allowlist.

    The authoritative session ledger and original artifacts are untouched.
    An obligation may remember dozens of historical source IDs, including
    pointer-only extracts that were not included in this model request. Showing
    those IDs as ordinary evidence invites a Skeptic to cite them, after which
    the strict output validator correctly rejects the entire (paid) response.
    Retain counts of withheld provenance, but offer only IDs that this exact
    request can legitimately cite. Do not make pointer-only evidence citable.
    """
    allowed_artifacts: set[str] = set()
    for field in ("context_artifact_ids", "prior_session_artifact_ids"):
        values = context.get(field)
        if isinstance(values, list):
            allowed_artifacts.update(value for value in values if isinstance(value, str))
    # Peer summaries are admissible only when the full bounded extract was
    # actually selected. Pointer-only peer IDs remain strictly unavailable.
    if context.get("scheduler_version") == 2:
        allowed_artifacts.update(
            item["artifact_id"]
            for item in context.get("other_strategy_evidence", [])
            if isinstance(item, dict)
            and isinstance(item.get("artifact_id"), str)
            and item.get("evidence_availability") != "pointer_only_original_not_supplied"
        )
    current_step = context.get("investigator_step_id")
    allowed_steps = {current_step} if isinstance(current_step, str) else set()
    ledger = context.get("obligation_ledger")
    if not isinstance(ledger, list):
        return
    for obligation in ledger:
        if not isinstance(obligation, dict):
            continue
        for field in (
            "source_artifact_ids",
            "basis_artifact_ids",
            "supplied_source_artifact_ids",
            "pointer_source_artifact_ids",
        ):
            refs = obligation.get(field)
            if not isinstance(refs, list):
                continue
            kept = [ref for ref in refs if isinstance(ref, str) and ref in allowed_artifacts]
            if field == "source_artifact_ids":
                saved_total = obligation.get("source_artifact_count")
                original_total = max(
                    len(refs),
                    saved_total if type(saved_total) is int and saved_total >= 0 else 0,
                )
                obligation["source_artifact_count"] = original_total
                obligation["unsupplied_source_artifact_count"] = max(0, original_total - len(kept))
            elif field == "pointer_source_artifact_ids":
                # Pointer IDs describe unavailable evidence; never expose them
                # in the same namespace as reviewable source references. Keep
                # the count if this already-normalized dispatch context passes
                # through a second finalization path.
                prior_count = obligation.get("withheld_pointer_source_count")
                obligation["withheld_pointer_source_count"] = max(
                    len(refs), prior_count if type(prior_count) is int and prior_count >= 0 else 0
                )
                kept = []
            obligation[field] = kept
        for field in ("source_step_ids", "basis_step_ids"):
            refs = obligation.get(field)
            if isinstance(refs, list):
                kept = [ref for ref in refs if isinstance(ref, str) and ref in allowed_steps]
                count_key = f"withheld_{field}_count"
                prior_count = obligation.get(count_key)
                obligation[count_key] = max(
                    len(refs) - len(kept),
                    prior_count if type(prior_count) is int and prior_count >= 0 else 0,
                )
                obligation[field] = kept
        if obligation.get("unsupplied_source_artifact_count", 0) or obligation.get(
            "withheld_pointer_source_count", 0
        ):
            obligation["source_artifact_availability"] = "incomplete_extract_original_not_supplied"
