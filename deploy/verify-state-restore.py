#!/usr/bin/env python3
"""Read-only acceptance checks for a mounted SIGMA state-disk recovery copy."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import sys
from pathlib import Path

DATABASES = {
    "auth identity database": ("access.sqlite3", {"identities", "sessions", "grants"}),
    "workspace mapping database": ("workspaces/workspaces.sqlite3", {"workspaces"}),
    "research accounting database": ("workspaces/cloud-research.sqlite3", {"jobs", "calls"}),
}
SAFE_WORKSPACE_ID = re.compile(r"^[0-9a-f]{32}$")


def check_database(
    path: Path, expected_tables: set[str], expected_uid: int
) -> tuple[set[str], str]:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"missing or symlinked database: {path.name}")
    metadata = path.stat()
    if metadata.st_uid != expected_uid or metadata.st_mode & 0o077:
        raise ValueError(f"database owner or private mode is invalid: {path.name}")
    uri = f"file:{path.resolve()}?mode=ro"
    connection = sqlite3.connect(uri, uri=True, timeout=5)
    try:
        connection.execute("PRAGMA query_only=ON")
        integrity = connection.execute("PRAGMA integrity_check").fetchall()
        if integrity != [("ok",)]:
            raise ValueError(f"SQLite integrity_check failed for {path.name}: {integrity}")
        tables = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        missing = expected_tables - tables
        if missing:
            raise ValueError(f"{path.name} is missing required tables: {sorted(missing)}")
        if "workspaces" in tables:
            rows = connection.execute("SELECT subject_hash,workspace_id FROM workspaces").fetchall()
            workspaces = {row[1] for row in rows}
            if len(workspaces) != len(rows) or len({row[0] for row in rows}) != len(rows):
                raise ValueError("workspace mapping contains duplicate identities or directories")
            return workspaces, "ok"
        return set(), "ok"
    finally:
        connection.close()


def verify(
    root: Path,
    min_workspaces: int,
    min_projects: int,
    min_artifacts: int,
    min_papers: int,
) -> list[str]:
    results: list[str] = []
    if root.is_symlink() or not root.is_dir():
        raise ValueError("restore root must be an existing directory, not a symlink")
    auth = root / "auth"
    if auth.is_symlink() or not auth.is_dir():
        raise ValueError("restore root must contain a real auth directory")
    auth_metadata = auth.stat()
    if auth_metadata.st_mode & 0o077:
        raise ValueError("auth directory grants group or other access")

    mapped: set[str] = set()
    for description, (filename, tables) in DATABASES.items():
        identifiers, status = check_database(auth / filename, tables, auth_metadata.st_uid)
        if filename == "workspaces/workspaces.sqlite3":
            mapped = identifiers
        results.append(f"PASS {description}: SQLite integrity and required tables ({status})")

    access_db = sqlite3.connect(f"file:{(auth / 'access.sqlite3').resolve()}?mode=ro", uri=True)
    mapping_db = sqlite3.connect(
        f"file:{(auth / 'workspaces/workspaces.sqlite3').resolve()}?mode=ro", uri=True
    )
    try:
        subjects = {row[0] for row in access_db.execute("SELECT subject FROM identities")}
        identity_hashes = {
            hashlib.sha256(b"sigma-cloud-workspace-v1\0" + subject.encode()).hexdigest()
            for subject in subjects
        }
        mapped_hashes = {
            row[0] for row in mapping_db.execute("SELECT subject_hash FROM workspaces")
        }
    finally:
        access_db.close()
        mapping_db.close()
    if len(subjects) < min_workspaces:
        raise ValueError(
            f"only {len(subjects)} persisted cloud identities; expected at least {min_workspaces}"
        )
    if not mapped_hashes <= identity_hashes:
        raise ValueError("a workspace mapping has no corresponding persisted cloud identity")
    results.append(
        f"PASS identity mapping: {len(subjects)} identities; every workspace maps to a saved identity"
    )

    workspace_root = auth / "workspaces"
    if workspace_root.is_symlink() or not workspace_root.is_dir():
        raise ValueError("workspaces root is missing or symlinked")
    workspace_root_metadata = workspace_root.stat()
    if (
        workspace_root_metadata.st_uid != auth_metadata.st_uid
        or workspace_root_metadata.st_mode & 0o077
    ):
        raise ValueError("workspaces root owner or private mode is invalid")
    if len(mapped) < min_workspaces:
        raise ValueError(
            f"only {len(mapped)} identity mappings; expected at least {min_workspaces}"
        )
    workspace_entries = list(workspace_root.iterdir())
    metadata_files = {"workspaces.sqlite3", "cloud-research.sqlite3"}
    invalid_entries = [
        p.name
        for p in workspace_entries
        if p.is_symlink() or (not p.is_dir() and p.name not in metadata_files)
    ]
    if invalid_entries:
        raise ValueError(f"workspaces root contains {len(invalid_entries)} non-directory entries")
    workspace_dirs = {p.name for p in workspace_entries if p.is_dir()}
    invalid = sorted(value for value in mapped if not SAFE_WORKSPACE_ID.fullmatch(value))
    if invalid:
        raise ValueError(f"mapping contains {len(invalid)} invalid workspace IDs")
    missing = mapped - workspace_dirs
    orphaned = workspace_dirs - mapped
    if missing or orphaned:
        raise ValueError(
            f"workspace mapping isolation mismatch: missing dirs={len(missing)}, "
            f"unmapped dirs={len(orphaned)}"
        )
    for workspace_id in mapped:
        path = workspace_root / workspace_id
        metadata = path.lstat()
        if (
            path.is_symlink()
            or not path.is_dir()
            or metadata.st_uid != auth_metadata.st_uid
            or metadata.st_mode & 0o077
        ):
            raise ValueError(f"workspace {workspace_id} is not a private isolated directory")
    symlinks = [path for path in workspace_root.rglob("*") if path.is_symlink()]
    if symlinks:
        raise ValueError(f"workspace tree contains {len(symlinks)} symlink(s)")
    results.append(
        f"PASS workspace isolation: {len(mapped)} distinct mappings each own one directory"
    )

    project_files = list(workspace_root.glob("*/**/project.json"))
    for project_file in project_files:
        project = json.loads(project_file.read_text(encoding="utf-8"))
        if not isinstance(project, dict) or not isinstance(project.get("id"), str):
            raise TypeError("a saved project record is invalid")
    artifact_files = [
        path
        for path in workspace_root.rglob("*")
        if path.is_file()
        and not path.is_symlink()
        and path.suffix.lower() in {".json", ".pdf", ".tex", ".csv", ".png", ".svg"}
        and path.name not in {"project.json", ".DS_Store"}
    ]
    if len(project_files) < min_projects:
        raise ValueError(f"found {len(project_files)} projects; expected at least {min_projects}")
    if len(artifact_files) < min_artifacts:
        raise ValueError(
            f"found {len(artifact_files)} research artifacts; expected at least {min_artifacts}"
        )
    results.append(f"PASS saved workspace content: {len(project_files)} project records")
    results.append(
        f"PASS research artifacts: {len(artifact_files)} persisted JSON/PDF/TeX/data assets"
    )

    paper_records = list(workspace_root.glob("*/**/papers/*.json"))
    verified_papers = 0
    for record_path in paper_records:
        if record_path.is_symlink() or not record_path.is_file():
            raise ValueError("paper record is missing or symlinked")
        record = json.loads(record_path.read_text(encoding="utf-8"))
        paper_id = record.get("paper_id") if isinstance(record, dict) else None
        if not isinstance(paper_id, str) or not re.fullmatch(r"[0-9a-f]{32}", paper_id):
            raise ValueError(f"invalid paper record identity at {record_path.name}")
        if (
            record_path.stem != paper_id
            or not isinstance(record.get("tex_source"), str)
            or not record["tex_source"]
        ):
            raise ValueError(f"paper source identity or TeX source is invalid for {paper_id}")
        pdf_path = record_path.with_name(f"{paper_id}.pdf")
        if pdf_path.is_symlink() or not pdf_path.is_file():
            raise ValueError(f"paper PDF is missing or symlinked for {paper_id}")
        pdf = pdf_path.read_bytes()
        if (
            not pdf.startswith(b"%PDF-")
            or record.get("pdf_sha256") != hashlib.sha256(pdf).hexdigest()
            or record.get("pdf_size_bytes") != len(pdf)
        ):
            raise ValueError(f"paper PDF hash/size does not match its saved record for {paper_id}")
        verified_papers += 1
    if verified_papers < min_papers:
        raise ValueError(
            f"found {verified_papers} verified TeX/PDF paper pairs; expected at least {min_papers}"
        )
    results.append(
        f"PASS paper artifacts: {verified_papers} saved TeX sources match PDF size and SHA-256"
    )

    ledger = sqlite3.connect(
        f"file:{(auth / 'workspaces/cloud-research.sqlite3').resolve()}?mode=ro", uri=True
    )
    try:
        job_workspaces = {
            row[0] for row in ledger.execute("SELECT DISTINCT workspace_id FROM jobs")
        }
        call_workspaces = {
            row[0] for row in ledger.execute("SELECT DISTINCT workspace_id FROM calls")
        }
        invalid_jobs = len(job_workspaces - mapped)
        invalid_calls = len(call_workspaces - mapped)
        totals = ledger.execute(
            "SELECT COUNT(*), COALESCE(SUM(amount_usd),0), "
            "SUM(CASE WHEN status IN ('reserved','unknown') THEN 1 ELSE 0 END) FROM calls"
        ).fetchone()
        ledger_fk_errors = ledger.execute("PRAGMA foreign_key_check").fetchall()
    finally:
        ledger.close()
    if invalid_jobs or invalid_calls:
        raise ValueError(
            f"accounting ledger references unmapped workspace: jobs={invalid_jobs}, calls={invalid_calls}"
        )
    if ledger_fk_errors:
        raise ValueError(
            f"research accounting ledger has {len(ledger_fk_errors)} foreign key error(s)"
        )
    results.append(
        f"PASS accounting state: {totals[0]} call rows, ${totals[1]:.6f} recorded/reserved amount, "
        f"{totals[2] or 0} reserved or unknown outcomes preserved"
    )
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "restore_root", type=Path, help="read-only mount of restored disk filesystem"
    )
    parser.add_argument(
        "--min-workspaces", type=int, default=2, help="minimum distinct restored users"
    )
    parser.add_argument("--min-projects", type=int, default=1)
    parser.add_argument("--min-artifacts", type=int, default=1)
    parser.add_argument("--min-papers", type=int, default=1)
    args = parser.parse_args()
    try:
        if min(args.min_workspaces, args.min_projects, args.min_artifacts, args.min_papers) < 0:
            raise ValueError("minimum counts cannot be negative")
        for line in verify(
            args.restore_root,
            args.min_workspaces,
            args.min_projects,
            args.min_artifacts,
            args.min_papers,
        ):
            print(line)
    except (OSError, sqlite3.Error, ValueError) as exc:
        print(f"FAIL restore verification: {exc}", file=sys.stderr)
        return 1
    print("PASS: all restore checks completed read-only")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
