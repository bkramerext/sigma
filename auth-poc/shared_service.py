"""One-container Personal ChatGPT POC: one worker, one transient browser.

All model calls are bound to a trusted SIGMA workspace HMAC. The browser is
single-user-at-a-time; its session is not authentication for model RPCs.
Encrypted records are handled by sigma.ai_store with shared-vault enabled.
"""
from __future__ import annotations

import asyncio
import hmac
import json
import os
import re
import socket
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from sigma import ai_store
from sigma.ui_instance import private_directory
from model_gateway import app as model_app
from server import app as signin_app

_WORKSPACE = re.compile(r"[0-9a-f]{32}\Z")
_active_workspace: str | None = None
_browser_lock = asyncio.Lock()
_control_socket = "/run/sigma-browser-control/control.sock"

app = FastAPI(openapi_url=None, docs_url=None, redoc_url=None)
for legacy in (model_app, signin_app):
    for route in legacy.router.routes:
        if getattr(route, "path", "") not in {
            "/health", "/docs", "/openapi.json", "/redoc"
        }:
            app.router.routes.append(route)


def _seed() -> bytes:
    raw = os.environ.get("SIGMA_AUTH_POC_RPC_SEED", "")
    if not re.fullmatch(r"[0-9a-f]{64}", raw):
        raise HTTPException(503, "Shared Personal service is not configured.")
    return bytes.fromhex(raw)


def _workspace(request: Request) -> str:
    workspace = request.headers.get("x-sigma-workspace", "")
    supplied = request.headers.get("x-sigma-worker-key", "")
    if not _WORKSPACE.fullmatch(workspace) or not re.fullmatch(r"[0-9a-f]{64}", supplied):
        raise HTTPException(403, "Personal request is not authorized.")
    expected = hmac.digest(_seed(), workspace.encode("ascii"), "sha256")
    if not hmac.compare_digest(expected, bytes.fromhex(supplied)):
        raise HTTPException(403, "Personal request is not authorized.")
    return workspace


def _store(workspace: str) -> Path:
    base = Path(os.environ.get("SIGMA_PERSONAL_SHARED_WORKSPACES", ""))
    if not base.is_absolute() or not _WORKSPACE.fullmatch(workspace):
        raise HTTPException(503, "Private credential storage is not configured.")
    try:
        private_directory(base)
        target = base / workspace
        private_directory(target)
        return target
    except (OSError, RuntimeError) as exc:
        raise HTTPException(503, "Private credential storage is unavailable.") from exc


async def _supervisor(action: str, workspace: str) -> dict:
    if action not in {"start", "stop", "status", "password"}:
        raise ValueError("Unsupported browser command")

    def call() -> dict:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(20)
            client.connect(_control_socket)
            client.sendall((action + " " + workspace + "\n").encode("ascii"))
            received = bytearray()
            while len(received) <= 4096:
                part = client.recv(4096)
                if not part:
                    break
                received.extend(part)
                if b"\n" in part:
                    break
            if len(received) > 4096:
                raise ValueError("Oversized supervisor response")
            result = json.loads(received.decode("utf-8"))
            if not isinstance(result, dict) or result.get("status") not in {
                "ready", "stopped", "unavailable"
            }:
                raise ValueError("Invalid supervisor status")
            return result

    try:
        return await asyncio.wait_for(asyncio.to_thread(call), timeout=25)
    except (OSError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(503, "Temporary sign-in browser is unavailable.") from exc


class WorkspaceMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        global _active_workspace
        path = request.url.path
        # No access to any sign-in route without the active browser.
        if path == "/health":
            return await call_next(request)
        if path.startswith("/v1/"):
            try:
                workspace = _workspace(request)
            except HTTPException as exc:
                return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)
        else:
            if (
                not request.client
                or request.client.host not in {"127.0.0.1", "::1"}
                or _active_workspace is None
            ):
                return JSONResponse({"detail": "Sign-in session unavailable"}, status_code=403)
            workspace = _active_workspace

        # ContextVar prevents concurrent requests from changing each other's
        # record selection. The callback stores its own immutable store path.
        request.state.shared_workspace = workspace
        request.state.shared_browser_active = workspace == _active_workspace
        with ai_store.use_directory(_store(workspace)):
            return await call_next(request)


app.add_middleware(WorkspaceMiddleware)


@app.post("/v1/browser/start")
async def browser_start(request: Request) -> dict:
    global _active_workspace
    workspace = _workspace(request)
    async with _browser_lock:
        if _active_workspace is not None:
            if (await _supervisor("status", _active_workspace))["status"] != "ready":
                _active_workspace = None
        if _active_workspace not in {None, workspace}:
            raise HTTPException(409, "Another sign-in is in progress.")
        _active_workspace = workspace
        try:
            state = await _supervisor("start", workspace)
        except BaseException:
            _active_workspace = None
            raise
        if state["status"] != "ready":
            _active_workspace = None
            raise HTTPException(503, "Sign-in browser could not start.")
        return {"status": "ready"}


@app.post("/v1/browser/stop")
async def browser_stop(request: Request) -> dict:
    global _active_workspace
    workspace = _workspace(request)
    async with _browser_lock:
        if _active_workspace != workspace:
            return {"status": "stopped"}
        try:
            return await _supervisor("stop", workspace)
        finally:
            _active_workspace = None


@app.get("/v1/browser/status")
async def browser_status(request: Request) -> dict:
    workspace = _workspace(request)
    if workspace != _active_workspace:
        return {"status": "stopped"}
    return await _supervisor("status", workspace)


@app.post("/v1/browser/password")
async def browser_password(request: Request) -> dict:
    workspace = _workspace(request)
    if workspace != _active_workspace:
        raise HTTPException(403, "The browser belongs to a different user.")
    response = await _supervisor("password", workspace)
    if response.get("status") != "ready" or not re.fullmatch(
        r"[A-Za-z0-9_-]{8}", str(response.get("password", ""))
    ):
        raise HTTPException(503, "Sign-in viewer is unavailable.")
    return response


@app.get("/health")
async def health() -> dict:
    return {"healthy": True, "shared": True}
