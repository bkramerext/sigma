"""Deterministic tests for production release image provenance."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("release_image", ROOT / "deploy/release_image.py")
assert SPEC is not None and SPEC.loader is not None
release_image = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release_image)


class ReleaseImageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="sigma-release-test-")
        self.addCleanup(self.temp.cleanup)
        self.repository = Path(self.temp.name) / "repo"
        self.repository.mkdir()
        self.git("init", "-q")
        self.git("config", "user.email", "test@example.invalid")
        self.git("config", "user.name", "Release Test")
        (self.repository / "Dockerfile").write_text("FROM scratch\nCOPY marker /marker\n")
        (self.repository / "deploy").mkdir()
        (self.repository / "deploy/frontend.Dockerfile").write_text(
            "FROM scratch\nCOPY marker /marker\n"
        )
        (self.repository / "marker").write_text("commit one\n")
        self.git("add", ".")
        self.git("commit", "-qm", "first")
        self.first = self.git("rev-parse", "HEAD")

    def git(self, *args: str) -> str:
        return subprocess.run(
            ["git", "-C", str(self.repository), *args], check=True, capture_output=True, text=True
        ).stdout.strip()

    def test_dirty_unrelated_head_builds_requested_commit_archive(self) -> None:
        (self.repository / "marker").write_text("commit two\n")
        self.git("add", "marker")
        self.git("commit", "-qm", "second")
        second = self.git("rev-parse", "HEAD")
        (self.repository / "marker").write_text("uncommitted dirty content\n")
        observed: list[tuple[list[str], str]] = []

        def docker(args: list[str]) -> str:
            observed.append((args, (Path(args[-1]) / "marker").read_text()))
            return ""

        release_image.build(self.repository, self.first, runner=docker)
        self.assertNotEqual(second, self.first)
        self.assertEqual(len(observed), 2)
        for index, (args, marker) in enumerate(observed):
            self.assertEqual(marker, "commit one\n")
            self.assertIn(f"org.opencontainers.image.revision={self.first}", args)
            self.assertIn(f"SIGMA_BUILD_COMMIT={self.first}", args)
            self.assertIn("--build-arg", args)
            image_name = "backend" if index == 0 else "frontend"
            self.assertIn(f"sigma-{image_name}:{self.first}", args)
            self.assertNotIn("uncommitted", marker)

    def test_unresolvable_or_malformed_requested_sha_fails_before_docker(self) -> None:
        invoked = False

        def docker(_args: list[str]) -> str:
            nonlocal invoked
            invoked = True
            return ""

        for requested in ("0" * 40, self.first[:12], self.first.upper()):
            with (
                self.subTest(requested=requested),
                self.assertRaises((ValueError, subprocess.CalledProcessError)),
            ):
                release_image.build(self.repository, requested, runner=docker)
        self.assertFalse(invoked)

    def test_production_frontend_requires_and_receives_release_sha(self) -> None:
        dockerfile = (ROOT / "deploy/frontend.Dockerfile").read_text(encoding="utf-8")
        vite = (ROOT / "frontend/vite.config.ts").read_text(encoding="utf-8")
        self.assertIn("ARG SIGMA_BUILD_COMMIT", dockerfile)
        self.assertIn("ENV SIGMA_BUILD_COMMIT=${SIGMA_BUILD_COMMIT}", dockerfile)
        self.assertIn("command === 'build'", vite)
        self.assertIn("if (requireIdentity) throw new Error", vite)

    def test_wrong_image_source_label_is_refused_and_correct_digests_are_recorded(self) -> None:
        def inspect(args: list[str]) -> str:
            if args[1] == "image":
                image = args[3]
                return json.dumps(
                    {
                        "Id": "sha256:" + "a" * 64,
                        "RepoDigests": [f"{image}@sha256:" + "b" * 64],
                        "Config": {"Labels": {release_image.LABEL: self.first}},
                    }
                )
            return json.dumps(
                {
                    "Image": "sha256:" + "a" * 64,
                    "State": {"Status": "running"},
                    "Config": {"Labels": {release_image.LABEL: self.first}},
                }
            )

        wrong = "1" * 40
        with self.assertRaisesRegex(ValueError, "source label"):
            release_image.verify(wrong, runner=inspect)
        infos = release_image.verify(self.first, runner=inspect)
        self.assertEqual(infos["backend"]["image_id"], "sha256:" + "a" * 64)
        record = release_image.record(
            self.first,
            Path(self.temp.name) / "records",
            {"backend": "backend-id", "frontend": "frontend-id"},
            runner=inspect,
        )
        document = json.loads(record.read_text())
        self.assertEqual(document["source_commit"], self.first)
        self.assertIn("repo_digests", document["images"]["frontend"])


if __name__ == "__main__":
    unittest.main()
