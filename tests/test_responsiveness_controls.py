"""Provider-free responsiveness and cancellation-ownership regression checks."""

from __future__ import annotations

import asyncio
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase, main
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from sigma import api, papers, research_sessions


class ResponsiveControlTests(TestCase):
    def test_session_stop_receipt_precedes_slow_worker_cleanup(self) -> None:
        async def scenario() -> None:
            session_id = str(uuid4())
            record = {
                "id": session_id,
                "project_path": "test-project",
                "status": "running",
                "current_action": "Investigator",
                "calls_used": 1,
                "strategy_runs": [],
                "events": [],
            }
            entered = asyncio.Event()
            releasing = asyncio.Event()
            finished = asyncio.Event()
            saved = []

            async def provider_worker() -> None:
                entered.set()
                try:
                    await asyncio.Event().wait()
                except asyncio.CancelledError:
                    await releasing.wait()
                    finished.set()
                    raise

            task = asyncio.create_task(provider_worker())
            await entered.wait()
            try:
                with (
                    patch.object(research_sessions, "_read", return_value=deepcopy(record)),
                    patch.object(research_sessions, "_recover", side_effect=lambda value: value),
                    patch.object(
                        research_sessions,
                        "_save",
                        side_effect=lambda _path, value: saved.append(deepcopy(value)),
                    ),
                    patch.object(research_sessions, "_event"),
                    patch.object(research_sessions, "_public", side_effect=lambda value: value),
                    patch.dict(research_sessions._tasks, {session_id: task}),
                    patch.dict(research_sessions._control, {session_id: asyncio.Event()}),
                ):
                    receipt = await asyncio.wait_for(
                        research_sessions.control_session(
                            "test-project", session_id, "stop", acknowledge_only=True
                        ),
                        timeout=3,
                    )
                    self.assertEqual(receipt["status"], "stopped")
                    self.assertEqual(saved[-1]["status"], "stopped")
                    self.assertFalse(finished.is_set(), "Stop waited for slow provider cleanup")
                    self.assertGreater(task.cancelling(), 0)
            finally:
                releasing.set()
                await asyncio.gather(task, return_exceptions=True)

        asyncio.run(scenario())

    def test_paper_stop_request_is_idempotent_and_run_isolated(self) -> None:
        async def scenario(path: str) -> None:
            first_run, second_run = uuid4().hex, uuid4().hex
            entered = asyncio.Event()
            releasing = asyncio.Event()

            async def slow_worker() -> None:
                entered.set()
                try:
                    await asyncio.Event().wait()
                except asyncio.CancelledError:
                    await releasing.wait()
                    raise

            async def other_worker() -> None:
                await asyncio.Event().wait()

            first = asyncio.create_task(slow_worker())
            second = asyncio.create_task(other_worker())
            try:
                with papers.paper_run_scope(first_run):
                    first_key = papers._paper_state_key(path)
                with papers.paper_run_scope(second_run):
                    second_key = papers._paper_state_key(path)
                with patch.dict(papers._submission_tasks, {first_key: first, second_key: second}):
                    await entered.wait()
                    with papers.paper_run_scope(first_run):
                        self.assertTrue(papers.request_cancel_generation(path))
                        self.assertTrue(papers.request_cancel_generation(path))
                    self.assertEqual(first.cancelling(), 1, "Repeated Stop interrupted cleanup")
                    self.assertFalse(first.done(), "A Stop request was mistaken for completion")
                    self.assertFalse(second.cancelling(), "Stopped a different creator's Paper")
            finally:
                releasing.set()
                second.cancel()
                await asyncio.gather(first, second, return_exceptions=True)

        with TemporaryDirectory() as directory:
            project = Path(directory) / "research.sigma"
            project.mkdir()
            asyncio.run(scenario(str(project)))

    def test_solo_and_multirun_paper_stop_ack_uses_authorization(self) -> None:
        for run_id in (None, "a" * 32):
            with self.subTest(run_id=run_id):
                body = api.PaperCancelRequest(
                    path="/unused/project.json",
                    run_id=run_id,
                    expected_project_id="project-1",
                    expected_binding="stop-only",
                    request_only=True,
                )
                with (
                    patch.object(
                        api,
                        "inspect_project",
                        return_value=SimpleNamespace(project=SimpleNamespace(id="project-1")),
                    ),
                    patch.object(api.project_collaboration, "execution_run") as run_acl,
                    patch.object(
                        api.project_collaboration, "require_paper_draft_operator"
                    ) as draft_acl,
                    patch.object(
                        api.papers, "request_cancel_generation", return_value=True
                    ) as stop,
                    patch.object(
                        api,
                        "require_cloud_inference_binding",
                        side_effect=AssertionError("Stop must not require provider authorization"),
                    ),
                ):
                    self.assertEqual(
                        asyncio.run(api.paper_cancel_view(body)),
                        {"stop_requested": True},
                    )
                    stop.assert_called_once_with(body.path)
                    if run_id is None:
                        draft_acl.assert_called_once()
                        run_acl.assert_not_called()
                    else:
                        run_acl.assert_called_once()
                        draft_acl.assert_not_called()

    def test_session_control_api_propagates_fast_ack_after_acl(self) -> None:
        session_id = str(uuid4())
        body = api.ResearchControlRequest(
            path="/unused/project.json", action="stop", request_only=True
        )
        request = SimpleNamespace(state=SimpleNamespace(cloud_principal=None))
        with (
            patch.object(api.project_collaboration, "require_execution_operator") as acl,
            patch.object(api.project_collaboration, "note_artifact_author") as author,
            patch.object(api.cloud_auth, "_mock_enabled", return_value=False),
            patch.object(api.cloud_auth, "config", return_value=SimpleNamespace()),
            patch.object(
                api.research_sessions,
                "control_session",
                new_callable=AsyncMock,
                return_value={"status": "stopped"},
            ) as stop,
        ):
            self.assertEqual(
                asyncio.run(api.research_control_view(session_id, body, request)),
                {"status": "stopped"},
            )
            acl.assert_called_once()
            author.assert_called_once()
            self.assertTrue(stop.await_args.kwargs["acknowledge_only"])


if __name__ == "__main__":
    main()
