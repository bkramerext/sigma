"""Backend build identity captured once per running process.

The checkout may be updated while a long-lived server remains active. Keep the
build that actually started the process instead of looking up the current
checkout HEAD separately for each research session.
"""

from __future__ import annotations

import os
import re
import subprocess
from functools import lru_cache
from pathlib import Path

_COMMIT = re.compile(r"[0-9a-fA-F]{7,40}")


@lru_cache(maxsize=1)
def build_commit() -> str:
    """Return the deployed commit (full SHA where available), or 'unknown'."""
    supplied = os.environ.get("SIGMA_BUILD_COMMIT") or os.environ.get("GITHUB_SHA")
    if supplied and _COMMIT.fullmatch(supplied):
        return supplied.lower()
    try:
        checkout = Path(__file__).resolve().parents[2]
        result = subprocess.run(
            ["git", "rev-parse", "--verify", "HEAD"],
            cwd=checkout,
            capture_output=True,
            text=True,
            timeout=2,
            check=True,
        )
        value = result.stdout.strip()
        return value.lower() if _COMMIT.fullmatch(value) else "unknown"
    except (OSError, subprocess.SubprocessError):
        return "unknown"
