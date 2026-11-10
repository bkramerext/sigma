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
    if step == ["node", "--test", "frontend/src/request-toast-store.test.mjs"]:
        return True
    if step[:3] == ["uv", "run", "--locked"] and len(step) >= 5:
        if step[3:4] == ["--no-sync"]:
            tool = step[4]
            args = step[5:]
        else:
            tool = step[3]
            args = step[4:]
        if tool == "python" and args:
            return args[0].startswith("tests/") or args[0] in (
                "scripts/increment15_offline_pairs.py",
                "docs/evaluations/t173/build_failure_rehearsal.py",
                "docs/evaluations/t173/build_source_sha_rehearsal.py",
            )
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


def _zstd_setup_steps() -> list[list[str]] | None:
    """Install the zstd executable and native lib needed for bundle storage."""
    if shutil.which("zstd"):
        return []
    if sys.platform == "darwin" and shutil.which("brew"):
        return [["brew", "install", "zstd"]]
    if sys.platform.startswith("linux") and shutil.which("apt-get"):
        privilege = [] if os.geteuid() == 0 else ["sudo"] if shutil.which("sudo") else None
        if privilege is not None:
            return [
                [*privilege, "apt-get", "update", "-qq"],
                [*privilege, "apt-get", "install", "-y", "zstd"],
            ]
    print(
        "Missing zstd. Install it (macOS: brew install zstd; "
        "Debian/Ubuntu: sudo apt-get install zstd) and retry ./sigma setup.",
        file=sys.stderr,
    )
    return None


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
        install_zstd = _zstd_setup_steps()
        if install_zstd is None:
            return 2
        steps = [
            *install_zstd,
            ["uv", "sync", "--locked", "--group", "dev"],
            ["npm", "--prefix", "frontend", "ci"],
        ]
    else:
        python = ["uv", "run", "--locked", "--no-sync"]
        steps = [
            [*python, "python", "tests/lifecycle.py"],
            [*python, "python", "tests/project_creation.py"],
            [*python, "python", "tests/project_bundle.py"],
            [*python, "python", "tests/zstd_project_bundles.py"],
            [*python, "python", "tests/project_types.py"],
            [*python, "python", "tests/recents.py"],
            [*python, "python", "tests/test_sample_copies.py"],
            [*python, "python", "tests/test_migrate_scored_samples.py"],
            [*python, "python", "tests/make_sample.py"],
            [*python, "python", "tests/example_math.py"],
            [*python, "python", "tests/research_ladder.py"],
            [*python, "python", "tests/rh_adversarial.py"],
            [*python, "python", "tests/t39_evaluation.py"],
            [*python, "python", "tests/project_settings.py"],
            [*python, "python", "tests/project_collaboration.py"],
            [*python, "python", "tests/research_ethos.py"],
            [*python, "python", "tests/progress_notifications.py"],
            [*python, "python", "tests/model_connection.py"],
            [*python, "python", "tests/cloud_sponsor.py"],
            [*python, "python", "tests/chatgpt.py"],
            [*python, "python", "tests/chatgpt_restart.py"],
            [*python, "python", "tests/strategy_tracking.py"],
            [*python, "python", "tests/proposals.py"],
            [*python, "python", "tests/agentic.py"],
            [*python, "python", "tests/agentic_evidence.py"],
            [*python, "python", "tests/research_sessions_part1.py"],
            [*python, "python", "tests/research_sessions_part2.py"],
            [*python, "python", "tests/research_sessions_part3.py"],
            [*python, "python", "tests/research_sessions_part4.py"],
            [*python, "python", "tests/crucible_scheduler_evidence.py"],
            [*python, "python", "tests/reference_compiler_integration.py"],
            [*python, "python", "tests/research_supplied_evidence_integration.py"],
            [*python, "python", "tests/reference_source_readiness.py"],
            [*python, "python", "tests/research_batch.py"],
            [*python, "python", "tests/session_log.py"],
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
            [*python, "python", "tests/t114_cumulative_dry_run.py"],
            [*python, "python", "tests/increment22_budget.py"],
            [
                *python,
                "python",
                "scripts/increment15_offline_pairs.py",
                "--output",
                "/tmp/sigma-increment15-offline-pairs.json",
            ],
            [*python, "python", "tests/papers_part1.py"],
            [*python, "python", "tests/papers_part2.py"],
            [*python, "python", "tests/test_paper_math_typesetting.py"],
            [*python, "python", "tests/publication_reference_compiler.py"],
            [*python, "python", "tests/paper_scores.py"],
            [*python, "python", "tests/project_evidence.py"],
            [*python, "python", "tests/project_transfer.py"],
            [*python, "python", "tests/research_qa.py"],
            [*python, "python", "tests/research_qa_security.py"],
            [*python, "python", "tests/sovereign_cost_model.py"],
            [*python, "python", "tests/mindrouter_empirical_envelope.py"],
            [*python, "python", "tests/text_views.py"],
            [*python, "python", "tests/strategies.py"],
            [*python, "python", "tests/strategy_changes.py"],
            [*python, "python", "tests/cli_smoke.py"],
            [*python, "python", "tests/tooling.py"],
            [*python, "python", "tests/local_config.py"],
            [*python, "python", "tests/cloud_demo.py"],
            [*python, "python", "tests/cloud_auth_part1.py"],
            [*python, "python", "tests/cloud_auth_part2.py"],
            [*python, "python", "tests/cloud_personal.py"],
            [*python, "python", "tests/cloud_workspaces.py"],
            [*python, "python", "tests/storage.py"],
            [*python, "python", "tests/cloud_research.py"],
            [*python, "python", "tests/cloud_research_api.py"],
            [*python, "python", "tests/cloud_research_windows.py"],
            [*python, "python", "tests/cloud_research_sponsored_api.py"],
            [*python, "python", "tests/deployment_package.py"],
            [*python, "python", "tests/deployment_automation.py"],
            [*python, "python", "tests/test_maintenance_switch.py"],
            [
                *python,
                "python",
                "docs/evaluations/t173/build_failure_rehearsal.py",
                "--deployment-script",
                "deploy/deploy-gce-release.py",
            ],
            [
                *python,
                "python",
                "docs/evaluations/t173/build_source_sha_rehearsal.py",
                "--deployment-script",
                "deploy/deploy-gce-release.py",
            ],
            [*python, "python", "tests/release_image.py"],
            [*python, "python", "tests/cloud_acceptance.py"],
            [*python, "python", "tests/public_endpoint.py"],
            [*python, "python", "tests/gce_host.py"],
            [*python, "python", "tests/state_backup.py"],
            [*python, "python", "tests/host_monitor.py"],
            [*python, "python", "tests/instance_ownership.py"],
            [*python, "python", "tests/ui_registry.py"],
            [*python, "python", "tests/ui_orphans.py"],
            ["node", "--test", "frontend/src/request-toast-store.test.mjs"],
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
            [*python, "python", "tests/test_provider_schema_contract.py"],
        ]
    # CI has a separate fast Ruff job; preserve lint/format for local ./sigma test.
    if command == "test" and os.environ.get("SIGMA_CI_SEPARATE_RUFF") == "1":
        steps = [
            step
            for step in steps
            if not (
                len(step) > 4
                and step[:4] == ["uv", "run", "--locked", "--no-sync"]
                and step[4] == "ruff"
            )
        ]
    # Eight independent CI jobs cover the entire test plan exactly once.
    # Assign checks in round-robin order; local './sigma test' remains whole.
    shard = os.environ.get("SIGMA_CI_TEST_SHARD") if command == "test" else None
    if shard:
        if shard not in {str(index) for index in range(1, 9)}:
            print("SIGMA_CI_TEST_SHARD must be an integer from 1 to 8.", file=sys.stderr)
            return 2
        steps = [step for index, step in enumerate(steps) if index % 8 == int(shard) - 1]
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
            # Do not leak this CI-only option into local-tooling regression tests.
            environment.pop("SIGMA_CI_SEPARATE_RUFF", None)
            environment.pop("SIGMA_CI_TEST_SHARD", None)
        else:
            environment = None
        for step_number, step in enumerate(steps):
            if command == "test" and failures and not _safe_independent_test_step(step):
                skipped.append(step)
                print(
                    f"\nSkipping after earlier failure (not a read-only independent check): {shlex.join(step)}",
                    flush=True,
                )
                continue
            print(f"\n> {shlex.join(step)}", flush=True)
            try:
                step_environment = environment
                if temporary_state:
                    # A check must not inherit another check's saved model,
                    # project or auth settings. The tests within one check
                    # still share one workspace for their own lifecycle cases.
                    check_root = Path(temporary_state) / f"check-{step_number}"
                    step_environment = dict(environment or {})
                    for variable, folder in (
                        ("SIGMA_STATE_DIR", "state"),
                        ("SIGMA_PROJECTS_ROOT", "projects"),
                        ("SIGMA_AUTH_HOME", "auth"),
                    ):
                        directory = check_root / folder
                        directory.mkdir(parents=True, mode=0o700)
                        step_environment[variable] = str(directory)
                result = subprocess.run(step, cwd=ROOT, check=False, env=step_environment)
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
