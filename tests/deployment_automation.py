"""Offline safety regressions for the GCE release operator command."""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch

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
        checker_source = repo / "deploy/gce_preflight.py"
        checker_source.write_text("# release-matched preflight\n", encoding="utf-8")
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
            if argv[0] == "install":
                shutil.copyfile(argv[-2], argv[-1])
                Path(argv[-1]).chmod(0o755)
            if argv[:4] == ["git", "-C", str(repo), "status"]:
                output = ""
            elif argv[-3:] in (
                ["ps", "-q", "backend"],
                ["ps", "-q", "frontend"],
                ["ps", "-q", "edge"],
            ):
                output = "container-" + argv[-1]
            elif argv[:3] == ["docker", "inspect", "--format"]:
                output = (
                    "healthy"
                    if "Health.Status" in argv[3]
                    else OLD
                    if "org.opencontainers.image.revision" in argv[3]
                    else f"sigma-{argv[-1].removeprefix('container-')}:{OLD}"
                )
            elif argv[-2:] == ["rev-parse", "HEAD"]:
                output = OLD
            elif argv[:2] == ["systemctl", "is-active"]:
                output = "active"
            return subprocess.CompletedProcess(argv, 0, output, "")

        deployment = module.Deployment(repo, env_file, root / "preflight.py", ok_runner, False)
        assert deployment.deploy(OLD, False, False) == "unchanged"
        assert calls[0][:4] == ["git", "-C", str(repo), "status"]
        assert calls[1][0] == "install"
        assert (root / "preflight.py").read_text(encoding="utf-8") == checker_source.read_text(
            encoding="utf-8"
        )
        assert (root / "preflight.py").stat().st_mode & 0o777 == 0o755
        assert any(argv[0] == "python3" and argv[1] == str(root / "preflight.py") for argv in calls)
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
                    else OLD
                    if "org.opencontainers.image.revision" in argv[3]
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
        real_is_file = Path.is_file

        def installed_switch(path: Path) -> bool:
            if path == Path("/usr/local/libexec/sigma/maintenance-switch.py"):
                return True
            return real_is_file(path)

        try:
            with patch.object(Path, "is_file", installed_switch):
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
        switch_calls = [
            (index, argv[-1])
            for index, argv in enumerate(calls)
            if argv[:2] == ["python3", "/usr/local/libexec/sigma/maintenance-switch.py"]
        ]
        assert [mode for _, mode in switch_calls] == ["on", "off"]
        switch_on_index, switch_off_index = (index for index, _ in switch_calls)
        first_stop_index = next(
            index
            for index, argv in enumerate(calls)
            if argv[:3] == ["systemctl", "stop", "sigma.service"]
        )
        last_health_index = max(
            index
            for index, argv in enumerate(calls)
            if argv[:3] == ["docker", "inspect", "--format"] and "Health.Status" in argv[3]
        )
        assert switch_on_index < first_stop_index
        assert last_health_index < switch_off_index
        assert sum(argv[0] == "install" for argv in calls) >= 4
        assert (root / "preflight.py").read_text(encoding="utf-8") == checker_source.read_text(
            encoding="utf-8"
        )

        # Candidate tooling must be checked out before image build so the
        # requested commit's builder receives its own build inputs.
        checkout_index = next(
            index
            for index, argv in enumerate(calls)
            if argv[:5] == ["git", "-C", str(repo), "checkout", "--detach"] and argv[5] == NEW
        )
        build_index = next(
            index
            for index, argv in enumerate(calls)
            if argv[:2] == ["python3", str(repo / "deploy/release_image.py")]
            and argv[2:] == ["build", str(repo), NEW]
        )
        assert checkout_index < build_index

        print(
            "GCE release automation idempotency, missing config, startup rollback, and state preservation passed."
        )


if __name__ == "__main__":
    main()
