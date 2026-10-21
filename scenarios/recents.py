"""A11 stock catalog, persistent direct opens, and genuine four-item recents."""

import json
import os
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from fastapi.testclient import TestClient

from sigma.api import app
from sigma.projects import (
    ROOT,
    ProjectError,
    create_project,
    create_strategy,
    inspect_project,
    open_project,
)
from sigma.recents import home_projects, recent_projects, state_directory
from sigma.stock import open_stock_project, stock_projects


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
    source_path = ROOT / "examples" / selected["id"] / "project.json"
    first = open_stock_project(selected["id"])
    assert first.path == str(root / f"{selected['id']}.sigma")
    assert first.project.id == json.loads(sources[source_path])["id"]
    assert Path(first.path, "project.json").read_bytes() == sources[source_path]
    assert open_stock_project(selected["id"]) == first
    assert len(list(root.iterdir())) == 1
    assert recent_projects()["projects"] == []
    edited = create_strategy(first.path, "My addition", "Investigate this case")
    reopened = open_stock_project(selected["id"])
    assert reopened.project == edited.project
    assert stock_projects()["projects"][0]["strategy_count"] == selected["strategy_count"] + 1
    assert recent_projects()["projects"] == []
    assert Path(first.path, "project.json").read_bytes() != sources[source_path]

    other = open_stock_project(catalog[-1]["id"])
    assert other.path != first.path and other.project.id != first.project.id
    assert len(list(root.iterdir())) == 2 and recent_projects()["projects"] == []
    try:
        open_stock_project("../../unknown")
        raise AssertionError("An unknown stock identifier was accepted")
    except ProjectError:
        pass

    collision = root / f"{selected['id']}.sigma"
    moved = root / "saved-stock.sigma"
    collision.rename(moved)
    impostor = create_project(selected["id"], "Different research")
    assert impostor.path == str(collision)
    try:
        open_stock_project(selected["id"])
        raise AssertionError("A different project was opened as stock")
    except ProjectError as error:
        assert "different project occupies" in str(error)
    assert inspect_project(collision).project == impostor.project
    collision.rename(root / "saved-impostor.sigma")
    moved.rename(collision)
    assert open_stock_project(selected["id"]).project == edited.project

    created = [create_project(f"User project {i}", "Own research") for i in range(5)]
    assert [entry["id"] for entry in recent_projects()["projects"]] == [
        view.project.id for view in reversed(created[-4:])
    ]
    open_project(created[0].path)
    assert recent_projects()["projects"][0]["id"] == created[0].project.id
    assert len(recent_projects()["projects"]) == 4
    open_project(first.path)
    assert all(entry["id"] != first.project.id for entry in recent_projects()["projects"])

    with TestClient(app) as api:
        before = (state_directory() / "recents.json").read_bytes()
        assert len(api.get("/api/projects/recent").json()["projects"]) == 4
        assert (state_directory() / "recents.json").read_bytes() == before
        assert api.get("/api/projects/stock").json()["projects"] == stock_projects()["projects"]
        response = api.post("/api/projects/stock/open", json={"stock_id": selected["id"]})
        assert response.status_code == 200
        assert response.json()["path"] == first.path
        assert len(list(root.glob(f"{selected['id']}.sigma"))) == 1
        assert api.post("/api/projects/stock/open", json={"stock_id": "unknown"}).status_code == 400
        assert (
            api.post("/api/projects/stock/copy", json={"stock_id": selected["id"]}).status_code
            == 404
        )
        assert (
            api.post(
                "/api/projects/recent/forget", json={"project_id": created[0].project.id}
            ).status_code
            == 200
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
    index = json.loads(index_path.read_text())
    index["entries"] = [
        {"id": first.project.id, "path": first.path, "accessed_at": None, "included_example": True},
        *index["entries"][:3],
    ]
    index_path.write_text(json.dumps(index))
    assert all(not entry["included_example"] for entry in home_projects()["projects"])
    assert len(recent_projects()["projects"]) == 3
    assert inspect_project(first.path).project == edited.project
    assert all(path.read_bytes() == original for path, original in sources.items())
    print(
        "PASS unlimited stock discovery, stable direct opens and retained edits, collision safety, source immutability, no stock recents, API/CLI and four-item LRU"
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
