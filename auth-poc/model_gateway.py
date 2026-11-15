"""Private, worker-only model RPC contract for the synthetic Personal POC.

Hosted workers bind this server to /run/sigma-personal/model.sock. The local
Docker POC binds it to worker port 8002, published only on host loopback; its
browser still has no credential mount. OAuth and provider dispatch stay blocked.
No token, refresh token, cookie or OAuth code is ever returned over this API.
"""

from __future__ import annotations

import json
import os
from typing import Any

import synthetic_signin

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, model_validator

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
            or any(key in body for key in ("token", "authorization", "headers", "url", "api_key"))
            or "input" not in body
            or len(json.dumps(body, separators=(",", ":")).encode("utf-8")) > MAX_RPC_BYTES
        ):
            raise ValueError("Unsafe model request")
        return self


@app.get("/v1/account")
async def account_status() -> dict[str, Any]:
    # Do not replace this with a fabricated "connected" state. Once live OAuth
    # is approved, status must come from the worker's validated token store.
    return {
        "status": "disabled",
        "binding": None,
        "models": [],
        "account_label": None,
    }


@app.get("/v1/test-account")
async def test_account_status() -> dict[str, bool]:
    if not synthetic_signin.enabled():
        raise HTTPException(404)
    return {"verified": synthetic_signin.verified()}


@app.post("/v1/response")
async def response(request: Request, body: ModelRequest) -> None:
    if request.headers.get("content-length", "").isdecimal():
        if int(request.headers["content-length"]) > MAX_RPC_BYTES:
            raise HTTPException(413, "Worker request is too large")
    # This branch must NOT issue a provider call. Tests inject fake response
    # servers over a Unix socket to verify the actual SIGMA routing boundary.
    # No environment switch can activate inference in this prototype.
    raise HTTPException(403, "Personal ChatGPT provider requests are not enabled")
