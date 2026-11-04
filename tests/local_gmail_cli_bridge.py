"""Local CLI Gmail callback handoff through an already-running SIGMA backend."""

from __future__ import annotations

import os
import secrets
from unittest.mock import patch

from cloud_auth_fixture import CloudAuthFixture

from sigma.local_gmail_cli_bridge import pending_flow, ready, receive, result


class LocalGmailCliBridgeTests(CloudAuthFixture):
    def test_existing_local_server_receives_cli_google_code_without_signin(self):
        state = secrets.token_urlsafe(32)
        with (
            patch.dict(
                os.environ,
                {
                    "SIGMA_CLOUD_AUTH_LOCAL": "true",
                    "SIGMA_CLOUD_PUBLIC_ORIGIN": "http://127.0.0.1:5173",
                },
            ),
            pending_flow(self.root, state),
        ):
            probe = self.client.get(
                "/api/cloud-auth/mail/cli-bridge-ready", params={"state": state}
            )
            self.assertEqual(probe.status_code, 200, probe.text)
            self.assertEqual(probe.json(), {"ready": True, "protocol": 1})
            callback = self.client.get(
                "/api/cloud-auth/callback",
                params={"state": state, "code": "google-auth-code"},
                follow_redirects=False,
            )
            self.assertEqual(callback.status_code, 200, callback.text)
            self.assertIn("Return to your terminal", callback.text)
            self.assertEqual(callback.headers["cache-control"], "no-store")
            self.assertNotIn("google-auth-code", callback.text)
            self.assertNotIn("set-cookie", callback.headers)
            self.assertEqual(result(self.root, state), ("google-auth-code", False))
            self.assertFalse(ready(self.root, state))
            duplicate = self.client.get(
                "/api/cloud-auth/callback",
                params={"state": state, "code": "different-code"},
            )
            self.assertEqual(duplicate.status_code, 400)
            self.assertEqual(result(self.root, state), ("google-auth-code", False))

    def test_google_decline_does_not_create_authorization(self):
        state = secrets.token_urlsafe(32)
        with (
            patch.dict(
                os.environ,
                {
                    "SIGMA_CLOUD_AUTH_LOCAL": "true",
                    "SIGMA_CLOUD_PUBLIC_ORIGIN": "http://127.0.0.1:5173",
                },
            ),
            pending_flow(self.root, state),
        ):
            response = self.client.get(
                "/api/cloud-auth/callback",
                params={"state": state, "error": "access_denied"},
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(result(self.root, state), ("", True))

    def test_hosted_mode_never_exposes_cli_handoff(self):
        state = secrets.token_urlsafe(32)
        with pending_flow(self.root, state):
            probe = self.client.get(
                "/api/cloud-auth/mail/cli-bridge-ready", params={"state": state}
            )
            self.assertEqual(probe.status_code, 404)
            callback = self.client.get(
                "/api/cloud-auth/callback",
                params={"state": state, "code": "google-code"},
            )
            self.assertEqual(callback.status_code, 400)
            self.assertIsNone(result(self.root, state))

    def test_unknown_state_never_touches_pending_flow(self):
        state = secrets.token_urlsafe(32)
        with (
            patch.dict(
                os.environ,
                {
                    "SIGMA_CLOUD_AUTH_LOCAL": "true",
                    "SIGMA_CLOUD_PUBLIC_ORIGIN": "http://127.0.0.1:5173",
                },
            ),
            pending_flow(self.root, state),
        ):
            other = secrets.token_urlsafe(32)
            self.assertFalse(receive(self.root, other, code="injected", error=""))
            self.assertIsNone(result(self.root, state))
            probe = self.client.get(
                "/api/cloud-auth/mail/cli-bridge-ready", params={"state": other}
            )
            self.assertEqual(probe.json(), {"ready": False, "protocol": 1})


if __name__ == "__main__":
    import unittest

    unittest.main()
