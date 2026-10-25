"""Fail-closed offline validation of a paired, blinded research evaluation.

No provider calls. Rejects absent, duplicated, asymmetric or unblinded records.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any

DIMENSIONS = ("correctness", "objection_uptake", "evidence_integrity", "calibration", "next_experiment")
WEIGHTS = (0.30, 0.20, 0.20, 0.15, 0.15)

def check_trial_records(manifest: dict[str, Any], records: list[dict[str, Any]]) -> dict[str, Any]:
    if manifest.get("status") != "FROZEN" or not manifest.get("freeze_approved"):
        raise ValueError("Unfrozen protocol")
    if not manifest.get("user_approved"):
        raise ValueError("User has not authorized the run")
    caps = {k: manifest.get(k) for k in (
        "model_provider", "model_exact_version", "per_arm_token_cap",
        "per_arm_model_call_cap", "per_arm_tool_call_cap",
        "per_arm_wall_seconds", "per_arm_usd_cap", "total_usd_cap")}
    if any(v is None for v in caps.values()):
        raise ValueError("Missing cap or provider")
    pairs = {(p["task_id"], p["variant"], p["replicate"]): p for p in manifest["pairs"]}
    if len(pairs) != len(manifest["pairs"]):
        raise ValueError("Duplicate manifest pair")
    seen: dict[tuple[str, str, int], dict[str, dict[str, Any]]] = defaultdict(dict)
    total_cost = 0.0
    for r in records:
        key = (r["task_id"], r["variant"], r["replicate"])
        arm = r["arm_code"]
        if key not in pairs or arm not in ("A", "B") or arm in seen[key]:
            raise ValueError("Unknown or repeated run")
        if r["packet_sha256"] != pairs[key]["packet_sha256"]:
            raise ValueError("Task packet mismatch")
        if r["model_provider"] != caps["model_provider"] or r["model_exact_version"] != caps["model_exact_version"]:
            raise ValueError("Model mismatch")
        for field, cap in (("total_tokens", "per_arm_token_cap"), ("model_calls", "per_arm_model_call_cap"),
                           ("tool_calls", "per_arm_tool_call_cap"), ("elapsed_seconds", "per_arm_wall_seconds"),
                           ("cost_usd", "per_arm_usd_cap")):
            value = r[field]
            if not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0 or value > caps[cap]:
                raise ValueError(f"Invalid or exceeded {field}")
        if not r.get("transcript_sha256") or not r.get("tool_audit_sha256"):
            raise ValueError("Missing audit trail")
        score = r["scores"]
        if set(score) != set(DIMENSIONS):
            raise ValueError("Missing or unknown score dimension")
        if any(not isinstance(score[d], int) or isinstance(score[d], bool) or not 0 <= score[d] <= 4 for d in DIMENSIONS):
            raise ValueError("Invalid blind score")
        if "arm_identity" in r or "system_role" in r or r.get("scorer_saw_arm_identity"):
            raise ValueError("Unblinded scoring record")
        seen[key][arm] = r
        total_cost += r["cost_usd"]
    if total_cost > caps["total_usd_cap"]:
        raise ValueError("Total spending cap exceeded")
    if set(seen) != set(pairs) or any(set(rows) != {"A", "B"} for rows in seen.values()):
        raise ValueError("Missing paired arm run")
    return {"pairs": len(pairs), "cost_usd": total_cost, "integrity_failures":
            sum(bool(r.get("critical_integrity_failure")) for r in records)}


def weighted_score(scores: dict[str, int]) -> float:
    if set(scores) != set(DIMENSIONS):
        raise ValueError("Invalid score dimensions")
    return sum(scores[d] * w for d, w in zip(DIMENSIONS, WEIGHTS))
