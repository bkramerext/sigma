"""Offline checks for the Ubuntu GCE host installer and read-only preflight."""

from __future__ import annotations

import contextlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
DEPLOY = ROOT / "deploy"
sys.path.insert(0, str(DEPLOY))
import gce_preflight  # pyright: ignore[reportMissingImports]


class GceHostToolingTests(unittest.TestCase):
    def test_installer_guard_accepts_ubuntu_os_release_spellings(self) -> None:
        guard = DEPLOY / "gce_host_guard.sh"
        for identity in ('ID=ubuntu\nVERSION_ID="24.04"\n', 'ID="ubuntu"\nVERSION_ID=24.04\n'):
            with self.subTest(identity=identity), tempfile.TemporaryDirectory() as temporary:
                release = Path(temporary) / "os-release"
                release.write_text(identity, encoding="utf-8")
                result = subprocess.run(
                    [
                        "bash",
                        "-c",
                        'source "$1"; require_ubuntu_2404 "$2"',
                        "test",
                        str(guard),
                        str(release),
                    ],
                    cwd=ROOT,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_installer_guard_blocks_non_ubuntu_without_running_installer(self) -> None:
        guard = DEPLOY / "gce_host_guard.sh"
        for identity in ('ID=debian\nVERSION_ID="12"\n', 'ID="fedora"\nVERSION_ID=40\n'):
            with self.subTest(identity=identity), tempfile.TemporaryDirectory() as temporary:
                release = Path(temporary) / "os-release"
                release.write_text(identity, encoding="utf-8")
                result = subprocess.run(
                    [
                        "bash",
                        "-c",
                        'source "$1"; require_ubuntu_2404 "$2"',
                        "test",
                        str(guard),
                        str(release),
                    ],
                    cwd=ROOT,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(result.returncode, 2)
                self.assertIn("BLOCKED:", result.stderr)

    def test_installer_runs_host_guard_before_mutative_commands(self) -> None:
        installer = (DEPLOY / "install-gce-host.sh").read_text(encoding="utf-8")
        self.assertIn("require_ubuntu_2404 /etc/os-release", installer)
        guard_position = installer.index("require_ubuntu_2404 /etc/os-release")
        for command in ("apt-get update", "curl --fail", "install -d"):
            self.assertLess(guard_position, installer.index(command))
        for path in (DEPLOY / "install-gce-host.sh", DEPLOY / "gce_host_guard.sh"):
            result = subprocess.run(
                ["bash", "-n", str(path)], capture_output=True, text=True, check=False
            )
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_preflight_exit_code_distinguishes_blocked_from_failed_checks(self) -> None:
        self.assertEqual(
            gce_preflight.result_exit_code([gce_preflight.Result("host", "BLOCKED", "")]), 2
        )
        self.assertEqual(
            gce_preflight.result_exit_code([gce_preflight.Result("service", "FAIL", "")]), 1
        )
        self.assertEqual(
            gce_preflight.result_exit_code(
                [
                    gce_preflight.Result("platform", "PASS", ""),
                    gce_preflight.Result("service", "FAIL", ""),
                ]
            ),
            1,
        )

    def test_ubuntu_preflight_reports_unready_host_as_failure_code(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sigma-ubuntu-preflight-test-") as temporary:
            root = Path(temporary)
            etc = root / "etc"
            etc.mkdir()
            (etc / "os-release").write_text('ID=ubuntu\nVERSION_ID="24.04"\n', encoding="utf-8")

            def unavailable(argv, **kwargs):
                return subprocess.CompletedProcess(argv, 1, "", "")

            preflight = gce_preflight.Preflight(
                env_file=root / "deploy.env",
                repository=ROOT,
                root=root,
                command=unavailable,
            )
            with patch("gce_preflight.os.uname", return_value=SimpleNamespace(machine="x86_64")):
                results = preflight.run()

        self.assertEqual(results[0].status, "PASS")
        self.assertTrue(any(result.status == "FAIL" for result in results))
        self.assertEqual(gce_preflight.result_exit_code(results), 1)

    def test_local_preflight_emits_safe_blocked_results(self) -> None:
        # Simulate an ineligible host deterministically. GitHub's Linux runner
        # may itself be Ubuntu 24.04 amd64, where real inspection legitimately
        # produces FAIL statuses instead of the intended BLOCKED-only control.
        with tempfile.TemporaryDirectory(prefix="sigma-preflight-test-") as temporary:
            env_file = Path(temporary) / "deploy.env"
            output = io.StringIO()
            with (
                patch.object(
                    gce_preflight.Preflight,
                    "check_platform",
                    lambda instance: instance.add(
                        "Platform", "BLOCKED", "simulated unsupported host"
                    ),
                ),
                patch.object(
                    sys,
                    "argv",
                    [
                        "gce_preflight.py",
                        "--json",
                        "--env-file",
                        str(env_file),
                        "--repository",
                        str(ROOT),
                    ],
                ),
                contextlib.redirect_stdout(output),
            ):
                result = gce_preflight.main()
        self.assertEqual(result, 2)
        entries = json.loads(output.getvalue())
        self.assertTrue(entries)
        self.assertEqual({item["status"] for item in entries}, {"BLOCKED"})
        self.assertNotIn("fixture-value-that-is-not-a-credential", output.getvalue())

    def test_deploy_environment_parser_rejects_shell_and_direct_credentials(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sigma-env-parse-") as temporary:
            path = Path(temporary) / "deploy.env"
            path.write_text(
                "SIGMA_CLOUD_OPENAI_API_KEY=fixture-value-that-is-not-a-credential\n",
                encoding="utf-8",
            )
            values, detail = gce_preflight._parse_env(path)
            self.assertIsNone(values)
            self.assertNotIn("fixture-value", detail)
            path.write_text("SIGMA_RELEASE=$(touch /tmp/not-allowed)\n", encoding="utf-8")
            values, detail = gce_preflight._parse_env(path)
            self.assertIsNone(values)
            self.assertIn("unsupported", detail)

    def test_parser_accepts_the_nonsecret_production_environment_shape(self) -> None:
        values = {
            "SIGMA_RELEASE": "a" * 40,
            "SIGMA_DOMAIN": "sigma-research.duckdns.org",
            "SIGMA_TLS_EMAIL": "ops@example.org",
            "SIGMA_CLOUD_BOOTSTRAP_ADMIN_EMAIL": "admin@example.org",
            "SIGMA_CLOUD_ADMIN_CONTACT_EMAIL": "ops@example.org",
            "GOOGLE_OIDC_CLIENT_ID": "fixture.apps.googleusercontent.com",
            "SIGMA_GOOGLE_OIDC_CLIENT_SECRET_FILE": "/run/sigma-secrets/google-oauth-client-secret",
            "SIGMA_CLOUD_OPENAI_API_KEY_FILE": "/run/sigma-secrets/openai-api-key",
            "SIGMA_SANDBOX_DOCKER_SOCKET": "/run/user/1002/docker.sock",
            "SIGMA_SANDBOX_DOCKER_GID": "1002",
            "SIGMA_STATE_DISK_MOUNT": "/srv/sigma-state",
        }
        with tempfile.TemporaryDirectory(prefix="sigma-env-valid-") as temporary:
            path = Path(temporary) / "deploy.env"
            path.write_text(
                "\n".join(f"{key}={value}" for key, value in values.items()) + "\n",
                encoding="utf-8",
            )
            parsed, detail = gce_preflight._parse_env(path)
        self.assertEqual(parsed, {**values, "SIGMA_CADDY_SCHEME": "https"})
        self.assertIn("valid", detail)

    def test_systemd_templates_preserve_mount_gate_and_rootless_boundary(self) -> None:
        app = (DEPLOY / "systemd/sigma.service").read_text(encoding="utf-8")
        sandbox = (DEPLOY / "systemd/sigma-sandbox.service.in").read_text(encoding="utf-8")
        socket_override = (DEPLOY / "systemd/docker.service.d/sigma-socket.conf").read_text(
            encoding="utf-8"
        )
        for expected in (
            "Requires=docker.service sigma-sandbox.service srv-sigma\\x2dstate.mount",
            "After=docker.service sigma-sandbox.service srv-sigma\\x2dstate.mount",
            "Restart=on-failure",
            "SIGMA_DEPLOY_ENV_FILE=/etc/sigma/deploy.env",
            "SIGMA_STATE_DISK_MOUNT=/srv/sigma-state",
            "gce_preflight.py --repository",
            "/opt/sigma/current/deploy/start-gce.sh",
        ):
            self.assertIn(expected, app)
        self.assertIn("user@__SANDBOX_UID__.service", sandbox)
        self.assertIn("systemctl --user start docker.service", sandbox)
        self.assertIn("chmod 0660 %t/docker.sock", socket_override)
        self.assertNotIn("docker.sock", app.split("ExecStartPre=")[0])

    def test_preflight_and_installer_keep_production_rootless_gate(self) -> None:
        installer = (DEPLOY / "install-gce-host.sh").read_text(encoding="utf-8")
        guard = (DEPLOY / "gce_host_guard.sh").read_text(encoding="utf-8")
        preflight = (DEPLOY / "gce_preflight.py").read_text(encoding="utf-8")
        self.assertIn("${VERSION_ID:-} != 24.04", guard)
        self.assertIn("docker-ce-rootless-extras", installer)
        self.assertIn("docker-ce=${DOCKER_CE_VERSION}", installer)
        self.assertIn("docker-compose-plugin=${COMPOSE_VERSION}", installer)
        socket_override = (DEPLOY / "systemd/docker.service.d/sigma-socket.conf").read_text(
            encoding="utf-8"
        )
        self.assertIn("ExecStartPost=/usr/bin/chgrp sigma-sandbox", socket_override)
        self.assertIn("rootless", preflight)
        self.assertIn("test", preflight)


if __name__ == "__main__":
    unittest.main()
