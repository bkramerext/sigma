"""Loopback-only account chooser and callback for the synthetic Docker lab."""

from __future__ import annotations

import os
import secrets
import time
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

router = APIRouter(prefix="/test-signin")
_ORIGIN = "http://127.0.0.1:8001"
_VERIFIED = Path("/tmp/sigma-test-account-verified")
_HEADERS = {
    "Cache-Control": "no-store",
    "Referrer-Policy": "same-origin",
    "Content-Security-Policy": "default-src 'none'; form-action 'self'; frame-ancestors 'none'",
}


@dataclass
class Attempt:
    state: str = field(default_factory=lambda: secrets.token_urlsafe(32))
    expires: float = field(default_factory=lambda: time.monotonic() + 300)
    code: str | None = None


_attempt: Attempt | None = None


def enabled() -> bool:
    return (
        os.environ.get("SIGMA_AUTH_POC_LOCAL_DOCKER") == "1"
        and os.environ.get("SIGMA_AUTH_POC_REAL_SIGNIN") != "1"
    )


def verified() -> bool:
    return enabled() and _VERIFIED.is_file()


def _require_lab(request: Request | None = None) -> None:
    if not enabled():
        raise HTTPException(404)
    if request is not None and request.headers.get("origin") != _ORIGIN:
        raise HTTPException(403, "Invalid browser origin")


def _current(state: str) -> Attempt:
    if (
        _attempt is None
        or time.monotonic() >= _attempt.expires
        or not secrets.compare_digest(_attempt.state.encode(), state.encode())
    ):
        raise HTTPException(400, "Invalid or expired test sign-in. Return to SIGMA and retry.")
    return _attempt


@router.post("/begin")
async def begin(request: Request) -> RedirectResponse:
    global _attempt
    _require_lab(request)
    _attempt = Attempt()
    query = urlencode({"state": _attempt.state})
    return RedirectResponse("/test-signin/choose?" + query, status_code=303, headers=_HEADERS)


@router.get("/choose")
async def choose(state: str) -> HTMLResponse:
    _require_lab()
    attempt = _current(state)
    return HTMLResponse(
        '<!doctype html><html lang="en"><meta charset="utf-8">'
        '<title>Choose a test account</title><h1>Choose a test account</h1>'
        '<p>This account is for the SIGMA sign-in test.</p>'
        f'<form method="post" action="/test-signin/choose?state={attempt.state}">'
        '<button type="submit">Continue as SIGMA Test</button></form></html>',
        headers=_HEADERS,
    )


@router.post("/choose")
async def authorize(request: Request, state: str) -> RedirectResponse:
    _require_lab(request)
    attempt = _current(state)
    if attempt.code is not None:
        raise HTTPException(409, "Test account was already selected.")
    attempt.code = secrets.token_urlsafe(32)
    query = urlencode({"state": attempt.state, "code": attempt.code})
    return RedirectResponse(_ORIGIN + "/test-signin/callback?" + query, status_code=303, headers=_HEADERS)


@router.get("/callback")
async def callback(state: str, code: str) -> HTMLResponse:
    global _attempt
    _require_lab()
    attempt = _current(state)
    if not attempt.code or not secrets.compare_digest(attempt.code.encode(), code.encode()):
        raise HTTPException(400, "Invalid test authorization code.")
    _attempt = None
    _VERIFIED.touch(mode=0o600)
    return HTMLResponse(
        '<!doctype html><html lang="en"><meta charset="utf-8">'
        '<title>Test account verified</title><h1>Test account verified</h1>'
        '<p>Return to SIGMA to continue.</p></html>',
        headers=_HEADERS,
    )
