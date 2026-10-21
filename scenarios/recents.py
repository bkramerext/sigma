"""Real application index, exclusive sample publication, concurrency and math sanity."""

import json
import os
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from fastapi.testclient import TestClient

from sigma.api import app
from sigma.projects import (
    ROOT,
    ProjectError,
    close_project,
    create_project,
    initialize_project,
    inspect_project,
    open_project,
    project_settings,
    update_project,
)
from sigma.recents import (
    EXAMPLE_ID,
    EXAMPLE_NAME,
    TEMPLATE,
    bootstrap_example,
    forget_recent,
    recent_projects,
    state_directory,
)


def entries():
    return recent_projects()["projects"]


def check(root):
    source = TEMPLATE.read_bytes()
    assert not bootstrap_example()
    example = root / EXAMPLE_NAME
    assert (example / "project.json").read_bytes() == source
    view = inspect_project(example)
    assert view.project.schema_version == 5 and view.project.id == EXAMPLE_ID
    assert len(view.project.strategies) == 3 and all(
        strategy.stage == "draft" and strategy.provenance is None
        for strategy in view.project.strategies
    )
    assert len(view.project.events) == 4 and list(view.project.active_order) == [
        strategy.id for strategy in view.project.strategies
    ]
    assert entries()[0]["included_example"] and entries()[0]["accessed_at"] is None
    before = (state_directory() / "recents.json").read_bytes()
    assert not bootstrap_example()
    inspect_project(example)
    close_project()
    assert (state_directory() / "recents.json").read_bytes() == before
    open_project(example)
    assert not entries()[0]["included_example"] and entries()[0]["accessed_at"]
    assert (example / "project.json").read_bytes() == source
    projects = [create_project(f"Recent {number}", f"Question {number}") for number in range(5)]
    assert [entry["id"] for entry in entries()] == [
        view.project.id for view in reversed(projects[1:])
    ]
    assert all(Path(view.path).exists() for view in projects)  # LRU never deletes research.
    open_project(projects[0].path)
    assert entries()[0]["id"] == projects[0].project.id and len(entries()) == 4
    before = (state_directory() / "recents.json").read_bytes()
    snapshot = project_settings(inspect_project(projects[0].path).project)
    renamed = update_project(
        projects[0].path,
        **{**asdict(snapshot), "title": "Renamed research"},
        expected=asdict(snapshot),
    )
    assert (
        entries()[0]["title"] == "Renamed research"
        and (state_directory() / "recents.json").read_bytes() == before
    )
    close_project()
    inspect_project(renamed.path)
    assert (state_directory() / "recents.json").read_bytes() == before
    moved = root / "moved.sigma"
    shutil.move(projects[0].path, moved)
    assert entries()[0]["available"] is False
    open_project(moved)
    assert (
        entries()[0]["path"] == str(moved.resolve())
        and sum(entry["id"] == renamed.project.id for entry in entries()) == 1
    )
    (moved / "project.json").write_text("corrupt")
    before = (state_directory() / "recents.json").read_bytes()
    assert not entries()[0]["available"]
    try:
        open_project(moved)
        raise AssertionError("Corrupt recent opened")
    except ProjectError:
        pass
    assert (state_directory() / "recents.json").read_bytes() == before
    forget_recent(renamed.project.id)
    assert renamed.project.id not in {entry["id"] for entry in entries()} and moved.exists()
    # Four fresh process writers retain all four UUIDs under the same index lock.
    paths = [root / f"parallel-{number}.sigma" for number in range(4)]
    views = [
        initialize_project(path, f"Parallel {number}", "Independent research")
        for number, path in enumerate(paths)
    ]
    processes = [
        subprocess.Popen(
            [
                sys.executable,
                "-c",
                "import sys; from sigma.projects import open_project; open_project(sys.argv[1])",
                str(path),
            ]
        )
        for path in paths
    ]
    assert all(process.wait(timeout=15) == 0 for process in processes)
    assert {entry["id"] for entry in entries()} == {view.project.id for view in views}
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(open_project, paths * 3))
    assert len(entries()) == 4 and len({entry["id"] for entry in entries()}) == 4
    # Reload/read titles never writes an index or complete project history.
    with TestClient(app) as api:
        listing = api.get("/api/projects/recent").json()
        assert len(listing["projects"]) == 4 and all(
            "strategies" not in entry for entry in listing["projects"]
        )
        before = (state_directory() / "recents.json").read_bytes()
        api.post("/api/projects/close")
        api.get("/api/projects/recent")
        assert (state_directory() / "recents.json").read_bytes() == before
        created = api.post(
            "/api/projects/create", json={"title": "API creation", "problem": "Create access"}
        )
        assert created.status_code == 201
        assert entries()[0]["id"] == created.json()["project"]["id"]
        assert (
            api.post(
                "/api/projects/recent/forget", json={"project_id": created.json()["project"]["id"]}
            ).status_code
            == 200
        )
    command = subprocess.run(
        [str(ROOT / "sigma"), "create", "--title", "CLI recent", "--problem", "Shared index"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert entries()[0]["id"] == json.loads(command.stdout)["project"]["id"]
    # Sample was evicted; deliberate deletion/forget never resurrects it.
    shutil.rmtree(example)
    forget_recent(EXAMPLE_ID)
    assert not bootstrap_example() and not example.exists()
    assert TEMPLATE.read_bytes() == source
    print(
        "PASS first/subsequent bootstrap, exact v5 seed/history, four-entry LRU, create/API/CLI/open tracking, read/close/no-op immutability, rename, moved/corrupt paths, forget/no reseed and real multiprocess/thread writers"
    )


def failures(base):
    for name in (
        "full",
        "collision",
        "bad-template",
        "failed-publication",
        "symlink",
        "bootstrap-race",
        "bad-index",
        "failed-index-write",
    ):
        area = base / name
        area.mkdir()
        root, state = area / "projects", area / "state"
        root.mkdir()
        with patch.dict(
            os.environ, {"SIGMA_PROJECTS_ROOT": str(root), "SIGMA_STATE_DIR": str(state)}
        ):
            if name == "full":
                views = [create_project(f"Real {number}", "Real access") for number in range(4)]
                assert not bootstrap_example()
                assert len(entries()) == 4 and {entry["id"] for entry in entries()} == {
                    view.project.id for view in views
                }
            elif name == "collision":
                destination = root / EXAMPLE_NAME
                view = initialize_project(destination, "User research", "Must retain")
                before = (destination / "project.json").read_bytes()
                assert bootstrap_example() and (destination / "project.json").read_bytes() == before
                assert inspect_project(destination).project.id == view.project.id
            elif name == "bad-template":
                invalid = area / "invalid.json"
                invalid.write_text('{"schema_version":99}')
                with patch("sigma.recents.TEMPLATE", invalid):
                    assert bootstrap_example()
                assert not (root / EXAMPLE_NAME).exists()
                assert not bootstrap_example()  # Transient template problem can be fixed.
            elif name == "failed-publication":
                with patch("sigma.recents.os.link", side_effect=OSError("fixture failure")):
                    assert bootstrap_example()
                assert not (root / EXAMPLE_NAME).exists()
                assert not bootstrap_example()
                # A second installation state preserves an already edited same-UUID copy.
                prior = project_settings(inspect_project(root / EXAMPLE_NAME).project)
                update_project(
                    root / EXAMPLE_NAME,
                    **{**asdict(prior), "title": "My evolved example"},
                    expected=asdict(prior),
                )
                document = (root / EXAMPLE_NAME / "project.json").read_bytes()
                with patch.dict(os.environ, {"SIGMA_STATE_DIR": str(area / "other-state")}):
                    assert not bootstrap_example()
                    assert entries()[0]["title"] == "My evolved example"
                    assert (root / EXAMPLE_NAME / "project.json").read_bytes() == document
            elif name == "bootstrap-race":
                with ThreadPoolExecutor(max_workers=6) as pool:
                    assert not any(pool.map(lambda _: bootstrap_example(), range(6)))
                assert len(entries()) == 1
                assert (root / EXAMPLE_NAME / "project.json").read_bytes() == TEMPLATE.read_bytes()
            elif name == "bad-index":
                state_directory()
                broken = state / "recents.json"
                broken.write_text("not an index")
                broken.chmod(0o600)
                view = create_project("Index failure", "Research must still save")
                assert (
                    Path(view.path).joinpath("project.json").exists()
                    and broken.read_text() == "not an index"
                )
                try:
                    recent_projects()
                    raise AssertionError("Corrupt index was silently replaced")
                except ProjectError:
                    pass
                broken.unlink()  # Disposable test fixture only.
            elif name == "failed-index-write":
                create_project("First", "First access")
                index = state / "recents.json"
                before = index.read_bytes()
                with patch(
                    "sigma.recents.os.replace", side_effect=OSError("fixture index write failure")
                ):
                    view = create_project(
                        "Second", "Already committed research must not report failure"
                    )
                assert (
                    Path(view.path).joinpath("project.json").exists()
                    and index.read_bytes() == before
                )
                open_project(view.path)
                assert entries()[0]["id"] == view.project.id
            else:
                unrelated = area / "unrelated"
                unrelated.mkdir()
                (unrelated / "keep").write_text("retain")
                (root / EXAMPLE_NAME).symlink_to(unrelated, target_is_directory=True)
                assert bootstrap_example() and (unrelated / "keep").read_text() == "retain"
            assert len(entries()) <= 4
            assert state.stat().st_mode & 0o777 == 0o700
            index = state / "recents.json"
            if index.exists():
                assert index.stat().st_mode & 0o777 == 0o600
    print(
        "PASS full genuine list retained, bad template, exclusive publication rollback, existing edited seed preservation, collision/symlink safety, root switching and private state"
    )


def main():
    with TemporaryDirectory() as temporary:
        base = Path(temporary)
        root = base / "projects"
        root.mkdir()
        with patch.dict(
            os.environ, {"SIGMA_PROJECTS_ROOT": str(root), "SIGMA_STATE_DIR": str(base / "state")}
        ):
            check(root)
        failures(base)
        with patch.dict(os.environ, {"XDG_STATE_HOME": str(ROOT / "frontend")}):
            os.environ.pop("SIGMA_STATE_DIR", None)
            try:
                state_directory()
                raise AssertionError("State inside checkout was accepted")
            except ProjectError:
                pass


if __name__ == "__main__":
    main()
