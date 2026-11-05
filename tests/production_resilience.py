"""Offline watchdog, log-retention, and memory telemetry regression checks."""

from __future__ import annotations

import importlib.util
import json
import os
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace
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


def main() -> None:
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
            second = asyncio.create_task(paper(second_name))
            third = asyncio.create_task(paper(third_name))
            await asyncio.sleep(0)
            assert papers.activity_status(first_name) == "active"
            assert papers.activity_status(second_name) == "queued"
            assert papers.activity_status(third_name) == "queued"
            assert papers.progress_status(second_name)["status"] == "queued"
            assert "position 2" in papers.progress_status(third_name)["detail"]
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
            assert papers.progress_status(second_name)["status"] == "cancelled"
            assert papers._load_work(second_name) == old_work
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
            assert papers.activity_status(restarted_name) is None

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
                papers.finish_progress(
                    second_name, "failed", expected_run_id="old-run"
                )
                assert papers._active_progress[key] is later
                assert papers._load_work(second_name) == old_work
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
                    memory_guard, "require_capacity",
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
            assert papers._load_work(second_name) == old_work
            assert not papers._paper_waiters
            assert not papers._busy_paper_projects

    asyncio.run(test_paper_queue())

    print("SIGMA resilience offline checks passed.")


if __name__ == "__main__":
    main()
