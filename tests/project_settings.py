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
    export_complete_project,
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
        # Build provenance belongs to the process that writes the project, not
        # a later checkout HEAD. It is optional for every legacy schema.
        first_commit, second_commit = 'a' * 40, 'b' * 40
        stamped = root / 'stamped.sigma'
        with patch('sigma.projects.build_commit', return_value=first_commit):
            stamped_view = initialize_project(stamped, 'Stamped', 'Provenance regression')
        assert stamped_view.project.backend_build_commit == first_commit
        assert json.loads((stamped / 'project.json').read_text())['backend_build_commit'] == first_commit
        prior_stamp = asdict(project_settings(stamped_view.project))
        original_bytes = (stamped / 'project.json').read_bytes()
        with patch('sigma.projects.build_commit', return_value=second_commit):
            assert edit(stamped, prior_stamp, prior_stamp) == stamped_view
        assert (stamped / 'project.json').read_bytes() == original_bytes
        with patch('sigma.projects.build_commit', return_value=second_commit):
            create_strategy(stamped, 'Stamped strategy', 'Check saved build identity')
        assert inspect_project(stamped).project.backend_build_commit == second_commit
        from sigma.project_bundle import import_bundle
        portable = json.loads(export_complete_project(stamped))
        assert portable['files']['project.json']['backend_build_commit'] == second_commit
        imported = root / 'stamped-import.json'
        import_bundle(portable, imported)
        assert inspect_project(imported).project.backend_build_commit == second_commit
        unstamped = root / 'unstamped.sigma'
        initialize_project(unstamped, 'Unstamped', 'Legacy compatibility')
        legacy_content = json.loads((unstamped / 'project.json').read_text())
        legacy_content.pop('backend_build_commit', None)
        (unstamped / 'project.json').write_text(json.dumps(legacy_content))
        assert inspect_project(unstamped).project.backend_build_commit is None
        with patch('sigma.projects.build_commit', return_value=second_commit):
            create_strategy(unstamped, 'Next edit', 'Future write stamps the build')
        assert inspect_project(unstamped).project.backend_build_commit == second_commit
        bad_commit = json.loads((stamped / 'project.json').read_text())
        bad_commit['backend_build_commit'] = 'not-a-sha'
        corrupt_build = root / 'corrupt-build.sigma'
        corrupt_build.mkdir()
        (corrupt_build / 'project.json').write_text(json.dumps(bad_commit))
        rejects(lambda: inspect_project(corrupt_build))
        print('PASS optional project build SHA creation/edit/no-op/legacy/export/import/validation')
        for version in range(1, 10):
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
            raw.pop('backend_build_commit', None)  # True legacy files never carried the field.
            if version < 8:
                raw.pop("difficulty", None)
            if version < 9:
                raw.pop("show_advanced_outcome_details", None)
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
            assert (
                view.project.difficulty is None
                if version < 8
                else view.project.difficulty is not None
            )
            assert view.project.show_advanced_outcome_details is False
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
            assert result.project.schema_version == max(version, 8)
            assert result.project.difficulty is not None
            assert result.project.difficulty.value == "hard"
            assert result.project.show_advanced_outcome_details is False
            assert result.project.strategies == view.project.strategies
            assert result.project.active_order == view.project.active_order
            assert result.project.events[:-1] == view.project.events
            if result.project.schema_version != version:
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
            assert back.project.show_advanced_outcome_details is False
        legacy = root / "unknown-preserved.sigma"
        initialize_project(legacy, "Legacy unknown", "Retain unknown difficulty")
        legacy_raw = json.loads((legacy / "project.json").read_bytes())
        legacy_raw["schema_version"] = 7
        legacy_raw.pop("difficulty")
        legacy_raw.pop("show_advanced_outcome_details")
        (legacy / "project.json").write_text(json.dumps(legacy_raw))
        legacy_view = inspect_project(legacy)
        legacy_settings = asdict(project_settings(legacy_view.project))
        renamed = edit(legacy, {**legacy_settings, "title": "Still unknown"}, legacy_settings)
        assert renamed.project.schema_version == 7 and renamed.project.difficulty is None
        assert "difficulty" not in json.loads((legacy / "project.json").read_bytes())
        assert inspect_project(legacy).project.difficulty is None
        with TestClient(app) as client:
            exported_legacy = client.get("/api/projects/audit", params={"path": str(legacy)})
            assert exported_legacy.status_code == 200
            assert "difficulty" not in exported_legacy.json()["project"]
            report_legacy = client.get(
                "/api/projects/export/report", params={"path": str(legacy), "format": "txt"}
            )
            assert report_legacy.status_code == 200 and "Difficulty:" not in report_legacy.text
        print(
            "PASS v1-v9 no-write/unknown/no-op reads, exact migration backups, stable identity/path/order/archives and auditable edit/reopen"
        )
        path = root / "new.sigma"
        initial = initialize_project(
            path, "Created", "Question", "mathematical", "gpt-6.1-sol", "high"
        )
        rejects(
            lambda: initialize_project(root / "invalid-model.sigma", "Bad", "Question", ai_model="")
        )
        assert not (root / "invalid-model.sigma").exists()
        assert initial.project.schema_version == 9
        assert initial.project.difficulty is not None
        assert initial.project.difficulty.value == "medium"
        assert initial.project.show_advanced_outcome_details is False
        sibling = initialize_project(root / "sibling.sigma", "Sibling", "Independent question")
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
            ("show_advanced_outcome_details", "yes"),
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
        assert inspect_project(path).project.schema_version == 9
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
            preference_settings = asdict(project_settings(inspect_project(path).project))
            preference_body = {
                "path": str(path),
                **preference_settings,
                "expected": preference_settings,
                "show_advanced_outcome_details": True,
            }
            preference_response = client.post("/api/projects/update", json=preference_body)
            assert preference_response.status_code == 200, preference_response.text
            assert preference_response.json()["project"]["show_advanced_outcome_details"] is True
            assert inspect_project(path).project.show_advanced_outcome_details is True
            assert inspect_project(sibling.path).project.show_advanced_outcome_details is False
            assert (
                json.loads((Path(path) / "project.json").read_bytes())[
                    "show_advanced_outcome_details"
                ]
                is True
            )
            assert client.post("/api/projects/update", json=body).status_code == 400
            exported = client.get("/api/projects/audit", params={"path": str(path)})
            assert exported.status_code == 200
            assert exported.json()["project"]["difficulty"] == "medium"
            assert exported.json()["project"]["show_advanced_outcome_details"] is True
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
            assert defaults == {**research_sessions.DEFAULT_LIMITS, "max_concurrent_sessions": "1"}
            assert defaults["research_rounds"] == 2
            assert defaults["model_calls"] == 12
            assert defaults["session_duration_minutes"] == 60
            assert defaults["output_tokens_per_call"] == 4000
            changed_limits = {**defaults, "research_rounds": 2, "model_calls": 4}
            saved_limits = client.put(limits_url, json={"path": str(path), **changed_limits})
            assert saved_limits.status_code == 200 and saved_limits.json() == changed_limits
            assert client.get(limits_url, params={"path": str(path)}).json() == changed_limits
            assert (
                client.put(
                    limits_url, json={"path": str(path), **changed_limits, "model_calls": 1}
                ).status_code
                == 422
            )
            three_turns = client.put(
                limits_url, json={"path": str(path), **changed_limits, "model_calls": 3}
            )
            assert three_turns.status_code == 200
            assert three_turns.json()["model_calls"] == 3
            for invalid in (
                {**defaults, "research_rounds": 6, "model_calls": 30},
                {**defaults, "model_calls": 121},
                {**defaults, "session_duration_minutes": 7 * 24 * 60 + 1},
                {**defaults, "output_tokens_per_call": 20001},
                {**defaults, "maximum_estimated_cost_usd": 0.001},
            ):
                assert (
                    client.put(limits_url, json={"path": str(path), **invalid}).status_code == 422
                )
            for invalid_concurrency in (0, "0", "-1", "1.5", "not-a-number", "5", 5):
                assert (
                    client.put(
                        limits_url,
                        json={
                            "path": str(path),
                            **changed_limits,
                            "max_concurrent_sessions": invalid_concurrency,
                        },
                    ).status_code
                    == 400
                )
            arbitrary_positive = "9" * 100
            unlimited_range = client.put(
                limits_url,
                json={
                    "path": str(path),
                    **changed_limits,
                    "max_concurrent_sessions": arbitrary_positive,
                },
            )
            assert unlimited_range.status_code == 400
            numeric_limit = client.put(
                limits_url,
                json={"path": str(path), **changed_limits, "max_concurrent_sessions": 4},
            )
            assert numeric_limit.status_code == 200
            assert numeric_limit.json()["max_concurrent_sessions"] == "4"
            unlimited_duration = client.put(
                limits_url,
                json={"path": str(path), **changed_limits, "session_duration_minutes": None},
            )
            assert unlimited_duration.status_code == 200, unlimited_duration.text
            assert unlimited_duration.json()["session_duration_minutes"] is None
            assert client.get(limits_url, params={"path": str(path)}).json()["session_duration_minutes"] is None
            assert research_sessions.get_limits(str(path))["session_duration_minutes"] is None
            finite_again = client.put(
                limits_url,
                json={"path": str(path), **changed_limits, "session_duration_minutes": 60},
            )
            assert finite_again.status_code == 200, finite_again.text
            assert finite_again.json()["session_duration_minutes"] == 60
            assert (
                research_sessions.get_limits(str(sibling.path)) == research_sessions.DEFAULT_LIMITS
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
