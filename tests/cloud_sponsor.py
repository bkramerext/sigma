"""No-network sponsor isolation, protected import, refresh, and no billing fallback."""

import os
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import IsolatedAsyncioTestCase, main
from unittest.mock import AsyncMock, patch

from sigma import ai_store, chatgpt_auth, cloud_sponsor, openai_connection, sponsor_diagnostics
from sigma.projects import ProjectError


class SponsorTests(IsolatedAsyncioTestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.target = self.root / "sponsor"
        self.env = patch.dict(
            os.environ,
            {
                "SIGMA_CLOUD_AUTH_ENABLED": "true",
                "SIGMA_CLOUD_AUTH_LOCAL": "false",
                "SIGMA_CLOUD_INFERENCE_PROVIDER": "chatgpt",
                "SIGMA_CLOUD_SPONSOR_EMAIL": "sponsor@example.test",
                "SIGMA_CLOUD_CHATGPT_AUTH_HOME": str(self.target),
                "SIGMA_AUTH_HOME": str(self.root / "local-must-not-be-used"),
                "OPENAI_API_KEY": "local-key-must-not-be-used",
                "SIGMA_CLOUD_OPENAI_API_KEY": "service-key-must-not-be-used",
            },
        )
        self.env.start()
        self.addCleanup(self.env.stop)
        self.account = {
            "client_id": "oaiapp_fixture",
            "subject": "sponsor-subject",
            "email": "sponsor@example.test",
            "issuer": chatgpt_auth.ISSUER,
            "access_token": "fixture-access",
            "refresh_token": "fixture-refresh",
            "id_token": "fixture-id",
            "token_type": "Bearer",
            "scopes": list(chatgpt_auth.PLAN_SCOPES),
            "expires_at": time.time() + 3600,
        }
        self.claims = {
            "sub": "sponsor-subject",
            "email": "sponsor@example.test",
            "email_verified": True,
        }

    def source(self):
        path = self.root / "transfer.json"
        ai_store.write(
            path,
            {
                "version": 1,
                "ext_agent_host_id": "urn:uuid:laptop",
                "mode": "chatgpt",
                "active": "selected",
                "accounts": {"selected": self.account, "other": {"email": "other"}},
            },
        )
        return path

    async def sponsor_context(self):
        return await openai_connection.sponsored_auth_context("a" * 64)

    async def test_local_sponsor_defaults_to_the_designated_admin_identity(self):
        from sigma import cloud_auth

        with patch.dict(
            os.environ,
            {
                "SIGMA_CLOUD_AUTH_ENABLED": "true",
                "SIGMA_CLOUD_AUTH_LOCAL": "true",
                "SIGMA_CLOUD_AUTH_HOME": str(self.root / "local-auth"),
            },
        ):
            os.environ.pop("SIGMA_CLOUD_SPONSOR_EMAIL", None)
            self.assertEqual(cloud_sponsor.expected_email(), cloud_auth.INVITATION_RECIPIENT)
            os.environ.pop("SIGMA_CLOUD_INFERENCE_PROVIDER", None)
            self.assertEqual(cloud_sponsor.inference_provider(), "chatgpt")

    async def test_missing_session_never_uses_local_or_service_credentials(self):
        with (
            patch.object(cloud_sponsor, "_last_issue", None),
            patch.object(cloud_sponsor, "record") as record,
        ):
            context = await self.sponsor_context()
            await self.sponsor_context()
        record.assert_called_once_with("sponsor_connection", "registration_missing")
        self.assertEqual(context["mode"], "chatgpt")
        self.assertEqual(context["status"], "disconnected")
        self.assertEqual(context["token"], "")
        self.assertFalse((self.root / "local-must-not-be-used").exists())

    async def test_local_diagnostics_are_private_bounded_and_token_free(self):
        path = self.root / sponsor_diagnostics.LOG_NAME
        with (
            patch.dict(os.environ, {"SIGMA_CLOUD_AUTH_LOCAL": "true"}),
            patch.object(sponsor_diagnostics, "ROOT", self.root),
            patch.object(sponsor_diagnostics._LOG, "warning") as warning,
        ):
            sponsor_diagnostics.record("sponsor_connection", "credential_missing")
            self.assertTrue(path.is_file())
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertIn("sponsor_connection status=credential_missing", path.read_text())
            self.assertNotIn(self.account["email"], path.read_text())
            self.assertNotIn(self.account["access_token"], path.read_text())
            path.write_bytes(b"x" * 65536)
            sponsor_diagnostics.record("sponsor_oauth", "started")
            self.assertLess(path.stat().st_size, 256)
            self.assertIn("sponsor_oauth status=started", path.read_text())
            path.unlink()
            target = self.root / "protected-target"
            target.write_text("unchanged")
            path.symlink_to(target)
            sponsor_diagnostics.record("sponsor_connection", "credential_missing")
            self.assertEqual(target.read_text(), "unchanged")
            self.assertIn("sponsor_diagnostics status=file_unavailable", str(warning.call_args))

    async def test_designated_sponsor_is_used_when_a_personal_account_is_active(self):
        personal = dict(self.account, email="personal@example.test", subject="personal-subject")
        async with ai_store.sponsor_transaction() as state:
            state["mode"] = "chatgpt"
            state["active"] = "personal"
            state["accounts"] = {"personal": personal, "sponsor": self.account}
        selected = await cloud_sponsor.sponsor_session()
        self.assertEqual(selected["status"], "connected")
        self.assertEqual(selected["account_id"], "sponsor")
        self.assertEqual(selected["account"]["email"], "sponsor@example.test")
        async with ai_store.sponsor_transaction() as state:
            self.assertEqual(state["active"], "personal")

    async def test_duplicate_sponsor_prefers_usable_account_after_personal_billing_choice(self):
        stale = dict(self.account)
        stale.pop("access_token")
        stale.pop("refresh_token")
        async with ai_store.sponsor_transaction() as state:
            state["mode"] = "api_key"
            state["active"] = "stale"
            state["accounts"] = {"stale": stale, "usable": self.account}
        self.assertEqual(await cloud_sponsor.sponsor_account_id(), "usable")
        selected = await cloud_sponsor.sponsor_session()
        self.assertEqual(selected["status"], "connected")
        self.assertEqual(selected["account_id"], "usable")
        self.assertEqual(selected["account"]["email"], "sponsor@example.test")

    async def test_import_selected_account_preserves_vm_host_and_is_used(self):
        async with ai_store.transaction() as state:
            host = state["ext_agent_host_id"]
        with patch.object(chatgpt_auth, "verify_id", AsyncMock(return_value=self.claims)):
            await cloud_sponsor.import_session(self.source())
        async with ai_store.transaction() as state:
            self.assertEqual(state["ext_agent_host_id"], host)
            self.assertEqual(len(state["accounts"]), 1)
            self.assertEqual(state["accounts"][state["active"]]["ext_agent_host_id"], host)
        context = await self.sponsor_context()
        self.assertEqual(context["token"], "fixture-access")
        self.assertEqual(context["status"], "connected")
        self.assertNotIn("fixture-access", repr(context))
        self.assertNotIn("sponsor@example.test", repr(context))

    async def test_invalid_import_retains_existing_state(self):
        async with ai_store.transaction():
            pass
        before = (self.target / "credentials.json").read_bytes()
        for changes in (
            {"email": "other@example.test"},
            {"email_verified": False},
            {"sub": "other"},
        ):
            with (
                patch.object(
                    chatgpt_auth, "verify_id", AsyncMock(return_value=self.claims | changes)
                ),
                self.assertRaises(ProjectError),
            ):
                await cloud_sponsor.import_session(self.source())
            self.assertEqual((self.target / "credentials.json").read_bytes(), before)
        self.account["scopes"] = []
        with (
            patch.object(chatgpt_auth, "verify_id", AsyncMock(return_value=self.claims)),
            self.assertRaises(ProjectError),
        ):
            await cloud_sponsor.import_session(self.source())
        self.assertEqual((self.target / "credentials.json").read_bytes(), before)

    async def test_wrong_saved_sponsor_is_not_refreshed(self):
        async with ai_store.transaction() as state:
            state["active"] = "wrong"
            state["accounts"] = {"wrong": self.account | {"email": "other@example.test"}}
        with patch.object(chatgpt_auth, "session", AsyncMock()) as session:
            context = await self.sponsor_context()
            session.assert_not_called()
        self.assertEqual(context["token"], "")

    async def test_model_catalog_uses_sponsor_token_without_exposing_identity(self):
        import httpx

        from sigma.model_catalog import CATALOG

        async with ai_store.transaction() as state:
            state["active"] = "sponsor"
            state["accounts"] = {"sponsor": self.account}
        real_client = httpx.AsyncClient
        calls = []

        def handler(request):
            calls.append(request.url.path)
            self.assertEqual(request.headers["authorization"], "Bearer fixture-access")
            return httpx.Response(
                200,
                json={
                    "models": [
                        {"slug": key, "display_name": key, "visibility": "list"} for key in CATALOG
                    ]
                },
            )

        openai_connection._identity = ""
        openai_connection._cached = None
        with patch.object(
            openai_connection.httpx,
            "AsyncClient",
            side_effect=lambda **kwargs: real_client(
                transport=httpx.MockTransport(handler), **kwargs
            ),
        ):
            result = await openai_connection.models(context=await self.sponsor_context())
        self.assertEqual(calls, ["/v1/models"])
        self.assertTrue(result["default_verified"])
        self.assertEqual(result["connection"]["accounts"], [])
        self.assertIsNone(result["connection"]["active_account"])
        self.assertNotIn("fixture-access", str(result))
        self.assertNotIn("sponsor@example.test", str(result))

    async def test_refresh_rotation_and_terminal_failure_never_fall_back(self):
        async with ai_store.transaction() as state:
            state["active"] = "sponsor"
            state["accounts"] = {"sponsor": self.account | {"expires_at": 0}}
        replacement = self.account | {
            "access_token": "rotated-access",
            "refresh_token": "rotated-refresh",
        }
        with (
            patch.object(chatgpt_auth, "discovery", AsyncMock(return_value={})),
            patch.object(chatgpt_auth, "http", AsyncMock(return_value=(200, {}))),
            patch.object(chatgpt_auth, "validate_tokens", AsyncMock(return_value=replacement)),
        ):
            context = await self.sponsor_context()
        self.assertEqual(context["token"], "rotated-access")
        async with ai_store.transaction() as state:
            self.assertEqual(state["accounts"]["sponsor"]["refresh_token"], "rotated-refresh")
            state["accounts"]["sponsor"]["expires_at"] = 0
        with (
            patch.object(chatgpt_auth, "discovery", AsyncMock(return_value={})),
            patch.object(
                chatgpt_auth, "http", AsyncMock(return_value=(400, {"error": "invalid_grant"}))
            ),
        ):
            context = await self.sponsor_context()
        self.assertEqual(context["status"], "reauth_required")
        self.assertEqual(context["token"], "")

    async def test_dispatch_rejects_local_accounts_and_billing_mode_mismatch(self):
        valid = {
            "mode": "chatgpt",
            "identity": "cloud_sponsor:fixture",
            "status": "connected",
            "token": "fixture",
        }
        self.assertTrue(openai_connection.cloud_credential(valid))
        for changes in (
            {"identity": "chatgpt:local"},
            {"mode": "api_key"},
            {"status": "reauth_required"},
            {"token": ""},
        ):
            self.assertFalse(openai_connection.cloud_credential(valid | changes))
        with patch.dict(os.environ, {"SIGMA_CLOUD_INFERENCE_PROVIDER": "api_key"}):
            self.assertFalse(openai_connection.cloud_credential(valid))

    async def test_private_import_and_explicit_mode_required(self):
        source = self.source()
        source.chmod(0o644)
        with self.assertRaises(ProjectError):
            await cloud_sponsor.import_session(source)
        with (
            patch.dict(os.environ, {"SIGMA_CLOUD_INFERENCE_PROVIDER": "api_key"}),
            self.assertRaises(ProjectError),
        ):
            await cloud_sponsor.import_session(source)


if __name__ == "__main__":
    main()
