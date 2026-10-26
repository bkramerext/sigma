#!/usr/bin/env python3
"""Permanent T249 JSON project integration suite (requires local Docker images).

Unlike scripts/t249_verify.py this runner never commits or pushes anything.
Use it for explicit Docker-enabled integration verification.
"""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(root / "src") + os.pathsep + env.get("PYTHONPATH", "")
    suites = (("tests/project_bundle.py", 90), ("tests/t249_docker_lifecycle.py", 90))
    for suite, timeout in suites:
        print(f"Running {suite} (timeout {timeout}s)", flush=True)
        try:
            result = subprocess.run([sys.executable, "-u", str(root / suite)], cwd=root,
                                    env=env, check=False, timeout=timeout)
        except subprocess.TimeoutExpired:
            print(f"TIMEOUT {suite} after {timeout}s", file=sys.stderr, flush=True)
            return 124
        if result.returncode:
            print(f"FAILED {suite} (exit {result.returncode})", file=sys.stderr)
            return result.returncode
    print("PASS JSON project bundle and Docker integration")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
