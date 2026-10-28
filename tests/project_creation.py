"""Managed project creation, research modes, legacy reads and safe failure."""

import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

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
                assert created.project.schema_version == 9
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
                assert removed.project.schema_version == 9
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
                # Both the canonical export route and the legacy download
                # alias must return one complete, importable file bundle.
                legacy_download = client.get(
                    "/api/projects/download", params={"path": response.json()["path"]}
                )
                assert legacy_download.status_code == 200
                assert legacy_download.content == downloaded.content
                from sigma.project_bundle import read_bundle

                assert portable == read_bundle(response.json()["path"])
                imported_document = json.loads(
                    __import__("base64").b64decode(portable["files"]["project.json"])
                )
                imported_document["title"] = "API math imported"
                portable["files"]["project.json"] = (
                    __import__("base64")
                    .b64encode((json.dumps(imported_document) + "\n").encode())
                    .decode()
                )
                imported = client.post("/api/projects/import", json={"bundle": portable})
                assert imported.status_code == 201, imported.text
                assert Path(imported.json()["path"]).suffix == ".json"
                assert (
                    client.post("/api/projects/import", json={"bundle": portable}).status_code
                    == 400
                )
                assert inspect_project(imported.json()["path"]).project.title == "API math imported"
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
