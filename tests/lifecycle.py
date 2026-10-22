"""Run with `uv run python tests/lifecycle.py`; offline, temporary investigations."""

import json
from dataclasses import asdict
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from fastapi.testclient import TestClient

from sigma.api import app
from sigma.investigations import (
    STATE,
    InvestigationError,
    close_investigation,
    initialize_investigation,
    inspect_investigation,
    investigation_path,
    investigation_settings,
    list_events,
    open_investigation,
    update_investigation,
)


def rejects(action, message: str) -> None:
    try:
        action()
    except InvestigationError:
        return
    raise AssertionError(message)


def main() -> None:
    with TemporaryDirectory() as directory:
        root = Path(directory).resolve()
        seed = root / "rh.sigma"
        seed.mkdir()
        (seed / ".gitkeep").touch()
        with patch("sigma.investigations.SEED", seed):
            first = open_investigation(seed)
            before = (seed / STATE).read_bytes()
            close_investigation()
            assert open_investigation(seed) == first
            assert inspect_investigation(seed) == first
            assert list_events(seed) == first.investigation.events
            assert (seed / STATE).read_bytes() == before
        assert first.investigation.title == "Riemann Hypothesis"
        assert [e.sequence for e in first.investigation.events] == [1]
        print("PASS seed initialization, close/reopen, identity, ordered immutable reads")

        created = initialize_investigation(root / "new.sigma", "New question", "Investigate it")
        assert inspect_investigation(created.path) == created
        rejects(lambda: initialize_investigation(seed, "Overwrite", "No"), "overwrote seed")
        assert (seed / STATE).read_bytes() == before
        occupied = root / "research.sigma"
        occupied.mkdir()
        (occupied / "notes.txt").write_text("irreplaceable research")
        rejects(lambda: initialize_investigation(occupied, "X", "Y"), "accepted nonempty directory")
        assert (occupied / "notes.txt").read_text() == "irreplaceable research"
        rejects(lambda: initialize_investigation(root / "bad", "X", "Y"), "accepted wrong suffix")
        rejects(lambda: initialize_investigation(root / "blank.sigma", " ", "Y"), "accepted blank")
        assert not (root / "blank.sigma").exists()
        rejects(lambda: open_investigation("\0.sigma"), "accepted null path")
        rejects(lambda: open_investigation(root / "missing.sigma"), "created missing investigation")
        assert not (root / "missing.sigma").exists()
        print("PASS explicit creation, invalid inputs, existing research protected")

        # A legacy project.json remains byte-for-byte readable until a real edit.
        legacy = root / "legacy.sigma"
        legacy.mkdir()
        seed_raw = json.loads(before)
        seed_raw["schema_version"] = 6
        seed_raw["events"][0]["kind"] = "project.initialized"
        legacy_bytes = json.dumps(seed_raw, indent=2).encode() + b"\n"
        (legacy / "project.json").write_bytes(legacy_bytes)
        legacy_view = inspect_investigation(legacy)
        assert legacy_view.investigation.id == first.investigation.id
        assert (legacy / "project.json").read_bytes() == legacy_bytes
        assert not (legacy / STATE).exists()
        settings = legacy_view.investigation
        migrated = update_investigation(
            legacy,
            settings.title + " revised",
            settings.problem,
            settings.investigation_type.value,
            settings.ai_model,
            settings.reasoning_effort,
            asdict(investigation_settings(settings)),
        )
        assert migrated.investigation.id == settings.id
        assert migrated.investigation.schema_version == 7
        assert migrated.investigation.events[0].kind == "project.initialized"
        assert (legacy / STATE).is_file() and not (legacy / "project.json").exists()
        assert (legacy / "investigation.v6.json").read_bytes() == legacy_bytes
        repeat = update_investigation(
            legacy,
            migrated.investigation.title,
            migrated.investigation.problem,
            migrated.investigation.investigation_type.value,
            migrated.investigation.ai_model,
            migrated.investigation.reasoning_effort,
            asdict(investigation_settings(migrated.investigation)),
        )
        assert repeat == migrated
        print("PASS read-only legacy load, first-write v7 migration, exact backup and idempotence")

        conflict = root / "conflict.sigma"
        conflict.mkdir()
        (conflict / STATE).write_bytes(b'{"new":true}')
        (conflict / "project.json").write_bytes(b'{"legacy":true}')
        rejects(lambda: inspect_investigation(conflict), "accepted conflicting state documents")
        assert (conflict / STATE).read_bytes() == b'{"new":true}'
        assert (conflict / "project.json").read_bytes() == b'{"legacy":true}'

        old_root = root / "projects"
        new_root = root / "investigations"
        moved = new_root / "rh.sigma"
        moved.mkdir(parents=True)
        with patch("sigma.investigations.ROOT", root):
            assert investigation_path(old_root / "rh.sigma") == moved.resolve()
        print(
            "PASS conflicting dual state is untouched; old checkout bookmarks resolve to moved seed"
        )

        failed = root / "failed.sigma"
        with patch(
            "sigma.investigations.os.link", side_effect=OSError("simulated publication failure")
        ):
            rejects(
                lambda: initialize_investigation(failed, "X", "Y"), "accepted publication failure"
            )
        assert not failed.exists()
        with patch(
            "sigma.investigations.os.link", side_effect=FileExistsError("concurrent winner")
        ):
            rejects(
                lambda: initialize_investigation(root / "race.sigma", "X", "Y"), "overwrote winner"
            )
        assert not (root / "race.sigma").exists()
        print("PASS failed publication cleanup and no-replace collision handling")

        corrupt = root / "corrupt.sigma"
        corrupt.mkdir()
        invalid_documents = [
            "{broken",
            json.dumps({"schema_version": 999}),
            json.dumps({"schema_version": True}),
        ]
        original = asdict(first.investigation)
        for field, value in [
            ("id", "invalid"),
            ("title", ""),
            ("events", []),
            (
                "events",
                [
                    {
                        "sequence": 2,
                        "kind": "investigation.initialized",
                        "timestamp": "2026-01-01T00:00:00+00:00",
                    }
                ],
            ),
            (
                "events",
                [{"sequence": 1, "kind": "investigation.initialized", "timestamp": "not a date"}],
            ),
        ]:
            invalid_documents.append(json.dumps({**original, field: value}))
        for raw in invalid_documents:
            (corrupt / STATE).write_text(raw)
            rejects(lambda: open_investigation(corrupt), "accepted corrupt investigation")
            assert (corrupt / STATE).read_text() == raw
        print("PASS malformed JSON, incompatible schema, metadata and event validation")

        with TestClient(app) as client:
            response = client.post("/api/investigations/open", json={"path": str(seed)})
            assert response.status_code == 200, response.text
            assert response.json()["investigation"]["id"] == first.investigation.id
            legacy_response = client.post("/api/projects/open", json={"path": str(seed)})
            assert legacy_response.status_code == 200
            assert legacy_response.json()["project"]["id"] == first.investigation.id
            assert legacy_response.json()["investigation"] == legacy_response.json()["project"]
            assert (
                client.get("/api/investigations/inspect", params={"path": str(seed)}).json()
                == response.json()
            )
            assert (
                client.get("/api/investigations/events", params={"path": str(seed)}).json()[
                    "events"
                ][0]["sequence"]
                == 1
            )
            assert client.post("/api/investigations/close").json() == {"closed": True}
            assert (
                client.post("/api/investigations/open", json={"path": str(corrupt)}).status_code
                == 400
            )
            assert client.post("/api/investigations/open", json={}).status_code == 422
            assert (
                client.post(
                    "/api/investigations/open",
                    json={"path": str(seed)},
                    headers={"Origin": "https://untrusted.example"},
                ).status_code
                == 403
            )
            assert (
                client.get(
                    "/api/investigations/events",
                    params={"path": str(seed)},
                    headers={"Host": "untrusted.example"},
                ).status_code
                == 400
            )
            response = client.post(
                "/api/investigations/init",
                json={
                    "path": str(root / "api.sigma"),
                    "title": "API investigation",
                    "problem": "Question",
                },
            )
            assert response.status_code == 201, response.text
            assert (
                inspect_investigation(root / "api.sigma").investigation.id
                == response.json()["investigation"]["id"]
            )
        assert (seed / STATE).read_bytes() == before
        print("PASS API open/inspect/events/close/init, errors, origin and host boundaries")
    print("All lifecycle scenarios passed.")


if __name__ == "__main__":
    main()
