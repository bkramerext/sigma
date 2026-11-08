#!/usr/bin/env python3
"""One-command, fail-closed keyless SIGMA routine release.

Run from a trusted persistent operator with short-lived GCP impersonation.
This does not provision IAM or credentials. No production mutation occurs
until exact-SHA CI, scoped GCE access, and dated safety evidence are verified.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
import time
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path

from release_controller import CheckpointedRelease, ReleaseBlocked, Stage

PROJECT = "sigma-research-prod"
ZONE = "us-west1-b"
HOST = "sigma-gce-01"
RECOVERY_SA = f"sigma-release-operator@{PROJECT}.iam.gserviceaccount.com"
HOST_SA = f"sigma-release-ssh@{PROJECT}.iam.gserviceaccount.com"
URL = "https://sigma-research.duckdns.org"
REQUIRED_CI = {
    "Ruff lint and format",
    "SIGMA verification",
    "Browser verification",
    "Frontend build",
}
SAFE_RESOURCE = re.compile(r"[a-z][a-z0-9-]{0,62}")


def safe_run(args: list[str], *, timeout: int = 600, check: bool = True) -> subprocess.CompletedProcess[str]:
    """Run without shell interpolation, suppressing potentially sensitive stderr."""
    try:
        result = subprocess.run(args, text=True, capture_output=True, timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ReleaseBlocked(f"command unavailable or timed out: {args[0]}") from exc
    if check and result.returncode:
        raise ReleaseBlocked(f"command failed: {args[0]} (exit {result.returncode}); output withheld")
    return result


def assert_safety_evidence(path: Path, sha: str) -> dict:
    """Evidence is an attestation from the release operator, not an IAM bypass."""
    if path.is_symlink() or not path.is_file():
        raise ReleaseBlocked("missing or symlinked safety evidence")
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
        timestamp = datetime.fromisoformat(record["checked_at"].replace("Z", "+00:00"))
        estimate = record["max_incremental_cost_usd"]
    except (ValueError, KeyError, TypeError) as exc:
        raise ReleaseBlocked("invalid safety evidence") from exc
    now = datetime.now(UTC)
    if (
        not isinstance(record, dict)
        or record.get("release_sha") != sha
        or timestamp.tzinfo is None
        or not now - timedelta(hours=24) <= timestamp <= now
        or type(estimate) not in (int, float)
        or not 0 < estimate <= 25
        or record.get("billing_enabled") is not True
        or record.get("quota_available") is not True
        or record.get("schema_compatible") is not True
        or not isinstance(record.get("billing_evidence"), str)
        or not record["billing_evidence"].strip()
        or not isinstance(record.get("schema_evidence"), str)
        or not record["schema_evidence"].strip()
    ):
        raise ReleaseBlocked("safety evidence is expired, incomplete, or exceeds $25")
    return {
        "checked_at": record["checked_at"],
        "max_incremental_cost_usd": estimate,
        "billing_evidence_present": True,
        "schema_evidence_present": True,
    }


def assert_source_ci(sha: str) -> dict:
    """Reuse existing required successful Actions on the exact frozen commit."""
    head = safe_run(["git", "rev-parse", "HEAD"], timeout=15).stdout.strip()
    if head != sha:
        raise ReleaseBlocked("checkout is not the frozen exact release SHA")
    if safe_run(["git", "merge-base", "--is-ancestor", sha, "origin/main"], timeout=15, check=False).returncode:
        raise ReleaseBlocked("release SHA is not included in fetched origin/main")
    request = urllib.request.Request(
        f"https://api.github.com/repos/bkramerext/sigma/actions/runs?head_sha={sha}&per_page=100",
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "sigma-release-controller",
            **({"Authorization": "Bearer " + os.environ["GITHUB_TOKEN"]} if os.environ.get("GITHUB_TOKEN") else {}),
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            runs = json.load(response)["workflow_runs"]
    except (OSError, ValueError, KeyError) as exc:
        raise ReleaseBlocked("unable to verify exact-SHA workflow evidence") from exc
    green = {}
    for run in runs:
        if run.get("head_sha") != sha or run.get("conclusion") != "success":
            continue
        if run.get("name") in REQUIRED_CI:
            green[run["name"]] = run.get("html_url", "")
    missing = REQUIRED_CI - set(green)
    if missing:
        raise ReleaseBlocked("exact-SHA CI not green: " + ", ".join(sorted(missing)))
    return {"successful_workflow_urls": green}


class GceRelease:
    def __init__(self, sha: str, safety_file: Path) -> None:
        if not re.fullmatch(r"[0-9a-f]{40}", sha):
            raise ValueError("invalid exact SHA")
        self.sha, self.safety_file = sha, safety_file
        self.snapshot = f"sigma-state-v021-pre-{sha[:12]}"
        self.disk = f"sigma-state-restore-{sha[:12]}"
        self.vm = f"sigma-v021-recovery-{sha[:12]}"
        assert all(SAFE_RESOURCE.fullmatch(s) for s in (self.snapshot, self.disk, self.vm))

    @staticmethod
    def _quote(value: str) -> str:
        return shlex.quote(value)

    def gce(self, principal: str, *args: str, timeout: int = 600, check: bool = True) -> subprocess.CompletedProcess[str]:
        return safe_run(
            ["gcloud", *args, f"--project={PROJECT}", f"--impersonate-service-account={principal}", "--quiet"],
            timeout=timeout, check=check,
        )

    def describe(self, principal: str, kind: str, name: str) -> dict | None:
        args = ["compute", kind, "describe", name, "--format=json"]
        if kind in {"instances", "disks"}:
            args += [f"--zone={ZONE}"]
        result = self.gce(principal, *args, check=False)
        if result.returncode:
            message = result.stderr.lower()
            if "not found" in message or "was not found" in message:
                return None
            raise ReleaseBlocked(f"unable to inspect scoped {kind} resource")
        try:
            return json.loads(result.stdout)
        except ValueError as exc:
            raise ReleaseBlocked("GCE returned invalid JSON resource metadata") from exc

    def ssh(self, principal: str, host: str, command: str, timeout: int = 600) -> str:
        result = self.gce(
            principal, "compute", "ssh", host, f"--zone={ZONE}",
            "--tunnel-through-iap", f"--command={command}",
            "--ssh-flag=-o BatchMode=yes", "--ssh-flag=-o ConnectTimeout=20",
            timeout=timeout,
        )
        return result.stdout.strip()

    def scp(self, source: str, host: str) -> None:
        self.gce(
            RECOVERY_SA, "compute", "scp", source, host + ":/tmp/verify-state-restore.py",
            f"--zone={ZONE}", "--tunnel-through-iap", timeout=150,
        )

    def access(self) -> dict:
        host = self.describe(HOST_SA, "instances", HOST)
        disk = self.describe(RECOVERY_SA, "disks", "sigma-state")
        if not host or host.get("name") != HOST or not disk or disk.get("name") != "sigma-state":
            raise ReleaseBlocked("expected production host or state disk missing")
        if not self.ssh(HOST_SA, HOST, "sudo -n true && sudo -n systemctl is-active --quiet sigma.service && sudo -n findmnt -n /srv/sigma-state && test ! -e /run/lock/sigma-state-backup.lock"):
            # An empty ssh response is fine; exit code is the important check.
            pass
        if self.describe(RECOVERY_SA, "instances", self.vm):
            raise ReleaseBlocked("a previous recovery VM already exists; reconcile before deployment")
        if self.describe(RECOVERY_SA, "disks", self.disk):
            raise ReleaseBlocked("a previous recovery clone already exists; reconcile before deployment")
        return {"host": HOST, "disk": "sigma-state", "identity": "keyless"}

    def snapshot_state(self) -> dict:
        """Ensure interrupted capture cannot result in a repeated unverified snapshot."""
        existing = self.describe(RECOVERY_SA, "snapshots", self.snapshot)
        if existing:
            raise ReleaseBlocked("snapshot already exists; consistency needs reconciliation")
        watchdog = "sudo -n systemd-run --unit=sigma-release-snapshot-watchdog --on-active=10m /bin/systemctl start sigma.service"
        self.ssh(HOST_SA, HOST, watchdog)
        stopped = False
        try:
            self.ssh(
                HOST_SA, HOST,
                "sudo -n systemctl stop sigma.service && "
                "! sudo -n systemctl is-active --quiet sigma.service && "
                "sudo -n sync -f /srv/sigma-state",
            )
            stopped = True
            self.gce(
                RECOVERY_SA, "compute", "snapshots", "create", self.snapshot,
                "--source-disk=sigma-state", f"--source-disk-zone={ZONE}",
                "--storage-location=us-west1", timeout=480,
            )
        finally:
            # If the controller is interrupted externally, the independent
            # host watchdog starts SIGMA even if the runner disappears.
            self.ssh(HOST_SA, HOST, "sudo -n systemctl start sigma.service", timeout=120)
        try:
            self.ssh(HOST_SA, HOST, "sudo -n systemctl stop sigma-release-snapshot-watchdog.timer", timeout=60)
        except ReleaseBlocked:
            # An armed watchdog is safer than leaving production stopped.
            pass
        if not stopped:
            raise ReleaseBlocked("production could not be confirmed stopped for snapshot")
        result = self.describe(RECOVERY_SA, "snapshots", self.snapshot)
        if (
            not result or result.get("status") != "READY"
            or not result.get("sourceDisk", "").endswith("/disks/sigma-state")
        ):
            raise ReleaseBlocked("fresh application-consistent snapshot not READY/verified")
        return {"snapshot": self.snapshot, "status": "READY", "source_disk": "sigma-state"}

    def recovery_create(self) -> None:
        snap = self.describe(RECOVERY_SA, "snapshots", self.snapshot)
        if not snap or snap.get("status") != "READY":
            raise ReleaseBlocked("selected recovery point is not READY")
        self.gce(
            RECOVERY_SA, "compute", "disks", "create", self.disk, f"--zone={ZONE}",
            f"--source-snapshot={self.snapshot}", "--type=pd-balanced",
        )
        self.gce(
            RECOVERY_SA, "compute", "instances", "create", self.vm, f"--zone={ZONE}",
            "--machine-type=e2-standard-2", "--image-project=ubuntu-os-cloud",
            "--image-family=ubuntu-2404-lts-amd64", "--subnet=sigma-us-west1",
            "--no-address", "--no-service-account", "--no-scopes",
            "--metadata=enable-oslogin=TRUE,block-project-ssh-keys=TRUE",
        )
        self.gce(
            RECOVERY_SA, "compute", "instances", "attach-disk", self.vm,
            f"--zone={ZONE}", f"--disk={self.disk}",
            "--device-name=sigma-state-restore", "--mode=ro",
        )

    def recovery_verify(self) -> dict:
        vm = self.describe(RECOVERY_SA, "instances", self.vm)
        if not vm:
            raise ReleaseBlocked("recovery VM is missing")
        metadata = {item.get("key"): item.get("value") for item in vm.get("metadata", {}).get("items", [])}
        if (
            any(iface.get("accessConfigs") for iface in vm.get("networkInterfaces", []))
            or vm.get("serviceAccounts")
            or metadata.get("enable-oslogin", "").upper() != "TRUE"
            or metadata.get("block-project-ssh-keys", "").upper() != "TRUE"
        ):
            raise ReleaseBlocked("recovery VM identity or isolation is unsafe")
        attachments = [d for d in vm.get("disks", []) if d.get("deviceName") == "sigma-state-restore"]
        if len(attachments) != 1 or attachments[0].get("mode") != "READ_ONLY":
            raise ReleaseBlocked("recovery clone attachment is not READ_ONLY")
        self.scp("deploy/verify-state-restore.py", self.vm)
        command = (
            "sudo -n mkdir -p /mnt/sigma-restore && "
            "sudo -n mount -o ro,noload,nosuid,nodev,noexec,norecovery "
            "/dev/disk/by-id/google-sigma-state-restore /mnt/sigma-restore && "
            "sudo -n findmnt -n -o OPTIONS /mnt/sigma-restore && "
            "sudo -n python3 /tmp/verify-state-restore.py /mnt/sigma-restore "
            "--min-workspaces 2 --min-projects 1 --min-artifacts 1 --min-papers 1"
        )
        for retry in range(5):
            try:
                output = self.ssh(RECOVERY_SA, self.vm, command, timeout=180)
                break
            except ReleaseBlocked:
                if retry == 4:
                    raise
                time.sleep(5)
        if "PASS: all restore checks completed read-only" not in output:
            raise ReleaseBlocked("isolated restore did not report full read-only PASS")
        return {"snapshot": self.snapshot, "verified_read_only": True, "vm": self.vm}

    def cleanup(self) -> dict:
        if self.describe(RECOVERY_SA, "instances", self.vm):
            self.gce(
                RECOVERY_SA, "compute", "instances", "delete", self.vm, f"--zone={ZONE}",
                "--delete-disks=boot",
            )
        if self.describe(RECOVERY_SA, "disks", self.disk):
            self.gce(RECOVERY_SA, "compute", "disks", "delete", self.disk, f"--zone={ZONE}")
        if self.describe(RECOVERY_SA, "instances", self.vm) or self.describe(RECOVERY_SA, "disks", self.disk):
            raise ReleaseBlocked("temporary recovery resources remain after cleanup")
        return {"recovery_vm_removed": True, "clone_removed": True, "snapshot_retained": self.snapshot}

    def reconcile_restore(self) -> str:
        # A crash can leave only scoped disposable resources; clear those
        # before a bounded retry. Never remove the recovery snapshot or data.
        self.cleanup()
        return "retry"

    def cutover(self) -> dict:
        command = (
            "sudo -n python3 /opt/sigma/current/deploy/deploy-gce-release.py "
            + self._quote(self.sha) + " --backup-verified --schema-compatible"
        )
        self.ssh(HOST_SA, HOST, command, timeout=1200)
        return {"guarded_helper_completed": True, "sha": self.sha}

    def production_verified(self) -> bool:
        command = (
            "sudo -n grep -qx " + self._quote("SIGMA_RELEASE=" + self.sha)
            + " /etc/sigma/deploy.env && "
            "sudo -n systemctl is-active --quiet sigma.service && "
            "sudo -n test -f /var/lib/sigma/releases/" + self.sha + ".json"
        )
        try:
            self.ssh(HOST_SA, HOST, command)
            with urllib.request.urlopen(URL + "/api/cloud-auth/status", timeout=25) as response:
                status = json.load(response)
                if response.status != 200 or status.get("ready") is not True:
                    return False
            with urllib.request.urlopen(URL + "/", timeout=25) as response:
                return response.status == 200
        except (ReleaseBlocked, OSError, ValueError, KeyError):
            return False

    def verify(self) -> dict:
        if not self.production_verified():
            raise ReleaseBlocked("production SHA, systemd, release record or public HTTPS/auth failed")
        return {"sha": self.sha, "https": "200", "auth_ready": True}

    def stages(self) -> list[Stage]:
        # CI and evidence gates precede all production mutations.
        return [
            Stage("safety-evidence", lambda: assert_safety_evidence(self.safety_file, self.sha), lambda: "retry"),
            Stage("exact-sha-ci", lambda: assert_source_ci(self.sha), lambda: "retry"),
            Stage("keyless-preflight", self.access, lambda: "retry"),
            Stage("fresh-snapshot", self.snapshot_state, lambda: "blocked"),
            Stage("isolated-readonly-restore", self._restore, self.reconcile_restore),
            Stage("temporary-resource-cleanup", self.cleanup, lambda: "retry"),
            Stage("guarded-cutover", self.cutover, lambda: "done" if self.production_verified() else "blocked"),
            Stage("production-verification", self.verify, lambda: "retry"),
        ]

    def _restore(self) -> dict:
        self.recovery_create()
        try:
            return self.recovery_verify()
        except Exception:
            # Cleanup cannot erase the retained snapshot; if cleanup itself
            # fails, the controller reports the blocker and remains stopped.
            self.cleanup()
            raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("release_sha")
    parser.add_argument("--safety-evidence", type=Path, required=True)
    parser.add_argument("--state-dir", type=Path, default=Path("/var/lib/sigma-release"))
    args = parser.parse_args()
    try:
        release = GceRelease(args.release_sha, args.safety_evidence)
        CheckpointedRelease(args.state_dir, args.release_sha, release.stages()).run()
    except (ReleaseBlocked, ValueError) as exc:
        print(f"BLOCKED: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
