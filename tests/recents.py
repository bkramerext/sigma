"""Sample catalog copies, recent-project behavior, collision safety, and API/CLI access."""

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
from sigma.samples import open_sample_project, sample_projects


def check(root: Path, base: Path) -> None:
    sources = {path: path.read_bytes() for path in (ROOT / "samples").glob("*/project.json")}
    catalog = sample_projects()["projects"]
    assert len(catalog) >= 2
    assert {entry["title"] for entry in catalog} >= {
        "Nonconsecutive Subset Sums Modulo 3",
        "Did Jesus Use Cannabis?",
    }
    assert {entry["investigation_type"] for entry in catalog} >= {"default", "mathematical"}
    assert catalog[-1]["title"] == "Did Jesus Use Cannabis?"
    assert home_projects()["projects"] == [] and not list(root.iterdir())

    expanded = base / "extra-samples"
    expanded.mkdir()
    for number in range(6):
        location = expanded / f"sample-{number}"
        location.mkdir()
        (location / "project.json").write_bytes(next(iter(sources.values())))
    with patch("sigma.samples.SAMPLES", expanded):
        assert len(sample_projects()["projects"]) == 6
    assert not list(root.iterdir())

    selected = next(item for item in catalog if item["investigation_type"] == "mathematical")
    source_path = ROOT / "samples" / selected["id"] / "project.json"
    first = open_sample_project(selected["id"])
    assert first.path == str(root / f"{selected['id']}.sigma")
    assert first.project.id != json.loads(sources[source_path])["id"]
    assert first.project.title == f"{selected['title']}, v1"
    assert Path(first.path, "project.json").read_bytes() != sources[source_path]
    second = open_sample_project(selected["id"])
    assert second.path != first.path and second.project.id != first.project.id
    assert second.project.title == f"{selected['title']}, v2"
    assert len(list(root.glob("*.sigma"))) == 2
    assert [item["id"] for item in recent_projects()["projects"]] == [
        second.project.id,
        first.project.id,
    ]
    edited = create_strategy(first.path, "My addition", "Investigate this case")
    reopened = open_sample_project(selected["id"])
    assert reopened.project.id not in {first.project.id, second.project.id}
    assert len(reopened.project.active_order) == selected["strategy_count"]
    assert sample_projects()["projects"][0]["strategy_count"] == selected["strategy_count"]
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
    assert impostor.path == str(collision)
    additional = open_sample_project(selected["id"])
    assert additional.path != str(collision)
    assert inspect_project(collision).project == impostor.project
    collision.rename(root / "saved-impostor.sigma")
    moved.rename(collision)
    last_copy = open_sample_project(selected["id"])
    assert last_copy.project.id != edited.project.id

    created = [create_project(f"User project {i}", "Own research") for i in range(5)]
    actual = [entry["id"] for entry in recent_projects()["projects"]]
    expected = [view.project.id for view in reversed(created)] + [last_copy.project.id]
    assert actual == expected, (actual, expected)
    open_project(created[0].path)
    assert recent_projects()["projects"][0]["id"] == created[0].project.id
    assert len(recent_projects()["projects"]) == 6
    open_project(first.path)
    assert recent_projects()["projects"][0]["id"] == first.project.id

    with TestClient(app) as api:
        before = (state_directory() / "recents.json").read_bytes()
        assert len(api.get("/api/projects/recent").json()["projects"]) == 6
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
        *[entry for entry in index["entries"] if entry["id"] != first.project.id][:3],
    ]
    index_path.write_text(json.dumps(index))
    assert all(not entry["included_example"] for entry in home_projects()["projects"])
    assert len(recent_projects()["projects"]) == 3
    assert inspect_project(first.path).project == edited.project
    assert all(path.read_bytes() == original for path, original in sources.items())
    print(
        "PASS sample discovery and independent copies, retained edits, collision safety, source immutability, API/CLI and six-item LRU"
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
