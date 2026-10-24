"""Identify and recover SIGMA dev servers left without their UI supervisor.

Ports only locate candidate processes. A matching checkout, exact command,
launch marker, OS identity, and marker served by the candidate are all required
before SIGMA sends a signal.
"""

import json
import os
import re
import shlex
import signal
import subprocess
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

PORTS = (8000, 5173)
MARKER = re.compile(r"(?:^|\s)SIGMA_UI_INSTANCE_ID=([0-9a-f]{32})(?:\s|$)")
Process = tuple[str, str, str, str, str]


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
        int(line[1:]) for line in result.splitlines() if line.startswith("p") and line[1:].isdigit()
    }


def _process(pid: int) -> Process | None:
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
    # ps eww is used only to compare a random launch marker. Its output is never
    # logged, so unrelated environment values and credentials are not exposed.
    environment = _command("ps", "eww", "-p", str(pid), "-o", "command=") or ""
    match = MARKER.search(environment)
    uid, started, command = fields
    assert uid is not None and started is not None and command is not None
    return uid, started, command, paths[0], match.group(1) if match else ""


def _checkout_root(cwd: str) -> Path | None:
    current = Path(cwd)
    for candidate in (current, *current.parents):
        if (
            all(
                (candidate / relative).is_file()
                for relative in ("pyproject.toml", "src/sigma/server.py", "frontend/package.json")
            )
            and (candidate / "sigma").is_file()
        ):
            try:
                return candidate.resolve(strict=True)
            except OSError:
                return None
    return None


def _sigma_instance(port: int) -> str | None:
    try:
        with urlopen(f"http://127.0.0.1:{port}/api/ui-instance", timeout=0.35) as response:
            if response.status != 200:
                return None
            raw = response.read(2048)
        parsed = json.loads(raw)
        value = parsed.get("instance") if isinstance(parsed, dict) else None
        if isinstance(value, str) and MARKER.fullmatch(f"SIGMA_UI_INSTANCE_ID={value}"):
            return value
        return None
    except (URLError, OSError, ValueError):
        return None


def _verified(port: int, pid: int, root: Path | None = None) -> Process | None:
    """Return identity only for a same-user SIGMA server from a valid checkout."""
    process = _process(pid)
    if process is None:
        return None
    uid, _started, command, cwd, marker = process
    checkout = _checkout_root(cwd)
    if uid != str(os.getuid()) or not marker or checkout is None:
        return None
    if root is not None:
        try:
            if checkout != root.resolve(strict=True):
                return None
        except OSError:
            return None
    try:
        parts = shlex.split(command)
    except ValueError:
        return None
    if not parts:
        return None
    if port == 8000:
        executable = Path(parts[0])
        try:
            if executable.resolve(strict=True) != (checkout / ".venv/bin/python").resolve(
                strict=True
            ):
                return None
        except OSError:
            return None
        expected = (
            "-m" in parts
            and "uvicorn" in parts
            and "sigma.server:create_app" in parts
            and "--factory" in parts
            and "--host" in parts
            and "127.0.0.1" in parts
            and "--port" in parts
            and "8000" in parts
        )
    elif port == 5173:
        frontend_entry = (checkout / "frontend/node_modules/.bin/vite").resolve(strict=False)
        entry_matches = False
        for token in parts:
            try:
                entry_matches = Path(token).resolve(strict=False) == frontend_entry
            except OSError:
                continue
            if entry_matches:
                break
        expected = (
            str(Path(cwd).resolve(strict=True)) in {str(checkout), str(checkout / "frontend")}
            and entry_matches
            and "--host" in parts
            and "127.0.0.1" in parts
            and "--port" in parts
            and "5173" in parts
            and "--strictPort" in parts
        )
    else:
        return None
    if not expected or _sigma_instance(port) != marker:
        return None
    return process


def listener_details(port: int) -> list[str]:
    """Describe each current listener without exposing its full command/env."""
    details = []
    for pid in sorted(_listeners(port)):
        process = _process(pid)
        if process is None:
            details.append(f"PID {pid} (process details unavailable)")
            continue
        _uid, _started, command, cwd, _marker = process
        try:
            executable = Path(shlex.split(command)[0]).name
        except (ValueError, IndexError):
            executable = "unknown process"
        details.append(f"PID {pid} ({executable}, working directory {cwd})")
    return details


def recover_orphans(root: Path | None = None) -> list[str]:
    """Stop identified orphan servers from any checkout and report the rest."""
    failures: list[str] = []
    for port in PORTS:
        for pid in sorted(_listeners(port)):
            initial = _verified(port, pid, root)
            if initial is None or _process(pid) != initial:
                continue
            print(f"Stopping orphaned SIGMA server on port {port} (PID {pid})…", flush=True)
            try:
                os.kill(pid, signal.SIGTERM)
            except ProcessLookupError:
                continue
            deadline = time.monotonic() + 4
            while time.monotonic() < deadline and pid in _listeners(port):
                time.sleep(0.1)
            # Initial route + environment proof established ownership. After
            # SIGTERM, the API may stop answering before its process exits, so
            # escalation rechecks the immutable process identity/launch marker.
            if pid in _listeners(port) and _process(pid) == initial:
                print(f"Forcing verified SIGMA server PID {pid} to stop…", flush=True)
                try:
                    os.kill(pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
        remaining = sorted(_listeners(port))
        for pid in remaining:
            details = next(
                (item for item in listener_details(port) if item.startswith(f"PID {pid} ")),
                f"PID {pid} (process details unavailable)",
            )
            message = (
                f"Port {port} remains occupied by {details}; ownership could not be verified, "
                "so SIGMA left it untouched."
            )
            print(message, flush=True)
            failures.append(message)
    return failures
