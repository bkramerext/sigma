"""Sample catalog copies, recent-project behavior, collision safety, and API/CLI access."""

import fcntl
import hashlib
import json
import os
import subprocess
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
    inspect_project,
    open_project,
)
from sigma.recents import home_projects, recent_projects, state_directory
from sigma.samples import open_sample_project, sample_projects


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
    }
    sample_categories = {entry["title"]: entry["investigation_type"] for entry in catalog}
    assert sample_categories["Did Jesus Use Cannabis?"] == "religion"
    assert sample_categories["Operation Narrow Passage"] == "military"
    assert sample_categories["Warp Drive Feasibility"] == "engineering"
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
