"""Sample catalog copies, recent-project behavior, collision safety, and API/CLI access."""

import fcntl
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import zlib
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient

from sigma.api import app
from sigma.projects import (
    ROOT,
    ProjectError,
    create_project,
    create_strategy,
    initialize_project,
    inspect_project,
    open_project,
)
from sigma.recents import (
    forget_recent,
    home_projects,
    pinned_projects,
    project_family,
    recent_projects,
    record_access,
    set_project_pin,
    state_directory,
)
from sigma.samples import open_sample_project, sample_projects


def check_recent_list_does_not_validate_sample_pdfs(root: Path) -> None:
    """Saved listing and opening need sample IDs, never sample PDF contents."""
    from sigma import samples

    # This is intentionally a cold call: do not depend on prior sample work.
    with patch.object(
        samples,
        "_sample_papers",
        side_effect=AssertionError("Saved Projects must never validate sample PDFs"),
    ):
        sample_ids = samples.sample_project_ids()
        assert sample_ids
        assert len(sample_ids) == len(samples._projects())
        view = initialize_project(
            root / "sample-id-only-list-test.sigma",
            "Saved list only",
            "Do not read unrelated sample papers.",
        )
        open_project(view.path)
        entries = recent_projects()["projects"]
        assert any(item["id"] == view.project.id and item["available"] for item in entries)
        with TestClient(app) as client:
            response = client.get("/api/projects/recent")
            assert response.status_code == 200
            assert response.headers["Server-Timing"].startswith("saved-projects;dur=")


def check_sample_index_metadata_does_not_decode_full_project() -> None:
    """Saved/name checks must not load project history or the project-type catalog."""
    from sigma import samples

    with patch.object(
        samples, "_decode", side_effect=AssertionError("Sample metadata used full decoder")
    ):
        identifiers = samples.sample_project_ids()
        titles = samples.sample_project_titles()
    assert len(identifiers) == len(titles) == len(samples._projects())


def check_index_sample_read_outside_lock() -> None:
    """Sample identity decoding must never monopolize the Saved index lock."""
    from sigma import samples

    lock_path = state_directory() / "recents.lock"
    original = samples.sample_project_ids

    def assert_unlocked() -> set[str]:
        with lock_path.open("a+b") as stream:
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
        return original()

    with patch.object(samples, "sample_project_ids", side_effect=assert_unlocked):
        recent_projects(lightweight=True)


def check_one_time_owner_migration(base: Path) -> None:
    """A verified owner gets one complete transfer, then never reopens old state."""
    from types import SimpleNamespace

    from sigma import (
        cloud_auth,
        cloud_workspaces,
        migrate_local_projects_once,
        project_collaboration,
    )
    from sigma.project_bundle import read_file, write_file
    from sigma.projects import initialize_project
    from sigma.research_sessions import read_session_snapshot

    root = base / "migration-original-projects"
    root.mkdir(mode=0o700)
    state = base / "migration-original-state"
    workspace_path = base / "migration-owner-workspace"
    workspace_path.mkdir(mode=0o700)
    database_root = base / "migration-workspaces-db"
    database_root.mkdir(mode=0o700)
    with (
        patch.dict(os.environ, {"SIGMA_PROJECTS_ROOT": str(root), "SIGMA_STATE_DIR": str(state)}),
        patch("sigma.projects._current_build_commit", return_value=None),
    ):
        saved = initialize_project(root / "previous.sigma", "Original project", "Existing research")
        record_access(saved)
        unlisted = initialize_project(root / "other.json", "Unlisted project", "Retain this also")
        source_sessions = {}
        for original in (saved, unlisted):
            session_id = str(uuid4())
            source_record = {
                "id": session_id,
                "project_id": original.project.id,
                "project_path": original.path,
                "session_number": 1,
                "status": "stopped",
                "created_at": "2026-11-08T00:00:00+00:00",
            }
            source_sessions[original.project.id] = source_record
            payload = (json.dumps(source_record) + "\n").encode()
            if original.path.endswith(".json"):
                write_file(original.path, f"research-sessions/{session_id}.json", payload)
            else:
                session_dir = Path(original.path) / "research-sessions"
                session_dir.mkdir()
                (session_dir / f"{session_id}.json").write_bytes(payload)
        # Old Saved may reference temporary worktrees removed after a test.
        # Only those missing paths are skipped; surviving projects still move.
        from sigma import recents

        missing_id = str(uuid4())
        missing_path = base / "deleted-pr-worktree" / "projects" / "missing.sigma"
        with recents._index() as index:
            index["entries"].append(
                {
                    "id": missing_id,
                    "path": str(missing_path),
                    "accessed_at": "2026-11-08T00:00:00+00:00",
                    "included_example": False,
                }
            )
            index["pins"]["missing test"] = missing_id
        index_before = (state / "recents.json").read_bytes()
        workspace = cloud_workspaces.Workspace(
            "a" * 32,
            "owner-hash",
            workspace_path,
            email=migrate_local_projects_once.TARGET_EMAIL,
            verified_subject="google:verified-owner",
        )
        principal = cloud_auth.Principal(
            subject="google:verified-owner",
            email=migrate_local_projects_once.TARGET_EMAIL,
            role="admin",
        )
        config = SimpleNamespace(local=True, enabled=True)
        token = cloud_workspaces.bind_workspace(workspace)
        try:
            with (
                patch("sigma.cloud_auth.config", return_value=config),
                patch.object(cloud_auth, "current_principal", return_value=principal),
                patch.object(cloud_workspaces, "storage_root", return_value=database_root),
            ):
                migrate_local_projects_once.migrate_if_needed(principal)
                with project_collaboration._db() as db:
                    owners = db.execute(
                        "SELECT path, project_id, owner_hash FROM shared_projects"
                    ).fetchall()
                assert len(owners) == 2
                assert all(row["owner_hash"] == workspace.subject_hash for row in owners)
                marker_path = workspace_path / ".sigma-state/local-projects-migrated-v1.json"
                assert marker_path.is_file()
                marker_data = json.loads(marker_path.read_text())
                assert marker_data["project_count"] == 2
                assert marker_data["skipped_missing"] == [
                    {"id": missing_id, "path": str(missing_path)}
                ]
                with recents._index() as index:
                    assert missing_id not in {entry["id"] for entry in index["entries"]}
                    assert missing_id not in index["pins"].values()
                imported = {row["id"]: row for row in recent_projects(lightweight=True)["projects"]}
                assert set(imported) == {saved.project.id, unlisted.project.id}
                for original in (saved, unlisted):
                    row = imported[original.project.id]
                    assert Path(row["path"]).is_relative_to(workspace_path)
                    assert inspect_project(row["path"]).project.id == original.project.id
                    records, unavailable = read_session_snapshot(row["path"])
                    assert unavailable == 0 and len(records) == 1
                    assert records[0]["id"] == source_sessions[original.project.id]["id"]
                    assert records[0]["project_path"] == row["path"]
                    # Originals remain at the original path and retain session identity.
                    original_record = source_sessions[original.project.id]
                    if original.path.endswith(".json"):
                        raw = read_file(
                            original.path, f"research-sessions/{original_record['id']}.json"
                        )
                    else:
                        raw = (
                            Path(original.path)
                            / "research-sessions"
                            / f"{original_record['id']}.json"
                        ).read_bytes()
                    assert json.loads(raw)["project_path"] == original.path
                # Second sign-in does not scan or copy the old library.
                with patch.object(
                    migrate_local_projects_once,
                    "_source_inventory",
                    side_effect=AssertionError("Migration ran a second time"),
                ):
                    migrate_local_projects_once.migrate_if_needed(principal)
        finally:
            cloud_workspaces.reset(token)
        assert (state / "recents.json").read_bytes() == index_before


def check_migration_rewrites_frozen_snapshot_refs() -> None:
    """Relocating a path-dependent frozen package preserves its content hash contract."""
    from sigma.migrate_local_projects_once import _relocate_members
    from sigma.project_copy import _canonical

    source = Path("/tmp/sigma-before.sigma")
    destination = Path("/tmp/sigma-after.sigma")
    project_id = str(uuid4())
    session_id = str(uuid4())
    original_package = {
        "schema": "sigma-paper-evidence-v2",
        "project_id": project_id,
        "project_path": str(source),
    }
    original = _canonical(original_package)
    old_digest = hashlib.sha256(original).hexdigest()
    members = {
        "project.json": json.dumps({"schema_version": 13, "id": project_id}).encode(),
        f"research-sessions/{session_id}.json": json.dumps(
            {"id": session_id, "project_id": project_id, "project_path": str(source)}
        ).encode(),
        "papers/frozen.json": json.dumps(
            {"snapshot_ref": old_digest, "snapshot_sha256": old_digest}
        ).encode(),
        f"papers/.snapshots/{old_digest}.json.zlib": zlib.compress(original),
    }
    migrated = _relocate_members(members, source, destination, project_id)
    result = json.loads(migrated[f"research-sessions/{session_id}.json"])
    assert result["project_path"] == str(destination) and result["id"] == session_id
    archive = next(name for name in migrated if name.endswith(".json.zlib"))
    new_digest = archive.split("/")[-1].removesuffix(".json.zlib")
    assert new_digest != old_digest
    assert hashlib.sha256(zlib.decompress(migrated[archive])).hexdigest() == new_digest
    assert json.loads(migrated["papers/frozen.json"])["snapshot_ref"] == new_digest


def check_compact_project_open() -> None:
    """Interactive opens omit the hidden event history; default reads retain it."""
    created = create_project("Compact opening contract", "Keep research history intact")
    with TestClient(app) as client:
        compact = client.post("/api/projects/open", json={"path": created.path, "compact": True})
        full = client.post("/api/projects/open", json={"path": created.path})
    assert compact.status_code == 200, compact.text
    assert full.status_code == 200, full.text
    assert compact.json()["project"]["events"] == []
    assert full.json()["project"]["events"]
    assert inspect_project(created.path).project.events == created.project.events


def check_existing_workspace_lookup_does_not_take_writer_lock(base: Path) -> None:
    """Ordinary signed-in requests must not wait for unrelated SQLite writers."""
    from sigma import cloud_workspaces

    storage = base / "workspace-registry-test"
    storage.mkdir(mode=0o700)
    actual_connect = cloud_workspaces._connect

    def short_timeout_connect(root: Path):
        connection = actual_connect(root)
        connection.execute("PRAGMA busy_timeout=100")
        return connection

    with (
        patch.object(cloud_workspaces, "storage_root", return_value=storage),
        patch.object(cloud_workspaces, "_connect", side_effect=short_timeout_connect),
    ):
        before = cloud_workspaces.workspace_for_subject("google:workspace-regression")
        with sqlite3.connect(storage / "workspaces.sqlite3", isolation_level=None) as writer:
            writer.execute("BEGIN IMMEDIATE")
            try:
                after = cloud_workspaces.workspace_for_subject("google:workspace-regression")
            finally:
                writer.execute("ROLLBACK")
        assert before.path == after.path and before.workspace_id == after.workspace_id


def check_title_collision_avoids_deep_metadata() -> None:
    """Creating a project must not hydrate Saved status or sample paper scores."""
    with (
        patch(
            "sigma.samples._best_sample_paper", side_effect=AssertionError("sample scores scanned")
        ),
        patch(
            "sigma.paper_scores.project_metadata",
            side_effect=AssertionError("paper metadata scanned"),
        ),
    ):
        created = create_project("Lightweight title collision check", "Fast creation")
    assert created.project.title == "Lightweight title collision check"


def check_project_metadata_cache_invalidation(root: Path) -> None:
    """Unchanged Saved-list polls must not read full paper records repeatedly."""
    from sigma import paper_scores, papers

    project_dir = root / "metadata-cache-test.sigma"
    project_dir.mkdir()
    (project_dir / "project.json").write_text("{}", encoding="utf-8")
    paper_dir = project_dir / "papers"
    paper_dir.mkdir()
    record = paper_dir / "paper-one.json"
    record.write_text('{"paper":1}', encoding="utf-8")
    pdf = paper_dir / "paper-one.pdf"
    pdf.write_bytes(b"%PDF-test")
    paper_scores._project_metadata_cached.cache_clear()
    calls: list[int] = []

    def mock_list(_path: str) -> list[dict]:
        calls.append(1)
        return [{"pdf_available": True, "score": None}]

    with patch.object(papers, "list_papers", new=mock_list):
        first = paper_scores.project_metadata(str(project_dir))
        assert first["paper_count"] == 1
        assert paper_scores.project_metadata(str(project_dir)) == first
        assert len(calls) == 1, "Unchanged Saved polls must reuse verified metadata"
        record.write_text('{"paper":2, "updated":true}', encoding="utf-8")
        assert paper_scores.project_metadata(str(project_dir)) == first
        assert len(calls) == 2, "Updating a paper must invalidate the cache"
        pdf.unlink()
        paper_scores.project_metadata(str(project_dir))
        assert len(calls) == 2, "PDF deletion must not trigger Home revalidation"
    paper_scores._project_metadata_cached.cache_clear()


def check_home_list_uses_only_paper_records(root: Path) -> None:
    """Cold Home/Most Recent listing must not read, inspect or hash PDFs."""
    from sigma import paper_scores, papers

    view = initialize_project(
        root / "home-paper-metadata-test.sigma", "Paper summary only", "List without PDF reads."
    )
    paper_id = "e" * 32
    papers._save(
        view.path,
        {
            "schema_version": 1,
            "paper_id": paper_id,
            "project_id": view.project.id,
            "created_at": "2026-11-08T00:00:00+00:00",
            "snapshot_sha256": "c" * 64,
            "draft": {"title": "Published paper"},
            "generation": {},
            "validation_warnings": [],
        },
        b"%PDF-home-metadata-fixture",
    )
    record = papers._read_one(view.path, paper_id)
    judgment = paper_scores.PaperJudgment.model_validate(
        {
            name: {"earned": 70, "explanation": "Valid fixture with measured evidence."}
            for name in paper_scores.WEIGHTS
        }
    )
    score = paper_scores._make_score(judgment, record["pdf_sha256"])
    paper_scores._save_score(view.path, paper_id, score)
    open_project(view.path)
    paper_scores._project_metadata_cached.cache_clear()
    original_open = Path.open
    original_read = Path.read_bytes

    def refuse_pdf_open(path: Path, *args, **kwargs):
        if path.suffix == ".pdf":
            raise AssertionError("Home opened a PDF")
        return original_open(path, *args, **kwargs)

    def refuse_pdf_read(path: Path, *args, **kwargs):
        if path.suffix == ".pdf":
            raise AssertionError("Home read a PDF")
        return original_read(path, *args, **kwargs)

    with (
        patch.object(papers, "_valid_pdf_file", side_effect=AssertionError("Home checked a PDF")),
        patch.object(papers, "_cached_pdf_digest", side_effect=AssertionError("Home hashed a PDF")),
        patch.object(Path, "open", refuse_pdf_open),
        patch.object(Path, "read_bytes", refuse_pdf_read),
    ):
        for listing in (recent_projects, home_projects):
            rows = [row for row in listing()["projects"] if row["id"] == view.project.id]
            assert len(rows) == 1 and rows[0]["available"], rows
            assert rows[0]["paper_count"] == 1, rows
            assert rows[0]["best_paper_score"] == 70, rows
        # Paper details and the Papers list must also remain metadata-only.
        assert papers.list_papers(view.path)[0]["score"]["total"] == 70
        assert papers.get_paper(view.path, paper_id, include_tex=False)["score"]["total"] == 70
        # Corrupt individual paper records must not hide the saved project.
        paper_dir = Path(view.path) / "papers"
        (paper_dir / "malformed.json").write_text("{broken", encoding="utf-8")
        assert any(
            row["id"] == view.project.id and row["available"] for row in home_projects()["projects"]
        )
        with patch.object(paper_scores, "project_metadata", side_effect=OSError("broken")):
            rows = [row for row in recent_projects()["projects"] if row["id"] == view.project.id]
            assert len(rows) == 1 and rows[0]["available"]
            assert rows[0]["paper_count"] == 0
    paper_scores._project_metadata_cached.cache_clear()


def check_shallow_home_does_not_load_deep_status(root: Path) -> None:
    """First paint never parses research history or paper records."""
    from sigma import paper_scores, papers, research_sessions

    view = initialize_project(
        root / "shallow-home-list-test.sigma",
        "Fast Home listing",
        "Read full history only when needed.",
    )
    open_project(view.path)
    with (
        patch.object(
            research_sessions,
            "has_active_session",
            side_effect=AssertionError("Shallow Home parsed research history"),
        ),
        patch.object(
            paper_scores,
            "project_metadata",
            side_effect=AssertionError("Shallow Home scanned papers"),
        ),
        patch.object(
            papers,
            "activity_status",
            side_effect=AssertionError("Shallow Home scanned activity"),
        ),
    ):
        rows = {item["id"]: item for item in home_projects(lightweight=True)["projects"]}
        assert rows[view.project.id]["available"]
        assert rows[view.project.id]["title"] == "Fast Home listing"
        with TestClient(app) as client:
            response = client.get("/api/projects/recent?lightweight=true")
            assert response.status_code == 200
            rows = {item["id"]: item for item in response.json()["projects"]}
            assert rows[view.project.id]["available"]
    with (
        patch.object(
            paper_scores,
            "project_metadata",
            side_effect=AssertionError("Activity poll scanned papers"),
        ),
        patch.object(research_sessions, "has_active_session", return_value=True),
        patch.object(papers, "activity_status", return_value="queued"),
        TestClient(app) as client,
    ):
        response = client.get("/api/projects/recent/activity")
        assert response.status_code == 200
        by_id = {item["id"]: item for item in response.json()["projects"]}
        assert by_id[view.project.id]["research_running"]
        assert by_id[view.project.id]["paper_activity"] == "queued"


def check_home_session_status_cache(root: Path) -> None:
    """Home listing must not repeatedly decode multi-MB research histories."""
    from sigma import cloud_research, research_sessions

    view = initialize_project(
        root / "recent-status-cache-test.sigma", "Status cache test", "Check status caching."
    )
    directory = Path(view.path) / "research-sessions"
    directory.mkdir(mode=0o700)
    session_id = str(uuid4())
    file = directory / f"{session_id}.json"
    record = {
        "id": session_id,
        "project_id": view.project.id,
        "project_path": view.path,
        "status": "ended",
        "large_history": "historical prompt " * 100_000,
    }
    file.write_text(json.dumps(record), encoding="utf-8")
    research_sessions._recent_session_status.cache_clear()
    original_read_text = Path.read_text
    reads: list[int] = []

    def tracked_read_text(path: Path, *args, **kwargs) -> str:
        if path == file:
            reads.append(1)
        return original_read_text(path, *args, **kwargs)

    with (
        patch.object(Path, "read_text", tracked_read_text),
        patch.object(
            research_sessions,
            "read_session_snapshot",
            side_effect=AssertionError("Home must not decode full session snapshots"),
        ),
        patch.object(cloud_research, "billing_enabled", return_value=True),
    ):
        for _ in range(3):
            assert not research_sessions.has_active_session(view.path, project_id=view.project.id)
        assert len(reads) == 1, "Unchanged 1+ MB session must be parsed just once"
        assert not research_sessions.has_active_session(view.path, project_id=str(uuid4()))
        assert len(reads) == 2, "Foreign workspace identity must not share cached status"
        record["status"] = "queued"
        file.write_text(json.dumps(record), encoding="utf-8")
        assert research_sessions.has_active_session(view.path, project_id=view.project.id)
        assert len(reads) == 3, "A changed session must invalidate cached status"
        file.unlink()
        assert not research_sessions.has_active_session(view.path, project_id=view.project.id)
    research_sessions._recent_session_status.cache_clear()


def check_paper_preflight_presence(root: Path) -> None:
    """New projects do not need startup preflight; checkpoints still do."""
    from sigma import papers

    view = initialize_project(
        root / "paper-preflight-status-test.sigma", "Paper preflight test", "Check recovery."
    )
    root_path = Path(view.path)
    assert not papers.needs_preflight_on_open(view.path)
    assert not (root_path / "papers").exists(), "Read-only check must not create paper storage"
    work = root_path / "papers" / ".long-paper-work"
    work.mkdir(parents=True, mode=0o700)
    checkpoint = work / "checkpoint.json"
    checkpoint.write_text("{}", encoding="utf-8")
    assert papers.needs_preflight_on_open(view.path)
    checkpoint.unlink()
    reset = work / "reset-ledger.json"
    reset.write_text("{}", encoding="utf-8")
    assert papers.needs_preflight_on_open(view.path), "Reset receipts need recovery preflight"
    reset.unlink()
    assert not papers.needs_preflight_on_open(view.path)


def check_pdf_verification_cache(root: Path) -> None:
    """Opening a listed project must reuse its verified PDF without another hash."""
    from sigma import papers

    view = initialize_project(
        root / "pdf-verification-cache-test.sigma", "PDF cache test", "Check integrity."
    )
    paper_dir = Path(view.path) / "papers"
    paper_dir.mkdir(mode=0o700)
    file = paper_dir / "paper-test.pdf"
    original = b"%PDF-verified-test"
    file.write_bytes(original)
    record = {
        "paper_id": "paper-test",
        "pdf_size_bytes": len(original),
        "pdf_sha256": hashlib.sha256(original).hexdigest(),
    }
    papers._cached_pdf_digest.cache_clear()
    original_open = Path.open
    reads: list[int] = []

    def tracked_open(path: Path, *args, **kwargs):
        if path == file and args and args[0] == "rb":
            reads.append(1)
        return original_open(path, *args, **kwargs)

    with patch.object(Path, "open", tracked_open):
        assert papers._valid_pdf_file(view.path, record)
        assert papers._valid_pdf_file(view.path, record)
        assert len(reads) == 1, "Project reopening should not hash an unchanged PDF"
        file.write_bytes(b"%PDX-verified-test")
        assert not papers._valid_pdf_file(view.path, record)
        assert len(reads) == 2, "Same-sized content changes must invalidate cached hashes"
        file.write_bytes(original)
        assert papers._valid_pdf_file(view.path, record)
        assert len(reads) == 3
        file.unlink()
        assert not papers._valid_pdf_file(view.path, record)
    papers._cached_pdf_digest.cache_clear()


def check(root: Path, base: Path) -> None:
    sources = {path: path.read_bytes() for path in (ROOT / "samples").glob("*/project.json")}
    catalog = sample_projects()["projects"]
    assert len(catalog) == len(sources)
    assert {entry["id"] for entry in catalog} == {path.parent.name for path in sources}
    assert {entry["title"] for entry in catalog} >= {
        "Nonconsecutive Subset Sums Modulo 3",
        "Did Jesus Use Cannabis?",
        "Operation Narrow Passage",
        "Warp Drive Feasibility",
        "When Does Qubit Decoherence Require a Non-Markovian Model?",
    }
    sample_categories = {entry["title"]: entry["investigation_type"] for entry in catalog}
    assert sample_categories["Did Jesus Use Cannabis?"] == "religion"
    assert sample_categories["Operation Narrow Passage"] == "military"
    assert sample_categories["Warp Drive Feasibility"] == "engineering"
    assert (
        sample_categories["When Does Qubit Decoherence Require a Non-Markovian Model?"] == "physics"
    )
    qubit_source = json.loads(
        (ROOT / "samples" / "qubit-non-markovian-decoherence" / "project.json").read_bytes()
    )
    assert qubit_source["schema_version"] == 13
    assert qubit_source["desired_outcomes"] and qubit_source["paper_requirements"]
    qubit_root = base / "qubit-projects"
    qubit_root.mkdir()
    with patch.dict(
        os.environ,
        {
            "SIGMA_PROJECTS_ROOT": str(qubit_root),
            "SIGMA_STATE_DIR": str(base / "qubit-state"),
        },
    ):
        qubit_sample = open_sample_project("qubit-non-markovian-decoherence")
    qubit_copy = json.loads((Path(qubit_sample.path) / "project.json").read_bytes())
    assert qubit_copy["problem"] == qubit_source["problem"]
    assert qubit_sample.project.investigation_type == "physics"
    assert qubit_sample.project.schema_version == 13
    qubit_snapshot = qubit_sample.project.project_type_snapshot
    assert qubit_snapshot is not None
    assert qubit_snapshot["name"] == "Physics"
    assert qubit_snapshot["icon"]["key"] == "physics"
    with patch.dict(
        os.environ,
        {
            "SIGMA_PROJECTS_ROOT": str(qubit_root),
            "SIGMA_STATE_DIR": str(base / "qubit-state"),
        },
    ):
        created_physics = initialize_project(
            qubit_root / "physics-created.sigma",
            qubit_source["title"],
            qubit_source["problem"],
            research_mode="physics",
        )
    created_document = json.loads((Path(created_physics.path) / "project.json").read_bytes())
    assert created_document["problem"] == qubit_source["problem"]
    assert created_document["project_type_snapshot"]["name"] == "Physics"
    assert created_document["project_type_snapshot"]["icon"]["key"] == "physics"
    maximum_regions = next(item for item in catalog if item["id"] == "maximum-regions-by-lines")
    assert maximum_regions["difficulty"] == "easy"
    assert maximum_regions["strategy_count"] == 1
    maximum_raw = json.loads(
        (ROOT / "samples" / "maximum-regions-by-lines" / "project.json").read_bytes()
    )
    archived_solution = next(
        strategy for strategy in maximum_raw["strategies"] if strategy["removed_at"]
    )
    active_starter = next(
        strategy for strategy in maximum_raw["strategies"] if not strategy["removed_at"]
    )
    assert archived_solution["provenance"]["provider"] == "openai"
    assert hashlib.sha256(archived_solution["approach"].encode()).hexdigest() == (
        "74b756da7105ba842adfb2bde8d6f88349b4c4010555cefc9d30b147983db9f4"
    )
    assert "R(n) = 1 + n(n + 1)/2" in archived_solution["summary"]
    assert "R(n) = 1 + n(n + 1)/2" not in active_starter["approach"]
    assert "upper bound" in active_starter["approach"]
    binary_counting = next(
        item for item in catalog if item["id"] == "counting-constrained-binary-strings"
    )
    assert binary_counting["difficulty"] == "easy"
    difficulty_by_id = {entry["id"]: entry["difficulty"] for entry in catalog}
    assert difficulty_by_id["nonconsecutive-subset-sums"] == "hard"
    assert difficulty_by_id["operation-narrow-passage"] == "hard"
    assert difficulty_by_id["warp-drive-engineering"] == "hard"
    strategy_counts = {entry["id"]: entry["strategy_count"] for entry in catalog}
    assert strategy_counts["algorithm-design"] == 2
    assert strategy_counts["counting-constrained-binary-strings"] == 1
    assert strategy_counts["operation-narrow-passage"] == 2
    assert strategy_counts["riemann-hypothesis-research"] == 4
    assert strategy_counts["scientific-investigation"] == 2
    assert strategy_counts["warp-drive-engineering"] == 2
    assert strategy_counts["warp-drive-physics"] == 2
    assert {entry["investigation_type"] for entry in catalog} >= {
        "mathematical",
        "engineering",
        "religion",
        "military",
    }
    assert catalog[-1]["title"] == "Did Jesus Use Cannabis?"
    assert home_projects()["projects"] == [] and not list(root.iterdir())

    # Three source-controlled defaults activate only when their exact project IDs
    # enter the workspace. They never mark unrelated local versions as pinned.
    from sigma.recents import _effective_pins, _paper_test_defaults

    defaults = _paper_test_defaults()
    assert defaults == {
        "ai agent reliability and evaluation": "da4580f5-7620-49b0-882e-aee34fcdc05d",
        "sovereign ai federation": "9175d73d-62aa-4523-a286-445f5390ae1d",
        "why do xenopus tadpoles temporarily lose tail regeneration?": (
            "01de54c9-9593-413a-9577-1a952d28da70"
        ),
    }
    empty = {"entries": [], "pins": {}, "dismissed_default_pins": []}
    assert _effective_pins(empty) == {}
    agent_id = defaults["ai agent reliability and evaluation"]
    open_index = {
        "entries": [{"id": agent_id}],
        "pins": {},
        "dismissed_default_pins": [],
    }
    assert _effective_pins(open_index) == {"ai agent reliability and evaluation": agent_id}
    open_index["dismissed_default_pins"] = ["ai agent reliability and evaluation"]
    assert _effective_pins(open_index) == {}
    open_index["pins"]["ai agent reliability and evaluation"] = str(uuid4())
    assert _effective_pins(open_index) == open_index["pins"]

    expanded = base / "extra-samples"
    expanded.mkdir()
    for number in range(6):
        location = expanded / f"sample-{number}"
        location.mkdir()
        (location / "project.json").write_bytes(next(iter(sources.values())))
    with patch("sigma.samples.SAMPLES", expanded):
        assert len(sample_projects()["projects"]) == 6
    assert not list(root.iterdir())

    selected = binary_counting
    source_path = ROOT / "samples" / selected["id"] / "project.json"
    first = open_sample_project(selected["id"])
    assert first.path == str(root / f"{selected['id']}.sigma")
    assert first.project.id != json.loads(sources[source_path])["id"]
    assert first.project.title == f"{selected['title']} v1"
    assert (Path(first.path) / "project.json").read_bytes() != sources[source_path]
    second = open_sample_project(selected["id"])
    assert second.path != first.path and second.project.id != first.project.id
    assert second.project.title == f"{selected['title']} v2"
    assert len(list(root.glob("*.sigma"))) == 2
    assert [item["id"] for item in recent_projects()["projects"]] == [
        second.project.id,
        first.project.id,
    ]
    recent_by_id = {item["id"]: item for item in recent_projects()["projects"]}
    assert recent_by_id[first.project.id]["difficulty"] == first.project.difficulty
    assert recent_by_id[second.project.id]["difficulty"] == second.project.difficulty

    # Pin is a local selection for paper tests, never a scientific or publication verdict.
    assert project_family(first.project.title) == project_family(second.project.title)
    assert project_family("Xenopus Tadpoles V9") == project_family("xenopus tadpoles v10")
    assert project_family("Warp Drive") == project_family("Warp Drive v2")
    assert project_family("Nonconsecutive Subsets") != project_family("Warp Drive v2")
    assert recent_by_id[first.project.id]["pin_state"] == "pin_remove"
    assert recent_by_id[second.project.id]["pin_state"] == "pin_remove"
    assert pinned_projects()["projects"] == []
    set_project_pin(first.project.id, first.path, True)
    states = {item["id"]: item["pin_state"] for item in recent_projects()["projects"]}
    assert states[first.project.id] == "unpin"
    assert states[second.project.id] == "remove"
    visibility = {
        item["id"]: item["hidden_by_family_pin"] for item in recent_projects()["projects"]
    }
    assert visibility[first.project.id] is False
    assert visibility[second.project.id] is True
    assert [item["id"] for item in pinned_projects()["projects"]] == [first.project.id]
    try:
        set_project_pin(second.project.id, second.path, True)
        raise AssertionError("Two family versions were pinned")
    except ProjectError as exc:
        assert "Another version" in str(exc)
    # Retired pin state no longer blocks removal from Saved; the project itself stays on disk.
    assert Path(first.path, "project.json").exists()
    with TestClient(app) as api:
        assert api.get("/api/projects/pinned").json()["projects"][0]["id"] == first.project.id
        # Removal and project deletion are no longer gated by a retired pin.
        assert api.get("/api/projects/recent").status_code == 200
        conflict = api.post(
            "/api/projects/pin",
            json={"project_id": second.project.id, "path": second.path, "pinned": True},
        )
        assert conflict.status_code == 400
        unpin = api.post(
            "/api/projects/pin",
            json={"project_id": first.project.id, "path": first.path, "pinned": False},
        )
        assert unpin.status_code == 200
        selected_pin_response = api.post(
            "/api/projects/pin",
            json={"project_id": second.project.id, "path": second.path, "pinned": True},
        )
        assert selected_pin_response.status_code == 200
        assert api.get("/api/projects/pinned").json()["projects"][0]["id"] == second.project.id
        assert (
            api.post(
                "/api/projects/pin",
                json={"project_id": second.project.id, "path": second.path, "pinned": False},
            ).status_code
            == 200
        )
        assert api.get("/api/projects/pinned").json()["projects"] == []
    assert all(item["pin_state"] == "pin_remove" for item in recent_projects()["projects"])
    assert not any(item["hidden_by_family_pin"] for item in recent_projects()["projects"])
    edited = create_strategy(first.path, "My addition", "Investigate this case")
    reopened = open_sample_project(selected["id"])
    assert reopened.project.id not in {first.project.id, second.project.id}
    assert len(reopened.project.active_order) == selected["strategy_count"]
    refreshed_catalog = {item["id"]: item for item in sample_projects()["projects"]}
    assert refreshed_catalog[selected["id"]]["strategy_count"] == selected["strategy_count"]
    assert Path(first.path, "project.json").read_bytes() != sources[source_path]

    other = open_sample_project(catalog[-1]["id"])
    assert other.path != first.path and other.project.id != first.project.id
    assert len(list(root.glob("*.sigma"))) == 4
    try:
        open_sample_project("../../unknown")
        raise AssertionError("An unknown sample identifier was accepted")
    except ProjectError:
        pass

    collision = root / f"{selected['id']}.sigma"
    moved = root / "saved-sample.sigma"
    collision.rename(moved)
    impostor = create_project(selected["id"], "Different research")
    assert impostor.path == str(root / f"{selected['id']}.json")
    assert inspect_project(impostor.path).project == impostor.project
    additional = open_sample_project(selected["id"])
    assert additional.path == str(collision)
    assert additional.project.id not in {first.project.id, second.project.id}
    assert inspect_project(collision).project == additional.project
    collision.rename(root / "saved-impostor.sigma")
    moved.rename(collision)
    last_copy = open_sample_project(selected["id"])
    assert last_copy.project.id != edited.project.id

    created = [create_project(f"User project {i}", "Own research") for i in range(5)]
    from sigma import research_sessions

    active = first  # Legacy directory project exercises worker-lock status reads.
    idle = created[-2]
    idle_directory = Path(idle.path) / "research-sessions"
    assert not idle_directory.exists()
    assert not research_sessions.has_active_session(idle.path)
    assert not idle_directory.exists(), "Home status must not create session storage"

    directory = Path(active.path) / "research-sessions"
    directory.mkdir(exist_ok=True)
    session_id = str(uuid4())
    session_file = directory / f"{session_id}.json"
    record = {
        "id": session_id,
        "project_id": active.project.id,
        "project_path": active.path,
        "status": "running",
        "created_at": "2026-10-25T00:00:00Z",
    }
    session_file.write_text(json.dumps(record), encoding="utf-8")
    lock_path = directory / f"{session_id}.worker.lock"
    original_record = session_file.read_bytes()
    assert not research_sessions.has_active_session(active.path)
    assert session_file.read_bytes() == original_record
    assert not lock_path.exists(), "Status reads must not create worker locks"
    with lock_path.open("a") as worker_lock:
        fcntl.flock(worker_lock.fileno(), fcntl.LOCK_EX)
        assert research_sessions.has_active_session(active.path)
        by_id = {item["id"]: item for item in recent_projects()["projects"]}
        assert by_id[active.project.id]["research_running"] is True
        with TestClient(app) as client:
            response = client.get("/api/projects/recent")
            assert response.status_code == 200
            api_by_id = {item["id"]: item for item in response.json()["projects"]}
            assert api_by_id[active.project.id]["research_running"] is True
        assert session_file.read_bytes() == original_record
        fcntl.flock(worker_lock.fileno(), fcntl.LOCK_UN)
    assert not research_sessions.has_active_session(active.path)
    for status in ("completed", "paused", "stopped", "failed"):
        record["status"] = status
        session_file.write_text(json.dumps(record), encoding="utf-8")
        assert not research_sessions.has_active_session(active.path)

    actual = recent_projects()["projects"]
    running_project = created[-1]
    session_id = str(uuid4())
    from sigma.project_bundle import write_file

    write_file(
        running_project.path,
        f"research-sessions/{session_id}.json",
        json.dumps(
            {
                "id": session_id,
                "project_id": running_project.project.id,
                "project_path": running_project.path,
                "status": "stopped",
            }
        ).encode("utf-8"),
    )
    assert [entry["id"] for entry in actual[:4]] == [
        view.project.id for view in reversed(created[-4:])
    ]
    assert all(view.project.id in {entry["id"] for entry in actual} for view in created)
    assert (
        max(
            sum(entry["investigation_type"] == category for entry in actual)
            for category in {entry["investigation_type"] for entry in actual}
        )
        > 4
    )
    open_project(created[0].path)
    assert recent_projects()["projects"][0]["id"] == created[0].project.id
    updated_recent = recent_projects()["projects"]
    assert [entry["id"] for entry in updated_recent[:4]] == [
        created[0].project.id,
        *(view.project.id for view in reversed(created[2:5])),
    ]
    open_project(first.path)
    assert recent_projects()["projects"][0]["id"] == first.project.id

    with TestClient(app) as api:
        before = (state_directory() / "recents.json").read_bytes()
        api_recent = api.get("/api/projects/recent").json()["projects"]
        assert len(api_recent) == len(updated_recent)
        assert len(api_recent) > 4
        assert (state_directory() / "recents.json").read_bytes() == before
        assert api.get("/api/projects/samples").json()["projects"] == sample_projects()["projects"]
        response = api.post("/api/projects/samples/open", json={"sample_id": selected["id"]})
        assert response.status_code == 200
        assert response.json()["path"] != first.path
        assert len(list(root.glob(f"{selected['id']}*.sigma"))) >= 5
        assert (
            api.post("/api/projects/samples/open", json={"sample_id": "unknown"}).status_code == 400
        )
        assert (
            api.post("/api/projects/samples/copy", json={"sample_id": selected["id"]}).status_code
            == 404
        )
        assert (
            api.post(
                "/api/projects/recent/forget", json={"project_id": created[0].project.id}
            ).status_code
            == 200
        )
        from sigma.project_bundle import read_file, write_file

        identity_drift = create_project("Codex identity drift", "Saved from a Codex session")
        document = json.loads(read_file(identity_drift.path, "project.json"))
        document["id"] = str(uuid4())
        write_file(identity_drift.path, "project.json", json.dumps(document).encode())
        drifted_entry = next(
            item
            for item in api.get("/api/projects/recent").json()["projects"]
            if item["path"] == identity_drift.path
        )
        assert drifted_entry["available"] is False
        removed = api.post(
            "/api/projects/recent/forget",
            params={"path": drifted_entry["path"]},
            json={"project_id": document["id"]},
        )
        assert removed.status_code == 200, removed.text
        assert all(
            item["path"] != identity_drift.path
            for item in api.get("/api/projects/recent").json()["projects"]
        )
    command = subprocess.run(
        [str(ROOT / "sigma"), "create", "--title", "CLI recent", "--problem", "Own work"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert recent_projects()["projects"][0]["id"] == json.loads(command.stdout)["project"]["id"]

    # Old automatic example entries disappear from Recents without deleting research.
    index_path = state_directory() / "recents.json"
    # Legacy v1 state is upgraded without discarding the saved project index.
    legacy = json.loads(index_path.read_text())
    assert legacy["version"] == 2 and legacy["pins"] == {}
    assert project_family(first.project.title) in legacy["dismissed_default_pins"]
    legacy["version"] = 1
    del legacy["pins"]
    del legacy["dismissed_default_pins"]
    for entry in legacy["entries"]:
        entry["pinned"] = entry["id"] == first.project.id
    rejected = json.loads(json.dumps(legacy))
    rejected_entry = next(entry for entry in rejected["entries"] if entry["pinned"])
    rejected_entry["id"] = str(uuid4())
    rejected_bytes = json.dumps(rejected).encode()
    index_path.write_bytes(rejected_bytes)
    try:
        recent_projects()
        raise AssertionError("Legacy pin with mismatched project identity was migrated")
    except ProjectError:
        pass
    assert index_path.read_bytes() == rejected_bytes
    index_path.write_text(json.dumps(legacy))
    previous_ids = [item["id"] for item in legacy["entries"]]
    assert [item["id"] for item in recent_projects()["projects"]] == previous_ids
    migrated = json.loads(index_path.read_text())
    assert migrated["version"] == 2
    assert migrated["pins"][project_family(first.project.title)] == first.project.id
    assert all("pinned" not in entry for entry in migrated["entries"])
    subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from sigma.recents import pinned_projects; "
                "projects = pinned_projects()['projects']; "
                "assert len(projects) == 1"
            ),
        ],
        check=True,
        capture_output=True,
        text=True,
        env=os.environ.copy(),
    )
    index = json.loads(index_path.read_text())
    index["entries"] = [
        {"id": first.project.id, "path": first.path, "accessed_at": None, "included_example": True},
        *[entry for entry in index["entries"] if entry["id"] != first.project.id][:3],
    ]
    index_path.write_text(json.dumps(index))
    assert all(not entry["included_example"] for entry in home_projects()["projects"])
    assert len(recent_projects()["projects"]) == 3
    assert inspect_project(first.path).project == edited.project
    assert all(path.read_bytes() == original for path, original in sources.items())
    # Some pre-hardening local installations have owned 0755 state directories
    # and 0644 index files. Reading Saved Projects must safely tighten them
    # rather than incorrectly report a missing Recent Projects index.
    previous_index = index_path.read_bytes()
    state_path = state_directory()
    lock_path = state_path / "recents.lock"
    os.chmod(state_path, 0o755)
    os.chmod(index_path, 0o644)
    os.chmod(lock_path, 0o644)
    assert recent_projects()["projects"]
    assert state_path.stat().st_mode & 0o777 == 0o700
    assert index_path.stat().st_mode & 0o777 == 0o600
    assert lock_path.stat().st_mode & 0o777 == 0o600
    assert index_path.read_bytes() == previous_index

    # No automatic "repair" may follow a symlink or overwrite a foreign
    # index. The saved bytes remain untouched if a symlink appears.
    backup = state_path / "recents-preserved-backup.json"
    index_path.rename(backup)
    try:
        index_path.symlink_to(backup)
        try:
            recent_projects()
        except ProjectError as exc:
            assert "index is unavailable" in str(exc)
        else:
            raise AssertionError("Symlinked Recent Projects index was accepted")
        assert backup.read_bytes() == previous_index
    finally:
        index_path.unlink(missing_ok=True)
        backup.rename(index_path)
    assert recent_projects()["projects"]
    check_sample_index_metadata_does_not_decode_full_project()
    check_index_sample_read_outside_lock()
    check_one_time_owner_migration(base)
    check_migration_rewrites_frozen_snapshot_refs()
    check_compact_project_open()
    check_existing_workspace_lookup_does_not_take_writer_lock(base)
    check_title_collision_avoids_deep_metadata()
    check_recent_list_does_not_validate_sample_pdfs(root)
    check_project_metadata_cache_invalidation(root)
    check_home_list_uses_only_paper_records(root)
    check_shallow_home_does_not_load_deep_status(root)
    check_home_session_status_cache(root)
    check_paper_preflight_presence(root)
    check_pdf_verification_cache(root)
    print(
        "PASS sample discovery and independent copies, retained edits, collision safety, source immutability, API/CLI and unlimited recents"
    )


def main() -> None:
    with TemporaryDirectory() as temporary:
        base = Path(temporary)
        root = base / "projects"
        root.mkdir()
        root = root.resolve()
        with patch.dict(
            os.environ, {"SIGMA_PROJECTS_ROOT": str(root), "SIGMA_STATE_DIR": str(base / "state")}
        ):
            check(root, base)


if __name__ == "__main__":
    main()
