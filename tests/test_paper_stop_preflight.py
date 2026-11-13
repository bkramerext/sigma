"""Paper Stop must remain available when the AI provider is disconnected."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest import TestCase, main
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
                api,
                "inspect_project",
                return_value=SimpleNamespace(project=SimpleNamespace(id="project-1")),
            ),
            patch.object(api.cloud_workspaces, "current", return_value=object()),
            patch.object(
                api.project_collaboration, "execution_run", return_value={"number": 1}
            ) as authorized,
            patch.object(
                api.papers, "cancel_generation", new_callable=AsyncMock, return_value=True
            ) as stopped,
            patch.object(
                api,
                "require_cloud_inference_binding",
                side_effect=AssertionError("Stop must not check the provider connection"),
            ),
        ):
            self.assertEqual(
                asyncio.run(api.paper_cancel_view(self._request())), {"cancelled": True}
            )
            authorized.assert_called_once_with(
                "/unused/project.json", "paper", "a" * 32, operator=True
            )
            stopped.assert_awaited_once_with("/unused/project.json")

    def test_local_stop_ignores_transient_client_run_id(self) -> None:
        """Local generation is project-scoped even when the UI holds a run ID."""
        observed: list[str | None] = []

        def cancel_local(_path: str) -> bool:
            observed.append(api.papers._paper_run_id.get())
            return True

        with (
            patch.object(api.cloud_workspaces, "current", return_value=None),
            patch.object(
                api,
                "inspect_project",
                return_value=SimpleNamespace(project=SimpleNamespace(id="project-1")),
            ),
            patch.object(api.project_collaboration, "require_paper_draft_operator") as authorized,
            patch.object(api.project_collaboration, "execution_run") as wrong_run,
            patch.object(api.papers, "request_cancel_generation", side_effect=cancel_local),
        ):
            request = self._request().model_copy(update={"request_only": True})
            self.assertEqual(asyncio.run(api.paper_cancel_view(request)), {"stop_requested": True})
            self.assertEqual(observed, [None])
            authorized.assert_called_once_with(
                "/unused/project.json", "project-1", controlling_active=True
            )
            wrong_run.assert_not_called()

    def test_local_progress_ignores_transient_client_run_id(self) -> None:
        observed: list[str | None] = []

        def progress_local(_path: str) -> dict[str, str]:
            observed.append(api.papers._paper_run_id.get())
            return {"status": "active", "stage": "proofreading"}

        with (
            patch.object(api.cloud_workspaces, "current", return_value=None),
            patch.object(api.project_collaboration, "execution_run") as wrong_run,
            patch.object(api.papers, "progress_status", side_effect=progress_local),
            patch.object(api.papers, "needs_preflight_on_open", return_value=False),
            patch.object(api.papers, "stop_request_pending", return_value=False),
            patch.object(api.papers, "run_progress_list", return_value=[]),
        ):
            result = api.papers_progress_view("/unused/project.json", "a" * 32)
            self.assertEqual(result["progress"]["stage"], "proofreading")
            self.assertEqual(observed, [None])
            wrong_run.assert_not_called()

    def test_stage_guard_allows_new_generation_without_stop(self) -> None:
        """A normal paper must reach its first progress callback."""
        async def scenario() -> None:
            key = "fresh-paper-fixture"
            with patch.object(api.papers, "_paper_state_key", return_value=key):
                api.papers._stop_requested_keys.discard(key)
                # Both the normal progress callback and earlier internal
                # phase transitions must accept the same guard.
                api.papers._abort_stopping_generation("/unused/project.json")
                api.papers._abort_stopping_generation()

        asyncio.run(scenario())

    def test_stage_guard_blocks_progress_after_accepted_stop(self) -> None:
        """A swallowed cancellation cannot advance a stopped paper."""
        async def scenario() -> None:
            key = "stopped-paper-fixture"
            with patch.object(api.papers, "_paper_state_key", return_value=key):
                api.papers._stop_requested_keys.add(key)
                try:
                    with self.assertRaises(asyncio.CancelledError):
                        api.papers._abort_stopping_generation("/unused/project.json")
                finally:
                    api.papers._stop_requested_keys.discard(key)

        asyncio.run(scenario())

    def test_local_stop_during_proofreading_prevents_later_stages(self) -> None:
        """An accepted Stop cancels the real local worker before PDF and scoring."""

        async def scenario() -> None:
            reached_proofreading = asyncio.Event()
            stages: list[str] = []

            async def fake_generation() -> None:
                stages.append("proofreading")
                reached_proofreading.set()
                await asyncio.Event().wait()
                stages.extend(["generate_pdf", "scoring", "finish"])

            with (
                patch.object(api.cloud_workspaces, "current", return_value=None),
                patch.object(
                    api,
                    "inspect_project",
                    return_value=SimpleNamespace(project=SimpleNamespace(id="project-1")),
                ),
                patch.object(api.project_collaboration, "require_paper_draft_operator"),
                patch.object(api.papers, "_paper_state_key", return_value="local-stop-fixture"),
                patch.object(api.papers, "_write_queue_status"),
                patch.object(api.papers, "_read_queue_status", return_value=None),
                patch.object(api.papers, "_read_reset_ledger", return_value=None),
            ):
                task = asyncio.create_task(fake_generation())
                api.papers.register_submission("/unused/project.json", task)
                await reached_proofreading.wait()
                request = self._request().model_copy(update={"request_only": True})
                self.assertEqual(await api.paper_cancel_view(request), {"stop_requested": True})
                result = await asyncio.gather(task, return_exceptions=True)
                self.assertIsInstance(result[0], asyncio.CancelledError)
                self.assertEqual(stages, ["proofreading"])
                await asyncio.sleep(0)  # clear the tracked submission callback
                self.assertNotIn("local-stop-fixture", api.papers._submission_tasks)

        asyncio.run(scenario())

    def test_wrong_project_identity_cannot_stop(self) -> None:
        with (
            patch.object(
                api,
                "inspect_project",
                return_value=SimpleNamespace(project=SimpleNamespace(id="project-2")),
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
                api,
                "inspect_project",
                return_value=SimpleNamespace(project=SimpleNamespace(id="project-1")),
            ),
            patch.object(api.cloud_workspaces, "current", return_value=object()),
            patch.object(
                api.project_collaboration,
                "execution_run",
                side_effect=ProjectError(
                    "Only the original execution creator may control this run."
                ),
            ),
            patch.object(api.papers, "cancel_generation", new_callable=AsyncMock) as stopped,
        ):
            with self.assertRaises(ProjectError):
                asyncio.run(api.paper_cancel_view(self._request()))
            stopped.assert_not_awaited()


if __name__ == "__main__":
    main()
