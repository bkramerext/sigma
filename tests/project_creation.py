"""Managed project creation, research modes, legacy reads and safe failure."""

import hashlib
import json
import os
import subprocess
import sys
import zlib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from uuid import uuid4

import test_environment as _test_environment  # noqa: F401
from fastapi.testclient import TestClient

from sigma.api import app
from sigma.project_bundle import read_file
from sigma.projects import (
    ROOT,
    STATE,
    ProjectError,
    ResearchMode,
    create_project,
    create_strategy,
    edit_strategy,
    initialize_project,
    inspect_project,
    open_project,
    project_destination,
    projects_root,
    remove_strategy,
)


def rejects(action) -> None:
    try:
        action()
    except ProjectError:
        return
    raise AssertionError("Expected rejection")


def main() -> None:
    with TemporaryDirectory() as directory:
        root = Path(directory).resolve()
        managed = root / "managed"
        managed.mkdir()
        with patch.dict(os.environ, {"SIGMA_PROJECTS_ROOT": str(managed)}):
            assert project_destination().root == str(managed)
            for mode in ResearchMode:
                title = f"A {mode.value} investigation"
                expected = project_destination(title)
                assert expected.path and not expected.exists
                created = create_project(title, "A bounded question", mode)
                assert created.path == expected.path
                assert created.project.schema_version == 11
                assert created.project.difficulty is not None
                assert created.project.difficulty.value == "medium"
                assert created.project.research_mode == mode
                raw = json.loads(read_file(Path(created.path), STATE))
                assert raw["investigation_type"] == mode.value
                assert raw["show_advanced_outcome_details"] is False
                assert open_project(created.path) == created
                assert project_destination(title).exists
                # Strategy mutations retain mode and v4 without a downgrade.
                added = create_strategy(created.path, "Idea", "Approach")
                strategy_id = added.project.strategies[0].id
                edit_strategy(created.path, strategy_id, "Edited idea", "Updated approach")
                removed = remove_strategy(created.path, strategy_id)
                assert removed.project.research_mode == mode
                assert removed.project.schema_version == 11
                snapshot = Path(created.path).read_bytes()
                rejects(
                    lambda title=title, mode=mode: create_project(title, "Overwrite attempt", mode)
                )
                assert Path(created.path).read_bytes() == snapshot
            print(
                "PASS all research types serialized/reopened, destination preview, collision and strategy integrity"
            )

            existing = set(managed.iterdir())
            for title, problem, mode in (
                (" ", "Question", "default"),
                ("Name", "\n", "default"),
                ("Unknown", "Question", "astral"),
                ("x" * 201, "Q", "default"),
                ("Name", "x" * 20001, "default"),
                ("../escape", "Q", "default"),
                ("a/b", "Q", "default"),
                ("a\\b", "Q", "default"),
                ("..", "Q", "default"),
                ("a\0b", "Q", "default"),
                ("a\nb", "Q", "default"),
            ):
                rejects(
                    lambda title=title, problem=problem, mode=mode: create_project(
                        title, problem, mode
                    )
                )
            assert set(managed.iterdir()) == existing
            # Real Unicode names remain safe and deterministic.
            unicode_project = create_project("  Étude — Σ  ", "Question")
            assert Path(unicode_project.path).parent == managed
            assert project_destination("Étude — Σ").path == unicode_project.path
            long_unicode = project_destination("𐐀" * 200)
            assert long_unicode.path and len(Path(long_unicode.path).name.encode()) <= 255
            occupied = managed / "occupied.sigma"
            occupied.mkdir()
            notes = occupied / "notes.txt"
            notes.write_text("Irreplaceable notes")
            rejects(lambda: create_project("Occupied", "Question"))
            assert notes.read_text() == "Irreplaceable notes"
            broken = managed / "linked.sigma"
            broken.symlink_to(root / "does-not-exist")
            assert project_destination("Linked").exists
            rejects(lambda: create_project("Linked", "Question"))
            assert broken.is_symlink()
            print(
                "PASS name/problem/mode validation, Unicode slug, arbitrary files and symlink protection"
            )

            for operation in ("fsync", "link"):
                with patch(
                    f"sigma.projects.os.{operation}", side_effect=OSError("publication failed")
                ):
                    rejects(lambda: create_project("Failed publication", "Question"))
                assert not (managed / "failed-publication.json").exists()

            # If another local process inserts research into a reserved directory, never remove it.
            def inserted_research(path, *args):
                # Simulate another writer publishing research during initialization.
                # The mocked initializer must create its own destination because
                # create_project delegates directory creation to initialize_project.
                Path(path).write_text("Concurrent research")
                raise ProjectError("Initialization failed")

            with patch("sigma.projects.initialize_project", side_effect=inserted_research):
                rejects(lambda: create_project("Preserve partial", "Question"))
            assert (managed / "preserve-partial.json").read_text() == "Concurrent research"

            def competing_create(index):
                try:
                    return create_project("One reservation", f"Question {index}")
                except ProjectError:
                    return None

            with ThreadPoolExecutor(max_workers=4) as pool:
                results = list(pool.map(competing_create, range(8)))
            assert sum(result is not None for result in results) == 1
            winner = next(result for result in results if result is not None)
            assert inspect_project(winner.path) == winner
            print(
                "PASS publication rollback, concurrent data preservation and exclusive name reservation"
            )

            with TestClient(app) as client:
                preview = client.get("/api/projects/destination", params={"title": "API math"})
                assert preview.status_code == 200
                assert preview.json()["path"] == str(managed / "api-math.json")
                body = {
                    "title": "API math",
                    "problem": "A mathematical question",
                    "investigation_type": "mathematical",
                    "ai_model": None,
                    "reasoning_effort": "high",
                    "difficulty": "hard",
                    "show_advanced_outcome_details": True,
                }
                response = client.post("/api/projects/create", json=body)
                assert response.status_code == 201, response.text
                assert response.json()["project"]["investigation_type"] == "mathematical"
                assert response.json()["project"]["difficulty"] == "hard"
                assert response.json()["project"]["show_advanced_outcome_details"] is True
                assert inspect_project(
                    response.json()["path"]
                ).project.show_advanced_outcome_details
                chemistry = client.post(
                    "/api/projects/create",
                    json={
                        "title": "API chemistry",
                        "problem": "A chemistry question",
                        "research_mode": "chemistry",
                    },
                )
                assert chemistry.status_code == 201, chemistry.text
                assert chemistry.json()["project"]["investigation_type"] == "chemistry"
                assert chemistry.json()["project"]["difficulty"] == "medium"
                assert chemistry.json()["project"]["show_advanced_outcome_details"] is False
                # Full portable download and authenticated-workspace import.
                downloaded = client.get(
                    "/api/projects/export", params={"path": response.json()["path"]}
                )
                assert downloaded.status_code == 200, downloaded.text
                assert "attachment" in downloaded.headers["content-disposition"]
                portable = downloaded.json()
                assert portable["format"] == "sigma.project.bundle"
                assert portable["version"] == 3
                # Both the canonical export route and the legacy download
                # alias must return one complete, importable file bundle.
                legacy_download = client.get(
                    "/api/projects/download", params={"path": response.json()["path"]}
                )
                assert legacy_download.status_code == 200
                assert legacy_download.content == downloaded.content
                imported_document = portable["files"]["project.json"]
                imported_document["title"] = "API math imported v1"
                portable["files"]["project.json"] = imported_document
                imported = client.post("/api/projects/import", json={"bundle": portable})
                assert imported.status_code == 201, imported.text
                assert Path(imported.json()["path"]).suffix == ".json"
                duplicate_import = client.post("/api/projects/import", json={"bundle": portable})
                assert duplicate_import.status_code == 201, duplicate_import.text
                assert duplicate_import.json()["project"]["title"] == "API math imported v2"
                assert duplicate_import.json()["path"] != imported.json()["path"]
                assert (
                    inspect_project(imported.json()["path"]).project.title == "API math imported v1"
                )
                # An emailed bundle with project.updated history must import
                # under a versioned name without corrupting the source or audit trail.
                history_source = client.post(
                    "/api/projects/create",
                    json={
                        "title": "Email History Origin",
                        "problem": "Test an emailed project's rename history",
                        "investigation_type": "default",
                        "ai_model": None,
                        "reasoning_effort": "high",
                        "difficulty": "medium",
                        "show_advanced_outcome_details": False,
                    },
                )
                assert history_source.status_code == 201, history_source.text
                history_path = history_source.json()["path"]
                initial_project = history_source.json()["project"]
                settings_fields = (
                    "title",
                    "problem",
                    "investigation_type",
                    "ai_model",
                    "reasoning_effort",
                    "difficulty",
                    "show_advanced_outcome_details",
                )
                initial_settings = {key: initial_project[key] for key in settings_fields}
                renamed = client.post(
                    "/api/projects/update",
                    json={
                        "path": history_path,
                        **initial_settings,
                        "title": "Email History",
                        "expected": initial_settings,
                    },
                )
                assert renamed.status_code == 200, renamed.text
                assert renamed.json()["project"]["events"][-1]["kind"] == "project.updated"
                before_import = Path(history_path).read_bytes()
                mail_bundle = client.get(
                    "/api/projects/export", params={"path": history_path}
                ).json()
                for index in (1, 2):
                    mail_import = client.post("/api/projects/import", json={"bundle": mail_bundle})
                    assert mail_import.status_code == 201, mail_import.text
                    imported_title = f"Email History v{index}"
                    assert mail_import.json()["project"]["title"] == imported_title
                    imported_events = mail_import.json()["project"]["events"]
                    assert len(imported_events) == len(renamed.json()["project"]["events"]) + 1
                    assert imported_events[-1]["kind"] == "project.updated"
                    assert (
                        imported_events[-1]["project_change"]["previous"]["title"]
                        == "Email History"
                    )
                    assert (
                        imported_events[-1]["project_change"]["current"]["title"] == imported_title
                    )
                    assert (
                        inspect_project(mail_import.json()["path"]).project.title == imported_title
                    )
                assert Path(history_path).read_bytes() == before_import

                # Home discovery and Open Project must work for both original
                # and imported single-file projects, not only legacy directories.
                from sigma.projects import list_json_projects

                discovered = {view.path for view in list_json_projects()}
                assert response.json()["path"] in discovered
                assert imported.json()["path"] in discovered
                for project_path in (response.json()["path"], imported.json()["path"]):
                    reopened = client.post("/api/projects/open", json={"path": project_path})
                    assert reopened.status_code == 200, reopened.text
                    assert reopened.json()["path"] == project_path
                recents = client.get("/api/projects/recent")
                assert recents.status_code == 200, recents.text
                recent_paths = {item["path"] for item in recents.json()["projects"]}
                assert imported.json()["path"] in recent_paths

                # Every project-owned reference is rebased, not just the root ID.
                from sigma.agentic_evidence import _bundle_entries
                from sigma.project_bundle import list_files, update_files
                from sigma.python_sandbox import list_executions

                source_path = response.json()["path"]
                source_id = response.json()["project"]["id"]
                session_id = str(uuid4())
                run_id = uuid4().hex
                execution_id = str(uuid4())
                session_member = f"research-sessions/{session_id}.json"
                session = {
                    "id": session_id,
                    "project_id": source_id,
                    "project_path": source_path,
                    "session_number": 1,
                    "idempotency_key": str(uuid4()),
                    "cloud_sponsored": True,
                    "status": "paused",
                    "artifacts": [
                        {
                            "id": str(uuid4()),
                            "project_id": source_id,
                            "session_id": session_id,
                            "source_ref": f"project:{source_id}",
                        }
                    ],
                }
                run_member = f"evidence/agentic-runs/{run_id}.json"
                run = {
                    "schema_version": 1,
                    "project_id": source_id,
                    "run_id": run_id,
                    "started_at": "2026-11-04T16:00:00+00:00",
                    "steps": [{"session_id": session_id, "project_id": source_id}],
                }
                execution_member = f"research-executions/{execution_id}.json"
                execution = {
                    "id": execution_id,
                    "project_id": source_id,
                    "session_id": session_id,
                    "status": "completed",
                    "created_at": "2026-11-04T16:00:00+00:00",
                }
                attachment = b"%PDF-1.4\ncopied evidence\x00\xff"
                paper_id = uuid4().hex
                package = {
                    "schema": "sigma-paper-evidence-v2",
                    "project_id": source_id,
                    "sources": [
                        {"id": f"project:{source_id}", "kind": "project", "data": {"id": source_id}}
                    ],
                }
                snapshot_bytes = json.dumps(
                    package, ensure_ascii=False, sort_keys=True, separators=(",", ":")
                ).encode()
                digest = hashlib.sha256(snapshot_bytes).hexdigest()
                paper = {
                    "schema_version": 1,
                    "project_id": source_id,
                    "paper_id": paper_id,
                    "created_at": "2026-11-04T16:01:00+00:00",
                    "snapshot_sha256": digest,
                    "snapshot_ref": digest,
                    "draft": {"title": "Saved paper copy regression"},
                    "validation_warnings": [],
                    "generation": {},
                    "pdf_size_bytes": len(attachment),
                    "pdf_sha256": hashlib.sha256(attachment).hexdigest(),
                }
                qa_id = uuid4().hex
                qa_record = {
                    "qa_id": qa_id,
                    "request_id": uuid4().hex,
                    "project_id": source_id,
                    "question": "What did the investigation establish?",
                    "answer": "The research remains exploratory.",
                    "snapshot_sha256": hashlib.sha256(b"snapshot").hexdigest(),
                    "evidence_snapshot": [
                        {
                            "id": f"project:{source_id}",
                            "kind": "project",
                            "data": {"id": source_id},
                        }
                    ],
                    "sources": [
                        {
                            "source_id": f"project:{source_id}",
                            "kind": "project",
                            "session_number": None,
                        }
                    ],
                    "generation": {
                        "model": "gpt-6.1-sol",
                        "reasoning_effort": "high",
                        "mode": "test",
                        "generation_elapsed_seconds": 1,
                    },
                    "created_at": "2026-11-04T16:02:00+00:00",
                }
                qa_archive = {
                    "schema_version": 1,
                    "project_id": source_id,
                    "records": [qa_record],
                    "pending_requests": [
                        {
                            "request_id": uuid4().hex,
                            "question_sha256": hashlib.sha256(b"unsettled").hexdigest(),
                        }
                    ],
                }
                tex_bytes = (
                    b"\\\\documentclass{article}\\n\\\\begin{document}Proof\\\\end{document}\\n"
                )
                paper["paper_version"] = 1
                paper["tex_sha256"] = hashlib.sha256(tex_bytes).hexdigest()
                paper["tex_size_bytes"] = len(tex_bytes)
                second_id = uuid4().hex
                second_pdf = b"%PDF-1.7\\nindependent-second-paper\\x00\\xff"
                second_tex = b"\\\\documentclass{article}\\nSecond proof.\\n"
                second_paper = {
                    **paper,
                    "paper_id": second_id,
                    "paper_version": 2,
                    "created_at": "2026-11-04T15:01:00+00:00",
                    "draft": {"title": "Second preserved paper"},
                    "pdf_size_bytes": len(second_pdf),
                    "pdf_sha256": hashlib.sha256(second_pdf).hexdigest(),
                    "tex_sha256": hashlib.sha256(second_tex).hexdigest(),
                    "tex_size_bytes": len(second_tex),
                }
                update_files(
                    source_path,
                    {
                        session_member: json.dumps(session).encode(),
                        run_member: json.dumps(run).encode(),
                        execution_member: json.dumps(execution).encode(),
                        "papers/copy.pdf": attachment,
                        f"artifacts/papers/{paper_id}.json": json.dumps(paper).encode(),
                        f"artifacts/papers/{paper_id}.pdf": attachment,
                        f"artifacts/papers/{paper_id}.tex": tex_bytes,
                        f"artifacts/papers/{second_id}.json": json.dumps(second_paper).encode(),
                        f"artifacts/papers/{second_id}.pdf": second_pdf,
                        f"artifacts/papers/{second_id}.tex": second_tex,
                        f"artifacts/papers/snapshots/{digest}.json.zlib": zlib.compress(
                            snapshot_bytes
                        ),
                        "artifacts/research-qa/records.json": json.dumps(qa_archive).encode(),
                    },
                )
                from sigma import project_diagnostics, session_log

                event = {
                    "type": "test",
                    "project_id": source_id,
                    "session_id": session_id,
                    "message": "Saved diagnostic history",
                }
                session_log._append_sync(
                    source_path, session, event, session_log._root(Path(source_path))
                )
                project_diagnostics.append(
                    source_path,
                    stage="research",
                    code="save_as_history",
                    message="Audit the cloned project",
                    session_id=session_id,
                )
                source_log = session_log.log_path(source_path, source_id, session_id)
                original_log = source_log.read_bytes()
                before_copy = Path(source_path).read_bytes()
                # User-reported data loss: importing an export of this same project
                # must not displace the original in Saved Projects, and must keep
                # every PDF/TeX and frozen evidence attachment across paper versions.
                from sigma import papers

                full_export = client.get("/api/projects/export", params={"path": source_path})
                assert full_export.status_code == 200, full_export.text
                full_payload = full_export.json()
                first_import = client.post("/api/projects/import", json={"bundle": full_payload})
                assert first_import.status_code == 201, first_import.text
                imported_project = first_import.json()
                imported_path = imported_project["path"]
                imported_id = imported_project["project"]["id"]
                assert imported_path != source_path
                assert imported_id != source_id
                imported_papers = {item["paper_id"] for item in papers.list_papers(imported_path)}
                assert imported_papers == {paper_id, second_id}
                for identifier, pdf, tex in (
                    (paper_id, attachment, tex_bytes),
                    (second_id, second_pdf, second_tex),
                ):
                    assert papers.get_pdf(imported_path, identifier) == pdf
                    assert papers.paper_tex(imported_path, identifier).encode() == tex
                    archived = papers.get_paper(imported_path, identifier)
                    assert archived["project_id"] == imported_id
                    assert archived["snapshot"]["project_id"] == imported_id
                assert Path(source_path).read_bytes() == before_copy
                assert papers.get_pdf(source_path, paper_id) == attachment
                assert papers.paper_tex(source_path, paper_id).encode() == tex_bytes
                recent = client.get("/api/projects/recent")
                assert recent.status_code == 200
                recent_paths = {item["path"] for item in recent.json()["projects"]}
                assert {source_path, imported_path} <= recent_paths
                repeat = client.post("/api/projects/import", json={"bundle": full_payload})
                assert repeat.status_code == 201, repeat.text
                assert repeat.json()["project"]["id"] not in {source_id, imported_id}
                assert Path(source_path).read_bytes() == before_copy

                # Incomplete paper transfers must reject publication, never
                # succeed with an empty Papers view.
                incomplete = json.loads(json.dumps(full_payload))
                incomplete["files"].pop(f"artifacts/papers/{paper_id}.pdf")
                existing_json = {item.name for item in managed.glob("*.json")}
                rejected = client.post("/api/projects/import", json={"bundle": incomplete})
                assert rejected.status_code != 201, rejected.text
                assert {item.name for item in managed.glob("*.json")} == existing_json
                assert Path(source_path).read_bytes() == before_copy

                # Legacy .sigma projects use papers/<id> and
                # papers/.snapshots/<sha>. Import must preserve all their
                # records and map them to the single-file artifact namespace.
                legacy_path = managed / "legacy-with-paper-artifacts.sigma"
                legacy_view = initialize_project(
                    legacy_path, "Legacy with paper artifacts", "A historical proof"
                )
                legacy_id = legacy_view.project.id
                legacy_paper_id = uuid4().hex
                legacy_pdf = b"%PDF-1.7\\nlegacy-paper\\x00\\xff"
                legacy_tex = b"\\\\documentclass{article}\\nLegacy proof.\\n"
                legacy_snapshot = {
                    "schema": "sigma-paper-evidence-v2",
                    "project_id": legacy_id,
                    "sources": [
                        {"id": f"project:{legacy_id}", "kind": "project", "data": {"id": legacy_id}}
                    ],
                }
                legacy_snapshot_bytes = json.dumps(
                    legacy_snapshot, sort_keys=True, separators=(",", ":")
                ).encode()
                legacy_digest = hashlib.sha256(legacy_snapshot_bytes).hexdigest()
                legacy_record = {
                    "project_id": legacy_id,
                    "paper_id": legacy_paper_id,
                    "paper_version": 1,
                    "created_at": "2026-11-04T16:01:00+00:00",
                    "snapshot_sha256": legacy_digest,
                    "snapshot_ref": legacy_digest,
                    "draft": {"title": "Legacy preserved paper"},
                    "validation_warnings": [],
                    "generation": {},
                    "pdf_size_bytes": len(legacy_pdf),
                    "pdf_sha256": hashlib.sha256(legacy_pdf).hexdigest(),
                    "tex_size_bytes": len(legacy_tex),
                    "tex_sha256": hashlib.sha256(legacy_tex).hexdigest(),
                }
                legacy_papers_dir = legacy_path / "papers"
                legacy_papers_dir.mkdir()
                (legacy_papers_dir / f"{legacy_paper_id}.json").write_text(
                    json.dumps(legacy_record)
                )
                (legacy_papers_dir / f"{legacy_paper_id}.pdf").write_bytes(legacy_pdf)
                (legacy_papers_dir / f"{legacy_paper_id}.tex").write_bytes(legacy_tex)
                frozen_dir = legacy_papers_dir / ".snapshots"
                frozen_dir.mkdir()
                (frozen_dir / f"{legacy_digest}.json.zlib").write_bytes(
                    zlib.compress(legacy_snapshot_bytes)
                )
                assert (
                    client.post("/api/projects/open", json={"path": str(legacy_path)}).status_code
                    == 200
                )
                legacy_bundle = client.get(
                    "/api/projects/export", params={"path": str(legacy_path)}
                )
                assert legacy_bundle.status_code == 200, legacy_bundle.text
                legacy_imported = client.post(
                    "/api/projects/import", json={"bundle": legacy_bundle.json()}
                )
                assert legacy_imported.status_code == 201, legacy_imported.text
                imported_legacy_path = legacy_imported.json()["path"]
                assert imported_legacy_path != str(legacy_path)
                assert legacy_imported.json()["project"]["id"] != legacy_id
                assert {item["paper_id"] for item in papers.list_papers(imported_legacy_path)} == {
                    legacy_paper_id
                }
                assert papers.get_pdf(imported_legacy_path, legacy_paper_id) == legacy_pdf
                assert (
                    papers.paper_tex(imported_legacy_path, legacy_paper_id).encode() == legacy_tex
                )
                assert (
                    papers.get_paper(imported_legacy_path, legacy_paper_id)["snapshot"][
                        "project_id"
                    ]
                    == legacy_imported.json()["project"]["id"]
                )
                assert (legacy_papers_dir / f"{legacy_paper_id}.pdf").read_bytes() == legacy_pdf
                assert (legacy_papers_dir / f"{legacy_paper_id}.tex").read_bytes() == legacy_tex
                recent = client.get("/api/projects/recent")
                assert recent.status_code == 200
                recent_paths = {item["path"] for item in recent.json()["projects"]}
                assert {str(legacy_path), imported_legacy_path} <= recent_paths

                saved_as = client.post(
                    "/api/projects/save-as",
                    json={"path": source_path, "title": "API math v2"},
                )
                assert saved_as.status_code == 201, saved_as.text
                clone = saved_as.json()
                assert clone["project"]["title"] == "API math v2"
                assert clone["project"]["id"] != source_id
                assert clone["path"] != source_path
                assert inspect_project(clone["path"]).project.title == "API math v2"
                assert len(clone["project"]["events"]) == (
                    len(response.json()["project"]["events"]) + 1
                )
                assert clone["project"]["events"][-1]["kind"] == "project.updated"
                assert read_file(clone["path"], "artifacts/papers/copy.pdf") == attachment
                from sigma import papers, research_qa

                saved_paper = papers.get_paper(clone["path"], paper_id)
                assert saved_paper["project_id"] == clone["project"]["id"]
                assert saved_paper["snapshot"]["project_id"] == clone["project"]["id"]
                assert saved_paper["snapshot_sha256"] != digest
                assert saved_paper["pdf_available"]
                assert papers.list_papers(clone["path"])[0]["paper_id"] == paper_id
                saved_archive, _pending = research_qa._decode_archive(
                    clone["path"],
                    read_file(clone["path"], "artifacts/research-qa/records.json"),
                )
                assert _pending == []
                assert saved_archive[0]["qa_id"] == qa_id
                assert saved_archive[0]["source_snapshot_sha256"] == qa_record["snapshot_sha256"]
                assert saved_archive[0]["snapshot_derivation"] == (
                    "save_as_rebased_selected_sources_v1"
                )
                derivative = {
                    "schema": "sigma.qa.rebased-selected-sources-v1",
                    "project_id": clone["project"]["id"],
                    "evidence_snapshot": saved_archive[0]["evidence_snapshot"],
                }
                assert (
                    saved_archive[0]["snapshot_sha256"]
                    == hashlib.sha256(
                        json.dumps(
                            derivative, ensure_ascii=False, sort_keys=True, separators=(",", ":")
                        ).encode()
                    ).hexdigest()
                )
                assert saved_archive[0]["project_id"] == clone["project"]["id"]
                assert saved_archive[0]["sources"][0]["source_id"] == (
                    f"project:{clone['project']['id']}"
                )
                session_members = [
                    name
                    for name in list_files(clone["path"])
                    if name.startswith("research-sessions/")
                    and name.endswith(".json")
                    and Path(name).stem
                    not in {
                        "limits",
                        "sequence",
                        "obligation-ids",
                    }
                ]
                assert len(session_members) == 1
                assert session_members[0] != session_member
                copied_session = json.loads(read_file(clone["path"], session_members[0]))
                assert copied_session["project_id"] == clone["project"]["id"]
                assert copied_session["project_path"] == clone["path"]
                assert copied_session["id"] != session_id
                assert copied_session["idempotency_key"] != session["idempotency_key"]
                assert copied_session["cloud_sponsored"] is True
                cloned_log = session_log.log_path(
                    clone["path"], clone["project"]["id"], copied_session["id"]
                )
                assert cloned_log.is_file()
                copied_events, _ = session_log._frames(cloned_log)
                assert copied_events[0]["project_id"] == clone["project"]["id"]
                assert copied_events[0]["session_id"] == copied_session["id"]
                assert source_log.read_bytes() == original_log
                saved_diagnostics = project_diagnostics.read(clone["path"])
                assert len(saved_diagnostics) == 1
                assert saved_diagnostics[0]["project_id"] == clone["project"]["id"]
                assert saved_diagnostics[0]["session_id"] == copied_session["id"]
                # Clones can themselves be copied without reusing admission
                # keys, losing audit history or altering source provenance.
                twice = client.post(
                    "/api/projects/save-as",
                    json={"path": clone["path"], "title": "API math v3"},
                )
                assert twice.status_code == 201, twice.text
                third = twice.json()
                twice_sessions = [
                    member
                    for member in list_files(third["path"])
                    if member.startswith("research-sessions/")
                    and member.endswith(".json")
                    and Path(member).stem not in {"limits", "sequence", "obligation-ids"}
                ]
                assert len(twice_sessions) == 1
                twice_session = json.loads(read_file(third["path"], twice_sessions[0]))
                assert twice_session["id"] != copied_session["id"]
                assert twice_session["idempotency_key"] != copied_session["idempotency_key"]
                twice_log = session_log.log_path(
                    third["path"], third["project"]["id"], twice_session["id"]
                )
                assert twice_log.is_file()
                assert session_log._frames(twice_log)[0][0]["session_id"] == twice_session["id"]
                assert (
                    project_diagnostics.read(third["path"])[0]["session_id"] == twice_session["id"]
                )
                twice_answers = json.loads(
                    read_file(third["path"], "artifacts/research-qa/records.json")
                )
                assert (
                    twice_answers["records"][0]["source_snapshot_sha256"]
                    == (qa_record["snapshot_sha256"])
                )
                assert copied_session["artifacts"][0]["session_id"] == copied_session["id"]
                assert copied_session["artifacts"][0]["project_id"] == clone["project"]["id"]
                assert copied_session["artifacts"][0]["source_ref"] == (
                    f"project:{clone['project']['id']}"
                )
                assert list_executions(clone["path"])[0]["session_id"] == copied_session["id"]
                assert len(_bundle_entries(Path(clone["path"]), clone["project"]["id"])) == 1
                assert (
                    _bundle_entries(Path(clone["path"]), clone["project"]["id"])[0][2]["steps"][0][
                        "session_id"
                    ]
                    == copied_session["id"]
                )
                assert Path(source_path).read_bytes() == before_copy
                assert json.loads(read_file(source_path, session_member)) == session
                for member in list_files(clone["path"]):
                    if member.endswith(".json"):
                        assert source_id not in read_file(clone["path"], member).decode(), member
                assert (
                    client.post(
                        "/api/projects/save-as",
                        json={"path": source_path, "title": "API math v2"},
                    ).status_code
                    == 400
                )
                assert (
                    client.post(
                        "/api/projects/save-as",
                        json={"path": source_path, "title": "../unsafe"},
                    ).status_code
                    == 400
                )
                assert (
                    client.post(
                        "/api/projects/save-as",
                        json={
                            "path": source_path,
                            "title": "Not allowed",
                            "unexpected": True,
                        },
                    ).status_code
                    == 422
                )
                running = {**session, "status": "running"}
                update_files(source_path, {session_member: json.dumps(running).encode()})
                active_copy = client.post(
                    "/api/projects/save-as",
                    json={"path": source_path, "title": "Not an active copy"},
                )
                assert active_copy.status_code == 400
                assert "Stop active research" in active_copy.json()["error"]
                assert not (managed / "not-an-active-copy.json").exists()
                update_files(
                    source_path,
                    {
                        session_member: None,
                        run_member: None,
                        execution_member: None,
                        "papers/copy.pdf": None,
                        f"artifacts/papers/{paper_id}.json": None,
                        f"artifacts/papers/{paper_id}.pdf": None,
                        f"artifacts/papers/snapshots/{digest}.json.zlib": None,
                        "artifacts/research-qa/records.json": None,
                    },
                )
                print(
                    "PASS Save As full identity cascade, execution and agentic evidence, "
                    "source preservation and validation"
                )

                # Concurrent Save As calls must publish exactly one destination.
                from sigma.projects import save_project_as

                def competing_save_as(_index):
                    try:
                        return save_project_as(source_path, "API math concurrent copy")
                    except ProjectError:
                        return None

                with ThreadPoolExecutor(max_workers=4) as pool:
                    copies = list(pool.map(competing_save_as, range(4)))
                assert sum(item is not None for item in copies) == 1
                assert inspect_project(next(item.path for item in copies if item is not None))

                # Exercise a genuine legacy research project with saved
                # paper PDF/metadata, Q/A citations and session history.
                from sigma import papers, research_qa
                from sigma.project_bundle import list_files

                legacy_fixture = ROOT / "projects/complete/xenopus-tadpoles.sigma"
                legacy_id = inspect_project(legacy_fixture).project.id
                original_papers = papers.list_papers(str(legacy_fixture))
                original_answers = research_qa.list_answers(str(legacy_fixture))
                assert original_papers, "The real-paper fixture is missing its papers"
                assert original_answers, "The real-Q/A fixture is missing its answers"
                source_session_ids = {
                    item.stem
                    for item in (legacy_fixture / "research-sessions").glob("*.json")
                    if item.stem not in {"limits", "sequence", "obligation-ids"}
                }
                legacy_copy = save_project_as(
                    legacy_fixture, "Xenopus Saved Project Copy Regression"
                )
                assert legacy_copy.project.id != legacy_id
                assert legacy_copy.path.endswith(".json")
                copied_papers = papers.list_papers(legacy_copy.path)
                copied_answers = research_qa.list_answers(legacy_copy.path)
                assert {row["paper_id"] for row in copied_papers} == {
                    row["paper_id"] for row in original_papers
                }
                assert {row["qa_id"] for row in copied_answers} == {
                    row["qa_id"] for row in original_answers
                }
                for paper in copied_papers:
                    detail = papers.get_paper(legacy_copy.path, paper["paper_id"])
                    assert detail["project_id"] == legacy_copy.project.id
                    assert detail["pdf_available"], paper["paper_id"]
                for answer in copied_answers:
                    assert answer["project_id"] == legacy_copy.project.id
                    for citation in answer["sources"]:
                        assert legacy_id not in citation["source_id"]
                copied_session_ids = {
                    Path(name).stem
                    for name in list_files(legacy_copy.path)
                    if name.startswith("research-sessions/")
                    and name.endswith(".json")
                    and Path(name).stem not in {"limits", "sequence", "obligation-ids"}
                }
                assert len(copied_session_ids) == len(source_session_ids)
                assert not (copied_session_ids & source_session_ids)
                for member in list_files(legacy_copy.path):
                    if member.endswith(".json"):
                        assert legacy_id not in read_file(legacy_copy.path, member).decode(), member
                assert inspect_project(legacy_fixture).project.id == legacy_id
                assert papers.list_papers(str(legacy_fixture)) == original_papers
                assert len(research_qa.list_answers(str(legacy_fixture))) == len(original_answers)
                print("PASS legacy Save As real paper PDFs, Q/A, citation and session integrity")

                assert client.post("/api/projects/create", json=body).status_code == 400
                assert (
                    client.post(
                        "/api/projects/create", json={**body, "investigation_type": "invalid"}
                    ).status_code
                    == 400
                )
                assert (
                    client.post(
                        "/api/projects/create",
                        json={**body, "title": "Bad difficulty", "difficulty": "trivial"},
                    ).status_code
                    == 400
                )
                assert (
                    client.post(
                        "/api/projects/create", json={**body, "path": str(root / "escaped.sigma")}
                    ).status_code
                    == 422
                )
                assert not (root / "escaped.sigma").exists()
                assert (
                    client.post("/api/projects/create", json={"title": "Incomplete"}).status_code
                    == 422
                )
                assert (
                    client.get("/api/projects/destination", params={"title": "../bad"}).status_code
                    == 400
                )
            environment = {**os.environ, "SIGMA_PROJECTS_ROOT": str(managed)}
            for mode in ResearchMode:
                result = subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "sigma.cli",
                        "create",
                        "--title",
                        f"CLI {mode.value}",
                        "--problem",
                        "CLI question",
                        "--research-mode",
                        mode.value,
                        "--difficulty",
                        "hard",
                    ],
                    env=environment,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                assert result.returncode == 0, result.stderr
                data = json.loads(result.stdout)
                assert data["project"]["investigation_type"] == mode.value
                assert data["project"]["difficulty"] == "hard"
                assert inspect_project(data["path"]).project.research_mode == mode
            print("PASS API create/preview/errors and both CLI research modes")

        for version in (1, 2, 3):
            legacy = root / f"v{version}.sigma"
            initialize_project(legacy, "Legacy", "Keep its history")
            if version >= 2:
                created = create_strategy(legacy, "An idea", "An approach")
                if version == 3:
                    edit_strategy(
                        legacy, created.project.strategies[0].id, "Edited", "Preserve earlier text"
                    )
            raw = json.loads((legacy / STATE).read_bytes())
            raw["schema_version"] = version
            raw.pop("active_order", None)
            raw.pop("difficulty", None)
            raw.pop("show_advanced_outcome_details", None)
            for item in raw.get("strategies", []):
                for key in ("stage", "summary", "provenance"):
                    item.pop(key, None)
                item.pop("enabled", None)
            raw.pop("ai_model", None)
            raw.pop("reasoning_effort", None)
            raw.pop("research_mode", None)
            raw.pop("investigation_type", None)
            if version == 1:
                del raw["strategies"]
            elif version == 2:
                for item in raw["strategies"]:
                    del item["removed_at"]
            (legacy / STATE).write_text(json.dumps(raw))
            before = (legacy / STATE).read_bytes()
            view = open_project(legacy)
            assert view.project.research_mode == ResearchMode.DEFAULT
            assert (legacy / STATE).read_bytes() == before
            updated = create_strategy(legacy, "Another", "Independent approach")
            assert updated.project.research_mode == ResearchMode.DEFAULT
            assert updated.project.events[: len(view.project.events)] == view.project.events
        print("PASS v1/v2/v3 default-mode reads without rewriting and retained history on writes")

        for configured in (
            "relative",
            str(root / "missing"),
            str(managed / "api-math.sigma/project.json"),
        ):
            with patch.dict(os.environ, {"SIGMA_PROJECTS_ROOT": configured}):
                rejects(lambda: create_project("Wrong location", "Question"))
        linked_root = root / "root-link"
        linked_root.symlink_to(managed)
        with patch.dict(os.environ, {"SIGMA_PROJECTS_ROOT": str(linked_root)}):
            rejects(projects_root)
        with (
            patch.dict(os.environ, {"SIGMA_PROJECTS_ROOT": str(managed)}),
            patch("sigma.projects.os.geteuid", return_value=-1),
        ):
            rejects(projects_root)
        assert not (root / "missing").exists()
        with patch.dict(os.environ):
            os.environ.pop("SIGMA_PROJECTS_ROOT", None)
            assert projects_root() == (ROOT / "projects").resolve()
        print(
            "PASS explicit default/configured roots, missing parents, ownership and root symlinks"
        )
    print("All project-creation scenarios passed.")


if __name__ == "__main__":
    main()
