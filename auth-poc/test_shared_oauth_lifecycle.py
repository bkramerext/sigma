"""Provider-free, in-container adversarial OAuth lease and cancellation tests.

The actual shared ASGI middleware is exercised with workspace-signed requests;
the root GUI supervisor is mocked to avoid contacting a real OpenAI account.
"""
from __future__ import annotations

import asyncio
import hmac
import os
from unittest.mock import AsyncMock, patch

import httpx

from sigma import ai_store
import server
import shared_service
import synthetic_signin

A, B = "a" * 32, "b" * 32


def headers(workspace: str) -> dict[str, str]:
    secret = bytes.fromhex(os.environ["SIGMA_AUTH_POC_RPC_SEED"])
    return {
        "X-Sigma-Workspace": workspace,
        "X-Sigma-Worker-Key": hmac.digest(secret, workspace.encode("ascii"), "sha256").hex(),
    }


async def verify() -> None:
    mock_status_a = "ready"
    cancellation_scopes: list[str] = []
    calls: list[tuple[str, str]] = []

    async def supervisor(action: str, workspace: str) -> dict[str, str]:
        calls.append((action, workspace))
        if action == "start":
            return {"status": "ready"}
        if action == "stop":
            return {"status": "stopped"}
        if action == "status":
            return {"status": mock_status_a if workspace == A else "ready"}
        raise AssertionError("Unexpected supervisor action")

    def cancel() -> None:
        cancellation_scopes.append(ai_store.directory().name)

    shared_service._active_workspace = None
    transport = httpx.ASGITransport(app=shared_service.app)
    try:
        with (
            patch.object(shared_service, "_supervisor", side_effect=supervisor),
            patch.object(shared_service, "cancel_pending_signin", side_effect=cancel),
        ):
            async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1") as client:
                response = await client.post("/v1/browser/start", headers=headers(A))
                assert response.status_code == 200, response.text
                # This is the actual production worker: a real OAuth chooser
                # must be available with *no* legacy local/laboratory flags.
                with patch.dict(
                    os.environ,
                    {
                        "SIGMA_AUTH_POC_LOCAL_DOCKER": "0",
                        "SIGMA_AUTH_POC_REAL_SIGNIN": "0",
                        "SIGMA_AUTH_POC_LAB": "0",
                    },
                ):
                    assert server.real_signin_enabled()
                    assert not synthetic_signin.enabled()
                    saved_id = server._ATTEMPT_ID
                    server._ATTEMPT_ID = None
                    target = "https://auth.openai.com/authorize?state=ci"
                    try:
                        with (
                            patch.object(
                                server.chatgpt_auth,
                                "begin",
                                new_callable=AsyncMock,
                                return_value={"id": "shared-real-oauth"},
                            ) as begin,
                            patch.object(server.chatgpt_auth, "authorization_url", return_value=target),
                            patch.object(server.chatgpt_auth, "session", new_callable=AsyncMock) as saved,
                        ):
                            chooser = await client.get(
                                "/", headers={"Host": "127.0.0.1:8001"},
                                follow_redirects=False,
                            )
                            assert chooser.status_code in (302, 303, 307, 308), chooser.text
                            assert chooser.headers["location"] == target
                            begin.assert_awaited_once()
                            saved.assert_not_awaited()
                        # The synthetic chooser is not even mounted on the
                        # production shared runtime.
                        synthetic = await client.get(
                            "/test-signin/choose?state=fake",
                            headers={"Host": "127.0.0.1:8001"},
                        )
                        assert synthetic.status_code == 404
                        # A previously connected account must not be mistaken
                        # for the result of this explicit new chooser request.
                        server._ATTEMPT_ID = None
                        with patch.object(
                            server, "_saved_preview_is_authorized", return_value=True
                        ) as cached:
                            preview = await client.get(
                                "/preview-state",
                                headers={"Host": "127.0.0.1:8001"},
                            )
                            assert preview.status_code == 200
                            assert preview.json() == {"phase": "ready"}
                            cached.assert_not_called()
                    finally:
                        server._ATTEMPT_ID = saved_id

                response = await client.post("/v1/browser/start", headers=headers(B))
                assert response.status_code == 409
                assert cancellation_scopes == []

                # Cross-user account deletion regression: a B-scoped HMAC
                # must NEVER authorize the legacy browser-global /disconnect
                # route while A is signing in.
                response = await client.post("/disconnect", headers=headers(B))
                assert response.status_code == 403
                # Similarly, local OAuth pages must reject a rebinding Host.
                response = await client.get("/status", headers={"Host": "evil.example"})
                assert response.status_code == 403
                response = await client.get("/status", headers={"Host": "127.0.0.1:8001"})
                assert response.status_code == 200
                assert cancellation_scopes == []
                response = await client.post("/v1/browser/stop", headers=headers(A))
                assert response.status_code == 200
                assert cancellation_scopes == [A]
                response = await client.post("/v1/browser/start", headers=headers(A))
                assert response.status_code == 200
                # Chromium timed out independently of the worker. B must
                # cancel A's stale PKCE attempt INSIDE A's storage context.
                mock_status_a = "stopped"
                response = await client.post("/v1/browser/start", headers=headers(B))
                assert response.status_code == 200, response.text
                assert cancellation_scopes == [A, A]
                response = await client.post("/v1/browser/stop", headers=headers(B))
                assert response.status_code == 200
                assert cancellation_scopes == [A, A, B]
                response = await client.post(
                    "/v1/browser/start",
                    headers={**headers(A), "X-Sigma-Worker-Key": "0" * 64},
                )
                assert response.status_code == 403
    finally:
        shared_service._active_workspace = None
    print("PASS shared OAuth ownership, stale attempt cancellation and wrong-user rejection")


if __name__ == "__main__":
    asyncio.run(verify())
