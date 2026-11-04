"""Offline tests of the one-command local Google Gmail Send OAuth flow."""

from __future__ import annotations

import json
import os
import stat
import threading
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from urllib.parse import parse_qs, urlencode, urlsplit
from urllib.request import urlopen

import httpx
from cloud_auth_fixture import CLIENT_ID, JWK, token
from sigma import local_gmail_cli_auth as auth


class GoogleClient:
    id_token = ""

    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def post(self, url, data):
        assert url == auth.GOOGLE_TOKEN
        assert data["grant_type"] == "authorization_code"
        assert data["code_verifier"]
        assert data["redirect_uri"] == auth.REDIRECT_URI
        return httpx.Response(
            200,
            request=httpx.Request("POST", url),
            json={
                "id_token": self.id_token,
                "scope": "openid email profile " + auth.GMAIL_SEND_SCOPE,
                "refresh_token": "fixture-private-refresh",
            },
        )

    def get(self, url):
        if url == auth.GOOGLE_DISCOVERY:
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


class LocalGmailCliAuthTests(unittest.TestCase):
    def test_full_cli_browser_roundtrip_validates_selected_google_account(self):
        with TemporaryDirectory() as directory:
            home = Path(directory) / "local-auth"
            callbacks = []
            callback_done = threading.Event()

            def open_browser(url, new=2):
                params = parse_qs(urlsplit(url).query)
                self.assertEqual(params["redirect_uri"], [auth.REDIRECT_URI])
                self.assertEqual(params["access_type"], ["offline"])
                self.assertEqual(params["prompt"], ["consent select_account"])
                self.assertIn(auth.GMAIL_SEND_SCOPE, params["scope"][0])
                GoogleClient.id_token = token(
                    nonce=params["nonce"][0],
                    email="selected-google@example.org",
                    subject="other-google-subject",
                    aud=CLIENT_ID,
                )
                query = urlencode({"state": params["state"][0], "code": "fixture-code"})

                def callback():
                    try:
                        with urlopen(auth.REDIRECT_URI + "?" + query, timeout=5) as response:
                            callbacks.append(response.status)
                    finally:
                        callback_done.set()

                threading.Thread(target=callback, daemon=True).start()
                return True

            with (
                patch.dict(
                    os.environ,
                    {
                        "GOOGLE_OIDC_CLIENT_ID": CLIENT_ID,
                        "GOOGLE_OIDC_CLIENT_SECRET": "fixture-client-secret",
                        "SIGMA_CLOUD_AUTH_HOME": str(home),
                        "SIGMA_CLOUD_ADMIN_CONTACT_EMAIL": "admin@example.org",
                    },
                    clear=True,
                ),
                patch.object(auth.httpx, "Client", GoogleClient),
                patch.object(auth.webbrowser, "open", side_effect=open_browser),
            ):
                path, sender = auth.authorize()
                self.assertEqual(sender, "selected-google@example.org")
                self.assertEqual(stat.S_IMODE(home.stat().st_mode), 0o700)
                self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
                self.assertTrue(callback_done.wait(2))
                self.assertEqual(callbacks, [200])
                self.assertEqual(auth.existing_grant(), (path, sender))
                saved = json.loads(path.read_text())
                self.assertEqual(saved["subject"], "other-google-subject")
                self.assertEqual(saved["refresh_token"], "fixture-private-refresh")
                self.assertNotIn("access_token", saved)
                self.assertNotIn("id_token", saved)
                os.chmod(path, 0o644)
                self.assertIsNone(auth.existing_grant())

    def test_identity_token_nonce_or_signature_mismatch_cannot_be_saved(self):
        with TemporaryDirectory() as directory:
            home = Path(directory) / "local-auth"
            home.mkdir(mode=0o700)
            with patch.dict(os.environ, {"SIGMA_CLOUD_AUTH_HOME": str(home)}, clear=True):
                GoogleClient.id_token = token(
                    nonce="incorrect", email="admin@example.org", aud=CLIENT_ID
                )
                with GoogleClient() as client, self.assertRaises(auth.LocalGmailAuthError):
                    auth._verified_google_identity(
                        client, GoogleClient.id_token, client_id=CLIENT_ID, nonce="expected"
                    )
                self.assertFalse((home / auth.GRANT_FILENAME).exists())

    def test_cannot_read_grant_for_a_different_local_google_client(self):
        with TemporaryDirectory() as directory:
            home = Path(directory) / "local-auth"
            home.mkdir(mode=0o700)
            with patch.dict(
                os.environ,
                {"GOOGLE_OIDC_CLIENT_ID": CLIENT_ID, "SIGMA_CLOUD_AUTH_HOME": str(home)},
                clear=True,
            ):
                auth._save_grant(
                    sender="signed-in@example.org",
                    subject="sub",
                    client_id=CLIENT_ID,
                    client_secret="private",
                    refresh_token="private-refresh",
                    scope=auth.GMAIL_SEND_SCOPE,
                )
                self.assertIsNotNone(auth.existing_grant())
                os.environ["GOOGLE_OIDC_CLIENT_ID"] = "a-different-client"
                self.assertIsNone(auth.existing_grant())


if __name__ == "__main__":
    unittest.main()
