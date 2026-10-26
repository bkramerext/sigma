"""Cloud workspace app with deterministic Google and sponsored-provider seams."""

from __future__ import annotations

import os
from pathlib import Path

from cloud_workspace_test_app import app
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

from sigma import cloud_auth, openai_connection

_real_client = openai_connection.httpx.AsyncClient
_provider_status = {"value": "connected"}


def _fixture_auth_config() -> cloud_auth.Config:
    auth_home = Path(os.environ["SIGMA_CLOUD_AUTH_HOME"])
    auth_home.mkdir(mode=0o700, parents=True, exist_ok=True)
    return cloud_auth.Config(
        True,
        "fixture.apps.googleusercontent.com",
        "fixture-secret",
        "https://sigma.test",
        "admin@example.test",
        auth_home / "access.sqlite3",
        None,
        False,
    )


cloud_auth.config = _fixture_auth_config


def _provider_response(request):
    import httpx

    status = _provider_status["value"]
    if request.url.path != "/v1/models":
        return httpx.Response(500, json={"error": "unexpected fixture request"})
    if status == "unavailable":
        raise httpx.ConnectError("deterministic unavailable fixture", request=request)
    if status == "unauthorized":
        return httpx.Response(401, json={"error": {"message": "fixture"}})
    if status == "invalid_response":
        return httpx.Response(200, json={"object": "unexpected", "data": []})
    return httpx.Response(200, json={"object": "list", "data": [{"id": "gpt-6.1-sol"}]})


def _mock_client(**kwargs):
    import httpx

    return _real_client(transport=httpx.MockTransport(_provider_response), **kwargs)


openai_connection.httpx.AsyncClient = _mock_client


@app.post("/__fixture/authorize")
def authorize_fixture_identity(request: Request):
    principal = getattr(request.state, "cloud_principal", None)
    if not isinstance(principal, cloud_auth.Principal):
        raise HTTPException(401, "Authentication required.")
    try:
        cfg = _fixture_auth_config()
        assert cfg.database is not None
        cloud_auth._initialize(cfg.database)
        cloud_auth._persist_user_state(cfg, principal)
    except (OSError, RuntimeError) as exc:
        raise HTTPException(503, "Fixture user state could not be created.") from exc
    return {"authorized": True}


@app.post("/__fixture/provider/{status}")
def set_provider_status(status: str):
    if status not in {"connected", "unavailable", "unauthorized", "invalid_response"}:
        return JSONResponse({"error": "unknown fixture status"}, status_code=400)
    _provider_status["value"] = status
    # Force a fresh, deterministic provider check on the next account request.
    openai_connection._cached = None
    return {"status": status}
