"""Offline, reference-only regression over the existing five-subject STAGING release.

Do not emit archived payloads, run provider calls, or modify any saved outcome.
The counterfactual is restricted to evidence present in the historical request;
it is not a reconstruction of omitted history or a full scientific validation.
"""

from __future__ import annotations

import gzip
import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from sigma import research_sessions
from sigma.projects import ProjectError
from sigma.research_context_budget import finalize_dispatch_evidence
from sigma.research_evidence_catalog import (
    Catalog,
    EvidenceContext,
    artifact_permissions,
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
        artifacts = {row["id"]: row for row in session["artifacts"]}
        original_duties = original_coverage = original_peers = 0
        new_duties = new_coverage = new_peers = byte_delta = 0
        max_catalog_bytes = oversized = reference_passes = responses_checked = 0
        for step in session["steps"]:
            context = _archived_context(step)
            original_catalog = build_catalog(context)
            before = _coverage(context, original_catalog)
            original_duties += before[0]
            original_coverage += before[1]
            original_peers += before[2]
            revised = _counterfactual(context, artifacts)
            catalog = revised["evidence_catalog"]
            assert catalog == build_catalog(revised)
            assert revised == _counterfactual(context, artifacts)
            after = _coverage(revised, catalog)
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
            f"aggregate_byte_delta={byte_delta} max_catalog_bytes={max_catalog_bytes} "
            f"above_compaction_target={oversized}; historical outcomes unchanged"
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
