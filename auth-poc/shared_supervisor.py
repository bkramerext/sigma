"""Tiny root supervisor; both services run in ONE shared Docker container.

The root process handles only lifecycle, never OAuth tokens or model payloads.
FastAPI runs as UID 10001; disposable Chromium runs as UID 11001. The browser
does not have permission to read the worker's key or credential records.
"""
from __future__ import annotations

import json
import os
import re
import signal
import socket
import socketserver
import stat
import subprocess
import threading
import time
from pathlib import Path

WORKER_UID = 10001
BROWSER_UID = 11001
CONTROL = Path("/run/sigma-browser-control/control.sock")
BROWSER_HOME = Path("/tmp/sigma-browser")
_LOCK = threading.Lock()
_BROWSER: subprocess.Popen | None = None
_WORKER: subprocess.Popen | None = None
_OWNER: str | None = None
_STARTED_AT = 0.0


def _alive() -> bool:
    return _BROWSER is not None and _BROWSER.poll() is None


def _browser_ready() -> bool:
    if not _alive():
        return False
    try:
        with socket.create_connection(("127.0.0.1", 6080), timeout=1) as s:
            s.sendall(b"GET /vnc.html HTTP/1.0\r\nHost: 127.0.0.1\r\n\r\n")
            return s.recv(128).startswith((b"HTTP/1.1 200", b"HTTP/1.0 200"))
    except OSError:
        return False


def _stop() -> None:
    global _BROWSER
    browser = _BROWSER
    _BROWSER = None
    if browser is not None:
        # Terminate helpers even when the Chromium leader has exited.
        try:
            os.killpg(browser.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            browser.wait(timeout=4)
        except subprocess.TimeoutExpired:
            pass
        try:
            os.killpg(browser.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        try:
            browser.wait(timeout=2)
        except subprocess.TimeoutExpired:
            pass
    if BROWSER_HOME.exists() or BROWSER_HOME.is_symlink():
        if BROWSER_HOME.is_symlink() or BROWSER_HOME.stat().st_uid != BROWSER_UID:
            raise RuntimeError("Untrusted browser home")
        # The supervisor deliberately lacks CAP_DAC_OVERRIDE/FOWNER. Delete
        # the isolated 0700 browser profile as its own unprivileged UID.
        cleanup = subprocess.run(
            [
                "/usr/bin/setpriv",
                "--reuid=11001",
                "--regid=11001",
                "--clear-groups",
                "/usr/bin/rm",
                "-rf",
                "--",
                str(BROWSER_HOME),
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=5,
        )
        if cleanup.returncode != 0:
            raise RuntimeError("Temporary browser cleanup failed")


def _start() -> bool:
    global _BROWSER
    if _browser_ready():
        return True
    _stop()
    BROWSER_HOME.mkdir(mode=0o700)
    os.chmod(BROWSER_HOME, 0o700)
    os.chown(BROWSER_HOME, BROWSER_UID, BROWSER_UID)
    env = dict(os.environ)
    for key in tuple(env):
        # Browser never receives the shared worker's RPC secret or vault paths.
        if key.startswith("SIGMA_AUTH_POC_RPC") or key.startswith("SIGMA_PERSONAL_SHARED"):
            env.pop(key, None)
    env.update({
        "HOME": str(BROWSER_HOME),
        "SIGMA_BROWSER_HOME": str(BROWSER_HOME),
        "SIGMA_BROWSER_PROFILE": str(BROWSER_HOME / "chromium"),
        "SIGMA_BROWSER_PASSWORD_PATH": str(BROWSER_HOME / "vnc-pass"),
    })
    _BROWSER = subprocess.Popen(
        ["/usr/bin/setpriv", "--reuid=11001", "--regid=11001",
         "--clear-groups", "/bin/sh", "/opt/sigma/auth-poc/boot.sh"],
        env=env,
        cwd="/tmp",
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    for _ in range(120):
        if _browser_ready():
            return True
        if not _alive():
            break
        time.sleep(0.1)
    _stop()
    return False


class Control(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        # Linux SO_PEERCRED enforces worker-only commands, even if socket mode
        # or parent directory permissions are changed accidentally.
        import struct

        raw = self.request.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12)
        pid, uid, gid = struct.unpack("3i", raw)
        if uid != WORKER_UID:
            return
        command = self.rfile.readline(96).strip().decode("ascii", errors="ignore")
        parts = command.split(" ")
        action, workspace = parts if len(parts) == 2 else ("", "")
        if not re.fullmatch(r"[0-9a-f]{32}", workspace):
            self.wfile.write((json.dumps({"status": "unavailable"}) + "\n").encode())
            return
        global _OWNER, _STARTED_AT
        with _LOCK:
            if action == "start":
                if _OWNER != workspace:
                    _stop()
                    _OWNER = None
                ready = _start()
                _OWNER = workspace if ready else None
                _STARTED_AT = time.monotonic() if ready else 0.0
                result = {"status": "ready" if ready else "unavailable"}
            elif action == "stop":
                if _OWNER == workspace:
                    _stop()
                    _OWNER = None
                result = {"status": "stopped"}
            elif action == "status":
                ready = _OWNER == workspace and _browser_ready()
                if _OWNER == workspace and not ready:
                    _stop()
                    _OWNER = None
                result = {"status": "ready" if ready else "stopped"}
            elif action == "password" and _OWNER == workspace:
                password = BROWSER_HOME / "vnc-pass"
                try:
                    result = subprocess.run(
                        [
                            "/usr/bin/setpriv",
                            "--reuid=11001",
                            "--regid=11001",
                            "--clear-groups",
                            "/usr/bin/cat",
                            str(password),
                        ],
                        capture_output=True,
                        check=False,
                        timeout=2,
                    )
                    value = result.stdout.decode("ascii").strip() if result.returncode == 0 else ""
                except (OSError, UnicodeDecodeError, subprocess.TimeoutExpired):
                    value = ""
                result = (
                    {"status": "ready", "password": value}
                    if _browser_ready() and re.fullmatch(r"[A-Za-z0-9_-]{8}", value)
                    else {"status": "unavailable"}
                )
            else:
                result = {"status": "unavailable"}
        self.wfile.write((json.dumps(result) + "\n").encode("utf-8"))


class Server(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    daemon_threads = True
    allow_reuse_address = False


def _prepare_volumes() -> None:
    """First-start creation only; NEVER import historical credential files."""
    records = Path("/var/lib/sigma-shared/records")
    workspaces = Path("/var/lib/sigma-shared/workspaces")
    key_home = Path("/var/lib/sigma-shared-key")
    for directory in (records, workspaces, key_home):
        if directory.is_symlink():
            raise SystemExit("Shared Personal storage contains a symlink")
        directory.mkdir(parents=True, exist_ok=True)
        info = directory.lstat()
        if (
            not stat.S_ISDIR(info.st_mode)
            or info.st_uid != WORKER_UID
            or stat.S_IMODE(info.st_mode) != 0o700
        ):
            raise SystemExit("Shared Personal storage permissions are invalid")
    # Key generation occurs in an isolated worker-UID subprocess. The root
    # supervisor intentionally cannot traverse the mode-0700 key directory.
    initialized = subprocess.run(
        [
            "/usr/bin/setpriv",
            "--reuid=10001",
            "--regid=10001",
            "--clear-groups",
            "/opt/venv/bin/python",
            "/opt/sigma/auth-poc/shared_initialize.py",
        ],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
        timeout=10,
    )
    if initialized.returncode != 0:
        raise SystemExit("Shared Personal encryption initialization failed")


def main() -> None:
    global _WORKER, _OWNER
    if os.geteuid() != 0:
        raise SystemExit("Shared Personal supervisor requires root for UID separation")
    _prepare_volumes()
    CONTROL.parent.mkdir(parents=True, exist_ok=True)
    os.chown(CONTROL.parent, 0, WORKER_UID)
    os.chmod(CONTROL.parent, 0o750)
    if CONTROL.exists() or CONTROL.is_symlink():
        info = CONTROL.lstat()
        if not stat.S_ISSOCK(info.st_mode) or info.st_uid != 0:
            raise SystemExit("Unsafe existing browser control socket")
        CONTROL.unlink()
    server = Server(str(CONTROL), Control)
    os.chown(CONTROL, 0, WORKER_UID)
    os.chmod(CONTROL, 0o660)
    _WORKER = subprocess.Popen(
        ["/usr/bin/setpriv", "--reuid=10001", "--regid=10001",
         "--clear-groups", "/opt/venv/bin/uvicorn", "shared_service:app",
         "--host", "0.0.0.0", "--port", "8001", "--no-access-log"],
        cwd="/opt/sigma/auth-poc", env=os.environ,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
    )

    def shutdown(_signal: int, _frame: object) -> None:
        server.shutdown()

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        while _WORKER.poll() is None:
            with _LOCK:
                if _OWNER is not None and time.monotonic() - _STARTED_AT > 360:
                    _stop()
                    _OWNER = None
            time.sleep(0.5)
    finally:
        with _LOCK:
            _stop()
        server.shutdown()
        server.server_close()
        if _WORKER.poll() is None:
            _WORKER.terminate()
            try:
                _WORKER.wait(timeout=5)
            except subprocess.TimeoutExpired:
                _WORKER.kill()
                _WORKER.wait()


if __name__ == "__main__":
    main()
