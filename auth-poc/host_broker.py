"""Host-side, synthetic-only manager for per-Google-user loopback containers.

This is a deliberately narrow Docker command broker, NOT a generic Docker API
or an OAuth token service. SIGMA authenticates the user and supplies only the
server-generated workspace ID via a private Unix socket. The broker can start,
query and stop a fixed pair of release-pinned images; it cannot execute arbitrary
commands, select other volumes/images, or accept caller-provided paths.
"""
from __future__ import annotations

import json
import os
import re
import socket
import socketserver
import stat
import struct
import subprocess
import threading
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

WORKSPACE_ID = re.compile(r"[0-9a-f]{32}\Z")
RELEASE = re.compile(r"[0-9a-f]{40}\Z")
MAX_REQUEST = 2048
ROOT = Path(__file__).resolve().parents[1]
FILES = (
    ROOT / "deploy/auth-poc.compose.yaml",
    ROOT / "deploy/auth-poc.gce.yaml",
    ROOT / "deploy/auth-poc.user.gce.yaml",
)
_LOCKS: dict[str, threading.Lock] = {}
_LOCK = threading.Lock()


def local_poc() -> bool:
    """Explicit single-machine POC: host user owns the private relay mounts.

    Production uses worker UID 10001; macOS Docker Desktop needs the launching
    user's mapped UID on bind mounts. The browser remains a separate UID.
    """
    return os.environ.get("SIGMA_AUTH_BROKER_LOCAL_POC") == "1"


def validate_id(workspace_id: str) -> str:
    if not isinstance(workspace_id, str) or not WORKSPACE_ID.fullmatch(workspace_id):
        raise ValueError("Invalid workspace identity")
    return workspace_id


def state_root() -> Path:
    raw = os.environ.get("SIGMA_AUTH_BROKER_STATE_ROOT", "")
    root = Path(raw)
    if not root.is_absolute() or ".." in root.parts or root == Path("/"):
        raise ValueError("Private state root must be an absolute directory")
    return root


def gateway_root() -> Path:
    raw = os.environ.get("SIGMA_AUTH_BROKER_GATEWAY_ROOT", "")
    root = Path(raw)
    if not root.is_absolute() or ".." in root.parts or root == Path("/"):
        raise ValueError("Private gateway root must be an absolute directory")
    return root


def _verify_directory(path: Path, *, create: bool = True) -> None:
    if create:
        path.mkdir(mode=0o700, exist_ok=True)
    details = path.lstat()
    if not stat.S_ISDIR(details.st_mode) or stat.S_ISLNK(details.st_mode):
        raise ValueError("Unsafe broker state directory")
    if details.st_mode & 0o077:
        raise ValueError("Broker state directory is not private")


def prepare_state(workspace_id: str) -> Path:
    """Fail closed on symlinks and existing unsafe state; never create outside root."""
    validate_id(workspace_id)
    root = state_root()
    _verify_directory(root)
    current = root
    for part in (workspace_id, "auth", "auth-poc"):
        current = current / part
        _verify_directory(current)
    # The worker needs access to its isolated state, not to sibling workspaces.
    worker_uid = os.geteuid() if local_poc() else 10001
    worker_gid = os.getegid() if local_poc() else 10001
    if os.geteuid() == 0:
        os.chown(current, worker_uid, worker_gid)
    elif current.stat().st_uid != worker_uid:
        raise ValueError("Browser worker volume ownership is unavailable")
    return root / workspace_id


def _verify_traversable_root(path: Path) -> None:
    """The backend may traverse, but not enumerate, private IPC directory roots."""
    details = path.lstat()
    if (
        not stat.S_ISDIR(details.st_mode)
        or stat.S_ISLNK(details.st_mode)
        or stat.S_IMODE(details.st_mode) != 0o711
    ):
        raise ValueError("Private IPC root must be mode 0711")


def prepare_gateway(workspace_id: str) -> Path:
    """Create only this worker's private, socket-only bind mount."""
    validate_id(workspace_id)
    root = gateway_root()
    _verify_traversable_root(root)
    child = root / workspace_id
    _verify_directory(child)
    worker_uid = os.geteuid() if local_poc() else 10001
    worker_gid = os.getegid() if local_poc() else 10001
    if os.geteuid() == 0:
        os.chown(child, worker_uid, worker_gid)
    elif child.stat().st_uid != worker_uid:
        raise ValueError("Browser relay ownership is unavailable")
    return child


def compose_args(workspace_id: str, *args: str) -> list[str]:
    validate_id(workspace_id)
    files = FILES + ((ROOT / "deploy/auth-poc.user.local.yaml",) if local_poc() else ())
    return [
        "docker", "compose", "--project-name", "sigma-personal-" + workspace_id,
        *(item for path in files for item in ("-f", str(path))),
        *args,
    ]


def compose_env(workspace_id: str) -> dict[str, str]:
    validate_id(workspace_id)
    release = os.environ.get("SIGMA_RELEASE", "")
    if not RELEASE.fullmatch(release):
        raise ValueError("The exact release SHA is not configured")
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": os.environ.get("HOME", "/tmp"),
        "SIGMA_RELEASE": release,
        "SIGMA_STATE_DISK_MOUNT": str(state_root() / workspace_id),
        "SIGMA_AUTH_POC_WORKSPACE_ID": workspace_id,
        "SIGMA_AUTH_POC_GATEWAY_DIR": str(gateway_root() / workspace_id),
    }
    if local_poc():
        env["SIGMA_AUTH_POC_LOCAL_UID"] = str(os.geteuid())
        env["SIGMA_AUTH_POC_LOCAL_GID"] = str(os.getegid())
    return env


def _compose(workspace_id: str, *args: str, timeout: int = 75) -> str:
    result = subprocess.run(
        compose_args(workspace_id, *args),
        cwd=ROOT,
        env=compose_env(workspace_id),
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        timeout=timeout,
        check=False,
    )
    if result.returncode:
        raise RuntimeError("Container supervisor action failed")
    return result.stdout.strip()


def _lock_for(workspace_id: str) -> threading.Lock:
    with _LOCK:
        return _LOCKS.setdefault(workspace_id, threading.Lock())


def operate(action: str, workspace_id: str) -> dict[str, str]:
    """No destructive delete operation: credentials survive an ordinary stop."""
    workspace_id = validate_id(workspace_id)
    if action not in {"start", "status", "stop", "password"}:
        raise ValueError("Unsupported broker action")
    with _lock_for(workspace_id):
        if action == "start":
            prepare_state(workspace_id)
            prepare_gateway(workspace_id)
            _compose(workspace_id, "up", "-d", "--no-build", "--wait")
        elif action == "stop":
            _compose(workspace_id, "stop")
        if action == "stop":
            status = "stopped"
        else:
            browser = _compose(workspace_id, "ps", "-q", "browser", timeout=10)
            if not browser or not re.fullmatch(r"[0-9a-f]{12,64}", browser):
                status = "stopped"
            else:
                health = subprocess.run(
                    ["docker", "inspect", "--format", "{{.State.Health.Status}}", browser],
                    env=compose_env(workspace_id),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    text=True,
                    timeout=10,
                    check=False,
                )
                gateway = gateway_root() / workspace_id
                gateway_ready = all(
                    (gateway / name).is_socket() and not (gateway / name).is_symlink()
                    for name in ("vnc.sock", "model.sock")
                )
                if gateway_ready and local_poc():
                    # Normalize socket modes from macOS itself. Docker Desktop's
                    # Linux VM cannot chmod Unix sockets on its host bind mount.
                    for name in ("vnc.sock", "model.sock"):
                        socket_path = gateway / name
                        os.chmod(socket_path, 0o600)
                        if stat.S_IMODE(socket_path.lstat().st_mode) != 0o600:
                            gateway_ready = False
                status = (
                    "ready"
                    if health.returncode == 0
                    and health.stdout.strip() == "healthy"
                    and gateway_ready
                    else "unavailable"
                )
        result = {"status": status, "worker": "sigma-personal-" + workspace_id}
        if action == "password":
            if status != "ready":
                raise RuntimeError("Browser session is not ready")
            password = _compose(
                workspace_id, "exec", "-T", "browser", "cat", "/tmp/sigma-vnc-pass",
                timeout=10,
            )
            if not re.fullmatch(r"[A-Za-z0-9_-]{8}", password):
                raise RuntimeError("Browser credential is unavailable")
            result["password"] = password
        return result


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, _format: str, *args: object) -> None:
        # Never log session identifiers, HTTP targets or credentials.
        pass

    def _send(self, status: int, body: dict[str, str]) -> None:
        encoded = json.dumps(body, separators=(",", ":")).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(encoded)

    def _authorized_peer(self) -> bool:
        expected = int(os.environ.get("SIGMA_AUTH_BROKER_CLIENT_UID", "10001"))
        if hasattr(socket, "SO_PEERCRED"):
            raw = self.connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12)
            _pid, uid, _gid = struct.unpack("3i", raw)
            return uid == expected
        # macOS lacks SO_PEERCRED; the private, mode 0600 Unix socket grants
        # access only to the configured owner. It is never TCP-bound.
        return True

    def _dispatch(self, action: str) -> None:
        if not self._authorized_peer():
            self._send(403, {"error": "Forbidden"})
            return
        try:
            if action == "status":
                query = parse_qs(urlsplit(self.path).query)
                if set(query) != {"workspace_id"} or len(query["workspace_id"]) != 1:
                    raise ValueError("Invalid query")
                identifier = query["workspace_id"][0]
            else:
                length = self.headers.get("Content-Length", "")
                if not length.isdecimal() or not 1 <= int(length) <= MAX_REQUEST:
                    raise ValueError("Invalid content length")
                body = json.loads(self.rfile.read(int(length)))
                if not isinstance(body, dict) or set(body) != {"workspace_id"}:
                    raise ValueError("Invalid request")
                identifier = body["workspace_id"]
            self._send(200, operate(action, validate_id(identifier)))
        except (ValueError, TypeError, json.JSONDecodeError):
            self._send(400, {"error": "Invalid broker request"})
        except (OSError, RuntimeError, subprocess.TimeoutExpired):
            self._send(503, {"error": "Container session is unavailable"})

    def do_GET(self) -> None:
        if urlsplit(self.path).path != "/v1/status":
            self._send(404, {"error": "Not found"})
        else:
            self._dispatch("status")

    def do_POST(self) -> None:
        action = {"/v1/start": "start", "/v1/stop": "stop", "/v1/password": "password"}.get(self.path)
        if action is None:
            self._send(404, {"error": "Not found"})
        else:
            self._dispatch(action)


class _Server(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    daemon_threads = True


def serve() -> None:
    """Run as a dedicated host service with an explicit protected socket."""
    if os.environ.get("SIGMA_AUTH_POC_REAL_SIGNIN") == "1":
        raise RuntimeError("Real sign-in must remain disabled in the synthetic broker")
    path = Path(os.environ["SIGMA_AUTH_BROKER_SOCKET"])
    if not path.is_absolute() or path.exists() or path.is_symlink():
        raise RuntimeError("Broker socket path is not safe or already in use")
    _verify_traversable_root(path.parent)
    with _Server(str(path), _Handler) as server:
        try:
            os.chmod(path, 0o600)
            uid = int(os.environ.get("SIGMA_AUTH_BROKER_CLIENT_UID", "10001"))
            if os.geteuid() == 0:
                os.chown(path, uid, -1)
            elif uid != os.geteuid():
                raise RuntimeError("Broker cannot restrict client socket ownership")
            server.serve_forever(poll_interval=0.2)
        finally:
            path.unlink(missing_ok=True)


if __name__ == "__main__":
    serve()
