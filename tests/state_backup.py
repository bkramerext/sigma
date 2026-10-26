"""Offline checks for SIGMA's state-disk backup policy and restore verifier."""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "deploy"))
import importlib.util

retention_spec = importlib.util.spec_from_file_location(
    "backup_retention", ROOT / "deploy/backup-retention.py"
)
assert retention_spec and retention_spec.loader
backup_retention = importlib.util.module_from_spec(retention_spec)
retention_spec.loader.exec_module(backup_retention)
spec = importlib.util.spec_from_file_location(
    "verify_state_restore", ROOT / "deploy/verify-state-restore.py"
)
assert spec and spec.loader
restore = importlib.util.module_from_spec(spec)
spec.loader.exec_module(restore)


class StateBackupTests(unittest.TestCase):
    def make_state(self, root: Path) -> list[Path]:
        auth = root / "auth"
        workspaces = auth / "workspaces"
        workspaces.mkdir(parents=True)
        auth.chmod(0o700)
        workspaces.chmod(0o700)
        workspace_ids = ["a" * 32, "b" * 32]
        for index, workspace_id in enumerate(workspace_ids):
            (workspaces / workspace_id).mkdir(mode=0o700)
            folder = workspaces / workspace_id / "project"
            folder.mkdir(mode=0o700)
            (folder / "project.json").write_text(json.dumps({"id": f"p{index}"}))
            (folder / "session.json").write_text(json.dumps({"artifacts": [{"id": "e1"}]}))
        paper_id = "c" * 32
        paper_dir = workspaces / workspace_ids[0] / "project" / "papers"
        paper_dir.mkdir()
        pdf = b"%PDF-1.4\nfixture\n%%EOF\n"
        (paper_dir / f"{paper_id}.pdf").write_bytes(pdf)
        (paper_dir / f"{paper_id}.json").write_text(
            json.dumps(
                {
                    "paper_id": paper_id,
                    "tex_source": "\\documentclass{article}",
                    "pdf_sha256": hashlib.sha256(pdf).hexdigest(),
                    "pdf_size_bytes": len(pdf),
                }
            )
        )
        access = auth / "access.sqlite3"
        with closing(sqlite3.connect(access)) as db:
            db.executescript(
                "CREATE TABLE identities(subject TEXT PRIMARY KEY,email TEXT,updated_at INTEGER);"
                "CREATE TABLE sessions(token_hash TEXT PRIMARY KEY,subject TEXT,email TEXT,expires_at INTEGER);"
                "CREATE TABLE grants(kind TEXT,value TEXT,role TEXT,active INTEGER,updated_at INTEGER,allowance_usd REAL);"
                "INSERT INTO identities VALUES('s1','one@example.org',1);"
                "INSERT INTO identities VALUES('s2','two@example.org',1);"
            )
            db.commit()
        mapping = auth / "workspaces.sqlite3"
        with closing(sqlite3.connect(mapping)) as db:
            db.execute(
                "CREATE TABLE workspaces(subject_hash TEXT,workspace_id TEXT,created_at TEXT)"
            )
            db.executemany(
                "INSERT INTO workspaces VALUES(?,?,?)",
                [
                    (
                        hashlib.sha256(
                            f"sigma-cloud-workspace-v1\0s{index + 1}".encode()
                        ).hexdigest(),
                        workspace_id,
                        "today",
                    )
                    for index, workspace_id in enumerate(workspace_ids)
                ],
            )
            db.commit()
        ledger = auth / "cloud-research.sqlite3"
        with closing(sqlite3.connect(ledger)) as db:
            db.executescript(
                "CREATE TABLE jobs(session_id TEXT,workspace_id TEXT,project_id TEXT);"
                "CREATE TABLE calls(call_id TEXT,session_id TEXT,workspace_id TEXT,amount_usd REAL,status TEXT);"
                "INSERT INTO jobs VALUES('j1','aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa','p0');"
                "INSERT INTO calls VALUES('c1','j1','aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',0.25,'unknown');"
            )
            db.commit()
        for database in (access, mapping, ledger):
            database.chmod(0o600)
        return [access, mapping, ledger]

    def test_restore_verifier_checks_integrity_isolation_artifacts_and_ledger_read_only(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            databases = self.make_state(root)
            before = [hashlib.sha256(path.read_bytes()).digest() for path in databases]
            result = restore.verify(
                root, min_workspaces=2, min_projects=2, min_artifacts=2, min_papers=1
            )
            after = [hashlib.sha256(path.read_bytes()).digest() for path in databases]
            self.assertEqual(before, after)
            self.assertTrue(any("workspace isolation" in line for line in result))
            self.assertTrue(any("paper artifacts" in line and "1 saved" in line for line in result))
            self.assertTrue(
                any(
                    "accounting state" in line and "1 reserved or unknown" in line
                    for line in result
                )
            )

    def test_restore_verifier_rejects_unmapped_workspace_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.make_state(root)
            (root / "auth/workspaces" / ("c" * 32)).mkdir()
            with self.assertRaisesRegex(ValueError, "isolation mismatch"):
                restore.verify(root, 2, 1, 1, 1)

    def test_restore_verifier_rejects_corrupt_sqlite(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            databases = self.make_state(root)
            databases[1].write_bytes(b"not sqlite")
            with self.assertRaises(sqlite3.DatabaseError):
                restore.verify(root, 2, 1, 1, 1)

    def test_restore_verifier_rejects_paper_hash_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.make_state(root)
            pdf_path = next((root / "auth/workspaces").glob("*/project/papers/*.pdf"))
            pdf_path.write_bytes(b"%PDF-1.4\nchanged\n%%EOF\n")
            with self.assertRaisesRegex(ValueError, "PDF hash/size"):
                restore.verify(root, 2, 1, 1, 1)

    def test_restore_verifier_rejects_accounting_for_unmapped_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            databases = self.make_state(root)
            with sqlite3.connect(databases[2]) as db:
                db.execute(
                    "INSERT INTO calls VALUES('c2','missing','d' || replace(?, 'a', 'd'),0.01,'reserved')",
                    ("a" * 32,),
                )
            with self.assertRaisesRegex(ValueError, "unmapped workspace"):
                restore.verify(root, 2, 1, 1, 1)

    def test_generated_snapshot_name_matches_gce_resource_contract(self) -> None:
        script = (ROOT / "deploy/backup-state.sh").read_text()
        match = re.search(r"stamp=\$\(date -u \+([^)]*)\)", script)
        self.assertIsNotNone(match)
        assert match is not None
        stamp = subprocess.check_output(["date", "-u", f"+{match[1]}"], text=True).strip()
        name = f"sigma-state-{stamp}"
        self.assertLessEqual(len(name), 63)
        self.assertRegex(name, r"^[a-z]([-a-z0-9]*[a-z0-9])?$")
        self.assertIsNotNone(backup_retention.NAME.fullmatch(name))

    def test_retention_prunes_only_old_managed_ready_points(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "snapshots.json"
            source = (
                "https://compute.googleapis.com/compute/v1/projects/p/zones/z/disks/sigma-state"
            )
            rows = [
                {
                    "name": f"sigma-state-202601{day:02}t021700z",
                    "creationTimestamp": f"2026-01-{day:02}T02:17:00Z",
                    "sourceDisk": source,
                    "labels": {"sigma-daily-backup": "true", "sigma-source-disk": "sigma-state"},
                }
                for day in range(1, 16)
            ]
            rows.append({"name": "unrelated", "labels": {}, "sourceDisk": source})
            path.write_text(json.dumps(rows))
            self.assertEqual(
                backup_retention.expired_snapshots(path, 14),
                ["sigma-state-20260101t021700z"],
            )

    def test_no_expired_snapshots_emits_no_deletion_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "snapshots.json"
            path.write_text("[]")
            result = subprocess.run(
                [sys.executable, str(ROOT / "deploy/backup-retention.py"), str(path), "14"],
                text=True,
                capture_output=True,
                check=True,
            )
            self.assertEqual(result.stdout, "")

    def test_retention_rejects_unsafe_policy_or_managed_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "snapshots.json"
            path.write_text("[]")
            with self.assertRaisesRegex(ValueError, "less than 14"):
                backup_retention.expired_snapshots(path, 13)
            path.write_text(
                json.dumps(
                    [{"labels": {"sigma-daily-backup": "true", "sigma-source-disk": "sigma-state"}}]
                )
            )
            with self.assertRaisesRegex(ValueError, "metadata"):
                backup_retention.expired_snapshots(path, 14)

    def test_daily_timer_and_backup_failure_detection_are_configured(self) -> None:
        timer = (ROOT / "deploy/systemd/sigma-backup.timer").read_text()
        service = (ROOT / "deploy/systemd/sigma-backup.service").read_text()
        script = (ROOT / "deploy/backup-state.sh").read_text()
        self.assertIn("OnCalendar=*-*-* 10:17:00 UTC", timer)
        self.assertIn("Persistent=true", timer)
        self.assertIn("OnFailure=sigma-backup-failure.service", service)
        self.assertIn("status != 0", script)
        self.assertIn("SIGMA_BACKUP_RETENTION >= 14", script)
        self.assertIn("/dev/disk/by-id/google-${SIGMA_BACKUP_DISK}", script)
        self.assertIn('mounted_device != "$expected_device"', script)


if __name__ == "__main__":
    unittest.main()
