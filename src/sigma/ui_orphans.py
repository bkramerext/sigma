"""Conservative recovery of SIGMA dev servers orphaned by old launchers.

Port ownership alone is never permission to terminate a process.
"""

import json
import os
import signal
import subprocess
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

PORTS = (8000, 5173)


def _command(*args: str) -> str | None:
    try:
        return subprocess.check_output(
            list(args), text=True, stderr=subprocess.DEVNULL, timeout=2
        ).strip()
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None


def _listeners(port: int) -> set[int]:
    result = _command("lsof", "-nP", "-iTCP:" + str(port), "-sTCP:LISTEN", "-Fp")
    if result is None:
        return set()
    return {
        int(line[1:])
        for line in result.splitlines()
        if line.startswith("p") and line[1:].isdigit()
    }


def _process(pid: int) -> tuple[str, str, str, str] | None:
    if pid <= 1 or pid == os.getpid():
        return None
    fields = tuple(
        _command("ps", "-ww", "-p", str(pid), "-o", field + "=")
        for field in ("uid", "lstart", "command")
    )
    if any(field is None or not field for field in fields):
        return None
    cwd_output = _command("lsof", "-nP", "-a", "-p", str(pid), "-d", "cwd", "-Fn")
    if cwd_output is None:
        return None
    paths = [line[1:] for line in cwd_output.splitlines() if line.startswith("n")]
    if len(paths) != 1:
        return None
    uid, start, command = fields
    assert uid is not None and start is not None and command is not None
    return uid, start, command, paths[0]


def _sigma_instance(port: int) -> str | None:
    try:
        with urlopen(
            "http://127.0.0.1:" + str(port) + "/api/ui-instance", timeout=0.35
        ) as response:
            if response.status != 200:
                return None
            raw = response.read(2048)
        parsed = json.loads(raw)
        value = parsed.get("instance") if isinstance(parsed, dict) else None
        if (
            isinstance(value, str)
            and len(value) == 32
            and all(c in "0123456789abcdef" for c in value)
        ):
            return value
        return None
    except (URLError, OSError, ValueError):
        return None


def _verified(port: int, pid: int, root: Path) -> tuple[str, str, str, str] | None:
    """Require exact checkout, known SIGMA server command and same-user process."""
    process = _process(pid)
    if process is None:
        return None
    uid, _, cmd, cwd = process
    if uid != str(os.getuid()):
        return None
    parts = cmd.split()
    if port == 8000:
        if cwd != str(root) or not _sigma_instance(port):
            return None
        if not (
            "-m" in parts
            and "uvicorn" in parts
            and "sigma.server:create_app" in parts
            and "--factory" in parts
            and "--host" in parts
            and "127.0.0.1" in parts
            and "--port" in parts
            and "8000" in parts
        ):
            return None
    elif port == 5173:
        if cwd != str(root / "frontend"):
            return None
        if not (
            any("vite" in token.split("/")[-1] for token in parts)
            and "--host" in parts
            and "127.0.0.1" in parts
            and "--port" in parts
            and "5173" in parts
            and "--strictPort" in parts
        ):
            return None
    else:
        return None
    return process


def recover_orphans(root: Path) -> None:
    """Stop demonstrably local SIGMA servers; leave unknown listeners alone."""
    root = root.resolve(strict=True)
    for port in PORTS:
        for pid in sorted(_listeners(port)):
            initial = _verified(port, pid, root)
            if initial is None or _process(pid) != initial:
                continue
            print(f"Stopping orphaned SIGMA server on port {port}…", flush=True)
            try:
                os.kill(pid, signal.SIGTERM)
            except ProcessLookupError:
                continue
            deadline = time.monotonic() + 4
            while time.monotonic() < deadline and pid in _listeners(port):
                time.sleep(0.1)
            if pid not in _listeners(port):
                continue
            if _verified(port, pid, root) != initial:
                continue
            print(f"Forcing orphaned SIGMA server on port {port} to stop…", flush=True)
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
