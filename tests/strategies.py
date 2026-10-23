"""Manual strategy persistence, legacy migration, concurrent writes and safe failure."""

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import test_environment as _test_environment  # noqa: F401
from fastapi.testclient import TestClient

from sigma import projects
from sigma.api import app
from sigma.projects import (
    STATE,
    ProjectError,
    create_strategy,
    initialize_project,
    inspect_project,
    list_strategies,
    open_project,
)


def rejects(action) -> None:
    try:
        action()
    except ProjectError:
        return
    raise AssertionError("Expected safe rejection")


def legacy(path: Path) -> bytes:
    initialize_project(path, "Legacy research", "Preserve existing work")
    raw = json.loads((path / STATE).read_bytes())
    raw["schema_version"] = 1
    del raw["strategies"]
    raw.pop("research_mode", None)
    raw.pop("investigation_type", None)
    for key in ("ai_model", "reasoning_effort", "active_order"):
        raw.pop(key, None)
    raw.pop("difficulty", None)
    contents = (json.dumps(raw, indent=2) + "\n").encode()
    (path / STATE).write_bytes(contents)
    return contents


def main() -> None:
    with TemporaryDirectory() as directory:
        root = Path(directory)
        path = root / "legacy.sigma"
        before = legacy(path)
        initial = inspect_project(path)
        assert initial.project.schema_version == 1
        assert not list_strategies(path)
        assert open_project(path) == initial
        assert (path / STATE).read_bytes() == before
        assert not (path / "project.v1.json").exists()
        updated = create_strategy(
            path,
            "  A manual idea  ",
            "  Examine a mathematical approach.\nKeep uncertainty explicit.  ",
        )
        strategy = updated.project.strategies[0]
        assert strategy.title == "A manual idea" and strategy.approach.startswith("Examine")
        assert strategy.author_kind == "human"
        assert updated.project.schema_version == 2
        assert updated.project.id == initial.project.id
        assert updated.project.events[0] == initial.project.events[0]
        assert updated.project.events[1].strategy_id == strategy.id
        assert updated.project.events[1].timestamp == strategy.created_at
        assert (path / "project.v1.json").read_bytes() == before
        assert open_project(path) == updated
        assert inspect_project(path) == updated
        print(
            "PASS read-only v1 access, first-save migration, exact backup, stable identity/history"
        )

        snapshot = (path / STATE).read_bytes()
        for title, approach in (
            (" ", "Text"),
            ("Title", "\n"),
            ("x" * 201, "Text"),
            ("Title", "x" * 10001),
        ):
            rejects(lambda title=title, approach=approach: create_strategy(path, title, approach))
            assert (path / STATE).read_bytes() == snapshot
        with patch("sigma.projects.os.replace", side_effect=OSError("disk failure")):
            rejects(lambda: create_strategy(path, "Failure", "Keep the original"))
        assert (path / STATE).read_bytes() == snapshot
        assert not list(path.glob(".sigma-write-*"))
        with patch("sigma.projects.os.fsync", side_effect=OSError("flush failure")):
            rejects(lambda: create_strategy(path, "Failure", "Keep the original"))
        assert (path / STATE).read_bytes() == snapshot
        assert not list(path.glob(".sigma-write-*"))
        print("PASS validation, failed replacement/flush, unchanged state and staging cleanup")

        failed = root / "failed-migration.sigma"
        legacy_bytes = legacy(failed)
        with patch("sigma.projects.os.replace", side_effect=OSError("disk failure")):
            rejects(lambda: create_strategy(failed, "Idea", "Approach"))
        assert (failed / STATE).read_bytes() == legacy_bytes
        assert (failed / "project.v1.json").read_bytes() == legacy_bytes
        assert create_strategy(failed, "Retry", "Approach").project.schema_version == 2
        conflict = root / "backup-conflict.sigma"
        legacy_bytes = legacy(conflict)
        (conflict / "project.v1.json").write_text("existing backup")
        rejects(lambda: create_strategy(conflict, "Idea", "Approach"))
        assert (conflict / STATE).read_bytes() == legacy_bytes
        assert (conflict / "project.v1.json").read_text() == "existing backup"
        print("PASS failed migration retry and existing backup protection")

        link_failure = root / "backup-link-failure.sigma"
        original = legacy(link_failure)
        with patch("sigma.projects.os.link", side_effect=OSError("backup link failed")):
            rejects(lambda: create_strategy(link_failure, "Idea", "Approach"))
        assert (link_failure / STATE).read_bytes() == original
        assert not list(link_failure.glob(".sigma-write-*"))
        external = root / "external.sigma"
        initialize_project(external, "Existing work", "Original objective")
        changed = json.loads((external / STATE).read_bytes())
        changed["problem"] = "A human edited this while the save was staged"
        changed_bytes = json.dumps(changed).encode()
        stage = projects._stage

        def external_edit(path: Path, contents: bytes) -> Path:
            staged = stage(path, contents)
            (path / STATE).write_bytes(changed_bytes)
            return staged

        with patch("sigma.projects._stage", side_effect=external_edit):
            rejects(lambda: create_strategy(external, "Idea", "Approach"))
        assert (external / STATE).read_bytes() == changed_bytes
        assert not list(external.glob(".sigma-write-*"))
        lock_symlink = root / "lock-symlink.sigma"
        initialize_project(lock_symlink, "Existing work", "Protect unrelated files")
        unrelated = root / "notes.txt"
        unrelated.write_text("Research notes")
        (lock_symlink / ".write.lock").symlink_to(unrelated)
        rejects(lambda: create_strategy(lock_symlink, "Idea", "Approach"))
        assert unrelated.read_text() == "Research notes"
        assert not list_strategies(lock_symlink)
        rejects(lambda: create_strategy(root / "missing.sigma", "Idea", "Approach"))
        assert not (root / "missing.sigma").exists()
        print(
            "PASS backup failure, external-edit conflict, unsafe lock and missing-project protection"
        )

        with ThreadPoolExecutor(max_workers=4) as pool:
            list(
                pool.map(
                    lambda index: create_strategy(path, f"Idea {index}", "Independent approach"),
                    range(8),
                )
            )
        concurrent = inspect_project(path).project
        assert len(concurrent.strategies) == 9
        assert len({strategy.id for strategy in concurrent.strategies}) == 9
        assert [event.sequence for event in concurrent.events] == list(range(1, 11))
        assert concurrent.strategies[0].id == strategy.id
        assert (path / "project.v1.json").read_bytes() == before
        print("PASS concurrent writers preserve all strategies, stable IDs and ordered events")

        corrupt = root / "corrupt.sigma"
        corrupt.mkdir()
        valid = json.loads((path / STATE).read_bytes())
        for field, value in (
            ("author_kind", "agent"),
            ("id", "invalid"),
            ("title", ""),
            ("created_at", "no timestamp"),
        ):
            raw = json.loads(json.dumps(valid))
            raw["strategies"][0][field] = value
            (corrupt / STATE).write_text(json.dumps(raw))
            invalid = (corrupt / STATE).read_bytes()
            rejects(lambda: create_strategy(corrupt, "Idea", "Approach"))
            assert (corrupt / STATE).read_bytes() == invalid
        for mutate in (
            lambda raw: raw["strategies"].append(raw["strategies"][0]),
            lambda raw: raw["events"][1].update(strategy_id=raw["id"]),
        ):
            raw = json.loads(json.dumps(valid))
            mutate(raw)
            (corrupt / STATE).write_text(json.dumps(raw))
            rejects(lambda: inspect_project(corrupt))
        print("PASS corrupt strategy records, unsupported authors and unmatched history rejected")

        with TestClient(app) as client:
            response = client.post(
                "/api/projects/strategies",
                json={
                    "path": str(path),
                    "title": "From the API",
                    "approach": "Test a bounded idea",
                },
            )
            assert response.status_code == 201, response.text
            api_strategy = response.json()["project"]["strategies"][-1]
            assert api_strategy["author_kind"] == "human"
            assert list_strategies(path)[-1].id == api_strategy["id"]
            response = client.get("/api/projects/strategies", params={"path": str(path)})
            assert response.status_code == 200 and len(response.json()["strategies"]) == 10
            snapshot = (path / STATE).read_bytes()
            assert (
                client.post(
                    "/api/projects/strategies",
                    json={
                        "path": str(path),
                        "title": " ",
                        "approach": "Invalid title",
                    },
                ).status_code
                == 400
            )
            assert (
                client.post("/api/projects/strategies", json={"path": str(path)}).status_code == 422
            )
            assert (path / STATE).read_bytes() == snapshot
        print("PASS API create/list, shared persistence, validation and safe error responses")
    print("All strategy scenarios passed.")


if __name__ == "__main__":
    main()
