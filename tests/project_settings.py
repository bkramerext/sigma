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

from sigma import research_sessions
from sigma.api import app
from sigma.projects import (
    ProjectError,
    change_stage,
    create_strategy,
    edit_strategy,
    initialize_project,
    inspect_project,
    project_settings,
    remove_strategy,
    update_project,
)


def rejects(action):
    try:
        action()
    except ProjectError:
        return
    raise AssertionError("Expected safe failure")


def edit(path, values, prior):
    normalized = dict(values)
    normalized["research_mode"] = normalized.pop("investigation_type")
    return update_project(path, **normalized, expected=prior)


def main():
    with TemporaryDirectory() as directory:
        root = Path(directory)
        for version in range(1, 8):
            path = root / f"legacy{version}.sigma"
            initialize_project(path, "Original", "Original question")
            if version >= 2:
                first = create_strategy(path, "A", "First approach").project.strategies[0]
                second = create_strategy(path, "B", "Keep archived content").project.strategies[-1]
                if version >= 3:
                    remove_strategy(path, second.id)
                if version >= 5:
                    change_stage(path, first.id, "ready")
            raw = json.loads((path / "project.json").read_bytes())
            raw["schema_version"] = version
            raw.pop("difficulty", None)
            if version < 6:
                raw.pop("ai_model", None)
                raw.pop("reasoning_effort", None)
            if version < 4:
                raw.pop("research_mode", None)
                raw.pop("investigation_type", None)
            if version == 1:
                del raw["strategies"]
            if version < 7:
                for strategy in raw.get("strategies", []):
                    strategy.pop("enabled", None)
            if version < 5:
                raw.pop("active_order", None)
                for strategy in raw.get("strategies", []):
                    for key in ("stage", "summary", "provenance"):
                        strategy.pop(key, None)
            if version == 2:
                for strategy in raw["strategies"]:
                    del strategy["removed_at"]
            (path / "project.json").write_text(json.dumps(raw))
            before = (path / "project.json").read_bytes()
            view = inspect_project(path)
            assert (
                view.project.ai_model == "gpt-6.1-sol" and view.project.reasoning_effort == "high"
            )
            assert view.project.difficulty.value == "medium"
            assert (path / "project.json").read_bytes() == before
            prior = asdict(project_settings(view.project))
            assert edit(path, prior, prior) == view
            assert (path / "project.json").read_bytes() == before
            values = {
                **prior,
                "title": "Renamed",
                "problem": "New question",
                "investigation_type": "mathematical",
                "ai_model": "gpt-6-luna",
                "reasoning_effort": "xhigh",
                "difficulty": "hard",
            }
            result = edit(path, values, prior)
            assert result.path == view.path and result.project.id == view.project.id
            assert result.project.schema_version == 8
            assert result.project.difficulty.value == "hard"
            assert result.project.strategies == view.project.strategies
            assert result.project.active_order == view.project.active_order
            assert result.project.events[:-1] == view.project.events
            assert (path / f"project.v{version}.json").read_bytes() == before
            project_change = result.project.events[-1].project_change
            assert project_change is not None
            assert asdict(project_change) == {
                "previous": prior,
                "current": values,
            }
            assert inspect_project(path) == result
            # Reverse mode as an actual single transaction.
            back = edit(path, {**values, "investigation_type": "default"}, values)
            assert back.project.id == view.project.id
        print(
            "PASS v1-v7 no-write/default/no-op reads, exact migration backups, stable identity/path/order/archives and auditable edit/reopen"
        )
        path = root / "new.sigma"
        initial = initialize_project(
            path, "Created", "Question", "mathematical", "gpt-6.1-sol", "high"
        )
        rejects(
            lambda: initialize_project(root / "invalid-model.sigma", "Bad", "Question", ai_model="")
        )
        assert not (root / "invalid-model.sigma").exists()
        assert initial.project.schema_version == 8
        assert initial.project.difficulty.value == "medium"
        prior = asdict(project_settings(initial.project))
        for key, bad in (
            ("title", " "),
            ("problem", ""),
            ("title", "x" * 201),
            ("problem", "x" * 20001),
            ("investigation_type", "alien"),
            ("ai_model", "text-embedding-3-small"),
            ("reasoning_effort", "none"),
            ("difficulty", "impossible"),
        ):
            rejects(lambda key=key, bad=bad: edit(path, {**prior, key: bad}, prior))
        assert inspect_project(path) == initial
        for failure in ("os.replace", "os.fsync"):
            with patch("sigma.projects." + failure, side_effect=OSError("Injected save failure")):
                rejects(lambda: edit(path, {**prior, "title": "Failed"}, prior))
            assert inspect_project(path) == initial

        def race(title):
            try:
                return edit(path, {**prior, "title": title}, prior)
            except ProjectError:
                return None

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(race, ["Editor one", "Editor two"]))
        assert sum(r is not None for r in results) == 1
        current = inspect_project(path)
        assert len(current.project.events) == 2
        create_strategy(path, "Independent strategy", "No settings conflict")
        values = asdict(project_settings(current.project))
        fresh = edit(path, {**values, "problem": "Concurrent strategy survives"}, values)
        assert len(fresh.project.strategies) == 1
        item = fresh.project.strategies[0]
        change_stage(path, item.id, "exploring")
        edit_strategy(path, item.id, "Edited strategy", "New approach")
        remove_strategy(path, item.id)
        assert inspect_project(path).project.schema_version == 8
        print(
            "PASS explicit model/High creation, field/pair rejection, atomic failures, stale editors and independent strategy changes"
        )
        valid = json.loads((path / "project.json").read_bytes())
        bad = root / "corrupt.sigma"
        bad.mkdir()
        for mutation in (
            lambda d: d.update(title="Unaudited"),
            lambda d: [e for e in d["events"] if e["kind"] == "project.updated"][-1][
                "project_change"
            ]["previous"].update(title="Broken chain"),
            lambda d: d["events"][1]["project_change"]["current"].update(title="Incorrect final"),
            lambda d: d.update(reasoning_effort="invented"),
            lambda d: d.update(difficulty="impossible"),
            lambda d: d.pop("difficulty"),
            lambda d: d.update(extra="unexpected"),
        ):
            raw = json.loads(json.dumps(valid))
            mutation(raw)
            (bad / "project.json").write_text(json.dumps(raw))
            rejects(lambda: inspect_project(bad))
        with TestClient(app) as client:
            expected = asdict(project_settings(inspect_project(path).project))
            body = {"path": str(path), **expected, "title": "API name", "expected": expected}
            assert (
                client.post(
                    "/api/projects/update", json={**body, "difficulty": "trivial"}
                ).status_code
                == 400
            )
            response = client.post("/api/projects/update", json=body)
            assert response.status_code == 200, response.text
            assert response.json()["project"]["difficulty"] == "medium"
            assert client.post("/api/projects/update", json=body).status_code == 400
            exported = client.get("/api/projects/export", params={"path": str(path)})
            assert exported.status_code == 200
            assert exported.json()["project"]["difficulty"] == "medium"
            report = client.get(
                "/api/projects/export/report", params={"path": str(path), "format": "txt"}
            )
            assert report.status_code == 200 and "Difficulty: Medium" in report.text
            assert (
                client.post("/api/projects/update", json={**body, "id": "new-guid"}).status_code
                == 422
            )
            limits_url = "/api/projects/research-limits"
            defaults = client.get(limits_url, params={"path": str(path)}).json()
            assert defaults == research_sessions.DEFAULT_LIMITS
            changed_limits = {**defaults, "research_rounds": 2, "model_calls": 4}
            saved_limits = client.put(limits_url, json={"path": str(path), **changed_limits})
            assert saved_limits.status_code == 200 and saved_limits.json() == changed_limits
            assert client.get(limits_url, params={"path": str(path)}).json() == changed_limits
            assert (
                client.put(
                    limits_url, json={"path": str(path), **changed_limits, "model_calls": 3}
                ).status_code
                == 400
            )
            for invalid in (
                {**defaults, "research_rounds": 11, "model_calls": 20},
                {**defaults, "session_duration_minutes": 121},
                {**defaults, "output_tokens_per_call": 16385},
                {**defaults, "maximum_estimated_cost_usd": 0.001},
            ):
                assert (
                    client.put(limits_url, json={"path": str(path), **invalid}).status_code == 422
                )
        expected = asdict(project_settings(inspect_project(path).project))
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "sigma.cli",
                "edit-project",
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
        assert inspect_project(path).project.id == initial.project.id
        print(
            "PASS strict project audit corruption rejection and consistent API/CLI update/conflict behavior"
        )


if __name__ == "__main__":
    main()
