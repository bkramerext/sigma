"""Provider-free tests for Personal companion pairing, isolation and dispatch."""

import os
import time
from unittest import TestCase, main
from unittest.mock import patch

from sigma import personal_companion_bridge as bridge
from sigma.projects import ProjectError


class CompanionBridgeTests(TestCase):
    def setUp(self):
        bridge.clear_for_tests()
        patcher = patch.dict(os.environ, {"SIGMA_PERSONAL_COMPANION_ENABLED": "true"})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(bridge.clear_for_tests)

    def test_pairing_and_no_cross_user_dispatch(self):
        code_a = bridge.start_pairing("google-A")["code"]
        token_a = bridge.redeem(code_a)
        with self.assertRaises(ProjectError):
            bridge.redeem(code_a)
        bridge.heartbeat(token_a, ready=True, label="Chosen A")
        self.assertTrue(bridge.status("google-A")["ready"])
        self.assertFalse(bridge.status("google-B")["ready"])
        with self.assertRaises(ProjectError):
            bridge.submit("google-B", "Should not dispatch")
        job_id = bridge.submit("google-A", "Test the companion")
        delivered = bridge.next_job(token_a)
        self.assertEqual(delivered, {"job_id": job_id, "prompt": "Test the companion"})
        self.assertIsNone(bridge.next_job(token_a))
        with self.assertRaises(ProjectError):
            bridge.result("google-B", job_id)
        code_b = bridge.start_pairing("google-B")["code"]
        token_b = bridge.redeem(code_b)
        bridge.heartbeat(token_b, ready=True, label="Chosen B")
        with self.assertRaises(ProjectError):
            bridge.complete(token_b, job_id, result="stolen", model="gpt-6-luna")
        bridge.complete(token_a, job_id, result="real companion answer", model="gpt-6-luna")
        self.assertEqual(bridge.result("google-A", job_id)["status"], "completed")
        with self.assertRaises(ProjectError):
            bridge.complete(token_a, job_id, result="replay", model="gpt-6-luna")

    def test_repair_revokes_old_worker_and_leaves_dispatched_job_unknown(self):
        old = bridge.redeem(bridge.start_pairing("a")["code"])
        bridge.heartbeat(old, ready=True, label="A")
        job_id = bridge.submit("a", "First attempt")
        bridge.next_job(old)
        new = bridge.redeem(bridge.start_pairing("a")["code"])
        with self.assertRaises(ProjectError):
            bridge.heartbeat(old, ready=True, label="old")
        bridge.heartbeat(new, ready=True, label="new")
        self.assertIsNone(bridge.next_job(new))
        self.assertEqual(bridge.result("a", job_id)["status"], "dispatched")
        bridge.disconnect(new)
        self.assertFalse(bridge.status("a")["ready"])

    def test_expired_code_and_disabled_flag(self):
        code = bridge.start_pairing("a")["code"]
        with patch.object(bridge.time, "monotonic", return_value=time.monotonic() + 500):
            with self.assertRaises(ProjectError):
                bridge.redeem(code)
        with patch.dict(os.environ, {"SIGMA_PERSONAL_COMPANION_ENABLED": "false"}):
            with self.assertRaises(ProjectError):
                bridge.start_pairing("a")


if __name__ == "__main__":
    main()
