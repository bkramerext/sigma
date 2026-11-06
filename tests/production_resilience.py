"""Offline watchdog, log-retention, and memory telemetry regression checks."""

from __future__ import annotations

import importlib.util
import json
import os
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

from sigma import memory_guard
from sigma.production_observability import memory_snapshot
from sigma.projects import ProjectError

ROOT = Path(__file__).resolve().parents[1]


def load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "deploy" / filename)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def check_memory_telemetry() -> None:
    """30-second telemetry must reach both docker logs and the durable file."""
    import io
    import logging

    from sigma import production_observability

    loggers = [
        logging.getLogger(),
        logging.getLogger("sigma.production"),
        logging.getLogger("sigma.memory_guard"),
        logging.getLogger("uvicorn.error"),
        logging.getLogger("uvicorn.access"),
    ]
    previous = [(logger, tuple(logger.handlers), logger.level) for logger in loggers]
    stderr = io.StringIO()
    with tempfile.TemporaryDirectory(prefix="sigma-memory-logs-") as temp:
        try:
            with (
                patch.dict(
                    os.environ,
                    {
                        "SIGMA_CLOUD_AUTH_ENABLED": "true",
                        "SIGMA_CLOUD_AUTH_HOME": temp,
                        "SIGMA_MEMORY_LOG_INTERVAL_SECONDS": "30",
                    },
                ),
                patch("sys.stderr", stderr),
                patch.object(production_observability, "_STARTED", False),
                patch.object(production_observability.threading, "Thread") as worker,
            ):
                production_observability.start()
                worker.assert_called_once()
                assert worker.call_args.kwargs["args"] == (30,)
                assert worker.call_args.kwargs["daemon"] is True
                logging.getLogger("sigma.production").info("memory rss_mib=123")
                for logger in loggers:
                    for handler in logger.handlers:
                        handler.flush()
                assert "memory rss_mib=123" in stderr.getvalue()
                durable = Path(temp) / "operational-logs" / "backend.log"
                assert "memory rss_mib=123" in durable.read_text(encoding="utf-8")
        finally:
            added: set[logging.Handler] = set()
            for logger, handlers, level in previous:
                for handler in tuple(logger.handlers):
                    if handler not in handlers:
                        logger.removeHandler(handler)
                        added.add(handler)
                logger.setLevel(level)
            for handler in added:
                handler.close()

    # A broken state disk may lose archival logging, but it must never
    # disable the console heartbeat or the memory-pressure safety guard.
    stderr = io.StringIO()
    log = logging.getLogger("sigma.production")
    before = tuple(log.handlers)
    before_level = log.level
    try:
        with (
            tempfile.TemporaryDirectory(prefix="sigma-memory-file-failure-") as home,
            patch.dict(
                os.environ,
                {
                    "SIGMA_CLOUD_AUTH_ENABLED": "true",
                    "SIGMA_CLOUD_AUTH_HOME": home,
                    "SIGMA_MEMORY_LOG_INTERVAL_SECONDS": "30",
                },
            ),
            patch("sys.stderr", stderr),
            patch.object(production_observability, "_STARTED", False),
            patch.object(production_observability, "TimedRotatingFileHandler", side_effect=OSError),
            patch.object(production_observability.threading, "Thread") as worker,
        ):
            production_observability.start()
            worker.assert_called_once()
            assert "persistent backend log setup failed" in stderr.getvalue()
    finally:
        for handler in tuple(log.handlers):
            if handler not in before:
                log.removeHandler(handler)
                handler.close()
        log.setLevel(before_level)


def check_memory_sources() -> None:
    """Unavailable kernel files are diagnosed, and cgroup v1 remains measurable."""
    from sigma import production_observability as telemetry

    fake = {
        "/proc/self/status": "VmRSS:\\t40960 kB\\nVmHWM:\\t51200 kB\\n",
        "/proc/meminfo": "MemAvailable: 2097152 kB\\n",
        "/sys/fs/cgroup/memory/memory.usage_in_bytes": str(3 * 1024**3),
        "/sys/fs/cgroup/memory/memory.limit_in_bytes": str(8 * 1024**3),
        "/sys/fs/cgroup/memory/memory.max_usage_in_bytes": str(4 * 1024**3),
    }

    def read(path: Path, encoding: str = "ascii") -> str:
        assert encoding == "ascii"
        if str(path) not in fake:
            raise FileNotFoundError(2, "not found", str(path))
        return fake[str(path)].replace("\\t", "\t").replace("\\n", "\n")

    with (
        patch.object(telemetry.Path, "read_text", autospec=True, side_effect=read),
        patch.object(telemetry._LOGGER, "warning") as warning,
    ):
        stats = telemetry.memory_snapshot()
    assert stats["rss_mib"] == 40
    assert stats["rss_peak_mib"] == 50
    assert stats["cgroup_used_mib"] == 3072
    assert stats["cgroup_limit_mib"] == 8192
    assert stats["cgroup_peak_mib"] == 4096
    assert stats["host_available_mib"] == 2048
    assert warning.called, "Unavailable v2 counters must be reported, not silently swallowed"

    # When both procfs and cgroupfs are unreadable, peak RSS still has a
    # standard-library fallback and the new-work admission gate fails closed.
    with (
        patch.object(
            telemetry.Path,
            "read_text",
            autospec=True,
            side_effect=PermissionError(13, "permission denied"),
        ),
        patch.object(telemetry._LOGGER, "warning") as warning,
    ):
        stats = telemetry.memory_snapshot()
    assert stats["rss_peak_mib"] is not None
    assert stats["cgroup_used_mib"] is None
    assert stats["cgroup_limit_mib"] is None
    assert warning.called

    assert not memory_guard.capacity_verified(stats)
    with (
        patch.object(memory_guard, "memory_snapshot", return_value=stats),
        patch.object(memory_guard, "_CRITICAL", False),
    ):
        try:
            memory_guard.require_capacity()
        except ProjectError as exc:
            assert "cannot be verified" in str(exc)
        else:
            raise AssertionError("Unverifiable memory admitted new inference")

    # Missing telemetry itself does not cancel sessions already in progress.
    with (
        patch.object(memory_guard, "memory_snapshot", return_value=stats),
        patch.object(memory_guard, "_CRITICAL", False),
        patch.object(memory_guard, "_TELEMETRY_DEGRADED", False),
        patch.object(memory_guard, "_LOOP", None),
        patch.object(memory_guard.LOG, "error") as log_error,
    ):
        memory_guard.poll()
        memory_guard.poll()
        assert log_error.call_count == 1
        assert "memory.telemetry_degraded" in log_error.call_args.args[0]
        assert not memory_guard._CRITICAL


def main() -> None:
    check_memory_telemetry()
    check_memory_sources()
    stats = memory_snapshot()
    assert {
        "rss_mib",
        "rss_peak_mib",
        "cgroup_used_mib",
        "cgroup_limit_mib",
        "cgroup_peak_mib",
        "host_available_mib",
    } <= stats.keys()
    assert all(value is None or isinstance(value, int) for value in stats.values())

    watchdog = load("sigma_watchdog_test", "backend-watchdog.py")
    cleanup = load("sigma_retention_test", "log-retention.py")
    with tempfile.TemporaryDirectory(prefix="sigma-resilience-") as temporary:
        root = Path(temporary)
        state = root / "state"
        state.mkdir()
        logs = state / "auth" / "operational-logs"
        logs.mkdir(parents=True)
        setattr(watchdog, "STATE", state)  # noqa: B010
        setattr(watchdog, "LOGS", logs)  # noqa: B010

        calls: list[tuple[str, ...]] = []
        health = {"value": "healthy"}

        def run(*args: str):
            calls.append(args)
            if args[0] == "mountpoint":
                return SimpleNamespace(returncode=0, stdout="")
            if args[0] == "systemctl":
                return SimpleNamespace(returncode=0, stdout="")
            if args[:2] == ("docker", "ps"):
                return SimpleNamespace(returncode=0, stdout="container123\n")
            if args[:2] == ("docker", "inspect"):
                return SimpleNamespace(
                    returncode=0,
                    stdout=json.dumps({"Running": True, "Health": {"Status": health["value"]}}),
                )
            if args[:2] == ("docker", "restart"):
                return SimpleNamespace(returncode=0, stdout="container123\n")
            raise AssertionError(args)

        with patch.object(watchdog, "command", side_effect=run):
            # /run watchdog lock and cooldown files cannot be touched in CI.
            # Check the restart-decision logic independently of systemd by
            # replacing the special paths with test-local paths.
            original_path = watchdog.Path

            def test_path(value):
                if value == "/run/sigma-backend-watchdog.lock":
                    return root / "lock"
                if value == "/run/sigma-backend-watchdog-last-restart":
                    return root / "last"
                return original_path(value)

            with patch.object(watchdog, "Path", side_effect=test_path):
                assert watchdog.main() == 0
                assert not any(c[:2] == ("docker", "restart") for c in calls)
                health["value"] = "unhealthy"
                assert watchdog.main() == 0
                assert len([c for c in calls if c[:2] == ("docker", "restart")]) == 1
                assert watchdog.main() == 1  # cooldown prevents repeated restarts
                assert len([c for c in calls if c[:2] == ("docker", "restart")]) == 1

        setattr(cleanup, "LOGS", logs)  # noqa: B010
        old = logs / "backend.log.2020-01-01"
        recent = logs / "backend.log.2026-11-05"
        active = logs / "backend.log"
        other = logs / "project.json"
        for file in (old, recent, active, other):
            file.write_text("test", encoding="utf-8")
        earlier = time.time() - 10 * 86400
        for file in (old, active, other):
            os.utime(file, (earlier, earlier))
        assert cleanup.main() == 0
        assert not old.exists() and recent.exists() and active.exists() and other.exists()

    # Cgroup pressure is a fail-closed admission and cancellation threshold,
    # not a comparison against process RSS or the host's spare RAM.
    base: dict[str, int | None] = {
        "cgroup_used_mib": 1000,
        "cgroup_limit_mib": 5000,
        "host_available_mib": 8000,
    }
    assert not memory_guard.critical_snapshot(base)
    assert memory_guard.critical_snapshot({**base, "cgroup_used_mib": 4250})
    assert memory_guard.critical_snapshot({**base, "cgroup_used_mib": 4500})
    assert memory_guard.critical_snapshot({**base, "cgroup_used_mib": 4488})
    assert memory_guard.critical_snapshot({**base, "host_available_mib": 700})
    with (
        patch.object(
            memory_guard,
            "memory_snapshot",
            return_value={
                **base,
                "cgroup_used_mib": 4500,
            },
        ),
        patch.object(memory_guard, "_CRITICAL", False),
    ):
        try:
            memory_guard.require_capacity()
        except ProjectError as exc:
            assert "nearly exhausted" in str(exc)
        else:
            raise AssertionError("New work was admitted at critical memory pressure")

    # Operator mail is addressed to the existing verified administrator roster
    # and guarded against duplicate sends after a process restart.
    from sigma import cloud_auth

    with tempfile.TemporaryDirectory(prefix="sigma-memory-alert-") as temporary:
        root = Path(temporary)
        (root / "operational-logs").mkdir()
        sent: list[tuple[str, str]] = []

        def capture(subject: str, body: str) -> None:
            sent.append((subject, body))

        with (
            patch.dict(os.environ, {"SIGMA_CLOUD_AUTH_HOME": str(root)}),
            patch.object(cloud_auth, "config", return_value=SimpleNamespace(enabled=True)),
            patch.object(cloud_auth, "_deliver_admin_notice", side_effect=capture),
        ):
            with patch.object(memory_guard, "_LAST_ALERT", 0.0):
                memory_guard._notify_admin(base)
                assert len(sent) == 1
            with patch.object(memory_guard, "_LAST_ALERT", 0.0):
                memory_guard._notify_admin(base)
                assert len(sent) == 1, "Restart-safe cooldown should prevent another alert"

    # All tracked AI activities are cancelled along with session/paper workers.
    import asyncio

    async def test_other_activity_cancellation() -> None:
        began = asyncio.Event()

        async def active() -> None:
            began.set()
            await asyncio.Event().wait()

        task = asyncio.create_task(active())
        memory_guard.track_task(task)
        await began.wait()
        await memory_guard._cancel_active()
        assert task.cancelled()
        assert task not in memory_guard._ACTIVE_TASKS
        assert not memory_guard._SHUTDOWN_PENDING

    asyncio.run(test_other_activity_cancellation())

    # FIFO paper queue: one running paper, two queued projects, and safe
    # cancellation of a queued project without blocking the next request.
    from sigma import papers

    async def test_paper_queue() -> None:
        with tempfile.TemporaryDirectory(prefix="sigma-paper-queue-") as temporary:
            root = Path(temporary)
            first_name, second_name, third_name, restarted_name = (
                str(root / f"paper-{name}.sigma")
                for name in ("first", "second", "third", "restarted")
            )
            for name in (first_name, second_name, third_name, restarted_name):
                Path(name).mkdir(mode=0o700)
            first_started = asyncio.Event()
            release_first = asyncio.Event()
            order: list[str] = []

            async def paper(name: str) -> None:
                async with papers._paper_operation(name, generating=True):
                    order.append(name)
                    if name == first_name:
                        first_started.set()
                        await release_first.wait()

            first = asyncio.create_task(paper(first_name))
            await first_started.wait()
            # An existing paper checkpoint must survive cancellation of a
            # queued attempt that never reached provider work.
            old_work = papers._new_work("1" * 64, "original", "2" * 64, "model", "high")
            papers._save_work(second_name, old_work)
            saved_work = papers._load_work(second_name)
            assert saved_work is not None
            second = asyncio.create_task(paper(second_name))
            third = asyncio.create_task(paper(third_name))
            await asyncio.sleep(0)
            assert papers.activity_status(first_name) == "active"
            assert papers.activity_status(second_name) == "queued"
            assert papers.activity_status(third_name) == "queued"
            queued_progress = papers.progress_status(second_name)
            assert queued_progress is not None and queued_progress["status"] == "queued"
            third_progress = papers.progress_status(third_name)
            assert third_progress is not None and "position 2" in third_progress["detail"]
            assert order == [first_name], "Queued projects must not run concurrently"
            try:
                async with papers._paper_operation(first_name, generating=True):
                    raise AssertionError("Duplicate paper project was admitted")
            except ProjectError as exc:
                assert "already active or queued" in str(exc)

            # A bounded queue prevents arbitrary request bursts from
            # pinning unbounded task/SSE memory on this single backend.
            with patch.object(papers, "MAX_QUEUED_PAPER_GENERATIONS", 2):
                try:
                    async with papers._paper_operation(restarted_name, generating=True):
                        raise AssertionError("A full queue admitted another job")
                except ProjectError as exc:
                    assert "queue is full" in str(exc)

            second.cancel()
            result = await asyncio.gather(second, return_exceptions=True)
            assert isinstance(result[0], asyncio.CancelledError)
            assert papers.activity_status(second_name) is None
            cancelled_progress = papers.progress_status(second_name)
            assert cancelled_progress is not None and cancelled_progress["status"] == "cancelled"
            assert papers._load_work(second_name) == saved_work
            release_first.set()
            await asyncio.gather(first, third)
            assert order == [first_name, third_name]
            assert papers.activity_status(third_name) is None
            assert not papers._paper_waiters
            assert not papers._generating_paper_projects
            assert not papers._busy_paper_projects

            # A backend crash bypasses finally/cleanup. The durable receipt
            # must report interruption, not pretend this job is still running
            # or vanish entirely. No provider attempt began while queued.
            papers._write_queue_status(restarted_name, "queued", papers._now())
            recovery = papers.progress_status(restarted_name)
            assert recovery and recovery["status"] == "interrupted"
            assert recovery["stage"] == "queued"
            assert "No AI call was started" in recovery["detail"]
            assert papers.activity_status(restarted_name) == "interrupted"

            # A callback from a previous attempt cannot corrupt a newer
            # attempt's progress or overwrite previously saved evidence.
            key = str(Path(second_name).resolve())
            later = {
                "run_id": "new-run",
                "status": "running",
                "stage": "writing",
                "current": None,
                "total": None,
                "started_at": papers._now(),
                "updated_at": papers._now(),
                "elapsed_seconds": 0,
            }
            papers._active_progress[key] = later
            try:
                papers.finish_progress(second_name, "failed", expected_run_id="old-run")
                assert papers._active_progress[key] is later
                assert papers._load_work(second_name) == saved_work
            finally:
                papers._active_progress.pop(key, None)

            # Memory pressure at queue handoff must fail without dispatching
            # any provider work and leave an inspectable terminal record.
            block = asyncio.Event()
            underway = asyncio.Event()

            async def active() -> None:
                async with papers._paper_operation(first_name, generating=True):
                    underway.set()
                    await block.wait()

            task = asyncio.create_task(active())
            await underway.wait()
            waiting = asyncio.create_task(paper(second_name))
            await asyncio.sleep(0)
            assert papers.activity_status(second_name) == "queued"
            with (
                patch.object(
                    memory_guard,
                    "require_capacity",
                    side_effect=ProjectError(memory_guard.MESSAGE),
                ),
                patch.object(memory_guard, "is_critical", return_value=True),
            ):
                block.set()
                await task
                failed = await asyncio.gather(waiting, return_exceptions=True)
            assert isinstance(failed[0], ProjectError)
            failed_status = papers.progress_status(second_name)
            assert failed_status is not None and failed_status["status"] == "failed"
            assert memory_guard.MESSAGE in failed_status["failure_reason"]
            assert papers._load_work(second_name) == saved_work
            assert not papers._paper_waiters
            assert not papers._busy_paper_projects

    asyncio.run(test_paper_queue())

    async def test_immediate_stop() -> None:
        # A job accepted by the API must be cancellable before generate()
        # even begins. No eventual provider call may escape this Stop.
        with tempfile.TemporaryDirectory(prefix="sigma-paper-stop-") as temporary:
            path = str(Path(temporary) / "immediate.sigma")
            Path(path).mkdir()
            provider_calls = 0

            async def would_dispatch() -> dict[str, object]:
                nonlocal provider_calls
                provider_calls += 1
                return {}

            task = asyncio.create_task(would_dispatch())
            papers.register_submission(path, task)
            receipt = papers._read_queue_status(path)
            assert receipt is not None and receipt["status"] == "queued"
            assert await papers.cancel_generation(path)
            assert task.cancelled()
            assert provider_calls == 0
            await asyncio.sleep(0)
            assert papers._submission_tasks == {}
            cancelled_status = papers.progress_status(path)
            assert cancelled_status is not None and cancelled_status["status"] == "cancelled"
            assert await papers.cancel_generation(path) is False

            async def unresolved_submission() -> dict[str, Any]:
                await asyncio.Event().wait()
                return {}

            pending = asyncio.create_task(unresolved_submission())
            papers.register_submission(path, pending)
            duplicate = asyncio.create_task(unresolved_submission())
            try:
                papers.register_submission(path, duplicate)
            except ProjectError as exc:
                assert "already active or queued" in str(exc)
            else:
                raise AssertionError("Duplicate API submission was admitted")
            duplicate.cancel()
            await asyncio.gather(duplicate, return_exceptions=True)
            assert await papers.cancel_generation(path)
            assert pending.cancelled()
            await asyncio.sleep(0)
            assert papers._submission_tasks == {}

    asyncio.run(test_immediate_stop())

    def test_bounded_progress_recovery() -> None:
        with tempfile.TemporaryDirectory(prefix="sigma-paper-progress-") as temporary:
            path = str(Path(temporary) / "checkpoint.sigma")
            Path(path).mkdir()
            work = papers._new_work("1" * 64, "original", "2" * 64, "model", "high")
            work["progress"] = {
                "run_id": "a" * 32,
                "status": "running",
                "stage": "sections",
                "current": 1,
                "total": 5,
                "started_at": papers._now(),
                "updated_at": papers._now(),
                "elapsed_seconds": 6,
            }
            papers._save_work(path, work)
            # Reading status must never need the entire saved evidence bundle.
            with patch.object(papers, "_load_work", side_effect=AssertionError("large read")):
                recovered = papers.progress_status(path)
            assert recovered is not None and recovered["status"] == "interrupted"
            assert recovered["current"] == 1
            with (
                patch.object(memory_guard, "is_critical", return_value=True),
                patch.object(papers, "_load_work", side_effect=AssertionError("large read")),
            ):
                papers.finish_progress(path, "failed", memory_guard.MESSAGE)
            failed = papers.progress_status(path)
            assert failed is not None and failed["status"] == "failed"
            assert failed["failure_reason"] == memory_guard.MESSAGE
            # Emergency status only updates tiny sidecar, not the full
            # checkpoint with provider-call accounting and frozen evidence.
            saved_work = papers._load_work(path)
            assert saved_work is not None
            assert saved_work["progress"] == work["progress"]
            assert saved_work["snapshot_sha256"] == work["snapshot_sha256"]
            papers._clear_work(path)
            assert papers.progress_status(path) is None

    test_bounded_progress_recovery()

    print("SIGMA resilience offline checks passed.")


if __name__ == "__main__":
    main()
