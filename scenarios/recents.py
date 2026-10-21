"""A11 stock catalog, explicit working copies and genuine four-item recents."""

import json
import os
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from fastapi.testclient import TestClient

from sigma.api import app
from sigma.projects import ROOT, ProjectError, create_project, inspect_project, open_project
from sigma.recents import home_projects, recent_projects, state_directory
from sigma.stock import create_stock_copy, stock_projects


def check(root: Path, base: Path) -> None:
    sources = {path: path.read_bytes() for path in (ROOT / "examples").glob("*/project.json")}
    catalog = stock_projects()["projects"]
    assert len(catalog) >= 2
    assert {entry["title"] for entry in catalog} >= {
        "Nonconsecutive Subset Sums Modulo 3",
        "Did Jesus Use Cannabis?",
    }
    assert {entry["research_mode"] for entry in catalog} >= {"default", "mathematical"}
    assert catalog[-1]["title"] == "Did Jesus Use Cannabis?"
    assert home_projects()["projects"] == [] and not list(root.iterdir())

    expanded = base / "extra-examples"
    expanded.mkdir()
    for number in range(6):
        location = expanded / f"sample-{number}"
        location.mkdir()
        (location / "project.json").write_bytes(next(iter(sources.values())))
    with patch("sigma.stock.EXAMPLES", expanded):
        assert len(stock_projects()["projects"]) == 6
    assert not list(root.iterdir())

    selected = next(item for item in catalog if item["research_mode"] == "mathematical")
    first = create_stock_copy(selected["id"], "My mathematical copy")
    second = create_stock_copy(selected["id"], "My mathematical copy again")
    source_path = ROOT / "examples" / selected["id"] / "project.json"
    assert first.project.id != second.project.id != json.loads(sources[source_path])["id"]
    assert first.project.research_mode == second.project.research_mode
    assert (
        len(first.project.strategies)
        == len(second.project.strategies)
        == selected["strategy_count"]
    )
    assert {item.id for item in first.project.strategies}.isdisjoint(
        {item.id for item in second.project.strategies}
    )
    assert inspect_project(first.path).project == first.project
    assert inspect_project(second.path).project == second.project
    assert [entry["id"] for entry in recent_projects()["projects"]] == [
        second.project.id,
        first.project.id,
    ]
    try:
        create_stock_copy(selected["id"], "My mathematical copy")
        raise AssertionError("A stock copy overwrote an existing project")
    except ProjectError as error:
        assert "already exists" in str(error)
    try:
        create_stock_copy("../../unknown", "Unsafe")
        raise AssertionError("An unknown stock identifier was accepted")
    except ProjectError:
        pass
    assert not (root / "unsafe.sigma").exists()

    legacy = root / "legacy.sigma"
    legacy.mkdir()
    (legacy / "project.json").write_bytes(source_path.read_bytes())
    assert len(recent_projects()["projects"]) == 2
    opened = open_project(legacy)
    assert opened.project.id not in {entry["id"] for entry in recent_projects()["projects"]}
    assert (legacy / "project.json").read_bytes() == sources[source_path]

    created = [create_project(f"User project {i}", "Own research") for i in range(5)]
    assert [entry["id"] for entry in recent_projects()["projects"]] == [
        view.project.id for view in reversed(created[-4:])
    ]
    open_project(first.path)
    assert recent_projects()["projects"][0]["id"] == first.project.id
    assert len(recent_projects()["projects"]) == 4

    with TestClient(app) as api:
        assert api.get("/api/projects/stock").json()["projects"] == catalog
        before = (state_directory() / "recents.json").read_bytes()
        assert len(api.get("/api/projects/recent").json()["projects"]) == 4
        assert (state_directory() / "recents.json").read_bytes() == before
        response = api.post(
            "/api/projects/stock/copy",
            json={"stock_id": selected["id"], "title": "API stock copy"},
        )
        assert response.status_code == 201
        assert response.json()["project"]["id"] != first.project.id
        assert (
            api.post(
                "/api/projects/stock/copy",
                json={"stock_id": selected["id"], "title": "API stock copy"},
            ).status_code
            == 400
        )
        assert (
            api.post(
                "/api/projects/recent/forget", json={"project_id": first.project.id}
            ).status_code
            == 200
        )
        assert first.project.id not in {entry["id"] for entry in recent_projects()["projects"]}
    command = subprocess.run(
        [str(ROOT / "sigma"), "create", "--title", "CLI recent", "--problem", "Own work"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert recent_projects()["projects"][0]["id"] == json.loads(command.stdout)["project"]["id"]

    # Old never-opened example entries disappear, while research stays on disk.
    index_path = state_directory() / "recents.json"
    index = json.loads(index_path.read_text())
    index["entries"] = [
        {
            "id": opened.project.id,
            "path": str(legacy),
            "accessed_at": None,
            "included_example": True,
        },
        *index["entries"][:3],
    ]
    index_path.write_text(json.dumps(index))
    assert all(not entry["included_example"] for entry in home_projects()["projects"])
    assert len(recent_projects()["projects"]) == 3
    assert legacy.exists() and (legacy / "project.json").read_bytes() == sources[source_path]
    assert all(path.read_bytes() == original for path, original in sources.items())
    print(
        "PASS unlimited stock discovery, no auto-seeding, independent copies, collisions, API/CLI, four-item LRU, legacy migration and source immutability"
    )


def main() -> None:
    with TemporaryDirectory() as temporary:
        base = Path(temporary)
        root = base / "projects"
        root.mkdir()
        with patch.dict(
            os.environ, {"SIGMA_PROJECTS_ROOT": str(root), "SIGMA_STATE_DIR": str(base / "state")}
        ):
            check(root, base)
        assert len(stock_projects()["projects"]) >= 2


if __name__ == "__main__":
    main()
