"""Permanent JSON project integration suite (Docker lifecycle opt-in).

Unlike scripts/t249_verify.py this runner never commits or pushes anything.
Run with --docker to include real sandbox lifecycle checks.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(root / "src") + os.pathsep + env.get("PYTHONPATH", "")
    venv_python = root / ".venv" / "bin" / "python"
    interpreter = str(venv_python) if venv_python.is_file() else sys.executable
    suites = [
        ("tests/project_bundle.py", 90),
        ("tests/project_creation.py", 120),
    ]
    if "--docker" in sys.argv[1:]:
        suites.append(("tests/t249_docker_lifecycle.py", 90))
    elif sys.argv[1:]:
        print("Usage: test_t249_integration.py [--docker]", file=sys.stderr)
        return 2
    for suite, timeout in suites:
        print(f"Running {suite} (timeout {timeout}s)", flush=True)
        try:
            result = subprocess.run(
                [interpreter, "-u", str(root / suite)],
                cwd=root,
                env=env,
                check=False,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            print(f"TIMEOUT {suite} after {timeout}s", file=sys.stderr, flush=True)
            return 124
        if result.returncode:
            print(f"FAILED {suite} (exit {result.returncode})", file=sys.stderr)
            return result.returncode
    suffix = " and Docker lifecycle" if "--docker" in sys.argv[1:] else ""
    print(f"PASS JSON project integration{suffix}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
