"""Platform contract tests for SIGMA memory instrumentation.

Portable assertions exercise macOS behavior without probing Linux-only paths.
The live procfs test is explicitly skipped on non-Linux hosts.
"""

from __future__ import annotations

import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from sigma import production_observability as telemetry


class PlatformMemoryTests(unittest.TestCase):
    def test_macos_never_probes_linux_paths(self) -> None:
        with (
            patch.object(telemetry.sys, "platform", "darwin"),
            patch.object(
                telemetry,
                "_integer",
                side_effect=AssertionError("Do not read cgroup files on macOS"),
            ),
            patch.object(
                telemetry,
                "_process_kib",
                side_effect=AssertionError("Do not read /proc files on macOS"),
            ),
            patch.object(
                telemetry,
                "_host_available_kib",
                side_effect=AssertionError("Do not read /proc/meminfo on macOS"),
            ),
            patch.object(telemetry.resource, "getrusage", return_value=SimpleNamespace(
                ru_maxrss=128 * 1024 * 1024
            )),
        ):
            snapshot = telemetry.memory_snapshot()
        self.assertEqual(snapshot["rss_peak_mib"], 128)
        self.assertIsNone(snapshot["rss_mib"])  # No falsely labeled current RSS
        self.assertIsNone(snapshot["cgroup_limit_mib"])
        self.assertIsNone(snapshot["host_available_mib"])

    @unittest.skipUnless(sys.platform == "linux", "Linux-only /proc and cgroup integration")
    def test_native_linux_process_metrics(self) -> None:
        snapshot = telemetry.memory_snapshot()
        self.assertIsInstance(snapshot["rss_peak_mib"], int)
        self.assertGreater(snapshot["rss_peak_mib"], 0)
        # A Linux system without a cgroup limit is valid; do not fake one.

    def test_linux_metrics_still_use_linux_contract(self) -> None:
        with (
            patch.object(telemetry.sys, "platform", "linux"),
            patch.object(telemetry, "_integer", side_effect=[
                256 * 1024 * 1024,
                1024 * 1024 * 1024,
                300 * 1024 * 1024,
            ]),
            patch.object(telemetry, "_process_kib", side_effect=[120 * 1024, 180 * 1024]),
            patch.object(telemetry, "_host_available_kib", return_value=4 * 1024 * 1024),
            patch.object(telemetry, "_host_free_kib", return_value=2 * 1024 * 1024),
        ):
            snapshot = telemetry.memory_snapshot()
        self.assertEqual(snapshot["rss_mib"], 120)
        self.assertEqual(snapshot["rss_peak_mib"], 180)
        self.assertEqual(snapshot["cgroup_used_mib"], 256)
        self.assertEqual(snapshot["cgroup_limit_mib"], 1024)
        self.assertEqual(snapshot["cgroup_peak_mib"], 300)


if __name__ == "__main__":
    unittest.main(verbosity=2)
