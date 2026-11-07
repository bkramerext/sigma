"""Per-user Settings remain independent from imported or historical project limits."""
from __future__ import annotations

import json
import stat

from sigma import global_research_settings, project_types, research_sessions


def test_global_research_settings_defaults_and_project_limits_ignored(tmp_path, monkeypatch):
    directory = tmp_path / "user-a"
    directory.mkdir()
    monkeypatch.setattr(project_types, "_store_path", lambda: directory / ".sigma-project-types.json")
    defaults = global_research_settings.load_config()
    assert defaults["limits"]["research_rounds"] == 3
    assert defaults["limits"]["turns_per_round"] == 3
    assert defaults["limits"]["model_calls"] == 18
    assert defaults["limits"]["session_duration_minutes"] == 60

    # A historical project may still carry limits.json in an archive.
    old_project = tmp_path / "legacy.sigma" / "research-sessions"
    old_project.mkdir(parents=True)
    (old_project / "limits.json").write_text(json.dumps({
        **research_sessions.NEW_DEFAULT_LIMITS,
        "research_rounds": 1, "turns_per_round": 1, "model_calls": 2,
    }))
    assert research_sessions.get_limits(str(old_project.parent))["research_rounds"] == 3
    assert not (directory / ".sigma-global-research-settings.json").exists()


def test_users_have_independent_settings_and_no_legacy_propagation(tmp_path, monkeypatch):
    alice = tmp_path / "alice"
    bob = tmp_path / "bob"
    alice.mkdir()
    bob.mkdir()
    monkeypatch.setattr(project_types, "_store_path", lambda: alice / "types.json")
    saved = global_research_settings.save_config({
        "limits": {**research_sessions.NEW_DEFAULT_LIMITS,
            "research_rounds": 4, "turns_per_round": 3, "model_calls": 24},
        "show_advanced_outcome_details": True,
    })
    assert saved["limits"]["research_rounds"] == 4
    assert global_research_settings.load_config()["show_advanced_outcome_details"] is True
    path = alice / ".sigma-global-research-settings.json"
    assert stat.S_IMODE(path.stat().st_mode) == 0o600

    monkeypatch.setattr(project_types, "_store_path", lambda: bob / "types.json")
    assert global_research_settings.load_config()["limits"]["research_rounds"] == 3
    assert global_research_settings.load_config()["show_advanced_outcome_details"] is False
    assert not (bob / ".sigma-global-research-settings.json").exists()


def test_legacy_save_limits_api_no_longer_writes_into_project(tmp_path, monkeypatch):
    owner = tmp_path / "owner"
    owner.mkdir()
    monkeypatch.setattr(project_types, "_store_path", lambda: owner / "types.json")
    project = tmp_path / "project.sigma"
    project.mkdir()
    updated = research_sessions.save_limits(str(project), {
        **research_sessions.NEW_DEFAULT_LIMITS,
        "research_rounds": 5, "turns_per_round": 2, "model_calls": 20,
    })
    assert updated["research_rounds"] == 5
    assert research_sessions.get_limits(str(project))["research_rounds"] == 5
    assert not (project / "research-sessions" / "limits.json").exists()
