"""Deterministic tests for opt-in hosted Google authentication."""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, main
from unittest.mock import AsyncMock, patch
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

import httpx
import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from jwt.algorithms import RSAAlgorithm

from sigma import cloud_auth, sponsor_diagnostics
from sigma.api import app
from sigma.projects import initialize_project

KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
CLIENT_ID = "sigma-test.apps.googleusercontent.com"
ORIGIN = "https://sigma.test"


JWK = RSAAlgorithm.to_jwk(KEY.public_key(), as_dict=True) | {
    "kid": "fixture-key",
    "alg": "RS256",
    "use": "sig",
}


class GoogleClient:
    token = ""

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def post(self, url, data):
        assert url == "https://oauth2.googleapis.com/token"
        assert data["code_verifier"]
        return httpx.Response(
            200, request=httpx.Request("POST", url), json={"id_token": self.token}
        )

    async def get(self, url):
        if url == cloud_auth.DISCOVERY_URL:
            return httpx.Response(
                200,
                request=httpx.Request("GET", url),
                json={
                    "issuer": "https://accounts.google.com",
                    "jwks_uri": "https://www.googleapis.com/oauth2/v3/certs",
                },
            )
        assert url == "https://www.googleapis.com/oauth2/v3/certs"
        return httpx.Response(200, request=httpx.Request("GET", url), json={"keys": [JWK]})


def token(
    *,
    nonce,
    email="admin@example.org",
    subject="google-sub-1",
    iss="https://accounts.google.com",
    aud=CLIENT_ID,
    exp=None,
    verified=True,
    azp=None,
):
    claims = {
        "iss": iss,
        "aud": aud,
        "exp": exp if exp is not None else int(time.time()) + 300,
        "iat": int(time.time()),
        "sub": subject,
        "nonce": nonce,
        "email": email,
        "email_verified": verified,
    }
    if azp:
        claims["azp"] = azp
    return jwt.encode(claims, KEY, algorithm="RS256", headers={"kid": "fixture-key"})


class CloudAuthTests(TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory(prefix="sigma-cloud-auth-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "auth"
        self.root.mkdir(mode=0o700)
        self.project_path = Path(self.temp.name) / "project"
        self.project_path.mkdir(mode=0o700)
        self.env = patch.dict(
            os.environ,
            {
                "SIGMA_CLOUD_AUTH_ENABLED": "true",
                "GOOGLE_OIDC_CLIENT_ID": CLIENT_ID,
                "GOOGLE_OIDC_CLIENT_SECRET": "fixture-secret",
                "SIGMA_CLOUD_PUBLIC_ORIGIN": ORIGIN,
                "SIGMA_CLOUD_AUTH_HOME": str(self.root),
                "SIGMA_CLOUD_ADMIN_CONTACT_EMAIL": "admin@example.org",
                "SIGMA_CLOUD_USER_SPEND_CEILING_USD": "2.00",
                "SIGMA_CLOUD_GLOBAL_SPEND_CEILING_USD": "15.00",
                "SIGMA_CLOUD_FORCE_SPONSORED_MODE": "false",
                "SIGMA_CLOUD_DEMO_AUDIT": str(
                    Path(__file__).resolve().parents[1] / "cloud-demo/handshake-demo-audit.json"
                ),
            },
        )
        self.env.start()
        self.addCleanup(self.env.stop)
        self.context = TestClient(app, base_url="http://127.0.0.1", client=("127.0.0.1", 12345))
        self.client = self.context.__enter__()
        self.addCleanup(self.context.__exit__, None, None, None)

    def test_mock_queue_recovery_never_contacts_hosted_research(self):
        import asyncio

        from sigma import cloud_research, cloud_workspaces, research_sessions

        with (
            patch.object(cloud_workspaces, "enabled", return_value=True),
            patch.object(
                research_sessions,
                "_all",
                return_value=[{"id": "mock-1", "status": "queued", "simulated": True}],
            ),
            patch.object(
                cloud_research,
                "reconcile_orphaned_jobs",
                side_effect=AssertionError("Mock queue contacted hosted jobs"),
            ),
            patch.object(
                research_sessions,
                "_worker",
                side_effect=AssertionError("Mock queue dispatched a provider worker"),
            ),
        ):
            asyncio.run(research_sessions.ensure_queued_workers("/mock/private-a"))

    def test_mock_save_skips_cloud_job_sync(self):
        from sigma import cloud_research, cloud_workspaces, research_sessions

        with (
            patch.object(cloud_workspaces, "enabled", return_value=True),
            patch.object(research_sessions, "_directory", return_value=Path(self.temp.name)),
            patch.object(
                cloud_research,
                "sync_job",
                side_effect=AssertionError("Mock session synced a hosted job"),
            ),
        ):
            research_sessions._save(
                "/mock/private-a",
                {
                    "id": "11111111-1111-4111-8111-111111111111",
                    "status": "queued",
                    "simulated": True,
                },
            )

    def test_mock_session_lifecycle_is_deterministic_and_provider_free(self):
        from sigma import research_sessions

        record = {
            "id": "11111111-1111-4111-8111-111111111111",
            "project_path": "/mock/private-a",
            "project_id": "project-a",
            "strategy_id": "strategy-a",
            "strategy_title": "Test strategy",
            "strategy_runs": [
                {"strategy_id": "strategy-a", "artifacts": [], "status": "queued", "calls_used": 0}
            ],
            "status": "queued",
            "mock_stage": 0,
            "mock_scenario": "completed",
            "simulated": True,
            "artifacts": [],
            "events": [],
        }
        with (
            patch.object(research_sessions, "_save") as saved,
            patch.object(research_sessions, "_outcome", return_value={"assessment": "mixed"}),
            patch.object(
                research_sessions,
                "_worker",
                side_effect=AssertionError("No provider worker may run"),
            ),
        ):
            for expected in ("running", "running", "ended"):
                research_sessions._advance_mock(record)
                self.assertEqual(record["status"], expected)
            self.assertEqual(len(record["artifacts"]), 1)
            self.assertTrue(record["artifacts"][0]["simulated"])
            self.assertEqual(
                record["strategy_runs"][0]["artifacts"], [record["artifacts"][0]["id"]]
            )
            self.assertEqual(record["strategy_runs"][0]["calls_used"], 0)
            self.assertEqual([e["sequence"] for e in record["events"]], [1, 2, 3])
            research_sessions._advance_mock(record)
            self.assertEqual(saved.call_count, 3)
            self.assertEqual(len(record["artifacts"]), 1)

    def test_mock_session_resume_continues_simulation_without_provider_calls(self):
        from sigma import research_sessions

        session_id = "11111111-1111-4111-8111-111111111111"
        record = {
            "id": session_id,
            "project_path": "/mock/private-a",
            "project_id": "project-a",
            "strategy_id": "strategy-a",
            "strategy_title": "Test strategy",
            "strategy_runs": [
                {
                    "strategy_id": "strategy-a",
                    "status": "stopped",
                    "current_action": "Stopped",
                    "artifacts": [],
                    "calls_used": 0,
                }
            ],
            "status": "stopped",
            "mode": "mock",
            "simulated": True,
            "mock_stage": 1,
            "mock_scenario": "completed",
            "events": [],
            "artifacts": [],
        }
        with (
            patch.object(research_sessions, "_read", return_value=record),
            patch.object(research_sessions, "_all", return_value=[record]),
            patch.object(research_sessions, "_save") as save,
            patch.object(
                research_sessions, "get_limits", return_value=research_sessions.DEFAULT_LIMITS
            ),
        ):
            resumed = research_sessions.control_mock_session(
                "/mock/private-a", session_id, "resume"
            )
            assert resumed is not None
            self.assertEqual(resumed["status"], "queued")
            self.assertEqual(resumed["mock_stage"], 1)
            self.assertTrue(resumed["simulated"])
            self.assertIn("No provider was called", resumed["message"])
            self.assertEqual(resumed["events"][-1]["kind"], "simulation.resumed")
            self.assertEqual(record["strategy_runs"][0]["status"], "queued")
            save.assert_called_once()

    def test_mock_failure_scenarios_never_create_fake_evidence(self):
        from sigma import research_sessions

        for scenario in ("failed", "provider-error", "exhausted"):
            record = {
                "project_path": "/mock/private-a",
                "project_id": "project-a",
                "strategy_id": "strategy-a",
                "strategy_title": "Test strategy",
                "strategy_runs": [{"artifacts": [], "status": "queued", "calls_used": 0}],
                "status": "queued",
                "mock_stage": 2,
                "mock_scenario": scenario,
                "simulated": True,
                "artifacts": [],
                "events": [],
            }
            with (
                self.subTest(scenario=scenario),
                patch.object(research_sessions, "_save"),
                patch.object(research_sessions, "_outcome", return_value={}),
            ):
                research_sessions._advance_mock(record)
                self.assertEqual(record["status"], "failed")
                self.assertEqual(record["artifacts"], [])
                self.assertIn("No provider was called", record["message"])

    def test_local_sponsored_test_flag_selects_mock_and_rejects_personal_switch(self):
        origin = {"Origin": "http://127.0.0.1:5173"}
        with patch.dict(
            os.environ,
            {
                "SIGMA_CLOUD_AUTH_ENABLED": "true",
                "SIGMA_CLOUD_AUTH_LOCAL": "true",
                "SIGMA_MOCK_AUTH": "1",
                "SIGMA_LOCAL_SPONSORED_TEST_MODE": "1",
                "SIGMA_CLOUD_PUBLIC_ORIGIN": "http://127.0.0.1:5173",
                "SIGMA_CLOUD_AUTH_HOME": str(self.root),
            },
        ):
            status = self.client.get("/api/cloud-auth/status").json()
            self.assertTrue(status["sponsored_test_mode"])
            self.assertEqual(
                self.client.post(
                    "/api/cloud-auth/mock/select?identity=member-a", headers=origin
                ).status_code,
                204,
            )
            status = self.client.get("/api/cloud-auth/status").json()
            self.assertTrue(status["account"]["sponsorship"]["eligible"])
            self.assertEqual(status["account"]["model_access"]["mode"], "sponsored")
            denied = self.client.post(
                "/api/cloud-auth/mock/model-access?mode=personal", headers=origin
            )
            self.assertEqual(denied.status_code, 403)
            direct_provider_mode = self.client.post(
                "/api/ai/mode", json={"mode": "personal"}, headers=origin
            )
            self.assertEqual(direct_provider_mode.status_code, 403)
            self.assertEqual(
                self.client.get("/api/cloud-auth/status").json()["account"]["model_access"]["mode"],
                "sponsored",
            )
            funding = self.client.get("/api/cloud-auth/mock/funding")
            self.assertEqual(funding.status_code, 200, funding.text)
            self.assertTrue(funding.json()["allowance"]["simulated"])
            self.assertEqual(funding.json()["provider"], "connected")
            disconnected = self.client.post(
                "/api/cloud-auth/mock/provider?scenario=unavailable", headers=origin
            )
            self.assertEqual(disconnected.status_code, 200, disconnected.text)
            self.assertEqual(
                self.client.get("/api/cloud-auth/mock/funding").json()["provider"], "unavailable"
            )
            # The next launch's automatic identity selection rediscovers the sponsored state.
            self.assertEqual(
                self.client.post(
                    "/api/cloud-auth/mock/select?identity=member-a", headers=origin
                ).status_code,
                204,
            )
            funding = self.client.get("/api/cloud-auth/mock/funding").json()
            self.assertEqual(funding["mode"], "sponsored")
            self.assertEqual(funding["provider"], "connected")

    def test_mock_research_route_never_invokes_live_start(self):
        from sigma import research_sessions

        origin = {"Origin": "http://127.0.0.1:5173"}
        with patch.dict(
            os.environ,
            {
                "SIGMA_CLOUD_AUTH_ENABLED": "true",
                "SIGMA_CLOUD_AUTH_LOCAL": "true",
                "SIGMA_MOCK_AUTH": "1",
                "SIGMA_CLOUD_PUBLIC_ORIGIN": "http://127.0.0.1:5173",
                "SIGMA_CLOUD_AUTH_HOME": str(self.root),
            },
        ):
            self.assertEqual(
                self.client.post(
                    "/api/cloud-auth/mock/select",
                    params={"identity": "member-a"},
                    headers=origin,
                ).status_code,
                204,
            )
            created = self.client.post(
                "/api/projects/create",
                json={"title": "Research fixture", "problem": "Test mock research."},
                headers=origin,
            )
            self.assertEqual(created.status_code, 201, created.text)
            project = created.json()
            with (
                patch.object(
                    research_sessions,
                    "start_session",
                    side_effect=AssertionError("Real research start must never run in mock mode"),
                ),
                patch.object(
                    research_sessions,
                    "mock_session",
                    return_value={
                        "id": "mock-session",
                        "status": "queued",
                        "simulated": True,
                    },
                ) as fake,
            ):
                response = self.client.post(
                    "/api/projects/research-sessions/mock",
                    json={
                        "path": project["path"],
                        "strategy_id": "fixture-strategy",
                        "expected_project_id": project["project"]["id"],
                        "idempotency_key": "11111111-1111-4111-8111-111111111111",
                    },
                    headers=origin,
                )
                self.assertEqual(response.status_code, 200, response.text)
                self.assertTrue(response.json()["simulated"])
                fake.assert_called_once()
            with (
                patch.object(
                    research_sessions,
                    "control_mock_session",
                    return_value={"id": "mock-session", "status": "queued", "simulated": True},
                ) as mock_control,
                patch.object(
                    research_sessions,
                    "control_session",
                    side_effect=AssertionError("Mock resume must not enter provider resume checks"),
                ),
            ):
                resumed = self.client.post(
                    "/api/projects/research-sessions/mock-session/control",
                    json={"path": project["path"], "action": "resume"},
                    headers=origin,
                )
                self.assertEqual(resumed.status_code, 200, resumed.text)
                self.assertTrue(resumed.json()["simulated"])
                mock_control.assert_called_once_with(project["path"], "mock-session", "resume")
            with (
                patch.object(research_sessions, "control_mock_session", return_value=None),
                patch.object(
                    research_sessions,
                    "control_session",
                    side_effect=AssertionError("Mock identities must not resume real sessions"),
                ),
            ):
                denied_resume = self.client.post(
                    "/api/projects/research-sessions/real-session/control",
                    json={"path": project["path"], "action": "resume"},
                    headers=origin,
                )
                self.assertEqual(denied_resume.status_code, 404, denied_resume.text)
            blocked = self.client.post(
                "/api/projects/research-sessions/start",
                json={},
                headers=origin,
            )
            self.assertEqual(blocked.status_code, 403)

    def test_mock_members_cannot_read_each_others_session_records(self):
        from sigma import research_sessions

        origin = {"Origin": "http://127.0.0.1:5173"}
        with patch.dict(
            os.environ,
            {
                "SIGMA_CLOUD_AUTH_ENABLED": "true",
                "SIGMA_CLOUD_AUTH_LOCAL": "true",
                "SIGMA_MOCK_AUTH": "1",
                "SIGMA_CLOUD_PUBLIC_ORIGIN": "http://127.0.0.1:5173",
                "SIGMA_CLOUD_AUTH_HOME": str(self.root),
            },
        ):
            self.assertEqual(
                self.client.post(
                    "/api/cloud-auth/mock/select",
                    params={"identity": "member-a"},
                    headers=origin,
                ).status_code,
                204,
            )
            created = self.client.post(
                "/api/projects/create",
                json={"title": "Private mock session", "problem": "Test isolation"},
                headers=origin,
            )
            self.assertEqual(created.status_code, 201, created.text)
            path = created.json()["path"]
            session_id = "11111111-1111-4111-8111-111111111111"
            # The session file belongs to Member A's project workspace.
            with patch.object(research_sessions, "_snapshot") as snapshot:
                # A project-scoped read must resolve through the active workspace,
                # never through a supplied path belonging to another member.
                self.assertEqual(
                    self.client.get(
                        "/api/projects/research-sessions",
                        params={"path": path},
                    ).status_code,
                    200,
                )
                self.assertFalse(snapshot.called)
            self.assertEqual(
                self.client.post(
                    "/api/cloud-auth/mock/select",
                    params={"identity": "member-b"},
                    headers=origin,
                ).status_code,
                204,
            )
            for endpoint in (
                "/api/projects/research-sessions",
                f"/api/projects/research-sessions/{session_id}",
            ):
                denied = self.client.get(endpoint, params={"path": path})
                self.assertIn(denied.status_code, {400, 403, 404}, denied.text)
            artifact = self.client.get(
                "/api/projects/research-executions/11111111-1111-4111-8111-111111111111/"
                "artifacts/evidence.txt",
                params={"path": path},
            )
            self.assertIn(artifact.status_code, {400, 403, 404}, artifact.text)
            self.assertEqual(
                self.client.post(
                    "/api/cloud-auth/mock/select",
                    params={"identity": "member-a"},
                    headers=origin,
                ).status_code,
                204,
            )
            self.assertEqual(
                self.client.get(
                    "/api/projects/research-sessions",
                    params={"path": path},
                ).status_code,
                200,
            )

    def test_mock_member_projects_are_not_visible_to_other_members(self):
        origin = {"Origin": "http://127.0.0.1:5173"}
        member_a_path = ""
        with patch.dict(
            os.environ,
            {
                "SIGMA_CLOUD_AUTH_ENABLED": "true",
                "SIGMA_CLOUD_AUTH_LOCAL": "true",
                "SIGMA_MOCK_AUTH": "1",
                "SIGMA_CLOUD_PUBLIC_ORIGIN": "http://127.0.0.1:5173",
                "SIGMA_CLOUD_AUTH_HOME": str(self.root),
            },
        ):
            for identity in ("member-a", "member-b"):
                selected = self.client.post(
                    "/api/cloud-auth/mock/select",
                    params={"identity": identity},
                    headers=origin,
                )
                self.assertEqual(selected.status_code, 204)
                created = self.client.post(
                    "/api/projects/create",
                    json={
                        "title": "Mock isolation " + identity,
                        "problem": "Verify member project isolation.",
                    },
                    headers=origin,
                )
                self.assertEqual(created.status_code, 201, created.text)
                project = created.json()
                self.assertIn("path", project)
                if identity == "member-a":
                    member_a_path = project["path"]
                    self.assertEqual(
                        self.client.get(
                            "/api/projects/inspect", params={"path": member_a_path}
                        ).status_code,
                        200,
                    )
                else:
                    denied = self.client.get(
                        "/api/projects/inspect",
                        params={"path": member_a_path},
                    )
                    self.assertIn(denied.status_code, {400, 403, 404})
                    denied_open = self.client.post(
                        "/api/projects/open",
                        json={"path": member_a_path},
                        headers=origin,
                    )
                    self.assertIn(denied_open.status_code, {400, 403, 404})
            switched = self.client.post(
                "/api/cloud-auth/mock/select",
                params={"identity": "member-a"},
                headers=origin,
            )
            self.assertEqual(switched.status_code, 204)
            self.assertEqual(
                self.client.get(
                    "/api/projects/inspect", params={"path": member_a_path}
                ).status_code,
                200,
            )

    def test_mock_member_switches_bind_separate_project_workspaces(self):
        from sigma import cloud_workspaces

        with patch.dict(
            os.environ,
            {
                "SIGMA_CLOUD_AUTH_ENABLED": "true",
                "SIGMA_CLOUD_AUTH_LOCAL": "true",
                "SIGMA_MOCK_AUTH": "1",
                "SIGMA_CLOUD_PUBLIC_ORIGIN": "http://127.0.0.1:5173",
                "SIGMA_CLOUD_AUTH_HOME": str(self.root),
            },
        ):
            self.assertTrue(cloud_workspaces.enabled())
            seen = []
            for identity in ("member-a", "member-b", "member-a"):
                response = self.client.post(
                    "/api/cloud-auth/mock/select",
                    params={"identity": identity},
                    headers={"Origin": "http://127.0.0.1:5173"},
                )
                self.assertEqual(response.status_code, 204)
                status = self.client.get("/api/cloud-auth/status")
                self.assertEqual(status.status_code, 200)
                self.assertTrue(status.json()["authenticated"])
                seen.append(status.json()["account"]["workspace"]["id"])
                # The project endpoint executes through the same workspace
                # dependency used by all project operations.
                projects = self.client.get("/api/projects/recent")
                self.assertEqual(projects.status_code, 200)
            self.assertNotEqual(seen[0], seen[1])
            self.assertEqual(seen[0], seen[2])

    def test_mock_project_mutations_are_not_blanket_blocked(self):
        with patch.dict(
            os.environ,
            {
                "SIGMA_CLOUD_AUTH_ENABLED": "true",
                "SIGMA_CLOUD_AUTH_LOCAL": "true",
                "SIGMA_MOCK_AUTH": "1",
                "SIGMA_CLOUD_PUBLIC_ORIGIN": "http://127.0.0.1:5173",
                "SIGMA_CLOUD_AUTH_HOME": str(self.root),
            },
        ):
            selected = self.client.post(
                "/api/cloud-auth/mock/select?identity=member-a",
                headers={"Origin": "http://127.0.0.1:5173"},
            )
            self.assertEqual(selected.status_code, 204)
            # A normal project mutation may fail validation, but must not be
            # rejected by the mock execution guard.
            project = self.client.post(
                "/api/projects/close",
                json={"path": "/nonexistent/mock-project"},
                headers={"Origin": "http://127.0.0.1:5173"},
            )
            self.assertNotIn("research execution is disabled", project.text)
            execution = self.client.post(
                "/api/projects/research-sessions",
                json={},
                headers={"Origin": "http://127.0.0.1:5173"},
            )
            self.assertEqual(execution.status_code, 403)
            self.assertTrue(execution.json()["simulated"])
            provider = self.client.get("/api/ai/connection")
            self.assertEqual(provider.status_code, 403)

    def test_mock_members_receive_distinct_stable_workspaces(self):
        from sigma.cloud_workspaces import workspace_for_subject

        with patch.dict(
            os.environ,
            {
                "SIGMA_CLOUD_AUTH_ENABLED": "true",
                "SIGMA_CLOUD_AUTH_LOCAL": "true",
                "SIGMA_MOCK_AUTH": "1",
                "SIGMA_CLOUD_PUBLIC_ORIGIN": "http://127.0.0.1:5173",
                "SIGMA_CLOUD_AUTH_HOME": str(self.root),
            },
        ):
            cfg = cloud_auth.config()
            self.assertIsNone(cfg.error)
            first = cloud_auth._persist_user_state(
                cfg,
                cloud_auth.Principal("mock:member-a", "mock-member-a@localhost.invalid", "member"),
            )
            second = cloud_auth._persist_user_state(
                cfg,
                cloud_auth.Principal("mock:member-b", "mock-member-b@localhost.invalid", "member"),
            )
            first_again = cloud_auth._persist_user_state(
                cfg,
                cloud_auth.Principal("mock:member-a", "mock-member-a@localhost.invalid", "member"),
            )
        self.assertTrue(first["workspace"]["available"])
        self.assertTrue(second["workspace"]["available"])
        self.assertNotEqual(first["workspace"]["id"], second["workspace"]["id"])
        self.assertEqual(first["workspace"]["id"], first_again["workspace"]["id"])
        self.assertEqual(
            workspace_for_subject("mock:member-a").workspace_id,
            first["workspace"]["id"],
        )

    def test_mock_auth_requires_explicit_loopback_local_configuration(self):
        with patch.dict(
            os.environ,
            {
                "SIGMA_CLOUD_AUTH_ENABLED": "true",
                "SIGMA_CLOUD_AUTH_LOCAL": "true",
                "SIGMA_MOCK_AUTH": "1",
                "SIGMA_CLOUD_PUBLIC_ORIGIN": "http://127.0.0.1:5173",
                "SIGMA_CLOUD_AUTH_HOME": str(self.root),
                "GOOGLE_OIDC_CLIENT_ID": "",
                "GOOGLE_OIDC_CLIENT_SECRET": "",
                "SIGMA_CLOUD_ADMIN_CONTACT_EMAIL": "",
            },
        ):
            cfg = cloud_auth.config()
            self.assertIsNone(cfg.error)
            self.assertTrue(cfg.local)
            self.assertTrue(cloud_auth._mock_enabled(cfg))
            with patch.dict(os.environ, {"SIGMA_CLOUD_PUBLIC_ORIGIN": "http://127.0.0.1:5182"}):
                self.assertTrue(cloud_auth._mock_enabled(cloud_auth.config()))
            with patch.dict(os.environ, {"SIGMA_CLOUD_PUBLIC_ORIGIN": "https://sigma.example.org"}):
                self.assertFalse(cloud_auth._mock_enabled(cloud_auth.config()))
            for invalid_origin in (
                "http://example.org:5182",
                "http://127.0.0.1:5182/path",
                "https://127.0.0.1:5182",
                "http://user@127.0.0.1:5182",
            ):
                with (
                    self.subTest(origin=invalid_origin),
                    patch.dict(os.environ, {"SIGMA_CLOUD_PUBLIC_ORIGIN": invalid_origin}),
                ):
                    self.assertFalse(cloud_auth._mock_enabled(cloud_auth.config()))

    def test_mock_auth_disabled_for_hosted_and_nonlocal_configurations(self):
        with patch.dict(os.environ, {"SIGMA_MOCK_AUTH": "1"}):
            self.assertFalse(cloud_auth._mock_enabled(cloud_auth.config()))
            response = self.client.post(
                "/api/cloud-auth/mock/select?identity=admin",
                headers={"Origin": ORIGIN},
            )
            self.assertEqual(
                response.status_code, 401
            )  # Protected by auth middleware when mock mode is off.
        with patch.dict(
            os.environ,
            {
                "SIGMA_MOCK_AUTH": "1",
                "SIGMA_CLOUD_AUTH_LOCAL": "true",
                "SIGMA_CLOUD_PUBLIC_ORIGIN": ORIGIN,
            },
        ):
            self.assertFalse(cloud_auth._mock_enabled(cloud_auth.config()))

    def test_mock_auth_rejects_cross_origin_and_remote_clients(self):
        with patch.dict(
            os.environ,
            {
                "SIGMA_MOCK_AUTH": "1",
                "SIGMA_CLOUD_AUTH_LOCAL": "true",
                "SIGMA_CLOUD_PUBLIC_ORIGIN": "http://127.0.0.1:5173",
            },
        ):
            self.assertTrue(cloud_auth._mock_enabled(cloud_auth.config()))
            self.assertEqual(
                self.client.post(
                    "/api/cloud-auth/mock/select?identity=admin",
                    headers={"Origin": "http://evil.example"},
                ).status_code,
                403,
            )
            # A remote ASGI peer must be rejected even with an allowed Origin.
            from fastapi.testclient import TestClient

            with TestClient(
                app, base_url="http://127.0.0.1", client=("198.51.100.8", 12345)
            ) as remote:
                self.assertEqual(
                    remote.post(
                        "/api/cloud-auth/mock/select?identity=admin",
                        headers={"Origin": "http://127.0.0.1:5173"},
                    ).status_code,
                    403,
                )

    def start_flow(self, client=None, return_to=None):
        client = client or self.client
        cfg = cloud_auth.config()
        params = {"return_to": return_to} if return_to is not None else None
        response = client.get("/api/cloud-auth/login", params=params, follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual("Secure" in response.headers["set-cookie"], not cfg.local)
        self.assertIn("HttpOnly", response.headers["set-cookie"])
        self.assertIn("SameSite=lax", response.headers["set-cookie"])
        query = parse_qs(urlsplit(response.headers["location"]).query)
        self.assertEqual(query["code_challenge_method"], ["S256"])
        self.assertEqual(query["prompt"], ["select_account"])
        flow_cookie = cloud_auth._cookie_name(cloud_auth.FLOW_COOKIE, cfg)
        return query["state"][0], response.cookies[flow_cookie]

    def test_google_login_reports_missing_local_oauth_settings_before_redirect(self):
        with patch.dict(
            os.environ,
            {
                "SIGMA_CLOUD_AUTH_LOCAL": "true",
                "SIGMA_CLOUD_PUBLIC_ORIGIN": "http://127.0.0.1:5173",
                "GOOGLE_OIDC_CLIENT_ID": "",
                "GOOGLE_OIDC_CLIENT_SECRET": "",
            },
        ):
            response = self.client.get("/api/cloud-auth/login", follow_redirects=False)
        self.assertEqual(response.status_code, 503)
        self.assertIn("GOOGLE_OIDC_CLIENT_ID", response.json()["detail"])
        self.assertIn("GOOGLE_OIDC_CLIENT_SECRET", response.json()["detail"])

    def test_guest_cookie_is_bound_to_one_verified_subject(self):
        from sigma import cloud_workspaces

        token_value = uuid4().hex * 2
        owner = cloud_workspaces.guest_workspace(
            token_value, create=True, subject="verified-google-subject-a"
        )
        self.assertIsNotNone(owner)
        assert owner is not None
        same_owner = cloud_workspaces.guest_workspace(
            token_value, subject="verified-google-subject-a"
        )
        self.assertEqual(same_owner, owner)
        self.assertIsNone(
            cloud_workspaces.guest_workspace(token_value, subject="verified-google-subject-b")
        )
        # A signed-out browser can continue its temporary guest page; signing
        # in as another Google identity will be checked against the binding.
        self.assertEqual(cloud_workspaces.guest_workspace(token_value), owner)

    def test_guest_sample_projects_use_temporary_workspace_without_recents(self):
        from sigma import cloud_workspaces

        with TestClient(app, base_url="https://testserver") as guest:
            catalog = guest.get("/api/projects/samples")
            self.assertEqual(catalog.status_code, 200, catalog.text)
            raw_guest = guest.cookies.get(cloud_auth.GUEST_COOKIE)
            self.assertIsNotNone(raw_guest)
            workspace = cloud_workspaces.guest_workspace(raw_guest)
            self.assertIsNotNone(workspace)
            assert workspace is not None
            self.assertTrue(workspace.guest)
            sample_id = catalog.json()["projects"][0]["id"]
            opened = guest.post(
                "/api/projects/samples/open",
                json={"sample_id": sample_id},
                headers={"Origin": ORIGIN},
            )
            self.assertEqual(opened.status_code, 200, opened.text)
            project_path = Path(opened.json()["path"])
            self.assertTrue(project_path.is_relative_to(workspace.path))
            self.assertTrue((project_path / "project.json").is_file())
            self.assertEqual(guest.get("/api/projects/recent").json(), {"projects": []})
            inspected = guest.get("/api/projects/inspect", params={"path": str(project_path)})
            self.assertEqual(inspected.status_code, 200, inspected.text)
            self.assertEqual(
                guest.post(
                    "/api/projects/research-sessions/start",
                    json={"path": str(project_path)},
                    headers={"Origin": ORIGIN},
                ).status_code,
                403,
            )
            self.assertEqual(
                guest.post(
                    "/api/projects/text/convert",
                    json={"path": str(project_path)},
                    headers={"Origin": ORIGIN},
                ).status_code,
                403,
            )
        self.assertTrue(project_path.exists(), "Guest files remain until expiry, not as projects")
        with TestClient(app, base_url="https://testserver") as another_guest:
            self.assertEqual(another_guest.get("/api/projects/recent").status_code, 401)

    def test_guest_play_signin_and_project_signout_keep_the_project_page(self):
        from sigma import cloud_workspaces

        with TestClient(app, base_url="https://testserver") as browser:
            catalog = browser.get("/api/projects/samples")
            self.assertEqual(catalog.status_code, 200, catalog.text)
            opened = browser.post(
                "/api/projects/samples/open",
                json={"sample_id": catalog.json()["projects"][0]["id"]},
                headers={"Origin": ORIGIN},
            )
            self.assertEqual(opened.status_code, 200, opened.text)
            guest_path = opened.json()["path"]
            guest_id = opened.json()["project"]["id"]
            source_guest = cloud_workspaces.guest_workspace(
                browser.cookies.get(cloud_auth.GUEST_COOKIE)
            )
            self.assertIsNotNone(source_guest)

            completed = self.finish(
                client=browser,
                return_to=f"/project?path={guest_path}&resume_play=1",
            )
            self.assertEqual(completed.status_code, 303)
            return_query = parse_qs(urlsplit(completed.headers["location"]).query)
            member_path = return_query["path"][0]
            self.assertEqual(return_query["resume_play"], ["1"])
            self.assertNotEqual(member_path, guest_path)
            member_project = browser.post(
                "/api/projects/open", json={"path": member_path}, headers={"Origin": ORIGIN}
            )
            self.assertEqual(member_project.status_code, 200, member_project.text)
            self.assertEqual(member_project.json()["project"]["id"], guest_id)

            copied = browser.post(
                "/api/projects/guest-copy",
                json={"path": member_path},
                headers={"Origin": ORIGIN},
            )
            self.assertEqual(copied.status_code, 201, copied.text)
            guest_copy_path = copied.json()["path"]
            self.assertNotEqual(guest_copy_path, member_path)
            self.assertTrue(Path(member_path).exists(), "Signing out must retain the account copy")
            signed_out = browser.post("/api/cloud-auth/logout", headers={"Origin": ORIGIN})
            self.assertEqual(signed_out.status_code, 204)
            guest_copy = browser.post(
                "/api/projects/open", json={"path": guest_copy_path}, headers={"Origin": ORIGIN}
            )
            self.assertEqual(guest_copy.status_code, 200, guest_copy.text)
            self.assertEqual(guest_copy.json()["project"]["id"], guest_id)

    def test_separate_guest_workspaces_can_open_same_sample_with_saved_sessions(self):
        from sigma import research_sessions

        paths: list[str] = []
        session_ids: list[set[str]] = []
        for _ in range(2):
            with TestClient(app, base_url="https://testserver") as guest:
                opened = guest.post(
                    "/api/projects/samples/open",
                    json={"sample_id": "nonconsecutive-subset-sums"},
                    headers={"Origin": ORIGIN},
                )
                self.assertEqual(opened.status_code, 200, opened.text)
                path = opened.json()["path"]
                paths.append(path)
                session_ids.append({record["id"] for record in research_sessions._all(path)})

        self.assertTrue(session_ids[0])
        self.assertTrue(session_ids[1])
        self.assertFalse(session_ids[0] & session_ids[1])
        self.assertNotEqual(paths[0], paths[1])

    def test_guest_projects_stay_temporary_when_local_google_auth_is_unready(self):
        from dataclasses import replace

        from sigma import cloud_workspaces

        unavailable = replace(cloud_auth.config(), error="Google sign-in is not configured")
        with (
            patch.dict(os.environ, {"SIGMA_CLOUD_AUTH_LOCAL": "true"}),
            patch.object(cloud_auth, "config", return_value=unavailable),
            TestClient(app, base_url="https://testserver") as guest,
        ):
            catalog = guest.get("/api/projects/samples")
            self.assertEqual(catalog.status_code, 200, catalog.text)
            opened = guest.post(
                "/api/projects/samples/open",
                json={"sample_id": catalog.json()["projects"][0]["id"]},
                headers={"Origin": ORIGIN},
            )
            self.assertEqual(opened.status_code, 200, opened.text)
            workspace = cloud_workspaces.guest_workspace(
                guest.cookies.get(cloud_auth._cookie_name(cloud_auth.GUEST_COOKIE, unavailable))
            )
            self.assertIsNotNone(workspace)
            assert workspace is not None
            self.assertTrue(Path(opened.json()["path"]).is_relative_to(workspace.path))

    def finish(
        self,
        email="admin@example.org",
        subject="google-sub-1",
        changes=None,
        client=None,
        return_to=None,
    ):
        client = client or self.client
        state, flow_cookie = self.start_flow(client, return_to=return_to)
        with cloud_auth._db(cloud_auth.config()) as db:
            nonce = db.execute(
                "SELECT nonce FROM flows WHERE state_hash=?", (cloud_auth._hash(state),)
            ).fetchone()["nonce"]
        GoogleClient.token = token(nonce=nonce, email=email, subject=subject, **(changes or {}))
        client.cookies.set(
            cloud_auth._cookie_name(cloud_auth.FLOW_COOKIE, cloud_auth.config()), flow_cookie
        )
        with patch.object(cloud_auth.httpx, "AsyncClient", GoogleClient):
            return client.get(
                "/api/cloud-auth/callback",
                params={"state": state, "code": "fixture"},
                follow_redirects=False,
            )

    def seed_personal_plan_authorization(
        self,
        subject: str,
        email: str | None = None,
        *,
        record_authorization: bool = True,
    ) -> None:
        """Fixture for tests whose setup assumes completed personal OAuth."""
        from sigma import ai_store, chatgpt_auth

        directory = ai_store.personal_directory_for_subject(subject)
        path = directory / "credentials.json"
        state = ai_store.read(path)
        state["accounts"] = {
            "fixture-personal": {
                "subject": "chatgpt-subject-" + subject,
                "client_id": "fixture-chatgpt-client",
                "email": email or f"personal-{subject}@example.org",
                "access_token": "fixture-personal-access-token-" + os.urandom(8).hex(),
                "refresh_token": "fixture-personal-refresh-token-" + subject,
                "expires_at": time.time() + 3600,
                "scopes": list(chatgpt_auth.PLAN_SCOPES),
                "plan_authorized": True,
            }
        }
        state["active"], state["mode"] = "fixture-personal", "chatgpt"
        ai_store.write(path, state)
        if record_authorization:
            cloud_auth.record_personal_authorization(subject)

    def test_signin_returns_to_safe_project_continuation(self):
        project_return = "/project?path=%2Ftmp%2Fguest-project&resume_play=1"
        completed = self.finish(return_to=project_return)
        self.assertEqual(completed.status_code, 303)
        self.assertEqual(completed.headers["location"], project_return)

        unsupported_intent, _ = self.start_flow(
            return_to="/project?path=%2Ftmp%2Fguest-project&resume_play=2"
        )
        with cloud_auth._db(cloud_auth.config()) as db:
            flow = db.execute(
                "SELECT return_to FROM flows WHERE state_hash=?",
                (cloud_auth._hash(unsupported_intent),),
            ).fetchone()
        self.assertEqual(flow["return_to"], "/project?path=%2Ftmp%2Fguest-project")

        state, _ = self.start_flow(return_to="https://evil.example/steal")
        with cloud_auth._db(cloud_auth.config()) as db:
            flow = db.execute(
                "SELECT return_to FROM flows WHERE state_hash=?", (cloud_auth._hash(state),)
            ).fetchone()
        self.assertIsNone(flow["return_to"])

    def test_successful_signin_admin_invite_and_revocation(self):
        self.assertEqual(
            self.client.get(
                "/api/projects/research-sessions", params={"path": str(self.project_path)}
            ).status_code,
            401,
        )
        self.assertEqual(
            self.client.get(
                "/api/projects/research-sessions", headers={"X-User-Email": "admin@example.org"}
            ).status_code,
            401,
        )
        signed_in = self.finish()
        self.assertEqual(signed_in.status_code, 303)
        self.assertTrue((self.root / "workspaces" / "workspaces.sqlite3").is_file())
        session = signed_in.cookies[cloud_auth.SESSION_COOKIE]
        self.assertIn("Secure", signed_in.headers["set-cookie"])
        self.assertIn("HttpOnly", signed_in.headers["set-cookie"])
        self.assertIn("Max-Age=28800", signed_in.headers["set-cookie"])
        self.client.cookies.set(cloud_auth.SESSION_COOKIE, session)
        status = self.client.get("/api/cloud-auth/status").json()
        self.assertEqual(
            status["user"],
            {"email": "admin@example.org", "role": "admin"},
        )
        self.assertEqual(
            status["account"]["identity"], {"email": "admin@example.org", "verified": True}
        )
        self.assertEqual(status["account"]["access"], {"status": "invited", "role": "admin"})
        self.assertTrue(status["account"]["workspace"]["available"])
        self.assertEqual(
            status["account"]["model_access"],
            {"mode": "sponsored", "connection": "checking"},
        )
        self.assertTrue(status["account"]["sponsorship"]["eligible"])
        self.assertEqual(status["admin_contact_email"], "admin@example.org")
        self.assertNotIn("grants", status)
        self.assertNotIn("denied_email", status)
        # Exercise the real verified Principal -> workspace dependency path,
        # not only the test-only deterministic identity adapter.
        workspace_response = self.client.get(
            "/api/projects/recent",
            headers={
                "X-Test-Subject": "forged-browser-subject",
                "X-User-Email": "victim@example.org",
                "X-Workspace-ID": "forged-workspace",
            },
        )
        self.assertEqual(workspace_response.status_code, 200, workspace_response.text)
        self.assertEqual(workspace_response.json()["projects"], [])
        workspace_database = self.root / "workspaces" / "workspaces.sqlite3"
        self.assertTrue(workspace_database.is_file())
        import sqlite3

        with sqlite3.connect(workspace_database) as db:
            entries = db.execute("SELECT subject_hash,workspace_id FROM workspaces").fetchall()
        self.assertEqual(len(entries), 1)
        with sqlite3.connect(self.root / "access.sqlite3") as db:
            persisted = db.execute(
                "SELECT email,role,access_active,workspace_id,sponsorship_eligible,model_access,model_connection_status FROM user_state WHERE subject=?",
                ("google-sub-1",),
            ).fetchone()
        self.assertEqual(
            persisted,
            (
                "admin@example.org",
                "admin",
                1,
                status["account"]["workspace"]["id"],
                1,
                "sponsored",
                "checking",
            ),
        )
        self.assertNotIn(b"forged-browser-subject", workspace_database.read_bytes())
        self.assertNotIn(b"victim@example.org", workspace_database.read_bytes())
        invite = self.client.post(
            "/api/cloud-auth/admin/grants",
            json={"kind": "email", "value": " Person@Example.org ", "role": "member"},
            headers={"Origin": ORIGIN},
        )
        self.assertEqual(invite.status_code, 200)
        self.assertEqual(invite.json()["value"], "person@example.org")
        member_context = TestClient(app)
        member = member_context.__enter__()
        self.addCleanup(member_context.__exit__, None, None, None)
        member_login = self.finish(
            email="person@example.org", subject="google-sub-member", client=member
        )
        self.assertEqual(member_login.status_code, 303)
        revoked = self.client.delete(
            "/api/cloud-auth/admin/grants/email/person%40example.org", headers={"Origin": ORIGIN}
        )
        self.assertEqual(revoked.status_code, 200)
        with sqlite3.connect(self.root / "access.sqlite3") as db:
            member_state = db.execute(
                "SELECT access_active,sponsorship_eligible FROM user_state WHERE subject=?",
                ("google-sub-member",),
            ).fetchone()
        self.assertEqual(member_state, (0, 0))
        self.assertEqual(member.get("/api/projects/recent").status_code, 401)
        self.assertEqual(
            self.client.get("/api/cloud-auth/admin/grants").json()["grants"][0]["active"], 0
        )
        self.assertEqual(
            self.client.post("/api/ai/disconnect", headers={"Origin": ORIGIN}).status_code, 403
        )

    def test_hosted_read_only_model_checks_keep_auth_mutations_blocked(self):
        signed_in = self.finish()
        self.client.cookies.set(
            cloud_auth.SESSION_COOKIE, signed_in.cookies[cloud_auth.SESSION_COOKIE]
        )
        with patch("sigma.api.models", return_value={"connection": {"status": "unconfigured"}}):
            response = self.client.get("/api/ai/models")
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()["connection"]["status"], "unconfigured")
            self.assertEqual(response.headers["cache-control"], "no-store")
        with patch("sigma.api.connection", return_value={"status": "unconfigured"}):
            self.assertEqual(self.client.get("/api/ai/connection").status_code, 200)
        for path in ("/api/ai/auth/begin", "/api/ai/disconnect"):
            self.assertEqual(
                self.client.post(path, headers={"Origin": ORIGIN}, json={}).status_code, 403
            )
        self.assertEqual(
            self.client.post(
                "/api/ai/mode", headers={"Origin": ORIGIN}, json={"mode": "api_key"}
            ).status_code,
            422,
        )
        # The admin-only sponsor handoff route accepts this URL shape, but an
        # unknown identifier cannot resolve to an OAuth authorization URL.
        self.assertEqual(self.client.get("/api/ai/auth/open/guessed").status_code, 400)
        self.assertEqual(TestClient(app).get("/api/ai/models").status_code, 401)

    def test_session_persists_across_client_restart_and_logout_revokes_it(self):
        signed_in = self.finish()
        raw = signed_in.cookies[cloud_auth.SESSION_COOKIE]

        # A new desktop browser process keeps its secure cookie while the
        # server-side session remains in the persistent auth database.
        restarted_context = TestClient(app)
        restarted = restarted_context.__enter__()
        self.addCleanup(restarted_context.__exit__, None, None, None)
        restarted.cookies.set(cloud_auth.SESSION_COOKIE, raw)
        self.assertEqual(
            restarted.get("/api/cloud-auth/status").json()["user"]["email"], "admin@example.org"
        )
        self.assertEqual(restarted.get("/api/projects/recent").status_code, 200)

        signed_out = restarted.post("/api/cloud-auth/logout", headers={"Origin": ORIGIN})
        self.assertEqual(signed_out.status_code, 204)
        self.assertIn('__Host-sigma_session="";', signed_out.headers["set-cookie"])
        self.assertIn("Max-Age=0", signed_out.headers["set-cookie"])
        self.assertIsNone(cloud_auth.resolve_session(raw))
        self.assertEqual(restarted.get("/api/projects/recent").status_code, 401)

        # A copied/stale cookie cannot restore access from another client.
        stale_context = TestClient(app)
        stale = stale_context.__enter__()
        self.addCleanup(stale_context.__exit__, None, None, None)
        stale.cookies.set(cloud_auth.SESSION_COOKIE, raw)
        self.assertEqual(stale.get("/api/projects/recent").status_code, 401)

    def test_admin_contact_is_designated_admin_and_subject_binding_is_enforced(self):
        response = self.finish(email="admin@example.org", subject="first-admin-subject")
        self.assertEqual(response.status_code, 303)
        self.assertIn(cloud_auth.SESSION_COOKIE, response.cookies)

        second_context = TestClient(app)
        second_client = second_context.__enter__()
        self.addCleanup(second_context.__exit__, None, None, None)
        denied = self.finish(
            email="admin@example.org", subject="different-google-subject", client=second_client
        )
        self.assertEqual(denied.status_code, 303)
        self.assertEqual(denied.headers["location"], "/?access=denied")
        self.assertNotIn(cloud_auth.SESSION_COOKIE, denied.cookies)

    def test_invitation_request_uses_verified_identity_and_is_admin_only(self):
        admin_login = self.finish(email="admin@example.org", subject="request-admin")
        self.assertEqual(admin_login.status_code, 303)
        self.client.cookies.set(
            cloud_auth.SESSION_COOKIE, admin_login.cookies[cloud_auth.SESSION_COOKIE]
        )
        visitor_context = TestClient(app)
        visitor = visitor_context.__enter__()
        self.addCleanup(visitor_context.__exit__, None, None, None)
        denied = self.finish(email="visitor@example.org", subject="request-visitor", client=visitor)
        self.assertEqual(denied.headers["location"], "/?access=denied")
        visitor.cookies.set(cloud_auth.DENIED_COOKIE, denied.cookies[cloud_auth.DENIED_COOKIE])
        with patch.object(cloud_auth, "_deliver_invitation") as deliver:
            result = visitor.post(
                "/api/cloud-auth/invitation-request",
                json={"email": "forged@example.org"},
                headers={"Origin": ORIGIN},
            )
        self.assertEqual(result.status_code, 200)
        deliver.assert_called_once()
        self.assertEqual(deliver.call_args.args[0], "visitor@example.org")
        self.assertGreater(deliver.call_args.args[1], 0)
        self.assertEqual(visitor.get("/api/cloud-auth/admin/invitation-requests").status_code, 401)
        requests = self.client.get("/api/cloud-auth/admin/invitation-requests")
        self.assertEqual(requests.status_code, 200)
        row = requests.json()["requests"][0]
        self.assertEqual(row["email"], "visitor@example.org")
        self.assertEqual(row["status"], "notified")
        authorized = self.client.post(
            "/api/cloud-auth/admin/grants",
            json={"kind": "email", "value": "Visitor@Example.org", "role": "member"},
            headers={"Origin": ORIGIN},
        )
        self.assertEqual(authorized.status_code, 200)
        self.assertEqual(
            self.client.get("/api/cloud-auth/admin/invitation-requests").json()["requests"], []
        )
        revoked = self.client.delete(
            "/api/cloud-auth/admin/grants/email/visitor%40example.org",
            headers={"Origin": ORIGIN},
        )
        self.assertEqual(revoked.status_code, 200)
        row = self.client.get("/api/cloud-auth/admin/invitation-requests").json()["requests"][0]
        updated = self.client.put(
            f"/api/cloud-auth/admin/invitation-requests/{row['subject']}",
            json={"status": "reviewed"},
            headers={"Origin": ORIGIN},
        )
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.json()["status"], "reviewed")
        self.assertEqual(
            self.client.get("/api/cloud-auth/admin/invitation-requests").json()["requests"], []
        )
        # A reviewed request is closed. Since the grant was subsequently
        # revoked, this uninvited identity can submit a fresh request; that
        # fresh request is then deduplicated while it is open.
        with patch.object(cloud_auth, "_deliver_invitation") as redeliver:
            resubmitted = visitor.post(
                "/api/cloud-auth/invitation-request", headers={"Origin": ORIGIN}
            )
            self.assertEqual(resubmitted.status_code, 200, resubmitted.text)
            self.assertEqual(resubmitted.json(), {"status": "notified", "duplicate": False})
            requests = self.client.get("/api/cloud-auth/admin/invitation-requests").json()[
                "requests"
            ]
            self.assertEqual(len(requests), 1)
            self.assertEqual(requests[0]["email"], "visitor@example.org")
            self.assertEqual(requests[0]["status"], "notified")
            self.assertTrue(
                visitor.post(
                    "/api/cloud-auth/invitation-request", headers={"Origin": ORIGIN}
                ).json()["duplicate"]
            )
            redeliver.assert_called_once()
        self.assertEqual(deliver.call_count, 1)

    def test_invited_user_welcome_is_persisted_once_and_scoped_to_identity(self):
        admin_login = self.finish(email="admin@example.org", subject="welcome-admin")
        self.client.cookies.set(
            cloud_auth.SESSION_COOKIE, admin_login.cookies[cloud_auth.SESSION_COOKIE]
        )
        initial_admin = self.client.get("/api/cloud-auth/status").json()
        self.assertFalse(initial_admin["account"]["invitation_welcome_pending"])
        grant = self.client.post(
            "/api/cloud-auth/admin/grants",
            headers={"Origin": ORIGIN},
            json={
                "kind": "email",
                "value": "welcome-member@example.org",
                "role": "member",
                "allowance_usd": 0.75,
            },
        )
        self.assertEqual(grant.status_code, 200, grant.text)

        member_login = self.finish(email="welcome-member@example.org", subject="welcome-member")
        self.client.cookies.set(
            cloud_auth.SESSION_COOKIE, member_login.cookies[cloud_auth.SESSION_COOKIE]
        )
        invited = self.client.get("/api/cloud-auth/status").json()
        self.assertTrue(invited["account"]["invitation_welcome_pending"])

        cross_origin = self.client.post(
            "/api/cloud-auth/welcome", headers={"Origin": "https://other.test"}
        )
        self.assertEqual(cross_origin.status_code, 403)
        dismissed = self.client.post("/api/cloud-auth/welcome", headers={"Origin": ORIGIN})
        self.assertEqual(dismissed.status_code, 200, dismissed.text)
        self.assertEqual(dismissed.json(), {"dismissed": True})
        self.assertFalse(
            self.client.get("/api/cloud-auth/status").json()["account"][
                "invitation_welcome_pending"
            ]
        )

        # A new verified callback and subsequent reload do not repeat a dismissed welcome.
        repeated_login = self.finish(email="welcome-member@example.org", subject="welcome-member")
        self.client.cookies.set(
            cloud_auth.SESSION_COOKIE, repeated_login.cookies[cloud_auth.SESSION_COOKIE]
        )
        self.assertFalse(
            self.client.get("/api/cloud-auth/status").json()["account"][
                "invitation_welcome_pending"
            ]
        )

        self.client.cookies.clear()
        guest_attempt = self.client.post("/api/cloud-auth/welcome", headers={"Origin": ORIGIN})
        self.assertEqual(guest_attempt.status_code, 401)

    def test_invitation_welcome_schema_migrates_existing_user_state(self):
        path = self.root / "legacy-auth.sqlite3"
        db = sqlite3.connect(path)
        try:
            db.execute(
                """CREATE TABLE user_state (
                    subject TEXT PRIMARY KEY, email TEXT NOT NULL,
                    role TEXT NOT NULL CHECK(role IN ('member','admin')),
                    access_active INTEGER NOT NULL CHECK(access_active IN (0,1)),
                    workspace_id TEXT,
                    sponsorship_eligible INTEGER NOT NULL CHECK(sponsorship_eligible IN (0,1)),
                    model_access TEXT NOT NULL CHECK(model_access IN ('personal','sponsored')),
                    model_connection_status TEXT NOT NULL DEFAULT 'checking',
                    updated_at INTEGER NOT NULL
                )"""
            )
            db.execute(
                "INSERT INTO user_state VALUES('legacy-subject','legacy@example.org','member',1,NULL,0,'personal','checking',123)"
            )
            db.commit()
        finally:
            db.close()
        path.chmod(0o600)
        cloud_auth._initialize(path)
        db = sqlite3.connect(path)
        try:
            columns = {row[1] for row in db.execute("PRAGMA table_info(user_state)")}
            self.assertIn("invitation_welcome_pending", columns)
            self.assertIn("model_access_explicit", columns)
            pending = db.execute(
                "SELECT invitation_welcome_pending FROM user_state WHERE subject='legacy-subject'"
            ).fetchone()[0]
            explicit = db.execute(
                "SELECT model_access_explicit FROM user_state WHERE subject='legacy-subject'"
            ).fetchone()[0]
        finally:
            db.close()
        self.assertEqual(pending, 0)
        self.assertEqual(explicit, 0)

    def test_invitation_request_succeeds_when_notification_delivery_fails(self):
        denied = self.finish(email="visitor@example.org", subject="request-retry")
        self.client.cookies.set(cloud_auth.DENIED_COOKIE, denied.cookies[cloud_auth.DENIED_COOKIE])
        with patch.object(
            cloud_auth, "_deliver_invitation", side_effect=RuntimeError("not configured")
        ):
            accepted = self.client.post(
                "/api/cloud-auth/invitation-request", headers={"Origin": ORIGIN}
            )
        self.assertEqual(accepted.status_code, 200)
        self.assertEqual(accepted.json(), {"status": "pending", "duplicate": False})
        with cloud_auth._db(cloud_auth.config()) as db:
            saved = db.execute(
                "SELECT status,notification_error FROM invitation_requests WHERE subject='request-retry'"
            ).fetchone()
        self.assertEqual(saved["status"], "pending")
        self.assertEqual(saved["notification_error"], "delivery failed")
        self.assertEqual(denied.headers["location"], "/?access=denied")

    def test_invitation_notification_uses_verified_admins_not_fixed_recipient(self):
        self.finish(email="admin@example.org", subject="verified-notification-admin")
        with (
            patch.dict(
                os.environ,
                {
                    "SIGMA_INVITATION_SMTP_USERNAME": "sigma-notify@example.org",
                    "SIGMA_INVITATION_SMTP_PASSWORD": "fixture-app-password",
                },
            ),
            patch.object(cloud_auth.smtplib, "SMTP") as smtp_factory,
        ):
            client = smtp_factory.return_value.__enter__.return_value
            cloud_auth._deliver_invitation("verified@example.org", 123)
        smtp_factory.assert_called_once_with("smtp.gmail.com", 587, timeout=10)
        client.starttls.assert_called_once()
        client.login.assert_called_once_with("sigma-notify@example.org", "fixture-app-password")
        message = client.send_message.call_args.args[0]
        self.assertEqual(message["From"], "sigma-notify@example.org")
        self.assertEqual(message["To"], "sigma-notify@example.org")
        self.assertEqual(message["Bcc"], "admin@example.org")
        self.assertEqual(client.send_message.call_args.kwargs["to_addrs"], ["admin@example.org"])

    def test_notification_recipient_set_tracks_verified_admin_grants_and_revocation(self):
        self.finish(email="admin@example.org", subject="notice-bootstrap")
        with cloud_auth._db(cloud_auth.config()) as db:
            db.execute(
                "INSERT INTO grants(kind,value,role,active,updated_at) VALUES('email',?,'admin',1,?)",
                ("second@example.org", cloud_auth._now()),
            )
        self.finish(email="second@example.org", subject="notice-second")
        with cloud_auth._db(cloud_auth.config()) as db:
            db.execute(
                "INSERT INTO grants(kind,value,role,active,updated_at) VALUES('email',?,'admin',1,?)",
                ("not-verified@example.org", cloud_auth._now()),
            )
        cfg = cloud_auth.config()
        self.assertEqual(
            cloud_auth._notification_admin_recipients(cfg),
            ["admin@example.org", "not-verified@example.org", "second@example.org"],
        )
        with (
            patch.dict(
                os.environ,
                {
                    "SIGMA_INVITATION_SMTP_USERNAME": "sigma-notify@example.org",
                    "SIGMA_INVITATION_SMTP_PASSWORD": "fixture-app-password",
                },
            ),
            patch.object(cloud_auth.smtplib, "SMTP") as smtp_factory,
        ):
            cloud_auth._deliver_invitation("applicant@example.org", 123)
        client = smtp_factory.return_value.__enter__.return_value
        sent = client.send_message.call_args
        self.assertEqual(sent.args[0]["To"], "sigma-notify@example.org")
        self.assertEqual(
            sent.args[0]["Bcc"],
            "admin@example.org, not-verified@example.org, second@example.org",
        )
        self.assertEqual(
            sent.kwargs["to_addrs"],
            ["admin@example.org", "not-verified@example.org", "second@example.org"],
        )
        with cloud_auth._db(cfg) as db:
            db.execute(
                "UPDATE grants SET active=0 WHERE kind='email' AND value=?",
                ("second@example.org",),
            )
        self.assertEqual(
            cloud_auth._notification_admin_recipients(cfg),
            ["admin@example.org", "not-verified@example.org"],
        )

    def test_feedback_delivery_failure_does_not_lose_saved_submission(self):
        self.finish(email="admin@example.org", subject="notice-feedback-admin")
        with patch.object(
            cloud_auth, "_deliver_feedback", side_effect=RuntimeError("mail unavailable")
        ) as send:
            received = self.client.post(
                "/api/cloud-auth/feedback",
                json={"message": "Please make the Session controls more visible."},
                headers={"Origin": ORIGIN},
            )
        self.assertEqual(received.status_code, 200, received.text)
        self.assertEqual(received.json()["status"], "received")
        send.assert_called_once()
        with cloud_auth._db(cloud_auth.config()) as db:
            row = db.execute(
                "SELECT message,notification_error,status FROM feedback_requests WHERE id=?",
                (received.json()["id"],),
            ).fetchone()
        self.assertIn("Session controls", row["message"])
        self.assertEqual(row["notification_error"], "delivery failed")
        self.assertEqual(row["status"], "new")

    def test_invitation_requests_are_rate_limited_per_verified_email(self):
        with patch.object(cloud_auth, "_deliver_invitation"):
            for index in range(4):
                denied = self.finish(email="visitor@example.org", subject=f"request-limit-{index}")
                self.client.cookies.set(
                    cloud_auth.DENIED_COOKIE, denied.cookies[cloud_auth.DENIED_COOKIE]
                )
                response = self.client.post(
                    "/api/cloud-auth/invitation-request", headers={"Origin": ORIGIN}
                )
                self.assertEqual(response.status_code, 429 if index == 3 else 200)

    def test_simultaneous_invitation_submission_does_not_send_duplicate_mail(self):
        denied = self.finish(email="visitor@example.org", subject="request-concurrent")
        raw_cookie = denied.cookies[cloud_auth.DENIED_COOKIE]
        self.client.cookies.set(cloud_auth.DENIED_COOKIE, raw_cookie)
        with cloud_auth._db(cloud_auth.config()) as db:
            subject = db.execute(
                "SELECT subject FROM denied_access WHERE token_hash=?",
                (cloud_auth._hash(raw_cookie),),
            ).fetchone()["subject"]
            db.execute(
                "INSERT INTO invitation_requests(subject,email,requested_at,status,notification_started_at) VALUES(?,?,?,'sending',?)",
                (subject, "visitor@example.org", int(time.time()), int(time.time())),
            )
        with patch.object(cloud_auth, "_deliver_invitation") as deliver:
            response = self.client.post(
                "/api/cloud-auth/invitation-request", headers={"Origin": ORIGIN}
            )
        self.assertEqual(response.status_code, 409)
        deliver.assert_not_called()

    def test_feedback_persists_optional_contact_and_verified_account_for_admin_review(self):
        response = self.finish(email="admin@example.org", subject="feedback-admin")
        self.client.cookies.set(
            cloud_auth.SESSION_COOKIE, response.cookies[cloud_auth.SESSION_COOKIE]
        )
        visitor_context = TestClient(app)
        visitor = visitor_context.__enter__()
        self.addCleanup(visitor_context.__exit__, None, None, None)
        submitted = visitor.post(
            "/api/cloud-auth/feedback",
            json={
                "message": "Please make the saved session list easier to scan.",
                "contact_email": " Visitor@Example.org ",
                "subject": "forged-subject",
                "account_email": "forged@example.org",
            },
            headers={"Origin": ORIGIN},
        )
        self.assertEqual(submitted.status_code, 422)
        accepted = visitor.post(
            "/api/cloud-auth/feedback",
            json={
                "message": "Please make the saved session list easier to scan.",
                "contact_email": " Visitor@Example.org ",
            },
            headers={"Origin": ORIGIN},
        )
        self.assertEqual(accepted.status_code, 200)
        self.assertEqual(accepted.json()["status"], "received")
        cookie = accepted.cookies[cloud_auth.FEEDBACK_RATE_COOKIE]
        self.assertIn("HttpOnly", accepted.headers["set-cookie"])
        self.assertIn("Secure", accepted.headers["set-cookie"])
        self.assertIn("SameSite=lax", accepted.headers["set-cookie"])
        with cloud_auth._db(cloud_auth.config()) as db:
            stored = db.execute(
                "SELECT * FROM feedback_requests WHERE id=?", (accepted.json()["id"],)
            ).fetchone()
            rate_row = db.execute("SELECT key_hash FROM feedback_rate_limits").fetchone()
        self.assertEqual(stored["contact_email"], "visitor@example.org")
        self.assertIsNone(stored["subject"])
        self.assertIsNone(stored["account_email"])
        self.assertNotEqual(rate_row["key_hash"], cookie)
        self.assertEqual(visitor.get("/api/cloud-auth/admin/feedback").status_code, 401)
        inbox = self.client.get("/api/cloud-auth/admin/feedback")
        self.assertEqual(inbox.status_code, 200)
        row = inbox.json()["feedback"][0]
        self.assertEqual(row["id"], accepted.json()["id"])
        self.assertEqual(row["contact_email"], "visitor@example.org")
        self.assertIsNone(row["account_email"])
        updated = self.client.put(
            f"/api/cloud-auth/admin/feedback/{row['id']}",
            json={"status": "reviewed"},
            headers={"Origin": ORIGIN},
        )
        self.assertEqual(updated.status_code, 200)
        removed = self.client.delete(
            f"/api/cloud-auth/admin/feedback/{row['id']}", headers={"Origin": ORIGIN}
        )
        self.assertEqual(removed.status_code, 200)
        self.assertEqual(removed.json(), {"removed": True})
        self.assertEqual(self.client.get("/api/cloud-auth/admin/feedback").json()["feedback"], [])
        with cloud_auth._db(cloud_auth.config()) as db:
            audit = db.execute(
                "SELECT actor,action,kind,value FROM audit WHERE action='feedback_removed'"
            ).fetchone()
        self.assertEqual(
            tuple(audit),
            ("admin@example.org", "feedback_removed", "feedback", row["id"]),
        )
        self.assertEqual(
            visitor.put(
                f"/api/cloud-auth/admin/feedback/{row['id']}",
                json={"status": "closed"},
                headers={"Origin": ORIGIN},
            ).status_code,
            401,
        )
        self.assertEqual(
            visitor.delete(
                f"/api/cloud-auth/admin/feedback/{row['id']}", headers={"Origin": ORIGIN}
            ).status_code,
            401,
        )

    def test_feedback_records_only_verified_session_identity_and_rate_limits(self):
        signed_in = self.finish(email="admin@example.org", subject="feedback-member")
        self.client.cookies.set(
            cloud_auth.SESSION_COOKIE, signed_in.cookies[cloud_auth.SESSION_COOKIE]
        )
        for index in range(6):
            response = self.client.post(
                "/api/cloud-auth/feedback",
                json={"message": f"Feedback message {index} with enough characters."},
                headers={"Origin": ORIGIN},
            )
            self.assertEqual(response.status_code, 429 if index == 5 else 200)
        with cloud_auth._db(cloud_auth.config()) as db:
            rows = db.execute("SELECT subject,account_email FROM feedback_requests").fetchall()
            buckets = db.execute("SELECT COUNT(*) AS n FROM feedback_rate_limits").fetchone()["n"]
        self.assertEqual(len(rows), 5)
        self.assertTrue(all(row["subject"] == "feedback-member" for row in rows))
        self.assertTrue(all(row["account_email"] == "admin@example.org" for row in rows))
        self.assertEqual(buckets, 1)

    def test_feedback_validates_fields_and_requires_same_origin(self):
        for payload in (
            {"message": "short"},
            {"message": "A message with enough characters.", "contact_email": "bad-email"},
            {"message": "A message with enough characters.", "identity": "admin@example.org"},
        ):
            response = self.client.post(
                "/api/cloud-auth/feedback", json=payload, headers={"Origin": ORIGIN}
            )
            self.assertEqual(response.status_code, 422)
        self.assertEqual(
            self.client.post(
                "/api/cloud-auth/feedback",
                json={"message": "A message with enough characters."},
                headers={"Origin": "https://attacker.example"},
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.post(
                "/api/cloud-auth/feedback", json={"message": "A message with enough characters."}
            ).status_code,
            403,
        )
        self.assertEqual(self.client.get("/api/cloud-auth/admin/feedback").status_code, 401)

    def test_non_admin_cannot_review_or_read_feedback(self):
        signed_in = self.finish(email="admin@example.org", subject="feedback-review-admin")
        self.client.cookies.set(
            cloud_auth.SESSION_COOKIE, signed_in.cookies[cloud_auth.SESSION_COOKIE]
        )
        grant = self.client.post(
            "/api/cloud-auth/admin/grants",
            json={"kind": "email", "value": "member@example.org", "role": "member"},
            headers={"Origin": ORIGIN},
        )
        self.assertEqual(grant.status_code, 200)
        member_context = TestClient(app)
        member = member_context.__enter__()
        self.addCleanup(member_context.__exit__, None, None, None)
        member_login = self.finish(
            email="member@example.org", subject="feedback-review-member", client=member
        )
        member.cookies.set(
            cloud_auth.SESSION_COOKIE, member_login.cookies[cloud_auth.SESSION_COOKIE]
        )
        submitted = member.post(
            "/api/cloud-auth/feedback",
            json={"message": "Please clarify the recent projects panel."},
            headers={"Origin": ORIGIN},
        )
        self.assertEqual(submitted.status_code, 200)
        self.assertEqual(member.get("/api/cloud-auth/admin/feedback").status_code, 403)
        self.assertEqual(
            member.put(
                f"/api/cloud-auth/admin/feedback/{submitted.json()['id']}",
                json={"status": "closed"},
                headers={"Origin": ORIGIN},
            ).status_code,
            403,
        )
        self.assertEqual(
            member.delete(
                f"/api/cloud-auth/admin/feedback/{submitted.json()['id']}",
                headers={"Origin": ORIGIN},
            ).status_code,
            403,
        )

    def test_changing_contact_preserves_bound_admin_and_authorizes_new_contact(self):
        response = self.finish(email="admin@example.org", subject="preserved-admin-subject")
        self.assertIn(cloud_auth.SESSION_COOKIE, response.cookies)
        os.environ["SIGMA_CLOUD_ADMIN_CONTACT_EMAIL"] = "zetacontinuation@gmail.com"

        admin_client_context = TestClient(app)
        admin_client = admin_client_context.__enter__()
        self.addCleanup(admin_client_context.__exit__, None, None, None)
        admin_client.cookies.set(
            cloud_auth.SESSION_COOKIE, response.cookies[cloud_auth.SESSION_COOKIE]
        )
        status = admin_client.get("/api/cloud-auth/status").json()
        self.assertEqual(status["admin_contact_email"], "zetacontinuation@gmail.com")
        self.assertEqual(status["user"], {"email": "admin@example.org", "role": "admin"})
        self.assertEqual(
            admin_client.get("/api/cloud-auth/admin/grants").json()["bootstrap_admin"],
            "admin@example.org",
        )

        denied_context = TestClient(app)
        denied_client = denied_context.__enter__()
        self.addCleanup(denied_context.__exit__, None, None, None)
        denied = self.finish(
            email="zetacontinuation@gmail.com", subject="new-contact-subject", client=denied_client
        )
        self.assertNotEqual(denied.headers["location"], "/?access=denied")
        self.assertIn(cloud_auth.SESSION_COOKIE, denied.cookies)
        denied_client.cookies.set(
            cloud_auth.SESSION_COOKIE, denied.cookies[cloud_auth.SESSION_COOKIE]
        )
        status = denied_client.get("/api/cloud-auth/status").json()
        self.assertEqual(status["user"]["role"], "admin")
        self.assertFalse(status["account"]["invitation_welcome_pending"])
        # The contact email remains pinned to its verified Google subject.
        other_context = TestClient(app)
        other = other_context.__enter__()
        self.addCleanup(other_context.__exit__, None, None, None)
        mismatched = self.finish(
            email="zetacontinuation@gmail.com", subject="different-google-subject", client=other
        )
        self.assertEqual(mismatched.headers["location"], "/?access=denied")

    def test_local_google_chosen_configured_admin_is_signed_in_without_invitation(self):
        # Reproduce a local development instance whose first bootstrap admin was
        # previously bound to a different Google account. Selecting the now
        # configured admin in Google's standard chooser must grant access.
        with patch.dict(
            os.environ,
            {
                "SIGMA_CLOUD_AUTH_LOCAL": "true",
                "SIGMA_CLOUD_PUBLIC_ORIGIN": "http://127.0.0.1:5173",
            },
        ):
            first = self.finish(email="admin@example.org", subject="initial-google-subject")
            self.assertIn("sigma_session", first.cookies)
            self.client.cookies.clear()
            initially_uninvited = self.finish(
                email="zetacontinuation@gmail.com", subject="configured-google-subject"
            )
            self.assertEqual(initially_uninvited.headers["location"], "/")
            self.assertIn("sigma_session", initially_uninvited.cookies)
            self.client.cookies.set("sigma_session", initially_uninvited.cookies["sigma_session"])
            self.assertEqual(
                self.client.get("/api/cloud-auth/status").json()["user"]["role"], "guest"
            )
            os.environ["SIGMA_CLOUD_ADMIN_CONTACT_EMAIL"] = "zetacontinuation@gmail.com"
            # The verified identity becomes an administrator as soon as the
            # configured contact changes; guest status does not pin its role.
            self.assertEqual(
                self.client.get("/api/cloud-auth/status").json()["user"]["role"], "admin"
            )
            self.assertEqual(
                self.client.post(
                    "/api/cloud-auth/invitation-request",
                    json={},
                    headers={"Origin": "http://127.0.0.1:5173"},
                ).status_code,
                401,
            )
            # A fresh chooser flow continues to complete normally.
            allowed = self.finish(
                email="zetacontinuation@gmail.com", subject="configured-google-subject"
            )
            self.assertEqual(allowed.status_code, 303)
            self.assertEqual(allowed.headers["location"], "/")
            self.assertIn("sigma_session", allowed.cookies)
            self.assertIn('sigma_denied="";', allowed.headers["set-cookie"])
            self.client.cookies.set("sigma_session", allowed.cookies["sigma_session"])
            account = self.client.get("/api/cloud-auth/status").json()
            self.assertTrue(account["authenticated"])
            self.assertEqual(
                account["user"], {"email": "zetacontinuation@gmail.com", "role": "admin"}
            )
            self.assertFalse(account["account"]["invitation_welcome_pending"])
            self.assertEqual(account["admin_contact_email"], "zetacontinuation@gmail.com")
            self.assertEqual(self.client.get("/api/cloud-auth/admin/grants").status_code, 200)

    def test_local_uninvited_google_user_requests_invitation_and_becomes_member(self):
        local_origin = "http://127.0.0.1:5173"
        with patch.dict(
            os.environ,
            {
                "SIGMA_CLOUD_AUTH_LOCAL": "true",
                "SIGMA_CLOUD_PUBLIC_ORIGIN": local_origin,
                "SIGMA_CLOUD_ADMIN_CONTACT_EMAIL": "admin@example.org",
            },
        ):
            admin_login = self.finish(email="admin@example.org", subject="onboard-admin")
            self.client.cookies.set("sigma_session", admin_login.cookies["sigma_session"])
            guest_context = TestClient(
                app, base_url="http://127.0.0.1", client=("127.0.0.1", 12346)
            )
            guest = guest_context.__enter__()
            self.addCleanup(guest_context.__exit__, None, None, None)
            signed_in = self.finish(
                email="new-member@example.org", subject="onboard-member", client=guest
            )
            self.assertEqual(signed_in.status_code, 303)
            self.assertEqual(signed_in.headers["location"], "/")
            guest.cookies.set("sigma_session", signed_in.cookies["sigma_session"])
            status = guest.get("/api/cloud-auth/status").json()
            self.assertTrue(status["authenticated"])
            self.assertEqual(status["user"], {"email": "new-member@example.org", "role": "guest"})
            self.assertEqual(status["account"]["access"]["status"], "uninvited")
            self.assertFalse(status["account"]["sponsorship"]["eligible"])
            self.assertEqual(guest.get("/api/projects/recent").status_code, 200)
            self.assertEqual(
                guest.post(
                    "/api/projects/research-sessions/start",
                    headers={"Origin": local_origin},
                    json={},
                ).status_code,
                403,
            )
            with patch.object(cloud_auth, "_deliver_invitation") as deliver:
                requested = guest.post(
                    "/api/cloud-auth/invitation-request", headers={"Origin": local_origin}
                )
                self.assertEqual(requested.status_code, 200, requested.text)
                self.assertEqual(requested.json()["status"], "notified")
                self.assertTrue(
                    guest.post(
                        "/api/cloud-auth/invitation-request", headers={"Origin": local_origin}
                    ).json()["duplicate"]
                )
                deliver.assert_called_once()
            admin_restart = TestClient(
                app, base_url="http://127.0.0.1", client=("127.0.0.1", 12347)
            )
            self.addCleanup(admin_restart.close)
            admin_restart.cookies.set("sigma_session", admin_login.cookies["sigma_session"])
            queue = admin_restart.get("/api/cloud-auth/admin/invitation-requests").json()[
                "requests"
            ]
            self.assertEqual(queue[0]["email"], "new-member@example.org")
            approved = admin_restart.post(
                "/api/cloud-auth/admin/grants",
                json={
                    "kind": "email",
                    "value": "new-member@example.org",
                    "role": "member",
                    "allowance_usd": 0.75,
                },
                headers={"Origin": local_origin},
            )
            self.assertEqual(approved.status_code, 200, approved.text)
            # The existing guest session becomes an authorized member without
            # another OAuth callback. Its first member status read must still
            # queue the one-time welcome dialog.
            promoted = guest.get("/api/cloud-auth/status").json()
            self.assertEqual(
                promoted["user"], {"email": "new-member@example.org", "role": "member"}
            )
            self.assertTrue(promoted["account"]["invitation_welcome_pending"])
            dismissed = guest.post("/api/cloud-auth/welcome", headers={"Origin": local_origin})
            self.assertEqual(dismissed.status_code, 200, dismissed.text)
            signed_in_again = self.finish(
                email="new-member@example.org", subject="onboard-member", client=guest
            )
            self.assertEqual(signed_in_again.status_code, 303)
            guest.cookies.set("sigma_session", signed_in_again.cookies["sigma_session"])
            member = guest.get("/api/cloud-auth/status").json()
            self.assertEqual(member["user"]["role"], "member")
            self.assertFalse(member["account"]["invitation_welcome_pending"])
            self.assertTrue(member["account"]["sponsorship"]["eligible"])
            self.assertIsNone(member["account"].get("invitation_status"))
            allowance = guest.get("/api/cloud-auth/local-sponsored-allowance")
            self.assertEqual(allowance.status_code, 200, allowance.text)
            self.assertEqual(allowance.json()["allowance_usd"], 0.75)

    def test_guest_project_api_allowlist_denies_every_other_registered_operation(self):
        local_origin = "http://127.0.0.1:5173"
        projects_root = Path(self.temp.name) / "projects"
        workspaces_root = Path(self.temp.name) / "workspaces"
        projects_root.mkdir()
        workspaces_root.mkdir()
        with patch.dict(
            os.environ,
            {
                "SIGMA_CLOUD_AUTH_LOCAL": "true",
                "SIGMA_CLOUD_PUBLIC_ORIGIN": local_origin,
                "SIGMA_CLOUD_ADMIN_CONTACT_EMAIL": "admin@example.org",
                "SIGMA_PROJECTS_ROOT": str(projects_root),
                "SIGMA_CLOUD_WORKSPACES_ROOT": str(workspaces_root),
            },
        ):
            admin_login = self.finish(email="admin@example.org", subject="route-admin")
            self.client.cookies.set("sigma_session", admin_login.cookies["sigma_session"])
            member_project = self.client.post(
                "/api/projects/create",
                json={
                    "title": f"Private route audit project {time.time_ns()}",
                    "problem": "A private member project used to check guest scoping.",
                    "research_mode": "default",
                },
                headers={"Origin": local_origin},
            )
            self.assertEqual(member_project.status_code, 201, member_project.text)
            member_path = member_project.json()["path"]
            member_project_before = self.client.get(
                "/api/projects/inspect", params={"path": member_path}
            ).json()

            guest_context = TestClient(
                app, base_url="http://127.0.0.1", client=("127.0.0.1", 12348)
            )
            guest = guest_context.__enter__()
            self.addCleanup(guest_context.__exit__, None, None, None)
            guest_login = self.finish(
                email="route-guest@example.org", subject="route-guest", client=guest
            )
            guest.cookies.set("sigma_session", guest_login.cookies["sigma_session"])
            catalog = guest.get("/api/projects/samples")
            self.assertEqual(catalog.status_code, 200, catalog.text)
            sample_id = catalog.json()["projects"][0]["id"]
            copied = guest.post(
                "/api/projects/samples/open",
                json={"sample_id": sample_id},
                headers={"Origin": local_origin},
            )
            self.assertEqual(copied.status_code, 200, copied.text)
            guest_path = copied.json()["path"]
            self.assertEqual(
                guest.get("/api/projects/inspect", params={"path": guest_path}).status_code, 200
            )
            from sigma import cloud_workspaces, project_bundle

            guest_workspace = cloud_workspaces.guest_workspace(
                guest.cookies.get(
                    cloud_auth._cookie_name(cloud_auth.GUEST_COOKIE, cloud_auth.config())
                ),
                subject="route-guest",
            )
            self.assertIsNotNone(guest_workspace)
            assert guest_workspace is not None
            self.assertTrue(Path(guest_path).is_relative_to(guest_workspace.path))

            def write_project_member(relative: str, contents: bytes) -> None:
                project = Path(guest_path)
                if project.is_dir():
                    target = project / relative
                    target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                    target.write_bytes(contents)
                else:
                    project_bundle.write_file(guest_path, relative, contents)

            # Populate valid owner-scoped session/execution artifacts in the
            # guest's own project bundle so the allowlisted read handlers are
            # exercised successfully, not just inferred from the middleware.
            project_id = copied.json()["project"]["id"]
            session_id = str(uuid4())
            session = {
                "id": session_id,
                "project_path": str(Path(guest_path).resolve()),
                "project_id": project_id,
                "session_number": 1,
                "status": "ended",
                "message": "isolated fixture session",
                "steps": [],
            }
            write_project_member(
                f"research-sessions/{session_id}.json", json.dumps(session).encode()
            )
            execution_id = str(uuid4())
            artifact_bytes = b"guest-owned artifact"
            execution = {
                "id": execution_id,
                "project_id": project_id,
                "status": "completed",
                "created_at": cloud_auth._now(),
                "artifacts": [
                    {
                        "filename": "owned.txt",
                        "media_type": "text/plain",
                        "size_bytes": len(artifact_bytes),
                        "sha256": hashlib.sha256(artifact_bytes).hexdigest(),
                    }
                ],
            }
            write_project_member(
                f"research-executions/{execution_id}.json", json.dumps(execution).encode()
            )
            write_project_member(
                f"research-executions/{execution_id}.artifacts/owned.txt", artifact_bytes
            )
            project_read = guest.get("/api/projects/inspect", params={"path": guest_path})
            self.assertEqual(project_read.status_code, 200, project_read.text)
            session_read = guest.get(
                f"/api/projects/research-sessions/{session_id}", params={"path": guest_path}
            )
            self.assertEqual(session_read.status_code, 200, session_read.text)
            artifact_read = guest.get(
                f"/api/projects/research-executions/{execution_id}/artifacts/owned.txt",
                params={"path": guest_path},
            )
            self.assertEqual(artifact_read.status_code, 200, artifact_read.text)
            self.assertEqual(artifact_read.content, artifact_bytes)
            for response in (project_read, session_read, artifact_read):
                self.assertEqual(response.headers.get("cache-control"), "no-store")
                self.assertEqual(response.headers.get("referrer-policy"), "no-referrer")
                self.assertEqual(response.headers.get("x-content-type-options"), "nosniff")
                self.assertEqual(
                    response.headers.get("content-security-policy"), "frame-ancestors 'none'"
                )
            for route in (
                "events",
                "research-limits",
                "current-understanding",
                "research-sessions",
                "research-executions",
                "papers",
                "papers/preflight",
                "papers/progress",
                "proposals/config",
                "text",
                "recent",
            ):
                response = guest.get(
                    f"/api/projects/{route}",
                    params={"path": guest_path, "scope": "project"},
                )
                self.assertEqual(response.status_code, 200, (route, response.text))

            paper_id = uuid4().hex
            pdf_bytes = b"%PDF-1.4 guest fixture"
            paper_record = {
                "paper_id": paper_id,
                "project_id": project_id,
                "created_at": cloud_auth._now(),
                "snapshot_sha256": "0" * 64,
                "validation_warnings": [],
                "generation": {},
                "draft": {
                    "title": "Guest-owned paper",
                    "abstract": "Fixture abstract.",
                    "problem_framing": [],
                    "methods": [],
                    "sections": [],
                    "claims": [],
                    "limitations": [],
                    "open_obligations": [],
                    "conclusions": [],
                },
                "tex_source": r"\documentclass{article}",
                "pdf_sha256": hashlib.sha256(pdf_bytes).hexdigest(),
                "pdf_size_bytes": len(pdf_bytes),
            }
            paper_prefix = "papers" if Path(guest_path).is_dir() else "artifacts/papers"
            write_project_member(
                f"{paper_prefix}/{paper_id}.json", json.dumps(paper_record).encode()
            )
            write_project_member(f"{paper_prefix}/{paper_id}.pdf", pdf_bytes)
            paper_reads = (
                guest.get("/api/projects/papers", params={"path": guest_path}),
                guest.get(f"/api/projects/papers/{paper_id}", params={"path": guest_path}),
                guest.get(f"/api/projects/papers/{paper_id}/pdf", params={"path": guest_path}),
                guest.get(f"/api/projects/papers/{paper_id}/txt", params={"path": guest_path}),
                guest.get(f"/api/projects/papers/{paper_id}/tex", params={"path": guest_path}),
            )
            self.assertTrue(
                all(response.status_code == 200 for response in paper_reads),
                [(response.status_code, response.text[:160]) for response in paper_reads],
            )
            self.assertEqual(paper_reads[2].content, pdf_bytes)
            self.assertIn("Guest-owned paper", paper_reads[3].text)
            self.assertIn(r"\documentclass{article}", paper_reads[4].text)
            self.assertTrue(
                all(response.headers.get("cache-control") == "no-store" for response in paper_reads)
            )
            self.assertEqual(
                guest.get("/api/projects/strategies", params={"path": guest_path}).status_code,
                200,
            )
            from sigma import research_sessions

            with patch.object(
                research_sessions,
                "ensure_queued_workers",
                side_effect=AssertionError("guest read attempted queued provider work"),
            ):
                sessions = guest.get("/api/projects/research-sessions", params={"path": guest_path})
            self.assertEqual(sessions.status_code, 200, sessions.text)
            with patch(
                "sigma.proposals.models",
                side_effect=AssertionError("guest config attempted provider discovery"),
            ):
                config = guest.get("/api/projects/proposals/config", params={"path": guest_path})
            self.assertEqual(config.status_code, 200, config.text)
            self.assertFalse(config.json()["available"])

            # Direct API requests to member-owned paths are scoped to the
            # guest workspace and return the same not-found response as absent
            # guest data. This avoids leaking whether member data exists.
            for route in (
                "inspect",
                "strategies",
                "events",
                "research-limits",
                "research-sessions",
                "current-understanding",
                "research-executions",
                "papers",
                "papers/preflight",
                "papers/progress",
            ):
                response = guest.get(f"/api/projects/{route}", params={"path": member_path})
                self.assertEqual(response.status_code, 404, (route, response.text))
            text_response = guest.get(
                "/api/projects/text", params={"path": member_path, "scope": "conclusions"}
            )
            self.assertEqual(text_response.status_code, 404, text_response.text)
            for route in (
                "research-sessions/audit-probe",
                "research-executions/audit-probe",
                "research-executions/audit-probe/artifacts/audit-probe",
                "papers/audit-probe",
                "papers/audit-probe/pdf",
                "papers/audit-probe/txt",
                "papers/audit-probe/tex",
            ):
                response = guest.get(f"/api/projects/{route}", params={"path": member_path})
                self.assertIn(response.status_code, {400, 404}, (route, response.text))
            self.assertEqual(
                guest.post(
                    "/api/projects/open",
                    json={"path": member_path},
                    headers={"Origin": local_origin},
                ).status_code,
                404,
            )
            self.assertEqual(
                guest.post(
                    "/api/projects/update",
                    json={"path": member_path, "title": "Overwritten"},
                    headers={"Origin": local_origin},
                ).status_code,
                403,
            )
            for route in (
                "/api/projects/audit",
                "/api/projects/export",
                "/api/projects/download",
                "/api/projects/export/report",
            ):
                self.assertEqual(
                    guest.get(route, params={"path": guest_path}).status_code,
                    403,
                    route,
                )
            member_project_after = self.client.get(
                "/api/projects/inspect", params={"path": member_path}
            ).json()
            self.assertEqual(member_project_after, member_project_before)

            # The route inventory is an enforcement test: future project
            # endpoints are denied unless their exact method/path is added to
            # the reviewed guest-safe allowlist.
            protected_count = 0
            allowed_routes = set()
            for route in app.routes:
                route_path = getattr(route, "path", "")
                if not route_path.startswith("/api/projects/"):
                    continue
                for method in getattr(route, "methods", set()) - {"HEAD", "OPTIONS"}:
                    concrete_path = re.sub(r"\{[^}]+\}", "audit-probe", route_path)
                    if cloud_auth._guest_project_route_allowed(method, concrete_path):
                        allowed_routes.add((method, route_path))
                        continue
                    response = guest.request(
                        method,
                        concrete_path,
                        params={"path": member_path},
                        json={} if method in {"POST", "PUT", "PATCH", "DELETE"} else None,
                        headers={"Origin": local_origin},
                    )
                    self.assertEqual(
                        response.status_code,
                        403,
                        (method, route_path, response.status_code, response.text),
                    )
                    protected_count += 1
            self.assertGreater(protected_count, 30)
            expected_guest_routes = {
                ("GET", path)
                for path in cloud_auth._GUEST_PROJECT_READ_PATHS | {"/api/projects/samples"}
            } | {
                ("GET", "/api/projects/research-sessions/{session_id}"),
                ("GET", "/api/projects/research-executions/{execution_id}"),
                (
                    "GET",
                    "/api/projects/research-executions/{execution_id}/artifacts/{filename}",
                ),
                ("GET", "/api/projects/papers/{paper_id}"),
                ("GET", "/api/projects/papers/{paper_id}/pdf"),
                ("GET", "/api/projects/papers/{paper_id}/txt"),
                ("GET", "/api/projects/papers/{paper_id}/tex"),
                ("POST", "/api/projects/samples/open"),
                ("POST", "/api/projects/open"),
                ("POST", "/api/projects/close"),
            }
            self.assertEqual(allowed_routes, expected_guest_routes)
            self.assertEqual(
                guest.get("/api/cloud-auth/local-sponsored-allowance").status_code, 403
            )
            self.assertEqual(guest.get("/api/ai/connection").status_code, 403)
            for admin_route in (
                "/api/cloud-auth/admin/invitation-requests",
                "/api/cloud-auth/admin/grants",
                "/api/cloud-auth/admin/feedback",
            ):
                self.assertEqual(guest.get(admin_route).status_code, 403, admin_route)

    def test_local_admin_pill_request_routes_selected_sponsor_to_sponsor_oauth(self):
        from sigma import ai_store

        local_origin = "http://127.0.0.1:5173"
        sponsor_home = Path(self.temp.name) / "sponsor-auth"
        with patch.dict(
            os.environ,
            {
                "SIGMA_CLOUD_AUTH_LOCAL": "true",
                "SIGMA_CLOUD_PUBLIC_ORIGIN": local_origin,
                "SIGMA_CLOUD_ADMIN_CONTACT_EMAIL": "zetacontinuation@gmail.com",
                "SIGMA_AUTH_HOME": str(sponsor_home),
            },
        ):
            os.environ.pop("SIGMA_CLOUD_SPONSOR_EMAIL", None)
            login = self.finish(
                email="zetacontinuation@gmail.com", subject="configured-google-admin"
            )
            self.assertEqual(login.status_code, 303)
            self.client.cookies.update(login.cookies)
            status = self.client.get("/api/cloud-auth/status").json()
            self.assertEqual(status["user"]["role"], "admin")
            self.assertEqual(status["user"]["email"], "zetacontinuation@gmail.com")
            self.assertEqual(status["account"]["model_access"]["mode"], "sponsored")

            # A pre-existing cookie whose legacy personal value was never
            # deliberately selected must still resolve to default sponsorship.
            with cloud_auth._db(cloud_auth.config()) as db:
                db.execute(
                    "UPDATE user_state SET model_access='personal',model_access_selected=0 "
                    "WHERE subject='configured-google-admin'"
                )
            status = self.client.get("/api/cloud-auth/status").json()
            self.assertEqual(status["account"]["model_access"]["mode"], "sponsored")

            self.seed_personal_plan_authorization("configured-google-admin")
            cloud_auth.set_model_access("configured-google-admin", "personal")
            status = self.client.get("/api/cloud-auth/status").json()
            self.assertEqual(status["account"]["model_access"]["mode"], "personal")

            async def add_selected_sponsor():
                async with ai_store.sponsor_transaction() as state:
                    state["accounts"]["selected-sponsor"] = {
                        "email": "zetacontinuation@gmail.com",
                        "access_token": "existing-sponsor-token",
                    }
                    state["active"] = "selected-sponsor"

            import asyncio

            asyncio.run(add_selected_sponsor())
            with patch(
                "sigma.api.chatgpt_auth.begin",
                new=AsyncMock(return_value={"id": "sponsor-attempt"}),
            ) as begin:
                response = self.client.post(
                    "/api/ai/sponsor-auth/begin", json={}, headers={"Origin": local_origin}
                )
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()["id"], "sponsor-attempt")
            begin.assert_awaited_once_with(account_id="selected-sponsor", sponsor=True)

            grant = self.client.post(
                "/api/cloud-auth/admin/grants",
                json={
                    "kind": "email",
                    "value": "nontrivialzeeros@gmail.com",
                    "role": "member",
                    "allowance_usd": 1,
                },
                headers={"Origin": local_origin},
            )
            self.assertEqual(grant.status_code, 200, grant.text)
            member_context = TestClient(
                app, base_url="http://127.0.0.1", client=("127.0.0.1", 23457)
            )
            member = member_context.__enter__()
            self.addCleanup(member_context.__exit__, None, None, None)
            member_login = self.finish(
                email="nontrivialzeeros@gmail.com",
                subject="sponsor-change-denied-member",
                client=member,
            )
            self.assertEqual(member_login.status_code, 303)
            member.cookies.update(member_login.cookies)
            with patch(
                "sigma.api.chatgpt_auth.begin",
                new=AsyncMock(return_value={"id": "member-personal-attempt"}),
            ) as member_begin:
                personal = member.post(
                    "/api/ai/auth/begin", json={}, headers={"Origin": local_origin}
                )
                sponsor_route_denied = member.post(
                    "/api/ai/sponsor-auth/begin", json={}, headers={"Origin": local_origin}
                )
            self.assertEqual(personal.status_code, 200, personal.text)
            member_begin.assert_awaited_once_with(None, False, None)
            self.assertEqual(sponsor_route_denied.status_code, 403, sponsor_route_denied.text)

            async def saved_sponsor_token():
                async with ai_store.sponsor_transaction() as state:
                    return state["accounts"]["selected-sponsor"]["access_token"]

            self.assertEqual(asyncio.run(saved_sponsor_token()), "existing-sponsor-token")

    def test_local_admin_sponsored_mode_transition_uses_bounded_global_pilot(self):
        from sigma import ai_store, chatgpt_auth

        local_origin = "http://127.0.0.1:5173"
        with patch.dict(
            os.environ,
            {
                "SIGMA_CLOUD_AUTH_LOCAL": "true",
                "SIGMA_CLOUD_PUBLIC_ORIGIN": local_origin,
                "SIGMA_CLOUD_ADMIN_CONTACT_EMAIL": "zetacontinuation@gmail.com",
                "SIGMA_AUTH_HOME": str(Path(self.temp.name) / "sponsor-auth"),
            },
        ):
            os.environ.pop("SIGMA_CLOUD_SPONSOR_EMAIL", None)
            os.environ.pop("SIGMA_CLOUD_GLOBAL_SPEND_CEILING_USD", None)
            login = self.finish(email="zetacontinuation@gmail.com", subject="mode-transition-admin")
            self.client.cookies.update(login.cookies)
            self.assertEqual(
                self.client.get("/api/cloud-auth/status").json()["account"]["model_access"]["mode"],
                "sponsored",
            )
            with patch(
                "sigma.api.chatgpt_auth.discovery",
                AsyncMock(
                    return_value={"authorization_endpoint": "https://auth.openai.com/authorize"}
                ),
            ):
                started = self.client.post(
                    "/api/ai/auth/begin", json={}, headers={"Origin": local_origin}
                )
                self.assertEqual(started.status_code, 200, started.text)
                cancelled = self.client.post(
                    f"/api/ai/auth/cancel/{started.json()['id']}",
                    json={},
                    headers={"Origin": local_origin},
                )
            self.assertEqual(cancelled.status_code, 200, cancelled.text)
            self.assertEqual(
                self.client.get("/api/cloud-auth/status").json()["account"]["model_access"]["mode"],
                "sponsored",
            )
            headers = {"Origin": local_origin}
            fabricated = self.client.post(
                "/api/ai/mode", json={"mode": "personal"}, headers=headers
            )
            self.assertEqual(fabricated.status_code, 403, fabricated.text)
            self.assertEqual(
                self.client.get("/api/cloud-auth/status").json()["account"]["model_access"]["mode"],
                "sponsored",
            )
            with cloud_auth._db(cloud_auth.config()) as db:
                db.execute(
                    "UPDATE user_state SET model_access='personal',model_access_selected=1 "
                    "WHERE subject='mode-transition-admin'"
                )
            legacy_selected = self.client.post(
                "/api/ai/mode", json={"mode": "personal"}, headers=headers
            )
            self.assertEqual(legacy_selected.status_code, 403, legacy_selected.text)
            self.assertEqual(
                self.client.get("/api/cloud-auth/status").json()["account"]["model_access"]["mode"],
                "personal",
                "legacy preference remains truthful without becoming authorization proof",
            )
            with cloud_auth._db(cloud_auth.config()) as db:
                db.execute(
                    "UPDATE user_state SET model_access='sponsored',model_access_selected=0 "
                    "WHERE subject='mode-transition-admin'"
                )
            self.seed_personal_plan_authorization(
                "mode-transition-admin", record_authorization=False
            )
            credential_path = (
                ai_store.personal_directory_for_subject("mode-transition-admin")
                / "credentials.json"
            )
            credential_state = ai_store.read(credential_path)
            credential = credential_state["accounts"]["fixture-personal"]
            credential["scopes"] = ["resource.invoke"]
            credential["plan_authorized"] = False
            ai_store.write(credential_path, credential_state)
            missing_plan_scope = self.client.post(
                "/api/ai/mode", json={"mode": "personal"}, headers=headers
            )
            self.assertEqual(missing_plan_scope.status_code, 403, missing_plan_scope.text)
            self.assertEqual(
                self.client.get("/api/cloud-auth/status").json()["account"]["model_access"]["mode"],
                "sponsored",
            )
            credential["scopes"] = list(chatgpt_auth.PLAN_SCOPES)
            credential["plan_authorized"] = True
            ai_store.write(credential_path, credential_state)
            cloud_auth.record_personal_authorization("mode-transition-admin")
            switched_personal = self.client.post(
                "/api/ai/mode", json={"mode": "personal"}, headers=headers
            )
            self.assertEqual(switched_personal.status_code, 200, switched_personal.text)

            from sigma import cloud_research

            # Funding mode selection remains possible even when allowance
            # inspection is unavailable; Play admission checks the ledger.
            with patch.object(
                cloud_research,
                "snapshot",
                side_effect=cloud_research.CloudResearchUnavailable("fixture ledger unavailable"),
            ) as snapshot:
                selected = self.client.post(
                    "/api/ai/mode",
                    json={"mode": "sponsored"},
                    headers={"Origin": local_origin},
                )
            self.assertEqual(selected.status_code, 200, selected.text)
            snapshot.assert_not_called()
            self.assertEqual(
                self.client.get("/api/cloud-auth/status").json()["account"]["model_access"]["mode"],
                "sponsored",
            )

            selected = self.client.post(
                "/api/ai/mode",
                json={"mode": "sponsored"},
                headers={"Origin": local_origin},
            )
            self.assertEqual(selected.status_code, 200, selected.text)
            self.assertEqual(
                self.client.get("/api/cloud-auth/status").json()["account"]["model_access"]["mode"],
                "sponsored",
            )
            budget = self.client.get("/api/cloud-auth/local-sponsored-allowance")
            self.assertEqual(budget.status_code, 200, budget.text)
            self.assertEqual(budget.json()["global_ceiling_usd"], 50.0)
            self.assertEqual(budget.json()["global_spend_period"], "calendar_month")

    def test_local_admin_connection_reports_validated_sponsor_identity(self):
        import asyncio
        import time

        from sigma import ai_store, chatgpt_auth, openai_connection

        local_origin = "http://127.0.0.1:5173"
        with patch.dict(
            os.environ,
            {
                "SIGMA_CLOUD_AUTH_LOCAL": "true",
                "SIGMA_CLOUD_PUBLIC_ORIGIN": local_origin,
                "SIGMA_CLOUD_ADMIN_CONTACT_EMAIL": "zetacontinuation@gmail.com",
                "SIGMA_AUTH_HOME": str(Path(self.temp.name) / "sponsor-auth"),
            },
        ):
            os.environ.pop("SIGMA_CLOUD_SPONSOR_EMAIL", None)
            login = self.finish(
                email="zetacontinuation@gmail.com", subject="connection-identity-admin"
            )
            self.client.cookies.update(login.cookies)
            self.assertEqual(
                self.client.get("/api/cloud-auth/status").json()["account"]["model_access"]["mode"],
                "sponsored",
            )

            async def persist_oauth_credentials():
                async with ai_store.sponsor_transaction() as state:
                    state["accounts"]["completed-oauth"] = {
                        "client_id": "fixture-oauth-client",
                        "email": "zetacontinuation@gmail.com",
                        "access_token": "validated-sponsor-access-token",
                        "refresh_token": "validated-sponsor-refresh-token",
                        "expires_at": time.time() + 3600,
                        "scopes": list(chatgpt_auth.PLAN_SCOPES),
                    }
                    state["active"] = "completed-oauth"

            asyncio.run(persist_oauth_credentials())

            async def validated_catalog(*_args, **_kwargs):
                result = {
                    "status": "connected",
                    "checked_at": "2026-10-28T00:00:00Z",
                    "ttl_seconds": 60,
                }
                return result

            with patch.object(
                openai_connection, "_check", AsyncMock(side_effect=validated_catalog)
            ):
                response = self.client.get("/api/ai/connection?refresh=true")
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()["status"], "connected")
            self.assertEqual(response.json()["account_label"], "zetacontinuation@gmail.com")
            self.assertNotIn("validated-sponsor-access-token", response.text)
            self.assertNotIn("validated-sponsor-refresh-token", response.text)

            grant = self.client.post(
                "/api/cloud-auth/admin/grants",
                json={
                    "kind": "email",
                    "value": "nontrivialzeeros@gmail.com",
                    "role": "member",
                    "allowance_usd": 1,
                },
                headers={"Origin": local_origin},
            )
            self.assertEqual(grant.status_code, 200, grant.text)
            member_context = TestClient(
                app, base_url="http://127.0.0.1", client=("127.0.0.1", 23458)
            )
            member = member_context.__enter__()
            self.addCleanup(member_context.__exit__, None, None, None)
            member_login = self.finish(
                email="nontrivialzeeros@gmail.com",
                subject="sponsor-identity-hidden-member",
                client=member,
            )
            self.assertEqual(member_login.status_code, 303)
            member.cookies.update(member_login.cookies)
            self.assertEqual(
                member.get("/api/cloud-auth/status").json()["account"]["model_access"]["mode"],
                "sponsored",
            )
            with patch.object(
                openai_connection, "_check", AsyncMock(side_effect=validated_catalog)
            ):
                member_response = member.get("/api/ai/connection?refresh=true")
                mode_response = member.post(
                    "/api/ai/mode",
                    json={"mode": "sponsored"},
                    headers={"Origin": local_origin},
                )
            self.assertEqual(member_response.status_code, 200, member_response.text)
            self.assertEqual(member_response.json()["status"], "connected")
            self.assertNotIn("account_label", member_response.json())
            self.assertNotIn("zetacontinuation@gmail.com", member_response.text)
            self.assertEqual(mode_response.status_code, 200, mode_response.text)
            self.assertNotIn("zetacontinuation@gmail.com", mode_response.text)

    def test_personal_disconnect_cannot_cancel_other_users_or_sponsor_oauth_attempts(self):
        from sigma import chatgpt_auth

        local_origin = "http://127.0.0.1:5173"
        b_client = TestClient(app, base_url="http://127.0.0.1", client=("127.0.0.1", 23461))
        self.addCleanup(b_client.close)
        with patch.dict(
            os.environ,
            {
                "SIGMA_CLOUD_AUTH_LOCAL": "true",
                "SIGMA_CLOUD_PUBLIC_ORIGIN": local_origin,
                "SIGMA_CLOUD_ADMIN_CONTACT_EMAIL": "zetacontinuation@gmail.com",
                "SIGMA_CLOUD_AUTH_HOME": str(Path(self.temp.name) / "auth-db"),
                "SIGMA_AUTH_HOME": str(Path(self.temp.name) / "auth-home"),
            },
        ):
            os.environ.pop("SIGMA_CLOUD_SPONSOR_EMAIL", None)
            with cloud_auth._db(cloud_auth.config()) as db:
                db.execute(
                    "INSERT INTO grants(kind,value,role,active,updated_at) VALUES('email',?,'admin',1,?)",
                    ("brian.kramer.personal@gmail.com", cloud_auth._now()),
                )
            z_login = self.finish(email="zetacontinuation@gmail.com", subject="attempt-owner-z")
            b_login = self.finish(
                email="brian.kramer.personal@gmail.com",
                subject="attempt-owner-b",
                client=b_client,
            )
            self.assertEqual(z_login.status_code, 303)
            self.assertEqual(b_login.status_code, 303)
            self.client.cookies.update(z_login.cookies)
            b_client.cookies.update(b_login.cookies)
            headers = {"Origin": local_origin}
            endpoint = "https://auth.openai.com/authorize"
            with patch.object(
                chatgpt_auth,
                "discovery",
                AsyncMock(return_value={"authorization_endpoint": endpoint}),
            ):
                z_personal = self.client.post("/api/ai/auth/begin", json={}, headers=headers)
                self.assertEqual(z_personal.status_code, 200, z_personal.text)
                z_sponsor = self.client.post("/api/ai/sponsor-auth/begin", json={}, headers=headers)
                self.assertEqual(z_sponsor.status_code, 200, z_sponsor.text)
                personal_id = z_personal.json()["id"]
                sponsor_id = z_sponsor.json()["id"]

                # B disconnects B's own personal store while both Z flows are
                # pending. Neither pending flow may be cancelled as a side effect.
                disconnected = b_client.post("/api/ai/disconnect", json={}, headers=headers)
                self.assertEqual(disconnected.status_code, 200, disconnected.text)
                for attempt_id in (personal_id, sponsor_id):
                    self.assertEqual(
                        self.client.get(f"/api/ai/auth/attempt/{attempt_id}").json()["status"],
                        "connecting",
                    )
                    self.assertEqual(
                        b_client.get(f"/api/ai/auth/attempt/{attempt_id}").status_code, 400
                    )
                    self.assertEqual(
                        b_client.post(
                            f"/api/ai/auth/cancel/{attempt_id}", json={}, headers=headers
                        ).status_code,
                        400,
                    )

                # A failed attempt can be retried only by its owner, against
                # the same personal/sponsor store in which it began.
                for attempt_id in (personal_id, sponsor_id):
                    attempt = chatgpt_auth._attempts[attempt_id]
                    chatgpt_auth.finish(attempt, "failed", "Fixture failure.")
                    attempt.retry_client_id = "fixture-client"
                    self.assertEqual(
                        b_client.post(
                            "/api/ai/auth/begin",
                            json={"retry_attempt_id": attempt_id},
                            headers=headers,
                        ).status_code,
                        400,
                    )
                self.assertEqual(
                    self.client.post(
                        "/api/ai/auth/begin",
                        json={"retry_attempt_id": sponsor_id},
                        headers=headers,
                    ).status_code,
                    400,
                    "a personal OAuth retry must not consume a sponsor-store attempt ID",
                )

    def test_local_existing_cookie_keeps_same_email_personal_and_sponsor_credentials_separate(self):
        import asyncio
        import time
        from urllib.parse import parse_qs, urlencode, urlsplit

        from sigma import ai_store, chatgpt_auth, openai_connection

        local_origin = "http://127.0.0.1:5173"
        sponsor_token = "shared-sponsor-access"
        personal_token = "z-personal-access"
        observed_tokens: list[str] = []

        async def checked_catalog(access_token, mode="chatgpt"):
            observed_tokens.append(access_token)
            return {
                "status": "connected",
                "checked_at": "2026-10-28T00:00:00Z",
                "ttl_seconds": 60,
            }

        with patch.dict(
            os.environ,
            {
                "SIGMA_CLOUD_AUTH_LOCAL": "true",
                "SIGMA_CLOUD_PUBLIC_ORIGIN": local_origin,
                "SIGMA_CLOUD_ADMIN_CONTACT_EMAIL": "zetacontinuation@gmail.com",
                "SIGMA_AUTH_HOME": str(Path(self.temp.name) / "sponsor-auth"),
            },
        ):
            os.environ.pop("SIGMA_CLOUD_SPONSOR_EMAIL", None)
            login = self.finish(
                email="zetacontinuation@gmail.com", subject="same-email-personal-owner"
            )
            self.assertEqual(login.status_code, 303)
            self.client.cookies.update(login.cookies)
            self.assertEqual(
                self.client.get("/api/cloud-auth/status").json()["account"]["model_access"]["mode"],
                "sponsored",
            )

            async def seed_shared_sponsor():
                async with ai_store.sponsor_transaction() as state:
                    state["accounts"]["shared-sponsor"] = {
                        "client_id": "oaiapp_fixture",
                        "subject": "same-chatgpt-subject",
                        "email": "zetacontinuation@gmail.com",
                        "access_token": sponsor_token,
                        "refresh_token": "shared-sponsor-refresh",
                        "expires_at": time.time() + 3600,
                        "scopes": list(chatgpt_auth.PLAN_SCOPES),
                    }
                    state["active"] = "shared-sponsor"

            asyncio.run(seed_shared_sponsor())
            rejected_before_oauth = self.client.post(
                "/api/ai/mode",
                json={"mode": "personal"},
                headers={"Origin": local_origin},
            )
            self.assertEqual(rejected_before_oauth.status_code, 403, rejected_before_oauth.text)
            cookie_name = cloud_auth._cookie_name(cloud_auth.SESSION_COOKIE, cloud_auth.config())
            cookie = self.client.cookies.get(cookie_name)

            # Reopen a fresh client using the existing cookie and durable auth
            # home; sponsored default survives before OAuth succeeds.
            restart_context = TestClient(
                app, base_url="http://127.0.0.1", client=("127.0.0.1", 23459)
            )
            restarted = restart_context.__enter__()
            self.addCleanup(restart_context.__exit__, None, None, None)
            restarted.cookies.set(cookie_name, cookie)
            status = restarted.get("/api/cloud-auth/status")
            self.assertEqual(status.status_code, 200, status.text)
            self.assertEqual(status.json()["account"]["model_access"]["mode"], "sponsored")
            with patch.object(
                openai_connection,
                "_check",
                AsyncMock(side_effect=checked_catalog),
            ):
                initial_connection = restarted.get("/api/ai/connection")
            self.assertEqual(initial_connection.status_code, 200, initial_connection.text)
            self.assertEqual(initial_connection.json()["status"], "connected")
            self.assertEqual(
                initial_connection.json().get("account_label"), "zetacontinuation@gmail.com"
            )
            self.assertIn(sponsor_token, observed_tokens)

            token_record = {
                "client_id": "oaiapp_fixture",
                "subject": "same-chatgpt-subject",
                "email": "zetacontinuation@gmail.com",
                "name": "Z Personal",
                "access_token": personal_token,
                "refresh_token": "z-personal-refresh",
                "expires_at": time.time() + 3600,
                "scopes": list(chatgpt_auth.PLAN_SCOPES),
            }
            with (
                patch.object(
                    chatgpt_auth,
                    "discovery",
                    AsyncMock(
                        return_value={"authorization_endpoint": "https://auth.openai.com/authorize"}
                    ),
                ),
                patch.object(
                    chatgpt_auth,
                    "http",
                    AsyncMock(return_value=(200, {"access_token": "exchanged-code"})),
                ) as exchange,
                patch.object(
                    chatgpt_auth, "validate_tokens", AsyncMock(return_value=token_record)
                ) as validate,
            ):
                started = restarted.post(
                    "/api/ai/auth/begin", json={}, headers={"Origin": local_origin}
                )
                self.assertEqual(started.status_code, 200, started.text)
                attempt_id = started.json()["id"]
                open_url = restarted.get(f"/api/ai/auth/open/{attempt_id}", follow_redirects=False)
                self.assertEqual(open_url.status_code, 307, open_url.text)
                authorization_url = urlsplit(open_url.headers["location"])
                self.assertEqual(authorization_url.hostname, "auth.openai.com")
                authorization = parse_qs(authorization_url.query)
                redirect_uri = urlsplit(authorization["redirect_uri"][0])
                callback_query = urlencode(
                    {
                        "state": authorization["state"][0],
                        "code": "fixture-oauth-code",
                        "client_id": "oaiapp_fixture",
                    }
                )

                async def complete_loopback_oauth():
                    port = redirect_uri.port
                    assert port is not None
                    reader, writer = await asyncio.open_connection("127.0.0.1", port)
                    writer.write(
                        (
                            f"GET {redirect_uri.path}?{callback_query} HTTP/1.1\r\n"
                            f"Host: {redirect_uri.netloc}\r\n\r\n"
                        ).encode()
                    )
                    await writer.drain()
                    response = await reader.read(4096)
                    writer.close()
                    await writer.wait_closed()
                    return response

                callback_response = asyncio.run(complete_loopback_oauth())
                self.assertIn(b"HTTP/1.1 200 OK", callback_response)
                exchange.assert_awaited_once()
                validate.assert_awaited_once()
            oauth_status = restarted.get(f"/api/ai/auth/attempt/{attempt_id}")
            for _ in range(100):
                oauth_status = restarted.get(f"/api/ai/auth/attempt/{attempt_id}")
                if oauth_status.json()["status"] != "connecting":
                    break
                time.sleep(0.01)
            self.assertEqual(oauth_status.json()["status"], "connected")
            self.assertEqual(
                restarted.get("/api/cloud-auth/status").json()["account"]["model_access"]["mode"],
                "sponsored",
                "successful OAuth alone must not switch funding mode",
            )

            with patch.object(openai_connection, "_check", AsyncMock(side_effect=checked_catalog)):
                personal_mode = restarted.post(
                    "/api/ai/mode", json={"mode": "personal"}, headers={"Origin": local_origin}
                )
            self.assertEqual(personal_mode.status_code, 200, personal_mode.text)
            self.assertEqual(
                restarted.get("/api/cloud-auth/status").json()["account"]["model_access"]["mode"],
                "personal",
            )
            with patch.object(openai_connection, "_check", AsyncMock(side_effect=checked_catalog)):
                personal = restarted.get("/api/ai/connection?refresh=true")
            self.assertEqual(personal.status_code, 200, personal.text)
            self.assertEqual(personal.json()["status"], "connected")
            self.assertEqual(personal.json()["account_label"], "zetacontinuation@gmail.com")
            self.assertEqual(observed_tokens[-1], personal_token)
            personal_account_id = personal.json()["active_account"]
            reauthorize = restarted.post(
                "/api/ai/auth/begin",
                json={"account_id": personal_account_id},
                headers={"Origin": local_origin},
            )
            self.assertEqual(reauthorize.status_code, 200, reauthorize.text)
            restarted.post(
                f"/api/ai/auth/cancel/{reauthorize.json()['id']}",
                json={},
                headers={"Origin": local_origin},
            )

            with patch.object(openai_connection, "_check", AsyncMock(side_effect=checked_catalog)):
                sponsored_mode = restarted.post(
                    "/api/ai/mode",
                    json={"mode": "sponsored"},
                    headers={"Origin": local_origin},
                )
            self.assertEqual(sponsored_mode.status_code, 200, sponsored_mode.text)
            self.assertEqual(
                restarted.get("/api/cloud-auth/status").json()["account"]["model_access"]["mode"],
                "sponsored",
            )
            with patch.object(openai_connection, "_check", AsyncMock(side_effect=checked_catalog)):
                sponsor_connection = restarted.get("/api/ai/connection?refresh=true")
            self.assertEqual(sponsor_connection.status_code, 200, sponsor_connection.text)
            self.assertEqual(sponsor_connection.json()["status"], "connected")
            self.assertEqual(
                sponsor_connection.json()["account_label"], "zetacontinuation@gmail.com"
            )
            self.assertIn(sponsor_token, observed_tokens)

            with patch.object(openai_connection, "_check", AsyncMock(side_effect=checked_catalog)):
                personal_mode = restarted.post(
                    "/api/ai/mode", json={"mode": "personal"}, headers={"Origin": local_origin}
                )
            self.assertEqual(personal_mode.status_code, 200, personal_mode.text)
            with (
                patch.object(
                    chatgpt_auth,
                    "discovery",
                    AsyncMock(
                        return_value={"revocation_endpoint": "https://auth.openai.com/revoke"}
                    ),
                ),
                patch.object(chatgpt_auth, "http", AsyncMock(return_value=(200, {}))) as revoke,
            ):
                disconnected = restarted.post(
                    "/api/ai/disconnect", json={}, headers={"Origin": local_origin}
                )
            self.assertEqual(disconnected.status_code, 200, disconnected.text)
            self.assertTrue(revoke.await_count <= 1)
            disconnected_personal = restarted.get("/api/ai/connection?refresh=true")
            self.assertIn(
                disconnected_personal.json()["status"], {"reauth_required", "disconnected"}
            )
            with patch.object(openai_connection, "_check", AsyncMock(side_effect=checked_catalog)):
                returned_to_sponsor = restarted.post(
                    "/api/ai/mode",
                    json={"mode": "sponsored"},
                    headers={"Origin": local_origin},
                )
            self.assertEqual(returned_to_sponsor.status_code, 200, returned_to_sponsor.text)
            with patch.object(openai_connection, "_check", AsyncMock(side_effect=checked_catalog)):
                sponsor_after_personal_disconnect = restarted.get("/api/ai/connection?refresh=true")
            self.assertEqual(sponsor_after_personal_disconnect.json()["status"], "connected")
            self.assertIn(sponsor_token, observed_tokens)

            async def sponsor_store_token():
                async with ai_store.sponsor_transaction() as state:
                    return state["accounts"]["shared-sponsor"]["access_token"]

            self.assertEqual(asyncio.run(sponsor_store_token()), sponsor_token)

    def test_local_z_and_b_admins_have_unlimited_and_n_has_metered_sponsorship(self):
        local_origin = "http://127.0.0.1:5173"
        with patch.dict(
            os.environ,
            {
                "SIGMA_CLOUD_AUTH_LOCAL": "true",
                "SIGMA_CLOUD_PUBLIC_ORIGIN": local_origin,
                "SIGMA_CLOUD_ADMIN_CONTACT_EMAIL": "zetacontinuation@gmail.com",
                "SIGMA_AUTH_HOME": str(Path(self.temp.name) / "allowance-sponsor-auth"),
            },
        ):
            z_login = self.finish(email="zetacontinuation@gmail.com", subject="allowance-z-admin")
            self.client.cookies.update(z_login.cookies)
            for email, role, allowance in (
                ("brian.kramer.personal@gmail.com", "admin", None),
                ("nontrivialzeeros@gmail.com", "member", 0.05),
            ):
                response = self.client.post(
                    "/api/cloud-auth/admin/grants",
                    json={
                        "kind": "email",
                        "value": email,
                        "role": role,
                        "allowance_usd": allowance,
                    },
                    headers={"Origin": local_origin},
                )
                self.assertEqual(response.status_code, 200, response.text)

            self.assertEqual(
                self.client.get("/api/cloud-auth/status").json()["user"]["role"], "admin"
            )
            z_budget = self.client.get("/api/cloud-auth/local-sponsored-allowance")
            self.assertEqual(z_budget.status_code, 200, z_budget.text)
            self.assertEqual(z_budget.json()["allowance_usd"], 15.0)

            for email, subject, expected_role, expected_allowance in (
                ("brian.kramer.personal@gmail.com", "allowance-b-admin", "admin", 15.0),
                ("nontrivialzeeros@gmail.com", "allowance-n-member", "member", 0.05),
            ):
                context = TestClient(
                    app,
                    base_url="http://127.0.0.1",
                    client=("127.0.0.1", 23460 if expected_role == "admin" else 23461),
                )
                client = context.__enter__()
                self.addCleanup(context.__exit__, None, None, None)
                login = self.finish(email=email, subject=subject, client=client)
                self.assertEqual(login.status_code, 303)
                client.cookies.update(login.cookies)
                status = client.get("/api/cloud-auth/status")
                self.assertEqual(status.json()["user"]["role"], expected_role)
                self.assertEqual(status.json()["account"]["model_access"]["mode"], "sponsored")
                budget = client.get("/api/cloud-auth/local-sponsored-allowance")
                self.assertEqual(budget.status_code, 200, budget.text)
                self.assertEqual(budget.json()["allowance_usd"], expected_allowance)

                if expected_role == "admin":
                    # A new Google identity can only select personal after its
                    # own isolated registration has plan permission.
                    unconnected = client.post(
                        "/api/ai/mode",
                        json={"mode": "personal"},
                        headers={"Origin": local_origin},
                    )
                    self.assertEqual(unconnected.status_code, 403, unconnected.text)
                    self.assertEqual(
                        client.get("/api/cloud-auth/status").json()["account"]["model_access"][
                            "mode"
                        ],
                        "sponsored",
                    )
                    self.seed_personal_plan_authorization(subject, "zetacontinuation@gmail.com")
                    with patch(
                        "sigma.openai_connection._check",
                        new=AsyncMock(
                            return_value={
                                "status": "connected",
                                "checked_at": "fixture",
                                "ttl_seconds": 60,
                            }
                        ),
                    ):
                        personal = client.post(
                            "/api/ai/mode",
                            json={"mode": "personal"},
                            headers={"Origin": local_origin},
                        )
                        self.assertEqual(personal.status_code, 200, personal.text)
                        connection = client.get("/api/ai/connection")
                    self.assertEqual(connection.json()["status"], "connected")
                    self.assertEqual(
                        connection.json().get("account_label"), "zetacontinuation@gmail.com"
                    )

    def test_denied_identity_is_retained_only_for_request_and_other_account_resets_it(self):
        denied = self.finish(email="visitor@example.org")
        self.assertEqual(denied.status_code, 303)
        self.assertEqual(denied.headers["location"], "/?access=denied")
        self.assertNotIn(cloud_auth.SESSION_COOKIE, denied.cookies)
        self.assertFalse((self.root / "workspaces").exists())
        denied_token = denied.cookies[cloud_auth.DENIED_COOKIE]
        self.assertIn("HttpOnly", denied.headers["set-cookie"])
        self.assertIn("Secure", denied.headers["set-cookie"])
        self.client.cookies.set(cloud_auth.DENIED_COOKIE, denied_token)
        self.assertEqual(
            self.client.get("/api/cloud-auth/denied").json(),
            {"identity_available": True, "invitation_status": None},
        )
        self.assertEqual(self.client.get("/api/cloud-auth/status").json()["authenticated"], False)
        with patch.object(cloud_auth, "_deliver_invitation"):
            requested = self.client.post(
                "/api/cloud-auth/invitation-request", headers={"Origin": ORIGIN}
            )
        self.assertEqual(requested.status_code, 200)
        self.assertEqual(
            self.client.get("/api/cloud-auth/denied").json()["invitation_status"], "notified"
        )
        public_demo = self.client.get("/api/cloud-demo/")
        self.assertEqual(public_demo.status_code, 200)
        self.assertEqual(public_demo.json()["project"]["title"], "Counting Pairwise Handshakes")
        self.assertEqual(
            self.client.get(
                "/api/projects/research-sessions", params={"path": str(self.project_path)}
            ).status_code,
            401,
        )
        restart = self.client.get("/api/cloud-auth/login", follow_redirects=False)
        self.assertEqual(
            parse_qs(urlsplit(restart.headers["location"]).query)["prompt"], ["select_account"]
        )
        self.assertIn('__Host-sigma_denied="";', restart.headers["set-cookie"])
        self.assertEqual(self.client.get("/api/cloud-auth/denied").status_code, 404)
        self.assertEqual(self.client.get("/api/projects/recent").status_code, 401)
        self.assertNotIn(cloud_auth.SESSION_COOKIE, restart.cookies)
        with cloud_auth._db(cloud_auth.config()) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM sessions").fetchone()[0], 0)

    def test_account_switch_authorized_to_unauthorized_invalidates_session(self):
        first = self.finish()
        first_raw = first.cookies[cloud_auth.SESSION_COOKIE]
        self.client.cookies.set(cloud_auth.SESSION_COOKIE, first_raw)
        self.assertEqual(self.client.get("/api/cloud-auth/admin/grants").status_code, 200)

        begin = self.client.get("/api/cloud-auth/login", follow_redirects=False)
        self.assertIn('__Host-sigma_session="";', begin.headers["set-cookie"])
        self.assertIn("Max-Age=0", begin.headers["set-cookie"])
        self.assertIsNone(cloud_auth.resolve_session(first_raw))
        with cloud_auth._db(cloud_auth.config()) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM sessions").fetchone()[0], 0)
        self.assertEqual(self.client.get("/api/cloud-auth/admin/grants").status_code, 401)
        self.assertEqual(self.client.get("/api/projects/recent").status_code, 401)

        denied = self.finish("visitor@example.org", "visitor-sub")
        self.assertEqual(denied.status_code, 303)
        self.assertNotIn(cloud_auth.SESSION_COOKIE, denied.cookies)
        self.assertIn('__Host-sigma_session="";', denied.headers["set-cookie"])
        self.assertIsNone(cloud_auth.resolve_session(first_raw))
        self.assertEqual(self.client.get("/api/projects/recent").status_code, 401)
        self.assertEqual(self.client.get("/api/cloud-auth/admin/grants").status_code, 401)

    def test_account_switch_authorized_to_authorized_replaces_session(self):
        first = self.finish()
        first_raw = first.cookies[cloud_auth.SESSION_COOKIE]
        self.client.cookies.set(cloud_auth.SESSION_COOKIE, first_raw)
        self.assertEqual(
            self.client.post(
                "/api/cloud-auth/admin/grants",
                json={"kind": "email", "value": "member@example.org", "role": "member"},
                headers={"Origin": ORIGIN},
            ).status_code,
            200,
        )
        begin = self.client.get("/api/cloud-auth/login", follow_redirects=False)
        self.assertIn('__Host-sigma_session="";', begin.headers["set-cookie"])
        self.assertIsNone(cloud_auth.resolve_session(first_raw))
        self.assertEqual(self.client.get("/api/projects/recent").status_code, 401)

        second = self.finish("member@example.org", "member-sub")
        second_raw = second.cookies[cloud_auth.SESSION_COOKIE]
        principal = cloud_auth.resolve_session(second_raw)
        assert principal is not None
        self.assertEqual(principal.email, "member@example.org")
        self.assertIsNone(cloud_auth.resolve_session(first_raw))
        self.client.cookies.set(cloud_auth.SESSION_COOKIE, second_raw)
        self.assertEqual(
            self.client.get("/api/cloud-auth/status").json()["user"]["email"], "member@example.org"
        )
        self.assertNotEqual(self.client.get("/api/projects/recent").status_code, 401)
        with cloud_auth._db(cloud_auth.config()) as db:
            rows = db.execute("SELECT email FROM sessions").fetchall()
            self.assertEqual([row["email"] for row in rows], ["member@example.org"])

    def test_local_mode_keeps_project_and_provider_apis_unauthenticated(self):
        local_project = self.root / "local-project.sigma"
        initialize_project(local_project, "Local test", "Test local API access")
        with patch.dict(os.environ, {"SIGMA_CLOUD_AUTH_ENABLED": "false"}):
            self.assertEqual(self.client.get("/api/cloud-auth/status").json()["enabled"], False)
            self.assertNotEqual(
                self.client.get(
                    "/api/projects/research-sessions", params={"path": str(local_project)}
                ).status_code,
                401,
            )
            self.assertNotEqual(self.client.get("/api/ai/connection").status_code, 401)

    def test_hosted_google_auth_still_blocks_personal_chatgpt_auth(self):
        signed_in = self.finish()
        self.client.cookies.set(
            cloud_auth.SESSION_COOKIE, signed_in.cookies[cloud_auth.SESSION_COOKIE]
        )
        response = self.client.post("/api/ai/auth/begin", headers={"Origin": ORIGIN}, json={})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.json()["error"],
            "AI provider authorization is unavailable in cloud mode.",
        )

    def test_hosted_default_and_explicit_sponsored_selection_match_provider_routing(self):
        import asyncio

        from sigma import ai_store, chatgpt_auth, openai_connection

        with patch.dict(
            os.environ,
            {
                "SIGMA_CLOUD_AUTH_LOCAL": "false",
                "SIGMA_CLOUD_SPONSOR_EMAIL": "admin@example.org",
                "SIGMA_CLOUD_CHATGPT_AUTH_HOME": str(Path(self.temp.name) / "hosted-sponsor"),
            },
        ):
            signed_in = self.finish()
            self.client.cookies.set(
                cloud_auth.SESSION_COOKIE, signed_in.cookies[cloud_auth.SESSION_COOKIE]
            )
            initial = self.client.get("/api/cloud-auth/status")
            self.assertEqual(initial.status_code, 200, initial.text)
            self.assertEqual(initial.json()["account"]["model_access"]["mode"], "sponsored")

            account = {
                "client_id": "fixture-chatgpt-client",
                "subject": "hosted-sponsor-subject",
                "email": "admin@example.org",
                "issuer": chatgpt_auth.ISSUER,
                "access_token": "hosted-sponsor-token",
                "refresh_token": "hosted-sponsor-refresh",
                "id_token": "hosted-sponsor-id",
                "token_type": "Bearer",
                "scopes": list(chatgpt_auth.PLAN_SCOPES),
                "expires_at": time.time() + 3600,
            }

            async def save_sponsor():
                async with ai_store.sponsor_transaction() as state:
                    state["accounts"] = {"hosted-sponsor": account}
                    state["active"] = "hosted-sponsor"

            asyncio.run(save_sponsor())
            provider_keys = []

            async def validated_provider(key, mode):
                provider_keys.append((key, mode))
                return openai_connection._CatalogResult(
                    {"status": "connected", "checked_at": "fixture", "ttl_seconds": 60},
                    set(),
                    {},
                    [],
                )

            with patch.object(openai_connection, "_check", side_effect=validated_provider):
                first = self.client.get("/api/ai/connection?refresh=true")
                self.assertEqual(first.status_code, 200, first.text)
                self.assertEqual(first.json()["status"], "connected")
                self.assertEqual(provider_keys[-1], ("hosted-sponsor-token", "chatgpt"))

                personal = self.client.post(
                    "/api/ai/mode", json={"mode": "personal"}, headers={"Origin": ORIGIN}
                )
                self.assertEqual(personal.status_code, 403, personal.text)
                self.assertEqual(
                    self.client.get("/api/cloud-auth/status").json()["account"]["model_access"][
                        "mode"
                    ],
                    "sponsored",
                )
                self.assertEqual(
                    len(provider_keys), 1, "personal mode must not borrow sponsor credentials"
                )

                sponsored = self.client.post(
                    "/api/ai/mode", json={"mode": "sponsored"}, headers={"Origin": ORIGIN}
                )
                self.assertEqual(sponsored.status_code, 200, sponsored.text)
                self.assertEqual(sponsored.json()["status"], "connected")
                self.assertEqual(provider_keys[-1], ("hosted-sponsor-token", "chatgpt"))
                self.assertEqual(
                    self.client.get("/api/cloud-auth/status").json()["account"]["model_access"][
                        "mode"
                    ],
                    "sponsored",
                )

    def test_domain_approved_google_login_materializes_individual_member(self):
        admin_context = TestClient(app)
        admin = admin_context.__enter__()
        self.addCleanup(admin_context.__exit__, None, None, None)
        signed_admin = self.finish(
            email="admin@example.org", subject="auto-login-admin", client=admin
        )
        admin.cookies.set(
            cloud_auth.SESSION_COOKIE, signed_admin.cookies[cloud_auth.SESSION_COOKIE]
        )
        grant = admin.post(
            "/api/cloud-auth/admin/grants",
            json={
                "kind": "domain",
                "value": "example.org",
                "role": "member",
                "allowance_usd": 1.25,
            },
            headers={"Origin": ORIGIN},
        )
        self.assertEqual(grant.status_code, 200, grant.text)
        with patch.object(cloud_auth, "_deliver_invitation") as notify:
            member = self.finish("member@example.org", "auto-login-member")
        self.assertEqual(member.status_code, 303)
        self.assertIn(cloud_auth.SESSION_COOKIE, member.cookies)
        notify.assert_called_once()
        self.assertEqual(notify.call_args.kwargs["request_type"], "auto_approved")
        self.assertEqual(notify.call_args.args[0], "member@example.org")
        with cloud_auth._db(cloud_auth.config()) as db:
            row = db.execute(
                "SELECT role,active,allowance_usd FROM grants WHERE kind='email' AND value=?",
                ("member@example.org",),
            ).fetchone()
            notice = db.execute(
                "SELECT status FROM invitation_requests WHERE subject='auto-login-member'"
            ).fetchone()
        self.assertEqual((row["role"], row["active"], row["allowance_usd"]), ("member", 1, 1.25))
        self.assertEqual(notice["status"], "reviewed")
        listed = admin.get("/api/cloud-auth/admin/grants").json()
        self.assertTrue(
            any(
                account["email"] == "member@example.org" and account["authorized"]
                for account in listed["sessions"]
            )
        )
        self.assertFalse(
            any(
                req["email"] == "member@example.org"
                for req in admin.get("/api/cloud-auth/admin/invitation-requests").json()["requests"]
            )
        )
        revoked = admin.delete(
            "/api/cloud-auth/admin/grants/domain/example.org", headers={"Origin": ORIGIN}
        )
        self.assertEqual(revoked.status_code, 200)
        # Revoking the domain policy blocks future automatic invites, but
        # already-materialized individual members remain independently active.
        current_member = cloud_auth.resolve_session(member.cookies[cloud_auth.SESSION_COOKIE])
        assert current_member is not None
        self.assertEqual(current_member.role, "member")

    def test_domain_granted_after_denied_signin_approves_invite_me_immediately(self):
        admin_context = TestClient(app)
        admin = admin_context.__enter__()
        self.addCleanup(admin_context.__exit__, None, None, None)
        signed_admin = self.finish(
            email="admin@example.org", subject="auto-request-admin", client=admin
        )
        admin.cookies.set(
            cloud_auth.SESSION_COOKIE, signed_admin.cookies[cloud_auth.SESSION_COOKIE]
        )
        denied = self.finish("later@example.org", "auto-request-member")
        self.assertIn(cloud_auth.DENIED_COOKIE, denied.cookies)
        self.client.cookies.set(cloud_auth.DENIED_COOKIE, denied.cookies[cloud_auth.DENIED_COOKIE])
        rule = admin.post(
            "/api/cloud-auth/admin/grants",
            json={"kind": "domain", "value": "example.org", "role": "member"},
            headers={"Origin": ORIGIN},
        )
        self.assertEqual(rule.status_code, 200)
        with patch.object(cloud_auth, "_deliver_invitation") as notify:
            approved = self.client.post(
                "/api/cloud-auth/invitation-request",
                json={"email": "forged@elsewhere.org"},
                headers={"Origin": ORIGIN},
            )
        self.assertEqual(approved.status_code, 200, approved.text)
        self.assertEqual(approved.json(), {"status": "approved", "duplicate": False})
        notify.assert_called_once()
        self.assertEqual(notify.call_args.kwargs["request_type"], "auto_approved")
        token = approved.cookies[cloud_auth.SESSION_COOKIE]
        active_member = cloud_auth.resolve_session(token)
        assert active_member is not None
        self.assertEqual(active_member.email, "later@example.org")
        with cloud_auth._db(cloud_auth.config()) as db:
            saved = db.execute(
                "SELECT role,active FROM grants WHERE kind='email' AND value='later@example.org'"
            ).fetchone()
            notice = db.execute(
                "SELECT status FROM invitation_requests WHERE subject='auto-request-member'"
            ).fetchone()
        self.assertEqual((saved["role"], saved["active"]), ("member", 1))
        self.assertEqual(notice["status"], "reviewed")
        # A parallel tab that still carries the original denied identity
        # receives the existing approval; it must not re-open the request.
        second_context = TestClient(app)
        second = second_context.__enter__()
        self.addCleanup(second_context.__exit__, None, None, None)
        second.cookies.set(cloud_auth.DENIED_COOKIE, denied.cookies[cloud_auth.DENIED_COOKIE])
        with patch.object(cloud_auth, "_deliver_invitation") as race_mail:
            race_result = second.post(
                "/api/cloud-auth/invitation-request", headers={"Origin": ORIGIN}
            )
        self.assertEqual(race_result.status_code, 200, race_result.text)
        self.assertEqual(race_result.json(), {"status": "approved", "duplicate": True})
        race_mail.assert_not_called()
        self.client.cookies.set(cloud_auth.SESSION_COOKIE, token)
        with patch.object(cloud_auth, "_deliver_invitation") as duplicate_mail:
            repeated = self.client.post(
                "/api/cloud-auth/invitation-request", headers={"Origin": ORIGIN}
            )
        self.assertEqual(repeated.status_code, 200)
        self.assertEqual(repeated.json(), {"status": "approved", "duplicate": True})
        duplicate_mail.assert_not_called()

    def test_domain_auto_member_survives_email_failure_but_revoked_domain_blocks_new_users(self):
        admin_context = TestClient(app)
        admin = admin_context.__enter__()
        self.addCleanup(admin_context.__exit__, None, None, None)
        signed_admin = self.finish(
            email="admin@example.org", subject="auto-failure-admin", client=admin
        )
        admin.cookies.set(
            cloud_auth.SESSION_COOKIE, signed_admin.cookies[cloud_auth.SESSION_COOKIE]
        )
        added = admin.post(
            "/api/cloud-auth/admin/grants",
            json={"kind": "domain", "value": "example.org", "role": "member"},
            headers={"Origin": ORIGIN},
        )
        self.assertEqual(added.status_code, 200)
        with patch.object(
            cloud_auth, "_deliver_invitation", side_effect=RuntimeError("mail offline")
        ):
            signed = self.finish("new@example.org", "auto-failure-member")
        self.assertIn(cloud_auth.SESSION_COOKIE, signed.cookies)
        with cloud_auth._db(cloud_auth.config()) as db:
            row = db.execute(
                "SELECT status,notification_error FROM invitation_requests "
                "WHERE subject='auto-failure-member'"
            ).fetchone()
            grant = db.execute(
                "SELECT role,active FROM grants WHERE kind='email' AND value='new@example.org'"
            ).fetchone()
        self.assertEqual(
            (row["status"], row["notification_error"]), ("reviewed", "delivery failed")
        )
        self.assertEqual((grant["role"], grant["active"]), ("member", 1))
        revoked = admin.delete(
            "/api/cloud-auth/admin/grants/domain/example.org",
            headers={"Origin": ORIGIN},
        )
        self.assertEqual(revoked.status_code, 200)
        later = self.finish("later@example.org", "auto-failure-new")
        self.assertIn(cloud_auth.DENIED_COOKIE, later.cookies)
        self.assertNotIn(cloud_auth.SESSION_COOKIE, later.cookies)
        existing = cloud_auth.resolve_session(signed.cookies[cloud_auth.SESSION_COOKIE])
        assert existing is not None
        self.assertEqual(existing.role, "member")

    def test_explicit_user_revocation_prevents_domain_auto_member(self):
        admin_context = TestClient(app)
        admin = admin_context.__enter__()
        self.addCleanup(admin_context.__exit__, None, None, None)
        signed_admin = self.finish(
            email="admin@example.org", subject="auto-deny-admin", client=admin
        )
        admin.cookies.set(
            cloud_auth.SESSION_COOKIE, signed_admin.cookies[cloud_auth.SESSION_COOKIE]
        )
        admin.post(
            "/api/cloud-auth/admin/grants",
            json={"kind": "domain", "value": "example.org", "role": "member"},
            headers={"Origin": ORIGIN},
        )
        with cloud_auth._db(cloud_auth.config()) as db:
            db.execute(
                "INSERT INTO grants(kind,value,role,active,updated_at) "
                "VALUES('email','blocked@example.org','member',0,?)",
                (cloud_auth._now(),),
            )
        denied = self.finish("blocked@example.org", "auto-blocked-member")
        self.assertIn(cloud_auth.DENIED_COOKIE, denied.cookies)
        self.client.cookies.set(cloud_auth.DENIED_COOKIE, denied.cookies[cloud_auth.DENIED_COOKIE])
        with patch.object(cloud_auth, "_deliver_invitation") as mail:
            requested = self.client.post(
                "/api/cloud-auth/invitation-request", headers={"Origin": ORIGIN}
            )
        self.assertEqual(requested.status_code, 200)
        self.assertNotEqual(requested.json()["status"], "approved")
        self.assertEqual(mail.call_args.kwargs.get("request_type", "invitation"), "invitation")
        with cloud_auth._db(cloud_auth.config()) as db:
            row = db.execute(
                "SELECT active FROM grants WHERE kind='email' AND value='blocked@example.org'"
            ).fetchone()
        self.assertEqual(row["active"], 0)

    def test_exact_domain_and_revocation_of_existing_session(self):
        admin_context = TestClient(app)
        admin_client = admin_context.__enter__()
        self.addCleanup(admin_context.__exit__, None, None, None)
        admin = self.finish(client=admin_client)
        admin_client.cookies.set(
            cloud_auth.SESSION_COOKIE, admin.cookies[cloud_auth.SESSION_COOKIE]
        )
        invited = admin_client.post(
            "/api/cloud-auth/admin/grants",
            json={"kind": "email", "value": "person@outside.org", "role": "member"},
            headers={"Origin": ORIGIN},
        )
        self.assertEqual(invited.status_code, 200)
        person = self.finish("person@outside.org", "person-sub")
        self.assertEqual(person.status_code, 303)
        person_cookie = person.cookies[cloud_auth.SESSION_COOKIE]
        person_principal = cloud_auth.resolve_session(person_cookie)
        assert person_principal is not None
        self.assertEqual(person_principal.email, "person@outside.org")
        self.assertEqual(
            admin_client.delete(
                "/api/cloud-auth/admin/grants/email/person%40outside.org",
                headers={"Origin": ORIGIN},
            ).status_code,
            200,
        )
        self.assertIsNone(cloud_auth.resolve_session(person_cookie))
        denied = self.finish("person@outside.org", "person-sub")
        self.assertEqual(denied.status_code, 303)
        self.assertNotIn(cloud_auth.SESSION_COOKIE, denied.cookies)
        self.assertIn("access=denied", denied.headers["location"])
        self.assertIn(cloud_auth.FLOW_COOKIE, denied.headers["set-cookie"])
        self.assertIn("Max-Age=0", denied.headers["set-cookie"])
        rule = admin_client.post(
            "/api/cloud-auth/admin/grants",
            json={"kind": "domain", "value": "Example.org"},
            headers={"Origin": ORIGIN},
        )
        self.assertEqual(rule.status_code, 200)
        member = self.finish("member@example.org", "member-sub")
        member_cookie = member.cookies[cloud_auth.SESSION_COOKIE]
        member_principal = cloud_auth.resolve_session(member_cookie)
        assert member_principal is not None
        self.assertEqual(member_principal.email, "member@example.org")
        self.client.cookies.set(cloud_auth.SESSION_COOKIE, member_cookie)
        self.assertEqual(self.client.get("/api/cloud-auth/admin/grants").status_code, 403)
        self.assertEqual(
            admin_client.delete(
                "/api/cloud-auth/admin/grants/email/member%40example.org",
                headers={"Origin": ORIGIN},
            ).status_code,
            200,
        )
        self.assertIsNone(
            cloud_auth.resolve_session(member_cookie)
        )  # Explicit deny beats allowed domain.
        lookalike = self.finish("member@notexample.org", "lookalike-sub")
        self.assertNotIn(cloud_auth.SESSION_COOKIE, lookalike.cookies)
        removed = admin_client.delete(
            "/api/cloud-auth/admin/grants/domain/example.org", headers={"Origin": ORIGIN}
        )
        self.assertEqual(removed.status_code, 200)
        self.assertIsNone(cloud_auth.resolve_session(member_cookie))
        accounts = admin_client.get("/api/cloud-auth/admin/grants").json()["sessions"]
        revoked = next(item for item in accounts if item["email"] == "member@example.org")
        self.assertEqual(revoked["status"], "revoked")
        self.assertFalse(revoked["authorized"])
        self.assertIn("held_usd", revoked["spending"])

    def test_nontrivialzeeros_domain_login_and_reload_request(self):
        admin_login = self.finish()
        self.assertEqual(admin_login.status_code, 303)
        self.client.cookies.set(
            cloud_auth.SESSION_COOKIE, admin_login.cookies[cloud_auth.SESSION_COOKIE]
        )
        grant = self.client.post(
            "/api/cloud-auth/admin/grants",
            json={
                "kind": "domain",
                "value": "nontrivialzeeros.com",
                "role": "member",
                "allowance_usd": 1.25,
            },
            headers={"Origin": ORIGIN},
        )
        self.assertEqual(grant.status_code, 200, grant.text)
        user_context = TestClient(app)
        user = user_context.__enter__()
        self.addCleanup(user_context.__exit__, None, None, None)
        login = self.finish(
            email="tester@nontrivialzeeros.com",
            subject="nontrivialzeeros-test-account",
            client=user,
        )
        self.assertEqual(login.status_code, 303)
        user.cookies.set(cloud_auth.SESSION_COOKIE, login.cookies[cloud_auth.SESSION_COOKIE])
        user_status = user.get("/api/cloud-auth/status").json()
        self.assertTrue(user_status["authenticated"])
        self.assertTrue(user_status["account"]["sponsorship"]["eligible"])
        self.assertEqual(user_status["account"]["access"]["role"], "member")
        with patch.object(cloud_auth, "_deliver_invitation") as deliver:
            reload_request = user.post(
                "/api/cloud-auth/invitation-request",
                json={"request_type": "reload"},
                headers={"Origin": ORIGIN},
            )
        self.assertEqual(reload_request.status_code, 200, reload_request.text)
        deliver.assert_called_once()
        self.assertEqual(deliver.call_args.args[0], "tester@nontrivialzeeros.com")
        self.assertEqual(deliver.call_args.kwargs["request_type"], "reload")
        requests = self.client.get("/api/cloud-auth/admin/invitation-requests").json()["requests"]
        self.assertEqual(len(requests), 1)
        self.assertEqual(requests[0]["request_type"], "reload")
        self.assertEqual(requests[0]["email"], "tester@nontrivialzeeros.com")

    def test_spending_allowance_admin_policy_and_email_precedence(self):
        admin_context = TestClient(app)
        admin = admin_context.__enter__()
        self.addCleanup(admin_context.__exit__, None, None, None)
        admin_result = self.finish(client=admin)
        admin.cookies.set(
            cloud_auth.SESSION_COOKIE, admin_result.cookies[cloud_auth.SESSION_COOKIE]
        )
        domain = admin.post(
            "/api/cloud-auth/admin/grants",
            json={"kind": "domain", "value": "example.org", "allowance_usd": 5.0},
            headers={"Origin": ORIGIN},
        )
        self.assertEqual(domain.status_code, 200, domain.text)
        user_context = TestClient(app)
        user = user_context.__enter__()
        self.addCleanup(user_context.__exit__, None, None, None)
        signed = self.finish("member@example.org", "member-sub", client=user)
        self.assertEqual(signed.status_code, 303)
        self.assertEqual(cloud_auth.effective_spending_allowance("member@example.org", 2), 5.0)
        # Domain policy is resolved for each verified email; a specific entry
        # overrides it, including when that individual allowance is larger.
        personal = admin.post(
            "/api/cloud-auth/admin/grants",
            json={"kind": "email", "value": "member@example.org", "allowance_usd": 8.0},
            headers={"Origin": ORIGIN},
        )
        self.assertEqual(personal.status_code, 200, personal.text)
        self.assertEqual(cloud_auth.effective_spending_allowance("member@example.org", 2), 8.0)
        self.assertEqual(cloud_auth.effective_spending_allowance("other@example.org", 2), 5.0)
        lowered = admin.put(
            "/api/cloud-auth/admin/grants/email/member%40example.org/allowance",
            json={"allowance_usd": 0.5},
            headers={"Origin": ORIGIN},
        )
        self.assertEqual(lowered.status_code, 200, lowered.text)
        self.assertEqual(cloud_auth.effective_spending_allowance("member@example.org", 2), 0.5)
        overview = admin.get("/api/cloud-auth/admin/grants")
        self.assertEqual(overview.status_code, 200, overview.text)
        records = overview.json()
        administrator = next(
            item for item in records["sessions"] if item["email"] == "admin@example.org"
        )
        self.assertIsNone(administrator["allowance_usd"])
        self.assertIsNone(administrator["spending"]["remaining_usd"])
        self.assertEqual(
            admin.post(
                "/api/cloud-auth/invitation-request",
                json={"request_type": "reload"},
                headers={"Origin": ORIGIN},
            ).status_code,
            403,
        )
        member = next(item for item in records["sessions"] if item["email"] == "member@example.org")
        self.assertEqual(member["allowance_usd"], 0.5)
        self.assertIn("estimated_usage_usd", member["spending"])
        self.assertIn("held_usd", member["spending"])
        self.assertIn("remaining_usd", member["spending"])
        email_grant = next(
            item for item in records["grants"] if item["value"] == "member@example.org"
        )
        self.assertEqual(email_grant["effective_allowance_usd"], 0.5)
        self.assertEqual(email_grant["allowance_usd"], 0.5)

    def test_admin_can_reload_only_one_active_member_email_allowance(self):
        from types import SimpleNamespace

        admin_login = self.finish()
        self.client.cookies.set(
            cloud_auth.SESSION_COOKIE, admin_login.cookies[cloud_auth.SESSION_COOKIE]
        )
        grant = self.client.post(
            "/api/cloud-auth/admin/grants",
            json={"kind": "email", "value": "member@example.org", "allowance_usd": 1.25},
            headers={"Origin": ORIGIN},
        )
        self.assertEqual(grant.status_code, 200, grant.text)
        member_context = TestClient(app, base_url="http://127.0.0.1", client=("127.0.0.1", 12346))
        member = member_context.__enter__()
        self.addCleanup(member_context.__exit__, None, None, None)
        login = self.finish("member@example.org", "member-sub", client=member)
        member.cookies.set(cloud_auth.SESSION_COOKIE, login.cookies[cloud_auth.SESSION_COOKIE])
        with (
            patch(
                "sigma.cloud_workspaces.workspace_for_subject",
                return_value=SimpleNamespace(workspace_id="a" * 32),
            ),
            patch(
                "sigma.cloud_research.admin_reload_workspace_allowance",
                return_value="reload-time",
            ) as reload,
        ):
            response = self.client.post(
                "/api/cloud-auth/admin/grants/reload/member%40example.org",
                headers={"Origin": ORIGIN},
            )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(
            response.json(),
            {"email": "member@example.org", "allowance_usd": 1.25, "reset_at": "reload-time"},
        )
        reload.assert_called_once_with("a" * 32, "admin@example.org")
        denied = member.post(
            "/api/cloud-auth/admin/grants/reload/member%40example.org",
            headers={"Origin": ORIGIN},
        )
        self.assertEqual(denied.status_code, 403)

    def test_role_and_allowance_updates_are_atomic_and_domain_admin_is_rejected(self):
        admin_context = TestClient(app)
        admin = admin_context.__enter__()
        self.addCleanup(admin_context.__exit__, None, None, None)
        signed = self.finish(client=admin)
        admin.cookies.set(cloud_auth.SESSION_COOKIE, signed.cookies[cloud_auth.SESSION_COOKIE])
        for kind, value in (("email", "member@example.org"), ("domain", "example.org")):
            response = admin.post(
                "/api/cloud-auth/admin/grants",
                json={"kind": kind, "value": value, "allowance_usd": 2.0},
                headers={"Origin": ORIGIN},
            )
            self.assertEqual(response.status_code, 200, response.text)
        invalid = admin.put(
            "/api/cloud-auth/admin/grants/updates",
            json={
                "updates": [
                    {
                        "kind": "email",
                        "value": "member@example.org",
                        "role": "admin",
                        "allowance_usd": 4.0,
                    },
                    {
                        "kind": "domain",
                        "value": "example.org",
                        "role": "admin",
                        "allowance_usd": 5.0,
                    },
                ]
            },
            headers={"Origin": ORIGIN},
        )
        self.assertEqual(invalid.status_code, 422, invalid.text)
        snapshot = admin.get("/api/cloud-auth/admin/grants").json()["grants"]
        self.assertEqual(
            next(row for row in snapshot if row["value"] == "member@example.org")["role"], "member"
        )
        saved = admin.put(
            "/api/cloud-auth/admin/grants/updates",
            json={
                "updates": [
                    {
                        "kind": "email",
                        "value": "member@example.org",
                        "role": "admin",
                        "allowance_usd": 4.0,
                    },
                    {
                        "kind": "domain",
                        "value": "example.org",
                        "role": "member",
                        "allowance_usd": None,
                    },
                ]
            },
            headers={"Origin": ORIGIN},
        )
        self.assertEqual(saved.status_code, 200, saved.text)
        snapshot = admin.get("/api/cloud-auth/admin/grants").json()["grants"]
        self.assertEqual(
            next(row for row in snapshot if row["value"] == "member@example.org")["role"], "admin"
        )
        self.assertEqual(
            next(row for row in snapshot if row["value"] == "member@example.org")["allowance_usd"],
            4.0,
        )

    def test_explicit_local_google_mode_accepts_only_loopback_http_and_preserves_local_projects(
        self,
    ):
        local_origin = "http://127.0.0.1:5173"
        with patch.dict(
            os.environ,
            {
                "SIGMA_CLOUD_AUTH_LOCAL": "true",
                "SIGMA_CLOUD_PUBLIC_ORIGIN": local_origin,
                "OPENAI_API_KEY": "",
            },
        ):
            cfg = cloud_auth.config()
            self.assertTrue(cfg.local)
            self.assertIsNone(cfg.error)
            self.assertEqual(cfg.origin, local_origin)
            response = self.client.get("/api/cloud-auth/login", follow_redirects=False)
            self.assertEqual(response.status_code, 302)
            flow_name = "sigma_oidc_flow"
            self.assertIn(flow_name, response.cookies)
            self.assertNotIn("Secure", response.headers["set-cookie"])
            query = parse_qs(urlsplit(response.headers["location"]).query)
            state = query["state"][0]
            self.assertEqual(query["redirect_uri"], [local_origin + "/api/cloud-auth/callback"])
            with cloud_auth._db(cfg) as db:
                nonce = db.execute(
                    "SELECT nonce FROM flows WHERE state_hash=?", (cloud_auth._hash(state),)
                ).fetchone()["nonce"]
            GoogleClient.token = token(nonce=nonce)
            self.client.cookies.set(flow_name, response.cookies[flow_name])
            with patch.object(cloud_auth.httpx, "AsyncClient", GoogleClient):
                signed = self.client.get(
                    "/api/cloud-auth/callback",
                    params={"state": state, "code": "fixture"},
                    follow_redirects=False,
                )
            self.assertEqual(signed.status_code, 303, signed.text)
            self.assertIn("sigma_session", signed.cookies)
            self.assertNotIn("Secure", signed.headers["set-cookie"])
            self.client.cookies.set("sigma_session", signed.cookies["sigma_session"])
            status = self.client.get("/api/cloud-auth/status").json()
            self.assertEqual(status["target"], "local")
            self.assertEqual(status["user"]["role"], "admin")
            self.assertEqual(status["account"]["model_access"]["connection"], "checking")
            with patch(
                "sigma.api.connection",
                return_value={
                    "mode": "api_key",
                    "status": "unconfigured",
                    "label": "OpenAI API key is not configured",
                    "guidance": "No provider request was made.",
                    "checked_at": None,
                },
            ):
                provider_status = self.client.get("/api/ai/connection")
            self.assertEqual(provider_status.status_code, 200, provider_status.text)
            self.assertNotEqual(
                provider_status.json().get("guidance"),
                "AI provider authorization is unavailable in cloud mode.",
            )
            refreshed = self.client.get("/api/cloud-auth/status").json()
            self.assertEqual(refreshed["account"]["model_access"]["connection"], "unconfigured")
            self.assertFalse((self.root / "workspaces" / "workspaces.sqlite3").exists())
            self.assertEqual(self.client.get("/api/projects/recent").status_code, 200)
        with patch.dict(
            os.environ,
            {
                "SIGMA_CLOUD_AUTH_LOCAL": "true",
                "SIGMA_CLOUD_PUBLIC_ORIGIN": "http://remote.example:5173",
            },
        ):
            self.assertIsNotNone(cloud_auth.config().error)

    def test_local_explicitly_authorized_google_member_can_view_sponsored_allowance(self):
        local_origin = "http://127.0.0.1:5173"
        with patch.dict(
            os.environ,
            {
                "SIGMA_CLOUD_AUTH_LOCAL": "true",
                "SIGMA_CLOUD_PUBLIC_ORIGIN": local_origin,
            },
        ):
            admin_context = TestClient(app)
            admin = admin_context.__enter__()
            self.addCleanup(admin_context.__exit__, None, None, None)
            admin_login = self.finish(client=admin)
            self.assertEqual(admin_login.status_code, 303)
            admin.cookies.set("sigma_session", admin_login.cookies["sigma_session"])
            member_context = TestClient(app)
            member_client = member_context.__enter__()
            self.addCleanup(member_context.__exit__, None, None, None)
            denied = self.finish(
                email="nontrivialzeeros@gmail.com",
                subject="nontrivialzeeros-local-member",
                client=member_client,
            )
            self.assertEqual(denied.status_code, 303)
            self.assertEqual(denied.headers["location"], "/")
            self.assertIn("sigma_session", denied.cookies)
            member_client.cookies.set("sigma_session", denied.cookies["sigma_session"])
            guest_status = member_client.get("/api/cloud-auth/status").json()
            self.assertEqual(guest_status["user"]["role"], "guest")
            self.assertFalse(guest_status["account"]["sponsorship"]["eligible"])
            grant = admin.post(
                "/api/cloud-auth/admin/grants",
                json={"kind": "email", "value": "nontrivialzeeros@gmail.com", "role": "member"},
                headers={"Origin": local_origin},
            )
            self.assertEqual(grant.status_code, 200, grant.text)
            signed_member = self.finish(
                email="nontrivialzeeros@gmail.com",
                subject="nontrivialzeeros-local-member",
                client=member_client,
            )
            self.assertEqual(signed_member.status_code, 303)
            member_client.cookies.set("sigma_session", signed_member.cookies["sigma_session"])
            status = member_client.get("/api/cloud-auth/status").json()
            self.assertEqual(status["target"], "local")
            self.assertTrue(status["authenticated"])
            self.assertTrue(status["account"]["sponsorship"]["eligible"])

    def test_local_sponsored_flag_forces_eligible_google_account_and_reads_its_grant(self):
        local_origin = "http://127.0.0.1:5173"
        with patch.dict(
            os.environ,
            {
                "SIGMA_CLOUD_AUTH_LOCAL": "true",
                "SIGMA_CLOUD_PUBLIC_ORIGIN": local_origin,
                "SIGMA_LOCAL_SPONSORED_TEST_MODE": "1",
                "SIGMA_MOCK_AUTH": "0",
            },
        ):
            admin_login = self.finish()
            self.assertEqual(admin_login.status_code, 303)
            self.client.cookies.set("sigma_session", admin_login.cookies["sigma_session"])
            admin_status = self.client.get("/api/cloud-auth/status").json()
            self.assertEqual(admin_status["account"]["access"]["role"], "admin")
            self.assertTrue(admin_status["account"]["sponsorship"]["eligible"])
            self.assertEqual(admin_status["account"]["model_access"]["mode"], "sponsored")
            grant = self.client.post(
                "/api/cloud-auth/admin/grants",
                json={
                    "kind": "email",
                    "value": "local-sponsor@example.org",
                    "role": "member",
                    "allowance_usd": 1.25,
                },
                headers={"Origin": local_origin},
            )
            self.assertEqual(grant.status_code, 200, grant.text)
            member_context = TestClient(
                app, base_url="http://127.0.0.1", client=("127.0.0.1", 23456)
            )
            member = member_context.__enter__()
            self.addCleanup(member_context.__exit__, None, None, None)
            login = self.finish(
                email="local-sponsor@example.org",
                subject="local-sponsored-test-user",
                client=member,
            )
            self.assertEqual(login.status_code, 303)
            member.cookies.set("sigma_session", login.cookies["sigma_session"])
            status = member.get("/api/cloud-auth/status").json()
            self.assertFalse(status["mock_auth"])
            self.assertFalse(status["mock_identity"])
            self.assertTrue(status["sponsored_test_mode"])
            self.assertEqual(status["account"]["model_access"]["mode"], "sponsored")
            self.assertTrue(status["account"]["sponsorship"]["forced"])
            with (
                patch.dict(
                    os.environ,
                    {
                        "SIGMA_CLOUD_SPONSOR_EMAIL": "zetacontinuation@gmail.com",
                    },
                ),
                patch(
                    "sigma.cloud_sponsor.sponsor_session",
                    new=AsyncMock(
                        return_value={
                            "status": "connected",
                            "account_id": "designated-admin",
                            "account": {
                                "email": "zetacontinuation@gmail.com",
                                "access_token": "sponsor-token",
                            },
                        }
                    ),
                ) as sponsor_session,
                patch(
                    "sigma.openai_connection.chatgpt_auth.session",
                    new=AsyncMock(side_effect=AssertionError("local ChatGPT session was used")),
                ),
                patch(
                    "sigma.openai_connection._check",
                    new=AsyncMock(
                        return_value={
                            "status": "connected",
                            "checked_at": "2026-10-27T00:00:00Z",
                            "ttl_seconds": 60,
                        }
                    ),
                ),
            ):
                os.environ.pop("SIGMA_CLOUD_INFERENCE_PROVIDER", None)
                connection = member.get("/api/ai/connection")
            self.assertEqual(connection.status_code, 200, connection.text)
            self.assertEqual(connection.json()["mode"], "chatgpt")
            self.assertTrue(connection.json()["label"].startswith("SIGMA-sponsored ChatGPT"))
            self.assertEqual(sponsor_session.await_count, 1)
            budget = member.get("/api/cloud-research/budget")
            self.assertEqual(budget.status_code, 200, budget.text)
            self.assertEqual(budget.json()["allowance_usd"], 1.25)
            self.assertEqual(budget.json()["remaining_usd"], 1.25)
            personal = member.post(
                "/api/ai/mode",
                json={"mode": "personal"},
                headers={"Origin": local_origin},
            )
            self.assertEqual(personal.status_code, 403, personal.text)
            allowance = member.get("/api/cloud-auth/local-sponsored-allowance")
            self.assertEqual(allowance.status_code, 200, allowance.text)
            self.assertEqual(allowance.json()["allowance_usd"], 1.25)
            self.assertEqual(allowance.json()["remaining_usd"], 1.25)
            self.assertTrue(allowance.json()["local_preview"])
            self.assertFalse(allowance.json()["simulated"])

    def test_local_sponsored_service_key_starts_play_with_quarter_allowance(self):
        import asyncio
        from uuid import uuid4

        from sigma import openai_connection, research_sessions

        origin = "http://127.0.0.1:5173"
        project_root = Path(self.temp.name) / "local-projects"
        project_root.mkdir(mode=0o700)
        workspace_root = Path(self.temp.name) / "local-workspaces"
        workspace_root.mkdir(mode=0o700)
        with patch.dict(
            os.environ,
            {
                "SIGMA_CLOUD_AUTH_LOCAL": "true",
                "SIGMA_CLOUD_PUBLIC_ORIGIN": origin,
                "SIGMA_CLOUD_INFERENCE_PROVIDER": "api_key",
                "SIGMA_CLOUD_OPENAI_API_KEY": "fixture-sponsored-key",
                "OPENAI_API_KEY": "personal-key-must-not-be-used",
                "SIGMA_PROJECTS_ROOT": str(project_root),
                "SIGMA_CLOUD_WORKSPACES_ROOT": str(workspace_root),
                "SIGMA_LOCAL_SPONSORED_TEST_MODE": "0",
                "SIGMA_MOCK_AUTH": "0",
            },
        ):
            admin_login = self.finish()
            self.client.cookies.set("sigma_session", admin_login.cookies["sigma_session"])
            grant = self.client.post(
                "/api/cloud-auth/admin/grants",
                json={
                    "kind": "email",
                    "value": "member@example.org",
                    "role": "member",
                    "allowance_usd": 0.25,
                },
                headers={"Origin": origin},
            )
            self.assertEqual(grant.status_code, 200, grant.text)
            with TestClient(app, base_url="http://127.0.0.1") as member:
                login = self.finish(
                    email="member@example.org",
                    subject="local-service-key-member",
                    client=member,
                )
                member.cookies.set("sigma_session", login.cookies["sigma_session"])
                member.headers.update({"Origin": origin})
                cloud_auth.set_model_access("local-service-key-member", "sponsored")
                budget = member.get("/api/cloud-research/budget")
                self.assertEqual(budget.status_code, 200, budget.text)
                self.assertEqual(budget.json()["remaining_usd"], 0.25)

                principal = cloud_auth.Principal(
                    "local-service-key-member", "member@example.org", "member"
                )
                principal_token = cloud_auth._CURRENT_PRINCIPAL.set(principal)
                try:
                    credential = asyncio.run(openai_connection.auth_context())
                finally:
                    cloud_auth._CURRENT_PRINCIPAL.reset(principal_token)
                self.assertEqual(credential["mode"], "api_key")
                self.assertEqual(credential["token"], "fixture-sponsored-key")
                self.assertTrue(openai_connection.cloud_credential(credential))

                # A selected personal funding source must fail closed on a
                # temporary provider outage instead of silently spending the
                # sponsor allowance.
                self.seed_personal_plan_authorization("local-service-key-member")
                cloud_auth.set_model_access("local-service-key-member", "personal")
                with patch.object(
                    openai_connection.chatgpt_auth,
                    "session",
                    new=AsyncMock(
                        return_value={
                            "mode": "chatgpt",
                            "account": {"email": "personal@example.org", "access_token": ""},
                            "status": "unavailable",
                        }
                    ),
                ):
                    principal_token = cloud_auth._CURRENT_PRINCIPAL.set(principal)
                    try:
                        personal_credential = asyncio.run(openai_connection.auth_context())
                    finally:
                        cloud_auth._CURRENT_PRINCIPAL.reset(principal_token)
                self.assertEqual(personal_credential["status"], "unavailable")
                self.assertEqual(personal_credential["token"], "")
                self.assertFalse(openai_connection.cloud_credential(personal_credential))
                self.assertEqual(
                    cloud_auth.model_access_for_subject("local-service-key-member"), "personal"
                )
                cloud_auth.set_model_access("local-service-key-member", "sponsored")

                investigator = {
                    "claim": "The base case suggests the recurrence bound.",
                    "method": "Check the first recurrence value.",
                    "assumptions": ["The recurrence applies at positive indices."],
                    "evidence_status": "Unverified model derivation.",
                    "open_obligations": ["Check the next value."],
                    "python_code": None,
                    "sage_code": None,
                    "prior_session_failure_attempt_ids": [],
                    "human_guidance_reviews": [],
                    "computational_citations": [],
                }
                skeptic = {
                    "assessment": "continue",
                    "stop_reason": "recoverable_objection",
                    "response": "The next value remains to be checked.",
                    "objections": ["Verify the next value."],
                    "remaining_obligations": ["Verify the next value."],
                    "next_question": "What is the next recurrence value?",
                    "objective_status": "partial",
                    "solution_claim": "A partial bound is plausible.",
                    "argument_summary": "The first value supports only a partial bound.",
                    "assumptions_reviewed": ["The recurrence applies at positive indices."],
                    "proof_obligations": ["Verify the next value."],
                    "unresolved_objections": ["Verify the next value."],
                    "supporting_cycles": [1],
                    "verification_status": "incomplete",
                    "strategy_contribution": "productive",
                    "contribution_rationale": "The next check is explicit.",
                    "cross_strategy_relations": [],
                    "retracted_cross_strategy_source_artifact_ids": [],
                    "peer_handoff_reviews": [],
                    "human_guidance_reviews": [],
                    "computational_citations": [],
                }

                async def fake_call(record, role, context, timeout_seconds=None, step_id=None):
                    del record, context, timeout_seconds
                    self.assertIsInstance(step_id, str)
                    return (investigator if role == "investigator" else skeptic), {
                        "input_tokens": 90,
                        "cached_input_tokens": 0,
                        "output_tokens": 30,
                    }

                async def provider_fixture(request):
                    self.assertEqual(
                        request.headers["authorization"], "Bearer fixture-sponsored-key"
                    )
                    self.assertEqual(request.url.path, "/v1/models")
                    return httpx.Response(
                        200,
                        json={"object": "list", "data": [{"id": "gpt-6.1-sol"}]},
                    )

                real_client = httpx.AsyncClient
                with (
                    patch.object(
                        openai_connection.httpx,
                        "AsyncClient",
                        side_effect=lambda **kwargs: real_client(
                            transport=httpx.MockTransport(provider_fixture), **kwargs
                        ),
                    ),
                    patch.object(research_sessions, "execution_capabilities", return_value=[]),
                    patch.object(
                        research_sessions, "_call", new=AsyncMock(side_effect=fake_call)
                    ) as calls,
                    patch.object(sponsor_diagnostics, "record") as diagnostics,
                ):
                    created = member.post(
                        "/api/projects/create",
                        json={"title": "Local sponsor Play", "problem": "Check a recurrence bound"},
                    )
                    self.assertEqual(created.status_code, 201, created.text)
                    path = created.json()["path"]
                    project_id = created.json()["project"]["id"]
                    strategy = member.post(
                        "/api/projects/strategies",
                        json={
                            "path": path,
                            "title": "Induction",
                            "approach": "Check the base case and induction step.",
                        },
                    )
                    self.assertEqual(strategy.status_code, 201, strategy.text)
                    strategies = member.get(
                        "/api/projects/strategies", params={"path": path}
                    ).json()["strategies"]
                    limits = member.put(
                        "/api/projects/research-limits",
                        json={
                            "path": path,
                            "research_rounds": 1,
                            "model_calls": 12,
                            "session_duration_minutes": 15,
                            "output_tokens_per_call": 256,
                            "maximum_estimated_cost_usd": 0.25,
                        },
                    )
                    self.assertEqual(limits.status_code, 200, limits.text)
                    self.assertEqual(limits.json()["model_calls"], 12, limits.text)
                    reloaded_limits = member.get(
                        "/api/projects/research-limits", params={"path": path}
                    )
                    self.assertEqual(reloaded_limits.status_code, 200, reloaded_limits.text)
                    self.assertEqual(
                        reloaded_limits.json()["model_calls"], 12, reloaded_limits.text
                    )
                    config = member.get("/api/projects/proposals/config", params={"path": path})
                    self.assertEqual(config.status_code, 200, config.text)
                    self.assertTrue(config.json()["available"], config.text)
                    self.assertEqual(config.json()["binding"], credential["identity"])
                    started = member.post(
                        "/api/projects/research-sessions/start",
                        json={
                            "path": path,
                            "strategy_id": strategies[0]["id"],
                            "idempotency_key": str(uuid4()),
                            "expected_project_id": project_id,
                            "expected_binding": credential["identity"],
                            "expected_limits": limits.json(),
                        },
                    )
                    self.assertEqual(started.status_code, 200, started.text)
                    self.assertEqual(
                        [item.args for item in diagnostics.call_args_list],
                        [
                            ("sponsor_context", "o0_b2_t0_a0_r0_p0"),
                            ("sponsor_play", "accepted"),
                        ],
                    )
                    session_id = started.json()["id"]
                    saved = started.json()
                    for _ in range(500):
                        saved = member.get(
                            f"/api/projects/research-sessions/{session_id}",
                            params={"path": path},
                        ).json()
                        if saved["status"] in {"ended", "failed", "paused"}:
                            break
                        time.sleep(0.01)
                    self.assertEqual(saved["status"], "ended", saved)
                    self.assertEqual(calls.await_count, 2)

    def test_local_expired_personal_connection_does_not_switch_funding_and_admin_can_renew(self):
        local_origin = "http://127.0.0.1:5173"
        with patch.dict(
            os.environ,
            {
                "SIGMA_CLOUD_AUTH_LOCAL": "true",
                "SIGMA_CLOUD_PUBLIC_ORIGIN": local_origin,
                "SIGMA_CLOUD_ADMIN_CONTACT_EMAIL": "zetacontinuation@gmail.com",
                "SIGMA_LOCAL_SPONSORED_TEST_MODE": "0",
                "SIGMA_MOCK_AUTH": "0",
            },
        ):
            os.environ.pop("SIGMA_CLOUD_SPONSOR_EMAIL", None)
            admin_login = self.finish(
                email="zetacontinuation@gmail.com", subject="configured-local-admin"
            )
            self.client.cookies.update(admin_login.cookies)
            grant = self.client.post(
                "/api/cloud-auth/admin/grants",
                json={
                    "kind": "email",
                    "value": "nontrivialzeeros@gmail.com",
                    "role": "member",
                    "allowance_usd": 0.01,
                },
                headers={"Origin": local_origin},
            )
            self.assertEqual(grant.status_code, 200, grant.text)
            member_context = TestClient(
                app, base_url="http://127.0.0.1", client=("127.0.0.1", 23456)
            )
            member = member_context.__enter__()
            self.addCleanup(member_context.__exit__, None, None, None)
            login = self.finish(
                email="nontrivialzeeros@gmail.com",
                subject="local-sponsored-member",
                client=member,
            )
            self.assertEqual(login.status_code, 303)
            member.cookies.update(login.cookies)
            initial_status = member.get("/api/cloud-auth/status").json()
            self.assertTrue(initial_status["account"]["sponsorship"]["eligible"])
            self.assertEqual(initial_status["account"]["model_access"]["mode"], "sponsored")
            # Once the user explicitly selects personal mode, later status
            # refreshes must preserve that choice.
            self.seed_personal_plan_authorization("local-sponsored-member")
            with patch(
                "sigma.openai_connection._check",
                new=AsyncMock(
                    return_value={"status": "connected", "checked_at": "fixture", "ttl_seconds": 60}
                ),
            ):
                cloud_auth.set_model_access("local-sponsored-member", "personal")
            with (
                patch(
                    "sigma.openai_connection.chatgpt_auth.session",
                    new=AsyncMock(
                        return_value={"mode": "chatgpt", "status": "reauth_required", "account": {}}
                    ),
                ) as personal_session,
                patch(
                    "sigma.cloud_sponsor.sponsor_session",
                    new=AsyncMock(return_value={"status": "reauth_required", "account": {}}),
                ) as sponsor_session,
            ):
                connection = member.get("/api/ai/connection")
            self.assertEqual(connection.status_code, 200, connection.text)
            self.assertEqual(personal_session.await_count, 1)
            self.assertEqual(sponsor_session.await_count, 0)
            self.assertIn("session has expired", connection.json()["guidance"])
            self.assertNotIn("administrator", connection.json()["guidance"].lower())
            status = member.get("/api/cloud-auth/status").json()
            self.assertEqual(status["account"]["model_access"]["mode"], "personal")
            with (
                patch(
                    "sigma.cloud_sponsor.sponsor_account_id",
                    new=AsyncMock(return_value="sponsor-id"),
                ),
                patch(
                    "sigma.api.chatgpt_auth.begin",
                    new=AsyncMock(
                        return_value={
                            "id": "attempt",
                            "authorization_url": "/api/ai/auth/open/attempt",
                        }
                    ),
                ) as begin,
            ):
                member_denied = member.post(
                    "/api/ai/sponsor-auth/begin", json={}, headers={"Origin": local_origin}
                )
                self.assertEqual(member_denied.status_code, 403, member_denied.text)
                with patch.dict(os.environ, {"SIGMA_CLOUD_SPONSORED_ENABLED": "false"}):
                    disabled_member_denied = member.post(
                        "/api/ai/sponsor-auth/begin", json={}, headers={"Origin": local_origin}
                    )
                    self.assertEqual(
                        disabled_member_denied.status_code, 403, disabled_member_denied.text
                    )
                allowed = self.client.post(
                    "/api/ai/sponsor-auth/begin", json={}, headers={"Origin": local_origin}
                )
            self.assertEqual(allowed.status_code, 200, allowed.text)
            self.assertEqual(begin.await_count, 1)
            begin.assert_awaited_with(account_id="sponsor-id", sponsor=True)

    def test_local_personal_mode_cannot_use_or_disconnect_active_sponsor_credential(self):
        import asyncio

        from sigma.ai_store import sponsor_transaction

        local_origin = "http://127.0.0.1:5173"
        with patch.dict(
            os.environ,
            {
                "SIGMA_CLOUD_AUTH_LOCAL": "true",
                "SIGMA_CLOUD_PUBLIC_ORIGIN": local_origin,
                "SIGMA_AUTH_HOME": str(Path(self.temp.name) / "sponsor-store"),
                "SIGMA_LOCAL_SPONSORED_TEST_MODE": "0",
                "SIGMA_MOCK_AUTH": "0",
            },
        ):
            admin_login = self.finish()
            self.client.cookies.set("sigma_session", admin_login.cookies["sigma_session"])
            grant = self.client.post(
                "/api/cloud-auth/admin/grants",
                json={
                    "kind": "email",
                    "value": "nontrivialzeero@gmail.com",
                    "role": "member",
                    "allowance_usd": 0.01,
                },
                headers={"Origin": local_origin},
            )
            self.assertEqual(grant.status_code, 200, grant.text)
            member_context = TestClient(
                app, base_url="http://127.0.0.1", client=("127.0.0.1", 23456)
            )
            member = member_context.__enter__()
            self.addCleanup(member_context.__exit__, None, None, None)
            login = self.finish(
                email="nontrivialzeero@gmail.com",
                subject="local-sponsored-member",
                client=member,
            )
            member.cookies.set("sigma_session", login.cookies["sigma_session"])
            self.seed_personal_plan_authorization("local-sponsored-member")
            cloud_auth.set_model_access("local-sponsored-member", "personal")

            async def seed():
                async with sponsor_transaction() as state:
                    state["mode"] = "chatgpt"
                    state["active"] = "sponsor"
                    state["accounts"] = {
                        "sponsor": {
                            "email": "zetacontinuation@gmail.com",
                            "client_id": "fixture-client",
                            "access_token": "fixture-sponsor-token",
                            "refresh_token": "fixture-refresh-token",
                            "expires_at": time.time() + 3600,
                            "scopes": ["resource.invoke", "chatgpt.tokens.use.direct"],
                        }
                    }

            asyncio.run(seed())
            with patch(
                "sigma.openai_connection._check",
                new=AsyncMock(
                    return_value={"status": "connected", "checked_at": "fixture", "ttl_seconds": 60}
                ),
            ):
                connection = member.get("/api/ai/connection")
            self.assertEqual(connection.status_code, 200, connection.text)
            self.assertEqual(connection.json()["status"], "connected")
            self.assertNotIn("fixture-sponsor-token", connection.text)

            renew = member.post(
                "/api/ai/auth/begin",
                json={"account_id": "sponsor"},
                headers={"Origin": local_origin},
            )
            self.assertEqual(renew.status_code, 400, renew.text)
            sponsor_renew = member.post(
                "/api/ai/sponsor-auth/begin", json={}, headers={"Origin": local_origin}
            )
            self.assertEqual(sponsor_renew.status_code, 403, sponsor_renew.text)
            with patch(
                "sigma.api.chatgpt_auth.disconnect",
                new=AsyncMock(return_value={"message": "disconnected"}),
            ):
                disconnected = member.post(
                    "/api/ai/disconnect", json={}, headers={"Origin": local_origin}
                )
            self.assertEqual(disconnected.status_code, 200, disconnected.text)

            async def assert_intact():
                async with sponsor_transaction() as state:
                    self.assertEqual(
                        state["accounts"]["sponsor"]["access_token"], "fixture-sponsor-token"
                    )

            asyncio.run(assert_intact())

    def test_connection_choice_is_separate_from_allowance_and_hosted_personal_is_unsupported(self):
        signed_in = self.finish()
        self.client.cookies.set(
            cloud_auth.SESSION_COOKIE, signed_in.cookies[cloud_auth.SESSION_COOKIE]
        )
        initial = self.client.get("/api/cloud-auth/status").json()
        self.assertEqual(initial["account"]["model_access"]["mode"], "sponsored")
        headers = {"Origin": ORIGIN, "Content-Type": "application/json"}
        with patch("sigma.api.cloud_research.snapshot", return_value={"remaining_usd": 1.25}):
            selected = self.client.post("/api/ai/mode", json={"mode": "sponsored"}, headers=headers)
        self.assertEqual(selected.status_code, 200, selected.text)
        # The connection response's mode describes the provider adapter;
        # funding selection is the persistent cloud-auth account state below.
        self.assertEqual(selected.json()["mode"], "chatgpt")
        self.assertEqual(
            self.client.get("/api/cloud-auth/status").json()["account"]["model_access"]["mode"],
            "sponsored",
        )
        with patch(
            "sigma.api.cloud_research.snapshot",
            side_effect=AssertionError("mode selection must not inspect spend ledger"),
        ):
            exhausted = self.client.post(
                "/api/ai/mode", json={"mode": "sponsored"}, headers=headers
            )
        self.assertEqual(exhausted.status_code, 200, exhausted.text)
        self.assertEqual(
            self.client.get("/api/cloud-auth/status").json()["account"]["model_access"]["mode"],
            "sponsored",
        )
        switched = self.client.post("/api/ai/mode", json={"mode": "personal"}, headers=headers)
        self.assertEqual(switched.status_code, 403, switched.text)
        refreshed = self.client.get("/api/cloud-auth/status").json()
        self.assertEqual(refreshed["account"]["model_access"]["mode"], "sponsored")

    def test_operator_can_disable_sponsor_without_removing_personal_connection(self):
        signed_in = self.finish()
        self.client.cookies.set(
            cloud_auth.SESSION_COOKIE, signed_in.cookies[cloud_auth.SESSION_COOKIE]
        )
        headers = {"Origin": ORIGIN, "Content-Type": "application/json"}
        with patch.dict(os.environ, {"SIGMA_CLOUD_SPONSORED_ENABLED": "false"}):
            status = self.client.get("/api/cloud-auth/status").json()
            self.assertTrue(status["authenticated"])
            self.assertEqual(status["account"]["model_access"]["mode"], "personal")
            self.assertFalse(status["account"]["sponsorship"]["eligible"])
            with patch(
                "sigma.api.cloud_research.snapshot",
                side_effect=AssertionError("disabled sponsor checked allowance"),
            ):
                blocked = self.client.post(
                    "/api/ai/mode", json={"mode": "sponsored"}, headers=headers
                )
            self.assertEqual(blocked.status_code, 403)
            self.assertEqual(self.client.get("/api/cloud-research/connection").status_code, 404)
            personal = self.client.post("/api/ai/mode", json={"mode": "personal"}, headers=headers)
            self.assertEqual(personal.status_code, 200)
            self.assertEqual(personal.json()["status"], "unavailable")

    def test_force_sponsored_mode_is_opt_in_and_enforced_for_eligible_users(self):
        self.assertFalse(cloud_auth.force_sponsored_mode_enabled())
        admin = self.finish()
        self.client.cookies.set(cloud_auth.SESSION_COOKIE, admin.cookies[cloud_auth.SESSION_COOKIE])
        granted = self.client.post(
            "/api/cloud-auth/admin/grants",
            headers={"Origin": ORIGIN},
            json={
                "kind": "email",
                "value": "member@example.org",
                "role": "member",
                "allowance_usd": 0.75,
            },
        )
        self.assertEqual(granted.status_code, 200, granted.text)

        headers = {"Origin": ORIGIN, "Content-Type": "application/json"}
        with patch.dict(os.environ, {"SIGMA_CLOUD_FORCE_SPONSORED_MODE": "true"}):
            self.assertTrue(cloud_auth.force_sponsored_mode_enabled())
            admin_status = self.client.get("/api/cloud-auth/status").json()
            self.assertTrue(admin_status["account"]["sponsorship"]["forced"])
            self.assertEqual(admin_status["account"]["model_access"]["mode"], "sponsored")
            denied_change = self.client.post(
                "/api/ai/mode", json={"mode": "personal"}, headers=headers
            )
            self.assertEqual(denied_change.status_code, 403)

            member = self.finish(email="member@example.org", subject="forced-member")
            self.client.cookies.set(
                cloud_auth.SESSION_COOKIE, member.cookies[cloud_auth.SESSION_COOKIE]
            )
            member_status = self.client.get("/api/cloud-auth/status").json()
            self.assertTrue(member_status["account"]["sponsorship"]["eligible"])
            self.assertTrue(member_status["account"]["sponsorship"]["forced"])
            self.assertEqual(member_status["account"]["model_access"]["mode"], "sponsored")
            denied_change = self.client.post(
                "/api/ai/mode", json={"mode": "personal"}, headers=headers
            )
            self.assertEqual(denied_change.status_code, 403)

            self.client.cookies.clear()
            guest = self.client.post("/api/ai/mode", json={"mode": "personal"}, headers=headers)
            self.assertEqual(guest.status_code, 401)

        self.assertFalse(cloud_auth.force_sponsored_mode_enabled())

    def test_session_expiration_is_enforced(self):
        signed_in = self.finish()
        raw = signed_in.cookies[cloud_auth.SESSION_COOKIE]
        with cloud_auth._db(cloud_auth.config()) as db:
            expiry = db.execute(
                "SELECT expires_at FROM sessions WHERE token_hash=?", (cloud_auth._hash(raw),)
            ).fetchone()["expires_at"]
        with patch.object(cloud_auth, "_now", return_value=expiry):
            self.assertIsNone(cloud_auth.resolve_session(raw))
            self.client.cookies.set(cloud_auth.SESSION_COOKIE, raw)
            self.assertEqual(self.client.get("/api/projects/recent").status_code, 401)

    def test_invalid_identity_claims_nonce_and_state_replay(self):
        invalid = [
            {"verified": False},
            {"iss": "https://attacker.test"},
            {"aud": "other-client"},
            {"exp": int(time.time()) - 1},
            {"azp": "other-client"},
        ]
        for changes in invalid:
            response = self.finish(changes=changes)
            self.assertEqual(response.status_code, 401, changes)
            self.assertNotIn(cloud_auth.SESSION_COOKIE, response.cookies)
        state, flow_cookie = self.start_flow()
        self.client.cookies.set(cloud_auth.FLOW_COOKIE, flow_cookie)
        bad_state = self.client.get(
            "/api/cloud-auth/callback", params={"state": "wrong", "code": "fixture"}
        )
        self.assertEqual(bad_state.status_code, 400)
        GoogleClient.token = token(nonce="wrong")
        self.client.cookies.set(cloud_auth.FLOW_COOKIE, flow_cookie)
        with patch.object(cloud_auth.httpx, "AsyncClient", GoogleClient):
            bad_nonce = self.client.get(
                "/api/cloud-auth/callback", params={"state": state, "code": "fixture"}
            )
        self.assertEqual(bad_nonce.status_code, 401)
        replay_state, replay_cookie = self.start_flow()
        with cloud_auth._db(cloud_auth.config()) as db:
            nonce = db.execute(
                "SELECT nonce FROM flows WHERE state_hash=?", (cloud_auth._hash(replay_state),)
            ).fetchone()["nonce"]
        GoogleClient.token = token(nonce=nonce)
        parts = GoogleClient.token.split(".")
        GoogleClient.token = ".".join(
            [parts[0], parts[1], parts[2][:-1] + ("a" if parts[2][-1] != "a" else "b")]
        )
        self.client.cookies.set(cloud_auth.FLOW_COOKIE, replay_cookie)
        with patch.object(cloud_auth.httpx, "AsyncClient", GoogleClient):
            bad_signature = self.client.get(
                "/api/cloud-auth/callback", params={"state": replay_state, "code": "fixture"}
            )
            replay = self.client.get(
                "/api/cloud-auth/callback", params={"state": replay_state, "code": "fixture"}
            )
        self.assertEqual(bad_signature.status_code, 401)
        self.assertEqual(replay.status_code, 400)

    def test_every_api_group_is_protected_and_origin_is_checked(self):
        for path in [
            f"/api/projects/inspect?path={self.project_path}",
            f"/api/projects/research-sessions?path={self.project_path}",
            f"/api/projects/research-executions?path={self.project_path}",
            "/api/projects/recent",
        ]:
            self.assertEqual(self.client.get(path).status_code, 401, path)
        rejected = self.client.post(
            "/api/projects/close",
            json={"path": str(self.project_path)},
            headers={"Origin": "https://attacker.test"},
        )
        self.assertEqual(rejected.status_code, 403)
        self.assertEqual(self.client.get("/api/ai/connection").status_code, 401)

    def test_missing_config_fails_closed_and_local_mode_remains_available(self):
        with patch.dict(
            os.environ,
            {
                "SIGMA_CLOUD_AUTH_ENABLED": "true",
                "GOOGLE_OIDC_CLIENT_ID": "",
                "GOOGLE_OIDC_CLIENT_SECRET": "",
                "SIGMA_CLOUD_PUBLIC_ORIGIN": "",
                "SIGMA_CLOUD_AUTH_HOME": "",
                "SIGMA_CLOUD_ADMIN_CONTACT_EMAIL": "",
            },
        ):
            self.assertIsNotNone(cloud_auth.config().error)
            self.assertEqual(self.client.get("/api/projects/research-executions").status_code, 503)
        with patch.dict(os.environ, {"SIGMA_CLOUD_AUTH_ENABLED": "false"}):
            self.assertFalse(self.client.get("/api/cloud-auth/status").json()["enabled"])
            self.assertEqual(self.client.get("/api/research-tools").status_code, 200)

    def test_local_status_reports_missing_admin_contact_without_exposing_credentials(self):
        with patch.dict(
            os.environ,
            {
                "SIGMA_CLOUD_AUTH_ENABLED": "false",
                "GOOGLE_OIDC_CLIENT_ID": CLIENT_ID,
                "GOOGLE_OIDC_CLIENT_SECRET": "local-test-secret",
                "SIGMA_CLOUD_ADMIN_CONTACT_EMAIL": "",
            },
        ):
            response = self.client.get("/api/cloud-auth/status")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertFalse(body["enabled"])
        self.assertEqual(body["local_setup_missing"], ["SIGMA_CLOUD_ADMIN_CONTACT_EMAIL"])
        self.assertNotIn("local-test-secret", response.text)
        self.assertNotIn("admin@example.org", response.text)


if __name__ == "__main__":
    main()
