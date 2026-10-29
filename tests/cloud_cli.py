"""Offline tests for hosted CLI configuration and credential handling."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from sigma import cloud_cli


def test_hosted_project_limit_update_uses_expected_snapshot() -> None:
    with tempfile.TemporaryDirectory(prefix="sigma-cloud-cli-") as directory:
        token_file = Path(directory) / "token"
        cloud_cli._save_token(token_file, "https://sigma.example.org", "opaque-fixture-token")
        before = {
            "research_rounds": 2,
            "model_calls": 4,
            "session_duration_minutes": 15,
            "output_tokens_per_call": 4000,
            "maximum_estimated_cost_usd": 0.1,
            "maximum_input_tokens_per_session": 200000,
            "max_concurrent_sessions": "1",
        }
        after = {**before, "maximum_estimated_cost_usd": 15.0}

        def fake_request(_host, _token, method, endpoint, *, params=None, body=None):
            if method == "GET":
                assert endpoint.endswith("research-limits")
                return before
            assert endpoint.endswith("research-limits")
            assert body is not None
            assert body["expected_limits"] == before
            assert body["maximum_estimated_cost_usd"] == 15.0
            return after

        with patch.object(cloud_cli, "request", side_effect=fake_request):
            result = cloud_cli.set_param(
                "https://sigma.example.org",
                token_file,
                "/workspace/operation-narrow-passage.sigma",
                "maximum-estimated-cost-usd",
                "15",
            )
        assert result["previous"] == 0.1 and result["value"] == 15.0
        assert token_file.stat().st_mode & 0o077 == 0


def test_project_setting_update_keeps_current_snapshot() -> None:
    with tempfile.TemporaryDirectory(prefix="sigma-cloud-cli-") as directory:
        token_file = Path(directory) / "token"
        cloud_cli._save_token(token_file, "https://sigma.example.org", "opaque-fixture-token")
        project = {
            "title": "Narrow Passage",
            "problem": "Scenario prompt",
            "investigation_type": "military",
            "ai_model": "gpt-6.1-sol",
            "reasoning_effort": "high",
            "difficulty": "hard",
            "show_advanced_outcome_details": False,
        }

        def fake_request(_host, _token, method, endpoint, *, params=None, body=None):
            if method == "GET":
                assert endpoint.endswith("inspect")
                return {"project": project}
            assert endpoint.endswith("update")
            assert body is not None
            assert body["expected"] == project
            assert body["investigation_type"] == "military"
            assert body["reasoning_effort"] == "high"
            return {"project": {**project, "difficulty": "medium"}}

        with patch.object(cloud_cli, "request", side_effect=fake_request):
            result = cloud_cli.set_param(
                "https://sigma.example.org",
                token_file,
                "/workspace/project.sigma",
                "difficulty",
                "medium",
            )
        assert result["previous"] == "hard" and result["value"] == "medium"


def test_cloud_cli_requires_https_origin() -> None:
    try:
        cloud_cli._host("http://sigma.example.org")
    except cloud_cli.CloudCliError:
        pass
    else:
        raise AssertionError("Insecure hosted SIGMA origin was accepted")
    assert cloud_cli._host("http://127.0.0.1:5173") == "http://127.0.0.1:5173"


def test_export_is_private_complete_and_never_overwritten() -> None:
    with tempfile.TemporaryDirectory(prefix="sigma-cloud-cli-") as directory:
        target = Path(directory) / "project.json"
        value = {"export_version": 2, "project": {"investigation_type": "military"}}
        cloud_cli.write_export(value, target)
        assert target.stat().st_mode & 0o077 == 0
        assert target.read_text(encoding="utf-8").endswith("\n")
        try:
            cloud_cli.write_export({"different": True}, target)
        except cloud_cli.CloudCliError as exc:
            assert "already exists" in str(exc)
        else:
            raise AssertionError("CLI export replaced existing evidence")
        assert '"export_version": 2' in target.read_text(encoding="utf-8")


def test_cli_run_uses_authenticated_api_and_exports_each_transition() -> None:
    with tempfile.TemporaryDirectory(prefix="sigma-cloud-cli-") as directory:
        token_file = Path(directory) / "token"
        cloud_cli._save_token(token_file, "http://127.0.0.1:5173", "fixture-token")
        path = "/workspace/narrow-passage.sigma"
        project_id = str(uuid4())
        ids = [str(uuid4()), str(uuid4())]
        limits = {
            "research_rounds": 2,
            "model_calls": 4,
            "session_duration_minutes": 15,
            "output_tokens_per_call": 4000,
            "maximum_estimated_cost_usd": 15.0,
            "maximum_input_tokens_per_session": 200000,
            "max_concurrent_sessions": "1",
        }
        session_id = str(uuid4())
        polls = iter(
            [
                {"id": session_id, "status": "running", "updated_at": "one", "steps": []},
                {
                    "id": session_id,
                    "status": "ended",
                    "updated_at": "two",
                    "steps": [{"status": "completed"}],
                },
            ]
        )
        calls = []

        def fake_request(_host, _token, method, endpoint, *, params=None, body=None):
            calls.append((method, endpoint, body))
            if endpoint == "/api/cloud-auth/status":
                return {
                    "authenticated": True,
                    "user": {"email": "zetacontinuation@gmail.com", "role": "admin"},
                }
            if endpoint == "/api/projects/inspect":
                return {
                    "project": {
                        "id": project_id,
                        "investigation_type": "military",
                        "ai_model": "gpt-6.1-sol",
                        "reasoning_effort": "high",
                    }
                }
            if endpoint == "/api/projects/proposals/config":
                return {"available": True, "binding": "fixture-binding"}
            if endpoint == "/api/projects/research-limits":
                return limits
            if endpoint == "/api/projects/research-sessions/start":
                assert body is not None
                assert body["expected_limits"] == limits
                assert body["expected_project_id"] == project_id
                assert body["expected_binding"] == "fixture-binding"
                return {"id": session_id, "status": "queued", "steps": []}
            if endpoint.endswith(session_id):
                return next(polls)
            raise AssertionError(f"Unexpected hosted API operation: {method} {endpoint}")

        saved = []

        def fake_export(_host, _token, _project_path, _directory, label):
            target = Path(directory) / f"{label}-{len(saved)}.json"
            target.touch()
            saved.append(target)
            return target

        with (
            patch.object(cloud_cli, "request", side_effect=fake_request),
            patch.object(cloud_cli, "_write_bundle", side_effect=fake_export),
            patch.object(cloud_cli.time, "sleep"),
        ):
            result = cloud_cli.run_session(
                "http://127.0.0.1:5173",
                token_file,
                path,
                ids,
                Path(directory) / "exports",
                required_email="zetacontinuation@gmail.com",
                poll_interval=0,
            )
        assert result["session"]["status"] == "ended"
        assert len(result["artifacts"]) == 3
        assert [call[1] for call in calls].count("/api/projects/research-sessions/start") == 1
        assert all("/api/" in call[1] for call in calls)


def main() -> None:
    test_hosted_project_limit_update_uses_expected_snapshot()
    test_project_setting_update_keeps_current_snapshot()
    test_cloud_cli_requires_https_origin()
    test_export_is_private_complete_and_never_overwritten()
    test_cli_run_uses_authenticated_api_and_exports_each_transition()
    print("Hosted CLI configuration scenarios passed.")


if __name__ == "__main__":
    main()
