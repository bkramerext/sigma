"""Offline checks for actionable, read-only GCE host monitoring."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("host_monitor", ROOT / "deploy/host-monitor.py")
assert spec and spec.loader
monitoring = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = monitoring
spec.loader.exec_module(monitoring)


class HostMonitorTests(unittest.TestCase):
    def fixture(self, root: Path, recovery_points: int = 14, *, failed: bool = False):
        (root / "srv/sigma-state").mkdir(parents=True)
        state = root / "var/lib/sigma-backup"
        state.mkdir(parents=True)
        now = datetime(2026, 10, 25, 12, tzinfo=UTC)
        timestamp = (now - timedelta(hours=1)).isoformat().replace("+00:00", "Z")
        (state / "last-success").write_text(f"{timestamp} sigma-state-20261025T110000Z\n")
        if failed:
            (state / "last-failure").write_text("failure\n")
        etc = root / "etc/sigma"
        etc.mkdir(parents=True)
        (etc / "backup.env").write_text("SIGMA_BACKUP_PROJECT=fixture-project\n")
        points = [
            {
                "name": "sigma-state-20261025T110000Z"
                if index == 0
                else f"sigma-state-20261024T{index:02d}0000Z",
                "creationTimestamp": "2026-10-25T11:00:00Z",
                "sourceDisk": "https://www.googleapis.com/compute/v1/projects/fixture/zones/us-west1-b/disks/sigma-state",
            }
            for index in range(recovery_points)
        ]

        def command(argv):
            if argv[0] == "findmnt":
                output = argv[-1] if "TARGET" in argv else "/dev/sdb1"
                return subprocess.CompletedProcess(argv, 0, output + "\n", "")
            if argv[0] == "readlink":
                output = (
                    "/dev/sdb"
                    if argv[-1].endswith("google-sigma-state") or argv[-1] == "/dev/sdb"
                    else "/dev/sdb1"
                )
                return subprocess.CompletedProcess(argv, 0, output + "\n", "")
            if argv[0] == "lsblk":
                return subprocess.CompletedProcess(argv, 0, "sdb\n", "")
            if argv[0] == "gcloud":
                return subprocess.CompletedProcess(argv, 0, json.dumps(points), "")
            if argv[0] == "docker":
                return subprocess.CompletedProcess(
                    argv,
                    0,
                    "backend Up 1 minute (healthy)\nfrontend Up 1 minute (healthy)\nedge Up 1 minute\n",
                    "",
                )
            return subprocess.CompletedProcess(argv, 0, "", "")

        return now, command

    def test_all_recovery_and_host_checks_pass_with_fourteen_points(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            now, command = self.fixture(root)
            checks = monitoring.Monitor(root=root, command=command, now=now).execute()
        self.assertTrue(all(check.status == "PASS" for check in checks), checks)
        self.assertEqual(
            next(c for c in checks if c.name == "recovery point retention").status, "PASS"
        )
        self.assertEqual(next(c for c in checks if c.name == "latest backup READY").status, "PASS")

    def test_stale_backup_and_failure_marker_are_actionable_failures(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            now, command = self.fixture(root, failed=True)
            marker = root / "var/lib/sigma-backup/last-success"
            marker.write_text("2026-10-23T00:00:00Z sigma-state-20261023T000000Z\n")
            checks = monitoring.Monitor(root=root, command=command, now=now).execute()
        by_name = {check.name: check for check in checks}
        self.assertEqual(by_name["backup failure marker"].status, "FAIL")
        self.assertIn("journalctl", by_name["backup failure marker"].action)
        self.assertEqual(by_name["backup freshness"].status, "FAIL")

    def test_retention_and_command_failures_fail_closed_without_command_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            now, _ = self.fixture(root, recovery_points=13)

            def command(argv):
                if argv[0] == "findmnt":
                    return subprocess.CompletedProcess(argv, 1, "SECRET USER DATA", "")
                if argv[0] == "docker":
                    return subprocess.CompletedProcess(
                        argv, 0, "backend Up (healthy)\nfrontend Up (healthy)\nedge Up\n", ""
                    )
                return subprocess.CompletedProcess(argv, 0, "[]", "")

            checks = monitoring.Monitor(root=root, command=command, now=now).execute()
        by_name = {check.name: check for check in checks}
        self.assertEqual(by_name["state disk mount"].status, "FAIL")
        self.assertEqual(by_name["recovery point retention"].status, "FAIL")
        self.assertNotIn("SECRET USER DATA", str(checks))

    def test_low_capacity_and_inode_exhaustion_have_actionable_failures(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            now, command = self.fixture(root)
            with (
                patch.object(
                    monitoring.shutil,
                    "disk_usage",
                    return_value=SimpleNamespace(total=100, free=10),
                ),
                patch.object(
                    monitoring.os,
                    "statvfs",
                    return_value=SimpleNamespace(f_favail=2, f_files=100),
                ),
            ):
                checks = monitoring.Monitor(root=root, command=command, now=now).execute()
        by_name = {check.name: check for check in checks}
        self.assertEqual(by_name["state disk capacity"].status, "FAIL")
        self.assertEqual(by_name["state disk inodes"].status, "FAIL")
        self.assertIn("Stop new research", by_name["state disk capacity"].action)

    def test_unmounted_state_path_never_reads_boot_disk_capacity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            now, _ = self.fixture(root)

            def command(argv):
                if argv[0] == "findmnt":
                    return subprocess.CompletedProcess(argv, 0, "/\n", "")
                return subprocess.CompletedProcess(argv, 0, "[]", "")

            with patch.object(monitoring.shutil, "disk_usage") as disk_usage:
                checks = monitoring.Monitor(root=root, command=command, now=now).execute()
                disk_usage.assert_not_called()
        by_name = {check.name: check for check in checks}
        self.assertEqual(by_name["state disk mount"].status, "FAIL")
        self.assertNotIn("state disk capacity", by_name)

    def test_wrong_attached_disk_never_passes_as_state_capacity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            now, initial = self.fixture(root)

            def command(argv):
                if argv[0] == "readlink" and argv[-1] == "/dev/sdb1":
                    return subprocess.CompletedProcess(argv, 0, "/dev/sdc1\n", "")
                if argv[0] == "lsblk":
                    return subprocess.CompletedProcess(argv, 0, "sdc\n", "")
                if argv[0] == "readlink" and argv[-1] == "/dev/sdc":
                    return subprocess.CompletedProcess(argv, 0, "/dev/sdc\n", "")
                return initial(argv)

            with patch.object(monitoring.shutil, "disk_usage") as disk_usage:
                checks = monitoring.Monitor(root=root, command=command, now=now).execute()
                disk_usage.assert_not_called()
        by_name = {check.name: check for check in checks}
        self.assertEqual(by_name["state disk mount"].status, "PASS")
        self.assertEqual(by_name["state disk identity"].status, "FAIL")
        self.assertNotIn("state disk capacity", by_name)

    def test_recent_marker_does_not_pass_if_its_snapshot_is_absent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            now, initial = self.fixture(root)

            def command(argv):
                result = initial(argv)
                if argv[0] == "gcloud":
                    points = json.loads(result.stdout)
                    result = subprocess.CompletedProcess(
                        argv,
                        0,
                        json.dumps(points[1:]),
                        "",
                    )
                return result

            checks = monitoring.Monitor(root=root, command=command, now=now).execute()
        by_name = {check.name: check for check in checks}
        self.assertEqual(by_name["backup freshness"].status, "PASS")
        self.assertEqual(by_name["latest backup READY"].status, "FAIL")

    def test_unit_contracts_retain_mount_ordering_restart_and_periodic_checks(self):
        app_unit = (ROOT / "deploy/systemd/sigma.service").read_text()
        backup_timer = (ROOT / "deploy/systemd/sigma-backup.timer").read_text()
        monitor_timer = (ROOT / "deploy/systemd/sigma-monitor.timer").read_text()
        self.assertIn(
            "Requires=docker.service sigma-sandbox.service srv-sigma\\x2dstate.mount", app_unit
        )
        self.assertIn("Restart=on-failure", app_unit)
        self.assertIn("Persistent=true", backup_timer)
        self.assertIn("OnUnitActiveSec=15min", monitor_timer)
        self.assertIn(
            "OnFailure=sigma-monitor-failure.service",
            (ROOT / "deploy/systemd/sigma-monitor.service").read_text(),
        )

    def test_rollback_requires_recovery_and_schema_gates_and_preserves_volumes(self):
        script = (ROOT / "deploy/rollback-gce-release.sh").read_text()
        self.assertIn("--backup-verified", script)
        self.assertIn("--schema-compatible", script)
        self.assertIn('docker image inspect "sigma-backend:$target"', script)
        self.assertIn("systemctl restart sigma.service", script)
        self.assertIn("rollback_active=1", script)
        self.assertIn("restore_previous_env", script)
        self.assertNotIn("down --volumes", script)
        self.assertNotIn("docker volume rm", script)
        result = subprocess.run(
            ["bash", str(ROOT / "deploy/rollback-gce-release.sh")],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("FAIL:", result.stderr)


if __name__ == "__main__":
    unittest.main()
