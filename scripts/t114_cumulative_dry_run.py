#!/usr/bin/env python3
"""Offline planner/auditor for T114's cumulative matched-budget study.

No task text, answer key, provider SDK, credentials, or network is read. This
checks only deterministic scheduling and preservation of submitted run records.

Run:
    uv run python scripts/t114_cumulative_dry_run.py --output /tmp/t114-plan.json
    uv run python tests/t114_cumulative_dry_run.py
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
from pathlib import Path
from typing import Any

TASK_COUNT = 12
PAIR_COUNT = 12
CALLS_PER_ARM = 8
INPUT_PER_ARM = 60_000
OUTPUT_PER_ARM = 32_768
ARM_USD_CAP = 0.65
STUDY_USD_CAP = 15.60
INPUT_PRICE_PER_M = 5.00  # Conservative 12-hour cache-write rate in the draft.
OUTPUT_PRICE_PER_M = 10.00


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def plan(task_commitments: list[dict[str, str]], seed: int = 114026) -> dict[str, Any]:
    """Plan 12 pairs from curator commitments; task payloads and keys stay sealed."""
    if len(task_commitments) != TASK_COUNT:
        raise ValueError("T114 requires exactly 12 preselected task commitments")
    ids = [row.get("opaque_id", "") for row in task_commitments]
    digests = [row.get("sha256", "") for row in task_commitments]
    domains = [row.get("domain", "") for row in task_commitments]
    if len(set(ids)) != TASK_COUNT or any(not item.startswith("sealed-") for item in ids):
        raise ValueError("Task identifiers must be unique opaque sealed IDs")
    if len(set(digests)) != TASK_COUNT or any(
        len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest)
        for digest in digests
    ):
        raise ValueError("Each task requires a unique lowercase SHA-256 commitment")
    if len(set(domains)) < 6:
        raise ValueError("Task set must cover at least six curator-recorded domains")

    rng = random.Random(seed)
    pairs: list[dict[str, Any]] = []
    for row in sorted(task_commitments, key=lambda item: item["opaque_id"]):
        order = ["A", "B"]
        rng.shuffle(order)
        assignment = ["sigma_cumulative", "single_role"]
        rng.shuffle(assignment)
        pairs.append(
            {
                "pair_id": hashlib.sha256(row["opaque_id"].encode()).hexdigest()[:16],
                "task_commitment_sha256": row["sha256"],
                "domain": row["domain"],
                "arm_codes": {"A": assignment[0], "B": assignment[1]},
                "execution_order": order,
            }
        )
    rng.shuffle(pairs)
    per_arm_estimate = (
        INPUT_PER_ARM * INPUT_PRICE_PER_M + OUTPUT_PER_ARM * OUTPUT_PRICE_PER_M
    ) / 1_000_000
    if per_arm_estimate > ARM_USD_CAP or per_arm_estimate * PAIR_COUNT * 2 > STUDY_USD_CAP:
        raise ValueError("Frozen token ceilings exceed the proposed dollar authorization sheet")
    return {
        "schema_version": 1,
        "status": "DRAFT_NOT_FROZEN",
        "provider_calls_authorized": 0,
        "seed": seed,
        "pair_count": PAIR_COUNT,
        "arm_count": PAIR_COUNT * 2,
        "task_count": TASK_COUNT,
        "task_manifest_sha256": hashlib.sha256(_canonical(task_commitments)).hexdigest(),
        "ceilings": {
            "calls_per_arm": CALLS_PER_ARM,
            "input_tokens_per_arm": INPUT_PER_ARM,
            "output_tokens_per_arm": OUTPUT_PER_ARM,
            "arm_usd_cap": ARM_USD_CAP,
            "study_usd_cap": STUDY_USD_CAP,
            "estimated_worst_case_usd_per_arm": round(per_arm_estimate, 6),
            "estimated_worst_case_usd_study": round(per_arm_estimate * PAIR_COUNT * 2, 6),
        },
        "pairs": pairs,
    }


def audit_records(planned: dict[str, Any], records: list[dict[str, Any]]) -> dict[str, Any]:
    """Check that all arms remain represented, including failed/partial records."""
    expected = {(pair["pair_id"], code) for pair in planned["pairs"] for code in ("A", "B")}
    actual = [(row.get("pair_id"), row.get("arm_code")) for row in records]
    if len(actual) != len(expected) or set(actual) != expected:
        raise ValueError("Every planned arm must have exactly one retained record")
    allowed_status = {"complete", "failed", "incomplete", "stopped"}
    if any(row.get("status") not in allowed_status for row in records):
        raise ValueError("Run status is missing or invalid; preserve failure status")
    return {
        "planned_arms": len(expected),
        "retained_arms": len(records),
        "status_counts": {
            status: sum(row["status"] == status for row in records)
            for status in sorted(allowed_status)
        },
        "provider_calls_authorized": 0,
        "research_result": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=114026)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    # Opaque synthetic commitments demonstrate scheduling only. They are not
    # benchmark problems and are never submitted to a model.
    domains = [f"domain-{index % 6 + 1}" for index in range(TASK_COUNT)]
    rows = [
        {
            "opaque_id": f"sealed-{index + 1:02d}",
            "domain": domains[index],
            "sha256": hashlib.sha256(f"offline-fixture-{index + 1}".encode()).hexdigest(),
        }
        for index in range(TASK_COUNT)
    ]
    result = plan(rows, args.seed)
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")


if __name__ == "__main__":
    main()
