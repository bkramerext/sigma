"""Single-administrator remote-browser OAuth feasibility worker.

This is an explicitly opt-in research POC, not a supported hosted ChatGPT
authorization mechanism. It never returns OAuth codes or tokens to callers.
"""
from __future__ import annotations

import asyncio
import hmac
import os
import subprocess
import tempfile
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from sigma import chat, chatgpt_auth
from sigma.projects import ProjectError

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
_attempt: str | None = None
_chrome: subprocess.Popen | None = None
_lock = asyncio.Lock()


def _require_key(header: str | None) -> None:
    filename = os.environ.get("SIGMA_AUTH_BROWSER_POC_KEY_FILE", "")
    try:
        key = Path(filename).read_text(encoding="ascii").strip()
    except (OSError, ValueError):
        raise HTTPException(503, "Authentication browser is not configured") from None
    if len(key) < 48 or header is None or not hmac.compare_digest(key, header):
        raise HTTPException(403, "Unauthorized browser control")


def _exec(*args: str) -> None:
    try:
        subprocess.run(args, check=True, timeout=8, stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError):
        raise HTTPException(503, "Remote display input is unavailable") from None


class Pointer(BaseModel):
    kind: str
    x: int = Field(default=0, ge=0, le=1279)
    y: int = Field(default=0, ge=0, le=799)
    value: str = Field(default="", max_length=200)


@app.get("/health")
async def health():
    return {"ready": True}


@app.post("/begin")
async def begin(x_sigma_poc_key: str | None = Header(default=None)):
    global _attempt, _chrome
    _require_key(x_sigma_poc_key)
    async with _lock:
        if _attempt:
            state = chatgpt_auth.attempt_status(_attempt)
            if state["status"] == "connecting":
                raise HTTPException(409, "An OpenAI sign-in is already underway")
        try:
            result = await chatgpt_auth.begin()
            attempt_id = result["id"]
            destination = chatgpt_auth.authorization_url(attempt_id)
        except ProjectError:
            raise HTTPException(503, "Could not initiate OpenAI sign-in") from None
        _attempt = attempt_id
        # Never pass the authorization URL to the API or write it to logs.
        if _chrome is not None and _chrome.poll() is None:
            _chrome.terminate()
        environment = {**os.environ, "DISPLAY": ":99"}
        try:
            _chrome = subprocess.Popen(
                [
                    "/usr/bin/chromium", "--no-first-run", "--no-default-browser-check",
                    "--disable-dev-shm-usage", "--disable-gpu", "--no-sandbox",
                    "--user-data-dir=/tmp/sigma-auth-browser-profile",
                    "--window-size=1280,800", "--window-position=0,0",
                    "--new-window", destination,
                ],
                env=environment, stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL, start_new_session=True,
            )
        except OSError:
            chatgpt_auth.cancel(attempt_id)
            raise HTTPException(503, "Container browser could not start") from None
        return {"status": "connecting"}


@app.get("/status")
async def status(x_sigma_poc_key: str | None = Header(default=None)):
    _require_key(x_sigma_poc_key)
    if _attempt:
        try:
            attempt = chatgpt_auth.attempt_status(_attempt)
        except ProjectError:
            return {"status": "unavailable"}
        if attempt["status"] == "connected":
            try:
                session = await chatgpt_auth.session()
                account = session.get("account") or {}
                return {
                    "status": session.get("status", "unavailable"),
                    "account_label": account.get("email", "ChatGPT account"),
                }
            except ProjectError:
                return {"status": "unavailable"}
        return {"status": attempt["status"], "message": attempt["message"]}
    return {"status": "not_started"}


@app.get("/frame")
async def frame(x_sigma_poc_key: str | None = Header(default=None)):
    _require_key(x_sigma_poc_key)
    # A fresh private file; never keep or log screenshots.
    path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as snapshot:
            path = snapshot.name
        _exec("/usr/bin/scrot", "-z", "-o", path)
        data = Path(path).read_bytes()
        if not data.startswith(b"\x89PNG\r\n\x1a\n") or len(data) > 4_000_000:
            raise HTTPException(503, "Remote display frame unavailable")
        return Response(data, media_type="image/png",
                        headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"})
    except OSError:
        raise HTTPException(503, "Remote display frame unavailable") from None
    finally:
        if path:
            Path(path).unlink(missing_ok=True)


@app.post("/input")
async def input_event(
    action: Pointer, x_sigma_poc_key: str | None = Header(default=None),
):
    _require_key(x_sigma_poc_key)
    if action.kind == "click":
        _exec("/usr/bin/xdotool", "mousemove", str(action.x), str(action.y), "click", "1")
    elif action.kind == "text" and action.value:
        _exec("/usr/bin/xdotool", "type", "--clearmodifiers", "--delay", "10", "--",
              action.value)
    elif action.kind == "key" and action.value in {
        "Return", "BackSpace", "Tab", "Escape", "Left", "Right", "Up", "Down",
        "Delete", "Home", "End",
    }:
        _exec("/usr/bin/xdotool", "key", "--clearmodifiers", action.value)
    else:
        raise HTTPException(422, "Invalid browser input")
    return {"accepted": True}


@app.post("/test")
async def test_turn(x_sigma_poc_key: str | None = Header(default=None)):
    _require_key(x_sigma_poc_key)
    async with _lock:
        try:
            configuration = await chat.configuration()
            if not configuration["available"] or configuration["mode"] != "chatgpt":
                raise HTTPException(409, "Personal ChatGPT connection is not ready")
            message = await chat.respond(
                speaker="ai_1",
                messages=[{"speaker": "human", "text": "Reply with the word connected."}],
                conversation_id=str(uuid4()),
                expected_binding=configuration["binding"],
                model=configuration["model"],
                reasoning_effort=configuration["reasoning_effort"],
            )
        except ProjectError:
            raise HTTPException(502, "OpenAI test call failed") from None
        return {"status": "completed", "response": message[:400],
                "model": configuration["model"]}
