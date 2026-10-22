"""Edit/removal audit history, format evolution, safe failures and peer adapters."""

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from fastapi.testclient import TestClient

from sigma.api import app
from sigma.projects import (
    STATE,
    ProjectError,
    create_strategy,
    edit_strategy,
    initialize_project,
    inspect_project,
    list_strategies,
    open_project,
    remove_strategy,
)


def rejects(action) -> None:
    try:
        action()
    except ProjectError:
        return
    raise AssertionError("Expected rejection without a write")


def fixture(path: Path):
    initialize_project(path, "Research", "Preserve the project and earlier text")
    raw = json.loads((path / STATE).read_bytes())
    raw["schema_version"] = 2
    raw.pop("research_mode", None)
    raw.pop("investigation_type", None)
    for key in ("ai_model", "reasoning_effort", "active_order"):
        raw.pop(key, None)
    (path / STATE).write_text(json.dumps(raw))
    view = create_strategy(path, "Original name", "Original description")
    return view, view.project.strategies[0]


def main() -> None:
    with TemporaryDirectory() as directory:
        root = Path(directory)
        path = root / "edits.sigma"
        original, strategy = fixture(path)
        before = (path / STATE).read_bytes()
        assert edit_strategy(path, strategy.id, strategy.title, strategy.approach) == original
        assert (path / STATE).read_bytes() == before  # No-op does not migrate or add an event.
        edited = edit_strategy(path, strategy.id, "Renamed idea", "Revised approach")
        assert edited.project.schema_version == 3
        assert (path / "project.v2.json").read_bytes() == before
        assert edited.project.id == original.project.id
        assert edited.project.events[:2] == original.project.events
        record = edited.project.strategies[0]
        assert (record.id, record.created_at, record.author_kind) == (
            strategy.id,
            strategy.created_at,
            strategy.author_kind,
        )
        change = edited.project.events[-1].change
        assert change is not None
        assert (change.previous_title, change.previous_approach) == (
            strategy.title,
            strategy.approach,
        )
        assert (change.title, change.approach) == (record.title, record.approach)
        second = edit_strategy(path, strategy.id, "Second edit", "A further revision")
        second_change = second.project.events[-1].change
        assert second_change is not None and second_change.previous_title == "Renamed idea"
        assert open_project(path) == second
        removed = remove_strategy(path, strategy.id)
        assert not list_strategies(path)
        assert removed.project.strategies[0].title == "Second edit"
        assert removed.project.strategies[0].removed_at == removed.project.events[-1].timestamp
        assert removed.project.events[:-1] == second.project.events
        assert removed.project.events[-1].kind == "strategy.removed"
        assert open_project(path) == removed
        assert (path / "project.v2.json").read_bytes() == before
        snapshot = (path / STATE).read_bytes()
        rejects(lambda: remove_strategy(path, strategy.id))
        rejects(lambda: edit_strategy(path, strategy.id, "No", "Removed"))
        rejects(lambda: remove_strategy(path, "unknown"))
        rejects(lambda: edit_strategy(path, "unknown", "No", "Unknown"))
        assert (path / STATE).read_bytes() == snapshot
        print(
            "PASS edit audit trail, unchanged identity, no-op, exact v2 backup, durable pool removal"
        )

        fresh = create_strategy(path, "A fresh idea", "After removal")
        assert fresh.project.schema_version == 3
        assert len(list_strategies(path)) == 1
        assert len(fresh.project.strategies) == 2
        active = list_strategies(path)[0]
        snapshot = (path / STATE).read_bytes()
        for title, approach in (
            (" ", "Text"),
            ("Name", "\n"),
            ("x" * 201, "Text"),
            ("Name", "x" * 10001),
        ):
            rejects(
                lambda title=title, approach=approach: edit_strategy(
                    path, active.id, title, approach
                )
            )
            assert (path / STATE).read_bytes() == snapshot
        for operation in (
            lambda: edit_strategy(path, active.id, "Changed", "Description"),
            lambda: remove_strategy(path, active.id),
        ):
            with patch("sigma.projects.os.replace", side_effect=OSError("disk failure")):
                rejects(operation)
            with patch("sigma.projects.os.fsync", side_effect=OSError("flush failure")):
                rejects(operation)
            assert (path / STATE).read_bytes() == snapshot
            assert not list(path.glob(".sigma-write-*"))
        print("PASS create after removal, validation, failed edits/removals leave state unchanged")

        for mode in ("edit", "remove"):
            target = root / f"{mode}.sigma"
            _, item = fixture(target)
            snapshot = (target / STATE).read_bytes()

            def mutate(target=target, item=item, mode=mode):
                return (
                    edit_strategy(target, item.id, "New", "Text")
                    if mode == "edit"
                    else remove_strategy(target, item.id)
                )

            with patch("sigma.projects.os.link", side_effect=OSError("backup failure")):
                rejects(mutate)
            assert (target / STATE).read_bytes() == snapshot
            assert not list(target.glob(".sigma-write-*"))
            with patch("sigma.projects.os.replace", side_effect=OSError("publish failure")):
                rejects(mutate)
            assert (target / STATE).read_bytes() == snapshot
            assert (target / "project.v2.json").read_bytes() == snapshot
            mutate()  # Retry accepts the existing exact backup.
            assert inspect_project(target).project.schema_version == 3
        print("PASS both first-write migrations, backup/publication failure and retry")

        concurrent = root / "concurrent.sigma"
        _, first = fixture(concurrent)
        second_id = (
            create_strategy(concurrent, "Keep me", "Separate idea").project.strategies[-1].id
        )
        with ThreadPoolExecutor(max_workers=3) as pool:
            jobs = [
                pool.submit(remove_strategy, concurrent, first.id),
                pool.submit(
                    edit_strategy, concurrent, second_id, "Edited concurrently", "Approach"
                ),
                pool.submit(create_strategy, concurrent, "New concurrently", "Approach"),
            ]
            for job in jobs:
                job.result()
        project = inspect_project(concurrent).project
        assert len(list_strategies(concurrent)) == 2
        assert len(project.events) == 6
        assert [event.sequence for event in project.events] == list(range(1, 7))
        print("PASS concurrent create/edit/remove preserve all records and ordered history")

        corrupt = root / "corrupt.sigma"
        corrupt.mkdir()
        valid = json.loads((path / STATE).read_bytes())
        mutations = [
            lambda raw: raw["strategies"][0].update(removed_at=None),
            lambda raw: raw["events"][2]["change"].update(title="Mismatched edit"),
            lambda raw: raw["events"][3]["change"].update(previous_title="Broken chain"),
            lambda raw: raw["events"][4].update(strategy_id=raw["id"]),
        ]
        for mutate_raw in mutations:
            raw = json.loads(json.dumps(valid))
            mutate_raw(raw)
            (corrupt / STATE).write_text(json.dumps(raw))
            before_bad = (corrupt / STATE).read_bytes()
            rejects(lambda: inspect_project(corrupt))
            assert (corrupt / STATE).read_bytes() == before_bad
        print("PASS inconsistent edit/removal histories rejected without repair")

        api_path = root / "api.sigma"
        _, api_strategy = fixture(api_path)
        with TestClient(app) as client:
            body = {"path": str(api_path), "strategy_id": api_strategy.id}
            response = client.post(
                "/api/projects/strategies/edit",
                json={
                    **body,
                    "title": "API edit",
                    "approach": "Updated description",
                },
            )
            assert response.status_code == 200, response.text
            assert list_strategies(api_path)[0].title == "API edit"
            assert (
                client.post(
                    "/api/projects/strategies/edit",
                    json={
                        **body,
                        "title": " ",
                        "approach": "Invalid",
                    },
                ).status_code
                == 400
            )
            assert client.post("/api/projects/strategies/edit", json=body).status_code == 422
            assert client.post("/api/projects/strategies/remove", json=body).status_code == 200
            assert client.get(
                "/api/projects/strategies", params={"path": str(api_path)}
            ).json() == {"strategies": []}
            assert client.post("/api/projects/strategies/remove", json=body).status_code == 400
        assert inspect_project(api_path).project.strategies[0].approach == "Updated description"
        print("PASS API edit/remove/list and validation through the shared services")
    print("All edit/removal scenarios passed.")


if __name__ == "__main__":
    main()
