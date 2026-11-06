"""Bounded, persistent hosted-backend logs and low-overhead memory telemetry.

The log directory lives on the existing durable auth disk, not in Docker's
ephemeral writable layer. No prompts, credentials, or workspace content are logged.
"""

from __future__ import annotations

import logging
import os
import resource
import threading
import traceback
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

_LOGGER = logging.getLogger("sigma.production")
_STARTED = False
_LOCK = threading.Lock()
_READ_FAILURES: set[str] = set()
_READ_FAILURES_LOCK = threading.Lock()


def _read_text(path: Path) -> str | None:
    """Read kernel counters, reporting failures instead of hiding them as None."""
    try:
        content = path.read_text(encoding="ascii")
    except (OSError, UnicodeError) as exc:
        key = str(path)
        with _READ_FAILURES_LOCK:
            first = key not in _READ_FAILURES
            _READ_FAILURES.add(key)
        if first:
            _LOGGER.warning(
                "memory.read_failed path=%s error_type=%s errno=%s",
                key,
                type(exc).__name__,
                getattr(exc, "errno", None),
            )
        return None
    with _READ_FAILURES_LOCK:
        _READ_FAILURES.discard(str(path))
    return content


def _integer(path: Path) -> int | None:
    content = _read_text(path)
    if content is None:
        return None
    value = content.strip()
    if value == "max":
        return None
    try:
        return int(value)
    except ValueError:
        _LOGGER.warning("memory.invalid_counter path=%s", path)
        return None


def _process_kib(field: str) -> int | None:
    content = _read_text(Path("/proc/self/status"))
    if content is None:
        return None
    for line in content.splitlines():
        if line.startswith(field + ":"):
            try:
                return int(line.split()[1])
            except (ValueError, IndexError):
                _LOGGER.warning("memory.invalid_field source=proc_status field=%s", field)
                return None
    return None


def _host_available_kib() -> int | None:
    content = _read_text(Path("/proc/meminfo"))
    if content is None:
        return None
    for line in content.splitlines():
        if line.startswith("MemAvailable:"):
            try:
                return int(line.split()[1])
            except (ValueError, IndexError):
                _LOGGER.warning("memory.invalid_field source=proc_meminfo field=MemAvailable")
                return None
    return None


def _resident_from_statm_kib() -> int | None:
    """Alternate current process RSS when /proc/self/status is unavailable."""
    content = _read_text(Path("/proc/self/statm"))
    if content is None:
        return None
    try:
        resident_pages = int(content.split()[1])
        return resident_pages * os.sysconf("SC_PAGE_SIZE") // 1024
    except (ValueError, IndexError, OSError):
        return None


def _host_free_kib() -> int | None:
    """Last-resort host free pages (not equivalent to MemAvailable)."""
    try:
        return os.sysconf("SC_AVPHYS_PAGES") * os.sysconf("SC_PAGE_SIZE") // 1024
    except (OSError, ValueError):
        return None


def safe_exception_trace(error: BaseException) -> str:
    """Stack locations only; never print exception messages or frame locals."""
    frames = traceback.extract_tb(error.__traceback__)[-12:]
    return " > ".join(
        f"{Path(frame.filename).name}:{frame.lineno}:{frame.name}" for frame in frames
    )


def memory_snapshot() -> dict[str, int | None]:
    """Process RSS and cgroup OOM counters, supporting Linux cgroup v1/v2."""
    group = Path("/sys/fs/cgroup")
    usage = _integer(group / "memory.current")
    limit = _integer(group / "memory.max")
    peak = _integer(group / "memory.peak")
    if usage is None:
        usage = _integer(group / "memory" / "memory.usage_in_bytes")
    if limit is None:
        limit = _integer(group / "memory" / "memory.limit_in_bytes")
    if peak is None:
        peak = _integer(group / "memory" / "memory.max_usage_in_bytes")
    # Linux cgroup-v1 uses a huge sentinel to mean "unlimited".
    if limit is not None and limit >= (1 << 60):
        limit = None

    rss_kib = _process_kib("VmRSS")
    if rss_kib is None:
        rss_kib = _resident_from_statm_kib()
    peak_kib = _process_kib("VmHWM")
    if peak_kib is None:
        # On Linux ru_maxrss is measured in KiB.
        peak_kib = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss

    return {
        "rss_mib": _to_mib(rss_kib, kib=True),
        "rss_peak_mib": _to_mib(peak_kib, kib=True),
        "cgroup_used_mib": _to_mib(usage),
        "cgroup_limit_mib": _to_mib(limit),
        "cgroup_peak_mib": _to_mib(peak),
        "host_available_mib": _to_mib(_host_available_kib(), kib=True),
        "host_free_mib": _to_mib(_host_free_kib(), kib=True),
    }

def _to_mib(value: int | None, *, kib: bool = False) -> int | None:
    return None if value is None else round(value / (1024 if kib else 1024 * 1024))


def _sample(period_seconds: int) -> None:
    """Log memory every period_seconds; check pressure every five seconds.

    A telemetry or protection failure must not silently terminate this thread.
    """
    import time

    last_log = float("-inf")
    wake = threading.Event()
    while True:
        try:
            now = time.monotonic()
            if now - last_log >= period_seconds:
                stats = memory_snapshot()
                used, limit = stats["cgroup_used_mib"], stats["cgroup_limit_mib"]
                pct = round(100 * used / limit, 1) if used is not None and limit else None
                _LOGGER.info(
                    "memory rss_mib=%s rss_peak_mib=%s cgroup_used_mib=%s "
                    "cgroup_limit_mib=%s cgroup_peak_mib=%s cgroup_pct=%s "
                    "host_available_mib=%s host_free_mib=%s",
                    stats["rss_mib"],
                    stats["rss_peak_mib"],
                    used,
                    limit,
                    stats["cgroup_peak_mib"],
                    pct,
                    stats["host_available_mib"],
                    stats["host_free_mib"],
                )
                last_log = now
        except Exception as exc:  # noqa: BLE001 - monitoring must survive sample errors
            _LOGGER.error("memory.sample_failed error_type=%s", type(exc).__name__)
        try:
            from sigma.memory_guard import poll

            poll()
        except Exception as exc:  # noqa: BLE001 - never lose telemetry after guard errors
            _LOGGER.error("memory.guard_poll_failed error_type=%s", type(exc).__name__)
        wake.wait(5)


def start() -> None:
    """Start hosted memory telemetry, mirrored to Docker logs and durable storage."""
    global _STARTED
    if os.getenv("SIGMA_CLOUD_AUTH_ENABLED", "").lower() != "true":
        return
    with _LOCK:
        if _STARTED:
            return

        formatter = logging.Formatter(
            "%(asctime)sZ %(levelname)s %(name)s %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )
        # Uvicorn configures its own console loggers, not the root logger.
        # Without this handler the periodic memory samples only reach the
        # persistent file, and are invisible in docker logs.
        console = logging.StreamHandler()
        console.setFormatter(formatter)
        _LOGGER.addHandler(console)
        logging.getLogger("sigma.memory_guard").addHandler(console)
        _LOGGER.setLevel(logging.INFO)

        home = Path(os.environ.get("SIGMA_CLOUD_AUTH_HOME", "/var/lib/sigma-auth"))
        directory = home / "operational-logs"
        persistent = False
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
            handler.setFormatter(formatter)
            for name in ("", "uvicorn.error", "uvicorn.access"):
                logging.getLogger(name).addHandler(handler)
            logging.getLogger().setLevel(logging.INFO)
            persistent = True
        except OSError as exc:
            # Keep memory sampling and the circuit breaker alive even when the
            # state disk is unavailable or its permissions have drifted.
            _LOGGER.error(
                "persistent backend log setup failed; console telemetry remains active "
                "error_type=%s",
                type(exc).__name__,
            )

        try:
            interval = max(10, int(os.environ.get("SIGMA_MEMORY_LOG_INTERVAL_SECONDS", "30")))
        except ValueError:
            interval = 30
            _LOGGER.warning("invalid memory log interval; using 30 seconds")

        _STARTED = True
        threading.Thread(
            target=_sample, args=(interval,), name="sigma-memory-telemetry", daemon=True
        ).start()
        _LOGGER.info(
            "memory telemetry started interval_s=%d console=true persistent=%s "
            "path=operational-logs/backend.log",
            interval,
            str(persistent).lower(),
        )
