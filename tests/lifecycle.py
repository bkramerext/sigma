"""Run with `uv run python tests/lifecycle.py`; offline, temporary projects."""

import json
from dataclasses import asdict
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from fastapi.testclient import TestClient

from sigma.api import app
from sigma.projects import (
    STATE,
    ProjectError,
    close_project,
    initialize_project,
    inspect_project,
    list_events,
    open_project,
)


def rejects(action, message: str) -> None:
    try:
        action()
    except ProjectError:
        return
    raise AssertionError(message)


def main() -> None:
    with TemporaryDirectory() as directory:
        root = Path(directory).resolve()
        seed = root / "rh.sigma"
        seed.mkdir()
        (seed / ".gitkeep").touch()
        with patch("sigma.projects.SEED", seed):
            first = open_project(seed)
            before = (seed / STATE).read_bytes()
            close_project()
            assert open_project(seed) == first
            assert inspect_project(seed) == first
            assert list_events(seed) == first.project.events
            assert (seed / STATE).read_bytes() == before
        assert first.project.title == "Riemann Hypothesis"
        assert [e.sequence for e in first.project.events] == [1]
        print("PASS seed initialization, close/reopen, identity, ordered immutable reads")

        created = initialize_project(root / "new.sigma", "New question", "Investigate it")
        assert inspect_project(created.path) == created
        rejects(lambda: initialize_project(seed, "Overwrite", "No"), "overwrote seed")
        assert (seed / STATE).read_bytes() == before
        occupied = root / "research.sigma"
        occupied.mkdir()
        (occupied / "notes.txt").write_text("irreplaceable research")
        rejects(lambda: initialize_project(occupied, "X", "Y"), "accepted nonempty directory")
        assert (occupied / "notes.txt").read_text() == "irreplaceable research"
        rejects(lambda: initialize_project(root / "bad", "X", "Y"), "accepted wrong suffix")
        rejects(lambda: initialize_project(root / "blank.sigma", " ", "Y"), "accepted blank")
        assert not (root / "blank.sigma").exists()
        rejects(lambda: open_project("\0.sigma"), "accepted null path")
        rejects(lambda: open_project(root / "missing.sigma"), "created missing project")
        assert not (root / "missing.sigma").exists()
        print("PASS explicit creation, invalid inputs, existing research protected")

        failed = root / "failed.sigma"
        with patch("sigma.projects.os.link", side_effect=OSError("simulated publication failure")):
            rejects(lambda: initialize_project(failed, "X", "Y"), "accepted publication failure")
        assert not failed.exists()
        with patch("sigma.projects.os.link", side_effect=FileExistsError("concurrent winner")):
            rejects(lambda: initialize_project(root / "race.sigma", "X", "Y"), "overwrote winner")
        assert not (root / "race.sigma").exists()
        print("PASS failed publication cleanup and no-replace collision handling")

        corrupt = root / "corrupt.sigma"
        corrupt.mkdir()
        invalid_documents = [
            "{broken",
            json.dumps({"schema_version": 999}),
            json.dumps({"schema_version": True}),
        ]
        original = asdict(first.project)
        for field, value in [
            ("id", "invalid"),
            ("title", ""),
            ("events", []),
            (
                "events",
                [
                    {
                        "sequence": 2,
                        "kind": "project.initialized",
                        "timestamp": "2026-01-01T00:00:00+00:00",
                    }
                ],
            ),
            ("events", [{"sequence": 1, "kind": "project.initialized", "timestamp": "not a date"}]),
        ]:
            invalid_documents.append(json.dumps({**original, field: value}))
        for raw in invalid_documents:
            (corrupt / STATE).write_text(raw)
            rejects(lambda: open_project(corrupt), "accepted corrupt project")
            assert (corrupt / STATE).read_text() == raw
        print("PASS malformed JSON, incompatible schema, metadata and event validation")

        with TestClient(app) as client:
            response = client.post("/api/projects/open", json={"path": str(seed)})
            assert response.status_code == 200, response.text
            assert response.json()["project"]["id"] == first.project.id
            assert (
                client.get("/api/projects/inspect", params={"path": str(seed)}).json()
                == response.json()
            )
            assert (
                client.get("/api/projects/events", params={"path": str(seed)}).json()["events"][0][
                    "sequence"
                ]
                == 1
            )
            assert client.post("/api/projects/close").json() == {"closed": True}
            assert client.post("/api/projects/open", json={"path": str(corrupt)}).status_code == 400
            assert client.post("/api/projects/open", json={}).status_code == 422
            assert (
                client.post(
                    "/api/projects/open",
                    json={"path": str(seed)},
                    headers={"Origin": "https://untrusted.example"},
                ).status_code
                == 403
            )
            assert (
                client.get(
                    "/api/projects/events",
                    params={"path": str(seed)},
                    headers={"Host": "untrusted.example"},
                ).status_code
                == 400
            )
            response = client.post(
                "/api/projects/init",
                json={
                    "path": str(root / "api.sigma"),
                    "title": "API project",
                    "problem": "Question",
                },
            )
            assert response.status_code == 201, response.text
            assert (
                inspect_project(root / "api.sigma").project.id == response.json()["project"]["id"]
            )
        assert (seed / STATE).read_bytes() == before
        print("PASS API open/inspect/events/close/init, errors, origin and host boundaries")
    print("All lifecycle scenarios passed.")


if __name__ == "__main__":
    main()
