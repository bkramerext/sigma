"""Identity-bound, fail-closed SIGMA client for the synthetic browser supervisor.

The API never receives a Docker project, hostname, container ID, credential
directory or OAuth token from the browser. Only the server-verified Google
principal determines the durable workspace ID sent over the private Unix socket.

This is a lifecycle protocol, not a claim that Personal ChatGPT is connected.
No real OpenAI authorization or inference is enabled here.
"""

from __future__ import annotations

import os
import stat
import sys
from pathlib import Path
from typing import Any

import httpx
from starlette.concurrency import run_in_threadpool

from sigma import cloud_auth, cloud_workspaces


class PersonalBrowserUnavailable(RuntimeError):
    """The per-user browser service is not safely available."""


def enabled() -> bool:
    return (
        os.environ.get("SIGMA_PERSONAL_BROWSER_LAB_ENABLED", "") == "1"
        and os.environ.get("SIGMA_AUTH_POC_REAL_SIGNIN") != "1"
        and cloud_auth.config().enabled
    )


def _socket() -> str:
    configured = os.environ.get("SIGMA_PERSONAL_BROWSER_BROKER_SOCKET", "")
    if not enabled() or not configured:
        raise PersonalBrowserUnavailable("Personal browser integration is disabled.")
    path = Path(configured)
    if not path.is_absolute() or ".." in path.parts:
        raise PersonalBrowserUnavailable("Personal browser integration is unavailable.")
    try:
        info = path.lstat()
    except OSError as exc:
        raise PersonalBrowserUnavailable("Personal browser integration is unavailable.") from exc
    if (
        not stat.S_ISSOCK(info.st_mode)
        or path.is_symlink()
        or info.st_uid not in {0, os.geteuid()}
        or info.st_mode & 0o077
    ):
        raise PersonalBrowserUnavailable("Personal browser integration is unavailable.")
    return configured


def _principal(request_principal: cloud_auth.Principal | None) -> cloud_auth.Principal:
    if (
        not isinstance(request_principal, cloud_auth.Principal)
        or request_principal.role not in {"member", "admin"}
        or request_principal.subject.startswith("mock:")
    ):
        raise PermissionError("Authenticated member required.")
    return request_principal


async def _workspace_id(principal: cloud_auth.Principal) -> str:
    try:
        workspace = await run_in_threadpool(
            cloud_workspaces.workspace_for_subject, principal.subject
        )
    except (cloud_workspaces.WorkspaceUnavailable, OSError, RuntimeError) as exc:
        raise PersonalBrowserUnavailable("Private user workspace is unavailable.") from exc
    return workspace.workspace_id


async def session(
    principal: cloud_auth.Principal | None,
    action: str = "status",
) -> dict[str, Any]:
    """One action for the currently authenticated user only, never an arbitrary ID."""
    trusted = _principal(principal)
    if action not in {"start", "status", "stop"}:
        raise ValueError("Unsupported browser lifecycle action")
    socket_path = _socket()
    workspace_id = await _workspace_id(trusted)
    transport = httpx.AsyncHTTPTransport(uds=socket_path)
    try:
        async with httpx.AsyncClient(
            transport=transport, base_url="http://sigma-personal-broker", timeout=85
        ) as client:
            if action == "status":
                response = await client.get("/v1/status", params={"workspace_id": workspace_id})
            else:
                response = await client.post("/v1/" + action, json={"workspace_id": workspace_id})
            response.raise_for_status()
            payload = response.json()
    except (httpx.HTTPError, ValueError, TypeError, OSError) as exc:
        raise PersonalBrowserUnavailable("Personal browser is unavailable.") from exc
    if (
        not isinstance(payload, dict)
        or payload.get("status") not in {"ready", "stopped", "unavailable"}
        or payload.get("worker") != "sigma-personal-" + workspace_id
    ):
        raise PersonalBrowserUnavailable("Invalid personal browser response.")
    # Deliberately no model connection or account label is returned. The
    # authenticated HTTPS browser stream and credential validation are separate
    # acceptance gates, and must never be represented by 'ready' alone.
    return {
        "browser_status": payload["status"],
        "personal_chatgpt_connected": False,
        "account": None,
    }


async def _gateway_socket(principal: cloud_auth.Principal | None, *, filename: str) -> str:
    """Resolve only the verified user's protected Unix socket, never a hostname."""
    if filename not in {"vnc.sock", "model.sock"}:
        raise ValueError("Unsupported private channel")
    trusted = _principal(principal)
    _socket()  # Lab disabled or unsafe broker must fail closed.
    workspace_id = await _workspace_id(trusted)
    raw = os.environ.get("SIGMA_PERSONAL_BROWSER_GATEWAY_ROOT", "")
    root = Path(raw)
    if not root.is_absolute() or ".." in root.parts or root == Path("/"):
        raise PersonalBrowserUnavailable("Private browser gateway is unavailable.")
    directory = root / workspace_id
    path = directory / filename
    try:
        parent_info = directory.lstat()
        info = path.lstat()
    except OSError as exc:
        raise PersonalBrowserUnavailable("Private browser gateway is unavailable.") from exc
    local_macos_socket = (
        os.environ.get("SIGMA_AUTH_BROKER_LOCAL_POC") == "1"
        and sys.platform == "darwin"
        and stat.S_IMODE(parent_info.st_mode) == 0o700
        and parent_info.st_uid == os.geteuid()
        and info.st_uid == os.geteuid()
        and bool(info.st_mode & stat.S_IRUSR)
        and bool(info.st_mode & stat.S_IWUSR)
    )
    if (
        not stat.S_ISDIR(parent_info.st_mode)
        or directory.is_symlink()
        or stat.S_IMODE(parent_info.st_mode) != 0o700
        or parent_info.st_uid != os.geteuid()
        or not stat.S_ISSOCK(info.st_mode)
        or path.is_symlink()
        or info.st_uid != os.geteuid()
        or (info.st_mode & 0o077 and not local_macos_socket)
    ):
        raise PersonalBrowserUnavailable("Private browser gateway is unavailable.")
    return str(path)


async def browser_socket(principal: cloud_auth.Principal | None) -> str:
    return await _gateway_socket(principal, filename="vnc.sock")


async def model_socket(principal: cloud_auth.Principal | None) -> str:
    return await _gateway_socket(principal, filename="model.sock")


async def browser_password(principal: cloud_auth.Principal | None) -> str:
    """Only the authenticated HTTPS view may request this ephemeral VNC secret.

    It is not an OpenAI credential; it grants control of this user's graphical
    browser and must never be logged, cached, or sent to a different principal.
    """
    trusted = _principal(principal)
    path = _socket()
    workspace_id = await _workspace_id(trusted)
    transport = httpx.AsyncHTTPTransport(uds=path)
    try:
        async with httpx.AsyncClient(
            transport=transport, base_url="http://sigma-personal-broker", timeout=15
        ) as client:
            response = await client.post("/v1/password", json={"workspace_id": workspace_id})
            response.raise_for_status()
            data = response.json()
    except (httpx.HTTPError, TypeError, ValueError, OSError) as exc:
        raise PersonalBrowserUnavailable("Private browser authorization is unavailable.") from exc
    if (
        not isinstance(data, dict)
        or data.get("status") != "ready"
        or data.get("worker") != "sigma-personal-" + workspace_id
        or not isinstance(data.get("password"), str)
        or len(data["password"]) != 8
    ):
        raise PersonalBrowserUnavailable("Private browser authorization is unavailable.")
    return data["password"]
