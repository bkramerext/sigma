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
    planned = protocol.manifest(140017, 1)
    # These local placeholder caps have NO authorization significance.
    frozen = dict(
        planned,
        status="FROZEN",
        freeze_approved=True,
        user_approved=True,
        model_provider="offline-fixture",
        model_exact_version="offline-only",
        per_arm_token_cap=200,
        per_arm_input_token_cap=100,
        per_arm_output_token_cap=100,
        per_call_input_token_cap=100,
        per_call_output_token_cap=100,
        per_arm_model_call_cap=2,
        per_arm_tool_call_cap=0,
        per_arm_wall_seconds=60,
        per_arm_usd_cap=0,
        total_usd_cap=0,
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
                "scores": {d: 0 for d in audit.DIMENSIONS},
                "critical_integrity_failure": False,
            }
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
            return
        raise AssertionError("Unsafe experiment record was accepted")

    must_reject(lambda m, r: r.pop())
    must_reject(lambda m, r: r.append(deepcopy(r[0])))
    must_reject(lambda m, r: r[0].update(packet_sha256="other-packet"))
    must_reject(lambda m, r: r[0].update(model_calls=3))
    must_reject(lambda m, r: r[0].update(total_tokens=201))
    must_reject(lambda m, r: r[0].update(input_tokens=101, total_tokens=101))
    must_reject(lambda m, r: r[0].update(output_tokens=101, total_tokens=101))
    must_reject(lambda m, r: r[0].update(input_tokens=1))
    must_reject(
        lambda m, r: r[0].update(
            call_usage=[{"input_tokens": 101, "output_tokens": 0}],
            model_calls=1,
            input_tokens=101,
            total_tokens=101,
        )
    )
    must_reject(lambda m, r: r[0].update(cost_usd=0.01))
    must_reject(lambda m, r: r[0].update(transcript_sha256=""))
    must_reject(lambda m, r: r[0].update(scorer_saw_arm_identity=True))
    must_reject(lambda m, r: m.update(user_approved=False))
    must_reject(lambda m, r: m.update(status="DRAFT_NOT_FROZEN"))

    result = audit.check_trial_records(frozen, records)
    if result != {"pairs": 12, "cost_usd": 0, "integrity_failures": 0}:
        raise AssertionError("Unexpected paired-run summary")
    return {
        "kind": "OFFLINE_FIXTURE_ONLY",
        "model_calls": 0,
        "spend_usd": 0,
        "records": len(records),
        "pairs": result["pairs"],
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
    print("PASS 24 synthetic records, 12 matched pairs, zero model calls/cost")


if __name__ == "__main__":
    main()
