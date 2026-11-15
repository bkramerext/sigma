"""No-Docker checks for the opt-in local SIGMA pill/container broker path.

Runtime Docker Desktop acceptance is separate. These tests guard against
accidentally applying local bind-mount UID overrides to hosted users.
"""

from __future__ import annotations

import importlib.util
import os
import stat
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


if __name__ == "__main__":
    unittest.main()
