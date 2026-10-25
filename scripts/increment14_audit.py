"""Fail-closed offline validation of a paired, blinded research evaluation.

No provider calls. Rejects absent, duplicated, asymmetric or unblinded records.
"""

from __future__ import annotations

import importlib.util
import math
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any

_PROTOCOL_SPEC = importlib.util.spec_from_file_location(
    "increment14_protocol", Path(__file__).with_name("increment14_protocol.py")
)
assert _PROTOCOL_SPEC and _PROTOCOL_SPEC.loader
_PROTOCOL = importlib.util.module_from_spec(_PROTOCOL_SPEC)
_PROTOCOL_SPEC.loader.exec_module(_PROTOCOL)

_BLINDING_SPEC = importlib.util.spec_from_file_location(
    "increment14_blinding", Path(__file__).with_name("increment14_blinding.py")
)
assert _BLINDING_SPEC and _BLINDING_SPEC.loader
_BLINDING = importlib.util.module_from_spec(_BLINDING_SPEC)
_BLINDING_SPEC.loader.exec_module(_BLINDING)

DIMENSIONS = (
    "task_outcome",
    "reasoning_validity",
    "calibration",
    "evidence_quality",
    "useful_next_test",
)
WEIGHTS = (0.35, 0.30, 0.15, 0.10, 0.10)


def check_frozen_protocol_manifest(manifest: dict[str, Any]) -> None:
    """Require a full, source-matched T114 v2 design before auditing its runs."""
    if manifest.get("schema_version") != 2:
        raise ValueError("Unsupported or missing frozen protocol schema")
    seed = manifest.get("seed")
    if not isinstance(seed, int) or isinstance(seed, bool):
        raise TypeError("Invalid scheduling seed")
    expected = _PROTOCOL.manifest(seed, 3)
    structural_fields = (
        "schema_version",
        "seed",
        "replicates_per_task_variant",
        "paired_runs",
        "total_arm_runs",
        "task_file_sha256",
        "canonical_tasks_sha256",
        "protocol_script_sha256",
        "agent_packet_script_sha256",
        "analysis_unit",
        "independent_task_count",
        "scoring_schema",
        "scoring_schema_sha256",
        "pairs",
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
    if any(manifest.get(field) != expected[field] for field in structural_fields):
        raise ValueError("Manifest differs from the complete current T114 protocol design")


def check_trial_records(
    manifest: dict[str, Any],
    records: list[dict[str, Any]],
    *,
    allow_partial_fixture: bool = False,
) -> dict[str, Any]:
    """Audit a complete T114 run; partial manifests are only for unit fixtures."""
    if not allow_partial_fixture:
        check_frozen_protocol_manifest(manifest)
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
    schedule = []
    for pair in manifest["pairs"]:
        order = pair.get("execution_order")
        if not isinstance(order, list) or len(order) != 2 or set(order) != {"A", "B"}:
            raise ValueError("Missing or malformed randomized execution order")
        key = (pair["task_id"], pair["variant"], pair["replicate"])
        schedule.extend((key, arm) for arm in order)
    seen: dict[tuple[str, str, int], dict[str, dict[str, Any]]] = defaultdict(dict)
    total_cost = 0.0
    schema_truncation_fields = 0
    schema_validation_errors = 0
    non_uncertain_guesses = 0
    correct_arm_guesses = 0
    for r in records:
        key = (r["task_id"], r["variant"], r["replicate"])
        arm = r["arm_code"]
        position = r.get("schedule_position")
        if (
            not isinstance(position, int)
            or isinstance(position, bool)
            or not 0 <= position < len(schedule)
            or schedule[position] != (key, arm)
        ):
            raise ValueError("Recorded execution position differs from randomized schedule")
        if key not in pairs or arm not in ("A", "B") or arm in seen[key]:
            raise ValueError("Unknown or repeated run")
        if r["packet_sha256"] != pairs[key]["packet_sha256"]:
            raise ValueError("Task packet mismatch")
        assignment = pairs[key].get("arm_assignment")
        if not isinstance(assignment, dict) or set(assignment) != {"A", "B"}:
            raise ValueError("Missing isolated arm assignment map")
        if assignment.get(arm) != r.get("executed_arm"):
            raise ValueError("Executed arm does not match the sealed assignment map")
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
        for field in ("schema_truncation_fields", "schema_validation_errors"):
            if not isinstance(r.get(field), list) or any(
                not isinstance(value, str) for value in r[field]
            ):
                raise ValueError(f"Missing or malformed {field}")
        schema_truncation_fields += len(r["schema_truncation_fields"])
        schema_validation_errors += len(r["schema_validation_errors"])
        submission = r.get("normalized_submission")
        if (
            not isinstance(submission, dict)
            or submission.get("schema") != "sigma-blind-submission-v1"
        ):
            raise ValueError("Missing common normalized submission")
        if set(submission) != {"schema", *_BLINDING.FIELDS, "clipped_fields"}:
            raise ValueError("Invalid common submission shape")
        if r.get("submission_sha256") != _BLINDING.digest_submission(submission):
            raise ValueError("Normalized submission digest mismatch")
        if any(
            not isinstance(submission[field], str) or len(submission[field]) > limit
            for field, limit in _BLINDING.FIELDS.items()
        ):
            raise ValueError("Normalized submission violates shared output limits")
        if not isinstance(submission["clipped_fields"], list) or any(
            field not in _BLINDING.FIELDS for field in submission["clipped_fields"]
        ):
            raise ValueError("Invalid clipping metadata")
        score = r["scores"]
        if set(score) != set(DIMENSIONS):
            raise ValueError("Missing or unknown score dimension")
        if any(
            not isinstance(score[d], int) or isinstance(score[d], bool) or not 0 <= score[d] <= 4
            for d in DIMENSIONS
        ):
            raise ValueError("Invalid blind score")
        check_scorer_reviews(r.get("scorer_reviews"))
        for review in r["scorer_reviews"]:
            if review["arm_guess"] != "uncertain":
                non_uncertain_guesses += 1
                correct_arm_guesses += review["arm_guess"] == r["executed_arm"]
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
        "clipped_submissions": sum(
            bool(r["normalized_submission"]["clipped_fields"]) for r in records
        ),
        "schema_truncation_fields": schema_truncation_fields,
        "schema_validation_errors": schema_validation_errors,
        "blinding_guess_accuracy": (
            correct_arm_guesses / non_uncertain_guesses if non_uncertain_guesses else None
        ),
    }


def weighted_score(scores: dict[str, int]) -> float:
    if set(scores) != set(DIMENSIONS):
        raise ValueError("Invalid score dimensions")
    return sum(scores[d] * w for d, w in zip(DIMENSIONS, WEIGHTS))


def check_scorer_reviews(reviews: list[dict[str, Any]]) -> dict[str, Any]:
    """Validate two independently identified, blinded artifact reviews."""
    if not isinstance(reviews, list) or len(reviews) != 2:
        raise ValueError("Exactly two independent scorer reviews are required")
    grader_ids: set[str] = set()
    scores: list[float] = []
    guesses: dict[str, int] = {"sigma": 0, "single_role": 0, "uncertain": 0}
    for review in reviews:
        if not isinstance(review, dict) or set(review) != {
            "grader_id",
            "scores",
            "task_key_pass",
            "arm_guess",
            "guess_confidence",
        }:
            raise ValueError("Invalid scorer review shape")
        grader_id = review["grader_id"]
        if not isinstance(grader_id, str) or not grader_id or grader_id in grader_ids:
            raise ValueError("Scorers must have distinct identities")
        grader_ids.add(grader_id)
        if not isinstance(review["task_key_pass"], bool):
            raise TypeError("Invalid task-key pass endpoint")
        guess = review["arm_guess"]
        if guess not in guesses:
            raise ValueError("Invalid post-score arm guess")
        confidence = review["guess_confidence"]
        if (
            not isinstance(confidence, int)
            or isinstance(confidence, bool)
            or not 0 <= confidence <= 3
        ):
            raise ValueError("Invalid arm-guess confidence")
        score = review["scores"]
        if set(score) != set(DIMENSIONS) or any(
            not isinstance(score[d], int) or isinstance(score[d], bool) or not 0 <= score[d] <= 4
            for d in DIMENSIONS
        ):
            raise ValueError("Invalid scorer dimensions")
        guesses[guess] += 1
        scores.append(weighted_score(score))
    return {
        "scorer_count": 2,
        "weighted_scores": scores,
        "task_key_passes": sum(bool(r["task_key_pass"]) for r in reviews),
        "arm_guesses": guesses,
    }


def task_cluster_summary(
    paired_differences: list[dict[str, Any]],
    *,
    outcome_field: str = "sigma_minus_single_role",
) -> dict[str, Any]:
    """Summarize repeats/variants within six tasks; tasks, not pairs, are n."""
    by_task: dict[str, list[float]] = defaultdict(list)
    for item in paired_differences:
        value = item[outcome_field]
        if (
            not isinstance(value, (int, float))
            or isinstance(value, bool)
            or not math.isfinite(value)
        ):
            raise ValueError("Invalid paired difference")
        by_task[str(item["task_id"])].append(float(value))
    if len(by_task) != 6 or any(not values for values in by_task.values()):
        raise ValueError("Cluster summary requires all six underlying tasks")
    task_means = {task: statistics.mean(values) for task, values in sorted(by_task.items())}
    values = list(task_means.values())
    mean = statistics.mean(values)
    sd = statistics.stdev(values)
    # Two-sided 95% Student-t critical value with five task-level degrees of freedom.
    half_width = 2.5705818356 * sd / math.sqrt(6)
    sign_flip_extreme = 0
    observed = abs(mean)
    for mask in range(1 << 6):
        permuted = statistics.mean(
            value if mask & (1 << index) else -value for index, value in enumerate(values)
        )
        if abs(permuted) >= observed - 1e-12:
            sign_flip_extreme += 1
    return {
        "independent_units": 6,
        "within_task_pair_count": len(paired_differences),
        "task_cluster_means": task_means,
        "mean_task_effect": mean,
        "task_level_sd": sd,
        "task_level_95pct_t_interval": [mean - half_width, mean + half_width],
        "task_level_sign_flip_two_sided_p_sensitivity": sign_flip_extreme / 64,
        "interpretation": "exploratory; six tasks do not support broad generalization",
    }


def paired_score_differences(
    manifest: dict[str, Any], records: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Compute per-pair mean-score effects after the private map is unsealed."""
    pairs = {(p["task_id"], p["variant"], p["replicate"]): p for p in manifest.get("pairs", [])}
    grouped: dict[tuple[str, str, int], dict[str, tuple[float, float]]] = defaultdict(dict)
    for record in records:
        key = (record["task_id"], record["variant"], record["replicate"])
        pair = pairs.get(key)
        if pair is None:
            raise ValueError("Run is absent from the frozen pair manifest")
        assignment = pair.get("arm_assignment", {})
        arm = assignment.get(record.get("arm_code"))
        if arm not in {"sigma", "single_role"}:
            raise ValueError("Cannot analyze without the sealed arm map")
        reviews = check_scorer_reviews(record.get("scorer_reviews"))
        if arm in grouped[key]:
            raise ValueError("Duplicate arm score in pair")
        grouped[key][arm] = (
            statistics.mean(reviews["weighted_scores"]),
            reviews["task_key_passes"] / reviews["scorer_count"],
        )
    if set(grouped) != set(pairs) or any(
        set(scores) != {"sigma", "single_role"} for scores in grouped.values()
    ):
        raise ValueError("Cannot analyze incomplete pairs")
    return [
        {
            "task_id": key[0],
            "variant": key[1],
            "replicate": key[2],
            "sigma_minus_single_role": scores["sigma"][0] - scores["single_role"][0],
            "task_key_pass_rate_diff": scores["sigma"][1] - scores["single_role"][1],
        }
        for key, scores in sorted(grouped.items())
    ]
