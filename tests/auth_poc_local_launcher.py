"""No-Docker checks for the opt-in local SIGMA pill/container broker path.

Runtime Docker Desktop acceptance is separate. These tests guard against
accidentally applying local bind-mount UID overrides to hosted users.
"""

from __future__ import annotations

import importlib.util
import os
import shutil
import socket
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("local_poc_broker", ROOT / "auth-poc/host_broker.py")
assert spec and spec.loader
broker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(broker)


class LocalBrokerTests(unittest.TestCase):
    def test_poc_uses_current_host_user_and_private_per_user_mounts(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            state = root / "state"
            gateway = root / "gateways"
            state.mkdir(mode=0o700)
            gateway.mkdir(mode=0o711)
            gateway.chmod(0o711)
            workspace = "a" * 32
            with patch.dict(
                os.environ,
                {
                    "SIGMA_AUTH_BROKER_LOCAL_POC": "1",
                    "SIGMA_AUTH_BROKER_STATE_ROOT": str(state),
                    "SIGMA_AUTH_BROKER_GATEWAY_ROOT": str(gateway),
                    "SIGMA_RELEASE": "b" * 40,
                    "SIGMA_AUTH_POC_CHECKOUT_ID": "c" * 32,
                },
            ):
                prepared_state = broker.prepare_state(workspace)
                prepared_gateway = broker.prepare_gateway(workspace)
                self.assertEqual(prepared_state, state / workspace)
                self.assertEqual(prepared_gateway, gateway / workspace)
                self.assertEqual(stat.S_IMODE(prepared_gateway.stat().st_mode), 0o700)
                self.assertEqual(prepared_gateway.stat().st_uid, os.geteuid())
                env = broker.compose_env(workspace)
                self.assertEqual(env["SIGMA_AUTH_POC_LOCAL_UID"], str(os.geteuid()))
                self.assertEqual(env["SIGMA_AUTH_POC_LOCAL_GID"], str(os.getegid()))
                self.assertEqual(env["SIGMA_RELEASE"], "b" * 40)
                self.assertEqual(env["SIGMA_AUTH_POC_CHECKOUT_ID"], "c" * 32)
                args = broker.compose_args(workspace, "ps")
                self.assertIn(str(ROOT / "deploy/auth-poc.user.local.yaml"), args)
                self.assertEqual(args[-1], "ps")
                self.assertTrue((prepared_state / "auth/auth-poc").is_dir())

    def test_production_broker_never_uses_local_uid_overlay(self) -> None:
        with patch.dict(
            os.environ,
            {
                "SIGMA_AUTH_BROKER_LOCAL_POC": "0",
                "SIGMA_RELEASE": "c" * 40,
                "SIGMA_AUTH_BROKER_STATE_ROOT": "/tmp/sigma-test-state",
                "SIGMA_AUTH_BROKER_GATEWAY_ROOT": "/tmp/sigma-test-gateways",
            },
        ):
            self.assertNotIn(
                str(ROOT / "deploy/auth-poc.user.local.yaml"),
                broker.compose_args("d" * 32, "status"),
            )
            self.assertNotIn("SIGMA_AUTH_POC_LOCAL_UID", broker.compose_env("d" * 32))

    def test_broker_rejects_caller_workspace_path(self) -> None:
        with self.assertRaises(ValueError):
            broker.compose_args("../other-user", "ps")


class ProdLifecycleTests(unittest.TestCase):
    """Local --prod owns exactly the containers it starts, with no companion CLI."""

    @classmethod
    def setUpClass(cls) -> None:
        spec = importlib.util.spec_from_file_location(
            "sigma_local_personal_test", ROOT / "src/sigma/local_personal.py"
        )
        assert spec and spec.loader
        cls.module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = cls.module
        spec.loader.exec_module(cls.module)

    def test_mac_long_tmpdir_uses_short_secure_gateway_paths(self) -> None:
        mod = self.module
        with patch.dict(
            os.environ,
            {"TMPDIR": "/private/var/folders/" + ("q" * 90) + "/T/"},
        ):
            runtime = mod._local_runtime_directory()
            try:
                self.assertEqual(runtime.parent, Path("/tmp"))
                self.assertEqual(stat.S_IMODE(runtime.stat().st_mode), 0o700)
                for name in ("vnc.sock", "model.sock"):
                    socket_path = runtime / "gateways" / ("a" * 32) / name
                    self.assertLess(len(os.fsencode(socket_path)), 104)
            finally:
                shutil.rmtree(runtime)

    def test_personal_connect_and_disconnect_ui_guards(self) -> None:
        source = (ROOT / "frontend/src/ai-connection.tsx").read_text(encoding="utf-8")
        # A previously verified token is used before the interactive iframe.
        self.assertIn("await finishContainerBrowserStart(sequence)", source)
        self.assertIn("account?.status === 'verified'", source)
        launch = source.split("async function startContainerPersonalBrowser()", 1)[1]
        self.assertIn("setPersonalDialogState('starting')", launch)
        self.assertLess(
            launch.index("setPersonalDialogState('starting')"),
            launch.index("await pendingPersonalStop.current"),
        )
        self.assertLess(
            launch.index("setPersonalDialogState('starting')"),
            launch.index("fetch(windowAuthUrl('/api/ai/personal-browser/start')"),
        )
        self.assertNotIn("setPersonalDialogState('closed')", launch.split("try {", 1)[0])
        self.assertIn("setPersonalDialogState('closed')", source)
        # User confirmation must report progress and surface failures, never
        # leave an unresponsive Confirm button on top of a failed HTTP call.
        self.assertIn("setDisconnectError", source)
        self.assertIn('{disconnecting ? <span role="status">Disconnecting…</span>', source)
        self.assertIn("if (result.disconnected !== true)", source)
        self.assertIn("await stopContainerPersonalBrowser().catch(", source)
        self.assertIn("state !== 'error' ? ' is-viewing' : ''", source)
        # Project header disables pointer events on its container and explicitly
        # re-enables only buttons/links/summaries. An iframe rendered there
        # displays remote frames but cannot accept pointer input. The modal
        # MUST be portaled out to body instead of inheriting the header mask.
        self.assertIn(
            "createPortal(\n    <PersonalBrowserDialog state={personalDialogState}",
            source,
        )
        self.assertIn(
            "onRetry={() => void startContainerPersonalBrowser()}/>,\n    document.body,",
            source,
        )
        workspace_css = (ROOT / "frontend/src/workspace.css").read_text(encoding="utf-8")
        self.assertIn(".header-controls {", workspace_css)
        self.assertIn("pointer-events: none;", workspace_css)

        self.assertNotIn("personal-chatgpt-preview-note", source)
        self.assertNotIn("OpenAI's personal ChatGPT sign-in uses", source)
        boot = (ROOT / "auth-poc/boot.sh").read_text(encoding="utf-8")
        self.assertIn("--app=http://127.0.0.1:8001/", boot)
        self.assertNotIn("set -- http://127.0.0.1:8001/", boot)
        # Host macOS Caps Lock is already applied to the keysyms sent by noVNC.
        # The isolated X server must not apply a second independent lock state;
        # reset any held Shift/Caps Lock on X11 VNC startup as well.
        self.assertIn("x11vnc -display :99", boot)
        self.assertIn("-skip_lockkeys -clear_all", boot)
        # Moving "Use passkey from another device" to the context menu avoids
        # obscuring the Google email field, without disabling WebAuthn itself.
        self.assertIn("--enable-features=WebAuthnUsePasskeyFromAnotherDeviceInContextMenu", boot)
        self.assertIn("--disable-features=AutofillReintroduceHybridPasskeyDropdownItem", boot)
        self.assertNotIn("--disable-features=WebAuthentication", boot)

    def test_prod_runtime_prepares_private_broker_and_preserves_state(self) -> None:
        mod = self.module
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp) / "home"
            home.mkdir()
            runtime = Path(temp) / "runtime"
            runtime.mkdir()
            active_socket = None

            class BrokerProcess:
                stopped = False

                def poll(self):
                    return 0 if self.stopped else None

                def terminate(self):
                    self.stopped = True

                def wait(self, timeout=None):
                    return 0

            fake = BrokerProcess()
            preparer = BrokerProcess()
            preparer.stopped = True

            def start_broker(args, **kwargs):
                nonlocal active_socket
                env = kwargs["env"]
                if "--prepare" in args:
                    self.assertEqual(env["SIGMA_AUTH_POC_BROWSER_PLATFORM"], "linux/arm64")
                    self.assertNotIn("SIGMA_AUTH_POC_RPC_SEED", env)
                    self.assertTrue(kwargs["start_new_session"])
                    return preparer
                self.assertEqual(env["SIGMA_AUTH_POC_REAL_SIGNIN"], "0")
                self.assertEqual(env["SIGMA_AUTH_POC_LOCAL_REAL_SIGNIN"], "1")
                self.assertEqual(env["SIGMA_PERSONAL_BROWSER_LAB_ENABLED"], "1")
                self.assertRegex(env["SIGMA_AUTH_POC_RPC_SEED"], r"[0-9a-f]{64}\Z")
                self.assertNotEqual(env["SIGMA_AUTH_POC_RPC_SEED"], "secret")
                active_socket = socket.socket(socket.AF_UNIX)
                active_socket.bind(env["SIGMA_AUTH_BROKER_SOCKET"])
                os.chmod(env["SIGMA_AUTH_BROKER_SOCKET"], 0o600)
                active_socket.listen()
                return fake

            commands = []

            def command(args, *, env, timeout=90):
                commands.append(args)
                return ""

            with (
                patch.object(
                    mod, "_docker_environment", return_value={"SIGMA_AUTH_POC_RPC_SEED": "secret"}
                ),
                patch.object(mod, "_release_images", return_value=("a" * 40, "linux/arm64")),
                patch.object(mod, "_owned_workspaces", return_value=set()),
                patch.object(mod.Path, "home", return_value=home),
                patch.object(mod.tempfile, "mkdtemp", return_value=str(runtime)),
                patch.object(mod.subprocess, "Popen", side_effect=start_broker),
                patch.object(mod, "_command", side_effect=command),
            ):
                running = mod.LocalPersonalRuntime.start()
                self.assertEqual(stat.S_IMODE((runtime / "broker").stat().st_mode), 0o711)
                self.assertEqual(stat.S_IMODE((runtime / "gateways").stat().st_mode), 0o711)
                self.assertEqual(stat.S_IMODE(running.state_root.stat().st_mode), 0o700)
                self.assertEqual(running.env["SIGMA_AUTH_POC_BROWSER_PLATFORM"], "linux/arm64")
                self.assertEqual((runtime / "prepare.status").read_text(), "preparing")
                (runtime / "gateways" / ("b" * 32)).mkdir()
                (runtime / "gateways" / "not-a-workspace").mkdir()
                running.close()
                self.assertEqual(len(commands), 1)
                self.assertIn("deploy/auth-poc.user.local.yaml", commands[0])
                self.assertIn("down", commands[0])
                self.assertEqual(commands[0][-1], "--remove-orphans")
                self.assertFalse(runtime.exists())
                self.assertTrue(running.state_root.is_dir())
                self.assertEqual(running.state_root.name, "personal-signin-preview-state")
                self.assertTrue(fake.stopped)
            if active_socket is not None:
                active_socket.close()

    def test_prod_retains_local_real_authorization_but_never_bypasses_worker(self) -> None:
        ui = (ROOT / "src/sigma/ui.py").read_text(encoding="utf-8")
        self.assertIn("LocalPersonalRuntime.start()", ui)
        self.assertIn("personal_runtime.close()", ui)
        self.assertIn("if prod:", ui)
        local = (ROOT / "src/sigma/local_personal.py").read_text(encoding="utf-8")
        self.assertIn('"SIGMA_AUTH_POC_REAL_SIGNIN": "0"', local)
        self.assertIn('"SIGMA_AUTH_POC_LOCAL_REAL_SIGNIN": "1"', local)
        self.assertIn('"SIGMA_AUTH_POC_RPC_SEED": secrets.token_hex(32)', local)
        self.assertIn('"SIGMA_LOCAL_HOSTED_NOTICE_PREVIEW"] = "false"', ui)
        self.assertIn('"SIGMA_AUTH_POC_RPC_SEED",', ui)
        self.assertIn("legacy_local_admin = (", ui)
        self.assertIn('"true" if signin or legacy_local_admin else "false"', ui)
        self.assertIn('not os.environ.get("GOOGLE_OIDC_CLIENT_ID", "").strip()', ui)
        self.assertIn('not os.environ.get("GOOGLE_OIDC_CLIENT_SECRET", "").strip()', ui)
        self.assertIn('not os.environ.get("GOOGLE_OIDC_CLIENT_SECRET_FILE", "").strip()', ui)
        self.assertNotIn('"true" if signin or prod else "false"', ui)
        self.assertIn('"SIGMA_LOCAL_PERSONAL_STARTUP_ERROR"', ui)
        self.assertIn('"SIGMA_PERSONAL_BROWSER_LAB_ENABLED": "1"', ui)
        api = (ROOT / "src/sigma/api.py").read_text(encoding="utf-8")
        self.assertIn('os.environ.get("SIGMA_LOCAL_PERSONAL_STARTUP_ERROR")', api)

    def test_arm64_platform_selected_before_build_and_cache_revalidated(self) -> None:
        mod = self.module
        observed = []

        def run(args, *, env, timeout=90):
            observed.append((list(args), dict(env)))
            if args[:2] == ["git", "rev-parse"]:
                return "a" * 40
            if args[:2] == ["docker", "info"]:
                return "aarch64"
            return ""

        with (
            patch.object(mod, "_command", side_effect=run),
            patch.object(mod, "_images_compatible", side_effect=[False, True]),
        ):
            env = {"PATH": "/usr/bin"}
            self.assertEqual(mod._release_images(env), ("a" * 40, "linux/arm64"))
            self.assertEqual(env["SIGMA_AUTH_POC_BROWSER_PLATFORM"], "linux/arm64")
            compose_build = [values for args, values in observed if args[-1] == "build"]
            self.assertEqual(len(compose_build), 1)
            self.assertEqual(compose_build[0]["SIGMA_AUTH_POC_BROWSER_PLATFORM"], "linux/arm64")
            tags = [args for args, _ in observed if args[:2] == ["docker", "tag"]]
            self.assertEqual(len(tags), 2)

    def test_orphans_require_verified_local_owner_and_checkout(self) -> None:
        mod = self.module
        observed = []

        def run(args, *, env, timeout=90):
            observed.append(args)
            return "sigma-personal-" + "a" * 32 + "\nforeign\nsigma-personal-" + "b" * 32

        env = {"SIGMA_AUTH_POC_CHECKOUT_ID": "c" * 32}
        with patch.object(mod, "_command", side_effect=run):
            self.assertEqual(mod._owned_workspaces(env), {"a" * 32, "b" * 32})
        self.assertIn("label=io.sigma.personal.checkout=" + "c" * 32, observed[0])
        self.assertIn("label=io.sigma.personal.owner=" + str(os.geteuid()), observed[0])

    def test_preparation_status_is_private_and_atomic(self) -> None:
        mod = self.module
        with tempfile.TemporaryDirectory() as temp:
            marker = Path(temp) / "prepare.status"
            mod._preparation_state(marker, "preparing")
            self.assertEqual(marker.read_text(), "preparing")
            mod._preparation_state(marker, "ready")
            self.assertEqual(marker.read_text(), "ready")
            self.assertEqual(stat.S_IMODE(marker.stat().st_mode), 0o600)
            self.assertFalse(marker.with_suffix(".next").exists())

    def test_crashed_preparation_becomes_actionable_failure(self) -> None:
        mod = self.module
        with tempfile.TemporaryDirectory() as temp:
            runtime = Path(temp)
            marker = runtime / "prepare.status"
            mod._preparation_state(marker, "preparing")

            class FinishedProcess:
                def poll(self):
                    return 1

            class Runtime:
                def __init__(self, root: Path) -> None:
                    self.runtime = root
                    self.preparation = FinishedProcess()

            instance = Runtime(runtime)
            mod.LocalPersonalRuntime.refresh_preparation(instance)
            self.assertEqual(marker.read_text(), "failed")

    def test_connection_dialog_retries_readiness_without_restarting_docker(self) -> None:
        source = (ROOT / "frontend/src/ai-connection.tsx").read_text(encoding="utf-8")
        dialog = source.split("function PersonalBrowserDialog", 1)[1]
        self.assertIn('className="sigma-text-action" type="button" onClick={onRetry}', dialog)
        self.assertIn("const deadline = Date.now() + 60_000", dialog)
        self.assertIn("'/api/ai/personal-browser/status'", dialog)
        self.assertIn("data.browser_status === 'ready'", dialog)
        self.assertNotIn("if (data.browser_status !== 'ready')", dialog)
        self.assertNotIn("OpenAI's personal ChatGPT sign-in uses a localhost callback", dialog)
        self.assertIn('className="personal-chatgpt-browser-frame"', dialog)

    def test_broker_health_accepts_http_10_and_http_11_only(self) -> None:
        from unittest.mock import MagicMock

        spec = importlib.util.spec_from_file_location(
            "sigma_host_broker_readiness_test", ROOT / "auth-poc/host_broker.py"
        )
        assert spec and spec.loader
        broker = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(broker)

        for response, expected in [
            (b"HTTP/1.0 200 OK\r\n\r\n", True),
            (b"HTTP/1.1 200 OK\r\n\r\n", True),
            (b"HTTP/1.1 403 Forbidden\r\n\r\n", False),
        ]:
            conn = MagicMock()
            conn.__enter__.return_value = conn
            conn.recv.return_value = response
            with patch.object(broker.socket, "socket", return_value=conn):
                self.assertEqual(
                    broker._socket_http_ready(Path("/tmp/virtual.sock"), "/vnc.html"),
                    expected,
                )

    def test_broker_readiness_logs_only_stage_transitions(self) -> None:
        spec = importlib.util.spec_from_file_location(
            "sigma_host_broker_diagnostics_test", ROOT / "auth-poc/host_broker.py"
        )
        assert spec and spec.loader
        broker = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(broker)
        with patch("builtins.print") as output:
            broker._readiness_report("a" * 32, "browser container health starting")
            broker._readiness_report("a" * 32, "browser container health starting")
            broker._readiness_report("a" * 32, "VNC viewer relay did not return HTTP 200")
            self.assertEqual(output.call_count, 2)
            self.assertNotIn("a" * 32, str(output.call_args_list))

    def test_diagnostics_do_not_relay_untrusted_docker_log_content(self) -> None:
        spec = importlib.util.spec_from_file_location(
            "sigma_broker_safe_log_test", ROOT / "auth-poc/host_broker.py"
        )
        assert spec and spec.loader
        broker = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(broker)
        raw = (
            "SIGMA Personal browser: starting Xvfb\n"
            "https://auth.openai.com/authorize?code=SECRET\n"
            "SIGMA Personal worker: starting model gateway on private port 8002\n"
            "SIGMA Personal browser: VNC relay launched; starting Chromium\n"
            "token=SECRET credential=SECRET\n"
        )
        messages = broker._safe_milestones(raw)
        self.assertEqual(len(messages), 3)
        self.assertNotIn("SECRET", repr(messages))
        self.assertFalse(broker._safe_probe_line("access_token=secret"))
        self.assertFalse(broker._safe_probe_line("component=worker;token=secret"))
        self.assertTrue(broker._safe_probe_line("websocket_http_6080=http_200"))

    def test_host_readiness_probe_never_prints_ports_or_credentials(self) -> None:
        import io
        from contextlib import redirect_stdout
        from unittest.mock import MagicMock

        port_map = ["127.0.0.1:49123", "127.0.0.1:49124"]

        def run(argv, **_kwargs):
            from subprocess import CompletedProcess

            assert "port" in argv and "ps" not in argv
            return CompletedProcess(argv, 0, port_map.pop(0), "")

        connection = MagicMock()
        connection.__enter__.return_value = connection
        connection.recv.return_value = b"HTTP/1.1 200 OK\r\nX-Token: secret"
        with (
            patch.object(broker, "compose_args", side_effect=lambda *a: ["docker", *a]),
            patch.object(broker.subprocess, "run", side_effect=run),
            patch.object(broker.socket, "create_connection", return_value=connection),
            patch.object(broker.socket, "socket", return_value=connection),
            patch.object(broker.Path, "is_socket", return_value=True),
            patch.object(broker.Path, "is_symlink", return_value=False),
            patch.object(broker, "gateway_root", return_value=Path("/tmp/private")),
            redirect_stdout(io.StringIO()) as output,
        ):
            broker._host_readiness_snapshot("a" * 32, {"PATH": "/usr/bin"})
        captured = output.getvalue()
        self.assertIn("host.loopback_vnc=http_200", captured)
        self.assertIn("host.private_model=http_200", captured)
        for disallowed in ("49123", "49124", "secret", "a" * 32, "/tmp/private"):
            self.assertNotIn(disallowed, captured)

    def test_container_diagnostics_include_stopped_containers(self) -> None:
        source = (ROOT / "auth-poc/host_broker.py").read_text(encoding="utf-8")
        self.assertIn('compose_args(workspace_id, "ps", "--all", "-q", service)', source)

    def test_diagnostics_are_backgrounded_and_deduplicated(self) -> None:
        spec = importlib.util.spec_from_file_location(
            "sigma_broker_async_diagnostics_test", ROOT / "auth-poc/host_broker.py"
        )
        assert spec and spec.loader
        broker = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(broker)

        class DeferredThread:
            def __init__(self, *, target, args, kwargs, name, daemon):
                self.target = target
                self.args = args
                self.kwargs = kwargs
                self.daemon = daemon
                self.started = False

            def is_alive(self):
                return self.started

            def start(self):
                self.started = True

        created = []

        def factory(**kwargs):
            task = DeferredThread(**kwargs)
            created.append(task)
            return task

        with (
            patch.object(broker, "local_poc", return_value=True),
            patch.object(broker.threading, "Thread", side_effect=factory),
            patch.object(broker, "_container_diagnostics"),
        ):
            broker._schedule_diagnostics("a" * 32, "readiness_unavailable")
            broker._schedule_diagnostics("a" * 32, "readiness_unavailable", force=True)
            self.assertEqual(len(created), 1)
            self.assertTrue(created[0].daemon)
            self.assertTrue(created[0].started)
            self.assertEqual(created[0].args, ("a" * 32, "readiness_unavailable"))

    def test_docker_error_diagnostics_are_sanitized_and_actionable(self) -> None:
        self.assertEqual(
            broker._diagnostic_failure_class("Bind failed: port is already allocated"),
            "port_conflict",
        )
        self.assertEqual(
            broker._diagnostic_failure_class(
                "Failed to move to new namespace: Operation not permitted"
            ),
            "chromium_sandbox",
        )
        self.assertEqual(
            broker._diagnostic_failure_class("OAuth token SECRET auth.openai.com?code=SECRET"),
            "unclassified",
        )
        self.assertEqual(
            self.module._docker_failure_class("no matching manifest for linux/arm64"),
            "image_platform_mismatch",
        )

    def test_browser_health_requires_real_gui_not_only_http(self) -> None:
        spec = importlib.util.spec_from_file_location(
            "sigma_browser_health_test", ROOT / "auth-poc/diag_probe.py"
        )
        assert spec and spec.loader
        diagnostic = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(diagnostic)
        ready = [
            "component=browser",
            "x11_socket=present",
            "vnc_tcp_5900=listening",
            "websocket_http_6080=http_200",
            "chromium_processes=5",
            "xvfb_processes=1",
            "x11vnc_processes=1",
            "websockify_processes=0",
        ]
        with patch.object(diagnostic, "report", return_value=ready):
            self.assertTrue(diagnostic.browser_healthy())
        with patch.object(
            diagnostic,
            "report",
            return_value=[
                "chromium_processes=0" if line.startswith("chromium_processes=") else line
                for line in ready
            ],
        ):
            self.assertFalse(diagnostic.browser_healthy())

    def test_only_same_origin_can_embed_private_view(self) -> None:
        proxy = (ROOT / "src/sigma/personal_browser_proxy.py").read_text(encoding="utf-8")
        self.assertIn("frame-ancestors 'self'", proxy)
        self.assertNotIn("frame-ancestors *", proxy)


if __name__ == "__main__":
    unittest.main()
