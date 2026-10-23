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
        self.env = patch.dict(
            os.environ,
            {
                "SIGMA_CLOUD_AUTH_ENABLED": "true",
                "GOOGLE_OIDC_CLIENT_ID": CLIENT_ID,
                "GOOGLE_OIDC_CLIENT_SECRET": "fixture-secret",
                "SIGMA_CLOUD_PUBLIC_ORIGIN": ORIGIN,
                "SIGMA_CLOUD_BOOTSTRAP_ADMIN_EMAIL": "admin@example.org",
                "SIGMA_CLOUD_AUTH_HOME": str(self.root),
                "SIGMA_CLOUD_ADMIN_CONTACT_EMAIL": "access@example.org",
            },
        )
        self.env.start()
        self.addCleanup(self.env.stop)
        self.context = TestClient(app)
        self.client = self.context.__enter__()
        self.addCleanup(self.context.__exit__, None, None, None)

    def start_flow(self):
        response = self.client.get("/api/cloud-auth/login", follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        self.assertIn("Secure", response.headers["set-cookie"])
        self.assertIn("HttpOnly", response.headers["set-cookie"])
        self.assertIn("SameSite=lax", response.headers["set-cookie"])
        query = parse_qs(urlsplit(response.headers["location"]).query)
        self.assertEqual(query["code_challenge_method"], ["S256"])
        self.assertEqual(query["prompt"], ["select_account"])
        return query["state"][0], response.cookies[cloud_auth.FLOW_COOKIE]

    def finish(self, email="admin@example.org", subject="google-sub-1", changes=None):
        state, flow_cookie = self.start_flow()
        with cloud_auth._db(cloud_auth.config()) as db:
            nonce = db.execute(
                "SELECT nonce FROM flows WHERE state_hash=?", (cloud_auth._hash(state),)
            ).fetchone()["nonce"]
        GoogleClient.token = token(nonce=nonce, email=email, subject=subject, **(changes or {}))
        self.client.cookies.set(cloud_auth.FLOW_COOKIE, flow_cookie)
        with patch.object(cloud_auth.httpx, "AsyncClient", GoogleClient):
            return self.client.get(
                "/api/cloud-auth/callback",
                params={"state": state, "code": "fixture"},
                follow_redirects=False,
            )

    def test_successful_signin_admin_invite_and_revocation(self):
        self.assertEqual(
            self.client.get(
                "/api/projects/research-sessions", params={"path": "projects/rh.sigma"}
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
        self.assertEqual(status["admin_contact_email"], "access@example.org")
        self.assertNotIn("grants", status)
        self.assertNotIn("denied_email", status)
        invite = self.client.post(
            "/api/cloud-auth/admin/grants",
            json={"kind": "email", "value": " Person@Example.org ", "role": "member"},
            headers={"Origin": ORIGIN},
        )
        self.assertEqual(invite.status_code, 200)
        self.assertEqual(invite.json()["value"], "person@example.org")
        revoked = self.client.delete(
            "/api/cloud-auth/admin/grants/email/person%40example.org", headers={"Origin": ORIGIN}
        )
        self.assertEqual(revoked.status_code, 200)
        self.assertEqual(
            self.client.get("/api/cloud-auth/admin/grants").json()["grants"][0]["active"], 0
        )
        self.assertEqual(
            self.client.post("/api/ai/disconnect", headers={"Origin": ORIGIN}).status_code, 403
        )

    def test_denied_identity_is_retained_only_for_request_and_other_account_resets_it(self):
        denied = self.finish(email="visitor@example.org")
        self.assertEqual(denied.status_code, 303)
        self.assertEqual(denied.headers["location"], "/?access=denied")
        self.assertNotIn(cloud_auth.SESSION_COOKIE, denied.cookies)
        denied_token = denied.cookies[cloud_auth.DENIED_COOKIE]
        self.assertIn("HttpOnly", denied.headers["set-cookie"])
        self.assertIn("Secure", denied.headers["set-cookie"])
        self.client.cookies.set(cloud_auth.DENIED_COOKIE, denied_token)
        self.assertEqual(
            self.client.get("/api/cloud-auth/denied").json(), {"email": "visitor@example.org"}
        )
        self.assertEqual(self.client.get("/api/cloud-auth/status").json()["authenticated"], False)
        self.assertEqual(
            self.client.get(
                "/api/projects/research-sessions", params={"path": "projects/rh.sigma"}
            ).status_code,
            401,
        )
        restart = self.client.get("/api/cloud-auth/login", follow_redirects=False)
        self.assertEqual(
            parse_qs(urlsplit(restart.headers["location"]).query)["prompt"], ["select_account"]
        )
        self.assertIn('__Host-sigma_denied="";', restart.headers["set-cookie"])
        self.assertEqual(self.client.get("/api/cloud-auth/denied").status_code, 404)

    def test_local_mode_keeps_project_and_provider_apis_unauthenticated(self):
        with patch.dict(os.environ, {"SIGMA_CLOUD_AUTH_ENABLED": "false"}):
            self.assertEqual(self.client.get("/api/cloud-auth/status").json()["enabled"], False)
            self.assertNotEqual(
                self.client.get(
                    "/api/projects/research-sessions", params={"path": "projects/rh.sigma"}
                ).status_code,
                401,
            )
            self.assertNotEqual(self.client.get("/api/ai/connection").status_code, 401)

    def test_exact_domain_and_revocation_of_existing_session(self):
        admin = self.finish()
        self.client.cookies.set(cloud_auth.SESSION_COOKIE, admin.cookies[cloud_auth.SESSION_COOKIE])
        invited = self.client.post(
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
        self.client.cookies.set(cloud_auth.SESSION_COOKIE, admin.cookies[cloud_auth.SESSION_COOKIE])
        self.assertEqual(
            self.client.delete(
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
        self.client.cookies.set(cloud_auth.SESSION_COOKIE, admin.cookies[cloud_auth.SESSION_COOKIE])
        rule = self.client.post(
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
        self.client.cookies.set(cloud_auth.SESSION_COOKIE, admin.cookies[cloud_auth.SESSION_COOKIE])
        self.assertEqual(
            self.client.delete(
                "/api/cloud-auth/admin/grants/email/member%40example.org",
                headers={"Origin": ORIGIN},
            ).status_code,
            200,
        )
        self.assertIsNone(
            cloud_auth.resolve_session(member_cookie)
        )  # Explicit deny beats allowed domain.
        self.client.cookies.set(cloud_auth.SESSION_COOKIE, admin.cookies[cloud_auth.SESSION_COOKIE])
        lookalike = self.finish("member@notexample.org", "lookalike-sub")
        self.assertNotIn(cloud_auth.SESSION_COOKIE, lookalike.cookies)
        self.client.cookies.set(cloud_auth.SESSION_COOKIE, admin.cookies[cloud_auth.SESSION_COOKIE])
        removed = self.client.delete(
            "/api/cloud-auth/admin/grants/domain/example.org", headers={"Origin": ORIGIN}
        )
        self.assertEqual(removed.status_code, 200)
        self.assertIsNone(cloud_auth.resolve_session(member_cookie))

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
            "/api/projects/inspect?path=projects/rh.sigma",
            "/api/projects/research-sessions?path=projects/rh.sigma",
            "/api/projects/research-executions?path=projects/rh.sigma",
            "/api/projects/recent",
        ]:
            self.assertEqual(self.client.get(path).status_code, 401, path)
        rejected = self.client.post(
            "/api/projects/close",
            json={"path": "projects/rh.sigma"},
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
                "SIGMA_CLOUD_BOOTSTRAP_ADMIN_EMAIL": "",
                "SIGMA_CLOUD_AUTH_HOME": "",
                "SIGMA_CLOUD_ADMIN_CONTACT_EMAIL": "",
            },
        ):
            self.assertIsNotNone(cloud_auth.config().error)
            self.assertEqual(self.client.get("/api/projects/research-executions").status_code, 503)
        with patch.dict(os.environ, {"SIGMA_CLOUD_AUTH_ENABLED": "false"}):
            self.assertFalse(self.client.get("/api/cloud-auth/status").json()["enabled"])
            self.assertEqual(self.client.get("/api/research-tools").status_code, 200)


if __name__ == "__main__":
    main()
