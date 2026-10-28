"""Hosted personal adapter isolation and explicit connection routing checks."""

from __future__ import annotations

import asyncio
import os
import tempfile
import time
from pathlib import Path
from unittest import TestCase, main
from unittest.mock import AsyncMock, patch

from sigma import (
    ai_store,
    chatgpt_auth,
    cloud_auth,
    cloud_workspaces,
    openai_connection,
)


class HostedPersonalIsolationTests(TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="sigma-cloud-personal-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.root.chmod(0o700)
        for name in ("auth", "workspaces", "sponsor"):
            (self.root / name).mkdir(mode=0o700)
        self.env = {
            "SIGMA_CLOUD_AUTH_ENABLED": "true",
            "SIGMA_CLOUD_AUTH_LOCAL": "false",
            "GOOGLE_OIDC_CLIENT_ID": "fixture.apps.googleusercontent.com",
            "GOOGLE_OIDC_CLIENT_SECRET": "fixture-secret",
            "SIGMA_CLOUD_PUBLIC_ORIGIN": "https://sigma.test",
            "SIGMA_CLOUD_ADMIN_CONTACT_EMAIL": "admin@example.test",
            "SIGMA_CLOUD_AUTH_HOME": str(self.root / "auth"),
            "SIGMA_CLOUD_WORKSPACES_ROOT": str(self.root / "workspaces"),
            "SIGMA_CLOUD_CHATGPT_AUTH_HOME": str(self.root / "sponsor"),
            "SIGMA_CLOUD_OPENAI_API_KEY": "fixture-sponsor-key",
            "SIGMA_CLOUD_INFERENCE_PROVIDER": "api_key",
        }
        self.old_env = {key: os.environ.get(key) for key in self.env}
        os.environ.update(self.env)
        self.addCleanup(self._restore_env)
        self.cfg = cloud_auth.config()
        assert self.cfg.database is not None
        cloud_auth._initialize(self.cfg.database)
        self.a = cloud_auth.Principal("google-subject-A", "a@example.test", "member")
        self.b = cloud_auth.Principal("google-subject-B", "b@example.test", "member")
        cloud_auth._persist_user_state(self.cfg, self.a)
        cloud_auth._persist_user_state(self.cfg, self.b)
        # Exercise hosted personal isolation after an explicit choice. Eligible
        # accounts now begin in sponsored mode until the user selects personal.
        cloud_auth.set_model_access(self.a.subject, "personal")
        cloud_auth.set_model_access(self.b.subject, "personal")

    def _restore_env(self):
        for key, value in self.old_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def _with_subject(self, principal, operation):
        token = cloud_workspaces.bind(principal)
        try:
            return operation()
        finally:
            cloud_workspaces.reset(token)

    def test_verified_subject_scoped_credential_store_and_selection(self):
        async def save(principal, token_value):
            async with ai_store.transaction() as state:
                state["accounts"] = {"private": {"access_token": token_value}}
                state["active"] = "private"

        self._with_subject(self.a, lambda: asyncio.run(save(self.a, "credential-A")))
        self._with_subject(self.b, lambda: asyncio.run(save(self.b, "credential-B")))

        async def load(principal):
            async with ai_store.transaction() as state:
                return state["accounts"][state["active"]]["access_token"]

        self.assertEqual(
            self._with_subject(self.a, lambda: asyncio.run(load(self.a))), "credential-A"
        )
        self.assertEqual(
            self._with_subject(self.b, lambda: asyncio.run(load(self.b))), "credential-B"
        )
        a_path = self.root / "sponsor" / "personal-users"
        directories = list(a_path.iterdir())
        self.assertEqual(len(directories), 2)
        self.assertNotEqual(directories[0].name, directories[1].name)
        self.assertNotIn("google-subject-A", str(directories))
        self.assertNotIn("a@example.test", str(directories))

        async def auth_for(principal):
            return await openai_connection.auth_context()

        personal_a = self._with_subject(self.a, lambda: asyncio.run(auth_for(self.a)))
        self.assertEqual(personal_a["status"], "unavailable")
        self.assertEqual(personal_a["token"], "")
        self.assertTrue(personal_a["identity"].startswith("cloud_personal_unavailable:"))
        self.assertFalse(openai_connection.cloud_credential(personal_a))
        selected_personal = asyncio.run(openai_connection.models(context=personal_a))
        self.assertEqual(selected_personal["connection"]["status"], "unavailable")

        cloud_auth.set_model_access(self.a.subject, "sponsored")
        self.assertEqual(cloud_auth.model_access_for_subject(self.b.subject), "personal")
        sponsored_a = self._with_subject(self.a, lambda: asyncio.run(auth_for(self.a)))
        self.assertTrue(openai_connection.cloud_credential(sponsored_a))
        self.assertEqual(sponsored_a["token"], "fixture-sponsor-key")
        cloud_auth.set_model_access(self.a.subject, "personal")
        restored_personal = self._with_subject(self.a, lambda: asyncio.run(auth_for(self.a)))
        personal_b = self._with_subject(self.b, lambda: asyncio.run(auth_for(self.b)))
        self.assertEqual(restored_personal["token"], "")
        self.assertEqual(personal_b["token"], "")
        self.assertEqual(cloud_auth.model_access_for_subject(self.a.subject), "personal")
        self.assertEqual(cloud_auth.model_access_for_subject(self.b.subject), "personal")
        self.assertFalse(openai_connection.cloud_credential(restored_personal))
        self.assertEqual(
            self._with_subject(self.a, lambda: asyncio.run(load(self.a))), "credential-A"
        )
        self.assertEqual(
            self._with_subject(self.b, lambda: asyncio.run(load(self.b))), "credential-B"
        )
        self.assertNotIn("credential-A", repr(personal_a))
        self.assertNotIn("credential-B", repr(personal_b))

    def test_sponsor_store_is_independent_of_subject_context(self):
        async def write_stores(principal):
            async with ai_store.sponsor_transaction() as sponsor:
                sponsor["accounts"] = {"designated-sponsor": {"access_token": "sponsor-only"}}
            async with ai_store.transaction() as personal:
                personal["accounts"] = {"personal": {"access_token": "personal-only"}}

        self._with_subject(self.a, lambda: asyncio.run(write_stores(self.a)))

        async def check():
            async with ai_store.sponsor_transaction() as sponsor:
                return sponsor["accounts"]["designated-sponsor"]["access_token"]

        self.assertEqual(asyncio.run(check()), "sponsor-only")
        self.assertFalse(
            (self.root / "sponsor" / "credentials.json").read_text().find("personal-only") >= 0
        )

    def test_rotating_refresh_stays_inside_each_verified_subject_store(self):
        async def save(principal, email):
            async with ai_store.transaction() as state:
                state["mode"] = "chatgpt"
                state["active"] = "account"
                state["accounts"] = {
                    "account": {
                        "client_id": "oaiapp_fixture",
                        "subject": email,
                        "email": email,
                        "access_token": "expired-" + email,
                        "refresh_token": "refresh-" + email,
                        "id_token": "id-" + email,
                        "expires_at": 0,
                        "earliest_refresh_at": 0,
                        "scopes": ["chatgpt.tokens.use.direct", "resource.invoke"],
                    }
                }

        self._with_subject(self.a, lambda: asyncio.run(save(self.a, "a@example.test")))
        self._with_subject(self.b, lambda: asyncio.run(save(self.b, "b@example.test")))

        async def refreshed(raw, client_id, nonce, existing, host_id):
            email = existing["email"]
            return existing | {
                "access_token": "rotated-" + email,
                "refresh_token": "next-" + email,
                "expires_at": time.time() + 3600,
            }

        async def refresh(principal):
            token = cloud_workspaces.bind(principal)
            try:
                return await chatgpt_auth.session()
            finally:
                cloud_workspaces.reset(token)

        with (
            patch.object(chatgpt_auth, "discovery", AsyncMock(return_value={})),
            patch.object(chatgpt_auth, "http", AsyncMock(return_value=(200, {}))),
            patch.object(chatgpt_auth, "validate_tokens", AsyncMock(side_effect=refreshed)),
        ):
            result_a = asyncio.run(refresh(self.a))
            result_b = asyncio.run(refresh(self.b))
        self.assertEqual(result_a["account"]["access_token"], "rotated-a@example.test")
        self.assertEqual(result_b["account"]["access_token"], "rotated-b@example.test")

        async def stored(principal):
            async with ai_store.transaction() as state:
                return state["accounts"]["account"]["refresh_token"]

        self.assertEqual(
            self._with_subject(self.a, lambda: asyncio.run(stored(self.a))), "next-a@example.test"
        )
        self.assertEqual(
            self._with_subject(self.b, lambda: asyncio.run(stored(self.b))), "next-b@example.test"
        )


if __name__ == "__main__":
    main()
