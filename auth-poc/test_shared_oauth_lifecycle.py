"""Provider-free, in-container adversarial OAuth lease and cancellation tests.

The actual shared ASGI middleware is exercised with workspace-signed requests;
the root GUI supervisor is mocked to avoid contacting a real OpenAI account.
"""
from __future__ import annotations

import asyncio
import hmac
import os
from unittest.mock import patch

import httpx

from sigma import ai_store
import shared_service

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
                response = await client.post("/v1/browser/start", headers=headers(B))
                assert response.status_code == 409
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
