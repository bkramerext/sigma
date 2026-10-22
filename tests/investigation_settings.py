"""Atomic settings transactions, strict audit, identity and legacy safety."""

import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from fastapi.testclient import TestClient

from sigma.api import app
from sigma.investigations import (
    InvestigationError,
    change_stage,
    create_strategy,
    edit_strategy,
    initialize_investigation,
    inspect_investigation,
    investigation_settings,
    remove_strategy,
    update_investigation,
)


def rejects(action):
    try:
        action()
    except InvestigationError:
        return
    raise AssertionError("Expected safe failure")


def edit(path, values, prior):
    normalized = dict(values)
    normalized["research_mode"] = normalized.pop("investigation_type")
    return update_investigation(path, **normalized, expected=prior)


def main():
    with TemporaryDirectory() as directory:
        root = Path(directory)
        for version in range(1, 6):
            path = root / f"legacy{version}.sigma"
            initialize_investigation(path, "Original", "Original question")
            if version >= 2:
                first = create_strategy(path, "A", "First approach").investigation.strategies[0]
                second = create_strategy(
                    path, "B", "Keep archived content"
                ).investigation.strategies[-1]
                if version >= 3:
                    remove_strategy(path, second.id)
                if version >= 5:
                    change_stage(path, first.id, "ready")
            raw = json.loads((path / "investigation.json").read_bytes())
            raw["schema_version"] = version
            raw.pop("ai_model", None)
            raw.pop("reasoning_effort", None)
            if version < 4:
                raw.pop("research_mode", None)
                raw.pop("investigation_type", None)
            if version == 1:
                del raw["strategies"]
            if version < 5:
                raw.pop("active_order", None)
                for strategy in raw.get("strategies", []):
                    for key in ("stage", "summary", "provenance"):
                        strategy.pop(key, None)
            if version == 2:
                for strategy in raw["strategies"]:
                    del strategy["removed_at"]
            (path / "investigation.json").write_text(json.dumps(raw))
            before = (path / "investigation.json").read_bytes()
            view = inspect_investigation(path)
            assert (
                view.investigation.ai_model == "gpt-6.1-sol"
                and view.investigation.reasoning_effort == "high"
            )
            assert (path / "investigation.json").read_bytes() == before
            prior = asdict(investigation_settings(view.investigation))
            assert edit(path, prior, prior) == view
            assert (path / "investigation.json").read_bytes() == before
            values = {
                **prior,
                "title": "Renamed",
                "problem": "New question",
                "investigation_type": "mathematical",
                "ai_model": "gpt-6-luna",
                "reasoning_effort": "xhigh",
            }
            result = edit(path, values, prior)
            assert result.path == view.path and result.investigation.id == view.investigation.id
            assert result.investigation.schema_version == 7
            assert result.investigation.strategies == view.investigation.strategies
            assert result.investigation.active_order == view.investigation.active_order
            assert result.investigation.events[:-1] == view.investigation.events
            assert (path / f"investigation.v{version}.json").read_bytes() == before
            investigation_change = result.investigation.events[-1].investigation_change
            assert investigation_change is not None
            assert asdict(investigation_change) == {
                "previous": prior,
                "current": values,
            }
            assert inspect_investigation(path) == result
            # Reverse mode as an actual single transaction.
            back = edit(path, {**values, "investigation_type": "default"}, values)
            assert back.investigation.id == view.investigation.id
        print(
            "PASS v1-v5 no-write/default/no-op reads, exact migration backups, stable identity/path/order/archives and auditable edit/reopen"
        )
        path = root / "new.sigma"
        initial = initialize_investigation(
            path, "Created", "Question", "mathematical", "gpt-6.1-sol", "high"
        )
        rejects(
            lambda: initialize_investigation(
                root / "invalid-model.sigma", "Bad", "Question", ai_model=""
            )
        )
        assert not (root / "invalid-model.sigma").exists()
        assert initial.investigation.schema_version == 7
        prior = asdict(investigation_settings(initial.investigation))
        for key, bad in (
            ("title", " "),
            ("problem", ""),
            ("title", "x" * 201),
            ("problem", "x" * 20001),
            ("investigation_type", "alien"),
            ("ai_model", "text-embedding-3-small"),
            ("reasoning_effort", "none"),
        ):
            rejects(lambda key=key, bad=bad: edit(path, {**prior, key: bad}, prior))
        assert inspect_investigation(path) == initial
        for failure in ("os.replace", "os.fsync"):
            with patch(
                "sigma.investigations." + failure, side_effect=OSError("Injected save failure")
            ):
                rejects(lambda: edit(path, {**prior, "title": "Failed"}, prior))
            assert inspect_investigation(path) == initial

        def race(title):
            try:
                return edit(path, {**prior, "title": title}, prior)
            except InvestigationError:
                return None

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(race, ["Editor one", "Editor two"]))
        assert sum(r is not None for r in results) == 1
        current = inspect_investigation(path)
        assert len(current.investigation.events) == 2
        create_strategy(path, "Independent strategy", "No settings conflict")
        values = asdict(investigation_settings(current.investigation))
        fresh = edit(path, {**values, "problem": "Concurrent strategy survives"}, values)
        assert len(fresh.investigation.strategies) == 1
        item = fresh.investigation.strategies[0]
        change_stage(path, item.id, "exploring")
        edit_strategy(path, item.id, "Edited strategy", "New approach")
        remove_strategy(path, item.id)
        assert inspect_investigation(path).investigation.schema_version == 7
        print(
            "PASS explicit model/High creation, field/pair rejection, atomic failures, stale editors and independent strategy changes"
        )
        valid = json.loads((path / "investigation.json").read_bytes())
        bad = root / "corrupt.sigma"
        bad.mkdir()
        for mutation in (
            lambda d: d.update(title="Unaudited"),
            lambda d: [e for e in d["events"] if e["kind"] == "investigation.updated"][-1][
                "investigation_change"
            ]["previous"].update(title="Broken chain"),
            lambda d: d["events"][1]["investigation_change"]["current"].update(
                title="Incorrect final"
            ),
            lambda d: d.update(reasoning_effort="invented"),
            lambda d: d.update(extra="unexpected"),
        ):
            raw = json.loads(json.dumps(valid))
            mutation(raw)
            (bad / "investigation.json").write_text(json.dumps(raw))
            rejects(lambda: inspect_investigation(bad))
        with TestClient(app) as client:
            expected = asdict(investigation_settings(inspect_investigation(path).investigation))
            body = {"path": str(path), **expected, "title": "API name", "expected": expected}
            response = client.post("/api/investigations/update", json=body)
            assert response.status_code == 200, response.text
            assert client.post("/api/investigations/update", json=body).status_code == 400
            assert (
                client.post(
                    "/api/investigations/update", json={**body, "id": "new-guid"}
                ).status_code
                == 422
            )
        expected = asdict(investigation_settings(inspect_investigation(path).investigation))
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "sigma.cli",
                "edit-investigation",
                str(path),
                "--title",
                "CLI name",
                "--problem",
                "CLI question",
                "--research-mode",
                "default",
                "--model",
                "gpt-6-astra",
                "--thinking",
                "high",
                "--expected",
                json.dumps(expected),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        assert inspect_investigation(path).investigation.id == initial.investigation.id
        print(
            "PASS strict investigation audit corruption rejection and consistent API/CLI update/conflict behavior"
        )


if __name__ == "__main__":
    main()
