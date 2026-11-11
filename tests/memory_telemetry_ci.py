"""Ensure optional CI cgroups are quiet while hosted capacity checks fail closed."""

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from sigma import memory_guard, production_observability


def main() -> None:
    with TemporaryDirectory() as temporary:
        missing = Path(temporary) / "absent-cgroup-memory.current"
        with patch.object(production_observability._LOGGER, "warning") as warning:
            assert production_observability._read_text(missing, missing_ok=True) is None
            warning.assert_not_called()
            assert production_observability._read_text(missing, missing_ok=False) is None
            warning.assert_called_once()
        # Repeat strict errors are intentionally throttled by path.
        with patch.object(production_observability._LOGGER, "warning") as warning:
            assert production_observability._read_text(missing, missing_ok=False) is None
            warning.assert_not_called()

    sample = {
        "rss_mib": 200,
        "rss_peak_mib": 200,
        "cgroup_used_mib": None,
        "cgroup_limit_mib": None,
        "cgroup_peak_mib": None,
        "host_available_mib": 8192,
        "host_free_mib": 4096,
    }
    previous = memory_guard._TELEMETRY_DEGRADED
    try:
        memory_guard._TELEMETRY_DEGRADED = False
        with (
            patch.object(memory_guard, "memory_snapshot", return_value=sample),
            patch.dict("os.environ", {"SIGMA_MEMORY_REQUIRE_METRICS": "false"}),
            patch.object(memory_guard.LOG, "error") as log,
        ):
            memory_guard.poll()
            log.assert_not_called()
            memory_guard.require_capacity()

        memory_guard._TELEMETRY_DEGRADED = False
        with (
            patch.object(memory_guard, "memory_snapshot", return_value=sample),
            patch.dict("os.environ", {"SIGMA_MEMORY_REQUIRE_METRICS": "true"}),
            patch.object(memory_guard.LOG, "error") as log,
        ):
            memory_guard.poll()
            log.assert_called_once()
            try:
                memory_guard.require_capacity()
            except Exception as exc:
                from sigma.projects import ProjectError

                assert isinstance(exc, ProjectError)
                assert "cannot be verified" in str(exc)
            else:
                raise AssertionError("Hosted admission must fail closed without cgroup metrics")
    finally:
        memory_guard._TELEMETRY_DEGRADED = previous
    print("PASS optional cgroup absence is quiet; hosted admission remains fail closed")


if __name__ == "__main__":
    main()
