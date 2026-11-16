"""Host-side, synthetic-only manager for per-Google-user loopback containers.

This is a deliberately narrow Docker command broker, NOT a generic Docker API
or an OAuth token service. SIGMA authenticates the user and supplies only the
server-generated workspace ID via a private Unix socket. The broker can start,
query and stop a fixed pair of release-pinned images; it cannot execute arbitrary
commands, select other volumes/images, or accept caller-provided paths.
"""
from __future__ import annotations

import hmac
import json
import os
import re
import select
import socket
import socketserver
import stat
import struct
import subprocess
import time
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
_LAST_READINESS: dict[str, str] = {}
_LAST_DIAGNOSTIC_AT: dict[str, float] = {}
_DIAGNOSTIC_THREADS: dict[str, threading.Thread] = {}
_DIAGNOSTIC_LOCK = threading.Lock()
_DIAGNOSTIC_INTERVAL_SECONDS = 18.0
_SAFE_PROBE_FIELDS = {
    "component": r"browser|worker",
    "local_model_gateway_enabled": r"yes|no",
    "x11_socket": r"present|missing",
    "vnc_password_file": r"present|missing",
    "vnc_tcp_5900": r"listening|unreachable",
    "websocket_http_6080": r"http_[1-5][0-9]{2}|unreachable|invalid",
    "chromium_processes": r"[0-9]{1,8}",
    "xvfb_processes": r"[0-9]{1,8}",
    "x11vnc_processes": r"[0-9]{1,8}",
    "websockify_processes": r"[0-9]{1,8}",
    "oauth_http_8001": r"http_[1-5][0-9]{2}|unreachable|invalid",
    "model_http_8002": r"http_[1-5][0-9]{2}|unreachable|invalid",
    "uvicorn_processes": r"[0-9]{1,8}",
    "cgroup_memory_bytes": r"[0-9]{1,13}|unavailable",
    "cgroup_pids": r"[0-9]{1,13}|unavailable",
}


def _safe_probe_line(line: str) -> bool:
    key, separator, value = line.partition("=")
    pattern = _SAFE_PROBE_FIELDS.get(key)
    return bool(separator and pattern and re.fullmatch(pattern, value))

_SAFE_MILESTONES = {
    "SIGMA Personal browser: starting Xvfb",
    "SIGMA Personal browser: Xvfb ready; starting x11vnc",
    "SIGMA Personal browser: VNC relay launched; starting Chromium",
    "SIGMA Personal browser: Xvfb did not initialize",
    "SIGMA Personal worker: starting model gateway on private port 8002",
    "SIGMA Personal worker: starting localhost OAuth callback on port 8001",
}


def _diagnostic_failure_class(message: str) -> str:
    """Fixed failure classifications, never raw Docker logs or OAuth content."""
    content = message.lower()
    rules = (
        ("docker_desktop_file_sharing", ("mounts denied", "file sharing is not enabled")),
        ("port_conflict", ("port is already allocated", "address already in use")),
        ("docker_daemon_unavailable", ("cannot connect to the docker daemon", "is the docker daemon running")),
        ("image_platform_mismatch", ("no matching manifest", "exec format error", "requested image's platform")),
        ("insufficient_memory", ("out of memory", "oomkilled", "resource exhausted")),
        ("disk_full", ("no space left on device",)),
        ("chromium_sandbox", ("no usable sandbox", "failed to move to new namespace", "sandbox host", "seccomp violation")),
        ("display_unavailable", ("missing x server", "failed to connect to the x server", "xvfb did not initialize")),
        ("permission_denied", ("permission denied", "operation not permitted", "access is denied")),
    )
    for category, fragments in rules:
        if any(fragment in content for fragment in fragments):
            return category
    return "unclassified"


def _safe_milestones(raw_output: str) -> list[str]:
    """Only literal, release-owned milestones; never dump Docker logs."""
    return [line for line in raw_output.splitlines() if line in _SAFE_MILESTONES]



def _readiness_report(workspace_id: str, reason: str) -> None:
    """Emit only changed infrastructure stages, never URLs, tokens, or account data."""
    if _LAST_READINESS.get(workspace_id) == reason:
        return
    _LAST_READINESS[workspace_id] = reason
    print("Personal browser readiness: " + reason, flush=True)



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
        env["SIGMA_AUTH_POC_LOCAL_REAL_SIGNIN"] = (
            "1" if os.environ.get("SIGMA_AUTH_POC_LOCAL_REAL_SIGNIN") == "1" else "0"
        )
        if env["SIGMA_AUTH_POC_LOCAL_REAL_SIGNIN"] == "1":
            seed = os.environ.get("SIGMA_AUTH_POC_RPC_SEED", "")
            if not re.fullmatch(r"[0-9a-f]{64}", seed):
                raise ValueError("Local Personal worker authentication is unavailable")
            env["SIGMA_AUTH_POC_RPC_KEY"] = hmac.digest(
                bytes.fromhex(seed), workspace_id.encode("ascii"), "sha256"
            ).hex()
        checkout = os.environ.get("SIGMA_AUTH_POC_CHECKOUT_ID", "")
        if not re.fullmatch(r"[0-9a-f]{32}", checkout):
            raise ValueError("Local checkout identity is unavailable")
        env["SIGMA_AUTH_POC_CHECKOUT_ID"] = checkout
        env["SIGMA_AUTH_POC_LOCAL_UID"] = str(os.geteuid())
        env["SIGMA_AUTH_POC_LOCAL_GID"] = str(os.getegid())
    return env


def _probe_http_status(sock: socket.socket, target: str) -> str:
    """Read only the response status line; discard all potentially private data."""
    try:
        sock.settimeout(2)
        sock.sendall(
            (
                "GET " + target + " HTTP/1.0\r\n"
                "Host: 127.0.0.1\r\nConnection: close\r\n\r\n"
            ).encode("ascii")
        )
        first = sock.recv(96).split(b"\r\n", 1)[0].split()
        if len(first) >= 2 and first[0] in (b"HTTP/1.0", b"HTTP/1.1"):
            code = int(first[1])
            if 100 <= code <= 599:
                return "http_" + str(code)
        return "invalid"
    except (OSError, ValueError):
        return "unreachable"


def _host_readiness_snapshot(workspace_id: str, environment: dict[str, str]) -> None:
    """Test Docker loopback publishing AND the SIGMA Unix relay independently.

    No host port numbers, private socket paths, responses or account identifiers
    are included in stdout. This runs only in the explicitly local POC.
    """
    for label, port, target, socket_name in (
        ("vnc", 6080, "/vnc.html", "vnc.sock"),
        ("model", 8002, "/v1/account", "model.sock"),
    ):
        result = "unmapped"
        try:
            mapping = subprocess.run(
                compose_args(workspace_id, "port", "auth-poc", str(port)),
                cwd=ROOT,
                env=environment,
                text=True,
                capture_output=True,
                timeout=8,
                check=False,
            )
            if mapping.returncode == 0:
                match = re.fullmatch(r"127\.0\.0\.1:(\d{1,5})", mapping.stdout.strip())
                if match is not None and 1 <= int(match.group(1)) <= 65535:
                    with socket.create_connection(
                        ("127.0.0.1", int(match.group(1))), timeout=2
                    ) as connection:
                        result = _probe_http_status(connection, target)
                else:
                    result = "mapping_invalid"
        except (OSError, subprocess.TimeoutExpired):
            result = "unreachable"
        print(f"  host.loopback_{label}={result}", flush=True)

        relay_result = "missing"
        try:
            relay = gateway_root() / workspace_id / socket_name
            if relay.is_socket() and not relay.is_symlink():
                with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
                    connection.settimeout(2)
                    connection.connect(str(relay))
                    relay_result = _probe_http_status(connection, target)
        except OSError:
            relay_result = "unreachable"
        print(f"  host.private_{label}={relay_result}", flush=True)


def _schedule_diagnostics(workspace_id: str, cause: str, *, force: bool = False) -> None:
    """Run costly Docker probes without blocking SIGMA's browser status API.

    One probe per user at a time; throttle repeated unavailable statuses.
    This keeps a frozen or emulated Docker Desktop from turning a quick status
    check into a second multi-minute timeout. No diagnostics leave the host.
    """
    if not local_poc():
        return
    now = time.monotonic()
    with _DIAGNOSTIC_LOCK:
        current = _DIAGNOSTIC_THREADS.get(workspace_id)
        if current is not None and current.is_alive():
            return
        if not force and now - _LAST_DIAGNOSTIC_AT.get(workspace_id, -1e9) < _DIAGNOSTIC_INTERVAL_SECONDS:
            return
        _LAST_DIAGNOSTIC_AT[workspace_id] = now
        task = threading.Thread(
            target=_container_diagnostics,
            args=(workspace_id, cause),
            kwargs={"force": True},
            name="sigma-personal-diagnostics",
            daemon=True,
        )
        _DIAGNOSTIC_THREADS[workspace_id] = task
        task.start()


def _container_diagnostics(workspace_id: str, cause: str, *, force: bool = False) -> None:
    """Diagnose BOTH Docker containers and their internals without raw logs.

    No Docker inspect Env, Config.Cmd, healthcheck output, browser URLs or
    account data can enter the diagnostic output. Throttle periodic checks.
    """
    if not local_poc():
        return
    now = time.monotonic()
    if not force and now - _LAST_DIAGNOSTIC_AT.get(workspace_id, -1e9) < _DIAGNOSTIC_INTERVAL_SECONDS:
        return
    _LAST_DIAGNOSTIC_AT[workspace_id] = now
    print(f"SIGMA Personal diagnostic snapshot: {cause}", flush=True)
    try:
        environment = compose_env(workspace_id)
    except (OSError, ValueError):
        print("  compose_environment=invalid", flush=True)
        return
    _host_readiness_snapshot(workspace_id, environment)
    for service, probe_path, mode, interpreter in (
        ("auth-poc", "/opt/sigma/auth-poc/diag_probe.py", "worker", "/opt/venv/bin/python"),
        ("browser", "/opt/sigma/diag_probe.py", "browser", "python3"),
    ):
        try:
            listing = subprocess.run(
                compose_args(workspace_id, "ps", "--all", "-q", service),
                cwd=ROOT,
                env=environment,
                text=True,
                capture_output=True,
                timeout=8,
                check=False,
            )
            container_id = listing.stdout.strip()
            if listing.returncode or not re.fullmatch(r"[a-f0-9]{12,64}", container_id):
                print(f"  {service}.container=missing_or_stopped", flush=True)
                continue
            inspect = subprocess.run(
                [
                    "docker", "inspect", "--format",
                    "{{.State.Status}} {{.State.ExitCode}} "
                    "{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}} "
                    "{{.RestartCount}}",
                    container_id,
                ],
                cwd=ROOT,
                env=environment,
                text=True,
                capture_output=True,
                timeout=8,
                check=False,
            )
            state = inspect.stdout.strip().split()
            if (
                inspect.returncode == 0
                and len(state) == 4
                and state[0] in {"created", "running", "restarting", "exited", "dead", "paused"}
                and state[1].isdecimal()
                and state[2] in {"none", "starting", "healthy", "unhealthy"}
                and state[3].isdecimal()
            ):
                print(
                    f"  {service}.state={state[0]} exit={state[1]} "
                    f"health={state[2]} restarts={state[3]}",
                    flush=True,
                )
            else:
                print(f"  {service}.state=inspect_failed", flush=True)
            # Docker logs may contain OAuth URLs and private data. Collect
            # them locally but print ONLY hardcoded startup milestone lines.
            logs = subprocess.run(
                ["docker", "logs", "--tail", "80", container_id],
                cwd=ROOT,
                env=environment,
                text=True,
                capture_output=True,
                timeout=8,
                check=False,
            )
            output = logs.stdout + "\n" + logs.stderr
            for message in _safe_milestones(output):
                print("  " + message, flush=True)
            category = _diagnostic_failure_class(output)
            if category != "unclassified":
                print(f"  {service}.failure_class={category}", flush=True)
            if state[:1] != ["running"]:
                continue
            result = subprocess.run(
                ["docker", "exec", container_id, interpreter, probe_path, mode],
                cwd=ROOT,
                env=environment,
                text=True,
                capture_output=True,
                timeout=12,
                check=False,
            )
            if result.returncode:
                print(f"  {service}.inside_probe=unavailable exit={result.returncode}", flush=True)
                continue
            # Only fixed schema lines generated by our trusted, read-only probe.
            # Never relay unexpected container output into the host console.
            for line in result.stdout.splitlines()[:20]:
                if _safe_probe_line(line):
                    print(f"  {service}.{line}", flush=True)
        except (OSError, subprocess.TimeoutExpired):
            print(f"  {service}.diagnostics=timed_out_or_unavailable", flush=True)


def _compose(workspace_id: str, *args: str, timeout: int = 75) -> str:
    try:
        result = subprocess.run(
            compose_args(workspace_id, *args),
            cwd=ROOT,
            env=compose_env(workspace_id),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        print(f"Personal Docker {args[0]} timed out or failed to launch.", flush=True)
        _schedule_diagnostics(workspace_id, "compose_execution_failed", force=True)
        raise
    if result.returncode:
        # Docker stderr can include private host paths. Print only the fixed
        # operation name and status, not subprocess output or arguments.
        print(
            f"Personal Docker {args[0]} failed (exit {result.returncode}; "
            f"failure_class={_diagnostic_failure_class(result.stderr or '')}).",
            flush=True,
        )
        _schedule_diagnostics(workspace_id, "compose_" + args[0] + "_failed", force=True)
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
            status = conn.recv(128).split(b"\r\n", 1)[0]
            # noVNC/websockify may answer with HTTP/1.0, while FastAPI
            # generally uses HTTP/1.1. Both are valid, healthy HTTP 200.
            return status.startswith((b"HTTP/1.0 200 ", b"HTTP/1.1 200 "))
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
            prepare_gateway(workspace_id)
            # A successful OAuth callback leaves Chromium displaying its
            # "Return to SIGMA" page. Disconnect clears worker credentials,
            # but a best-effort stop may fail. Always create a fresh disposable
            # browser on the next explicit start, even if Docker still reports
            # the previous browser as running. The credential worker and its
            # durable per-user state are NOT recreated.
            _compose(
                workspace_id, "up", "-d", "--no-build", "--wait",
                "--force-recreate", "browser",
            )
        elif action == "stop":
            _compose(workspace_id, "stop")
            if local_poc():
                _stop_local_gateway(workspace_id)
        if action == "stop":
            status = "stopped"
            _readiness_report(workspace_id, "stopped")
        else:
            browser = _compose(workspace_id, "ps", "-q", "browser", timeout=10)
            if not browser or not re.fullmatch(r"[0-9a-f]{12,64}", browser):
                status = "stopped"
                _readiness_report(workspace_id, "browser container not running")
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
                browser_healthy = (
                    health.returncode == 0 and health.stdout.strip() == "healthy"
                )
                gateway = gateway_root() / workspace_id
                reason = "ready"
                try:
                    if local_poc():
                        _ensure_local_gateway(workspace_id)
                    sockets_ready = all(
                        (gateway / name).is_socket() and not (gateway / name).is_symlink()
                        for name in ("vnc.sock", "model.sock")
                    )
                    if not sockets_ready:
                        reason = "private gateway sockets unavailable"
                    else:
                        vnc_ready = _socket_http_ready(gateway / "vnc.sock", "/vnc.html")
                        model_ready = _socket_http_ready(gateway / "model.sock", "/v1/account")
                        if not vnc_ready:
                            reason = "VNC viewer relay did not return HTTP 200"
                        elif not model_ready:
                            reason = "model worker relay did not return HTTP 200"
                    if reason == "ready" and local_poc():
                        parent = gateway.lstat()
                        permissions_ready = (
                            stat.S_ISDIR(parent.st_mode)
                            and not gateway.is_symlink()
                            and stat.S_IMODE(parent.st_mode) == 0o700
                            and parent.st_uid == os.geteuid()
                        )
                        for name in ("vnc.sock", "model.sock"):
                            info = (gateway / name).lstat()
                            permissions_ready = permissions_ready and (
                                stat.S_ISSOCK(info.st_mode)
                                and not (gateway / name).is_symlink()
                                and info.st_uid == os.geteuid()
                                and stat.S_IMODE(info.st_mode) == 0o600
                            )
                        if not permissions_ready:
                            reason = "private relay socket permissions invalid"
                except (OSError, RuntimeError, subprocess.TimeoutExpired):
                    reason = "private gateway setup failed"
                if not browser_healthy:
                    reason = "browser container health " + (
                        health.stdout.strip()
                        if health.returncode == 0
                        and health.stdout.strip() in {"starting", "unhealthy"}
                        else "unavailable"
                    )
                status = "ready" if reason == "ready" else "unavailable"
                _readiness_report(workspace_id, reason)
        if status != "ready" and action != "stop":
            _schedule_diagnostics(workspace_id, "readiness_" + status)
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
            print("SIGMA Personal broker: private container operation failed", flush=True)
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
