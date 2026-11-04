"""Provider-free project diagnostic persistence, pre-session failures, and export parity."""

from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path
from fastapi.responses import JSONResponse
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from sigma import api, project_diagnostics, session_log
from sigma.projects import ProjectError


def test_project_errors_survive_reload_without_creating_sessions(tmp_path: Path) -> None:
    tmp_path.mkdir(parents=True, exist_ok=True)
    project_file = tmp_path / "project.json"
    project_file.write_text('{"fixture": true}', encoding="utf-8")
    project_id = "c840b847-e508-4809-9663-c51d9ae2d6e5"
    with (
        patch.object(
            project_diagnostics,
            "inspect_project",
            return_value=SimpleNamespace(project=SimpleNamespace(id=project_id)),
        ),
        patch.object(project_diagnostics.cloud_workspaces, "current", return_value=None),
    ):
        one = project_diagnostics.append(
            str(project_file),
            stage="admission",
            code="reference_http_404",
            message="Reference unavailable: HTTP 404. Bearer supersecret api_key=secret123",
            http_status=404,
            reference_url="https://example.org/missing?token=private",
        )
        two = project_diagnostics.append(
            str(project_file),
            stage="retrieval",
            code="reference_oversized",
            message="Source exceeded retrieval size limit. sk-0123456789abcdefghijk",
        )
        loaded = project_diagnostics.read(str(project_file))
        assert [entry["id"] for entry in loaded] == [one["id"], two["id"]]
        assert all(entry["session_id"] is None for entry in loaded)
        export = project_diagnostics.export(str(project_file))
        assert "none (pre-session)" in export
        assert "reference_http_404" in export
        assert "reference_oversized" in export
        assert one["id"] in export and two["id"] in export
        assert "supersecret" not in export
        assert "secret123" not in export
        assert "private" not in export
        assert "sk-0123456789abcdefghijk" not in export
        assert "[REDACTED]" in export
        # Neither the writer nor export path creates a research session.
        assert not list(tmp_path.glob("*.session.json"))


def test_client_report_and_copy_download_share_canonical_record(tmp_path: Path) -> None:
    tmp_path.mkdir(parents=True, exist_ok=True)
    project_file = tmp_path / "project.json"
    project_file.touch()
    with (
        patch.object(
            project_diagnostics,
            "inspect_project",
            return_value=SimpleNamespace(
                project=SimpleNamespace(id="40a094e9-0cad-4b63-96c0-fd9c2b2c30de")
            ),
        ),
        patch.object(project_diagnostics.cloud_workspaces, "current", return_value=None),
    ):
        request = api.ClientDiagnosticRequest(
            path=str(project_file),
            stage="browser",
            code="browser_request_failed",
            message="Browser could not fetch response.",
            correlation_id="browser-123",
        )
        reply = api.record_project_diagnostic(request)
        assert isinstance(reply, dict)
        assert reply["recorded"] is True
        persisted = api.project_diagnostics_view(str(project_file))["diagnostics"][0]
        assert reply["diagnostic"] == persisted
        downloaded = api.project_diagnostics_download(str(project_file))
        assert persisted["id"].encode() in downloaded.body
        assert persisted["message"].encode() in downloaded.body
        assert b"browser-123" in downloaded.body


def test_logging_failure_is_reported_without_breaking_admission(tmp_path: Path) -> None:
    tmp_path.mkdir(parents=True, exist_ok=True)
    project_file = tmp_path / "project.json"
    project_file.touch()
    with (
        patch.object(
            project_diagnostics,
            "inspect_project",
            return_value=SimpleNamespace(
                project=SimpleNamespace(id="40a094e9-0cad-4b63-96c0-fd9c2b2c30de")
            ),
        ),
        patch.object(project_diagnostics.cloud_workspaces, "current", return_value=None),
        patch.object(project_diagnostics, "MAX_BYTES", 120),
    ):
        result = api.record_project_diagnostic(
            api.ClientDiagnosticRequest(
                path=str(project_file),
                stage="browser",
                code="browser_request_failed",
                message="unavailable",
            )
        )
        assert isinstance(result, JSONResponse)
        assert result.status_code == 503
        assert b'"recorded":false' in result.body


def test_pre_session_rejection_persists_same_sanitized_error(tmp_path: Path) -> None:
    tmp_path.mkdir(parents=True, exist_ok=True)
    project_file = tmp_path / "project.json"
    project_file.touch()
    project_id = "40a094e9-0cad-4b63-96c0-fd9c2b2c30de"
    body = api.ResearchStartRequest(
        path=str(project_file),
        strategy_id="strategy",
        idempotency_key="f491f31f-5bb0-494d-9075-f77b0d93b837",
        expected_project_id=project_id,
        expected_binding="test-binding",
        expected_limits=None,
        strategy_ids=["strategy"],
        continue_using_saved_type_settings=False,
    )
    with (
        patch.object(
            project_diagnostics,
            "inspect_project",
            return_value=SimpleNamespace(project=SimpleNamespace(id=project_id)),
        ),
        patch.object(project_diagnostics.cloud_workspaces, "current", return_value=None),
        patch.object(
            api.research_sessions,
            "start_session",
            new=AsyncMock(side_effect=ProjectError("Retrieval HTTP 404 api_key=verysecret")),
        ),
    ):
        response = asyncio.run(api.research_start_view(body))
        assert isinstance(response, JSONResponse)
        data = json.loads(bytes(response.body))
        saved = project_diagnostics.read(str(project_file))
        repeated = project_diagnostics.append(
            str(project_file),
            stage="admission",
            code="research_admission_failed",
            message="Retrieval HTTP 404 api_key=verysecret",
            correlation_id=body.idempotency_key,
            http_status=400,
        )
        assert repeated == saved[0]
        assert project_diagnostics.read(str(project_file)) == saved
        assert response.status_code == 400
        assert len(saved) == 1
        assert data["diagnostic_recorded"] is True
        assert data["diagnostic"] == saved[0]
        assert data["error"] == saved[0]["message"]
        assert "verysecret" not in data["error"]


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="sigma-project-diagnostics-") as directory:
        root = Path(directory)
        test_project_errors_survive_reload_without_creating_sessions(root / "project")
        test_client_report_and_copy_download_share_canonical_record(root / "client")
        test_logging_failure_is_reported_without_breaking_admission(root / "capacity")
        test_pre_session_rejection_persists_same_sanitized_error(root / "admission")
    print("Project diagnostics persistence, redaction, admission and copy/download parity passed.")


if __name__ == "__main__":
    main()
