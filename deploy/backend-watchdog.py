"""Restart only an unhealthy/exited SIGMA backend, after safety checks.

Docker"s restart policy alone cannot act on an unhealthy but running container.
This script runs from a systemd timer; it never deletes application state.
"""

from __future__ import annotations

import fcntl
import json
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

STATE = Path("/srv/sigma-state")
LOGS = STATE / "auth" / "operational-logs"


def command(*argv: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, capture_output=True, text=True, check=False, timeout=25)


def note(message: str) -> None:
    line = datetime.now(UTC).isoformat() + " " + message
    print(line, flush=True)
    try:
        LOGS.mkdir(mode=0o700, exist_ok=True)
        with (LOGS / ("watchdog-" + datetime.now(UTC).strftime("%Y%m%d") + ".log")).open(
            "a", encoding="utf-8"
        ) as log:
            log.write(line + "\n")
    except OSError:
        print("Watchdog durable log write failed", file=sys.stderr)


def main() -> int:
    if (
        STATE.is_symlink()
        or not STATE.is_dir()
        or command("mountpoint", "-q", str(STATE)).returncode
    ):
        print("State disk not mounted; refusing backend restart", file=sys.stderr)
        return 1
    if command("systemctl", "is-active", "--quiet", "sigma.service").returncode:
        note("SIGMA service not active; watchdog will not interfere with deploy/maintenance")
        return 0

    # Overlapping timers or operator invocation cannot issue parallel restarts.
    lock_path = Path("/run/sigma-backend-watchdog.lock")
    with lock_path.open("a+") as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return 0
        result = command(
            "docker",
            "ps",
            "-aq",
            "--filter",
            "label=com.docker.compose.project=sigma",
            "--filter",
            "label=com.docker.compose.service=backend",
        )
        if result.returncode:
            note("Cannot query Docker backend container; operator attention required")
            return 1
        containers = result.stdout.split()
        if len(containers) != 1:
            note("Expected exactly one backend container; operator attention required")
            return 1
        container = containers[0]
        result = command("docker", "inspect", "--format", "{{json .State}}", container)
        if result.returncode:
            note("Cannot inspect backend container; operator attention required")
            return 1
        try:
            state = json.loads(result.stdout)
            running = state["Running"]
            status = state.get("Health", {}).get("Status", "unknown")
            oom = state.get("OOMKilled", False)
        except (ValueError, KeyError, AttributeError):
            note("Invalid Docker backend state; operator attention required")
            return 1
        if running and status in ("healthy", "starting"):
            return 0
        if running and status == "unknown":
            note("Backend health is unknown; refusing speculative restart")
            return 1

        # Limit flapping while an upstream dependency is unavailable.
        stamp = Path("/run/sigma-backend-watchdog-last-restart")
        try:
            last = float(stamp.read_text(encoding="ascii"))
        except (OSError, ValueError):
            last = 0.0
        if time.time() - last < 300:
            note("Backend remains unhealthy; restart cooldown active (5 minutes)")
            return 1
        stamp.write_text(str(time.time()), encoding="ascii")
        # Persist the reason before attempting recovery.
        note(
            f"Restarting backend container={container[:12]} running={running} health={status} oom_killed={oom}"
        )
        restarted = (
            command("docker", "restart", "--time", "10", container)
            if running
            else command("docker", "start", container)
        )
        if restarted.returncode:
            note("Backend restart failed; operator attention required")
            return 1
        note("Backend restart requested successfully; health will be checked on next tick")
        return 0


if __name__ == "__main__":
    sys.exit(main())
