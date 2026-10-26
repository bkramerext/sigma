"""Deterministic tests for opt-in hosted Google authentication."""

from __future__ import annotations

import os
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, main
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

import httpx
import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from jwt.algorithms import RSAAlgorithm

from sigma import cloud_auth
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
                "SIGMA_CLOUD_DEMO_AUDIT": str(
                    Path(__file__).resolve().parents[1] / "cloud-demo/handshake-demo-audit.json"
                ),
            },
        )
        self.env.start()
        self.addCleanup(self.env.stop)
        self.context = TestClient(app)
        self.client = self.context.__enter__()
        self.addCleanup(self.context.__exit__, None, None, None)

    def test_mock_members_receive_distinct_stable_workspaces(self):
        from sigma.cloud_workspaces import workspace_for_subject

        with patch.dict(os.environ, {
            "SIGMA_CLOUD_AUTH_ENABLED": "true",
            "SIGMA_CLOUD_AUTH_LOCAL": "true",
            "SIGMA_MOCK_AUTH": "1",
            "SIGMA_CLOUD_PUBLIC_ORIGIN": "http://127.0.0.1:5173",
            "SIGMA_CLOUD_AUTH_HOME": str(self.root),
        }):
            cfg = cloud_auth.config()
            self.assertIsNone(cfg.error)
            first = cloud_auth._persist_user_state(
                cfg, cloud_auth.Principal("mock:member-a", "mock-member-a@localhost.invalid", "member")
            )
            second = cloud_auth._persist_user_state(
                cfg, cloud_auth.Principal("mock:member-b", "mock-member-b@localhost.invalid", "member")
            )
            first_again = cloud_auth._persist_user_state(
                cfg, cloud_auth.Principal("mock:member-a", "mock-member-a@localhost.invalid", "member")
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
        with patch.dict(os.environ, {
            "SIGMA_CLOUD_AUTH_ENABLED": "true",
            "SIGMA_CLOUD_AUTH_LOCAL": "true",
            "SIGMA_MOCK_AUTH": "1",
            "SIGMA_CLOUD_PUBLIC_ORIGIN": "http://127.0.0.1:5173",
            "SIGMA_CLOUD_AUTH_HOME": str(self.root),
            "GOOGLE_OIDC_CLIENT_ID": "",
            "GOOGLE_OIDC_CLIENT_SECRET": "",
            "SIGMA_CLOUD_ADMIN_CONTACT_EMAIL": "",
        }):
            cfg = cloud_auth.config()
            self.assertIsNone(cfg.error)
            self.assertTrue(cfg.local)
            self.assertTrue(cloud_auth._mock_enabled(cfg))
        with patch.dict(os.environ, {"SIGMA_CLOUD_PUBLIC_ORIGIN": "https://sigma.example.org"}):
            self.assertFalse(cloud_auth._mock_enabled(cloud_auth.config()))

    def test_mock_auth_disabled_for_hosted_and_nonlocal_configurations(self):
        with patch.dict(os.environ, {"SIGMA_MOCK_AUTH": "1"}):
            self.assertFalse(cloud_auth._mock_enabled(cloud_auth.config()))
            response = self.client.post(
                "/api/cloud-auth/mock/select?identity=admin",
                headers={"Origin": ORIGIN},
            )
            self.assertEqual(response.status_code, 404)
        with patch.dict(os.environ, {
            "SIGMA_MOCK_AUTH": "1",
            "SIGMA_CLOUD_AUTH_LOCAL": "true",
            "SIGMA_CLOUD_PUBLIC_ORIGIN": ORIGIN,
        }):
            self.assertFalse(cloud_auth._mock_enabled(cloud_auth.config()))

    def test_mock_auth_rejects_cross_origin_and_remote_clients(self):
        with patch.dict(os.environ, {
            "SIGMA_MOCK_AUTH": "1",
            "SIGMA_CLOUD_AUTH_LOCAL": "true",
            "SIGMA_CLOUD_PUBLIC_ORIGIN": "http://127.0.0.1:5173",
        }):
            self.assertTrue(cloud_auth._mock_enabled(cloud_auth.config()))
            self.assertEqual(
                self.client.post(
                    "/api/cloud-auth/mock/select?identity=admin",
                    headers={"Origin": "http://evil.example"},
                ).status_code, 403,
            )
            self.assertEqual(
                self.client.post(
                    "/api/cloud-auth/mock/select?identity=admin",
                    headers={"Origin": "http://127.0.0.1:5173"},
                ).status_code, 403,
            )

    def start_flow(self, client=None):
        client = client or self.client
        response = client.get("/api/cloud-auth/login", follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        self.assertIn("Secure", response.headers["set-cookie"])
        self.assertIn("HttpOnly", response.headers["set-cookie"])
        self.assertIn("SameSite=lax", response.headers["set-cookie"])
        query = parse_qs(urlsplit(response.headers["location"]).query)
        self.assertEqual(query["code_challenge_method"], ["S256"])
        self.assertEqual(query["prompt"], ["select_account"])
        return query["state"][0], response.cookies[cloud_auth.FLOW_COOKIE]

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

    def finish(self, email="admin@example.org", subject="google-sub-1", changes=None, client=None):
        client = client or self.client
        state, flow_cookie = self.start_flow(client)
        with cloud_auth._db(cloud_auth.config()) as db:
            nonce = db.execute(
                "SELECT nonce FROM flows WHERE state_hash=?", (cloud_auth._hash(state),)
            ).fetchone()["nonce"]
        GoogleClient.token = token(nonce=nonce, email=email, subject=subject, **(changes or {}))
        client.cookies.set(cloud_auth.FLOW_COOKIE, flow_cookie)
        with patch.object(cloud_auth.httpx, "AsyncClient", GoogleClient):
            return client.get(
                "/api/cloud-auth/callback",
                params={"state": state, "code": "fixture"},
                follow_redirects=False,
            )

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
            {"mode": "personal", "connection": "checking"},
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
                "personal",
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
        self.assertEqual(self.client.get("/api/ai/auth/open/guessed").status_code, 403)
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
        updated = self.client.put(
            f"/api/cloud-auth/admin/invitation-requests/{row['subject']}",
            json={"status": "reviewed"},
            headers={"Origin": ORIGIN},
        )
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.json()["status"], "reviewed")
        self.assertEqual(
            visitor.post("/api/cloud-auth/invitation-request", headers={"Origin": ORIGIN}).json()[
                "duplicate"
            ],
            True,
        )
        self.assertEqual(deliver.call_count, 1)

    def test_invitation_request_fails_closed_when_notification_unconfigured(self):
        denied = self.finish(email="visitor@example.org", subject="request-retry")
        self.client.cookies.set(cloud_auth.DENIED_COOKIE, denied.cookies[cloud_auth.DENIED_COOKIE])
        with patch.object(
            cloud_auth, "_deliver_invitation", side_effect=RuntimeError("not configured")
        ):
            failed = self.client.post(
                "/api/cloud-auth/invitation-request", headers={"Origin": ORIGIN}
            )
        self.assertEqual(failed.status_code, 503)
        self.assertEqual(
            failed.json()["detail"], "Your request could not be sent. Please try again later."
        )
        self.assertEqual(denied.headers["location"], "/?access=denied")

    def test_invitation_notification_uses_authenticated_sender_and_fixed_recipient(self):
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
        self.assertEqual(message["To"], "zetacontinuation@gmail.com")

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
        self.assertEqual(
            visitor.put(
                f"/api/cloud-auth/admin/feedback/{row['id']}",
                json={"status": "closed"},
                headers={"Origin": ORIGIN},
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

    def test_changing_contact_preserves_bound_admin_and_does_not_authorize_new_contact(self):
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
        self.assertEqual(denied.headers["location"], "/?access=denied")
        self.assertNotIn(cloud_auth.SESSION_COOKIE, denied.cookies)

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
            self.client.get("/api/cloud-auth/denied").json(), {"email": "visitor@example.org"}
        )
        self.assertEqual(self.client.get("/api/cloud-auth/status").json()["authenticated"], False)
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

    def test_connection_choice_persists_per_verified_subject_and_exhaustion_blocks_sponsor(self):
        signed_in = self.finish()
        self.client.cookies.set(
            cloud_auth.SESSION_COOKIE, signed_in.cookies[cloud_auth.SESSION_COOKIE]
        )
        initial = self.client.get("/api/cloud-auth/status").json()
        self.assertEqual(initial["account"]["model_access"]["mode"], "personal")
        headers = {"Origin": ORIGIN, "Content-Type": "application/json"}
        with patch("sigma.api.cloud_research.snapshot", return_value={"remaining_usd": 1.25}):
            selected = self.client.post("/api/ai/mode", json={"mode": "sponsored"}, headers=headers)
        self.assertEqual(selected.status_code, 200, selected.text)
        self.assertEqual(selected.json()["mode"], "api_key")
        self.assertEqual(
            self.client.get("/api/cloud-auth/status").json()["account"]["model_access"]["mode"],
            "sponsored",
        )
        with patch("sigma.api.cloud_research.snapshot", return_value={"remaining_usd": 0.0}):
            exhausted = self.client.post(
                "/api/ai/mode", json={"mode": "sponsored"}, headers=headers
            )
        self.assertEqual(exhausted.status_code, 409, exhausted.text)
        switched = self.client.post("/api/ai/mode", json={"mode": "personal"}, headers=headers)
        self.assertEqual(switched.status_code, 200, switched.text)
        self.assertEqual(switched.json()["status"], "unavailable")
        refreshed = self.client.get("/api/cloud-auth/status").json()
        self.assertEqual(refreshed["account"]["model_access"]["mode"], "personal")

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
