"""Hosted Demo boundary: public reads are fixed, deterministic and non-mutating."""

from __future__ import annotations

import hashlib
import os
import secrets
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from fastapi.testclient import TestClient

from sigma import cloud_auth
from sigma.api import app


class CloudDemoTests(TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory(prefix="sigma-cloud-demo-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "auth").mkdir(mode=0o700)
        repo = Path(__file__).resolve().parents[1]
        self.snapshot = repo / "cloud-demo/handshake-demo-audit.json"
        self.env = patch.dict(
            os.environ,
            {
                "SIGMA_CLOUD_AUTH_ENABLED": "true",
                "GOOGLE_OIDC_CLIENT_ID": "sigma-test.apps.googleusercontent.com",
                "GOOGLE_OIDC_CLIENT_SECRET": "fixture-secret",
                "SIGMA_CLOUD_PUBLIC_ORIGIN": "https://sigma.test",
                "SIGMA_CLOUD_BOOTSTRAP_ADMIN_EMAIL": "admin@example.org",
                "SIGMA_CLOUD_ADMIN_CONTACT_EMAIL": "access@example.org",
                "SIGMA_CLOUD_AUTH_HOME": str(self.root / "auth"),
                "SIGMA_CLOUD_DEMO_AUDIT": str(self.snapshot),
            },
        )
        self.env.start()
        self.addCleanup(self.env.stop)
        self.client = TestClient(app)
        self.addCleanup(self.client.close)
        from sigma import proposals, python_sandbox, research_sessions

        for target, name in (
            (proposals, "generate_proposal"),
            (python_sandbox, "execute_research_code"),
            (research_sessions, "start_session"),
        ):
            blocker = patch.object(
                target, name, side_effect=AssertionError("guest path invoked execution")
            )
            blocker.start()
            self.addCleanup(blocker.stop)

    def test_anonymous_demo_browsing_exports_and_guessed_project_inputs_are_fixed(self):
        before = hashlib.sha256(self.snapshot.read_bytes()).digest()
        audit = self.client.get("/api/cloud-demo/")
        self.assertEqual(audit.status_code, 200)
        value = audit.json()
        self.assertEqual(value["project"]["title"], "Counting Pairwise Handshakes")
        self.assertEqual(len(value["project"]["strategies"]), 2)
        self.assertEqual(len(value["research_sessions"]), 1)
        self.assertTrue(value["research_sessions"][0]["artifacts"])
        self.assertEqual(
            value["research_sessions"][0]["artifacts"][0]["computational_evidence"]["files"][0][
                "filename"
            ],
            "handshake-counts.csv",
        )
        self.assertTrue(value["agentic_runs"])
        guessed = self.client.get(
            "/api/cloud-demo/", params={"path": "/etc/passwd", "project_id": "private"}
        )
        self.assertEqual(guessed.json(), value)
        self.assertEqual(
            self.client.get("/api/projects/export", params={"path": "/etc/passwd"}).status_code, 401
        )
        self.assertEqual(
            self.client.get("/api/projects/inspect", params={"path": str(self.root)}).status_code,
            401,
        )
        self.assertEqual(
            self.client.get(
                "/api/projects/research-sessions", params={"path": str(self.root)}
            ).status_code,
            401,
        )
        for format_name in ("txt", "html", "tex"):
            report = self.client.get("/api/cloud-demo/report", params={"format": format_name})
            self.assertEqual(report.status_code, 200)
            self.assertTrue(report.content)
            self.assertEqual(
                report.content,
                self.client.get("/api/cloud-demo/report", params={"format": format_name}).content,
            )
            guessed_report = self.client.get(
                "/api/cloud-demo/report",
                params={"format": format_name, "path": "/etc/passwd", "project_id": "private"},
            )
            self.assertEqual(guessed_report.content, report.content)
        self.assertEqual(
            self.client.post(
                "/api/projects/strategies/add",
                json={"path": str(self.root)},
                headers={"Origin": "https://sigma.test"},
            ).status_code,
            401,
        )
        self.assertEqual(
            self.client.post(
                "/api/cloud-demo/", json={}, headers={"Origin": "https://sigma.test"}
            ).status_code,
            401,
        )
        denied_cookie = secrets.token_urlsafe(32)
        with cloud_auth._db(cloud_auth.config()) as db:
            db.execute(
                "INSERT INTO denied_access(token_hash,email,expires_at) VALUES(?,?,?)",
                (cloud_auth._hash(denied_cookie), "visitor@example.org", int(time.time()) + 300),
            )
        self.client.cookies.set(cloud_auth.DENIED_COOKIE, denied_cookie)
        self.assertEqual(self.client.get("/api/cloud-demo/").status_code, 200)
        self.assertEqual(
            self.client.get("/api/projects/export", params={"path": str(self.root)}).status_code,
            401,
        )
        self.assertEqual(hashlib.sha256(self.snapshot.read_bytes()).digest(), before)
        self.assertFalse(any(self.root.rglob("*.sigma")))

    def test_demo_configuration_fails_closed_and_local_mode_is_unchanged(self):
        with patch.dict(os.environ, {"SIGMA_CLOUD_DEMO_AUDIT": ""}):
            unavailable = self.client.get("/api/cloud-demo/")
            self.assertEqual(unavailable.status_code, 503)
        with patch.dict(os.environ, {"SIGMA_CLOUD_AUTH_ENABLED": "false"}):
            self.assertEqual(self.client.get("/api/cloud-demo/").status_code, 404)
            # Existing local project API remains unrestricted by hosted Demo rules.
            local = self.client.get(
                "/api/projects/inspect", params={"path": str(self.snapshot.parent / "local.sigma")}
            )
            self.assertNotEqual(local.status_code, 401)


if __name__ == "__main__":
    import unittest

    unittest.main()
