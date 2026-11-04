# ruff: noqa: F401, I001
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

# The authorization fixture tests research roles without a compiler provider.
os.environ.setdefault("SIGMA_REFERENCE_COMPILATION_ENABLED", "false")

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


class CloudAuthFixture(TestCase):
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

