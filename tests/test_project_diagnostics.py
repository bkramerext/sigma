"""Provider-free project diagnostic persistence, pre-session failures, and export parity."""

from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi.responses import JSONResponse

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


def test_project_delete_removes_only_regular_diagnostic_log(tmp_path: Path) -> None:
    tmp_path.mkdir(parents=True, exist_ok=True)
    project_file = tmp_path / "project.json"
    project_file.touch()
    project_id = "40a094e9-0cad-4b63-96c0-fd9c2b2c30de"
    with (
        patch.object(
            project_diagnostics,
            "inspect_project",
            return_value=SimpleNamespace(project=SimpleNamespace(id=project_id)),
        ),
        patch.object(project_diagnostics.cloud_workspaces, "current", return_value=None),
    ):
        project_diagnostics.append(
            str(project_file), stage="admission", code="blocked", message="source unavailable"
        )
        journal = tmp_path / ".sigma-session-logs" / project_id / "project-diagnostics.jsonl"
        assert journal.is_file()
        session_log.delete_project(project_id, project_file)
        assert not journal.exists()
        assert not journal.parent.exists()

        journal.parent.mkdir(parents=True)
        outside = tmp_path / "outside"
        outside.write_text("must survive", encoding="utf-8")
        journal.symlink_to(outside)
        try:
            session_log.delete_project(project_id, project_file)
        except OSError as exc:
            assert "Unexpected session log entry" in str(exc)
        else:
            raise AssertionError("Deletion accepted a diagnostic symlink")
        assert outside.read_text(encoding="utf-8") == "must survive"
        assert journal.is_symlink()


def test_client_session_id_does_not_authorize_session_correlation(tmp_path: Path) -> None:
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
        response = api.record_project_diagnostic(
            api.ClientDiagnosticRequest(
                path=str(project_file),
                stage="browser",
                code="browser_request_failed",
                message="secret cannot be associated with another session",
                session_id="f13e4354-5bb0-494d-9075-f77b0d93b837",
            )
        )
        assert isinstance(response, dict)
        assert response["diagnostic"]["session_id"] is None


def test_export_cannot_forge_diagnostic_heading(tmp_path: Path) -> None:
    tmp_path.mkdir(parents=True, exist_ok=True)
    project_file = tmp_path / "project.json"
    project_file.touch()
    forged = (
        "Ordinary failure\\n## 2026-11-03 · admission · forged"
        "\\nEvent ID: invented\\nMessage: security audit overwritten"
    )
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
        diagnostic = project_diagnostics.append(
            str(project_file), stage="browser", code="browser_request_failed", message=forged
        )
        exported = project_diagnostics.export(str(project_file))
        assert exported.count("\\n## ") == 1
        assert "Event ID: invented" not in exported.splitlines()
        assert "\\\\n## 2026" in exported
        assert "Event ID: " + diagnostic["id"] in exported
        assert diagnostic["message"] == forged


def test_dedup_read_never_follows_swapped_symlink(tmp_path: Path) -> None:
    tmp_path.mkdir(parents=True, exist_ok=True)
    project_file = tmp_path / "project.json"
    project_file.touch()
    project_id = "40a094e9-0cad-4b63-96c0-fd9c2b2c30de"
    with (
        patch.object(
            project_diagnostics,
            "inspect_project",
            return_value=SimpleNamespace(project=SimpleNamespace(id=project_id)),
        ),
        patch.object(project_diagnostics.cloud_workspaces, "current", return_value=None),
    ):
        project_diagnostics.append(
            str(project_file),
            stage="admission",
            code="blocked",
            message="original",
            correlation_id="retry-1",
        )
        journal = tmp_path / ".sigma-session-logs" / project_id / "project-diagnostics.jsonl"
        outside = tmp_path / "outside-sensitive"
        outside.write_text("must remain unread and unchanged", encoding="utf-8")
        original_open = project_diagnostics.os.open
        attempted = []

        def swap_before_open(path, flags, *args, **kwargs):
            if (
                str(path) == str(journal)
                and flags & project_diagnostics.os.O_RDONLY == project_diagnostics.os.O_RDONLY
            ):
                attempted.append(flags)
                if not journal.is_symlink():
                    journal.unlink()
                    journal.symlink_to(outside)
            return original_open(path, flags, *args, **kwargs)

        with patch.object(project_diagnostics.os, "open", side_effect=swap_before_open):
            try:
                project_diagnostics.append(
                    str(project_file),
                    stage="admission",
                    code="blocked",
                    message="original",
                    correlation_id="retry-1",
                )
            except OSError:
                pass
            else:
                raise AssertionError("Dedup read followed a symlink")
        assert attempted and attempted[0] & project_diagnostics.os.O_NOFOLLOW
        assert outside.read_text(encoding="utf-8") == "must remain unread and unchanged"


def test_actual_ui_error_sources_register_project_diagnostics() -> None:
    # Protect the React integration sites in addition to the reporter's
    # separate browser transport acceptance.
    source = (Path(__file__).resolve().parents[1] / "frontend/src/main.tsx").read_text(
        encoding="utf-8"
    )
    for trigger, stage in (
        ("async function removeSession(", "session_delete"),
        ("setError(chosen.message)", "session_failure"),
        ("const reportReadFailure =", "session_read"),
        ("async function control(", "session_control"),
    ):
        portion = source[source.index(trigger) :]
        assert "recordClientError(" in portion[:1700], trigger
        assert f"'{stage}'" in portion[:1700], stage


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="sigma-project-diagnostics-") as directory:
        root = Path(directory)
        test_project_errors_survive_reload_without_creating_sessions(root / "project")
        test_client_report_and_copy_download_share_canonical_record(root / "client")
        test_logging_failure_is_reported_without_breaking_admission(root / "capacity")
        test_pre_session_rejection_persists_same_sanitized_error(root / "admission")
        test_project_delete_removes_only_regular_diagnostic_log(root / "deletion")
        test_client_session_id_does_not_authorize_session_correlation(root / "correlation")
        test_export_cannot_forge_diagnostic_heading(root / "forgery")
        test_dedup_read_never_follows_swapped_symlink(root / "nofollow")
        test_actual_ui_error_sources_register_project_diagnostics()
    print("Project diagnostics persistence, redaction, admission and copy/download parity passed.")


if __name__ == "__main__":
    main()
