"""Offline safety regressions for the GCE release operator command."""

from __future__ import annotations

import importlib.util
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "deploy_gce_release", ROOT / "deploy/deploy-gce-release.py"
)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)

OLD = "a" * 40
NEW = "b" * 40


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="sigma-release-test-") as directory:
        root = Path(directory)
        repo = root / "checkout"
        repo.mkdir()
        (repo / "deploy").mkdir()
        env_file = root / "deploy.env"
        original = (
            f"SIGMA_RELEASE={OLD}\nSIGMA_DOMAIN=example.test\n"
            "GOOGLE_OIDC_CLIENT_SECRET_FILE=/run/sigma-secrets/google\n"
            "SIGMA_CLOUD_OPENAI_API_KEY_FILE=/run/sigma-secrets/openai\n"
        ).encode()
        env_file.write_bytes(original)
        env_file.chmod(0o600)
        state = root / "state"
        state.mkdir()
        (state / "auth.sqlite").write_bytes(b"preserve-me")

        # Repeating the selected release runs read-only preflight only.
        calls: list[list[str]] = []

        def ok_runner(argv: list[str], **_: object) -> subprocess.CompletedProcess[str]:
            calls.append(argv)
            output = "ready"
            if argv[-3:] in (
                ["ps", "-q", "backend"],
                ["ps", "-q", "frontend"],
                ["ps", "-q", "edge"],
            ):
                output = "container-" + argv[-1]
            elif argv[:3] == ["docker", "inspect", "--format"]:
                output = (
                    "healthy"
                    if "Health.Status" in argv[3]
                    else f"sigma-{argv[-1].removeprefix('container-')}:{OLD}"
                )
            elif argv[-2:] == ["rev-parse", "HEAD"]:
                output = OLD
            elif argv[:2] == ["systemctl", "is-active"]:
                output = "active"
            return subprocess.CompletedProcess(argv, 0, output, "")

        deployment = module.Deployment(repo, env_file, root / "preflight.py", ok_runner, False)
        assert deployment.deploy(OLD, False, False) == "unchanged"
        assert calls[0][0] == "python3"
        assert not any(argv[:2] == ["systemctl", "start"] for argv in calls)
        assert not any(argv[:4] == ["git", "-C", str(repo), "checkout"] for argv in calls)
        assert env_file.read_bytes() == original

        # Missing configuration fails before invoking any host command.
        missing = root / "missing.env"
        try:
            module.Deployment(repo, missing, root / "preflight.py", ok_runner, False).deploy(
                NEW, True, True
            )
        except module.DeployFailure as error:
            assert "missing" in str(error)
        else:
            raise AssertionError("missing deploy.env was accepted")
        assert len(calls) > 0

        # Startup failure restores the original code pin/config and never writes
        # to the durable state directory. Failure diagnostics contain no values.
        start_attempts = 0

        def failing_start(argv: list[str], **_: object) -> subprocess.CompletedProcess[str]:
            nonlocal start_attempts
            calls.append(argv)
            if argv[:2] == ["python3", str(root / "preflight.py")]:
                return subprocess.CompletedProcess(argv, 0, "preflight passed", "")
            if argv[:4] == ["git", "-C", str(repo), "status"]:
                return subprocess.CompletedProcess(argv, 0, "", "")
            if argv[:4] == ["git", "-C", str(repo), "cat-file"]:
                return subprocess.CompletedProcess(argv, 0, "", "")
            if argv[:4] == ["git", "-C", str(repo), "rev-parse"]:
                return subprocess.CompletedProcess(argv, 0, OLD, "")
            if argv[-3:] in (
                ["ps", "-q", "backend"],
                ["ps", "-q", "frontend"],
                ["ps", "-q", "edge"],
            ):
                return subprocess.CompletedProcess(argv, 0, "container-" + argv[-1], "")
            if argv[:3] == ["docker", "inspect", "--format"]:
                output = (
                    "healthy"
                    if "Health.Status" in argv[3]
                    else f"sigma-{argv[-1].removeprefix('container-')}:{OLD}"
                )
                return subprocess.CompletedProcess(argv, 0, output, "")
            if argv[:2] == ["systemctl", "is-active"]:
                return subprocess.CompletedProcess(argv, 0, "active", "")
            if argv[:2] == ["systemctl", "start"]:
                start_attempts += 1
                if start_attempts == 1:
                    return subprocess.CompletedProcess(
                        argv, 1, "", "startup failed; token=NEVER-LOG"
                    )
            return subprocess.CompletedProcess(argv, 0, "", "")

        failing = module.Deployment(repo, env_file, root / "preflight.py", failing_start, False)
        try:
            failing.deploy(NEW, True, True)
        except module.DeployFailure as error:
            diagnostic = str(error)
            assert "restored" in diagnostic
            assert "NEVER-LOG" not in diagnostic and "token" not in diagnostic
        else:
            raise AssertionError("failed startup was reported as successful")
        assert env_file.read_bytes() == original
        assert (state / "auth.sqlite").read_bytes() == b"preserve-me"
        assert start_attempts == 2  # candidate failed, previous release restarted

        print(
            "GCE release automation idempotency, missing config, startup rollback, and state preservation passed."
        )


if __name__ == "__main__":
    main()
