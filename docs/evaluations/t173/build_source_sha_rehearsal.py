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
            if argv[:2] == ["python3", str(checkout / "deploy/release_image.py")]:
                if argv[2] == "build":
                    source_sha_at_build = argv[-1]
                    image_sha_at_build = argv[-1]
                return subprocess.CompletedProcess(argv, 0, "fixture", "")
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
                if "org.opencontainers.image.revision" in argv[3]:
                    active_sha = next(
                        line.split("=", 1)[1]
                        for line in deploy_env.read_text(encoding="utf-8").splitlines()
                        if line.startswith("SIGMA_RELEASE=")
                    )
                    return subprocess.CompletedProcess(argv, 0, active_sha, "")
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
        assert source_sha_at_build == candidate_sha
        assert checked_out_sha == candidate_sha
        print("PASS: requested SHA is passed to the isolated archive-based image builder")
        print(f"selected_image_sha={image_sha_at_build}")
        print(f"build_source_sha={source_sha_at_build}")
        print(f"post-deploy_checkout_sha={checked_out_sha}")


if __name__ == "__main__":
    main()
