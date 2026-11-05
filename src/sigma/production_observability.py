"""Bounded, persistent hosted-backend logs and low-overhead memory telemetry.

The log directory lives on the existing durable auth disk, not in Docker's
ephemeral writable layer. No prompts, credentials, or workspace content are logged.
"""

from __future__ import annotations

import logging
import os
import threading
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

_LOGGER = logging.getLogger("sigma.production")
_STARTED = False
_LOCK = threading.Lock()


def _integer(path: Path) -> int | None:
    try:
        value = path.read_text(encoding="ascii").strip()
        return int(value) if value != "max" else None
    except (OSError, ValueError):
        return None


def _process_kib(field: str) -> int | None:
    try:
        for line in Path("/proc/self/status").read_text(encoding="ascii").splitlines():
            if line.startswith(field + ":"):
                return int(line.split()[1])
    except (OSError, ValueError, IndexError):
        pass
    return None


def _host_available_kib() -> int | None:
    try:
        for line in Path("/proc/meminfo").read_text(encoding="ascii").splitlines():
            if line.startswith("MemAvailable:"):
                return int(line.split()[1])
    except (OSError, ValueError, IndexError):
        pass
    return None


def memory_snapshot() -> dict[str, int | None]:
    """Current process RSS plus cgroup usage/limit, the actual OOM boundary."""
    group = Path("/sys/fs/cgroup")
    return {
        "rss_mib": _to_mib(_process_kib("VmRSS"), kib=True),
        "rss_peak_mib": _to_mib(_process_kib("VmHWM"), kib=True),
        "cgroup_used_mib": _to_mib(_integer(group / "memory.current")),
        "cgroup_limit_mib": _to_mib(_integer(group / "memory.max")),
        "cgroup_peak_mib": _to_mib(_integer(group / "memory.peak")),
        "host_available_mib": _to_mib(_host_available_kib(), kib=True),
    }


def _to_mib(value: int | None, *, kib: bool = False) -> int | None:
    return None if value is None else round(value / (1024 if kib else 1024 * 1024))


def _sample(period_seconds: int) -> None:
    while True:
        stats = memory_snapshot()
        used, limit = stats["cgroup_used_mib"], stats["cgroup_limit_mib"]
        pct = round(100 * used / limit, 1) if used is not None and limit else None
        _LOGGER.info(
            "memory rss_mib=%s rss_peak_mib=%s cgroup_used_mib=%s "
            "cgroup_limit_mib=%s cgroup_peak_mib=%s cgroup_pct=%s "
            "host_available_mib=%s",
            stats["rss_mib"],
            stats["rss_peak_mib"],
            used,
            limit,
            stats["cgroup_peak_mib"],
            pct,
            stats["host_available_mib"],
        )
        # Event.wait avoids a busy loop and allows clean process exit.
        threading.Event().wait(period_seconds)


def start() -> None:
    """Attach one file handler for application, Uvicorn error and access logs."""
    global _STARTED
    if os.getenv("SIGMA_CLOUD_AUTH_ENABLED", "").lower() != "true":
        return
    with _LOCK:
        if _STARTED:
            return
        home = Path(os.environ.get("SIGMA_CLOUD_AUTH_HOME", "/var/lib/sigma-auth"))
        directory = home / "operational-logs"
        try:
            directory.mkdir(mode=0o700, parents=True, exist_ok=True)
            if directory.is_symlink():
                raise OSError("log directory is a symlink")
            os.chmod(directory, 0o700)
            handler = TimedRotatingFileHandler(
                directory / "backend.log",
                when="midnight",
                interval=1,
                backupCount=0,  # Host retention timer owns expiry.
                utc=True,
                encoding="utf-8",
            )
            handler.setFormatter(
                logging.Formatter(
                    "%(asctime)sZ %(levelname)s %(name)s %(message)s",
                    datefmt="%Y-%m-%dT%H:%M:%S",
                )
            )
            for name in ("", "uvicorn.error", "uvicorn.access"):
                logging.getLogger(name).addHandler(handler)
            logging.getLogger().setLevel(logging.INFO)
            _LOGGER.setLevel(logging.INFO)
        except OSError:
            logging.getLogger("sigma.configuration").exception(
                "Persistent backend log setup failed; stdout logs remain available"
            )
            return
        _STARTED = True
        interval = max(10, int(os.environ.get("SIGMA_MEMORY_LOG_INTERVAL_SECONDS", "30")))
        threading.Thread(
            target=_sample, args=(interval,), name="sigma-memory-telemetry", daemon=True
        ).start()
        _LOGGER.info(
            "persistent logging enabled path=operational-logs/backend.log interval_s=%d", interval
        )
