#!/usr/bin/env python3
"""Low-cadence deletion of expired SIGMA operational logs only."""
from __future__ import annotations

import sys
import time
from pathlib import Path

LOGS = Path("/srv/sigma-state/auth/operational-logs")
SECONDS = 7 * 24 * 60 * 60


def main() -> int:
    if not LOGS.is_dir() or LOGS.is_symlink():
        print("Operational log directory missing/unsafe; refusing cleanup", file=sys.stderr)
        return 1
    cutoff = time.time() - SECONDS
    deleted = 0
    for candidate in LOGS.iterdir():
        name = candidate.name
        # Never touch the active backend.log or any project/other durable data.
        if not (name.startswith("backend.log.") or (
            name.startswith("watchdog-") and name.endswith(".log")
        )):
            continue
        if candidate.is_symlink() or not candidate.is_file():
            continue
        if candidate.stat().st_mtime < cutoff:
            candidate.unlink()
            deleted += 1
    print(f"Expired operational log files deleted: {deleted}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
