"""Provider-free verification of Personal model routing across two workspaces.

A mock upstream validates the exact Responses endpoint and authorization
header; it never performs an actual OpenAI request or uses real credentials.
This protects the shared-container request boundary, not provider eligibility.
"""

from __future__ import annotations

import asyncio
import hmac
import json
import os
from unittest.mock import patch

import httpx

import model_gateway
import shared_service
from sigma import ai_store
from sigma.model_catalog import CATALOG

A, B = "a" * 32, "b" * 32
BINDING = "d" * 64
MODEL = next(iter(CATALOG))


def headers(workspace: str) -> dict[str, str]:
    key = hmac.digest(
        bytes.fromhex(os.environ["SIGMA_AUTH_POC_RPC_SEED"]),
        workspace.encode("ascii"),
        "sha256",
    ).hex()
    return {"X-Sigma-Workspace": workspace, "X-Sigma-Worker-Key": key}


def payload() -> dict:
    return {
        "request_id": "e" * 32,
        "expected_binding": BINDING,
        "timeout_seconds": 20,
        "payload": {
            "model": MODEL,
            "store": False,
            "stream": True,
            "input": "SIGMA model transport acceptance",
        },
    }


async def verify() -> None:
    account_scopes: list[str] = []
    upstream_calls: list[str] = []
    original_client = httpx.AsyncClient

    async def fake_account() -> tuple[dict, str | None]:
        current_workspace = ai_store.directory().name
        account_scopes.append(current_workspace)
        if current_workspace == A:
            return (
                {
                    "status": "verified",
                    "binding": BINDING,
                    "models": [MODEL],
                    "account_label": "Test account",
                },
                "synthetic-private-token",
            )
        return (
            {
                "status": "disconnected",
                "binding": None,
                "models": [],
                "account_label": None,
            },
            None,
        )

    async def fake_upstream(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "https://api.openai.com/v1/responses"
        assert request.headers["authorization"] == "Bearer synthetic-private-token"
        assert request.headers["accept"] == "text/event-stream"
        forwarded = json.loads(request.content)
        assert forwarded["model"] == MODEL
        assert forwarded["stream"] is True
        assert forwarded["store"] is False
        assert "access_token" not in forwarded
        upstream_calls.append(str(request.url))
        return httpx.Response(200, content=b"data: [DONE]\\n\\n")

    def provider_client(*args, **kwargs):
        if "transport" not in kwargs:
            kwargs["transport"] = httpx.MockTransport(fake_upstream)
        return original_client(*args, **kwargs)

    async def completed(_upstream, **_kwargs) -> dict:
        return {
            "id": "resp_simulated",
            "status": "completed",
            "model": MODEL,
            "output": [],
            "usage": {"input_tokens": 1, "output_tokens": 1},
        }

    async with original_client(
        transport=httpx.ASGITransport(app=shared_service.app),
        base_url="http://127.0.0.1",
    ) as client:
        with (
            patch.object(model_gateway, "_verified_account", side_effect=fake_account),
            patch.object(model_gateway.plan_stream, "completed", side_effect=completed),
            patch.object(model_gateway.httpx, "AsyncClient", side_effect=provider_client),
        ):
            good = await client.post(
                "/v1/response", json=payload(), headers=headers(A)
            )
            assert good.status_code == 200, (good.status_code, good.text)
            result = good.json()
            assert result["binding"] == BINDING
            assert result["response"]["model"] == MODEL
            assert len(upstream_calls) == 1

            wrong_scope = await client.post(
                "/v1/response", json=payload(), headers=headers(B)
            )
            assert wrong_scope.status_code == 409, wrong_scope.text
            assert account_scopes[-1] == B
            assert len(upstream_calls) == 1

            wrong_key = await client.post(
                "/v1/response",
                json=payload(),
                headers={**headers(B), "X-Sigma-Worker-Key": "0" * 64},
            )
            assert wrong_key.status_code == 403
            assert len(upstream_calls) == 1

            wrong_binding = payload()
            wrong_binding["expected_binding"] = "f" * 64
            expired = await client.post(
                "/v1/response", json=wrong_binding, headers=headers(A)
            )
            assert expired.status_code == 409
            assert len(upstream_calls) == 1

            smuggling = payload()
            smuggling["payload"]["authorization"] = "Bearer other-user"
            denied = await client.post(
                "/v1/response", json=smuggling, headers=headers(A)
            )
            assert denied.status_code == 422
            assert len(upstream_calls) == 1

    print("PASS scoped Personal model RPC, provider endpoint, no cross-user fallback")


if __name__ == "__main__":
    asyncio.run(verify())
