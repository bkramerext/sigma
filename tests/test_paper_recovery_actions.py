"""Provider-free Paper removal and user-facing cursor regression checks."""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase, main
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException

from sigma import api
from sigma.projects import ProjectError


class PaperRecoveryActionsTests(TestCase):
    def _body(self, run_id: str | None = None) -> api.PaperDiscardRequest:
        return api.PaperDiscardRequest(
            path="/unused/project.json",
            run_id=run_id,
            expected_project_id="project-1",
            expected_binding="stop-only",
            confirm_discard=True,
        )

    def test_draft_remove_works_without_ai_connection(self) -> None:
        with (
            patch.object(
                api,
                "inspect_project",
                return_value=SimpleNamespace(project=SimpleNamespace(id="project-1")),
            ),
            patch.object(
                api,
                "require_cloud_inference_binding",
                side_effect=AssertionError("Remove must not require AI connection"),
            ),
            patch.object(api.project_collaboration, "require_paper_draft_operator") as acl,
            patch.object(
                api.papers,
                "discard_work",
                new_callable=AsyncMock,
                return_value={"discarded": True},
            ) as discard,
        ):
            result = asyncio.run(api.papers_discard_view(self._body()))
            self.assertEqual(result, {"discarded": True})
            acl.assert_called_once_with("/unused/project.json", "project-1")
            discard.assert_awaited_once_with("/unused/project.json", "project-1")

    def test_run_remove_preserves_creator_authorization(self) -> None:
        run_id = "a" * 32
        with (
            patch.object(
                api,
                "inspect_project",
                return_value=SimpleNamespace(project=SimpleNamespace(id="project-1")),
            ),
            patch.object(
                api.project_collaboration,
                "execution_run",
                side_effect=ProjectError("Only the creator can remove unfinished work"),
            ),
            patch.object(api.papers, "discard_work", new_callable=AsyncMock) as discard,
        ):
            with self.assertRaises(ProjectError):
                asyncio.run(api.papers_discard_view(self._body(run_id)))
            discard.assert_not_awaited()

    def test_owner_may_remove_stopped_collaborator_paper(self) -> None:
        run_id = "a" * 32
        with (
            patch.object(
                api,
                "inspect_project",
                return_value=SimpleNamespace(project=SimpleNamespace(id="project-1")),
            ),
            patch.object(
                api.project_collaboration,
                "execution_run",
                return_value={"run_id": run_id},
            ) as acl,
            patch.object(api.project_collaboration, "is_project_owner", return_value=True),
            patch.object(api.papers, "progress_status", return_value={"status": "cancelled"}),
            patch.object(
                api.papers,
                "discard_work",
                new_callable=AsyncMock,
                return_value={"discarded": True},
            ),
            patch.object(api.project_collaboration, "discard_execution_run") as discard_index,
        ):
            result = asyncio.run(api.papers_discard_view(self._body(run_id)))
            self.assertEqual(result, {"discarded": True})
            acl.assert_called_once_with("/unused/project.json", "paper", run_id)
            discard_index.assert_called_once_with(
                "/unused/project.json", "paper", run_id, owner_terminal=True
            )

    def test_owner_cannot_remove_active_collaborator_paper(self) -> None:
        run_id = "b" * 32

        def verify_access(_path, _kind, _run_id, *, operator=False):
            if operator:
                raise ProjectError("Only the original execution creator may control this run")
            return {"run_id": run_id}

        with (
            patch.object(
                api,
                "inspect_project",
                return_value=SimpleNamespace(project=SimpleNamespace(id="project-1")),
            ),
            patch.object(
                api.project_collaboration,
                "execution_run",
                side_effect=verify_access,
            ),
            patch.object(api.project_collaboration, "is_project_owner", return_value=True),
            patch.object(api.papers, "progress_status", return_value={"status": "active"}),
            patch.object(api.papers, "discard_work", new_callable=AsyncMock) as discard,
        ):
            with self.assertRaises(ProjectError):
                asyncio.run(api.papers_discard_view(self._body(run_id)))
            discard.assert_not_awaited()

    def test_guest_cannot_remove_unpublished_work(self) -> None:
        with (
            patch.object(api.cloud_workspaces, "current", return_value=SimpleNamespace(guest=True)),
            patch.object(api.cloud_workspaces, "enabled", return_value=True),
            patch.object(api.cloud_auth, "current_principal", return_value=None),
            patch.object(api.papers, "discard_work", new_callable=AsyncMock) as discard,
        ):
            with self.assertRaises(HTTPException) as error:
                asyncio.run(api.papers_discard_view(self._body()))
            self.assertEqual(error.exception.status_code, 403)
            discard.assert_not_awaited()

    def test_wrong_project_never_discards(self) -> None:
        with (
            patch.object(
                api,
                "inspect_project",
                return_value=SimpleNamespace(project=SimpleNamespace(id="project-2")),
            ),
            patch.object(api.papers, "discard_work", new_callable=AsyncMock) as discard,
        ):
            with self.assertRaises(HTTPException) as error:
                asyncio.run(api.papers_discard_view(self._body()))
            self.assertEqual(error.exception.status_code, 404)
            discard.assert_not_awaited()


class CursorPolicyTests(TestCase):
    def test_frontend_has_no_prohibited_cursor_styles(self) -> None:
        css = Path(__file__).resolve().parents[1] / "frontend" / "src"
        for path in css.glob("*.css"):
            with self.subTest(file=path.name):
                source = path.read_text(encoding="utf-8").lower()
                self.assertNotIn("cursor: not-allowed", source)
                self.assertNotIn("cursor: no-drop", source)


if __name__ == "__main__":
    main()
