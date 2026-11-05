"""Offline watchdog, log-retention, and memory telemetry regression checks."""

from __future__ import annotations

import importlib.util
import json
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from sigma.production_observability import memory_snapshot

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
        watchdog.STATE = state
        watchdog.LOGS = logs

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

        cleanup.LOGS = logs
        old = logs / "backend.log.2020-01-01"
        recent = logs / "backend.log.2026-11-05"
        active = logs / "backend.log"
        other = logs / "project.json"
        for file in (old, recent, active, other):
            file.write_text("test", encoding="utf-8")
        earlier = time.time() - 10 * 86400
        import os

        for file in (old, active, other):
            os.utime(file, (earlier, earlier))
        assert cleanup.main() == 0
        assert not old.exists() and recent.exists() and active.exists() and other.exists()

    print("SIGMA resilience offline checks passed.")


if __name__ == "__main__":
    main()
