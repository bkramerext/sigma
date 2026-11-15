"""No-Docker checks for the opt-in local SIGMA pill/container broker path.

Runtime Docker Desktop acceptance is separate. These tests guard against
accidentally applying local bind-mount UID overrides to hosted users.
"""

from __future__ import annotations

import importlib.util
import os
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

            def start_broker(*args, **kwargs):
                nonlocal active_socket
                env = kwargs["env"]
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
        self.assertIn('"SIGMA_LOCAL_HOSTED_NOTICE_PREVIEW"] = (', ui)
        self.assertIn('"SIGMA_AUTH_POC_RPC_SEED",', ui)

    def test_only_same_origin_can_embed_private_view(self) -> None:
        proxy = (ROOT / "src/sigma/personal_browser_proxy.py").read_text(encoding="utf-8")
        self.assertIn("frame-ancestors 'self'", proxy)
        self.assertNotIn("frame-ancestors *", proxy)


if __name__ == "__main__":
    unittest.main()
