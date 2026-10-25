#!/usr/bin/env python3
"""Offline Increment 14 preregistration validator. Never invokes a model/provider."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TASKS = ROOT / "docs/evaluations/increment14/tasks.json"
EXPECTED = {"E1", "S1", "C1", "P1", "M1", "M2"}
DOMAINS = {
    "experimental_design",
    "source_criticism",
    "constrained_engineering",
    "scenario_reasoning",
    "formal_mathematics",
}


def canonical_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode(
        "utf-8"
    )


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def validate() -> dict:
    data = json.loads(TASKS.read_text(encoding="utf-8"))
    assert data["schema_version"] == 1
    assert data["task_count"] == 6 and data["variants_per_task"] == 2
    assert len(data["tasks"]) == 6
    assert {x["id"] for x in data["tasks"]} == EXPECTED
    assert {x["domain"] for x in data["tasks"]} == DOMAINS
    for row in data["tasks"]:
        assert set(row) == {
            "id",
            "domain",
            "question",
            "evidence_present",
            "evidence_withheld",
            "scoring_dimensions",
        }
        assert len(row["question"]) >= 90
        assert row["evidence_present"]["packet"] != row["evidence_withheld"]["packet"]
        assert row["scoring_dimensions"]
        for variant in ("evidence_present", "evidence_withheld"):
            packet = row[variant]["packet"]
            assert len(packet) >= 50
            assert not any(
                term in packet.lower()
                for term in ("answer key:", "hidden rubric:", "correct answer:")
            )
    return data


def manifest(seed: int, repetitions: int) -> dict:
    assert 1 <= repetitions <= 5
    data = validate()
    rng = random.Random(seed)
    pairs = []
    for t in data["tasks"]:
        for variant in ("evidence_present", "evidence_withheld"):
            for repeat in range(repetitions):
                order = ["A", "B"]  # A/B are internal arm codes; hidden from graders.
                rng.shuffle(order)
                assignment = ["sigma", "single_role"]
                rng.shuffle(assignment)
                packet = {
                    "instruction": data["global_instruction"],
                    "question": t["question"],
                    "evidence": t[variant]["packet"],
                }
                pairs.append(
                    {
                        "task_id": t["id"],
                        "variant": variant,
                        "replicate": repeat,
                        "packet_sha256": sha256(canonical_bytes(packet)),
                        "execution_order": order,
                        "arm_assignment": dict(zip(("A", "B"), assignment, strict=True)),
                    }
                )
    rng.shuffle(pairs)
    return {
        "schema_version": 2,
        "status": "DRAFT_NOT_FROZEN",
        "seed": seed,
        "replicates_per_task_variant": repetitions,
        "paired_runs": len(pairs),
        "total_arm_runs": 2 * len(pairs),
        "task_file_sha256": sha256(TASKS.read_bytes()),
        "canonical_tasks_sha256": sha256(canonical_bytes(data)),
        "protocol_script_sha256": sha256(Path(__file__).read_bytes()),
        "agent_packet_script_sha256": sha256(
            (ROOT / "scripts/increment14_agent_packet.py").read_bytes()
        ),
        "analysis_unit": "task_cluster",
        "independent_task_count": len(data["tasks"]),
        "scoring_schema": "sigma-blind-submission-v1",
        "scoring_schema_sha256": sha256((ROOT / "scripts/increment14_blinding.py").read_bytes()),
        "pairs": pairs,
        # Proposed ceilings only. Provider/model selection, a priced estimate,
        # protocol freeze, and owner authorization remain separate gates.
        "model_provider": None,
        "model_exact_version": None,
        "per_arm_token_cap": 64000,
        "per_arm_input_token_cap": 48000,
        "per_arm_output_token_cap": 16000,
        "per_call_input_token_cap": 12000,
        "per_call_output_token_cap": 4000,
        "per_arm_model_call_cap": 4,
        "per_arm_tool_call_cap": 1,
        "per_arm_wall_seconds": 600,
        "per_arm_usd_cap": 0.55,
        "total_usd_cap": 0.55 * 2 * len(pairs),
        "user_approved": False,
        "freeze_approved": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=140017)
    parser.add_argument("--replicates", type=int, default=3)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = manifest(args.seed, args.replicates)
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")


if __name__ == "__main__":
    main()
