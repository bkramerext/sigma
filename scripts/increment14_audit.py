"""Fail-closed offline validation of a paired, blinded research evaluation.

No provider calls. Rejects absent, duplicated, asymmetric or unblinded records.
"""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Any

DIMENSIONS = (
    "correctness",
    "objection_uptake",
    "evidence_integrity",
    "calibration",
    "next_experiment",
)
WEIGHTS = (0.30, 0.20, 0.20, 0.15, 0.15)


def check_trial_records(manifest: dict[str, Any], records: list[dict[str, Any]]) -> dict[str, Any]:
    if manifest.get("status") != "FROZEN" or not manifest.get("freeze_approved"):
        raise ValueError("Unfrozen protocol")
    if not manifest.get("user_approved"):
        raise ValueError("User has not authorized the run")
    caps = {
        k: manifest.get(k)
        for k in (
            "model_provider",
            "model_exact_version",
            "per_arm_token_cap",
            "per_arm_input_token_cap",
            "per_arm_output_token_cap",
            "per_call_input_token_cap",
            "per_call_output_token_cap",
            "per_arm_model_call_cap",
            "per_arm_tool_call_cap",
            "per_arm_wall_seconds",
            "per_arm_usd_cap",
            "total_usd_cap",
        )
    }
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
        if (
            r["model_provider"] != caps["model_provider"]
            or r["model_exact_version"] != caps["model_exact_version"]
        ):
            raise ValueError("Model mismatch")
        for field, cap in (
            ("total_tokens", "per_arm_token_cap"),
            ("input_tokens", "per_arm_input_token_cap"),
            ("output_tokens", "per_arm_output_token_cap"),
            ("model_calls", "per_arm_model_call_cap"),
            ("tool_calls", "per_arm_tool_call_cap"),
            ("elapsed_seconds", "per_arm_wall_seconds"),
            ("cost_usd", "per_arm_usd_cap"),
        ):
            value = r[field]
            if field in (
                "total_tokens",
                "input_tokens",
                "output_tokens",
                "model_calls",
                "tool_calls",
            ):
                valid_number = isinstance(value, int) and not isinstance(value, bool)
            else:
                valid_number = (
                    isinstance(value, (int, float))
                    and not isinstance(value, bool)
                    and math.isfinite(value)
                )
            if not valid_number or value < 0 or value > caps[cap]:
                raise ValueError(f"Invalid or exceeded {field}")
        if r["total_tokens"] != r["input_tokens"] + r["output_tokens"]:
            raise ValueError("Aggregate tokens do not match input plus output")
        call_usage = r["call_usage"]
        if not isinstance(call_usage, list) or len(call_usage) != r["model_calls"]:
            raise ValueError("Per-call usage does not match model-call count")
        for usage in call_usage:
            if (
                not isinstance(usage, dict)
                or not isinstance(usage.get("input_tokens"), int)
                or not isinstance(usage.get("output_tokens"), int)
                or isinstance(usage.get("input_tokens"), bool)
                or isinstance(usage.get("output_tokens"), bool)
                or usage["input_tokens"] < 0
                or usage["output_tokens"] < 0
                or usage["input_tokens"] > caps["per_call_input_token_cap"]
                or usage["output_tokens"] > caps["per_call_output_token_cap"]
            ):
                raise ValueError("Invalid or exceeded per-call token ceiling")
        if sum(x["input_tokens"] for x in call_usage) != r["input_tokens"]:
            raise ValueError("Per-call input usage does not match aggregate")
        if sum(x["output_tokens"] for x in call_usage) != r["output_tokens"]:
            raise ValueError("Per-call output usage does not match aggregate")
        if not r.get("transcript_sha256") or not r.get("tool_audit_sha256"):
            raise ValueError("Missing audit trail")
        score = r["scores"]
        if set(score) != set(DIMENSIONS):
            raise ValueError("Missing or unknown score dimension")
        if any(
            not isinstance(score[d], int) or isinstance(score[d], bool) or not 0 <= score[d] <= 4
            for d in DIMENSIONS
        ):
            raise ValueError("Invalid blind score")
        if "arm_identity" in r or "system_role" in r or r.get("scorer_saw_arm_identity"):
            raise ValueError("Unblinded scoring record")
        seen[key][arm] = r
        total_cost += r["cost_usd"]
    if total_cost > caps["total_usd_cap"]:
        raise ValueError("Total spending cap exceeded")
    if set(seen) != set(pairs) or any(set(rows) != {"A", "B"} for rows in seen.values()):
        raise ValueError("Missing paired arm run")
    return {
        "pairs": len(pairs),
        "cost_usd": total_cost,
        "integrity_failures": sum(bool(r.get("critical_integrity_failure")) for r in records),
    }


def weighted_score(scores: dict[str, int]) -> float:
    if set(scores) != set(DIMENSIONS):
        raise ValueError("Invalid score dimensions")
    return sum(scores[d] * w for d, w in zip(DIMENSIONS, WEIGHTS))
