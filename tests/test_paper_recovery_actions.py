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
