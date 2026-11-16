"""No-Docker contract tests for SIGMA's greenfield shared Personal worker.

The separate Docker CI workflow exercises real Chromium, OAuth helper routes,
encrypted vaults, and the two-user boundary. No per-user Docker compatibility.
"""

from __future__ import annotations

import ast
import asyncio
import importlib.util
import os
import shutil
import socket
import stat
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from subprocess import CompletedProcess
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx

ROOT = Path(__file__).resolve().parents[1]


def load(path: str, name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class SharedBrokerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.broker = load("auth-poc/shared_broker.py", "test_shared_broker")

    def test_one_shared_docker_project_no_user_containers(self) -> None:
        broker = self.broker
        with (
            patch.dict(
                os.environ,
                {
                    "SIGMA_AUTH_POC_CHECKOUT_ID": "c" * 32,
                    "SIGMA_RELEASE": "d" * 40,
                },
            ),
            patch.object(
                broker.subprocess, "run", return_value=CompletedProcess([], 0, "", "")
            ) as run,
        ):
            broker._compose("ps", "-q", "personal")
            argv = run.call_args.args[0]
            self.assertEqual(
                argv[:4], ["docker", "compose", "--project-name", "sigma-shared-" + "c" * 32]
            )
            self.assertEqual(argv[4:6], ["-f", "deploy/personal-shared.compose.yaml"])
            self.assertNotIn("sigma-personal-", " ".join(argv))
            self.assertEqual(argv[-3:], ["ps", "-q", "personal"])

    def test_docker_failure_diagnostics_do_not_leak_stderr(self) -> None:
        broker = self.broker
        secret = "/Users/private/oauth-token-secret"
        with (
            patch.dict(os.environ, {"SIGMA_AUTH_POC_CHECKOUT_ID": "c" * 32}),
            patch.object(
                broker.subprocess,
                "run",
                return_value=CompletedProcess([], 1, "", "Error: permission denied at " + secret),
            ),
            self.assertRaises(broker.SharedDockerUnavailable) as context,
        ):
            broker._compose("up", "-d", "--no-build", "--wait")
        self.assertEqual(context.exception.stage, "docker_up")
        self.assertEqual(context.exception.failure_class, "permission_denied")
        self.assertNotIn(secret, str(context.exception))

    def test_unexpected_compose_port_binding_fails_closed(self) -> None:
        broker = self.broker
        with (
            patch.object(broker, "_compose", return_value="0.0.0.0:32768"),
            self.assertRaises(broker.SharedDockerUnavailable) as context,
        ):
            broker._port(8001)
        self.assertEqual(context.exception.failure_class, "invalid_loopback_binding")

    def test_private_browser_503_preserves_only_safe_broker_codes(self) -> None:
        from sigma import personal_browser

        for exposed in (True, False):
            result = (
                {"stage": "docker_up", "failure_class": "container_unhealthy"}
                if exposed
                else {"stage": "/tmp/private/session", "failure_class": "Bearer secret"}
            )
            transport = httpx.MockTransport(lambda _, payload=result: httpx.Response(503, json=payload))
            with (
                patch.object(personal_browser, "_principal", return_value=object()),
                patch.object(personal_browser, "_socket", return_value="/tmp/unused.sock"),
                patch.object(
                    personal_browser, "_workspace_id", new_callable=AsyncMock, return_value="a" * 32
                ),
                patch.object(personal_browser.httpx, "AsyncHTTPTransport", return_value=transport),
                self.assertRaises(personal_browser.PersonalBrowserUnavailable) as context,
            ):
                asyncio.run(personal_browser.session(None, "start"))
            if exposed:
                self.assertIn("docker_up (container_unhealthy)", str(context.exception))
            else:
                self.assertNotIn("Bearer secret", str(context.exception))
                self.assertNotIn("/tmp/private/session", str(context.exception))

    def test_relay_revocation_closes_already_connected_vnc_clients(self) -> None:
        broker = self.broker
        with tempfile.TemporaryDirectory() as temp:
            listener = Path(temp) / "vnc.sock"
            server = broker.RelayServer(str(listener), broker.RelayHandler)
            server.configure(workspace="a" * 32, name="vnc.sock", port=6080)
            left, right = socket.socketpair()
            try:
                vars(broker)["_ACTIVE"] = "a" * 32
                self.assertTrue(server.authorized())
                with server.clients_lock:
                    server.clients.add(left)
                # A's old noVNC stream cannot survive when B begins login.
                vars(broker)["_ACTIVE"] = "b" * 32
                self.assertFalse(server.authorized())
                server.revoke()
                right.settimeout(1)
                self.assertEqual(right.recv(1), b"")
                self.assertTrue(server.closed)
            finally:
                left.close()
                right.close()
                server.server_close()
                vars(broker)["_ACTIVE"] = None

    def test_compose_restarts_stopped_shared_worker_without_new_user_container(self) -> None:
        broker = self.broker
        calls: list[tuple[str, ...]] = []

        def compose(*parts: str) -> str:
            calls.append(parts)
            if parts[:3] == ("ps", "--status", "running"):
                return ""
            return ""

        with patch.object(broker, "_compose", side_effect=compose):
            broker._ensure_shared()
        self.assertEqual(calls[0], ("ps", "--status", "running", "-q", "personal"))
        self.assertEqual(calls[1], ("up", "-d", "--no-build", "--wait"))

    def test_foreign_user_cannot_interrupt_active_signin(self) -> None:
        broker = self.broker
        previous = broker._ACTIVE
        vars(broker)["_ACTIVE"] = "a" * 32
        try:
            with (
                patch.object(broker, "_ensure_shared"),
                patch.object(broker, "_port", return_value=8001),
                patch.object(broker, "_relay") as relay,
                patch.object(broker, "_rpc", return_value={"status": "ready"}) as rpc,
            ):
                result = broker.operate("start", "b" * 32)
            self.assertEqual(result["status"], "unavailable")
            self.assertEqual(broker._ACTIVE, "a" * 32)
            rpc.assert_called_once_with("a" * 32, "status")
            self.assertEqual(relay.call_args.args[1], "model.sock")
        finally:
            vars(broker)["_ACTIVE"] = previous

    def test_new_login_retires_stale_other_user_relay_before_launch(self) -> None:
        broker = self.broker
        previous = broker._ACTIVE
        vars(broker)["_ACTIVE"] = "a" * 32
        events: list[tuple[str, str, str]] = []

        def rpc(workspace: str, operation: str) -> dict[str, str]:
            events.append(("rpc", workspace, operation))
            return {"status": "stopped" if operation == "status" else "ready"}

        def relay(workspace: str, channel: str, _port: int) -> None:
            events.append(("relay", workspace, channel))

        def unrelay(workspace: str, channel: str) -> None:
            events.append(("unrelay", workspace, channel))

        broker._GATEWAYS["a" * 32] = {}
        try:
            with (
                patch.object(broker, "_ensure_shared"),
                patch.object(broker, "_port", return_value=6080),
                patch.object(broker, "_rpc", side_effect=rpc),
                patch.object(broker, "_relay", side_effect=relay),
                patch.object(broker, "_unrelay", side_effect=unrelay),
            ):
                result = broker.operate("start", "b" * 32)
            self.assertEqual(result["status"], "ready")
            self.assertEqual(broker._ACTIVE, "b" * 32)
            self.assertLess(
                events.index(("unrelay", "a" * 32, "vnc.sock")),
                events.index(("rpc", "b" * 32, "start")),
            )
        finally:
            vars(broker)["_ACTIVE"] = previous
            broker._GATEWAYS.pop("a" * 32, None)

    def test_status_restores_relay_after_private_broker_restart(self) -> None:
        broker = self.broker
        previous = broker._ACTIVE
        vars(broker)["_ACTIVE"] = None
        try:
            with (
                patch.object(broker, "_ensure_shared"),
                patch.object(broker, "_port", return_value=6080),
                patch.object(broker, "_rpc", return_value={"status": "ready"}),
                patch.object(broker, "_relay") as relay,
            ):
                state = broker.operate("status", "a" * 32)
            self.assertEqual(state["status"], "ready")
            self.assertEqual(broker._ACTIVE, "a" * 32)
            self.assertIn("vnc.sock", [call.args[1] for call in relay.call_args_list])
        finally:
            vars(broker)["_ACTIVE"] = previous

    def test_all_credential_and_browser_calls_bound_to_workspace(self) -> None:
        broker = self.broker
        with patch.dict(os.environ, {"SIGMA_AUTH_POC_RPC_SEED": "a" * 64}):
            self.assertRegex(broker._key("a" * 32), r"^[0-9a-f]{64}$")
            self.assertNotEqual(broker._key("a" * 32), broker._key("b" * 32))
        for invalid in ("../other", "A" * 32, "not-a-workspace", ""):
            with self.assertRaises(ValueError):
                broker._valid(invalid)
        self.assertEqual(broker._valid("a" * 32), "a" * 32)

    def test_idle_gateway_cache_is_bounded_without_interrupting_active_streams(self) -> None:
        broker = self.broker
        prior_gateways = broker._GATEWAYS
        prior_active = broker._ACTIVE

        class FakeRelay:
            def __init__(self, index: int) -> None:
                self.clients_lock = threading.Lock()
                self.clients = {object()} if index == 2 else set()
                self.last_used = float(index)

        workspaces = [f"{i:032x}" for i in range(40)]
        vars(broker)["_GATEWAYS"] = {
            workspace: {"model.sock": (Path("/unused"), FakeRelay(i), None)}
            for i, workspace in enumerate(workspaces)
        }
        vars(broker)["_ACTIVE"] = workspaces[0]
        try:

            def unrelay(workspace: str, channel: str) -> None:
                broker._GATEWAYS[workspace].pop(channel)

            with patch.object(broker, "_unrelay", side_effect=unrelay):
                broker._prune_idle_gateways(preserve=workspaces[1])
            self.assertEqual(len(broker._GATEWAYS), broker.MAX_IDLE_GATEWAYS)
            self.assertIn(workspaces[0], broker._GATEWAYS)  # Browser owner
            self.assertIn(workspaces[1], broker._GATEWAYS)  # Caller
            self.assertIn(workspaces[2], broker._GATEWAYS)  # In-flight RPC
            self.assertNotIn(workspaces[3], broker._GATEWAYS)  # Oldest idle
        finally:
            vars(broker)["_GATEWAYS"] = prior_gateways
            vars(broker)["_ACTIVE"] = prior_active

    def test_broker_denies_unknown_peer_credential_protocols(self) -> None:
        broker = self.broker
        fake = SimpleNamespace(connection=SimpleNamespace())
        with (
            patch.object(broker, "socket", SimpleNamespace()),
            patch.dict(os.environ, {"SIGMA_AUTH_BROKER_CLIENT_UID": "1001"}),
        ):
            self.assertFalse(broker.Handler._authorized(fake))
            fake.connection = SimpleNamespace(getpeereid=lambda: (1002, 1001))
            self.assertFalse(broker.Handler._authorized(fake))
            fake.connection = SimpleNamespace(getpeereid=lambda: (1001, 1002))
            self.assertTrue(broker.Handler._authorized(fake))

    def test_workspace_only_owns_private_relay_directory(self) -> None:
        broker = self.broker
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            root.chmod(0o700)
            with patch.dict(os.environ, {"SIGMA_AUTH_BROKER_GATEWAY_ROOT": str(root)}):
                first = broker._gateway_dir("a" * 32)
                second = broker._gateway_dir("b" * 32)
                self.assertNotEqual(first, second)
                self.assertEqual(stat.S_IMODE(first.stat().st_mode), 0o700)
                self.assertEqual(first.stat().st_uid, os.geteuid())
                first.chmod(0o777)
                with self.assertRaises(RuntimeError):
                    broker._gateway_dir("a" * 32)


class SharedLocalLifecycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.mod = load("src/sigma/local_personal.py", "test_shared_local_personal")

    def test_single_native_image_and_no_per_user_compose(self) -> None:
        mod = self.mod
        self.assertEqual(mod.COMPOSE_FILES, ("deploy/personal-shared.compose.yaml",))
        observed = []

        def command(argv, *, env, timeout=90):
            observed.append((argv, dict(env)))
            if argv[:2] == ["git", "rev-parse"]:
                return "b" * 40
            if argv[:2] == ["docker", "info"]:
                return "aarch64"
            if argv[:3] == ["docker", "image", "inspect"]:
                return "linux/arm64"
            return ""

        with patch.object(mod, "_command", side_effect=command):
            env = {"SIGMA_AUTH_POC_RPC_SEED": "secret"}
            release, platform = mod._release_images(env)
            self.assertEqual(release, "b" * 40)
            self.assertEqual(platform, "linux/arm64")
            self.assertEqual(env["SIGMA_SHARED_PLATFORM"], "linux/arm64")
            self.assertFalse(any("sigma-auth-browser-poc" in str(argv) for argv, _ in observed))

    def test_docker_shutdown_keeps_encrypted_volumes(self) -> None:
        mod = self.mod
        with patch.object(mod, "_command") as command:
            mod._down_shared(
                {
                    "SIGMA_AUTH_POC_CHECKOUT_ID": "c" * 32,
                    "SIGMA_AUTH_POC_RPC_SEED": "a" * 64,
                }
            )
            argv = command.call_args.args[0]
            self.assertEqual(argv[-2:], ["down", "--remove-orphans"])
            self.assertNotIn("-v", argv)
            self.assertNotIn("--volumes", argv)
            self.assertIn("sigma-shared-" + "c" * 32, argv)

    def test_local_start_uses_private_broker_and_fresh_shared_state(self) -> None:
        mod = self.mod
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp) / "home"
            home.mkdir()
            runtime = Path(temp) / "runtime"
            runtime.mkdir()
            listener = None

            class Process:
                dead = False

                def poll(self):
                    return 0 if self.dead else None

                def terminate(self):
                    self.dead = True

                def wait(self, timeout=None):
                    return 0

            active, prep = Process(), Process()
            prep.dead = True

            def process(argv, **kwargs):
                nonlocal listener
                if "--prepare" in argv:
                    self.assertNotIn("SIGMA_AUTH_POC_RPC_SEED", kwargs["env"])
                    return prep
                self.assertTrue(argv[-1].endswith("shared_broker.py"))
                env = kwargs["env"]
                self.assertEqual(env["SIGMA_PERSONAL_SHARED_MODE"], "1")
                self.assertRegex(env["SIGMA_AUTH_POC_RPC_SEED"], r"^[0-9a-f]{64}$")
                listener = socket.socket(socket.AF_UNIX)
                listener.bind(env["SIGMA_AUTH_BROKER_SOCKET"])
                os.chmod(env["SIGMA_AUTH_BROKER_SOCKET"], 0o600)
                listener.listen()
                return active

            with (
                patch.object(mod, "_docker_environment", return_value={"PATH": "/usr/bin"}),
                patch.object(mod, "_release_images", return_value=("a" * 40, "linux/arm64")),
                patch.object(mod.Path, "home", return_value=home),
                patch.object(mod.tempfile, "mkdtemp", return_value=str(runtime)),
                patch.object(mod.subprocess, "Popen", side_effect=process),
                patch.object(mod, "_down_shared") as down,
            ):
                running = mod.LocalPersonalRuntime.start()
                self.assertEqual(running.state_root.name, "personal-shared-poc")
                self.assertEqual(stat.S_IMODE((runtime / "broker").stat().st_mode), 0o711)
                running.close()
                down.assert_called_once()
                self.assertFalse(runtime.exists())
                self.assertTrue(running.state_root.is_dir())
                self.assertTrue(active.dead)
            if listener is not None:
                listener.close()

    def test_all_request_paths_use_one_personal_model_boundary(self) -> None:
        browser = (ROOT / "src/sigma/personal_browser.py").read_text()
        inference = (ROOT / "src/sigma/personal_inference.py").read_text()
        self.assertIn('headers["X-Sigma-Workspace"] = workspace_id', inference)
        self.assertIn("def _shared_rpc_headers(", browser)
        self.assertIn('personal_browser.session(principal, action="status")', inference)
        self.assertNotIn("_owned_workspaces", (ROOT / "src/sigma/local_personal.py").read_text())

    def test_pill_and_dialog_remain_protected_and_close_reclaims_browser(self) -> None:
        source = (ROOT / "frontend/src/ai-connection.tsx").read_text()
        self.assertIn("async function startContainerPersonalBrowser()", source)
        self.assertIn("const stop = stopContainerPersonalBrowser()", source)
        self.assertIn("createPortal(", source)
        self.assertIn("personal-chatgpt-browser-frame", source)
        self.assertIn("if (result.disconnected !== true)", source)
        self.assertIn("setDisconnectError", source)

    def test_mac_socket_path_remains_short(self) -> None:
        mod = self.mod
        with patch.dict(os.environ, {"TMPDIR": "/private/var/folders/" + "x" * 100}):
            p = mod._local_runtime_directory()
            try:
                path = p / "gateways" / ("a" * 32) / "model.sock"
                self.assertLess(len(os.fsencode(path)), 104)
            finally:
                shutil.rmtree(p)


class PersonalModelDispatchAuditTests(unittest.TestCase):
    """All SIGMA generation paths honor the same Personal worker boundary."""

    def test_no_unreviewed_direct_responses_api_call_sites(self) -> None:
        # This is a closed inventory, not a whitelist of features to forget:
        # adding any new direct Responses caller requires transport review.
        expected = {
            "agentic.py": {"_invoke"},
            "chat.py": {"respond"},
            "papers.py": {"_provider", "_provider_structured"},
            "proposals.py": {"generate_proposal"},
            "research_sessions.py": {"_call_provider", "_ensure_reference_compilation"},
            "text_conversion.py": {"_convert_text"},
        }
        observed: dict[str, set[str]] = {}
        bypasses: list[str] = []
        for path in (ROOT / "src/sigma").rglob("*.py"):
            source = path.read_text(encoding="utf-8")
            if (
                "https://api.openai.com/v1/responses" not in source
                and 'provider_endpoint("responses")' not in source
            ):
                continue
            functions: set[str] = set()
            for node in ast.walk(ast.parse(source, filename=str(path))):
                if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                body = ast.get_source_segment(source, node) or ""
                if (
                    "https://api.openai.com/v1/responses" not in body
                    and 'provider_endpoint("responses")' not in body
                ):
                    continue
                if "model_dispatch.private_response_if_selected(" not in body:
                    bypasses.append(f"{path.name}:{node.name}")
                functions.add(node.name)
            observed[path.name] = functions
        self.assertFalse(bypasses, f"Unreviewed provider call sites: {bypasses}")
        self.assertEqual(observed, expected)

        # Q/A, ELI5 and the section/proofreading generators must reuse the
        # audited paper adapter, never create their own direct HTTP path.
        for filename in ("research_qa.py", "paper_eli5.py"):
            source = (ROOT / "src/sigma" / filename).read_text(encoding="utf-8")
            self.assertIn("papers._provider_structured(", source)


if __name__ == "__main__":
    unittest.main()
