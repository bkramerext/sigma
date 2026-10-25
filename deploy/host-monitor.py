#!/usr/bin/env python3
"""Read-only health checks for the SIGMA GCE host and its recovery points."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

Command = Callable[[Sequence[str]], subprocess.CompletedProcess[str]]


def run(argv: Sequence[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, capture_output=True, text=True, check=False, timeout=30)


@dataclass(frozen=True)
class Check:
    name: str
    status: str
    detail: str
    action: str


class Monitor:
    def __init__(
        self,
        *,
        root: Path = Path("/"),
        command: Command = run,
        now: datetime | None = None,
        min_free_percent: int = 15,
        max_backup_age: timedelta = timedelta(hours=26),
        min_recovery_points: int = 14,
    ) -> None:
        self.root = root
        self.command = command
        self.now = now or datetime.now(UTC)
        self.min_free_percent = min_free_percent
        self.max_backup_age = max_backup_age
        self.min_recovery_points = min_recovery_points
        self.checks: list[Check] = []

    def path(self, absolute: str) -> Path:
        return Path(absolute) if self.root == Path("/") else self.root / absolute.lstrip("/")

    def add(self, name: str, ok: bool, detail: str, action: str) -> None:
        self.checks.append(Check(name, "PASS" if ok else "FAIL", detail, action))

    def command_ok(self, name: str, argv: Sequence[str], action: str) -> str | None:
        try:
            result = self.command(argv)
        except (OSError, subprocess.TimeoutExpired):
            result = None
        ok = result is not None and result.returncode == 0
        self.add(
            name, ok, "command succeeded" if ok else "required command failed or timed out", action
        )
        return result.stdout.strip() if ok and result else None

    def check_disk(self) -> None:
        mount = self.path("/srv/sigma-state")
        action = "Inspect state-disk identity and fstab/systemd mount configuration; do not start SIGMA on boot storage."
        try:
            mounted_at = self.command(["findmnt", "-n", "-o", "TARGET", "--mountpoint", str(mount)])
        except (OSError, subprocess.TimeoutExpired):
            mounted_at = None
        mount_ok = (
            mounted_at is not None
            and mounted_at.returncode == 0
            and mounted_at.stdout.strip() == str(mount)
            and mount.is_dir()
            and not mount.is_symlink()
        )
        self.add(
            "state disk mount",
            mount_ok,
            "dedicated state filesystem is mounted exactly at /srv/sigma-state"
            if mount_ok
            else "dedicated state filesystem is not mounted exactly at /srv/sigma-state",
            action,
        )
        identity_ok = False
        if mount_ok:
            source = self.command_ok(
                "state disk source",
                ["findmnt", "-n", "-o", "SOURCE", "--mountpoint", str(mount)],
                action,
            )
            expected = self.command_ok(
                "configured state disk",
                ["readlink", "-f", str(self.path("/dev/disk/by-id/google-sigma-state"))],
                "Verify the attached device is named google-sigma-state and is the source mounted at /srv/sigma-state.",
            )
            if source is not None and expected is not None:
                mounted_device = self.command_ok(
                    "mounted block device", ["readlink", "-f", source], action
                )
                if mounted_device == expected:
                    identity_ok = True
                elif mounted_device is not None:
                    parent = self.command_ok(
                        "state partition parent",
                        ["lsblk", "-ndo", "PKNAME", mounted_device],
                        action,
                    )
                    if parent:
                        resolved_parent = self.command_ok(
                            "state disk parent device", ["readlink", "-f", f"/dev/{parent}"], action
                        )
                        identity_ok = resolved_parent == expected
            self.add(
                "state disk identity",
                identity_ok,
                "mounted device matches configured sigma-state disk"
                if identity_ok
                else "mounted device does not match configured sigma-state disk",
                action,
            )

        if mount_ok and identity_ok:
            try:
                usage = shutil.disk_usage(mount)
                free_percent = usage.free * 100 // usage.total
                self.add(
                    "state disk capacity",
                    free_percent >= self.min_free_percent,
                    f"{free_percent}% free ({usage.free} bytes); threshold {self.min_free_percent}%",
                    "Stop new research and expand/review capacity; do not delete user data as emergency cleanup.",
                )
                stats = os.statvfs(mount)
                inode_percent = (stats.f_favail * 100 // stats.f_files) if stats.f_files else 0
                self.add(
                    "state disk inodes",
                    inode_percent >= 5,
                    f"{inode_percent}% free; threshold 5%",
                    "Inspect inode usage and preserve workspaces and SQLite files while planning capacity repair.",
                )
            except OSError:
                self.add(
                    "state disk capacity",
                    False,
                    "filesystem usage is unavailable",
                    "Verify the persistent disk is mounted and readable.",
                )

    def check_services(self) -> None:
        for unit, label in (
            ("sigma.service", "SIGMA service"),
            ("sigma-sandbox.service", "rootless sandbox daemon"),
            ("docker.service", "Docker engine"),
            ("sigma-backup.timer", "daily backup timer"),
        ):
            self.command_ok(
                label,
                ["systemctl", "is-active", "--quiet", unit],
                f"Inspect `systemctl status {unit}` and its journal; restore dependencies in runbook order.",
            )

        output = self.command_ok(
            "application container health",
            [
                "docker",
                "ps",
                "--filter",
                "label=com.docker.compose.project=sigma",
                "--format",
                '{{.Label "com.docker.compose.service"}} {{.Status}}',
            ],
            "Inspect `docker ps` and `journalctl -u sigma.service`; restart only after mount and preflight pass.",
        )
        if output is not None:
            states = {
                line.split(maxsplit=1)[0]: line.split(maxsplit=1)[1]
                for line in output.splitlines()
                if len(line.split(maxsplit=1)) == 2
            }
            backend_ok = "backend" in states and "(healthy)" in states["backend"]
            frontend_ok = "frontend" in states and "(healthy)" in states["frontend"]
            edge_ok = "edge" in states and states["edge"].startswith("Up")
            for name, ok in (
                ("backend container health", backend_ok),
                ("frontend container health", frontend_ok),
                ("HTTPS edge container", edge_ok),
            ):
                self.add(
                    name,
                    ok,
                    "container is healthy/running"
                    if ok
                    else "expected Compose container is missing or unhealthy",
                    "Inspect `docker inspect` health status and bounded container journal; check service, secrets, mount and preflight before restart.",
                )

    def check_backup(self) -> None:
        state_dir = self.path("/var/lib/sigma-backup")
        failed = state_dir / "last-failure"
        success = state_dir / "last-success"
        marker_ok = not failed.exists()
        self.add(
            "backup failure marker",
            marker_ok,
            "no failure marker" if marker_ok else "failure marker is present",
            "Read `journalctl -u sigma-backup.service` and `journalctl -u sigma-backup-failure.service`; resolve before assuming recovery coverage.",
        )
        recent = False
        latest_snapshot = ""
        if success.is_file():
            try:
                timestamp, snapshot = success.read_text(encoding="utf-8").strip().split(maxsplit=1)
                latest_snapshot = snapshot
                created = datetime.fromisoformat(timestamp)
                recent = created.tzinfo is not None and (
                    self.now - created <= self.max_backup_age
                    and created <= self.now + timedelta(minutes=5)
                )
                if not snapshot.startswith("sigma-state-"):
                    recent = False
            except (OSError, ValueError):
                timestamp = "invalid"
        else:
            timestamp = "missing"
        self.add(
            "backup freshness",
            recent,
            f"last successful backup marker: {timestamp}; maximum age {self.max_backup_age}",
            "Inspect backup timer, service journal, last-failure marker, source disk and GCP snapshot operation; create a verified point after repair.",
        )

        env_file = self.path("/etc/sigma/backup.env")
        project = ""
        if env_file.is_file():
            for line in env_file.read_text(encoding="utf-8").splitlines():
                if line.startswith("SIGMA_BACKUP_PROJECT="):
                    project = line.split("=", 1)[1].strip().strip('"')
        if project and all(char.isalnum() or char in "-:." for char in project):
            output = self.command_ok(
                "managed READY recovery points",
                [
                    "gcloud",
                    "compute",
                    "snapshots",
                    "list",
                    "--project",
                    project,
                    "--filter=labels.sigma-daily-backup=true AND labels.sigma-source-disk=sigma-state AND status=READY",
                    "--format=json(name,creationTimestamp,sourceDisk)",
                ],
                "Check backup IAM and snapshot inventory; never prune until a new READY point exists.",
            )
            if output is not None:
                try:
                    points = json.loads(output)
                    valid = [
                        point
                        for point in points
                        if point.get("name", "").startswith("sigma-state-")
                        and point.get("sourceDisk", "").rstrip("/").endswith("/disks/sigma-state")
                    ]
                    self.add(
                        "recovery point retention",
                        len(valid) >= self.min_recovery_points,
                        f"{len(valid)} managed READY points; minimum {self.min_recovery_points}",
                        "Restore approved snapshot permissions and daily scheduling; retain at least 14 READY points before cleanup.",
                    )
                    latest_exists = any(point.get("name") == latest_snapshot for point in valid)
                    self.add(
                        "latest backup READY",
                        latest_exists,
                        "last-success snapshot is present in READY inventory"
                        if latest_exists
                        else "last-success marker snapshot is absent from managed READY inventory",
                        "Inspect snapshot status and backup journal; do not rely on a local success marker when its snapshot is absent.",
                    )
                except (json.JSONDecodeError, AttributeError):
                    self.add(
                        "recovery point retention",
                        False,
                        "snapshot inventory response was invalid",
                        "Inspect the gcloud snapshot-list command and permissions.",
                    )
        else:
            self.add(
                "recovery point retention",
                False,
                "approved backup project is not configured",
                "Complete owner-approved /etc/sigma/backup.env and narrowly scoped backup IAM.",
            )

    def execute(self) -> list[Check]:
        self.check_disk()
        self.check_services()
        self.check_backup()
        return self.checks


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit machine-readable checks")
    args = parser.parse_args(argv)
    checks = [asdict(check) for check in Monitor().execute()]
    if args.json:
        print(json.dumps(checks, indent=2))
    else:
        for check in checks:
            print(f"{check['status']}: {check['name']}: {check['detail']}")
            if check["status"] == "FAIL":
                print(f"  Action: {check['action']}")
    return 0 if all(check["status"] == "PASS" for check in checks) else 1


if __name__ == "__main__":
    sys.exit(main())
