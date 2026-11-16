"""Identity-bound, fail-closed SIGMA client for the isolated browser supervisor.

The API never receives a Docker project, hostname, container ID, credential
directory or OAuth token from the browser. Only the server-verified Google
principal determines the durable workspace ID sent over the private Unix socket.

This is a lifecycle protocol, not a claim that Personal ChatGPT is connected.
The local-only real sign-in preview may authorize a Personal account, but
browser readiness is never sufficient proof of connection.
"""

from __future__ import annotations

import hmac
import os
import re
import stat
import time
from pathlib import Path
from typing import Any

import httpx
from starlette.concurrency import run_in_threadpool

from sigma import cloud_auth, cloud_workspaces, personal_diagnostics


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
    personal_diagnostics.emit(
        "api",
        "socket_check",
        enabled=int(enabled()),
        configured=int(bool(configured)),
    )
    if not enabled() or not configured:
        personal_diagnostics.emit("api", "socket_failed", reason="integration_disabled")
        raise PersonalBrowserUnavailable("Personal browser integration is disabled.")
    path = Path(configured)
    if not path.is_absolute() or ".." in path.parts:
        personal_diagnostics.emit("api", "socket_failed", reason="invalid_path")
        raise PersonalBrowserUnavailable("Personal browser integration is unavailable.")
    try:
        info = path.lstat()
    except OSError as exc:
        personal_diagnostics.emit(
            "api", "socket_failed", reason="socket_missing", failure=type(exc).__name__
        )
        raise PersonalBrowserUnavailable(
            "Personal broker socket is missing; see diagnostics."
        ) from exc
    if (
        not stat.S_ISSOCK(info.st_mode)
        or path.is_symlink()
        or info.st_uid not in {0, os.geteuid()}
        or info.st_mode & 0o077
    ):
        personal_diagnostics.emit(
            "api",
            "socket_failed",
            reason="socket_unsafe",
            is_socket=int(stat.S_ISSOCK(info.st_mode)),
            owner_ok=int(info.st_uid in {0, os.geteuid()}),
            permissions_ok=int(not (info.st_mode & 0o077)),
        )
        raise PersonalBrowserUnavailable(
            "Personal broker socket validation failed; see diagnostics."
        )
    personal_diagnostics.emit("api", "socket_ok")
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
        personal_diagnostics.emit("api", "workspace_failed", failure=type(exc).__name__)
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
    began = time.monotonic()
    personal_diagnostics.emit("api", "browser_operation_begin", operation=action)
    socket_path = _socket()
    workspace_id = await _workspace_id(trusted)
    transport = httpx.AsyncHTTPTransport(uds=socket_path)
    diagnostic_id = personal_diagnostics.current_attempt()
    headers = {"X-Sigma-Personal-Attempt": diagnostic_id} if diagnostic_id != "-" else {}
    try:
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://sigma-personal-broker",
            trust_env=False,
            # A cold Docker Desktop startup may consume the broker's full
            # 150-second Compose grace period. Do not time out at 85 seconds
            # and misreport a still-starting Chromium as a broken iframe.
            timeout=230,
        ) as client:
            if action == "status":
                response = await client.get(
                    "/v1/status",
                    params={"workspace_id": workspace_id},
                    headers=headers,
                )
            else:
                response = await client.post(
                    "/v1/" + action,
                    json={"workspace_id": workspace_id},
                    headers=headers,
                )
            personal_diagnostics.emit(
                "api",
                "broker_http_response",
                operation=action,
                http_status=response.status_code,
                elapsed_ms=int((time.monotonic() - began) * 1000),
            )
            if response.status_code == 503:
                failure = response.json()
                stage = failure.get("stage") if isinstance(failure, dict) else None
                failure_class = failure.get("failure_class") if isinstance(failure, dict) else None
                known_stages = {
                    "docker_up",
                    "docker_ps",
                    "docker_port",
                    "docker_other",
                    "worker_rpc",
                    "broker",
                }
                known_reasons = {
                    "docker_daemon_unavailable",
                    "permission_denied",
                    "port_conflict",
                    "image_platform_mismatch",
                    "container_unhealthy",
                    "chromium_security_rejected",
                    "resource_exhausted",
                    "docker_command_failed",
                    "docker_command_timeout",
                    "docker_command_unavailable",
                    "invalid_loopback_binding",
                    "worker_rejected",
                    "worker_unreachable",
                    "broker_unavailable",
                }
                if stage in known_stages and failure_class in known_reasons:
                    raise PersonalBrowserUnavailable(
                        f"Personal browser failed at {stage} ({failure_class}). "
                        "Use Copy diagnostics for details."
                    )
            if response.status_code != 200:
                personal_diagnostics.emit(
                    "api",
                    "broker_http_failed",
                    operation=action,
                    http_status=response.status_code,
                )
                raise PersonalBrowserUnavailable(
                    f"Personal broker returned HTTP {response.status_code}; "
                    "use Copy diagnostics for details."
                )
            payload = response.json()
    except (httpx.HTTPError, ValueError, TypeError, OSError) as exc:
        personal_diagnostics.emit(
            "api",
            "broker_transport_failed",
            operation=action,
            failure=type(exc).__name__,
            elapsed_ms=int((time.monotonic() - began) * 1000),
        )
        raise PersonalBrowserUnavailable(
            f"Personal broker transport failed ({type(exc).__name__}); "
            "use Copy diagnostics for details."
        ) from exc
    if (
        not isinstance(payload, dict)
        or payload.get("status") not in {"ready", "stopped", "unavailable"}
        or payload.get("worker") != "sigma-personal-" + workspace_id
    ):
        personal_diagnostics.emit("api", "broker_invalid_payload", operation=action)
        raise PersonalBrowserUnavailable("Invalid personal browser response.")
    personal_diagnostics.emit(
        "api",
        "browser_operation_ok",
        operation=action,
        browser_status=payload["status"],
        elapsed_ms=int((time.monotonic() - began) * 1000),
    )
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
    if (
        not stat.S_ISDIR(parent_info.st_mode)
        or directory.is_symlink()
        or stat.S_IMODE(parent_info.st_mode) != 0o700
        or parent_info.st_uid != os.geteuid()
        or not stat.S_ISSOCK(info.st_mode)
        or path.is_symlink()
        or info.st_uid != os.geteuid()
        or (info.st_mode & 0o077)
    ):
        raise PersonalBrowserUnavailable("Private browser gateway is unavailable.")
    return str(path)


async def browser_socket(principal: cloud_auth.Principal | None) -> str:
    return await _gateway_socket(principal, filename="vnc.sock")


async def model_socket(principal: cloud_auth.Principal | None) -> str:
    return await _gateway_socket(principal, filename="model.sock")


async def _shared_rpc_headers(principal: cloud_auth.Principal | None) -> dict[str, str]:
    if os.environ.get("SIGMA_PERSONAL_SHARED_MODE") != "1":
        return {}
    seed = os.environ.get("SIGMA_AUTH_POC_RPC_SEED", "")
    if not re.fullmatch(r"[0-9a-f]{64}", seed):
        raise PersonalBrowserUnavailable("Shared Personal authentication unavailable.")
    workspace = await _workspace_id(_principal(principal))
    return {
        "X-Sigma-Workspace": workspace,
        "X-Sigma-Worker-Key": hmac.digest(
            bytes.fromhex(seed), workspace.encode("ascii"), "sha256"
        ).hex(),
    }


async def test_account_verified(principal: cloud_auth.Principal | None) -> bool:
    """Read only the isolated worker's test status. Never select a billing mode."""
    if os.environ.get("SIGMA_AUTH_BROKER_LOCAL_POC") != "1":
        return False
    try:
        path = await model_socket(principal)
        transport = httpx.AsyncHTTPTransport(uds=path)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://private-personal-worker",
            trust_env=False,
            timeout=3,
        ) as client:
            response = await client.get(
                "/v1/test-account", headers=await _shared_rpc_headers(principal)
            )
            return response.status_code == 200 and response.json() == {"verified": True}
    except (PersonalBrowserUnavailable, httpx.HTTPError, OSError, ValueError):
        return False


def sign_in_preview_enabled() -> bool:
    return (
        enabled()
        and os.environ.get("SIGMA_AUTH_BROKER_LOCAL_POC") == "1"
        and os.environ.get("SIGMA_AUTH_POC_LOCAL_REAL_SIGNIN") == "1"
    )


async def sign_in_preview_phase(principal: cloud_auth.Principal | None) -> str:
    if not sign_in_preview_enabled():
        return "unavailable"
    try:
        path = await model_socket(principal)
        transport = httpx.AsyncHTTPTransport(uds=path)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://private-personal-worker",
            trust_env=False,
            timeout=3,
        ) as client:
            response = await client.get(
                "/v1/preview-state", headers=await _shared_rpc_headers(principal)
            )
            response.raise_for_status()
            phase = response.json()["phase"]
            if phase in (
                "rendering",
                "ready",
                "connecting",
                "connected",
                "plan_not_permitted",
                "declined",
                "cancelled",
                "expired",
                "failed",
            ):
                return phase
    except (PersonalBrowserUnavailable, httpx.HTTPError, OSError, ValueError, KeyError, TypeError):
        pass
    return "unavailable"


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
