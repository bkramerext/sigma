"""Cloud workspace app with deterministic Google and sponsored-provider seams."""

from __future__ import annotations

import os
import secrets
from pathlib import Path

from cloud_workspace_test_app import app
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

from sigma import api, cloud_auth, cloud_workspaces, openai_connection

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

_identity_only_middleware = api.cloud_auth.middleware


async def _guest_aware_identity_middleware(request: Request, call_next):
    """Use production's isolated, read-only guest workspace behavior in Chrome."""
    principal = getattr(request.state, "cloud_principal", None)
    path = request.url.path
    if not isinstance(principal, cloud_auth.Principal) and path.startswith("/api/projects/"):
        guest_token = request.cookies.get("sigma_guest")
        workspace = cloud_workspaces.guest_workspace(guest_token) if guest_token else None
        create_guest = (path == "/api/projects/samples" and request.method == "GET") or (
            path == "/api/projects/samples/open" and request.method == "POST"
        )
        created = False
        if workspace is None and create_guest:
            guest_token = secrets.token_hex(32)
            workspace = cloud_workspaces.guest_workspace(guest_token, create=True)
            created = True
        if workspace is not None:
            if (
                request.method not in {"GET", "HEAD", "OPTIONS"}
                and path != "/api/projects/samples/open"
            ):
                return JSONResponse({"error": "Guest projects are read-only."}, status_code=403)
            if path in {
                "/api/projects/research-sessions/start",
                "/api/projects/proposals",
                "/api/projects/proposals/agentic",
                "/api/projects/strategy-suggestions",
                "/api/projects/text/convert",
                "/api/projects/papers",
                "/api/projects/papers/restart",
                "/api/projects/research-executions",
            }:
                return JSONResponse({"error": "Guest projects are read-only."}, status_code=403)
            request.state.cloud_guest_workspace = workspace
            response = await call_next(request)
            if created and guest_token:
                response.set_cookie(
                    "sigma_guest", guest_token, path="/", httponly=True, samesite="lax"
                )
            return response
    return await _identity_only_middleware(request, call_next)


api.cloud_auth.middleware = _guest_aware_identity_middleware


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
