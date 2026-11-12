"""Paper Stop must remain available when the AI provider is disconnected."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException

from sigma import api
from sigma.projects import ProjectError


class PaperStopPreflightTests(TestCase):
    def _request(self, project_id: str = "project-1") -> api.PaperCancelRequest:
        return api.PaperCancelRequest(
            path="/unused/project.json",
            run_id="a" * 32,
            expected_project_id=project_id,
            expected_binding="stop-only",
        )

    def test_authorized_stop_does_not_depend_on_connected_provider(self) -> None:
        with (
            patch.object(
                api, "inspect_project", return_value=SimpleNamespace(project=SimpleNamespace(id="project-1"))
            ),
            patch.object(api.project_collaboration, "execution_run", return_value={"number": 1}) as authorized,
            patch.object(api.papers, "cancel_generation", new_callable=AsyncMock, return_value=True) as stopped,
            patch.object(
                api, "require_cloud_inference_binding",
                side_effect=AssertionError("Stop must not check the provider connection"),
            ),
        ):
            self.assertEqual(asyncio.run(api.paper_cancel_view(self._request())), {"cancelled": True})
            authorized.assert_called_once_with("/unused/project.json", "paper", "a" * 32, operator=True)
            stopped.assert_awaited_once_with("/unused/project.json")

    def test_wrong_project_identity_cannot_stop(self) -> None:
        with (
            patch.object(
                api, "inspect_project", return_value=SimpleNamespace(project=SimpleNamespace(id="project-2"))
            ),
            patch.object(api.papers, "cancel_generation", new_callable=AsyncMock) as stopped,
        ):
            with self.assertRaises(HTTPException) as error:
                asyncio.run(api.paper_cancel_view(self._request()))
            self.assertEqual(error.exception.status_code, 404)
            stopped.assert_not_awaited()

    def test_non_creator_still_cannot_stop(self) -> None:
        with (
            patch.object(
                api, "inspect_project", return_value=SimpleNamespace(project=SimpleNamespace(id="project-1"))
            ),
            patch.object(
                api.project_collaboration, "execution_run",
                side_effect=ProjectError("Only the original execution creator may control this run."),
            ),
            patch.object(api.papers, "cancel_generation", new_callable=AsyncMock) as stopped,
        ):
            with self.assertRaises(ProjectError):
                asyncio.run(api.paper_cancel_view(self._request()))
            stopped.assert_not_awaited()
