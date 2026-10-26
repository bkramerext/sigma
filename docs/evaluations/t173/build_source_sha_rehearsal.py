"""Demonstrate whether T129 builds an image from the selected commit."""

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

    with tempfile.TemporaryDirectory(prefix="sigma-t173-source-sha-") as temporary:
        root = Path(temporary)
        checkout = root / "checkout"
        checkout.mkdir()
        deploy_env = root / "deploy.env"
        deploy_env.write_text(
            f"SIGMA_RELEASE={old_sha}\nSIGMA_DOMAIN=fixture.example\n", encoding="utf-8"
        )
        deploy_env.chmod(0o600)
        checked_out_sha = old_sha
        source_sha_at_build: str | None = None
        image_sha_at_build: str | None = None

        def runner(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
            nonlocal checked_out_sha, source_sha_at_build, image_sha_at_build
            if argv[:1] == ["python3"]:
                return subprocess.CompletedProcess(argv, 0, "[]", "")
            if argv[:3] == ["git", "-C", str(checkout)]:
                operation = argv[3]
                if operation == "status":
                    return subprocess.CompletedProcess(argv, 0, "", "")
                if operation in {"fetch", "cat-file"}:
                    return subprocess.CompletedProcess(argv, 0, "", "")
                if operation == "rev-parse":
                    return subprocess.CompletedProcess(argv, 0, checked_out_sha, "")
                if operation == "checkout":
                    checked_out_sha = argv[-1]
                    return subprocess.CompletedProcess(argv, 0, "", "")
            if argv[:3] == ["docker", "compose", "--project-name"] and argv[-3:] == [
                "build",
                "backend",
                "frontend",
            ]:
                source_sha_at_build = checked_out_sha
                environment = kwargs.get("env")
                assert isinstance(environment, dict)
                image_sha_at_build = environment["SIGMA_RELEASE"]
                return subprocess.CompletedProcess(argv, 0, "", "")
            if argv[:2] == ["systemctl", "start"] or argv[:2] == ["systemctl", "stop"]:
                return subprocess.CompletedProcess(argv, 0, "", "")
            if argv[-3:] in (
                ["ps", "-q", "backend"],
                ["ps", "-q", "frontend"],
                ["ps", "-q", "edge"],
            ):
                return subprocess.CompletedProcess(argv, 0, "fixture-" + argv[-1], "")
            if argv[:3] == ["docker", "inspect", "--format"]:
                if "Health.Status" in argv[3]:
                    return subprocess.CompletedProcess(argv, 0, "healthy", "")
                image = argv[-1].removeprefix("fixture-")
                suffix = candidate_sha if image in {"backend", "frontend"} else ""
                return subprocess.CompletedProcess(
                    argv, 0, f"sigma-{image}:{suffix}".rstrip(":"), ""
                )
            if argv[:2] == ["systemctl", "is-active"]:
                return subprocess.CompletedProcess(argv, 0, "active", "")
            if argv[:1] == ["findmnt"] or argv[:1] == ["test"]:
                return subprocess.CompletedProcess(argv, 0, "", "")
            return subprocess.CompletedProcess(argv, 0, "", "")

        deployment = module.Deployment(checkout, deploy_env, root / "preflight.py", runner, False)
        deployment.deploy(candidate_sha, backup_verified=True, schema_compatible=True)
        assert image_sha_at_build == candidate_sha
        assert source_sha_at_build == old_sha
        assert checked_out_sha == candidate_sha
        print(
            "FAIL: candidate image tag was assigned while the build checkout still pointed to the previous SHA"
        )
        print(f"selected_image_sha={image_sha_at_build}")
        print(f"build_context_checkout_sha={source_sha_at_build}")
        print(f"post-build_checkout_sha={checked_out_sha}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
