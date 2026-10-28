"""Build and attest production images for one exact Git commit."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any

LABEL = "org.opencontainers.image.revision"
SHA_RE = re.compile(r"[0-9a-f]{40}\Z")


def _run(args: list[str], *, cwd: Path | None = None) -> str:
    result = subprocess.run(args, cwd=cwd, check=True, text=True, capture_output=True)
    return result.stdout.strip()


def resolve_commit(repository: Path, requested: str) -> str:
    if not SHA_RE.fullmatch(requested):
        raise ValueError("requested release must be a full lowercase 40-character Git SHA")
    resolved = _run(
        ["git", "-C", str(repository), "rev-parse", "--verify", f"{requested}^{{commit}}"]
    )
    if resolved != requested:
        raise ValueError("requested release SHA did not resolve to the exact commit")
    return resolved


def build(repository: Path, requested: str, runner=_run) -> None:
    commit = resolve_commit(repository, requested)
    with tempfile.TemporaryDirectory(prefix="sigma-release-") as directory:
        context = Path(directory)
        archive = subprocess.run(
            ["git", "-C", str(repository), "archive", "--format=tar", commit],
            check=True,
            capture_output=True,
        ).stdout
        import io
        import tarfile

        with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as tar:
            tar.extractall(context, filter="data")
        for name, dockerfile in (
            ("backend", "Dockerfile"),
            ("frontend", "deploy/frontend.Dockerfile"),
        ):
            runner(
                [
                    "docker",
                    "build",
                    "--platform",
                    "linux/amd64",
                    "--label",
                    f"{LABEL}={commit}",
                    "--build-arg",
                    f"SIGMA_BUILD_COMMIT={commit}",
                    "--tag",
                    f"sigma-{name}:{commit}",
                    "--file",
                    str(context / dockerfile),
                    str(context),
                ]
            )


def image_info(image: str, requested: str, runner=_run) -> dict[str, Any]:
    raw = runner(["docker", "image", "inspect", image, "--format", "{{json .}}"])
    data = json.loads(raw)
    actual = data.get("Config", {}).get("Labels", {}).get(LABEL)
    if actual != requested:
        raise ValueError(f"image {image} source label does not match requested release SHA")
    image_id = data.get("Id")
    if not isinstance(image_id, str) or not image_id.startswith("sha256:"):
        raise ValueError(f"image {image} has no immutable image ID")
    return {"tag": image, "image_id": image_id, "repo_digests": data.get("RepoDigests", [])}


def record(
    requested: str,
    record_root: Path,
    containers: dict[str, str],
    runner=_run,
) -> Path:
    if not SHA_RE.fullmatch(requested):
        raise ValueError("requested release must be a full lowercase 40-character Git SHA")
    if set(containers) != {"backend", "frontend"} or any(
        not value for value in containers.values()
    ):
        raise ValueError("recording requires the running backend and frontend container IDs")
    images = {
        name: image_info(f"sigma-{name}:{requested}", requested, runner)
        for name in ("backend", "frontend")
    }
    for name, container_id in containers.items():
        container = json.loads(
            runner(["docker", "inspect", container_id, "--format", "{{json .}}"])
        )
        if container.get("Image") != images[name]["image_id"]:
            raise ValueError(f"running {name} container does not use the verified release image")
        if container.get("State", {}).get("Status") != "running":
            raise ValueError(f"{name} release container is not running")
        labels = container.get("Config", {}).get("Labels", {})
        if labels.get(LABEL) != requested:
            raise ValueError(
                f"running {name} container source label does not match requested release SHA"
            )
        images[name]["container_id"] = container_id
        images[name]["running_image_id"] = container["Image"]
    record_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    document = {"source_commit": requested, "images": images}
    destination = record_root / f"{requested}.json"
    temporary = destination.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(document, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    os.chmod(temporary, 0o600)
    os.replace(temporary, destination)
    return destination


def verify(requested: str, runner=_run) -> dict[str, Any]:
    if not SHA_RE.fullmatch(requested):
        raise ValueError("requested release must be a full lowercase 40-character Git SHA")
    return {
        name: image_info(f"sigma-{name}:{requested}", requested, runner)
        for name in ("backend", "frontend")
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    build_parser = commands.add_parser("build")
    build_parser.add_argument("repository", type=Path)
    build_parser.add_argument("sha")
    record_parser = commands.add_parser("record")
    record_parser.add_argument("sha")
    record_parser.add_argument("--directory", type=Path, default=Path("/var/lib/sigma/releases"))
    record_parser.add_argument("--backend-container", required=True)
    record_parser.add_argument("--frontend-container", required=True)
    verify_parser = commands.add_parser("verify")
    verify_parser.add_argument("sha")
    args = parser.parse_args()
    if args.command == "build":
        build(args.repository.resolve(), args.sha)
        print(f"PASS: built backend and frontend from {args.sha}")
    elif args.command == "record":
        path = record(
            args.sha,
            args.directory,
            {"backend": args.backend_container, "frontend": args.frontend_container},
        )
        print(f"PASS: verified image source labels and recorded image IDs at {path}")
    else:
        verify(args.sha)
        print(f"PASS: both production images are built from {args.sha}")


if __name__ == "__main__":
    main()
