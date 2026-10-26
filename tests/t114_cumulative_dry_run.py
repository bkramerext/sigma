"""Deterministic T114 cumulative planner checks; fixtures are not research."""

from __future__ import annotations

import hashlib
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[1]
spec = spec_from_file_location(
    "t114_cumulative_dry_run", ROOT / "scripts/t114_cumulative_dry_run.py"
)
if spec is None or spec.loader is None:
    raise RuntimeError("Unable to import T114 offline planner")
t114 = cast(Any, module_from_spec(spec))
spec.loader.exec_module(t114)


def commitments() -> list[dict[str, str]]:
    return [
        {
            "opaque_id": f"sealed-{index + 1:02d}",
            "domain": f"domain-{index % 6 + 1}",
            "sha256": hashlib.sha256(f"fixture-{index}".encode()).hexdigest(),
        }
        for index in range(t114.TASK_COUNT)
    ]


def run() -> None:
    rows = commitments()
    first = t114.plan(rows)
    assert first == t114.plan(rows)
    assert first["pair_count"] == 12 and first["arm_count"] == 24
    assert first["provider_calls_authorized"] == 0
    assert first["ceilings"]["estimated_worst_case_usd_study"] < t114.STUDY_USD_CAP
    assert first["pairs"] != t114.plan(rows, seed=4)["pairs"]

    records = [
        {"pair_id": pair["pair_id"], "arm_code": code, "status": "complete"}
        for pair in first["pairs"]
        for code in ("A", "B")
    ]
    records[0]["status"] = "failed"
    report = t114.audit_records(first, records)
    assert report["retained_arms"] == 24 and report["status_counts"]["failed"] == 1
    for altered in (records[:-1], records + [records[0]]):
        try:
            t114.audit_records(first, altered)
        except ValueError:
            pass
        else:
            raise AssertionError("Missing/duplicate arm record must be rejected")

    for change in (
        lambda data: data[:-1],
        lambda data: [*data[:-1], {**data[-1], "opaque_id": data[0]["opaque_id"]}],
        lambda data: [*data[:-1], {**data[-1], "sha256": "not-a-digest"}],
    ):
        try:
            t114.plan(change(list(rows)))
        except ValueError:
            pass
        else:
            raise AssertionError("Invalid task commitments must be rejected")
    print("PASS T114 cumulative schedule determinism, caps, pairing and failure retention")


if __name__ == "__main__":
    run()
