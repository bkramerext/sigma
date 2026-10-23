"""Deterministic concurrency, idempotency and accounting tests for Gate B."""

from __future__ import annotations

import asyncio
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from sigma import cloud_research, cloud_workspaces, openai_connection, research_sessions
from sigma.projects import create_strategy, initialize_project


def research_outputs() -> tuple[dict, dict]:
    investigator = {
        "claim": "The saved recurrence gives a candidate bound.",
        "method": "Induct on the recurrence and check the initial value.",
        "assumptions": ["The recurrence is defined for all positive indices."],
        "evidence_status": "Unverified model derivation.",
        "open_obligations": ["Check the equality case."],
        "python_code": None,
        "sage_code": None,
        "prior_session_failure_attempt_ids": [],
        "human_guidance_reviews": [],
        "computational_citations": [],
    }
    skeptic = {
        "assessment": "continue",
        "stop_reason": "recoverable_objection",
        "response": "The induction step needs a separate boundary check.",
        "objections": ["Check the initial value."],
        "remaining_obligations": ["Check the initial value."],
        "next_question": "Verify the first two terms.",
        "objective_status": "partial",
        "solution_claim": "A candidate bound is plausible.",
        "argument_summary": "The inductive step is described but remains unverified.",
        "assumptions_reviewed": ["The recurrence is defined for positive indices."],
        "proof_obligations": ["Check the initial value."],
        "unresolved_objections": ["Check the initial value."],
        "supporting_cycles": [1],
        "verification_status": "incomplete",
        "strategy_contribution": "productive",
        "contribution_rationale": "The induction step narrows the remaining check.",
        "cross_strategy_relations": [],
        "retracted_cross_strategy_source_artifact_ids": [],
        "peer_handoff_reviews": [],
        "human_guidance_reviews": [],
        "computational_citations": [],
    }
    return investigator, skeptic


def job(workspace: str, *, session: str | None = None, key: str | None = None) -> dict:
    return {
        "id": session or str(uuid4()),
        "project_id": "project-" + workspace,
        "idempotency_key": key or str(uuid4()),
        "mode": "api_key",
        "maximum_estimated_cost_usd": 2.0,
        "cost_status": "available",
    }


def workspace(root: Path, identifier: str) -> cloud_workspaces.Workspace:
    path = root / identifier
    path.mkdir(mode=0o700, exist_ok=True)
    return cloud_workspaces.Workspace(identifier, identifier, path)


def global_reserved_spend() -> float:
    db = cloud_research._connect()
    try:
        return float(db.execute("SELECT COALESCE(SUM(amount_usd),0) FROM calls").fetchone()[0])
    finally:
        db.close()


def main() -> None:
    with TemporaryDirectory(prefix="sigma-cloud-research-", dir=Path.cwd().parent) as temp:
        root = Path(temp)
        ledger_root = root / "service"
        ledger_root.mkdir(mode=0o700)
        a = workspace(root, "a" * 32)
        b = workspace(root, "b" * 32)
        settings = {
            "SIGMA_CLOUD_AUTH_ENABLED": "true",
            "SIGMA_CLOUD_GLOBAL_SPEND_CEILING_USD": "1.00",
            "SIGMA_CLOUD_USER_MAX_CONCURRENT": "1",
            "SIGMA_CLOUD_GLOBAL_MAX_CONCURRENT": "1",
            "SIGMA_CLOUD_USER_MAX_QUEUED": "2",
            "SIGMA_CLOUD_GLOBAL_MAX_QUEUED": "2",
            "SIGMA_CLOUD_USER_TOKEN_BUDGET": "1000",
        }
        with patch.dict(
            os.environ,
            {
                "SIGMA_CLOUD_AUTH_ENABLED": "true",
                "OPENAI_API_KEY": "local-operator-key-must-not-be-used",
                "SIGMA_CLOUD_OPENAI_API_KEY": "",
            },
            clear=False,
        ):
            cloud_credential = asyncio.run(openai_connection.auth_context())
            assert cloud_credential["status"] == "unconfigured"
            assert cloud_credential["token"] == ""
        with patch.dict(
            os.environ,
            {
                "SIGMA_CLOUD_AUTH_ENABLED": "true",
                "SIGMA_CLOUD_OPENAI_API_KEY": "explicit-cloud-fixture",
            },
            clear=False,
        ):
            cloud_credential = asyncio.run(openai_connection.auth_context())
            assert cloud_credential["token"] == "explicit-cloud-fixture"
            assert cloud_credential["mode"] == "api_key"
        with (
            patch.dict(os.environ, settings, clear=False),
            patch.object(cloud_workspaces, "storage_root", return_value=ledger_root),
        ):
            token = cloud_workspaces._CURRENT.set(a)
            try:
                first = job(a.workspace_id)
                cloud_research.prepare_job(first)
                assert cloud_research.claim_job(first["id"])
                call = str(uuid4())
                cloud_research.reserve_call(first["id"], call, 0.2, 120)
                try:
                    cloud_research.reserve_call(first["id"], call, 0.2, 120)
                    raise AssertionError("duplicate provider attempt reservation was accepted")
                except cloud_research.CloudResearchUnavailable as exc:
                    assert "already reserved" in str(exc)
                assert cloud_research.snapshot()["user_reserved_and_estimated_usd"] == 0.2
                cloud_research.settle_call(
                    first["id"], call, input_tokens=90, output_tokens=30, estimated_cost_usd=0.001
                )
                summary = cloud_research.snapshot()
                assert summary["user_reserved_and_estimated_usd"] == 0.001
                assert summary["unknown_provider_attempts"] == 0
                not_dispatched = str(uuid4())
                cloud_research.reserve_call(first["id"], not_dispatched, 0.1, 10)
                cloud_research.mark_call_not_dispatched(first["id"], not_dispatched)
                summary = cloud_research.snapshot()
                assert summary["user_reserved_and_estimated_usd"] == 0.001
                assert summary["user_reserved_or_observed_tokens"] == 120

                second = job(a.workspace_id)
                cloud_research.prepare_job(second)
                assert not cloud_research.claim_job(second["id"])
            finally:
                cloud_workspaces._CURRENT.reset(token)

            # A different owner cannot inspect or settle another owner's attempt.
            token = cloud_workspaces._CURRENT.set(b)
            try:
                try:
                    cloud_research.settle_call(
                        first["id"], call, input_tokens=1, output_tokens=1, estimated_cost_usd=0.001
                    )
                    raise AssertionError("cross-workspace attempt settlement succeeded")
                except cloud_research.CloudResearchUnavailable:
                    pass
                assert cloud_research.snapshot()["jobs"].get("queued", 0) == 0
                third = job(b.workspace_id)
                cloud_research.prepare_job(third)
                assert not cloud_research.claim_job(third["id"])
            finally:
                cloud_workspaces._CURRENT.reset(token)

            # Simulate a timeout or process death: unknown usage retains the full
            # reservation and consumes the per-user token budget.
            token = cloud_workspaces._CURRENT.set(a)
            try:
                timeout_call = str(uuid4())
                cloud_research.reserve_call(first["id"], timeout_call, 0.4, 500)
                cloud_research.mark_call_unknown(first["id"], timeout_call)
                summary = cloud_research.snapshot()
                assert summary["user_reserved_and_estimated_usd"] == 0.401
                assert summary["unknown_provider_attempts"] == 1
                try:
                    cloud_research.reserve_call(first["id"], str(uuid4()), 0.1, 501)
                    raise AssertionError("per-user token budget did not fail closed")
                except cloud_research.CloudResearchUnavailable as exc:
                    assert "token budget" in str(exc)

                # Persist a real session record, then simulate a process restart
                # by removing its worker and reconciling the stale running state.
                db = cloud_research._connect()
                db.execute("UPDATE jobs SET status='paused'")
                db.close()
                live_view = initialize_project(
                    a.path / "integrated-session.sigma",
                    "Integrated cloud session",
                    "Check a recurrence bound",
                )
                live_strategy = create_strategy(
                    live_view.path, "Induction", "Derive a recurrence bound and check bases."
                ).project.strategies[0]
                session_limits = {
                    "research_rounds": 1,
                    "model_calls": 2,
                    "session_duration_minutes": 5,
                    "output_tokens_per_call": 256,
                    "maximum_estimated_cost_usd": 1.0,
                }
                research_sessions.save_limits(live_view.path, session_limits)
                credential = {
                    "mode": "api_key",
                    "identity": "cloud_service_api_key",
                    "token": "test-server-key",
                    "status": "connected",
                }
                model_config = {
                    "available": True,
                    "model": "gpt-6.1-sol",
                    "reasoning_effort": "high",
                }
                outputs = research_outputs()

                async def fake_call(record, role, context, timeout_seconds=None):
                    del record, context, timeout_seconds
                    output = outputs[0] if role == "investigator" else outputs[1]
                    return output, {
                        "input_tokens": 90,
                        "cached_input_tokens": 0,
                        "output_tokens": 30,
                    }

                async def run_research() -> dict:
                    key = str(uuid4())
                    with (
                        patch.object(
                            research_sessions,
                            "auth_context",
                            new=AsyncMock(return_value=credential),
                        ),
                        patch.object(
                            research_sessions,
                            "configuration",
                            new=AsyncMock(return_value=model_config),
                        ),
                        patch.object(
                            research_sessions,
                            "execution_capabilities",
                            return_value=[],
                        ),
                        patch.object(
                            research_sessions,
                            "_call",
                            new=AsyncMock(side_effect=fake_call),
                        ) as mocked_call,
                    ):
                        started = await research_sessions.start_session(
                            live_view.path,
                            live_strategy.id,
                            key,
                            live_view.project.id,
                            credential["identity"],
                            session_limits,
                        )
                        # Simulate a process ending just after durable enqueue and
                        # before its task gets CPU. On reconnect, only this queued
                        # no-attempt work is scheduled again.
                        queued_task = research_sessions._tasks.pop(started["id"])
                        research_sessions._control.pop(started["id"], None)
                        queued_task.cancel()
                        await asyncio.gather(queued_task, return_exceptions=True)
                        await research_sessions.ensure_queued_workers(live_view.path)
                        for _ in range(300):
                            current = research_sessions.get_session(live_view.path, started["id"])
                            if current["status"] in {"ended", "failed", "paused"}:
                                break
                            await asyncio.sleep(0.01)
                        else:
                            raise AssertionError("integrated cloud session did not finish")
                        duplicate = await research_sessions.start_session(
                            live_view.path,
                            live_strategy.id,
                            key,
                            live_view.project.id,
                            credential["identity"],
                            session_limits,
                        )
                        assert duplicate["id"] == started["id"]
                        assert mocked_call.await_count == 2, (
                            mocked_call.await_count,
                            current["status"],
                            current["calls_used"],
                            current["message"],
                            current["events"],
                        )
                        assert current["calls_used"] == 2
                        assert all(
                            step["attempt_status"] == "usage_estimated" for step in current["steps"]
                        )
                        return current

                with patch.dict(os.environ, {"SIGMA_CLOUD_USER_TOKEN_BUDGET": "1000000"}):
                    integrated = asyncio.run(run_research())
                assert integrated["status"] == "ended"
                assert len(integrated["artifacts"]) == 1
                assert cloud_research.snapshot()["user_reserved_and_estimated_usd"] < 1.0

                async def run_ambiguous_failure() -> None:
                    key = str(uuid4())
                    with (
                        patch.object(
                            research_sessions,
                            "auth_context",
                            new=AsyncMock(return_value=credential),
                        ),
                        patch.object(
                            research_sessions,
                            "configuration",
                            new=AsyncMock(return_value=model_config),
                        ),
                        patch.object(
                            research_sessions,
                            "execution_capabilities",
                            return_value=[],
                        ),
                        patch.object(
                            research_sessions,
                            "_call",
                            new=AsyncMock(side_effect=TimeoutError("provider timed out")),
                        ) as mocked_call,
                    ):
                        started = await research_sessions.start_session(
                            live_view.path,
                            live_strategy.id,
                            key,
                            live_view.project.id,
                            credential["identity"],
                            session_limits,
                        )
                        for _ in range(300):
                            failed = research_sessions.get_session(live_view.path, started["id"])
                            if failed["status"] in {"ended", "failed", "paused"}:
                                break
                            await asyncio.sleep(0.01)
                        else:
                            raise AssertionError("timed-out cloud call did not reach a saved state")
                        assert failed["status"] == "failed"
                        assert failed["steps"][0]["attempt_status"] == "unknown"
                        duplicate = await research_sessions.start_session(
                            live_view.path,
                            live_strategy.id,
                            key,
                            live_view.project.id,
                            credential["identity"],
                            session_limits,
                        )
                        assert duplicate["id"] == started["id"]
                        assert mocked_call.await_count == 1
                        db = cloud_research._connect()
                        persisted = db.execute(
                            "SELECT status FROM calls WHERE call_id=?",
                            (failed["steps"][0]["id"],),
                        ).fetchone()[0]
                        db.close()
                        assert persisted == "unknown"

                with patch.dict(os.environ, {"SIGMA_CLOUD_USER_TOKEN_BUDGET": "1000000"}):
                    asyncio.run(run_ambiguous_failure())

                async def run_cancelled_call() -> None:
                    key = str(uuid4())
                    dispatched = asyncio.Event()

                    async def hang(record, role, context, timeout_seconds=None):
                        del record, role, context, timeout_seconds
                        dispatched.set()
                        await asyncio.Future()

                    with (
                        patch.object(
                            research_sessions,
                            "auth_context",
                            new=AsyncMock(return_value=credential),
                        ),
                        patch.object(
                            research_sessions,
                            "configuration",
                            new=AsyncMock(return_value=model_config),
                        ),
                        patch.object(
                            research_sessions,
                            "execution_capabilities",
                            return_value=[],
                        ),
                        patch.object(
                            research_sessions, "_call", new=AsyncMock(side_effect=hang)
                        ) as mocked_call,
                    ):
                        started = await research_sessions.start_session(
                            live_view.path,
                            live_strategy.id,
                            key,
                            live_view.project.id,
                            credential["identity"],
                            session_limits,
                        )
                        try:
                            await asyncio.wait_for(dispatched.wait(), timeout=5)
                        except TimeoutError as exc:
                            current = research_sessions.get_session(live_view.path, started["id"])
                            raise AssertionError(
                                f"cloud call did not dispatch: {current['status']} calls={current['calls_used']} "
                                f"{current['message']} events={current['events']}"
                            ) from exc
                        paused = await research_sessions.control_session(
                            live_view.path, started["id"], "pause"
                        )
                        assert paused["status"] == "paused"
                        assert paused["steps"][0]["attempt_status"] == "unknown"
                        assert mocked_call.await_count == 1
                        db = cloud_research._connect()
                        persisted = db.execute(
                            "SELECT status FROM calls WHERE call_id=?",
                            (paused["steps"][0]["id"],),
                        ).fetchone()[0]
                        db.close()
                        assert persisted == "unknown"

                with patch.dict(os.environ, {"SIGMA_CLOUD_USER_TOKEN_BUDGET": "1000000"}):
                    asyncio.run(run_cancelled_call())

                view = initialize_project(
                    a.path / "restart-proof.sigma", "Restart proof", "A bounded question"
                )
                interrupted = job(a.workspace_id)
                interrupted["project_id"] = view.project.id
                interrupted.update(
                    {
                        "project_path": view.path,
                        "status": "queued",
                        "created_at": "2026-01-01T00:00:00+00:00",
                        "updated_at": "2026-01-01T00:00:00+00:00",
                        "steps": [
                            {
                                "id": str(uuid4()),
                                "role": "investigator",
                                "status": "running",
                                "attempt_status": "reserved",
                            }
                        ],
                        "strategy_runs": [],
                        "events": [],
                        "current_step": None,
                        "current_steps": [],
                        "mode": "api_key",
                        "estimated_cost_usd": 0.0,
                    }
                )
                research_sessions._tasks.pop(interrupted["id"], None)
                cloud_research.prepare_job(interrupted)
                assert cloud_research.claim_job(interrupted["id"])
                interrupted["status"] = "running"
                research_sessions._save(view.path, interrupted)
                attempt_id = interrupted["steps"][0]["id"]
                with patch.dict(os.environ, {"SIGMA_CLOUD_USER_TOKEN_BUDGET": "1000000"}):
                    cloud_research.reserve_call(interrupted["id"], attempt_id, 0.1, 20)
                recovered = research_sessions._recover(interrupted)
                assert recovered["status"] == "paused"
                assert recovered["steps"][0]["status"] == "interrupted"
                assert recovered["steps"][0]["attempt_status"] == "unknown"
                db = cloud_research._connect()
                status = db.execute(
                    "SELECT status FROM jobs WHERE session_id=?", (interrupted["id"],)
                ).fetchone()[0]
                attempt_status = db.execute(
                    "SELECT status FROM calls WHERE call_id=?", (attempt_id,)
                ).fetchone()[0]
                db.close()
                assert status == "interrupted" and attempt_status == "unknown"
            finally:
                cloud_workspaces._CURRENT.reset(token)

        # Concurrent owners race for one global execution slot. SQLite's
        # BEGIN IMMEDIATE transaction must admit exactly one claimant.
        with (
            patch.dict(os.environ, settings, clear=False),
            patch.object(cloud_workspaces, "storage_root", return_value=ledger_root),
        ):
            # Clear prior slots to isolate this race while retaining spend history.
            db = cloud_research._connect()
            db.execute("UPDATE jobs SET status='paused'")
            db.close()
            jobs = [job(a.workspace_id), job(b.workspace_id)]
            for record in jobs:
                token = cloud_workspaces._CURRENT.set(
                    a if record["project_id"].endswith("a" * 32) else b
                )
                try:
                    cloud_research.prepare_job(record)
                finally:
                    cloud_workspaces._CURRENT.reset(token)

            barrier = threading.Barrier(2)

            def claim(record: dict, owner: cloud_workspaces.Workspace) -> bool:
                context = cloud_workspaces._CURRENT.set(owner)
                try:
                    barrier.wait(timeout=5)
                    return cloud_research.claim_job(record["id"])
                finally:
                    cloud_workspaces._CURRENT.reset(context)

            with ThreadPoolExecutor(max_workers=2) as pool:
                results = [pool.submit(claim, record, owner) for record, owner in zip(jobs, (a, b))]
                claimed = [future.result(timeout=10) for future in results]
            assert sorted(claimed) == [False, True], claimed

        spend_root = root / "spend-ledger"
        spend_root.mkdir(mode=0o700)
        with (
            patch.dict(
                os.environ,
                {**settings, "SIGMA_CLOUD_GLOBAL_MAX_CONCURRENT": "2"},
                clear=False,
            ),
            patch.object(cloud_workspaces, "storage_root", return_value=spend_root),
        ):
            spend_jobs = [job(a.workspace_id), job(b.workspace_id)]
            for record, owner in zip(spend_jobs, (a, b)):
                token = cloud_workspaces._CURRENT.set(owner)
                try:
                    cloud_research.prepare_job(record)
                    assert cloud_research.claim_job(record["id"])
                finally:
                    cloud_workspaces._CURRENT.reset(token)

            barrier = threading.Barrier(2)

            def reserve(record: dict, owner: cloud_workspaces.Workspace) -> bool:
                context = cloud_workspaces._CURRENT.set(owner)
                try:
                    barrier.wait(timeout=5)
                    cloud_research.reserve_call(record["id"], str(uuid4()), 0.6, 100)
                    return True
                except cloud_research.CloudResearchUnavailable:
                    return False
                finally:
                    cloud_workspaces._CURRENT.reset(context)

            with ThreadPoolExecutor(max_workers=2) as pool:
                futures = [
                    pool.submit(reserve, record, owner) for record, owner in zip(spend_jobs, (a, b))
                ]
                admitted = [future.result(timeout=10) for future in futures]
            assert sorted(admitted) == [False, True], admitted
            owner_token = cloud_workspaces._CURRENT.set(a)
            try:
                assert global_reserved_spend() == 0.6
            finally:
                cloud_workspaces._CURRENT.reset(owner_token)

    print(
        "PASS cloud research durable admission, owner scope, atomic limits, duplicate reservation and unknown-cost accounting"
    )


if __name__ == "__main__":
    main()
