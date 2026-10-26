"""Deterministic contract tests for the repository Codex launcher."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class CodexLauncherTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "checkout"
        (self.root / "scripts").mkdir(parents=True)
        shutil.copy2(ROOT / "scripts/codex", self.root / "scripts/codex")
        shutil.copy2(ROOT / "scripts/codex-env.sh", self.root / "scripts/codex-env.sh")
        self.bin = Path(self.temp.name) / "bin"
        self.bin.mkdir()
        self.capture = Path(self.temp.name) / "capture.json"
        self.env = {
            **os.environ,
            "PATH": f"{self.bin}:/usr/bin:/bin",
            "SIGMA_CAPTURE": str(self.capture),
            "HOME": str(Path(self.temp.name) / "home"),
        }
        Path(self.env["HOME"]).mkdir()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def install_fake_codex(self, exit_code: int = 0) -> None:
        executable = self.bin / "codex"
        executable.write_text(
            "#!/usr/bin/env python3\n"
            "import json, os, sys\n"
            "with open(os.environ['SIGMA_CAPTURE'], 'w') as out:\n"
            " json.dump({'args': sys.argv[1:], 'cwd': os.getcwd(), "
            "'root': os.environ.get('SIGMA_REPO_ROOT'), "
            "'project': os.environ.get('SIGMA_GCP_PROJECT')}, out)\n"
            f"sys.exit({exit_code})\n",
            encoding="utf-8",
        )
        executable.chmod(0o755)

    def run_wrapper(self, *args: str, cwd: Path | None = None, extra_env=None):
        env = {**self.env, **(extra_env or {})}
        return subprocess.run(
            ["/bin/bash", str(self.root / "scripts/codex"), *args],
            cwd=cwd or Path(self.temp.name),
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_forwards_arguments_and_resolves_root_outside_checkout(self) -> None:
        self.install_fake_codex()
        result = self.run_wrapper("--some-flag", "two words", "", "--", "-x")
        self.assertEqual(result.returncode, 0, result.stderr)
        captured = json.loads(self.capture.read_text(encoding="utf-8"))
        self.assertEqual(captured["args"], ["--some-flag", "two words", "", "--", "-x"])
        self.assertEqual(captured["root"], str(self.root.resolve()))
        self.assertEqual(captured["cwd"], str(Path(self.temp.name).resolve()))
        self.assertEqual(captured["project"], "sigma-research-prod")

    def test_missing_codex_returns_127(self) -> None:
        result = self.run_wrapper()
        self.assertEqual(result.returncode, 127)
        self.assertIn("Codex CLI executable not found", result.stderr)

    def test_recursion_guard_returns_126(self) -> None:
        self.install_fake_codex()
        result = self.run_wrapper(extra_env={"SIGMA_CODEX_WRAPPER_ACTIVE": "1"})
        self.assertEqual(result.returncode, 126)
        self.assertIn("recursive wrapper invocation prevented", result.stderr)
        self.assertFalse(self.capture.exists())

    def test_environment_sourcing_is_idempotent(self) -> None:
        command = (
            f'. "{self.root}/scripts/codex-env.sh"; first=$PATH; '
            f'. "{self.root}/scripts/codex-env.sh"; '
            'test "$first" = "$PATH" && '
            'test "$SIGMA_REPO_ROOT" = "' + str(self.root.resolve()) + '" && '
            'test "$SIGMA_GCP_PROJECT" = sigma-research-prod && '
            'test "$SIGMA_GCP_ZONE" = us-west1-b'
        )
        result = subprocess.run(
            ["/bin/bash", "-c", command],
            env=self.env,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_exit_code_is_preserved(self) -> None:
        self.install_fake_codex(exit_code=37)
        self.assertEqual(self.run_wrapper("--version").returncode, 37)

    def test_signal_is_preserved(self) -> None:
        executable = self.bin / "codex"
        executable.write_text(
            "#!/usr/bin/env python3\nimport os, signal\nos.kill(os.getpid(), signal.SIGTERM)\n",
            encoding="utf-8",
        )
        executable.chmod(0o755)
        self.assertEqual(self.run_wrapper().returncode, -15)


if __name__ == "__main__":
    unittest.main()
