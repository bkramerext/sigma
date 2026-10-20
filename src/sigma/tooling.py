"""Repository maintenance commands with streamed output and fail-fast exit codes."""

import shlex
import shutil
import subprocess
import sys

from sigma.projects import ROOT


def run_tooling(command: str) -> int:
    if not all((ROOT / name).is_file() for name in ("pyproject.toml", "frontend/package.json")):
        print(
            "These commands require a SIGMA source checkout (use an editable install).",
            file=sys.stderr,
        )
        return 2
    for tool in ("uv", "npm"):
        if shutil.which(tool) is None:
            print(
                f"Missing prerequisite: {tool}. Install it and retry sigma {command}.",
                file=sys.stderr,
            )
            return 2
    if command == "setup":
        steps = [
            ["uv", "sync", "--locked", "--group", "dev"],
            ["npm", "--prefix", "frontend", "ci"],
        ]
    else:
        python = ["uv", "run", "--locked", "--no-sync"]
        steps = [
            [*python, "python", "scenarios/lifecycle.py"],
            [*python, "python", "scenarios/cli_smoke.py"],
            [*python, "python", "scenarios/tooling.py"],
            [*python, "ruff", "check", "src", "scenarios", "sigma"],
            [*python, "ruff", "format", "--check", "src", "scenarios", "sigma"],
            [*python, "pyright"],
            ["npm", "--prefix", "frontend", "run", "typecheck"],
            ["npm", "--prefix", "frontend", "run", "build"],
        ]
    for step in steps:
        print(f"\n> {shlex.join(step)}", flush=True)
        try:
            result = subprocess.run(step, cwd=ROOT, check=False)
        except OSError as exc:
            print(f"Could not start {step[0]}: {exc}", file=sys.stderr)
            return 2
        if result.returncode:
            print(
                f"sigma {command} stopped: {shlex.join(step)} failed (exit {result.returncode}).",
                file=sys.stderr,
            )
            return result.returncode if result.returncode > 0 else 1
    print(f"\nsigma {command}: all steps passed.", flush=True)
    return 0
