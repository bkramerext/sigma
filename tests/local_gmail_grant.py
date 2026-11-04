"""Provider-free verification of private, account-bound Gmail Send grants."""

import json
import os
import stat
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from sigma.local_gmail_grant import GMAIL_SEND_SCOPE, grant_for_account, grant_path, save_grant


class LocalGmailGrantTests(unittest.TestCase):
    def test_grant_is_private_and_bound_to_sender_and_client(self):
        with TemporaryDirectory() as directory:
            home = Path(directory) / "auth"
            home.mkdir(mode=0o700)
            path = save_grant(
                home,
                subject="google-sub-123",
                sender="Sender@Example.org",
                client_id="local-web-client",
                client_secret="private-client-secret",
                refresh_token="private-refresh-token",
                scope="openid email profile " + GMAIL_SEND_SCOPE,
            )
            self.assertEqual(path, grant_path(home))
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            result = grant_for_account(home, email="sender@example.org", client_id="local-web-client")
            assert result is not None
            self.assertEqual(result[1]["subject"], "google-sub-123")
            self.assertIsNone(grant_for_account(home, email="other@example.org", client_id="local-web-client"))
            self.assertIsNone(grant_for_account(home, email="sender@example.org", client_id="other-client"))
            os.chmod(path, 0o644)
            self.assertIsNone(grant_for_account(home, email="sender@example.org", client_id="local-web-client"))

    def test_grant_requires_mail_scope_and_real_google_identity(self):
        with TemporaryDirectory() as directory:
            home = Path(directory) / "auth"
            home.mkdir(mode=0o700)
            with self.assertRaises(ValueError):
                save_grant(
                    home,
                    subject="local-admin:sender@example.org",
                    sender="sender@example.org",
                    client_id="id",
                    client_secret="secret",
                    refresh_token="refresh",
                    scope=GMAIL_SEND_SCOPE,
                )
            with self.assertRaises(ValueError):
                save_grant(
                    home,
                    subject="google-sub",
                    sender="sender@example.org",
                    client_id="id",
                    client_secret="secret",
                    refresh_token="refresh",
                    scope="openid email profile",
                )
            p = grant_path(home)
            p.write_text(json.dumps({"sender":"sender@example.org","client_id":"id"}))
            os.chmod(p, 0o600)
            self.assertIsNone(grant_for_account(home, email="sender@example.org", client_id="id"))


if __name__ == "__main__":
    unittest.main()
