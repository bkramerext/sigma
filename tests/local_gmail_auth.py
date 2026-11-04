"""Verify the existing UI's local Google identity can separately consent to Gmail Send."""

from __future__ import annotations

import os
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

import httpx

from cloud_auth_fixture import CloudAuthFixture, GoogleClient, token
from sigma import cloud_auth
from sigma.local_gmail_grant import GMAIL_SEND_SCOPE, grant_for_account


class MailGoogleClient(GoogleClient):
    scope = "openid email profile " + GMAIL_SEND_SCOPE
    refresh = "private-local-refresh-token"

    async def post(self, url, data):
        assert url == "https://oauth2.googleapis.com/token"
        assert data["code_verifier"]
        return httpx.Response(
            200,
            request=httpx.Request("POST", url),
            json={"id_token": self.token, "scope": self.scope, "refresh_token": self.refresh},
        )


class LocalMailAuthorizationTests(CloudAuthFixture):
    def local_auth_environment(self):
        return patch.dict(
            os.environ,
            {
                "SIGMA_CLOUD_AUTH_LOCAL": "true",
                "SIGMA_CLOUD_PUBLIC_ORIGIN": "http://127.0.0.1:5173",
            },
        )

    def begin_local_mail(self):
        signed = self.finish(email="admin@example.org", subject="google-mail-admin")
        cfg = cloud_auth.config()
        cookie_name = cloud_auth._cookie_name(cloud_auth.SESSION_COOKIE, cfg)
        self.client.cookies.set(cookie_name, signed.cookies[cookie_name])
        response = self.client.get("/api/cloud-auth/mail/authorize", follow_redirects=False)
        self.assertEqual(response.status_code, 302, response.text)
        query = parse_qs(urlsplit(response.headers["location"]).query)
        self.assertEqual(query["access_type"], ["offline"])
        self.assertEqual(query["prompt"], ["consent select_account"])
        self.assertIn(GMAIL_SEND_SCOPE, query["scope"][0])
        self.assertEqual(query["redirect_uri"], ["http://127.0.0.1:5173/api/cloud-auth/callback"])
        state = query["state"][0]
        with cloud_auth._db(cfg) as db:
            nonce = db.execute(
                "SELECT nonce FROM flows WHERE state_hash=?", (cloud_auth._hash(state),)
            ).fetchone()["nonce"]
        flow_cookie = cloud_auth._cookie_name(cloud_auth.FLOW_COOKIE, cfg)
        self.client.cookies.set(flow_cookie, response.cookies[flow_cookie])
        return state, nonce

    def finish_local_mail(self, state, nonce, *, subject="google-mail-admin", email="admin@example.org"):
        MailGoogleClient.token = token(nonce=nonce, email=email, subject=subject)
        with patch.object(cloud_auth.httpx, "AsyncClient", MailGoogleClient):
            return self.client.get(
                "/api/cloud-auth/callback",
                params={"state": state, "code": "fixture"},
                follow_redirects=False,
            )

    def test_reuses_signed_in_google_account_and_saves_private_scoped_grant(self):
        with self.local_auth_environment():
            state, nonce = self.begin_local_mail()
            response = self.finish_local_mail(state, nonce)
            self.assertEqual(response.status_code, 303, response.text)
            self.assertEqual(response.headers["location"], "/?gmail_send=authorized")
            matched = grant_for_account(
                self.root, email="admin@example.org", client_id="sigma-test.apps.googleusercontent.com"
            )
            self.assertIsNotNone(matched)
            assert matched is not None
            self.assertEqual(matched[1]["subject"], "google-mail-admin")
            self.assertEqual(cloud_auth.email_env("GMAIL_TOKEN_FILE"), str(matched[0]))
            self.assertEqual(cloud_auth.email_env("GMAIL_SENDER"), "admin@example.org")
            self.assertIsNotNone(
                cloud_auth.resolve_session(self.client.cookies.get("sigma_session"))
            )

    def test_refuses_a_different_google_identity_at_callback(self):
        with self.local_auth_environment():
            state, nonce = self.begin_local_mail()
            response = self.finish_local_mail(state, nonce, subject="another-google-subject")
            self.assertEqual(response.status_code, 403, response.text)
            self.assertIsNone(
                grant_for_account(
                    self.root, email="admin@example.org", client_id="sigma-test.apps.googleusercontent.com"
                )
            )

    def test_refuses_missing_gmail_scope(self):
        with self.local_auth_environment():
            state, nonce = self.begin_local_mail()
            with patch.object(MailGoogleClient, "scope", "openid email profile"):
                response = self.finish_local_mail(state, nonce)
            self.assertEqual(response.status_code, 403, response.text)
            self.assertIsNone(
                grant_for_account(
                    self.root, email="admin@example.org", client_id="sigma-test.apps.googleusercontent.com"
                )
            )

    def test_hosted_app_never_offers_gmail_authorization(self):
        self.finish(email="admin@example.org", subject="hosted-admin")
        response = self.client.get("/api/cloud-auth/mail/authorize", follow_redirects=False)
        self.assertEqual(response.status_code, 404, response.text)

    def test_local_signin_shortcut_cannot_impersonate_google_consent(self):
        with (
            self.local_auth_environment(),
            patch.dict(os.environ, {"SIGMA_LOCAL_AUTO_ADMIN": "true"}),
        ):
            response = self.client.get("/api/cloud-auth/mail/authorize", follow_redirects=False)
        self.assertEqual(response.status_code, 403, response.text)
        self.assertIn("--signin", response.text)


if __name__ == "__main__":
    import unittest

    unittest.main()
