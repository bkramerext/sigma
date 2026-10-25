"""Offline pilot readiness gate. This tool never calls a model or network."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {name}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    protocol = load_module("i14_protocol", "scripts/increment14_protocol.py")
    packet = load_module("i14_packet", "scripts/increment14_agent_packet.py")
    manifest = protocol.manifest(140017, 1)

    # Validate all 12 exact source packets against their manifest hashes.
    for item in manifest["pairs"]:
        payload = packet.agent_packet(item["task_id"], item["variant"])
        if protocol.sha256(protocol.canonical_bytes(payload)) != item["packet_sha256"]:
            raise ValueError("Agent packet differs from frozen manifest packet")

    checks = {
        "task_packet_hashes": "passed",
        "paired_trials": manifest["paired_runs"],
        "planned_model_runs": manifest["total_arm_runs"],
        "manifest_is_frozen": manifest["status"] == "FROZEN" and manifest["freeze_approved"],
        "paid_runs_approved": manifest["user_approved"],
        "model_version_configured": bool(
            manifest["model_provider"] and manifest["model_exact_version"]
        ),
        "cost_cap_configured": manifest["total_usd_cap"] is not None,
        "runner_isolation_demonstrated": False,
        "baseline_and_sigma_run_adapter_tested": False,
        "two_independent_blind_graders_ready": False,
        "status": "BLOCKED_FOR_LIVE_PILOT",
        "paid_provider_calls": 0,
    }
    # Fail closed: do not accidentally claim readiness from a draft manifest.
    if checks["manifest_is_frozen"] or checks["paid_runs_approved"]:
        raise ValueError("Offline preparation unexpectedly received live authorization")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(checks, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("Offline pilot readiness inspected; real inference remains blocked.")


if __name__ == "__main__":
    main()
