"""Offline agent-only packet exporter. No evaluator-side answer keys are read."""

from __future__ import annotations

import argparse
import json
import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = spec_from_file_location("protocol14", ROOT / "scripts/increment14_protocol.py")
assert spec is not None and spec.loader is not None
protocol = module_from_spec(spec)
sys.modules[spec.name] = protocol
spec.loader.exec_module(protocol)


def agent_packet(task_id: str, variant: str) -> dict[str, str]:
    if variant not in ("evidence_present", "evidence_withheld"):
        raise ValueError("Unknown evidence variant")
    tasks = protocol.validate()
    matches = [t for t in tasks["tasks"] if t["id"] == task_id]
    if len(matches) != 1:
        raise ValueError("Unknown or duplicate task")
    task = matches[0]
    # Positive allowlist: exclude grading dimensions, reference answers,
    # arm order and all evaluator-side material. This is not an access-control boundary.
    return {
        "instruction": tasks["global_instruction"],
        "question": task["question"],
        "evidence": task[variant]["packet"],
    }


def main() -> None:
    cli = argparse.ArgumentParser()
    cli.add_argument("task_id")
    cli.add_argument("variant", choices=("evidence_present", "evidence_withheld"))
    cli.add_argument("--output", type=Path, required=True)
    args = cli.parse_args()
    packet = agent_packet(args.task_id, args.variant)
    args.output.write_text(
        json.dumps(packet, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
