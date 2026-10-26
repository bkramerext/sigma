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
import prepare_state_disk  # pyright: ignore[reportMissingImports]


class GceHostToolingTests(unittest.TestCase):
    def test_host_readiness_derives_rootless_socket_without_production_environment(self) -> None:
        preflight = gce_preflight.Preflight(host_readiness=True)
        with patch("gce_preflight._sandbox_uid", return_value=1001):
            self.assertEqual(preflight._sandbox_socket(), "/run/user/1001/docker.sock")
        self.assertEqual(preflight.values, {})

    def test_host_readiness_reboot_gate_requires_enabled_daemons_but_not_app(self) -> None:
        calls: list[list[str]] = []
        preflight = gce_preflight.Preflight(host_readiness=True, after_reboot=True)

        def command(argv, **kwargs):
            calls.append(argv)
            output = "yes\n" if argv[0] == "loginctl" else ""
            return subprocess.CompletedProcess(argv, 0, output, "")

        with (
            patch("gce_preflight._sandbox_uid", return_value=1001),
            patch.object(preflight, "command", side_effect=command),
        ):
            preflight.check_services()
        self.assertIn(["systemctl", "is-enabled", "--quiet", "docker.service"], calls)
        self.assertIn(["systemctl", "is-enabled", "--quiet", "sigma-sandbox.service"], calls)
        self.assertNotIn(["systemctl", "is-enabled", "--quiet", "sigma.service"], calls)
        self.assertIn(
            ["loginctl", "show-user", "--property=Linger", "--value", "sigma-sandbox"], calls
        )
        self.assertTrue(all(result.status == "PASS" for result in preflight.results))

    def test_host_readiness_mode_does_not_require_deploy_env_or_secret_checks(self) -> None:
        preflight = gce_preflight.Preflight(host_readiness=True)
        with (
            patch.object(preflight, "check_platform") as platform,
            patch.object(preflight, "check_mount") as mount,
            patch.object(preflight, "check_services") as services,
            patch.object(preflight, "check_host_daemon") as host_docker,
            patch.object(preflight, "check_rootless_daemon") as rootless,
            patch.object(preflight, "check_socket") as socket,
            patch.object(preflight, "check_runtime_images") as images,
            patch.object(preflight, "check_app_unit") as app_unit,
            patch.object(preflight, "check_env") as environment,
            patch.object(preflight, "check_secret_files") as secrets,
            patch.object(preflight, "_command"),
            patch("gce_preflight.os.geteuid", return_value=0),
        ):
            platform.side_effect = lambda: preflight.add("Ubuntu production host", "PASS", "test")
            preflight.run()
        environment.assert_not_called()
        secrets.assert_not_called()
        for check in (mount, services, host_docker, rootless, socket, images, app_unit):
            check.assert_called_once()

    def test_preflight_requires_all_healthchecks_and_healthy_startup_dependencies(self) -> None:
        services = {
            "backend": {
                "read_only": True,
                "group_add": ["1002"],
                "volumes": [
                    {
                        "source": "/run/user/1002/docker.sock",
                        "target": "/run/sigma-sandbox/docker.sock",
                        "read_only": True,
                    }
                ],
                "healthcheck": {"test": ["CMD", "python", "-m", "sigma.deployment_health"]},
            },
            "frontend": {"healthcheck": {"test": ["CMD-SHELL", "wget /"]}},
            "edge": {
                "ports": ["80:80"],
                "healthcheck": {"test": ["CMD-SHELL", "wget localhost:2019"]},
                "depends_on": {
                    "backend": {"condition": "service_healthy"},
                    "frontend": {"condition": "service_healthy"},
                },
            },
        }
        configuration = {
            "services": services,
            "volumes": {"sigma-state": {"driver_opts": {"device": "/srv/sigma-state/auth"}}},
        }
        preflight = gce_preflight.Preflight(repository=ROOT)
        preflight.values = {
            "SIGMA_SANDBOX_DOCKER_GID": "1002",
            "SIGMA_SANDBOX_DOCKER_SOCKET": "/run/user/1002/docker.sock",
        }

        def compose_result(argv, **kwargs):
            return subprocess.CompletedProcess(argv, 0, json.dumps(configuration), "")

        with patch.object(preflight, "command", side_effect=compose_result):
            preflight.check_compose()
        self.assertEqual(preflight.results[-1].status, "PASS")

        services["edge"].pop("healthcheck")
        with patch.object(preflight, "command", side_effect=compose_result):
            preflight.check_compose()
        self.assertEqual(preflight.results[-1].status, "FAIL")

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

    def test_installer_keeps_state_mount_root_private(self) -> None:
        installer = (DEPLOY / "install-gce-host.sh").read_text(encoding="utf-8")
        self.assertIn("state_mount=/srv/sigma-state", installer)
        self.assertIn('mountpoint --quiet "$state_mount"', installer)
        self.assertIn("stat -c '%u:%a' \"$state_mount\"", installer)
        self.assertIn('install -d -o root -g root -m 0700 "$state_mount"', installer)
        self.assertIn("state mount path contains data but is not mounted", installer)
        self.assertNotIn("install -d -o root -g root -m 0755 /srv/sigma-state", installer)

    def test_runtime_toolchains_are_pinned_in_their_container_recipes(self) -> None:
        backend = (ROOT / "Dockerfile").read_text(encoding="utf-8")
        runner = (ROOT / "sandbox-poc/Dockerfile").read_text(encoding="utf-8")
        sage = (ROOT / "sandbox-poc/Dockerfile.sage").read_text(encoding="utf-8")
        requirements = (ROOT / "sandbox-poc/requirements.txt").read_text(encoding="utf-8")
        image_build = (DEPLOY / "build-sandbox-images.sh").read_text(encoding="utf-8")
        self.assertIn("ghcr.io/astral-sh/uv:0.12.17@sha256:", backend)
        self.assertIn("uv sync --locked --no-dev", backend)
        self.assertIn("tectonic%400.15.0", backend)
        self.assertIn("--checksum=sha256:", backend)
        self.assertIn("COPY --from=tectonic /usr/local/bin/tectonic", backend)
        self.assertIn("python:3.12.8-slim@sha256:", runner)
        self.assertIn("sagemath/sagemath:10.8@sha256:", sage)
        self.assertTrue(all("==" in line for line in requirements.splitlines() if line.strip()))
        self.assertIn('DOCKER_HOST="unix://${socket}"', image_build)
        self.assertIn("sigma-research-python:0.1", image_build)
        self.assertIn("sigma-research-sage:10.8", image_build)

    def test_state_mount_fstab_planning_is_uuid_based_hardened_and_idempotent(self) -> None:
        uuid = "12345678-1234-1234-1234-123456789abc"
        planned = prepare_state_disk.plan_fstab("# host fstab\n", uuid, "ext4")
        fields = planned.splitlines()[1].split()
        self.assertEqual(fields[:3], [f"UUID={uuid}", "/srv/sigma-state", "ext4"])
        self.assertTrue(
            {"rw", "nodev", "nosuid", "noexec", "nofail", "x-systemd.device-timeout=60s"}.issubset(
                fields[3].split(",")
            )
        )
        self.assertEqual(prepare_state_disk.plan_fstab(planned, uuid, "ext4"), planned)

    def test_state_mount_fstab_planning_rejects_conflicts_and_never_formats(self) -> None:
        uuid = "12345678-1234-1234-1234-123456789abc"
        with self.assertRaisesRegex(ValueError, "different filesystem"):
            prepare_state_disk.plan_fstab(
                "UUID=aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa /srv/sigma-state ext4 defaults 0 2\n",
                uuid,
                "ext4",
            )
        with self.assertRaisesRegex(ValueError, "already configured"):
            prepare_state_disk.plan_fstab(
                f"UUID={uuid} /mnt/other ext4 defaults 0 2\n",
                uuid,
                "ext4",
            )
        source = (DEPLOY / "prepare_state_disk.py").read_text(encoding="utf-8")
        self.assertNotRegex(source, r"\bmkfs(?:\.[A-Za-z0-9_-]+)?\b")
        self.assertIn("blkid", source)

    def test_state_mount_uuid_validation_and_existing_options(self) -> None:
        uuid = "12345678-1234-1234-1234-123456789abc"
        with self.assertRaisesRegex(ValueError, "standard"):
            prepare_state_disk.validate_uuid("not-a-uuid")
        previous = f"UUID={uuid} /srv/sigma-state ext4 defaults,exec,suid,dev,noauto 0 2\n"
        planned = prepare_state_disk.plan_fstab(previous, uuid, "ext4")
        options = planned.split()[3].split(",")
        self.assertNotIn("exec", options)
        self.assertNotIn("suid", options)
        self.assertNotIn("dev", options)
        self.assertNotIn("noauto", options)
        self.assertTrue({"rw", "nodev", "nosuid", "noexec", "nofail"}.issubset(options))

    def test_preflight_requires_matching_uuid_backed_state_mount(self) -> None:
        uuid = "12345678-1234-1234-1234-123456789abc"
        with tempfile.TemporaryDirectory(prefix="sigma-gce-mount-test-") as temporary:
            root = Path(temporary)
            mount = root / "srv" / "sigma-state"
            mount.mkdir(parents=True)
            mount.chmod(0o700)

            def matching_mount(argv, **kwargs):
                if argv[0] == "findmnt":
                    output = f"{uuid} ext4 rw,nodev,nosuid,noexec\n"
                else:
                    output = ""
                return subprocess.CompletedProcess(argv, 0, output, "")

            preflight = gce_preflight.Preflight(root=root, command=matching_mount)
            with (
                patch("gce_preflight.os.path.ismount", return_value=True),
                patch("gce_preflight.pwd.getpwnam", return_value=SimpleNamespace(pw_gid=1002)),
            ):
                preflight.check_mount()
            statuses = {result.name: result.status for result in preflight.results}
            self.assertEqual(statuses["Persistent state source"], "PASS")
            self.assertEqual(statuses["Persistent state mount"], "PASS")

            def mismatched_mount(argv, **kwargs):
                output = (
                    f"{uuid} ext4 rw,nodev,nosuid,noexec\n"
                    if "--fstab" in argv
                    else f"{'a' * 8}-aaaa-aaaa-aaaa-aaaaaaaaaaaa ext4 rw,nodev,nosuid,noexec\n"
                )
                return subprocess.CompletedProcess(argv, 0, output, "")

            preflight = gce_preflight.Preflight(root=root, command=mismatched_mount)
            with patch("gce_preflight.os.path.ismount", return_value=True):
                preflight.check_mount()
            statuses = {result.name: result.status for result in preflight.results}
            self.assertEqual(statuses["Persistent state source"], "FAIL")

            def weak_fstab_mount(argv, **kwargs):
                if "--fstab" in argv:
                    output = f"{uuid} ext4 defaults,rw\n"
                else:
                    output = f"{uuid} ext4 rw,nodev,nosuid,noexec\n"
                return subprocess.CompletedProcess(argv, 0, output, "")

            preflight = gce_preflight.Preflight(root=root, command=weak_fstab_mount)
            with patch("gce_preflight.os.path.ismount", return_value=True):
                preflight.check_mount()
            statuses = {result.name: result.status for result in preflight.results}
            self.assertEqual(statuses["Persistent state options"], "FAIL")

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
            "Requires=docker.service sigma-sandbox.service RequiresMountsFor=/srv/sigma-state",
            "After=docker.service sigma-sandbox.service RequiresMountsFor=/srv/sigma-state",
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
