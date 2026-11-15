#!/usr/bin/env python3
"""Print only safely identified expired SIGMA state-disk snapshots."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

NAME = re.compile(r"^sigma-state-[0-9]{8}t[0-9]{6}z$")


def expired_snapshots(path: Path, retention: int) -> list[str]:
    if retention < 14:
        raise ValueError("retention cannot be less than 14 recovery points")
    rows = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        raise TypeError("snapshot listing must be a JSON array")
    candidates = []
    for row in rows:
        if not isinstance(row, dict):
            raise TypeError("snapshot listing contains a malformed entry")
        labels = row.get("labels") or {}
        source_value = row.get("sourceDisk", "")
        if not isinstance(labels, dict) or not isinstance(source_value, str):
            raise TypeError("managed snapshot metadata has invalid types")
        source = source_value.rstrip("/")
        if (
            labels.get("sigma-daily-backup") != "true"
            or labels.get("sigma-source-disk") != "sigma-state"
        ):
            continue
        name = row.get("name", "")
        if not NAME.fullmatch(name) or not source.endswith("/disks/sigma-state"):
            raise ValueError("managed snapshot metadata does not match the SIGMA state disk")
        created = row.get("creationTimestamp")
        if not isinstance(created, str) or not created:
            raise ValueError(f"managed snapshot {name} lacks a creation timestamp")
        candidates.append((created, name))
    candidates.sort(reverse=True)
    return [name for _, name in candidates[retention:]]


def main() -> int:
    try:
        if len(sys.argv) != 3:
            raise ValueError("usage: backup-retention.py SNAPSHOTS.json RETENTION")
        for name in expired_snapshots(Path(sys.argv[1]), int(sys.argv[2])):
            print(name)
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        print(f"FAIL retention planning: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
