"""Admin-only, same-origin browser proxy for the containerized OAuth feasibility POC.

All browser control goes through SIGMA's existing Google authentication
middleware. The worker is private to the Docker network (or local loopback).
This deliberately does not enable Personal inference for ordinary users.
"""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/auth-browser-poc")


def _authorize(request: Request) -> None:
    if os.getenv("SIGMA_AUTH_BROWSER_POC_ENABLED", "").casefold() not in {
        "1",
        "true",
        "yes",
    }:
        raise HTTPException(404, "Authentication experiment is disabled")
    principal = getattr(request.state, "cloud_principal", None)
    if principal is None or principal.role != "admin" or principal.subject.startswith("mock:"):
        raise HTTPException(
            403, "Only the authenticated SIGMA administrator may run this experiment"
        )


def _upstream() -> tuple[str, str]:
    origin = os.environ.get("SIGMA_AUTH_BROWSER_POC_ORIGIN", "").strip().rstrip("/")
    parsed = urlsplit(origin)
    # Never accept caller-selected URLs or arbitrary network destinations.
    if (
        parsed.scheme != "http"
        or parsed.hostname not in {"127.0.0.1", "auth-browser-poc"}
        or parsed.path
        or parsed.query
        or parsed.fragment
        or parsed.username
        or parsed.password
        or parsed.port not in {8765, 18765}
    ):
        raise HTTPException(503, "Authentication experiment worker is not configured")
    filename = os.environ.get("SIGMA_AUTH_BROWSER_POC_KEY_FILE", "")
    try:
        secret = Path(filename).read_text(encoding="ascii").strip()
    except (ValueError, OSError):
        raise HTTPException(503, "Authentication experiment key is unavailable") from None
    if len(secret) < 48:
        raise HTTPException(503, "Authentication experiment key is invalid")
    return origin, secret


async def _send(method: str, path: str, data: dict | None = None) -> httpx.Response:
    origin, secret = _upstream()
    try:
        async with httpx.AsyncClient(timeout=70, trust_env=False, follow_redirects=False) as client:
            response = await client.request(
                method,
                origin + path,
                headers={"X-Sigma-Poc-Key": secret},
                json=data,
            )
    except (httpx.HTTPError, TimeoutError):
        raise HTTPException(503, "Authentication browser container is unavailable") from None
    if response.status_code >= 400:
        # No third-party page or token/error bodies reach the main SIGMA API.
        raise HTTPException(response.status_code, "Authentication experiment request failed")
    return response


class BrowserInput(BaseModel):
    kind: str = Field(max_length=12)
    x: int = Field(default=0, ge=0, le=1279)
    y: int = Field(default=0, ge=0, le=799)
    value: str = Field(default="", max_length=200)


@router.get("/ui")
async def ui(request: Request):
    _authorize(request)
    from sigma.auth_browser_poc_ui import HTML

    return HTMLResponse(HTML, headers={"Cache-Control": "no-store"})


@router.post("/begin")
async def begin(request: Request):
    _authorize(request)
    return _send_json(await _send("POST", "/begin"))


@router.get("/status")
async def status(request: Request):
    _authorize(request)
    return _send_json(await _send("GET", "/status"))


@router.get("/frame")
async def frame(request: Request):
    _authorize(request)
    response = await _send("GET", "/frame")
    if response.headers.get("content-type", "").split(";")[0] != "image/png":
        raise HTTPException(502, "Authentication browser returned an invalid frame")
    return Response(
        response.content,
        media_type="image/png",
        headers={
            "Cache-Control": "no-store",
            "Referrer-Policy": "no-referrer",
        },
    )


@router.post("/input")
async def browser_input(request: Request, action: BrowserInput):
    _authorize(request)
    return _send_json(await _send("POST", "/input", action.model_dump()))


@router.post("/test")
async def test(request: Request):
    _authorize(request)
    return _send_json(await _send("POST", "/test"))


def _send_json(response: httpx.Response) -> dict:
    try:
        value = response.json()
    except ValueError:
        raise HTTPException(502, "Authentication browser returned invalid JSON") from None
    if not isinstance(value, dict):
        raise HTTPException(502, "Authentication browser returned invalid JSON")
    return value
