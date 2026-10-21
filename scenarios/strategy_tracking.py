"""Active order, manual stages, strict history and v1-v4 lazy migration."""

import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from fastapi.testclient import TestClient

from sigma.api import app
from sigma.projects import (
    ProjectError,
    change_stage,
    create_strategy,
    edit_strategy,
    initialize_project,
    inspect_project,
    list_strategies,
    remove_strategy,
    reorder_strategies,
)


def rejects(action):
    try:
        action()
    except ProjectError:
        return
    raise AssertionError("Expected safe rejection")


def main():
    with TemporaryDirectory() as directory:
        root = Path(directory)
        for version in (1, 2, 3, 4):
            path = root / f"v{version}.sigma"
            initialize_project(path, "Research", "Truthful stages")
            if version > 1:
                create_strategy(path, "First", "Full first approach")
                create_strategy(path, "Second", "Full second approach")
            raw = json.loads((path / "project.json").read_bytes())
            raw["schema_version"] = version
            raw.pop("active_order", None)
            for item in raw.get("strategies", []):
                for key in ("stage", "summary", "provenance"):
                    item.pop(key, None)
            raw.pop("ai_model", None)
            raw.pop("reasoning_effort", None)
            if version < 4:
                del raw["research_mode"]
            if version == 1:
                del raw["strategies"]
            if version == 2:
                for s in raw["strategies"]:
                    del s["removed_at"]
            (path / "project.json").write_text(json.dumps(raw))
            before = (path / "project.json").read_bytes()
            project = inspect_project(path).project
            assert project.active_order == tuple(s.id for s in project.strategies)
            assert all(s.stage == "draft" for s in project.strategies)
            assert (path / "project.json").read_bytes() == before
            if version == 1:
                create_strategy(path, "First", "Full approach")
                before = (path / "project.json").read_bytes()
                backup_version = 2
            else:
                backup_version = version
            first = list_strategies(path)[0]
            changed = change_stage(path, first.id, "exploring")
            assert changed.project.schema_version == 5
            assert (path / f"project.v{backup_version}.json").read_bytes() == before
            stage_change = changed.project.events[-1].stage_change
            assert stage_change is not None and stage_change.previous == "draft"
            assert list_strategies(path)[0].created_at == first.created_at
            assert inspect_project(path) == changed
        print(
            "PASS v1/v2/v3/v4 no-write reads, creation-order/Draft defaults and exact v5 migration backups"
        )

        path = root / "tracking.sigma"
        initialize_project(path, "Tracking", "Keep history")
        for name in ("A", "B", "C"):
            create_strategy(path, name, f"Full {name} approach")
        ids = [s.id for s in list_strategies(path)]
        removed_id = ids[1]
        remove_strategy(path, removed_id)
        old = [ids[0], ids[2]]
        wanted = list(reversed(old))
        view = reorder_strategies(path, wanted, old)
        assert [s.id for s in list_strategies(path)] == wanted
        assert [
            s.id for s in view.project.strategies
        ] == ids  # Durable creation order never changes.
        before = (path / "project.json").read_bytes()
        reorder_strategies(path, wanted, wanted)
        change_stage(path, wanted[0], "draft")
        assert (path / "project.json").read_bytes() == before
        for invalid in ([removed_id, wanted[0]], [wanted[0]] * 2, ["unknown"], []):
            rejects(lambda invalid=invalid: reorder_strategies(path, invalid, wanted))
        rejects(lambda: reorder_strategies(path, old, old))
        rejects(lambda: change_stage(path, removed_id, "ready"))
        rejects(lambda: change_stage(path, wanted[0], "evaluated"))
        assert (path / "project.json").read_bytes() == before
        for operation in (
            lambda: reorder_strategies(path, old, wanted),
            lambda: change_stage(path, wanted[0], "hold"),
        ):
            with patch("sigma.projects.os.replace", side_effect=OSError("Injected disk error")):
                rejects(operation)
            assert (path / "project.json").read_bytes() == before
        edit_strategy(path, wanted[0], "Renamed", "Edited full approach")
        assert [s.id for s in list_strategies(path)] == wanted
        added = create_strategy(path, "D", "New joins at end").project.strategies[-1]
        assert [s.id for s in list_strategies(path)] == [*wanted, added.id]
        print(
            "PASS active-only reorder, no-op, removed history, stable identities, reload, stale order and failed writes"
        )

        current = [s.id for s in list_strategies(path)]

        def racing_order():
            try:
                return reorder_strategies(path, list(reversed(current)), current)
            except ProjectError:
                return None

        with ThreadPoolExecutor(max_workers=4) as pool:
            jobs = [
                pool.submit(racing_order),
                pool.submit(racing_order),
                pool.submit(change_stage, path, current[0], "ready"),
                pool.submit(edit_strategy, path, current[1], "Concurrent edit", "Preserved"),
            ]
            results = [j.result() for j in jobs]
        assert sum(r is not None for r in results[:2]) == 1
        assert list_strategies(path)[-1].stage == "ready"
        snapshot = (path / "project.json").read_bytes()
        raw = json.loads(snapshot)
        corrupt = root / "corrupt.sigma"
        corrupt.mkdir()
        for mutation in (
            lambda d: d.update(active_order=list(reversed(d["active_order"]))),
            lambda d: d["strategies"][0].update(stage="hold"),
            lambda d: d["strategies"][0].update(stage="evaluated"),
            lambda d: d["events"][-2].update(order=[]),
            lambda d: d["strategies"][0].update(
                provenance={"provider": "fake", "model": "invented"}
            ),
        ):
            bad = json.loads(json.dumps(raw))
            mutation(bad)
            (corrupt / "project.json").write_text(json.dumps(bad))
            rejects(lambda: inspect_project(corrupt))
        print(
            "PASS concurrent order/stage/edit persistence and strict corrupt history/metadata rejection"
        )
        with TestClient(app) as client:
            body = {"path": str(path), "strategy_id": current[0], "stage": "hold"}
            assert client.post("/api/projects/strategies/stage", json=body).status_code == 200
            active = list(inspect_project(path).project.active_order)
            response = client.post(
                "/api/projects/strategies/reorder",
                json={"path": str(path), "order": active[::-1], "expected_order": active},
            )
            assert response.status_code == 200
            assert (
                client.post(
                    "/api/projects/strategies/stage", json={**body, "stage": "evaluated"}
                ).status_code
                == 400
            )
        cli = subprocess.run(
            [sys.executable, "-m", "sigma.cli", "stage-strategy", str(path), current[0], "draft"],
            check=False,
            capture_output=True,
            text=True,
        )
        assert cli.returncode == 0, cli.stderr
        assert list_strategies(path)[0].stage == "draft"
        print("PASS API and CLI tracking through common services")


if __name__ == "__main__":
    main()
