"""Repository maintenance commands with streamed output and failure summaries."""

import os
import shlex
import shutil
import subprocess
import sys
from contextlib import nullcontext
from pathlib import Path
from tempfile import TemporaryDirectory

from sigma.projects import ROOT


def _test_step_allowed(step: list[str]) -> bool:
    """Reject test plans that include commands outside the repository check set."""
    if step[:3] == ["uv", "run", "--locked"] and len(step) >= 5:
        if step[3:4] == ["--no-sync"]:
            tool = step[4]
            args = step[5:]
        else:
            tool = step[3]
            args = step[4:]
        if tool == "python" and args:
            return args[0].startswith("tests/") or args[0] == "scripts/increment15_offline_pairs.py"
        if tool == "ruff" and args[:1] in (["check"], ["format"]):
            return True
        if tool == "pyright" and not args:
            return True
    return step[:4] == ["npm", "--prefix", "frontend", "run"] and step[4:] in (
        ["typecheck"],
        ["build"],
    )


def _safe_independent_test_step(step: list[str]) -> bool:
    """Identify checks that may continue after another check has failed."""
    if not _test_step_allowed(step):
        return False
    if step[:3] == ["uv", "run", "--locked"]:
        script = step[5] if len(step) > 5 and step[3] == "--no-sync" else ""
        return script != "scripts/increment15_offline_pairs.py"
    return step[4:] != ["build"]


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
            [*python, "python", "tests/make_sample.py"],
            [*python, "python", "tests/example_math.py"],
            [*python, "python", "tests/research_ladder.py"],
            [*python, "python", "tests/rh_adversarial.py"],
            [*python, "python", "tests/t39_evaluation.py"],
            [*python, "python", "tests/project_settings.py"],
            [*python, "python", "tests/model_connection.py"],
            [*python, "python", "tests/chatgpt.py"],
            [*python, "python", "tests/chatgpt_restart.py"],
            [*python, "python", "tests/strategy_tracking.py"],
            [*python, "python", "tests/proposals.py"],
            [*python, "python", "tests/agentic.py"],
            [*python, "python", "tests/agentic_evidence.py"],
            [*python, "python", "tests/research_sessions.py"],
            [*python, "python", "tests/epistemic_continuity.py"],
            [*python, "python", "tests/closure_basis.py"],
            [*python, "python", "tests/research_state.py"],
            [*python, "python", "tests/continuations.py"],
            [*python, "python", "tests/research_feedback.py"],
            [*python, "python", "tests/python_sandbox.py"],
            [*python, "python", "tests/sage_execution.py"],
            [*python, "python", "tests/computational_evidence.py"],
            [*python, "python", "tests/project_reports.py"],
            [*python, "python", "tests/increment13_integrity.py"],
            [*python, "python", "tests/increment14_protocol.py"],
            [*python, "python", "tests/increment14_audit.py"],
            [*python, "python", "tests/increment22_budget.py"],
            [
                *python,
                "python",
                "scripts/increment15_offline_pairs.py",
                "--output",
                "/tmp/sigma-increment15-offline-pairs.json",
            ],
            [*python, "python", "tests/papers.py"],
            [*python, "python", "tests/text_views.py"],
            [*python, "python", "tests/strategies.py"],
            [*python, "python", "tests/strategy_changes.py"],
            [*python, "python", "tests/cli_smoke.py"],
            [*python, "python", "tests/tooling.py"],
            [*python, "python", "tests/local_config.py"],
            [*python, "python", "tests/cloud_demo.py"],
            [*python, "python", "tests/cloud_auth.py"],
            [*python, "python", "tests/cloud_workspaces.py"],
            [*python, "python", "tests/storage.py"],
            [*python, "python", "tests/cloud_research.py"],
            [*python, "python", "tests/cloud_research_api.py"],
            [*python, "python", "tests/cloud_research_sponsored_api.py"],
            [*python, "python", "tests/deployment_package.py"],
            [*python, "python", "tests/public_endpoint.py"],
            [*python, "python", "tests/gce_host.py"],
            [*python, "python", "tests/state_backup.py"],
            [*python, "python", "tests/host_monitor.py"],
            [*python, "python", "tests/instance_ownership.py"],
            [*python, "python", "tests/ui_registry.py"],
            [*python, "python", "tests/ui_orphans.py"],
            [
                *python,
                "ruff",
                "check",
                "src",
                "tests",
                "sigma",
                "deploy",
                "browser_checks",
                "scripts",
                "docs/evaluations",
            ],
            [
                *python,
                "ruff",
                "format",
                "--check",
                "src",
                "tests",
                "sigma",
                "deploy",
                "scripts",
                "browser_checks",
                "docs/evaluations",
            ],
            [*python, "pyright"],
            ["npm", "--prefix", "frontend", "run", "typecheck"],
            ["npm", "--prefix", "frontend", "run", "build"],
        ]
    unsupported_steps = [step for step in steps if not _test_step_allowed(step)]
    if command == "test" and unsupported_steps:
        print(
            "Refusing test plan command outside the approved check set: "
            f"{shlex.join(unsupported_steps[0])}",
            file=sys.stderr,
        )
        return 2

    failures: list[tuple[list[str], int]] = []
    skipped: list[list[str]] = []
    with (
        TemporaryDirectory(prefix="sigma-test-state-")
        if command == "test"
        else nullcontext(None) as temporary_state
    ):
        if temporary_state:
            test_root = Path(temporary_state)
            state_root = test_root / "state"
            projects_root = test_root / "projects"
            auth_root = test_root / "auth"
            for directory in (state_root, projects_root, auth_root):
                directory.mkdir(mode=0o700)
            environment = {
                **os.environ,
                "SIGMA_STATE_DIR": str(state_root),
                "SIGMA_PROJECTS_ROOT": str(projects_root),
                "SIGMA_AUTH_HOME": str(auth_root),
            }
        else:
            environment = None
        for step in steps:
            if command == "test" and failures and not _safe_independent_test_step(step):
                skipped.append(step)
                print(
                    f"\nSkipping after earlier failure (not a read-only independent check): {shlex.join(step)}",
                    flush=True,
                )
                continue
            print(f"\n> {shlex.join(step)}", flush=True)
            try:
                result = subprocess.run(step, cwd=ROOT, check=False, env=environment)
            except OSError as exc:
                print(f"Could not start {step[0]}: {exc}", file=sys.stderr)
                code = 2
            else:
                code = result.returncode
            if code:
                normalized_code = code if code > 0 else 1
                failures.append((step, normalized_code))
                print(
                    f"sigma {command} check failed: {shlex.join(step)} (exit {normalized_code}).",
                    file=sys.stderr,
                )
                if command != "test":
                    return normalized_code
    if failures:
        print(f"\nsigma test: {len(failures)} step(s) failed:", file=sys.stderr)
        for step, code in failures:
            print(f"  exit {code}: {shlex.join(step)}", file=sys.stderr)
        if skipped:
            print(
                f"sigma test: {len(skipped)} non-read-only step(s) skipped after failures:",
                file=sys.stderr,
            )
            for step in skipped:
                print(f"  {shlex.join(step)}", file=sys.stderr)
        return failures[0][1]
    print(f"\nsigma {command}: all steps passed.", flush=True)
    return 0


def build_sandbox(runtime_name: str) -> int:
    """Explicit, optional setup only. Ordinary setup/test never downloads Sage."""
    from sigma.python_sandbox import runtime_settings

    settings = runtime_settings(runtime_name)
    filename = "Dockerfile.sage" if runtime_name == "sagemath" else "Dockerfile"
    command = [
        "docker",
        "build",
        "-f",
        f"sandbox-poc/{filename}",
        "-t",
        settings["image"],
        "sandbox-poc",
    ]
    try:
        return subprocess.run(command, cwd=ROOT, check=False).returncode
    except OSError:
        print(
            "Docker is unavailable; install/start Docker and retry this explicit build.",
            file=sys.stderr,
        )
        return 2
