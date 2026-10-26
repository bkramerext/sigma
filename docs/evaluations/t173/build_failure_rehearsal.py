"""Fixture rehearsal for T129 candidate-build failure before activation."""

from __future__ import annotations

import argparse
import importlib.util
import subprocess
import tempfile
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--deployment-script", type=Path, required=True)
    args = parser.parse_args()
    spec = importlib.util.spec_from_file_location("deploy_gce_release", args.deployment_script)
    if spec is None or spec.loader is None:
        raise SystemExit("FAIL: cannot load the T129 release command")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    old_sha, candidate_sha = "a" * 40, "b" * 40

    with tempfile.TemporaryDirectory(prefix="sigma-t173-build-failure-") as temporary:
        root = Path(temporary)
        checkout = root / "checkout"
        checkout.mkdir()
        deploy_env = root / "deploy.env"
        original_env = f"SIGMA_RELEASE={old_sha}\nSIGMA_DOMAIN=fixture.example\n".encode()
        deploy_env.write_bytes(original_env)
        deploy_env.chmod(0o600)
        state = root / "state"
        state.mkdir()
        marker = state / "fixture.sqlite"
        marker.write_bytes(b"persistent-fixture")
        calls: list[list[str]] = []

        def runner(argv: list[str], **_: object) -> subprocess.CompletedProcess[str]:
            calls.append(argv)
            if argv[:1] == ["python3"]:
                return subprocess.CompletedProcess(argv, 0, "[]", "")
            if argv[:3] == ["git", "-C", str(checkout)]:
                if argv[3] == "status":
                    return subprocess.CompletedProcess(argv, 0, "", "")
                if argv[3] == "rev-parse":
                    return subprocess.CompletedProcess(argv, 0, old_sha, "")
                if argv[3] in {"fetch", "cat-file"}:
                    return subprocess.CompletedProcess(argv, 0, "", "")
            if argv[:3] == ["docker", "compose", "--project-name"] and argv[-3:] == [
                "build",
                "backend",
                "frontend",
            ]:
                return subprocess.CompletedProcess(argv, 17, "", "fixture failure")
            raise AssertionError(f"unexpected release command: {argv}")

        deployment = module.Deployment(checkout, deploy_env, root / "preflight.py", runner, False)
        try:
            deployment.deploy(candidate_sha, backup_verified=True, schema_compatible=True)
        except module.DeployFailure as error:
            assert "command failed (docker, exit 17)" in str(error)
        else:
            raise AssertionError("failed candidate build unexpectedly succeeded")

        assert deploy_env.read_bytes() == original_env
        assert marker.read_bytes() == b"persistent-fixture"
        assert not any(command[:2] == ["systemctl", "stop"] for command in calls)
        assert not any(command[:4] == ["git", "-C", str(checkout), "checkout"] for command in calls)
        assert sum(command[:1] == ["docker"] for command in calls) == 1

    print(
        "PASS: failed candidate build leaves active pin, service and persistent fixture untouched"
    )


if __name__ == "__main__":
    main()
