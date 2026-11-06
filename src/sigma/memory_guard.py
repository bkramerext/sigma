"""Fail-safe admission and cancellation of expensive work under memory pressure.

Cgroup usage (not only Python RSS) is used because LaTeX, subprocesses and
Docker cache count against the backend's container memory limit. No provider
attempts are replayed after resource-triggered cancellation.
"""

from __future__ import annotations

import asyncio
import fcntl
import logging
import os
import threading
import time
from pathlib import Path

from sigma.production_observability import memory_snapshot

LOG = logging.getLogger("sigma.memory_guard")
MESSAGE = (
    "SIGMA stopped AI activity because backend memory is nearly exhausted. "
    "Saved research and paper checkpoints remain available where supported. "
    "Resume after resource pressure clears; interrupted provider calls are not replayed."
)
_LOCK = threading.Lock()
_CRITICAL = False
_TELEMETRY_DEGRADED = False
_LOOP: asyncio.AbstractEventLoop | None = None
_SHUTDOWN_PENDING = False
_LAST_ALERT = 0.0
_ACTIVE_TASKS: set[asyncio.Task[object]] = set()


def track_task(task: asyncio.Task[object]) -> None:
    """Track non-session AI work so the pressure breaker can stop it too."""
    _ACTIVE_TASKS.add(task)
    task.add_done_callback(_ACTIVE_TASKS.discard)


def critical_snapshot(snapshot: dict[str, int | None]) -> bool:
    used = snapshot["cgroup_used_mib"]
    limit = snapshot["cgroup_limit_mib"]
    host_available = snapshot["host_available_mib"]
    if host_available is not None and host_available <= 768:
        return True
    if not limit or used is None or limit < 256:
        return False
    # Act before OOM: 85% of the container's limit OR <512 MiB headroom.
    return used * 100 >= limit * 85 or limit - used <= 512


def capacity_verified(snapshot: dict[str, int | None]) -> bool:
    """Unverifiable container pressure is not evidence of spare capacity."""
    used = snapshot["cgroup_used_mib"]
    limit = snapshot["cgroup_limit_mib"]
    return used is not None and limit is not None and limit >= 256


def is_critical() -> bool:
    # Never rely on an old sample alone when admitting a new provider job.
    return critical_snapshot(memory_snapshot()) or _CRITICAL


def require_capacity() -> None:
    from sigma.projects import ProjectError

    snapshot = memory_snapshot()
    if os.getenv("SIGMA_CLOUD_AUTH_ENABLED", "").lower() == "true" and not capacity_verified(
        snapshot
    ):
        # Do not cancel active work just because metrics are unavailable, but
        # do not admit another hosted job without an OOM boundary. Local
        # development often has no cgroup memory limit and must still work.
        raise ProjectError(
            "Backend memory capacity cannot be verified. Existing work is preserved, "
            "but new AI jobs are paused. Check memory.read_failed in backend logs."
        )
    if critical_snapshot(snapshot) or _CRITICAL:
        raise ProjectError(MESSAGE)


def _notify_admin(snapshot: dict[str, int | None]) -> None:
    """One operator notification per 15 minutes, including across backend restarts."""
    global _LAST_ALERT
    now = time.time()
    with _LOCK:
        if now - _LAST_ALERT < 900:
            return
        _LAST_ALERT = now

    try:
        from sigma import cloud_auth

        cfg = cloud_auth.config()
        if not cfg.enabled:
            LOG.error("memory.alert_cloud_auth_disabled")
            return
        home = Path(os.environ.get("SIGMA_CLOUD_AUTH_HOME", "/var/lib/sigma-auth"))
        directory = home / "operational-logs"
        if directory.is_symlink() or not directory.is_dir():
            LOG.error("memory.alert_log_directory_unavailable")
            return
        marker = directory / "memory-alert-cooldown"
        fd = os.open(marker, os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            last_bytes = os.read(fd, 48)
            try:
                last_sent = float(last_bytes.decode("ascii").strip())
            except ValueError:
                last_sent = 0.0
            if now - last_sent < 900:
                return
            # Reserve before mail dispatch; the outcome may be unknown after
            # SMTP DATA. Never risk resending an ambiguous notification.
            os.lseek(fd, 0, os.SEEK_SET)
            os.ftruncate(fd, 0)
            os.write(fd, f"{now:.3f}".encode("ascii"))
            os.fsync(fd)
        finally:
            os.close(fd)

        cloud_auth._deliver_admin_notice(
            "URGENT: SIGMA backend memory pressure — AI activity stopped",
            (
                "SIGMA has entered memory-protection mode. Active research sessions "
                "and paper-generation tasks are being cancelled with recoverable "
                "checkpoint errors. New work is blocked until memory recovers.\n\n"
                f"Container memory: {snapshot['cgroup_used_mib']} MiB used / "
                f"{snapshot['cgroup_limit_mib']} MiB limit.\n"
                f"Host available: {snapshot['host_available_mib']} MiB.\n\n"
                "Inspect the persistent backend and watchdog logs on the SIGMA "
                "state disk. Review OOM events and paper generation before "
                "resuming work. No research content is included."
            ),
        )
        LOG.warning("memory.admin_alert_sent")
    except Exception as exc:  # noqa: BLE001 — alerting must never kill telemetry
        LOG.error("memory.admin_alert_failed error_type=%s", type(exc).__name__)


async def _cancel_active() -> None:
    global _SHUTDOWN_PENDING
    try:
        from sigma import papers, research_sessions

        # Do not await file operations or remote I/O here: task-owned finally/
        # cancellation handlers preserve workspace binding and billing holds.
        paper_tasks = [task for task in list(papers._generation_tasks.values()) if not task.done()]
        session_tasks = [
            task for task in list(research_sessions._tasks.values()) if not task.done()
        ]
        other_tasks = [task for task in list(_ACTIVE_TASKS) if not task.done()]
        all_tasks = list(set(paper_tasks + session_tasks + other_tasks))
        LOG.error(
            "memory.stop_active sessions=%d papers=%d other_ai=%d",
            len(session_tasks),
            len(paper_tasks),
            len(other_tasks),
        )
        for task in all_tasks:
            task.cancel()
        # Let task-owned checkpoint/cancellation handling run. Do not replay calls.
        if all_tasks:
            await asyncio.gather(*all_tasks, return_exceptions=True)
    finally:
        _SHUTDOWN_PENDING = False


def _schedule_cancellation() -> None:
    global _SHUTDOWN_PENDING
    if _SHUTDOWN_PENDING:
        return
    _SHUTDOWN_PENDING = True
    asyncio.create_task(_cancel_active())


def poll() -> None:
    """Called from the telemetry thread; safe to invoke without a running loop."""
    global _CRITICAL, _TELEMETRY_DEGRADED
    snapshot = memory_snapshot()
    verified = capacity_verified(snapshot)
    if not verified and not _TELEMETRY_DEGRADED:
        LOG.error(
            "memory.telemetry_degraded cgroup_used_mib=%s cgroup_limit_mib=%s "
            "new_ai_admission=blocked active_work=preserved",
            snapshot["cgroup_used_mib"],
            snapshot["cgroup_limit_mib"],
        )
    elif verified and _TELEMETRY_DEGRADED:
        LOG.info("memory.telemetry_restored new_ai_admission=permitted_if_capacity")
    _TELEMETRY_DEGRADED = not verified
    critical = critical_snapshot(snapshot)
    previous = _CRITICAL
    # Hysteresis reduces repeated alerts and premature re-admission.
    used = snapshot["cgroup_used_mib"]
    limit = snapshot["cgroup_limit_mib"]
    host_available = snapshot["host_available_mib"]
    host_recovered = host_available is None or host_available >= 1280
    if not critical and host_recovered and limit and used is not None and used * 100 <= limit * 75:
        _CRITICAL = False
    elif critical:
        _CRITICAL = True
    if critical and not previous:
        LOG.critical(
            "memory.critical cgroup_used_mib=%s cgroup_limit_mib=%s host_available_mib=%s",
            used,
            limit,
            snapshot["host_available_mib"],
        )
        threading.Thread(
            target=_notify_admin, args=(snapshot,), name="sigma-memory-alert", daemon=True
        ).start()
    if critical and _LOOP is not None and not _LOOP.is_closed():
        _LOOP.call_soon_threadsafe(_schedule_cancellation)


def attach_loop(loop: asyncio.AbstractEventLoop) -> None:
    global _LOOP
    _LOOP = loop
    poll()


def detach_loop() -> None:
    global _LOOP
    _LOOP = None
