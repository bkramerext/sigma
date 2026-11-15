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
import select
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
_GATEWAY_SERVERS: dict[str, list[tuple[Path, socketserver.BaseServer, threading.Thread]]] = {}


def local_poc() -> bool:
    """Explicit single-machine POC: host user owns native private relay sockets.

    Production uses worker UID 10001; local Docker uses the launching user's
    UID for its isolated credential volume. The browser remains a separate UID.
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
        browser_platform = os.environ.get("SIGMA_AUTH_POC_BROWSER_PLATFORM", "linux/amd64")
        if browser_platform not in {"linux/amd64", "linux/arm64"}:
            raise ValueError("Unsupported local browser platform")
        env["SIGMA_AUTH_POC_BROWSER_PLATFORM"] = browser_platform
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


def _socket_http_ready(path: Path, target: str) -> bool:
    """Check that a private Unix relay accepts HTTP, not just that its inode exists."""
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as conn:
            conn.settimeout(3)
            conn.connect(str(path))
            request = (
                f"GET {target} HTTP/1.1\r\nHost: private-relay\r\n"
                "Connection: close\r\n\r\n"
            )
            conn.sendall(request.encode("ascii"))
            return conn.recv(128).startswith(b"HTTP/1.1 200 ")
    except OSError:
        return False


class _GatewayRelayHandler(socketserver.BaseRequestHandler):
    """Forward one Unix stream to a fixed loopback-only Docker published port."""

    def handle(self) -> None:
        client = self.request
        try:
            upstream = socket.create_connection(
                ("127.0.0.1", self.server.upstream_port), timeout=5
            )
        except OSError:
            return
        with upstream:
            try:
                while True:
                    readable, _, _ = select.select([client, upstream], [], [], 300)
                    if not readable:
                        continue
                    for source in readable:
                        payload = source.recv(65536)
                        if not payload:
                            return
                        target = upstream if source is client else client
                        target.sendall(payload)
            except OSError:
                return


class _GatewayServer(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    daemon_threads = True
    block_on_close = False


def _stop_local_gateway(workspace_id: str) -> None:
    active = _GATEWAY_SERVERS.pop(workspace_id, [])
    for path, server, thread in active:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
        try:
            info = path.lstat()
            if stat.S_ISSOCK(info.st_mode) and info.st_uid == os.geteuid():
                path.unlink()
        except FileNotFoundError:
            pass


def _published_loopback_port(workspace_id: str, container_port: int) -> int:
    output = _compose(
        workspace_id, "port", "auth-poc", str(container_port), timeout=10
    )
    matches = re.findall(r"(?m)^127\.0\.0\.1:(\d+)$", output)
    if len(matches) != 1:
        raise RuntimeError("Private loopback port mapping is unavailable")
    port = int(matches[0])
    if not 1 <= port <= 65535:
        raise RuntimeError("Private loopback port mapping is invalid")
    return port


def _ensure_local_gateway(workspace_id: str) -> None:
    """Create native host sockets that forward only to fixed loopback ports."""
    gateway = prepare_gateway(workspace_id)
    active = _GATEWAY_SERVERS.get(workspace_id, [])
    if len(active) == 2 and all(path.is_socket() and thread.is_alive() for path, _, thread in active):
        return
    _stop_local_gateway(workspace_id)
    specifications = (
        ("vnc.sock", _published_loopback_port(workspace_id, 6080)),
        ("model.sock", _published_loopback_port(workspace_id, 8002)),
    )
    started: list[tuple[Path, socketserver.BaseServer, threading.Thread]] = []
    try:
        for name, upstream_port in specifications:
            path = gateway / name
            if path.exists() or path.is_symlink():
                old = path.lstat()
                if not stat.S_ISSOCK(old.st_mode) or old.st_uid != os.geteuid():
                    raise RuntimeError("Unsafe existing private gateway socket")
                path.unlink()
            server = _GatewayServer(str(path), _GatewayRelayHandler)
            server.upstream_port = upstream_port
            os.chmod(path, 0o600)
            thread = threading.Thread(
                target=server.serve_forever, kwargs={"poll_interval": 0.2}, daemon=True
            )
            thread.start()
            started.append((path, server, thread))
        _GATEWAY_SERVERS[workspace_id] = started
    except Exception:
        for path, server, thread in started:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
            path.unlink(missing_ok=True)
        raise


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
            if local_poc():
                _stop_local_gateway(workspace_id)
            else:
                prepare_gateway(workspace_id)
            _compose(workspace_id, "up", "-d", "--no-build", "--wait")
        elif action == "stop":
            _compose(workspace_id, "stop")
            if local_poc():
                _stop_local_gateway(workspace_id)
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
                try:
                    if local_poc():
                        _ensure_local_gateway(workspace_id)
                    gateway_ready = all(
                        (gateway / name).is_socket() and not (gateway / name).is_symlink()
                        for name in ("vnc.sock", "model.sock")
                    )
                    if gateway_ready:
                        gateway_ready = (
                            _socket_http_ready(gateway / "vnc.sock", "/vnc.html")
                            and _socket_http_ready(gateway / "model.sock", "/v1/account")
                        )
                    if gateway_ready and local_poc():
                        parent = gateway.lstat()
                        gateway_ready = (
                            stat.S_ISDIR(parent.st_mode)
                            and not gateway.is_symlink()
                            and stat.S_IMODE(parent.st_mode) == 0o700
                            and parent.st_uid == os.geteuid()
                        )
                        for name in ("vnc.sock", "model.sock"):
                            socket_path = gateway / name
                            info = socket_path.lstat()
                            gateway_ready = gateway_ready and (
                                stat.S_ISSOCK(info.st_mode)
                                and not socket_path.is_symlink()
                                and info.st_uid == os.geteuid()
                                and stat.S_IMODE(info.st_mode) == 0o600
                            )
                except (OSError, RuntimeError, subprocess.TimeoutExpired):
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
