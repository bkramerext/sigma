"""Offline evidence regression over the existing five-subject STAGING release.

Do not emit archived payloads, run provider calls, or modify any saved outcome.
The packet-only counterfactual is separate from the causal builder replay.
Missing checkpoints and file inspections are reported, never reconstructed from
later outcomes. No result is a scientific validation.
"""

from __future__ import annotations

import asyncio
import gzip
import hashlib
import json
from collections import Counter
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import httpx

from sigma import model_dispatch, research_sessions
from sigma.projects import ProjectError
from sigma.research_context_budget import finalize_dispatch_evidence
from sigma.research_evidence_catalog import (
    Catalog,
    EvidenceContext,
    artifact_permissions,
    audit_inventory,
    build_catalog,
    citable,
    step_permissions,
)

ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / "docs/evaluations/research_quality/handoff/releases/phase2-i2-v1"


def _verified_archive(entry: dict[str, Any]) -> Any:
    raw = (ROOT / entry["path"]).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == entry["sha256_compressed"]
    expanded = gzip.decompress(raw)
    assert hashlib.sha256(expanded).hexdigest() == entry["sha256_uncompressed"]
    return json.loads(expanded)


def _archived_context(step: dict[str, Any]) -> dict[str, Any]:
    audit = dict(step["provider_input_audit"])
    research_sessions._expand_role_input_audit(audit)
    assert audit.get("status") != "audit_unavailable_or_corrupt"
    supplied = audit["request_body"]["input"]
    if isinstance(supplied, list):
        supplied = supplied[0]["content"]
    return json.loads(supplied)


def _coverage(context: dict[str, Any], catalog: Catalog) -> tuple[int, int, int]:
    allowed = artifact_permissions(catalog, include_peer=catalog["obligation_peer_citations"])
    argument_ids = {
        identifier
        for group in (catalog["own"], catalog["prior"], catalog["continuation"], catalog["peer"])
        for identifier, source in group.items()
        if identifier in allowed and source["argument"] != "not_supplied"
    }
    current = catalog["current_investigator"]
    available_steps = step_permissions(catalog) if current["argument"] != "not_supplied" else set()
    duties = [row for row in context["obligation_ledger"] if row["status"] == "unresolved"]
    covered = sum(
        bool(
            argument_ids.intersection(row.get("source_artifact_ids", []))
            or argument_ids.intersection(row.get("basis_artifact_ids", []))
            or available_steps.intersection(row.get("source_step_ids", []))
            or available_steps.intersection(row.get("basis_step_ids", []))
        )
        for row in duties
    )
    peer_arguments = sum(
        source["argument"] != "not_supplied" for source in catalog["peer"].values()
    )
    return len(duties), covered, peer_arguments


def _complete_basis_coverage(context: dict[str, Any], catalog: Catalog) -> int:
    allowed = artifact_permissions(catalog, include_peer=catalog["obligation_peer_citations"])
    arguments = {
        identifier
        for group in (catalog["own"], catalog["prior"], catalog["continuation"], catalog["peer"])
        for identifier, source in group.items()
        if identifier in allowed and source["closure_argument"]
    }
    steps = (
        step_permissions(catalog) if catalog["current_investigator"]["closure_argument"] else set()
    )
    return sum(
        bool(
            arguments.intersection(row.get("source_artifact_ids", []))
            or arguments.intersection(row.get("basis_artifact_ids", []))
            or steps.intersection(row.get("source_step_ids", []))
            or steps.intersection(row.get("basis_step_ids", []))
        )
        for row in context["obligation_ledger"]
        if row["status"] == "unresolved" and row.get("text_complete", True)
    )


def _reference_accepted(context: dict[str, Any], output: dict[str, Any]) -> bool:
    """Reference acceptance only, not schema, scientific or provider acceptance."""
    catalog = context["evidence_catalog"]
    allowed = artifact_permissions(catalog, include_peer=True)
    try:
        for row in output.get("obligation_reviews", []):
            research_sessions._validate_obligation_review_basis(context, row)
        research_sessions._validate_computation_citations(
            context, output.get("computational_citations", [])
        )
    except ProjectError:
        return False
    if any(
        not set(row.get("basis_artifact_ids", [])) <= allowed
        for field in ("reasoning_steps", "reasoning_assessments")
        for row in output.get(field, [])
    ):
        return False
    peers = {
        (source["strategy_id"], identifier)
        for identifier, source in catalog["peer"].items()
        if identifier in citable(catalog["peer"])
    }
    if any(
        (row["strategy_id"], row["artifact_id"]) not in peers
        for row in output.get("cross_strategy_relations", [])
    ):
        return False
    continuation = context.get("approved_continuation") or {}
    expected = {row["artifact_id"] for row in continuation.get("sources", [])}
    reviewed = [row["artifact_id"] for row in output.get("continuation_reviews", [])]
    return set(reviewed) == expected and len(reviewed) == len(expected)


def _causal_artifacts(
    session: dict[str, Any], step: dict[str, Any], context: dict[str, Any]
) -> tuple[list[dict[str, Any]] | None, str]:
    """Require the saved creation-time prefix to agree with the audited counts."""
    try:
        cutoff = datetime.fromisoformat(step["started_at"])
        if cutoff.tzinfo is None:
            return None, "missing_timezone"
        prefix = [
            deepcopy(artifact)
            for artifact in session["artifacts"]
            if datetime.fromisoformat(artifact["created_at"]) < cutoff
        ]
    except (KeyError, TypeError, ValueError):
        return None, "missing_causal_timestamps"
    own = {row["id"] for row in prefix if row["strategy_id"] == step["strategy_id"]}
    peer = {row["id"] for row in prefix if row["strategy_id"] != step["strategy_id"]}
    manifest = context["context_manifest"]
    expected_own = manifest.get("selected_count", 0) + manifest.get("omitted_count", 0)
    expected_peer = len(context.get("other_strategy_evidence", [])) + manifest.get(
        "omitted_peer_evidence", {}
    ).get("count", 0)
    if (
        len(own) != expected_own
        or len(peer) != expected_peer
        or not {row["id"] for row in context.get("prior_artifacts", [])} <= own
        or not {row["artifact_id"] for row in context.get("other_strategy_evidence", [])} <= peer
    ):
        return None, "prefix_does_not_match_audited_selection_counts"
    available = own | peer
    for artifact in prefix:
        # Retraction metadata can be appended after the original artifact
        # was committed. Never expose a future retraction in a causal replay.
        if "retracted_by_artifact_ids" in artifact:
            artifact["retracted_by_artifact_ids"] = [
                identifier
                for identifier in artifact["retracted_by_artifact_ids"]
                if identifier in available
            ]
    return prefix, "timestamp_and_audited_counts_match"


def _failure_categories(
    context: dict[str, Any], output: dict[str, Any], prefix: list[dict[str, Any]] | None
) -> dict[str, int]:
    catalog = build_catalog(context)
    allowed = artifact_permissions(catalog, include_peer=catalog["obligation_peer_citations"])
    pointers = {
        identifier
        for group in (catalog["own"], catalog["prior"], catalog["continuation"], catalog["peer"])
        for identifier, source in group.items()
        if source["availability"] == "pointer_only" and identifier not in allowed
    }
    prior_ids = {row["id"] for row in prefix or []}
    missing = {
        identifier
        for review in output.get("obligation_reviews", [])
        for identifier in review.get("basis_artifact_ids", [])
        if identifier not in allowed
    }
    required = {
        row["artifact_id"]
        for row in (context.get("approved_continuation") or {}).get("sources", [])
    }
    reviewed = [row["artifact_id"] for row in output.get("continuation_reviews", [])]
    return {
        "pointer_only_citations": len(missing & pointers),
        "causal_but_omitted_or_disallowed": len((missing & prior_ids) - pointers),
        "not_in_proven_causal_prefix": len(missing - pointers - prior_ids),
        "unsupplied_step_citations": len(
            {
                identifier
                for row in output.get("obligation_reviews", [])
                for identifier in row.get("basis_step_ids", [])
                if identifier not in step_permissions(catalog)
            }
        ),
        "missing_continuation_reviews": len(required - set(reviewed)),
        "unexpected_continuation_reviews": len(set(reviewed) - required),
        "duplicate_continuation_reviews": len(reviewed) - len(set(reviewed)),
    }


def _reconstruct_context(
    session: dict[str, Any],
    step: dict[str, Any],
    original: dict[str, Any],
    prefix: list[dict[str, Any]] | None,
    files: dict[str, Any],
) -> tuple[dict[str, Any] | None, str]:
    """Rebuild the production evidence context from proven pre-call sources.

    Immutable session-start snapshots and the exact audited question/handoffs
    supply the non-artifact fields. No final branch state, later artifact,
    uncertain dispatch, private supervisor material or file lookup is used.
    """
    if prefix is None:
        return None, "causal_prefix_unavailable"
    if any(
        not isinstance(session.get(key), list)
        for key in ("prior_session_findings", "prior_session_obligations", "prior_session_failures")
    ):
        return None, "frozen_prior_snapshot_unavailable"
    current_ids = {row["id"] for row in session["artifacts"]}
    prior_findings = session["prior_session_findings"]
    prior_obligations = session["prior_session_obligations"]
    if any(row.get("id") in current_ids for row in prior_findings) or any(
        current_ids.intersection(row.get("source_artifact_ids", []))
        or current_ids.intersection(row.get("basis_artifact_ids", []))
        for row in prior_obligations
    ):
        return None, "frozen_prior_snapshot_contains_current_session_lineage"
    # Build only from session-start fields; dynamic fields come from the exact
    # original request or timestamp-validated accepted preceding role.
    frozen_fields = (
        "id",
        "project_id",
        "problem",
        "desired_outcomes",
        "model",
        "reasoning_effort",
        "investigation_type",
        "research_method_version",
        "research_method_sources",
        "research_method_references",
        "research_method_reference_urls",
        "project_type_snapshot",
        "use_saved_project_type_settings",
        "strategy_snapshot",
        "prior_session_findings",
        "prior_session_obligations",
        "prior_session_failures",
        "prior_session_findings_omitted",
        "prior_session_findings_omitted_source_ids",
        "prior_session_obligations_omitted",
        "prior_session_obligation_omitted_ids",
        "prior_session_obligation_omitted_by_strategy",
        "prior_session_obligation_omitted_ids_by_strategy",
        "prior_session_failures_omitted",
        "prior_session_failure_omitted_attempt_ids",
        "research_context_version",
        "obligation_id_format",
    )
    record = {key: deepcopy(session[key]) for key in frozen_fields if key in session}
    record["problem"] = original["problem"]
    record["artifacts"] = deepcopy(prefix)
    record["project_path"] = None
    record["supervisor_reviews"] = []
    record["steps"] = []
    role = step["role"]
    strategy = original["strategy"]
    cycle = original["cycle"]
    branch = {
        "strategy_id": strategy["id"],
        "strategy_title": strategy["title"],
        "strategy_text": strategy["approach"],
        "current_question": original["question"],
        "initial_question_source": original.get("question_source"),
        "protocol_completion_recovery": original.get("protocol_completion_recovery"),
    }
    if original.get("scheduler_version") == 2:
        record.update(
            scheduler_version=2,
            research_round_limit=session["research_round_limit"],
            turns_per_round=session["turns_per_round"],
        )
    if original.get("session_settings"):
        record["session_settings"] = deepcopy(original["session_settings"])
    if original.get("uploaded_project_evidence"):
        record["uploaded_project_evidence"] = deepcopy(original["uploaded_project_evidence"])
    if original.get("approved_continuation"):
        from sigma.continuations import expand_dispatch_packet

        record["approved_continuations"] = {
            strategy["id"]: expand_dispatch_packet(deepcopy(original["approved_continuation"]))
        }
    if role == "skeptic":
        current = next(
            (
                item
                for item in session["steps"]
                if item["id"] == original.get("investigator_step_id")
                and item["status"] == "completed"
                and item["role"] == "investigator"
                and item["strategy_id"] == strategy["id"]
                and item["cycle"] == cycle
            ),
            None,
        )
        if not current or not isinstance(current.get("output"), dict):
            return None, "accepted_investigator_checkpoint_unavailable"
        try:
            if datetime.fromisoformat(current["finished_at"]) >= datetime.fromisoformat(
                step["started_at"]
            ):
                return None, "investigator_checkpoint_not_before_dispatch"
        except (KeyError, TypeError, ValueError):
            return None, "investigator_checkpoint_timestamp_unavailable"
        branch["pending_investigation"] = deepcopy(current["output"])
        record["steps"] = [deepcopy(current)]
    handoffs = deepcopy(original.get("peer_handoffs", []))
    record["retracted_peer_handoffs"] = [
        {"handoff_id": row["handoff_id"]} for row in handoffs if row.pop("retracted", False)
    ]
    for row in handoffs:
        row.pop("approval_status", None)
    branch["active_peer_handoffs" if role == "skeptic" else "pending_peer_handoffs"] = handoffs

    # File previews are not reconstructible from metadata alone. Never read
    # the original machine's path or silently replace missing file evidence.
    evidence = [*prefix]
    if role == "skeptic":
        evidence.append(branch["pending_investigation"])
    for row in evidence:
        investigation = row.get("investigator_output", row)
        if any(
            isinstance(execution := investigation.get(field), dict) and execution.get("artifacts")
            for field in ("python_execution", "sage_execution")
        ):
            return None, "historical_file_inspection_checkpoint_unavailable"

    alias_map: dict[str, str] = {}
    observed_ids = {row["obligation_id"] for row in original.get("obligation_ledger", [])} | set(
        original.get("obligation_ledger_omitted_ids", [])
    )
    if record.get("obligation_id_format") == "compact-v1":
        raw_map = files.get("research-sessions/obligation-ids.json")
        if raw_map is None:
            return None, "frozen_obligation_alias_map_unavailable"
        aliases = json.loads(raw_map) if isinstance(raw_map, str) else raw_map
        alias_map = aliases["by_digest"]
        record["project_path"] = "/unavailable-offline-reconstruction.sigma"

    def frozen_aliases(_path: str, digests: list[str]) -> dict[str, str]:
        # The final map is used only for aliases observed in this original
        # request. New/later aliases must never leak into a historical replay.
        if any(alias_map.get(digest) not in observed_ids for digest in digests):
            raise ProjectError("Historical alias not observed at dispatch")
        return {digest: alias_map[digest] for digest in digests}

    try:
        with (
            patch.object(research_sessions, "assign_project_obligation_ids", frozen_aliases),
            patch.object(research_sessions, "inspect_execution_artifacts", return_value=[]),
        ):
            context = research_sessions._portfolio_context(
                record, branch, role, cycle, finalize=False
            )
            for field in ("human_guidance", "execution_tools", "supervisor_guidance"):
                if field in original:
                    context[field] = deepcopy(original[field])
            research_sessions._finalize_role_context(record, context)
    except (KeyError, TypeError, ValueError, ProjectError):
        return None, "historical_builder_inputs_incomplete"
    assert context["evidence_catalog"] == build_catalog(context)
    return context, "production_builder_from_causal_prefix"


async def _production_validate(
    session: dict[str, Any], step: dict[str, Any], context: dict[str, Any], raw: dict[str, Any]
) -> str:
    """Run the real request audit and output validator behind an offline seam."""
    context = deepcopy(context)
    record = {
        "model": session["model"],
        "reasoning_effort": session["reasoning_effort"],
        "mode": session["mode"],
        "strategy_runs": [{"strategy_id": step["strategy_id"]}],
    }
    audit = research_sessions._role_input_audit(record, step["role"], context, None)
    record["steps"] = [
        {
            "id": step["id"],
            "status": "running",
            "role": step["role"],
            "strategy_id": step["strategy_id"],
            "provider_input_audit": audit,
        }
    ]
    response = AsyncMock(return_value=deepcopy(raw))
    with (
        patch.object(
            research_sessions,
            "auth_context",
            new=AsyncMock(
                return_value={
                    "mode": record["mode"],
                    "token": "offline-fixture-token",
                }
            ),
        ),
        patch.object(model_dispatch, "private_response_if_selected", new=response),
        patch.object(httpx, "AsyncClient", side_effect=AssertionError("Network forbidden")),
        patch.object(research_sessions, "_require_current_local_backend", return_value=None),
    ):
        try:
            await research_sessions._call_provider(
                record, step["role"], context, step_id=step["id"]
            )
        except ProjectError as exc:
            # Never emit archived mathematical prose, IDs or raw response.
            message = str(exc)
            if "obligation_reviews cited evidence" in message:
                return "rejected_obligation_basis"
            if "Review every approved continuation" in message:
                return "rejected_continuation_coverage"
            if "JSON schema validation" in message:
                return "rejected_schema"
            if "addressed obligation" in message:
                return "rejected_inadequate_closure"
            return "rejected_other_production_validation"
    assert response.await_count == 1
    return "accepted_counterfactual_only"


def _counterfactual(
    original: dict[str, Any], artifacts: dict[str, dict[str, Any]]
) -> EvidenceContext:
    context = EvidenceContext(deepcopy(original))
    # Only project argument from an already supplied peer ID. No later/new
    # artifact can enter a historical request.
    peers = [
        row
        for row in context.get("other_strategy_evidence", [])
        if row.get("evidence_availability") != "pointer_only_original_not_supplied"
    ]
    latest: dict[str, dict[str, Any]] = {}
    for row in peers:
        strategy = row["strategy_id"]
        if strategy not in latest or row["sequence"] > latest[strategy]["sequence"]:
            latest[strategy] = row
    for row in latest.values():
        saved = artifacts.get(row["artifact_id"])
        if saved is not None and saved.get("strategy_id") == row["strategy_id"]:
            row["current_peer_argument"] = True
            row["argument_extract"] = research_sessions._peer_argument_extract(saved)
    finalize_dispatch_evidence(context, limit=256_000)
    return context


def verify_frozen_evidence_archive() -> None:
    manifest = json.loads((RELEASE / "MANIFEST.json").read_text(encoding="utf-8"))
    sidecar = _verified_archive(manifest["provider_response_validation_evidence"])
    # The published response-validation release contains four complete envelopes.
    if isinstance(sidecar, list):
        responses = sidecar
    else:
        matches = [
            value
            for value in sidecar.values()
            if isinstance(value, list)
            and len(value) == 4
            and all(isinstance(row, dict) and "step_id" in row for row in value)
        ]
        assert len(matches) == 1
        responses = matches[0]
    invalid = {row["step_id"]: row for row in responses}
    assert len(invalid) == 4
    examined: set[str] = set()
    attempts = completed = accepted_references = 0
    prior_valid_reference_passes = prior_invalid_reference_passes = 0

    for subject in manifest["projects"]:
        bundle = _verified_archive(subject["output_bundle"])
        saved = bundle["files"][f"research-sessions/{subject['session_id']}.json"]
        session = json.loads(saved) if isinstance(saved, str) else saved
        original_duties = original_coverage = original_peers = 0
        categories_before: Counter[str] = Counter()
        categories_after: Counter[str] = Counter()
        causal_replays = 0
        reconstructed_audit_bytes = 0
        complete_before = complete_after = 0
        new_duties = new_coverage = new_peers = byte_delta = 0
        max_catalog_bytes = oversized = reference_passes = responses_checked = 0
        for step in session["steps"]:
            context = _archived_context(step)
            original_catalog = build_catalog(context)
            before = _coverage(context, original_catalog)
            complete_before += _complete_basis_coverage(context, original_catalog)
            original_duties += before[0]
            original_coverage += before[1]
            original_peers += before[2]
            prefix, prefix_reason = _causal_artifacts(session, step, context)
            # Use only the proven prefix, or the exact historical packet without
            # enrichment when causal reconstruction cannot be established.
            causal = {row["id"]: row for row in prefix or []}
            revised = _counterfactual(context, causal)
            catalog = revised["evidence_catalog"]
            assert catalog == build_catalog(revised)
            assert revised == _counterfactual(context, causal)
            for category, before_group, after_group in (
                ("own", original_catalog["own"], catalog["own"]),
                ("prior", original_catalog["prior"], catalog["prior"]),
                ("continuation", original_catalog["continuation"], catalog["continuation"]),
                ("peer", original_catalog["peer"], catalog["peer"]),
            ):
                for source in before_group.values():
                    categories_before[f"{category}.{source['availability']}"] += 1
                for source in after_group.values():
                    categories_after[f"{category}.{source['availability']}"] += 1
            after = _coverage(revised, catalog)
            complete_after += _complete_basis_coverage(revised, catalog)
            new_duties += after[0]
            new_coverage += after[1]
            new_peers += after[2]
            old_size = research_sessions._json_bytes(context)
            new_size = research_sessions._json_bytes(revised)
            byte_delta += new_size - old_size
            max_catalog_bytes = max(max_catalog_bytes, research_sessions._json_bytes(catalog))
            oversized += int(new_size > 256_000)
            attempts += 1

            identifier = step["id"]
            if identifier in invalid:
                row = invalid[identifier]
                assert row["project_key"] == subject["key"]
                assert (
                    row["request_body_sha256"]
                    == step["provider_input_audit"]["request_body_sha256"]
                )
                assert step.get("status") != "completed"
                raw = row["response"]["output"][0]["content"][0]["text"]
                output = json.loads(raw)
                # Never certify a previously rejected response based on changed
                # availability. Quantify the counterfactual separately.
                examined.add(identifier)
                failures = _failure_categories(context, output, prefix)
                reconstructed, reason = _reconstruct_context(
                    session, step, context, prefix, bundle["files"]
                )
                selected = reconstructed if reconstructed is not None else revised
                if reconstructed is not None:
                    causal_replays += 1
                    reconstructed_audit_bytes += research_sessions._json_bytes(
                        audit_inventory(reconstructed)
                    )
                result = asyncio.run(_production_validate(session, step, selected, row["response"]))
                print(
                    f"EVIDENCE_ARCHIVE {subject['key']} causal={prefix_reason}/{reason} "
                    f"original_failure_categories={json.dumps(failures, sort_keys=True)} "
                    f"production_validator={result}; historical rejection unchanged"
                )
            elif step.get("status") == "completed":
                output = step.get("output")
                assert isinstance(output, dict)
                completed += 1
            else:
                continue
            responses_checked += 1
            passes = int(_reference_accepted(revised, output))
            reference_passes += passes
            if identifier in invalid:
                prior_invalid_reference_passes += passes
                print(
                    f"EVIDENCE_ARCHIVE {subject['key']} historical invalid envelope "
                    f"counterfactual_reference_pass={bool(passes)}; unchanged disposition"
                )
            else:
                prior_valid_reference_passes += passes
        accepted_references += reference_passes
        print(
            f"EVIDENCE_ARCHIVE {subject['key']} reference_acceptance="
            f"{reference_passes}/{responses_checked} "
            f"obligation_argument_coverage={original_coverage}/{original_duties}"
            f"->{new_coverage}/{new_duties} peer_arguments={original_peers}->{new_peers} "
            f"complete_actionable_basis={complete_before}->{complete_after} "
            f"aggregate_byte_delta={byte_delta} max_catalog_bytes={max_catalog_bytes} "
            f"above_compaction_target={oversized} causal_builder_replays={causal_replays} "
            f"reconstructed_lineage_bytes={reconstructed_audit_bytes}; "
            "historical outcomes unchanged"
        )

        print(
            f"EVIDENCE_ARCHIVE {subject['key']} completeness_before="
            f"{json.dumps(categories_before, sort_keys=True)} "
            f"completeness_after={json.dumps(categories_after, sort_keys=True)}"
        )

    assert examined == set(invalid)
    assert attempts == manifest["totals"]["provider_call_attempts"] == 62
    assert completed == manifest["totals"]["completed_role_turns"] == 40
    print(
        f"EVIDENCE_ARCHIVE reference acceptance only: {accepted_references}/44; "
        f"historically accepted reference passes={prior_valid_reference_passes}/40; "
        f"historically invalid counterfactual reference passes={prior_invalid_reference_passes}/4; "
        "no paid replay or historical outcome mutation"
    )


if __name__ == "__main__":
    verify_frozen_evidence_archive()
