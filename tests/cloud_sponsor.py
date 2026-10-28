"""No-network sponsor isolation, protected import, refresh, and no billing fallback."""

import os
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import IsolatedAsyncioTestCase, main
from unittest.mock import AsyncMock, patch

from sigma import (
    ai_store,
    chatgpt_auth,
    cloud_sponsor,
    openai_connection,
    research_sessions,
    sponsor_diagnostics,
)
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

    async def test_local_sponsor_requires_explicit_designated_identity(self):
        with patch.dict(
            os.environ,
            {
                "SIGMA_CLOUD_AUTH_ENABLED": "true",
                "SIGMA_CLOUD_AUTH_LOCAL": "true",
                "SIGMA_CLOUD_AUTH_HOME": str(self.root / "local-auth"),
            },
        ):
            os.environ.pop("SIGMA_CLOUD_SPONSOR_EMAIL", None)
            with self.assertRaisesRegex(ProjectError, "Configure the explicit"):
                cloud_sponsor.expected_email()
            os.environ.pop("SIGMA_CLOUD_INFERENCE_PROVIDER", None)
            self.assertEqual(cloud_sponsor.inference_provider(), "chatgpt")

    async def test_hosted_admin_connection_is_role_based(self):
        from types import SimpleNamespace

        from fastapi import HTTPException

        from sigma import api, cloud_auth

        principal = SimpleNamespace(
            role="admin", email="admin@example.test", subject="admin-subject"
        )
        request = SimpleNamespace(state=SimpleNamespace(cloud_principal=principal))
        cfg = SimpleNamespace(enabled=True, local=False)
        with (
            patch.object(cloud_auth, "config", return_value=cfg),
            patch.object(cloud_auth, "Principal", SimpleNamespace),
            patch.object(
                cloud_sponsor,
                "sponsor_account_id",
                AsyncMock(side_effect=ProjectError("missing")),
            ),
            patch.object(chatgpt_auth, "begin", AsyncMock(return_value={"id": "attempt"})) as begin,
        ):
            # The Google administrator identity is deliberately different from
            # the ChatGPT sponsor identity. Authorization is by verified role.
            result = await api.sponsor_auth_begin(request)
            self.assertEqual(result["id"], "attempt")
            begin.assert_awaited_once_with(account_id=None, sponsor=True)

            principal.role = "member"
            with self.assertRaises(HTTPException) as rejected:
                await api.sponsor_auth_begin(request)
            self.assertEqual(rejected.exception.status_code, 403)

    async def test_hosted_sponsor_oauth_callback_persists_connected_credentials(self):
        from urllib.parse import parse_qs, urlsplit

        from sigma import cloud_auth, cloud_workspaces

        with (
            patch.object(cloud_workspaces, "enabled", return_value=True),
            patch.object(
                cloud_auth,
                "config",
                return_value=type(
                    "Config",
                    (),
                    {"origin": "https://sigma.example.test", "local": False},
                )(),
            ),
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
                AsyncMock(return_value=(200, {"access_token": "oauth-access"})),
            ) as exchange,
            patch.object(
                chatgpt_auth,
                "validate_tokens",
                AsyncMock(return_value=self.account),
            ) as validate,
        ):
            started = await chatgpt_auth.begin(sponsor=True)
            authorization_url = chatgpt_auth.authorization_url(started["id"])
            params = parse_qs(urlsplit(authorization_url).query)
            attempt = chatgpt_auth._attempts[started["id"]]
            self.assertEqual(
                params["redirect_uri"],
                [f"https://sigma.example.test/api/ai/auth/callback/{started['id']}"],
            )

            await chatgpt_auth.hosted_callback(
                started["id"],
                f"state={attempt.state}&code=fixture-code&client_id=oaiapp_fixture",
            )

        self.assertEqual(chatgpt_auth.attempt_status(started["id"])["status"], "connected")
        exchange.assert_awaited_once()
        validate.assert_awaited_once()
        async with ai_store.sponsor_transaction() as persisted:
            # Re-read through the store service after OAuth completion; the
            # connection state must come from the saved sponsor record.
            self.assertEqual(len(persisted["accounts"]), 1)
            saved = next(iter(persisted["accounts"].values()))
            self.assertEqual(saved["access_token"], "fixture-access")
            self.assertEqual(saved["email"], "sponsor@example.test")
        connected = await cloud_sponsor.sponsor_session()
        self.assertEqual(connected["status"], "connected")

    async def test_hosted_sponsor_connection_reads_saved_credentials(self):
        async with ai_store.sponsor_transaction() as state:
            state["accounts"]["sponsor"] = dict(self.account)
            state["active"] = "sponsor"
            state["mode"] = "chatgpt"
        result = await cloud_sponsor.sponsor_session()
        self.assertEqual(result["status"], "connected")
        self.assertEqual(result["account"]["email"], "sponsor@example.test")

    async def test_personal_connection_identifies_selected_designated_sponsor(self):
        from sigma import cloud_workspaces

        with (
            patch.object(cloud_workspaces, "enabled", return_value=False),
            patch.object(
                chatgpt_auth,
                "preferences",
                AsyncMock(
                    return_value={
                        "mode": "chatgpt",
                        "active_account": "sponsor",
                        "accounts": [],
                        "welcome_pending": False,
                    }
                ),
            ),
        ):
            result = await openai_connection.connection(
                context={
                    "identity": "local_personal_unconnected",
                    "token": "",
                    "mode": "chatgpt",
                    "status": "disconnected",
                    "account_label": None,
                }
            )
        self.assertTrue(result["sponsor_account_selected"])

    async def test_hosted_sponsor_defaults_to_chatgpt_without_api_billing(self):
        with patch.dict(
            os.environ,
            {
                "SIGMA_CLOUD_AUTH_LOCAL": "false",
                "SIGMA_CLOUD_SPONSOR_EMAIL": "zetacontinuation@gmail.com",
                "SIGMA_CLOUD_OPENAI_API_KEY": "must-not-be-used",
            },
        ):
            os.environ.pop("SIGMA_CLOUD_INFERENCE_PROVIDER", None)
            self.assertEqual(cloud_sponsor.inference_provider(), "chatgpt")
            self.assertEqual(cloud_sponsor.expected_email(), "zetacontinuation@gmail.com")
            with patch.object(
                cloud_sponsor,
                "sponsor_session",
                AsyncMock(return_value={"status": "disconnected"}),
            ) as sponsor:
                context = await self.sponsor_context()
            sponsor.assert_awaited_once()
            self.assertEqual(context["mode"], "chatgpt")
            self.assertEqual(context["status"], "disconnected")
            self.assertEqual(context["token"], "")

    async def test_local_service_key_requires_explicit_provider_and_dedicated_secret(self):
        with (
            patch.dict(
                os.environ,
                {
                    "SIGMA_CLOUD_AUTH_LOCAL": "true",
                    "SIGMA_CLOUD_INFERENCE_PROVIDER": "api_key",
                    "SIGMA_CLOUD_OPENAI_API_KEY": "fixture-sponsored-key",
                },
            ),
            patch.object(cloud_sponsor, "sponsor_session", AsyncMock()) as session,
        ):
            self.assertEqual(cloud_sponsor.inference_provider(), "api_key")
            context = await self.sponsor_context()
            session.assert_not_called()
            self.assertEqual(context["mode"], "api_key")
            self.assertEqual(context["status"], "connected")
            self.assertEqual(context["token"], "fixture-sponsored-key")
            self.assertTrue(openai_connection.cloud_credential(context))

            os.environ.pop("SIGMA_CLOUD_OPENAI_API_KEY")
            unconfigured = await self.sponsor_context()
            self.assertEqual(unconfigured["status"], "unconfigured")
            self.assertEqual(unconfigured["token"], "")
            with patch.object(
                chatgpt_auth,
                "preferences",
                AsyncMock(
                    side_effect=AssertionError("sponsored service key read ChatGPT preferences")
                ),
            ):
                state = await openai_connection.connection(context=unconfigured)
            self.assertEqual(state["mode"], "api_key")
            self.assertEqual(state["accounts"], [])

            os.environ["SIGMA_CLOUD_INFERENCE_PROVIDER"] = "invalid"
            invalid = await self.sponsor_context()
            self.assertEqual(invalid["status"], "unavailable")
            self.assertEqual(invalid["token"], "")

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
            sponsor_diagnostics.record("sponsor_play", "http_400")
            self.assertTrue(path.is_file())
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertIn("sponsor_connection status=credential_missing", path.read_text())
            self.assertIn("sponsor_play status=http_400", path.read_text())
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

    async def test_sponsored_inference_diagnostics_record_only_fixed_status_codes(self):
        with patch.object(sponsor_diagnostics, "record") as write_diagnostic:
            research_sessions._sponsor_inference_diagnostic(
                {"cloud_sponsored": False}, "call_started"
            )
            write_diagnostic.assert_not_called()
            research_sessions._sponsor_inference_diagnostic(
                {"cloud_sponsored": True}, "http_403_subscription_sharing_unsupported_capability"
            )
        write_diagnostic.assert_called_once_with(
            "sponsor_inference", "http_403_subscription_sharing_unsupported_capability"
        )

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
