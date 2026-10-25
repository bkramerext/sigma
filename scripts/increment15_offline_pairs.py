#!/usr/bin/env python3
"""Increment 15 offline paired-run transport test. No network, model or credentials.

This exercises deterministic scheduling, exact packet hashes, capped records,
transcript audit and pair completeness. It is NOT a live runner or isolation proof.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    if spec is None or spec.loader is None:
        raise RuntimeError("Missing local module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def dry_run() -> dict:
    protocol = load("protocol15", "scripts/increment14_protocol.py")
    packets = load("packets15", "scripts/increment14_agent_packet.py")
    audit = load("audit15", "scripts/increment14_audit.py")
    planned = protocol.manifest(140017, 3)
    # These model identifiers are fixture labels and have NO authorization
    # significance. Keep the frozen protocol ceilings unchanged in the audit.
    frozen = dict(
        planned,
        status="FROZEN",
        freeze_approved=True,
        user_approved=True,
        model_provider="offline-fixture",
        model_exact_version="offline-only",
    )
    records = []
    for pair in planned["pairs"]:
        payload = packets.agent_packet(pair["task_id"], pair["variant"])
        digest = protocol.sha256(protocol.canonical_bytes(payload))
        if digest != pair["packet_sha256"]:
            raise ValueError("Packet mismatch")
        for arm in pair["execution_order"]:
            synthetic = {
                "kind": "synthetic-not-a-model",
                "arm": arm,
                "task": pair["task_id"],
                "variant": pair["variant"],
                "message": "No inference performed",
            }
            transcript = protocol.canonical_bytes({"request": payload, "response": synthetic})
            record = {
                "task_id": pair["task_id"],
                "variant": pair["variant"],
                "replicate": pair["replicate"],
                "arm_code": arm,
                "schedule_position": len(records),
                "executed_arm": pair["arm_assignment"][arm],
                "packet_sha256": digest,
                "model_provider": "offline-fixture",
                "model_exact_version": "offline-only",
                "total_tokens": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "call_usage": [],
                "model_calls": 0,
                "tool_calls": 0,
                "elapsed_seconds": 0,
                "cost_usd": 0,
                "transcript_sha256": hashlib.sha256(transcript).hexdigest(),
                "tool_audit_sha256": hashlib.sha256(b"[]").hexdigest(),
                "normalized_submission": audit._BLINDING.normalize_submission(
                    {
                        "conclusion": "synthetic offline fixture",
                        "reasoning": "no model inference performed",
                        "challenge": "not applicable",
                        "evidence": "fixture only",
                        "uncertainty": "not research evidence",
                        "next_test": "none",
                    },
                    arm="single_role",
                ),
                "schema_truncation_fields": [],
                "schema_validation_errors": [],
                "scores": {d: 0 for d in audit.DIMENSIONS},
                "scorer_reviews": [
                    {
                        "grader_id": "fixture-grader-1",
                        "scores": {d: 0 for d in audit.DIMENSIONS},
                        "task_key_pass": False,
                        "arm_guess": "uncertain",
                        "guess_confidence": 0,
                    },
                    {
                        "grader_id": "fixture-grader-2",
                        "scores": {d: 0 for d in audit.DIMENSIONS},
                        "task_key_pass": False,
                        "arm_guess": "uncertain",
                        "guess_confidence": 0,
                    },
                ],
                "critical_integrity_failure": False,
            }
            record["submission_sha256"] = audit._BLINDING.digest_submission(
                record["normalized_submission"]
            )
            records.append(record)
    # Adversarial fixture mutations must fail closed, not silently score a win.
    from copy import deepcopy

    def must_reject(change):
        altered = deepcopy(records)
        changed_manifest = deepcopy(frozen)
        change(changed_manifest, altered)
        try:
            audit.check_trial_records(changed_manifest, altered)
        except (ValueError, KeyError):
            rejected_mutations.append(None)
            return
        raise AssertionError("Unsafe experiment record was accepted")

    rejected_mutations: list[None] = []
    must_reject(lambda m, r: r.pop())
    must_reject(lambda m, r: r.append(deepcopy(r[0])))
    must_reject(lambda m, r: r[0].update(packet_sha256="other-packet"))
    must_reject(lambda m, r: r[0].update(model_calls=5))
    must_reject(lambda m, r: r[0].update(total_tokens=64001))
    must_reject(lambda m, r: r[0].update(input_tokens=48001, total_tokens=48001))
    must_reject(lambda m, r: r[0].update(output_tokens=16001, total_tokens=16001))
    must_reject(lambda m, r: r[0].update(input_tokens=1))
    must_reject(
        lambda m, r: r[0].update(
            call_usage=[{"input_tokens": 12001, "output_tokens": 0}],
            model_calls=1,
            input_tokens=12001,
            total_tokens=12001,
        )
    )
    must_reject(lambda m, r: r[0].update(cost_usd=0.56))
    must_reject(lambda m, r: r[0].update(transcript_sha256=""))
    must_reject(lambda m, r: r[0].update(scorer_saw_arm_identity=True))
    must_reject(lambda m, r: m.update(user_approved=False))
    must_reject(lambda m, r: m.update(status="DRAFT_NOT_FROZEN"))
    must_reject(lambda m, r: m.update(schema_version=2))
    must_reject(lambda m, r: m["pairs"].pop())
    must_reject(lambda m, r: m["pairs"][0].update(replicate=99))
    must_reject(lambda m, r: m.update(seed=140018))
    must_reject(lambda m, r: m.update(per_arm_output_token_cap=16001))
    must_reject(lambda m, r: m.update(protocol_script_sha256="tampered"))
    must_reject(lambda m, r: r[1].update(schedule_position=r[0]["schedule_position"]))
    must_reject(lambda m, r: m.update(audit_script_sha256="tampered"))
    must_reject(lambda m, r: m.update(evaluator_key_sha256="tampered"))

    result = audit.check_trial_records(frozen, records)
    if result != {
        "pairs": 36,
        "cost_usd": 0,
        "integrity_failures": 0,
        "clipped_submissions": 0,
        "schema_truncation_fields": 0,
        "schema_validation_errors": 0,
        "blinding_guess_accuracy": None,
    }:
        raise AssertionError("Unexpected paired-run summary")
    differences = audit.paired_score_differences(frozen, records)
    cluster_summary = audit.task_cluster_summary(differences)
    pass_cluster_summary = audit.task_cluster_summary(
        differences, outcome_field="task_key_pass_rate_diff"
    )
    if cluster_summary["independent_units"] != 6 or len(differences) != 36:
        raise AssertionError("Unexpected task-cluster analysis summary")
    if pass_cluster_summary["independent_units"] != 6:
        raise AssertionError("Unexpected task-key pass analysis summary")
    return {
        "kind": "OFFLINE_FIXTURE_ONLY",
        "model_calls": 0,
        "spend_usd": 0,
        "records": len(records),
        "pairs": result["pairs"],
        "unsafe_mutations_rejected": len(rejected_mutations),
        "audit_passed": True,
        "real_runner_isolation_verified": False,
        "live_pilot_authorized": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    outcome = dry_run()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(outcome, indent=2, sort_keys=True) + "\n")
    print("PASS 72 synthetic records, 36 matched pairs, zero model calls/cost")


if __name__ == "__main__":
    main()
