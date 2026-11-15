"""Private model RPC contract for the Personal ChatGPT worker.

Hosted workers bind this server to /run/sigma-personal/model.sock. The local
Docker POC binds it to worker port 8002, published only on host loopback; its
browser still has no credential mount. Only the explicit local preview allows
provider dispatch with a per-workspace RPC key.
No token, refresh token, cookie or OAuth code is ever returned over this API.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import os
import re
import time
from typing import Any

import httpx
import synthetic_signin

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from sigma import chatgpt_auth, openai_connection, plan_stream
from sigma.model_catalog import CATALOG
from sigma.projects import ProjectError

if os.environ.get("SIGMA_AUTH_POC_LAB") != "1":
    raise RuntimeError("Worker model transport is not enabled outside the POC")

MAX_RPC_BYTES = 256_000

app = FastAPI(openapi_url=None, docs_url=None, redoc_url=None)


class ModelRequest(BaseModel):
    """Strict bound request: no provider URL, bearer token, or arbitrary headers."""

    model_config = ConfigDict(extra="forbid", strict=True)

    request_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    expected_binding: str = Field(pattern=r"^[0-9a-f]{64}$")
    payload: dict[str, Any]

    @model_validator(mode="after")
    def bounded(self) -> ModelRequest:
        body = self.payload
        if (
            not isinstance(body.get("model"), str)
            or body.get("store") is not False
            or body.get("stream") is not True
            or body.keys() - {"model", "store", "stream", "input", "instructions", "reasoning", "text"}
            or "input" not in body
            or len(json.dumps(body, separators=(",", ":")).encode("utf-8")) > MAX_RPC_BYTES
        ):
            raise ValueError("Unsafe model request")
        return self


_catalog_lock = asyncio.Lock()
_catalog_cache: tuple[bytes, float, list[str]] | None = None


def _valid_rpc_key(request: Request) -> bool:
    key = os.environ.get("SIGMA_AUTH_POC_RPC_KEY", "")
    return (
        os.environ.get("SIGMA_AUTH_POC_LOCAL_DOCKER") == "1"
        and os.environ.get("SIGMA_AUTH_POC_REAL_SIGNIN") == "1"
        and re.fullmatch(r"[0-9a-f]{64}", key) is not None
        and hmac.compare_digest(key.encode(), request.headers.get("x-sigma-worker-key", "").encode())
    )


async def _verified_account() -> tuple[dict[str, Any], str | None]:
    global _catalog_cache
    session = await chatgpt_auth.session()
    account = session.get("account")
    if (
        session.get("mode") != "chatgpt"
        or session.get("status") != "connected"
        or not isinstance(account, dict)
        or account.get("plan_authorized") is not True
        or not isinstance(account.get("access_token"), str)
        or not account["access_token"]
        or not isinstance(session.get("account_id"), str)
    ):
        return {"status": "disconnected", "binding": None, "models": [], "account_label": None}, None

    token = account["access_token"]
    token_digest = hashlib.sha256(token.encode()).digest()
    async with _catalog_lock:
        cached = _catalog_cache
        if cached is None or cached[0] != token_digest or cached[1] <= time.monotonic():
            catalog = await openai_connection._check(token, "chatgpt")
            models = [model for model in catalog.order if model in CATALOG]
            if catalog.result["status"] != "connected" or not models:
                return {"status": "unavailable", "binding": None, "models": [], "account_label": None}, None
            _catalog_cache = (token_digest, time.monotonic() + openai_connection.TTL, models)
        else:
            models = cached[2]
    binding = hashlib.sha256(session["account_id"].encode()).hexdigest()
    return {
        "status": "verified", "binding": binding, "models": models, "account_label": None,
    }, token


@app.get("/v1/account")
async def account_status(request: Request) -> dict[str, Any]:
    if not _valid_rpc_key(request):
        # The broker also uses this endpoint as a credential-free health probe.
        return {"status": "disabled", "binding": None, "models": [], "account_label": None}
    try:
        snapshot, _ = await _verified_account()
        return snapshot
    except (ProjectError, OSError, ValueError, KeyError, TypeError) as exc:
        raise HTTPException(503, "Could not check the isolated ChatGPT account.") from exc


@app.get("/v1/test-account")
async def test_account_status() -> dict[str, bool]:
    if not synthetic_signin.enabled():
        raise HTTPException(404)
    return {"verified": synthetic_signin.verified()}


@app.get("/v1/preview-state")
async def preview_state() -> dict[str, str]:
    if (
        os.environ.get("SIGMA_AUTH_POC_LOCAL_DOCKER") != "1"
        or os.environ.get("SIGMA_AUTH_POC_REAL_SIGNIN") != "1"
    ):
        raise HTTPException(404)
    try:
        async with httpx.AsyncClient(timeout=2, trust_env=False) as client:
            result = await client.get("http://127.0.0.1:8001/preview-state")
            result.raise_for_status()
            phase = result.json()["phase"]
    except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
        raise HTTPException(503, "The worker could not report sign-in progress.") from exc
    return {"phase": phase}


@app.post("/v1/response")
async def response(request: Request) -> dict[str, Any]:
    if not _valid_rpc_key(request):
        raise HTTPException(403, "Personal ChatGPT provider requests are not enabled.")
    raw = bytearray()
    async for chunk in request.stream():
        if len(raw) + len(chunk) > MAX_RPC_BYTES:
            raise HTTPException(413, "Worker request is too large.")
        raw.extend(chunk)
    try:
        body = ModelRequest.model_validate_json(bytes(raw))
    except ValidationError as exc:
        raise HTTPException(422, "Invalid Personal ChatGPT request.") from exc

    try:
        async with asyncio.timeout(60):
            account, token = await _verified_account()
            model = body.payload["model"]
            if (
                not token
                or account["binding"] != body.expected_binding
                or model not in account["models"]
            ):
                raise HTTPException(409, "The selected ChatGPT account or model changed.")
            async with (
                httpx.AsyncClient(timeout=55, trust_env=False, follow_redirects=False) as client,
                client.stream(
                    "POST",
                    "https://api.openai.com/v1/responses",
                    headers={"Authorization": "Bearer " + token, "Accept": "text/event-stream"},
                    json=body.payload,
                ) as upstream,
            ):
                if upstream.status_code != 200:
                    raise HTTPException(502, f"ChatGPT rejected this request (HTTP {upstream.status_code}).")
                result = await plan_stream.completed(upstream)
            if result.get("status") != "completed" or result.get("model") != model:
                raise HTTPException(502, "ChatGPT did not complete the requested model response.")
            return {
                "binding": body.expected_binding,
                "response": {
                    key: result[key]
                    for key in ("id", "status", "model", "output", "usage")
                    if key in result
                },
            }
    except (ProjectError, OSError, ValueError, KeyError, TypeError, httpx.HTTPError, TimeoutError) as exc:
        raise HTTPException(502, "The Personal ChatGPT request did not complete.") from exc
