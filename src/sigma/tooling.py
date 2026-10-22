"""Repository maintenance commands with streamed output and fail-fast exit codes."""

import os
import shlex
import shutil
import subprocess
import sys
from contextlib import nullcontext
from tempfile import TemporaryDirectory

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
            [*python, "python", "tests/lifecycle.py"],
            [*python, "python", "tests/project_creation.py"],
            [*python, "python", "tests/recents.py"],
            [*python, "python", "tests/test_sample_copies.py"],
            [*python, "python", "tests/example_math.py"],
            [*python, "python", "tests/project_settings.py"],
            [*python, "python", "tests/model_connection.py"],
            [*python, "python", "tests/chatgpt.py"],
            [*python, "python", "tests/chatgpt_restart.py"],
            [*python, "python", "tests/strategy_tracking.py"],
            [*python, "python", "tests/proposals.py"],
            [*python, "python", "tests/agentic.py"],
            [*python, "python", "tests/agentic_evidence.py"],
            [*python, "python", "tests/research_sessions.py"],
            [*python, "python", "tests/project_reports.py"],
            [*python, "python", "tests/text_views.py"],
            [*python, "python", "tests/strategies.py"],
            [*python, "python", "tests/strategy_changes.py"],
            [*python, "python", "tests/cli_smoke.py"],
            [*python, "python", "tests/tooling.py"],
            [*python, "python", "tests/local_config.py"],
            [*python, "python", "tests/instance_ownership.py"],
            [*python, "python", "tests/ui_orphans.py"],
            [*python, "ruff", "check", "src", "tests", "sigma"],
            [*python, "ruff", "format", "--check", "src", "tests", "sigma"],
            [*python, "pyright"],
            ["npm", "--prefix", "frontend", "run", "typecheck"],
            ["npm", "--prefix", "frontend", "run", "build"],
        ]
    with (
        TemporaryDirectory(prefix="sigma-test-state-")
        if command == "test"
        else nullcontext(None) as temporary_state
    ):
        environment = (
            {**os.environ, "SIGMA_STATE_DIR": str(temporary_state)} if temporary_state else None
        )
        for step in steps:
            print(f"\n> {shlex.join(step)}", flush=True)
            try:
                result = subprocess.run(step, cwd=ROOT, check=False, env=environment)
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
