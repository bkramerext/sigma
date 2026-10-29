"""Authenticated hosted SIGMA CLI helpers.

Authentication uses SIGMA's normal Google OIDC flow and exchanges a
single-use PKCE-bound code over a loopback callback. Project operations use
the same hosted API endpoints as the browser.
"""

from __future__ import annotations

import base64
import hashlib
import http.server
import json
import os
import secrets
import stat
import tempfile
import threading
import time
import webbrowser
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlencode, urlsplit
from uuid import uuid4

import httpx


class CloudCliError(RuntimeError):
    """A hosted CLI request failed safely."""


def _host(value: str) -> str:
    host = value.rstrip("/")
    parsed = urlsplit(host)
    local_http = (
        parsed.scheme == "http"
        and parsed.hostname in {"127.0.0.1", "localhost"}
        and parsed.port is not None
    )
    if (
        (parsed.scheme != "https" and not local_http)
        or not parsed.hostname
        or parsed.path
        or parsed.query
        or parsed.fragment
        or parsed.username
        or parsed.password
    ):
        raise CloudCliError(
            "Host must be HTTPS or a loopback development origin such as http://127.0.0.1:5173"
        )
    return host


def _save_token(path: Path, host: str, token: str) -> None:
    path = path.expanduser().absolute()
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    try:
        parent_info = path.parent.lstat()
    except OSError as exc:
        raise CloudCliError("Token directory is unavailable.") from exc
    if (
        path.parent.is_symlink()
        or not stat.S_ISDIR(parent_info.st_mode)
        or parent_info.st_uid != os.getuid()
        or parent_info.st_mode & 0o077
    ):
        raise CloudCliError("Token directory must be a private directory owned by this user.")
    temporary = path.with_name(f".{path.name}.{secrets.token_hex(8)}.tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(json.dumps({"host": _host(host), "access_token": token}) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        os.chmod(path, 0o600)
    finally:
        temporary.unlink(missing_ok=True)


def _load_token(path: Path, host: str) -> str:
    path = path.expanduser().absolute()
    try:
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077:
            raise CloudCliError("Token file must be a private regular file (permissions 0600).")
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise CloudCliError(f"Cannot read CLI token file {path}.") from exc
    token = payload.get("access_token") if isinstance(payload, dict) else None
    if (
        not isinstance(token, str)
        or not token
        or len(token) > 128
        or payload.get("host") != _host(host)
    ):
        raise CloudCliError("CLI token file is empty or invalid.")
    return token


def login(
    host: str, token_file: Path, *, open_browser=webbrowser.open, timeout: int = 300
) -> dict[str, Any]:
    """Complete hosted Google login using a temporary 127.0.0.1 callback."""
    origin = _host(host)
    state = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(48)
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    )
    received: dict[str, str] = {}
    event = threading.Event()

    class Callback(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urlsplit(self.path)
            query = parse_qs(parsed.query)
            if parsed.path == "/callback" and query.get("state") == [state] and query.get("code"):
                received["code"] = query["code"][0]
                event.set()
                body = b"SIGMA CLI sign-in received. You may close this tab."
                self.send_response(200)
            else:
                body = b"Invalid SIGMA CLI sign-in response."
                self.send_response(400)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format, *args):
            return

    server = http.server.HTTPServer(("127.0.0.1", 0), Callback)
    port = server.server_address[1]
    redirect_uri = f"http://127.0.0.1:{port}/callback"
    worker = threading.Thread(
        target=server.serve_forever, kwargs={"poll_interval": 0.1}, daemon=True
    )
    worker.start()
    try:
        query = urlencode(
            {"redirect_uri": redirect_uri, "cli_state": state, "challenge": challenge}
        )
        url = f"{origin}/api/cloud-auth/cli/login?{query}"
        if not open_browser(url):
            print(f"Open this URL to sign in: {url}")
        if not event.wait(timeout):
            raise CloudCliError("Timed out waiting for Google sign-in.")
        response = httpx.post(
            f"{origin}/api/cloud-auth/cli/exchange",
            json={"code": received["code"], "verifier": verifier, "redirect_uri": redirect_uri},
            timeout=15,
            follow_redirects=False,
        )
        if response.status_code != 200:
            raise CloudCliError(
                f"CLI token exchange failed ({response.status_code}): {response.text[:300]}"
            )
        payload = response.json()
        token = payload.get("access_token")
        if not isinstance(token, str) or not token:
            raise CloudCliError("SIGMA returned an invalid CLI credential.")
        try:
            _save_token(token_file, origin, token)
        except CloudCliError:
            try:
                httpx.post(
                    f"{origin}/api/cloud-auth/logout",
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=10,
                )
            except httpx.HTTPError:
                pass
            raise
        return request(origin, token, "GET", "/api/cloud-auth/status")
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=2)


def request(host: str, token: str, method: str, endpoint: str, *, params=None, body=None) -> Any:
    origin = _host(host)
    try:
        response = httpx.request(
            method,
            origin + endpoint,
            params=params,
            json=body,
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
            follow_redirects=False,
        )
    except httpx.HTTPError as exc:
        raise CloudCliError(f"Could not reach hosted SIGMA: {type(exc).__name__}.") from exc
    if response.status_code >= 400:
        try:
            message = response.json().get("error") or response.json().get("detail")
        except (ValueError, AttributeError):
            message = None
        raise CloudCliError(
            f"SIGMA returned HTTP {response.status_code}: {message or response.text[:300]}"
        )
    if "application/json" in response.headers.get("content-type", ""):
        return response.json()
    return response.content


LIMIT_FIELDS: dict[str, tuple[str, type]] = {
    "research-rounds": ("research_rounds", int),
    "model-calls": ("model_calls", int),
    "session-duration-minutes": ("session_duration_minutes", int),
    "output-tokens-per-call": ("output_tokens_per_call", int),
    "maximum-estimated-cost-usd": ("maximum_estimated_cost_usd", float),
    "maximum-input-tokens-per-session": ("maximum_input_tokens_per_session", int),
    "max-concurrent-sessions": ("max_concurrent_sessions", int),
}
PROJECT_FIELDS: dict[str, tuple[str, type]] = {
    "title": ("title", str),
    "problem": ("problem", str),
    "research-mode": ("investigation_type", str),
    "model": ("ai_model", str),
    "thinking": ("reasoning_effort", str),
    "difficulty": ("difficulty", str),
    "show-advanced-outcome-details": ("show_advanced_outcome_details", bool),
}


def _convert(value: str, converter: type, name: str):
    try:
        if converter is bool:
            lowered = value.casefold()
            if lowered not in {"true", "false"}:
                raise ValueError
            return lowered == "true"
        return converter(value)
    except ValueError as exc:
        raise CloudCliError(f"{name} must be a {converter.__name__} value.") from exc


def set_param(host: str, token_file: Path, project_path: str, name: str, raw_value: str):
    """Update one allowlisted project setting through the hosted API."""
    token = _load_token(token_file, host)
    if name in LIMIT_FIELDS:
        field, converter = LIMIT_FIELDS[name]
        value = _convert(raw_value, converter, name)
        current = request(
            host, token, "GET", "/api/projects/research-limits", params={"path": project_path}
        )
        updated = dict(current)
        updated[field] = value
        updated["path"] = project_path
        updated["expected_limits"] = current
        result = request(host, token, "PUT", "/api/projects/research-limits", body=updated)
        return {
            "project_path": project_path,
            "parameter": name,
            "previous": current[field],
            "value": result[field],
            "settings": result,
        }
    if name not in PROJECT_FIELDS:
        allowed = [*LIMIT_FIELDS, *PROJECT_FIELDS]
        raise CloudCliError(
            f"Unsupported project parameter {name!r}. Allowed: {', '.join(allowed)}"
        )
    field, converter = PROJECT_FIELDS[name]
    value = _convert(raw_value, converter, name)
    snapshot = request(host, token, "GET", "/api/projects/inspect", params={"path": project_path})
    project = snapshot["project"]
    keys = (
        "title",
        "problem",
        "investigation_type",
        "ai_model",
        "reasoning_effort",
        "difficulty",
        "show_advanced_outcome_details",
    )
    expected = {
        key: project.get(key)
        for key in keys
        if key != "show_advanced_outcome_details" or key in project
    }
    body = {**expected, "path": project_path, "expected": expected, field: value}
    result = request(host, token, "POST", "/api/projects/update", body=body)
    return {
        "project_path": project_path,
        "parameter": name,
        "previous": project.get(field),
        "value": result["project"].get(field)
        if isinstance(result.get("project"), dict)
        else result.get(field),
        "settings": result,
    }


def print_json(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2))


def write_export(value: Any, path: Path) -> Path:
    """Publish one private immutable JSON snapshot without replacing existing evidence."""
    target = path.expanduser().absolute()
    target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
    temporary = Path(temporary_name)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, target)
        directory_fd = os.open(target.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except FileExistsError as exc:
        raise CloudCliError(f"Export already exists; choose a new path: {target}") from exc
    except OSError as exc:
        raise CloudCliError("SIGMA project export could not be safely published.") from exc
    finally:
        temporary.unlink(missing_ok=True)
    return target


def _write_bundle(host: str, token: str, project_path: str, directory: Path, label: str) -> Path:
    bundle = request(host, token, "GET", "/api/projects/export", params={"path": project_path})
    directory = directory.expanduser().absolute()
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    directory_info = directory.lstat()
    if (
        directory.is_symlink()
        or not stat.S_ISDIR(directory_info.st_mode)
        or directory_info.st_uid != os.getuid()
        or directory_info.st_mode & 0o077
    ):
        raise CloudCliError("Artifact directory must be private and owned by this user.")
    timestamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    target = directory / f"{label}-{timestamp}-{secrets.token_hex(3)}.json"
    return write_export(bundle, target)


def run_session(
    host: str,
    token_file: Path,
    project_path: str,
    strategy_ids: list[str],
    artifact_directory: Path,
    *,
    required_email: str,
    poll_interval: float = 5,
    timeout_seconds: int = 3600,
    on_update=lambda _value: None,
):
    """Start and observe a normal hosted research session, saving immutable bundle snapshots."""
    if not strategy_ids or len(strategy_ids) > 12:
        raise CloudCliError("Select between one and twelve strategy IDs.")
    token = _load_token(token_file, host)
    identity = request(host, token, "GET", "/api/cloud-auth/status")
    user = identity.get("user") or {}
    if (
        not identity.get("authenticated")
        or user.get("role") not in {"member", "admin"}
        or user.get("email", "").casefold() != required_email.casefold()
    ):
        raise CloudCliError("Authenticated SIGMA account does not match --require-email.")
    project_view = request(
        host, token, "GET", "/api/projects/inspect", params={"path": project_path}
    )
    project = project_view["project"]
    if project.get("investigation_type") != "military":
        raise CloudCliError("Project category changed; this run expects the Military project.")
    if project.get("ai_model") != "gpt-6.1-sol" or project.get("reasoning_effort") != "high":
        raise CloudCliError("Project model settings must remain Sol / High for this evaluation.")
    config = request(
        host, token, "GET", "/api/projects/proposals/config", params={"path": project_path}
    )
    if not config.get("available"):
        raise CloudCliError(config.get("message") or "Configured provider is unavailable.")
    limits = request(
        host, token, "GET", "/api/projects/research-limits", params={"path": project_path}
    )
    before = _write_bundle(host, token, project_path, artifact_directory, "pre-run")
    request_body = {
        "path": project_path,
        "strategy_id": strategy_ids[0],
        "strategy_ids": strategy_ids,
        "expected_project_id": project["id"],
        "expected_binding": config["binding"],
        "expected_limits": limits,
        "idempotency_key": str(uuid4()),
    }
    try:
        started = request(
            host, token, "POST", "/api/projects/research-sessions/start", body=request_body
        )
    except Exception:
        failed_attempt = _write_bundle(
            host, token, project_path, artifact_directory, "session-start-failure"
        )
        on_update({"status": "start_failed", "artifact_saved": str(failed_attempt)})
        raise
    session_id = started["id"]
    snapshots = [str(before)]
    latest_update = None
    deadline = time.monotonic() + timeout_seconds
    last_record = started
    try:
        while time.monotonic() < deadline:
            record = request(
                host,
                token,
                "GET",
                f"/api/projects/research-sessions/{session_id}",
                params={"path": project_path},
            )
            last_record = record
            on_update(
                {
                    "session_id": session_id,
                    "status": record.get("status"),
                    "updated_at": record.get("updated_at"),
                    "completed_steps": sum(
                        step.get("status") == "completed" for step in record.get("steps", [])
                    ),
                    "call_limit": record.get("call_limit"),
                }
            )
            updated = record.get("updated_at")
            if updated != latest_update:
                snapshot = _write_bundle(
                    host,
                    token,
                    project_path,
                    artifact_directory,
                    f"session-{session_id}-{record.get('status', 'unknown')}",
                )
                snapshots.append(str(snapshot))
                latest_update = updated
            if record.get("status") not in {"queued", "running"}:
                return {
                    "identity": identity.get("user"),
                    "project_id": project["id"],
                    "session": record,
                    "artifacts": snapshots,
                }
            time.sleep(poll_interval)
        raise CloudCliError(f"Research session {session_id} exceeded CLI observation timeout.")
    except KeyboardInterrupt:
        try:
            request(
                host,
                token,
                "POST",
                f"/api/projects/research-sessions/{session_id}/control",
                body={"path": project_path, "action": "stop"},
            )
        finally:
            snapshots.append(
                str(
                    _write_bundle(
                        host,
                        token,
                        project_path,
                        artifact_directory,
                        f"session-{session_id}-interrupted",
                    )
                )
            )
        raise
    except Exception:
        snapshots.append(
            str(
                _write_bundle(
                    host, token, project_path, artifact_directory, f"session-{session_id}-failure"
                )
            )
        )
        on_update(
            {
                "session_id": session_id,
                "status": last_record.get("status"),
                "artifact_saved": snapshots[-1],
            }
        )
        raise
