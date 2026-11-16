"""Local host-only broker for ONE shared Personal ChatGPT Docker container.

SIGMA derives the workspace ID from a verified Google identity. This broker
never accepts arbitrary paths, Docker commands, OAuth tokens or credentials.
It only owns local Unix relays and a fixed shared Compose service.
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
import threading
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parents[1]
_WORKSPACE = re.compile(r"[0-9a-f]{32}\\Z")
_PORT = re.compile(r"127\.0\.0\.1:(\d+)\Z")
_LOCK = threading.RLock()
_ACTIVE: str | None = None
_GATEWAYS: dict[str, dict[str, tuple[Path, socketserver.BaseServer, threading.Thread]]] = {}
MAX_REQUEST = 512


def _valid(workspace: str) -> str:
    if not isinstance(workspace, str) or not _WORKSPACE.fullmatch(workspace):
        raise ValueError("Invalid workspace identity")
    return workspace


def _compose(*args: str) -> str:
    checkout = os.environ.get("SIGMA_AUTH_POC_CHECKOUT_ID", "")
    if not _WORKSPACE.fullmatch(checkout):
        raise RuntimeError("Invalid checkout identity")
    env = dict(os.environ)
    result = subprocess.run(
        ["docker", "compose", "--project-name", "sigma-shared-" + checkout,
         "-f", "deploy/personal-shared.compose.yaml", *args],
        cwd=ROOT, env=env, capture_output=True, text=True,
        check=False, timeout=150 if "up" in args else 20,
    )
    if result.returncode:
        # Never surface Docker errors containing paths, environment or tokens.
        raise RuntimeError("Shared Personal Docker service unavailable")
    return result.stdout.strip()


def _port(number: int) -> int:
    raw = _compose("port", "personal", str(number))
    match = _PORT.fullmatch(raw)
    if not match:
        raise RuntimeError("Shared Personal port is not host-loopback-only")
    port = int(match.group(1))
    if not 1 <= port <= 65535:
        raise RuntimeError("Invalid shared Personal port")
    return port


def _key(workspace: str) -> str:
    seed = os.environ.get("SIGMA_AUTH_POC_RPC_SEED", "")
    if not re.fullmatch(r"[0-9a-f]{64}", seed):
        raise RuntimeError("Private RPC authentication unavailable")
    return hmac.digest(bytes.fromhex(seed), workspace.encode("ascii"), "sha256").hex()


def _rpc(workspace: str, operation: str) -> dict:
    if operation not in {"start", "stop", "status", "password"}:
        raise ValueError("Unsupported browser operation")
    method = "GET" if operation == "status" else "POST"
    path = "/v1/browser/" + operation
    import http.client

    connection = http.client.HTTPConnection("127.0.0.1", _port(8001), timeout=35)
    try:
        connection.request(
            method, path, headers={
                "X-Sigma-Workspace": workspace,
                "X-Sigma-Worker-Key": _key(workspace),
                "Content-Length": "0",
            },
        )
        response = connection.getresponse()
        body = response.read(2048)
        if response.status == 409:
            return {"status": "unavailable"}
        if response.status != 200:
            raise RuntimeError("Shared Personal browser operation denied")
        state = json.loads(body)
        if state.get("status") not in {"ready", "stopped", "unavailable"}:
            raise RuntimeError("Invalid Personal browser response")
        return state
    finally:
        connection.close()


class RelayHandler(socketserver.BaseRequestHandler):
    def handle(self) -> None:
        client = self.request
        try:
            upstream = socket.create_connection(
                ("127.0.0.1", self.server.upstream_port), timeout=5
            )
            with upstream:
                while True:
                    readable, _, _ = select.select([client, upstream], [], [], 300)
                    if not readable:
                        continue
                    for source in readable:
                        chunk = source.recv(65536)
                        if not chunk:
                            return
                        (upstream if source is client else client).sendall(chunk)
        except OSError:
            return


class RelayServer(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    daemon_threads = True
    block_on_close = False


def _gateway_dir(workspace: str) -> Path:
    root = Path(os.environ["SIGMA_AUTH_BROKER_GATEWAY_ROOT"])
    if not root.is_absolute() or root.is_symlink():
        raise RuntimeError("Invalid private relay root")
    dest = root / _valid(workspace)
    dest.mkdir(mode=0o700, exist_ok=True)
    info = dest.lstat()
    if (
        not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid()
        or stat.S_IMODE(info.st_mode) != 0o700
    ):
        raise RuntimeError("Private relay permissions are invalid")
    return dest


def _relay(workspace: str, name: str, port: int) -> None:
    active = _GATEWAYS.setdefault(workspace, {})
    existing = active.get(name)
    if existing and existing[0].is_socket() and existing[2].is_alive():
        return
    if existing:
        _unrelay(workspace, name)
    path = _gateway_dir(workspace) / name
    if path.exists() or path.is_symlink():
        # Fail rather than unlink unknown filesystem entries.
        raise RuntimeError("Untrusted private relay pathname")
    server = RelayServer(str(path), RelayHandler)
    server.upstream_port = port
    os.chmod(path, 0o600)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    active[name] = path, server, thread


def _unrelay(workspace: str, name: str) -> None:
    active = _GATEWAYS.get(workspace, {})
    entry = active.pop(name, None)
    if entry is None:
        return
    path, server, thread = entry
    server.shutdown()
    server.server_close()
    thread.join(timeout=2)
    if path.is_socket() and path.lstat().st_uid == os.geteuid():
        path.unlink()


def _ensure_shared() -> None:
    # Exactly one shared Compose project for the launching SIGMA checkout.
    if not _compose("ps", "-q", "personal"):
        _compose("up", "-d", "--no-build", "--wait")
    else:
        _compose("ps", "--status", "running", "-q", "personal")


def operate(action: str, workspace: str) -> dict:
    global _ACTIVE
    _valid(workspace)
    if action not in {"start", "stop", "status", "password"}:
        raise ValueError("Unsupported operation")
    with _LOCK:
        _ensure_shared()
        # Model relay stays available when Chromium closes; no idle browser.
        _relay(workspace, "model.sock", _port(8001))
        if action == "start":
            state = _rpc(workspace, "start")
            if state["status"] == "ready":
                _ACTIVE = workspace
                _relay(workspace, "vnc.sock", _port(6080))
        elif action == "stop":
            state = _rpc(workspace, "stop")
            _unrelay(workspace, "vnc.sock")
            if _ACTIVE == workspace:
                _ACTIVE = None
        elif action == "password":
            state = _rpc(workspace, "password")
        else:
            state = _rpc(workspace, "status")
        if action == "status" and state["status"] != "ready":
            _unrelay(workspace, "vnc.sock")
        result = {"status": state["status"], "worker": "sigma-personal-" + workspace}
        if action == "password" and "password" in state:
            result["password"] = state["password"]
        return result


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args: object) -> None:
        pass

    def _send(self, code: int, value: dict) -> None:
        data = json.dumps(value, separators=(",", ":")).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(data)

    def _authorized(self) -> bool:
        uid = int(os.environ.get("SIGMA_AUTH_BROKER_CLIENT_UID", "10001"))
        if hasattr(socket, "SO_PEERCRED"):
            pid, peer_uid, gid = struct.unpack(
                "3i", self.connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12)
            )
            return peer_uid == uid
        return True

    def _dispatch(self, operation: str) -> None:
        if not self._authorized():
            self._send(403, {"error": "Forbidden"})
            return
        try:
            if operation == "status":
                query = parse_qs(urlsplit(self.path).query)
                if set(query) != {"workspace_id"} or len(query["workspace_id"]) != 1:
                    raise ValueError("Invalid status request")
                workspace = query["workspace_id"][0]
            else:
                length = self.headers.get("Content-Length", "")
                if not length.isdecimal() or not 1 <= int(length) <= MAX_REQUEST:
                    raise ValueError("Invalid request length")
                body = json.loads(self.rfile.read(int(length)))
                if not isinstance(body, dict) or set(body) != {"workspace_id"}:
                    raise ValueError("Invalid request")
                workspace = body["workspace_id"]
            self._send(200, operate(operation, _valid(workspace)))
        except (ValueError, TypeError, json.JSONDecodeError):
            self._send(400, {"error": "Invalid request"})
        except (RuntimeError, OSError, subprocess.TimeoutExpired):
            self._send(503, {"error": "Personal container unavailable"})

    def do_GET(self) -> None:
        if urlsplit(self.path).path != "/v1/status":
            self._send(404, {"error": "Not found"})
        else:
            self._dispatch("status")

    def do_POST(self) -> None:
        op = {"/v1/start": "start", "/v1/stop": "stop",
              "/v1/password": "password"}.get(self.path)
        if op:
            self._dispatch(op)
        else:
            self._send(404, {"error": "Not found"})


class Server(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    daemon_threads = True


def main() -> None:
    path = Path(os.environ["SIGMA_AUTH_BROKER_SOCKET"])
    if not path.is_absolute() or path.exists() or path.is_symlink():
        raise RuntimeError("Private broker socket already exists")
    if path.parent.stat().st_uid != os.geteuid():
        raise RuntimeError("Private broker owner mismatch")
    with Server(str(path), Handler) as service:
        os.chmod(path, 0o600)
        try:
            service.serve_forever(poll_interval=0.2)
        finally:
            for workspace, names in list(_GATEWAYS.items()):
                for name in list(names):
                    _unrelay(workspace, name)
            path.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
