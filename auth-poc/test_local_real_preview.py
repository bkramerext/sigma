"""Offline acceptance of the local REAL ChatGPT sign-in preview, without provider calls.

Unlike the synthetic OAuth loopback test, this exercises the existing real
authorization routes under local-only gates. No genuine account or network
request is used in CI.
"""

from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx

import server
import model_gateway
from sigma import api, chatgpt_auth, cloud_auth, personal_browser, personal_inference
from sigma.projects import ProjectError


async def main() -> None:
    key = "a" * 64
    with patch.dict(
        os.environ,
        {
            "SIGMA_AUTH_POC_LOCAL_DOCKER": "1",
            "SIGMA_AUTH_POC_REAL_SIGNIN": "1",
            "SIGMA_AUTH_POC_RPC_KEY": key,
        },
    ):
        assert server.real_signin_enabled()
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=server.app),
            base_url="http://127.0.0.1:8001",
            follow_redirects=False,
        ) as client:
            page = await client.get("/")
            assert page.status_code == 200
            assert "Local ChatGPT connection preview" in page.text
            assert "Continue with ChatGPT" in page.text

            missing_origin = await client.post("/lab-painted")
            assert missing_origin.status_code == 403
            painted = await client.post(
                "/lab-painted", headers={"Origin": "http://127.0.0.1:8001"}
            )
            assert painted.status_code == 200

            attempt_id = "test-authorization-id"
            with patch.object(
                server.chatgpt_auth,
                "begin",
                new_callable=AsyncMock,
                return_value={"id": attempt_id},
            ) as begin:
                authorized = await client.post(
                    "/begin", headers={"Origin": "http://127.0.0.1:8001"}
                )
                assert authorized.status_code == 200
                assert authorized.json()["id"] == attempt_id
                begin.assert_awaited_once()

            with patch.object(
                server.chatgpt_auth, "authorization_url",
                return_value="https://auth.openai.com/authorize?state=example",
            ):
                chooser = await client.get("/open/" + attempt_id)
                assert chooser.status_code in (302, 303, 307, 308)
                assert chooser.headers["location"].startswith(
                    "https://auth.openai.com/"
                )
            with patch.object(server, "_saved_preview_is_authorized", return_value=True):
                server._ATTEMPT_ID = None
                preview = await client.get("/preview-state")
                assert preview.status_code == 200
                assert preview.json() == {"phase": "connected"}

        assert model_gateway._valid_rpc_key(
            type("RequestStub", (), {"headers": {"x-sigma-worker-key": key}})()
        )
        assert not model_gateway._valid_rpc_key(
            type("RequestStub", (), {"headers": {}})()
        )
        assert not model_gateway._valid_rpc_key(
            type("RequestStub", (), {"headers": {"x-sigma-worker-key": "0" * 64}})()
        )

    # A saved local user selection must reconnect after the normal launcher
    # stops and restarts its private Docker browser/worker containers.
    principal = cloud_auth.Principal("test-user", "test@example.com", "admin")
    with (
        patch.object(personal_browser, "sign_in_preview_enabled", return_value=True),
        patch.object(
            personal_browser,
            "model_socket",
            new_callable=AsyncMock,
            side_effect=[
                personal_browser.PersonalBrowserUnavailable("worker stopped"),
                "/tmp/private-restored-model.sock",
            ],
        ) as model_socket,
        patch.object(
            personal_browser,
            "session",
            new_callable=AsyncMock,
            return_value={"browser_status": "ready"},
        ) as restore,
    ):
        restored = await personal_inference._socket(principal)
        assert restored == "/tmp/private-restored-model.sock"
        assert model_socket.await_count == 2
        restore.assert_awaited_once_with(principal, action="start")

    with (
        patch.object(personal_browser, "sign_in_preview_enabled", return_value=False),
        patch.object(
            personal_browser,
            "model_socket",
            new_callable=AsyncMock,
            side_effect=personal_browser.PersonalBrowserUnavailable("worker stopped"),
        ),
        patch.object(
            personal_browser, "session", new_callable=AsyncMock
        ) as restore,
    ):
        try:
            await personal_inference._socket(principal)
        except personal_inference.PersonalInferenceUnavailable:
            pass
        else:
            raise AssertionError("Unavailable hosted Personal worker did not fail closed")
        restore.assert_not_awaited()

    # Confirm disconnect must clear locally even when OpenAI discovery is down.
    # Revocation is optional; a provider outage cannot leave bearer credentials
    # saved or a credential lock held while the UI waits for a network timeout.
    credentials = {
        "active": "saved-account",
        "mode": "chatgpt",
        "accounts": {
            "saved-account": {
                "access_token": "fake-access-token",
                "refresh_token": "fake-refresh-token",
                "id_token": "fake-id-token",
                "client_id": "test-client",
            }
        },
    }
    lock_held = False

    @asynccontextmanager
    async def fake_transaction():
        nonlocal lock_held
        lock_held = True
        try:
            yield credentials
        finally:
            lock_held = False

    async def provider_offline():
        assert not lock_held, "Revocation must not run under the credential lock"
        assert "access_token" not in credentials["accounts"]["saved-account"]
        assert "refresh_token" not in credentials["accounts"]["saved-account"]
        raise ProjectError("Provider discovery unavailable")

    with (
        patch.object(chatgpt_auth, "transaction", side_effect=fake_transaction),
        patch.object(chatgpt_auth, "_attempt_store_directory", return_value=Path("/tmp/test-personal")),
        patch.object(chatgpt_auth, "_owner_subject", return_value=None),
        patch.dict(chatgpt_auth._attempts, {}, clear=True),
        patch.object(chatgpt_auth, "discovery", side_effect=provider_offline),
    ):
        result = await chatgpt_auth.disconnect()
    assert result["remote_revocation_confirmed"] is False
    assert lock_held is False
    assert all(
        field not in credentials["accounts"]["saved-account"]
        for field in ("access_token", "refresh_token", "id_token")
    )

    # Only after the isolated worker confirms local disconnect may SIGMA erase
    # the user's Personal authorization and return their selection to Sponsored.
    with (
        patch.object(api, "_personal_browser_principal", return_value=principal),
        patch.object(api.cloud_auth, "config", return_value=SimpleNamespace(local=True)),
        patch.object(api.personal_browser, "sign_in_preview_enabled", return_value=True),
        patch.object(api.personal_inference, "disconnect", new_callable=AsyncMock) as worker_disconnect,
        patch.object(api.cloud_auth, "clear_personal_authorization") as clear_mode,
    ):
        ui_request = httpx.Request("POST", "http://localhost/api/ai/personal-browser/disconnect")
        # The route only reads the already validated request principal.
        from starlette.requests import Request as StarletteRequest
        request = StarletteRequest({
            "type": "http", "method": "POST",
            "path": ui_request.url.path, "headers": [], "query_string": b"",
        })
        response = await api.personal_browser_disconnect(request)
        assert response.status_code == 200
        assert response.body == b'{"disconnected":true}'
        worker_disconnect.assert_awaited_once_with(principal)
        clear_mode.assert_called_once_with(principal.subject)

    with (
        patch.object(api, "_personal_browser_principal", return_value=principal),
        patch.object(api.cloud_auth, "config", return_value=SimpleNamespace(local=True)),
        patch.object(api.personal_browser, "sign_in_preview_enabled", return_value=True),
        patch.object(api.personal_inference, "disconnect", new_callable=AsyncMock,
                     side_effect=personal_inference.PersonalInferenceUnavailable("worker offline")),
        patch.object(api.cloud_auth, "clear_personal_authorization") as clear_mode,
    ):
        try:
            await api.personal_browser_disconnect(request)
        except Exception as error:
            assert getattr(error, "status_code", None) == 503
        else:
            raise AssertionError("Failed worker disconnect incorrectly reported success")
        clear_mode.assert_not_called()

    with patch.dict(os.environ, {"SIGMA_AUTH_POC_REAL_SIGNIN": "0"}):
        assert not server.real_signin_enabled()
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=server.app),
            base_url="http://127.0.0.1:8001",
        ) as client:
            denied = await client.post(
                "/begin", headers={"Origin": "http://127.0.0.1:8001"}
            )
            assert denied.status_code == 403
    print("PASS: gated real local chooser, origin, verified preview, and worker RPC key")


if __name__ == "__main__":
    asyncio.run(main())
