"""Fail-safe admission and cancellation of expensive work under memory pressure.

Cgroup usage (not only Python RSS) is used because LaTeX, subprocesses and
Docker cache count against the backend's container memory limit. No provider
attempts are replayed after resource-triggered cancellation.
"""

from __future__ import annotations

import asyncio
import logging
import os
import threading
import fcntl
import time
from pathlib import Path

from sigma.production_observability import memory_snapshot

LOG = logging.getLogger("sigma.memory_guard")
MESSAGE = (
    "SIGMA paused research and paper generation because backend memory is "
    "nearly exhausted. Saved checkpoints remain available. Resume after "
    "resource pressure clears; interrupted provider calls are not replayed."
)
_LOCK = threading.Lock()
_CRITICAL = False
_LOOP: asyncio.AbstractEventLoop | None = None
_SHUTDOWN_PENDING = False
_LAST_ALERT = 0.0


def critical_snapshot(snapshot: dict[str, int | None]) -> bool:
    used = snapshot["cgroup_used_mib"]
    limit = snapshot["cgroup_limit_mib"]
    if not limit or used is None or limit < 256:
        return False
    # Act before OOM: 85% of the container's limit OR <512 MiB headroom.
    return used * 100 >= limit * 85 or limit - used <= 512


def is_critical() -> bool:
    # Never rely on an old sample alone when admitting a new provider job.
    return critical_snapshot(memory_snapshot()) or _CRITICAL


def require_capacity() -> None:
    if is_critical():
        from sigma.projects import ProjectError

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
        fd = os.open(
            marker, os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o600
        )
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
            "URGENT: SIGMA backend memory pressure — work paused",
            (
                "SIGMA has entered memory-protection mode. Active research sessions "
                "and paper-generation tasks are being cancelled with recoverable "
                "checkpoint errors. New work is blocked until memory recovers.\\n\\n"
                f"Container memory: {snapshot['cgroup_used_mib']} MiB used / "
                f"{snapshot['cgroup_limit_mib']} MiB limit.\\n"
                f"Host available: {snapshot['host_available_mib']} MiB.\\n\\n"
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
        LOG.error(
            "memory.stop_active sessions=%d papers=%d",
            len(session_tasks),
            len(paper_tasks),
        )
        for task in paper_tasks + session_tasks:
            task.cancel()
        # Let each task's existing checkpoint/cancellation handling run.
        if paper_tasks or session_tasks:
            await asyncio.gather(*paper_tasks, *session_tasks, return_exceptions=True)
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
    global _CRITICAL
    snapshot = memory_snapshot()
    critical = critical_snapshot(snapshot)
    previous = _CRITICAL
    # Hysteresis reduces repeated alerts and premature re-admission.
    used = snapshot["cgroup_used_mib"]
    limit = snapshot["cgroup_limit_mib"]
    if not critical and limit and used is not None and used * 100 <= limit * 75:
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
