"""Fixture rehearsal for exact-SHA release image staging and failure isolation."""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILDER = ROOT / "deploy/build-release-images.sh"


def run() -> None:
    with tempfile.TemporaryDirectory(prefix="sigma-release-rehearsal-") as temporary:
        root = Path(temporary) / "checkout"
        root.mkdir()
        subprocess.run(["git", "init", "-q", str(root)], check=True)
        subprocess.run(
            ["git", "-C", str(root), "config", "user.email", "fixture@example.test"], check=True
        )
        subprocess.run(["git", "-C", str(root), "config", "user.name", "Fixture"], check=True)
        (root / "Dockerfile").write_text("FROM scratch\n", encoding="utf-8")
        (root / "deploy").mkdir()
        (root / "deploy/frontend.Dockerfile").write_text("FROM scratch\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(root), "add", "."], check=True)
        subprocess.run(["git", "-C", str(root), "commit", "-qm", "fixture"], check=True)
        sha = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        (root / "deploy/build-release-images.sh").write_bytes(BUILDER.read_bytes())
        (root / "deploy/build-release-images.sh").chmod(0o755)
        # Include the builder in the fixture commit so that the clean-tree gate is exercised.
        subprocess.run(["git", "-C", str(root), "add", "."], check=True)
        subprocess.run(["git", "-C", str(root), "commit", "-qm", "builder"], check=True)
        sha = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        bin_dir = Path(temporary) / "bin"
        bin_dir.mkdir()
        docker = bin_dir / "docker"
        log = Path(temporary) / "docker.log"
        docker.write_text(
            '#!/bin/sh\nprintf \'%s\\n\' "$*" >> "$DOCKER_LOG"\n'
            'case "$*" in *sigma-frontend:*) exit 17;; esac\n',
            encoding="utf-8",
        )
        docker.chmod(0o755)
        env = os.environ | {
            "PATH": str(bin_dir) + os.pathsep + os.environ["PATH"],
            "DOCKER_LOG": str(log),
        }
        result = subprocess.run(
            [str(root / "deploy/build-release-images.sh"), sha],
            cwd=root,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode != 0 and "frontend release image build failed" in result.stderr
        commands = log.read_text(encoding="utf-8").splitlines()
        assert len(commands) == 2 and "sigma-backend:" + sha + "-staging" in commands[0]
        assert "sigma-frontend:" + sha + "-staging" in commands[1]
        assert not any(line.startswith("image tag") for line in commands)
        assert "--label org.opencontainers.image.revision=" + sha in commands[0]
        mismatch = subprocess.run(
            [str(root / "deploy/build-release-images.sh"), "0" * 40],
            cwd=root,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert mismatch.returncode != 0 and "does not match requested release" in mismatch.stderr
        assert len(log.read_text(encoding="utf-8").splitlines()) == 2
        dirty = root / "untracked-fixture"
        dirty.write_text("dirty", encoding="utf-8")
        dirty_result = subprocess.run(
            [str(root / "deploy/build-release-images.sh"), sha],
            cwd=root,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert dirty_result.returncode != 0 and "clean worktree" in dirty_result.stderr
        assert len(log.read_text(encoding="utf-8").splitlines()) == 2
        assert dirty.exists()
    print(
        "PASS: failed frontend build leaves candidate undispatchable; mismatched or dirty source is rejected"
    )


if __name__ == "__main__":
    run()
