"""Deterministic concurrency, idempotency and accounting tests for Gate B."""

from __future__ import annotations

import asyncio
import fcntl
import json
import os
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from sigma import cloud_research, cloud_workspaces, openai_connection, research_sessions
from sigma.projects import (
    ProjectError,
    create_strategy,
    export_complete_project,
    initialize_project,
)


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
        "maximum_estimated_cost_usd": 0.25,
        "call_limit": 6,
        "duration_limit_minutes": 15,
        "cost_status": "available",
    }


def workspace(root: Path, identifier: str, email: str | None = None) -> cloud_workspaces.Workspace:
    path = root / identifier
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    return cloud_workspaces.Workspace(identifier, identifier, path, email)


def global_reserved_spend() -> float:
    db = cloud_research._connect()
    try:
        return float(db.execute("SELECT COALESCE(SUM(amount_usd),0) FROM calls").fetchone()[0])
    finally:
        db.close()


def test_orphaned_job_reconciliation(
    root: Path,
    ledger_root: Path,
    limits_env: dict[str, str],
) -> None:
    """Fault-inject the prepare/record-publication gap and recover conservatively."""
    project_root = root / "orphan-recovery-projects"
    project_root.mkdir(mode=0o700)
    workspace_a = workspace(project_root, "c" * 32)
    workspace_b = workspace(project_root, "d" * 32)
    with (
        patch.dict(
            os.environ,
            {
                **limits_env,
                # This suite injects several independent historical jobs to
                # test recovery, not the hosted execution-capacity boundary.
                "SIGMA_CLOUD_USER_MAX_CONCURRENT": "8",
                "SIGMA_CLOUD_GLOBAL_MAX_CONCURRENT": "32",
                "SIGMA_CLOUD_USER_MAX_QUEUED": "2",
                "SIGMA_CLOUD_GLOBAL_MAX_QUEUED": "8",
                "SIGMA_CLOUD_USER_TOKEN_BUDGET": "1000000",
            },
            clear=False,
        ),
        patch.object(cloud_workspaces, "storage_root", return_value=ledger_root),
    ):
        binding = cloud_workspaces._CURRENT.set(workspace_a)
        try:
            project = initialize_project(
                workspace_a.path / "reconcile.sigma", "Reconciliation", "Check queue recovery"
            )
            strategy = create_strategy(
                project.path, "Direct", "Check a saved finite recurrence."
            ).project.strategies[0]
            session_limits = {
                "research_rounds": 1,
                "model_calls": 2,
                "session_duration_minutes": 5,
                "output_tokens_per_call": 256,
                "maximum_estimated_cost_usd": 0.25,
            }
            research_sessions.save_limits(project.path, session_limits)
            credential = {
                "mode": "api_key",
                "identity": "cloud_service_api_key:" + workspace_a.subject_hash,
                "token": "test-server-key",
                "status": "connected",
            }
            model_config = {
                "available": True,
                "model": "gpt-6.1-sol",
                "reasoning_effort": "high",
            }
            idempotency_key = str(uuid4())
            captured: dict[str, Any] = {}

            def crash_before_save(path: str, record: dict[str, Any]) -> None:
                del path
                captured.update(json.loads(json.dumps(record)))
                raise RuntimeError("injected crash after durable prepare_job")

            async def initial_start_crash() -> None:
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
                    patch.object(research_sessions, "execution_capabilities", return_value=[]),
                    patch.object(research_sessions, "_save", side_effect=crash_before_save),
                ):
                    try:
                        await research_sessions.start_session(
                            project.path,
                            strategy.id,
                            idempotency_key,
                            project.project.id,
                            credential["identity"],
                            session_limits,
                        )
                    except RuntimeError as exc:
                        assert "injected crash" in str(exc)
                    else:
                        raise AssertionError("fault injection did not interrupt after prepare_job")

            asyncio.run(initial_start_crash())
            orphan_id = captured["id"]
            orphan_record = Path(project.path) / "research-sessions" / f"{orphan_id}.json"
            assert not orphan_record.exists()
            db = cloud_research._connect()
            orphan = db.execute(
                "SELECT status,process_epoch,project_relpath FROM jobs WHERE session_id=?",
                (orphan_id,),
            ).fetchone()
            assert orphan and orphan["status"] == "queued" and orphan["project_relpath"]
            assert (
                db.execute("SELECT 1 FROM calls WHERE session_id=?", (orphan_id,)).fetchone()
                is None
            )
            old_epoch = orphan["process_epoch"]
            db.close()

            # Reconnect after a new server epoch. The orphan disappears before
            # the same idempotent request is retried; only the retried job runs.
            next_epoch = uuid4().hex
            outputs = research_outputs()
            dispatched_roles: list[str] = []

            async def retry_call(record, role, context, timeout_seconds=None, step_id=None):
                del record, context, timeout_seconds
                assert isinstance(step_id, str)
                dispatched_roles.append(role)
                output = outputs[0] if role == "investigator" else outputs[1]
                return output, {
                    "input_tokens": 90,
                    "cached_input_tokens": 0,
                    "output_tokens": 30,
                }

            async def retry_after_restart() -> dict[str, Any]:
                with (
                    patch.object(cloud_research, "_PROCESS_EPOCH", next_epoch),
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
                    patch.object(research_sessions, "execution_capabilities", return_value=[]),
                    patch.object(
                        research_sessions, "_call", new=AsyncMock(side_effect=retry_call)
                    ) as calls,
                ):
                    started = await research_sessions.start_session(
                        project.path,
                        strategy.id,
                        idempotency_key,
                        project.project.id,
                        credential["identity"],
                        session_limits,
                    )
                    assert started["id"] != orphan_id
                    for _ in range(500):
                        completed = research_sessions.get_session(project.path, started["id"])
                        if completed["status"] in {"ended", "failed", "paused"}:
                            break
                        await asyncio.sleep(0.01)
                    else:
                        raise AssertionError("retried orphan job did not reach a saved state")
                    assert calls.await_count == 2
                    assert dispatched_roles == ["investigator", "skeptic"]
                    return completed

            completed = asyncio.run(retry_after_restart())
            assert completed["status"] == "ended"
            db = cloud_research._connect()
            assert (
                db.execute("SELECT 1 FROM jobs WHERE session_id=?", (orphan_id,)).fetchone() is None
            )
            db.close()

            # Queue one valid saved job, a running row, and a queued row with an
            # ambiguous provider reservation. Recovery may remove only the
            # unpublished no-call row.
            prototype = captured

            def derived_job(status: str) -> dict[str, Any]:
                item = json.loads(json.dumps(prototype))
                item["id"] = str(uuid4())
                item["idempotency_key"] = str(uuid4())
                item["status"] = status
                item["max_concurrent_sessions"] = 10
                item["steps"] = []
                item["events"] = []
                return item

            # Existing databases migrate the new column to zero. An active
            # legacy job with a saved session record must still consume a slot.
            legacy = derived_job("queued")
            legacy["max_concurrent_sessions"] = 1
            cloud_research.prepare_job(legacy)
            research_sessions._save(project.path, legacy)
            db = cloud_research._connect()
            db.execute(
                "UPDATE jobs SET session_slot=0,project_relpath='' WHERE session_id=?",
                (legacy["id"],),
            )
            db.close()
            after_upgrade = derived_job("queued")
            after_upgrade["max_concurrent_sessions"] = 1
            try:
                cloud_research.prepare_job(after_upgrade)
            except cloud_research.CloudResearchUnavailable as exc:
                assert "maximum concurrent sessions" in str(exc).lower()
            else:
                raise AssertionError("an active pre-migration job did not consume a project slot")
            db = cloud_research._connect()
            assert (
                db.execute(
                    "SELECT 1 FROM jobs WHERE session_id=?", (after_upgrade["id"],)
                ).fetchone()
                is None
            )
            db.execute("DELETE FROM jobs WHERE session_id=?", (legacy["id"],))
            db.close()
            (Path(project.path) / "research-sessions" / f"{legacy['id']}.json").unlink()

            slot_one = derived_job("queued")
            slot_one["max_concurrent_sessions"] = 1
            cloud_research.prepare_job(slot_one)
            slot_two = derived_job("queued")
            slot_two["max_concurrent_sessions"] = 1
            try:
                cloud_research.prepare_job(slot_two)
            except cloud_research.CloudResearchUnavailable as exc:
                assert "maximum concurrent sessions" in str(exc).lower()
                assert slot_one["id"] in str(exc)
            else:
                raise AssertionError("hosted reservation exceeded the project's session limit")
            db = cloud_research._connect()
            db.execute("UPDATE jobs SET status='paused' WHERE session_id=?", (slot_one["id"],))
            db.close()
            cloud_research.prepare_job(slot_two)
            db = cloud_research._connect()
            db.execute("UPDATE jobs SET status='terminal' WHERE session_id=?", (slot_two["id"],))
            db.close()
            slot_three = derived_job("queued")
            slot_three["max_concurrent_sessions"] = 1
            cloud_research.prepare_job(slot_three)
            db = cloud_research._connect()
            db.execute(
                "UPDATE jobs SET status='interrupted' WHERE session_id=?", (slot_three["id"],)
            )
            db.close()
            slot_four = derived_job("queued")
            slot_four["max_concurrent_sessions"] = 1
            cloud_research.prepare_job(slot_four)
            db = cloud_research._connect()
            db.execute(
                "DELETE FROM jobs WHERE session_id IN (?,?,?,?)",
                (slot_one["id"], slot_two["id"], slot_three["id"], slot_four["id"]),
            )
            db.close()

            valid = derived_job("queued")
            cloud_research.prepare_job(valid)
            research_sessions._save(project.path, valid)
            running = derived_job("running")
            cloud_research.prepare_job(running)
            assert cloud_research.claim_job(running["id"])
            research_sessions._save(project.path, running)
            slow_worker_fd = os.open(
                research_sessions._worker_lock_path(project.path, running["id"]),
                os.O_CREAT | os.O_RDWR,
                0o600,
            )
            fcntl.flock(slow_worker_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            abandoned = derived_job("running")
            cloud_research.prepare_job(abandoned)
            db = cloud_research._connect()
            db.execute("UPDATE jobs SET status='running' WHERE session_id=?", (abandoned["id"],))
            db.close()
            research_sessions._save(project.path, abandoned)
            ambiguous = derived_job("running")
            cloud_research.prepare_job(ambiguous)
            # Seed a historical concurrent-running state while exercising recovery;
            # admission itself correctly permits only one live session per owner.
            db = cloud_research._connect()
            db.execute("UPDATE jobs SET status='paused' WHERE session_id=?", (running["id"],))
            db.execute("UPDATE jobs SET status='paused' WHERE session_id=?", (abandoned["id"],))
            db.close()
            assert cloud_research.claim_job(ambiguous["id"])
            db = cloud_research._connect()
            db.execute("UPDATE jobs SET status='running' WHERE session_id=?", (running["id"],))
            db.execute("UPDATE jobs SET status='running' WHERE session_id=?", (abandoned["id"],))
            db.close()
            call_id = str(uuid4())
            cloud_research.reserve_call(ambiguous["id"], call_id, 0.25, 100)
            cloud_research.mark_call_unknown(ambiguous["id"], call_id)
            db = cloud_research._connect()
            db.execute(
                "UPDATE jobs SET process_epoch=? WHERE session_id IN (?,?,?,?)",
                (old_epoch, valid["id"], running["id"], abandoned["id"], ambiguous["id"]),
            )
            db.execute("UPDATE jobs SET status='queued' WHERE session_id=?", (ambiguous["id"],))
            db.close()
            with patch.object(cloud_research, "_PROCESS_EPOCH", next_epoch):
                removed = cloud_research.reconcile_orphaned_jobs()
            fcntl.flock(slow_worker_fd, fcntl.LOCK_UN)
            os.close(slow_worker_fd)
            assert ambiguous["id"] not in removed
            db = cloud_research._connect()
            assert (
                db.execute("SELECT status FROM jobs WHERE session_id=?", (valid["id"],)).fetchone()[
                    0
                ]
                == "queued"
            )
            assert (
                db.execute(
                    "SELECT status FROM jobs WHERE session_id=?", (running["id"],)
                ).fetchone()[0]
                == "running"
            )
            assert (
                research_sessions.get_session(project.path, abandoned["id"])["status"] == "paused"
            )
            assert cloud_research.job_status(abandoned["id"]) == "interrupted"
            assert (
                db.execute(
                    "SELECT status,amount_usd FROM calls WHERE call_id=?", (call_id,)
                ).fetchone()["status"]
                == "unknown"
            )
            assert (
                db.execute("SELECT amount_usd FROM calls WHERE call_id=?", (call_id,)).fetchone()[
                    "amount_usd"
                ]
                == 0.25
            )
            assert (
                db.execute(
                    "SELECT COUNT(*) FROM jobs WHERE workspace_id=? AND status='queued'",
                    (workspace_a.workspace_id,),
                ).fetchone()[0]
                == 2
            )
            db.close()

            # With the orphan gone, another job can consume the recovered queue
            # slot once one of the independently verified queued rows is removed.
            db = cloud_research._connect()
            db.execute("DELETE FROM jobs WHERE session_id=?", (valid["id"],))
            db.close()
            next_job = derived_job("queued")
            cloud_research.prepare_job(next_job)
        finally:
            cloud_workspaces._CURRENT.reset(binding)

        # An owner A recovery pass cannot inspect or remove owner B's orphan.
        binding = cloud_workspaces._CURRENT.set(workspace_b)
        try:
            project_b = initialize_project(
                workspace_b.path / "other.sigma", "Other workspace", "Owner B question"
            )
            foreign = job(workspace_b.workspace_id)
            foreign.update({"project_id": project_b.project.id, "project_path": project_b.path})
            cloud_research.prepare_job(foreign)
            db = cloud_research._connect()
            foreign_epoch = db.execute(
                "SELECT process_epoch FROM jobs WHERE session_id=?", (foreign["id"],)
            ).fetchone()[0]
            db.close()
        finally:
            cloud_workspaces._CURRENT.reset(binding)
        binding = cloud_workspaces._CURRENT.set(workspace_a)
        try:
            with patch.object(cloud_research, "_PROCESS_EPOCH", uuid4().hex):
                cloud_research.reconcile_orphaned_jobs()
            binding_b = cloud_workspaces._CURRENT.set(workspace_b)
            try:
                db = cloud_research._connect()
                assert (
                    db.execute(
                        "SELECT process_epoch FROM jobs WHERE session_id=?", (foreign["id"],)
                    ).fetchone()[0]
                    == foreign_epoch
                )
                db.close()
            finally:
                cloud_workspaces._CURRENT.reset(binding_b)
        finally:
            cloud_workspaces._CURRENT.reset(binding)


def test_workspace_spend_budget(root: Path, ledger_root: Path) -> None:
    """Spend is atomic across projects and remains attributed after reopening SQLite."""
    owner = workspace(root, "e" * 32)
    other = workspace(root, "f" * 32)
    first_project = initialize_project(owner.path / "budget-one.sigma", "Budget one", "Question")
    second_project = initialize_project(owner.path / "budget-two.sigma", "Budget two", "Question")
    env = {
        "SIGMA_CLOUD_AUTH_ENABLED": "true",
        "SIGMA_CLOUD_INFERENCE_PROVIDER": "api_key",
        "SIGMA_CLOUD_OPENAI_API_KEY": "cloud-research-fixture-key",
        "SIGMA_CLOUD_GLOBAL_SPEND_CEILING_USD": "15.00",
        "SIGMA_CLOUD_USER_SPEND_CEILING_USD": "0.25",
        "SIGMA_CLOUD_USER_MAX_CONCURRENT": "1",
        "SIGMA_CLOUD_GLOBAL_MAX_CONCURRENT": "2",
        "SIGMA_CLOUD_USER_MAX_QUEUED": "2",
        "SIGMA_CLOUD_GLOBAL_MAX_QUEUED": "16",
        "SIGMA_CLOUD_USER_TOKEN_BUDGET": "10000",
    }
    with (
        patch.dict(os.environ, env, clear=False),
        patch.object(cloud_workspaces, "storage_root", return_value=ledger_root),
    ):
        binding = cloud_workspaces._CURRENT.set(owner)
        try:
            first = job(owner.workspace_id)
            first.update(project_id=first_project.project.id, project_path=first_project.path)
            cloud_research.prepare_job(first)
            assert cloud_research.claim_job(first["id"])
            cloud_research.reserve_call(first["id"], "known-usage", 0.15, 10)
            cloud_research.settle_call(
                first["id"],
                "known-usage",
                input_tokens=5,
                output_tokens=5,
                estimated_cost_usd=0.15,
            )
            db = cloud_research._connect()
            db.execute("UPDATE jobs SET status='terminal' WHERE session_id=?", (first["id"],))
            db.close()

            second = job(owner.workspace_id)
            second.update(project_id=second_project.project.id, project_path=second_project.path)
            cloud_research.prepare_job(second)
            assert cloud_research.claim_job(second["id"])
            barrier = threading.Barrier(2)

            def spend(attempt: str) -> bool:
                context = cloud_workspaces._CURRENT.set(owner)
                try:
                    barrier.wait(timeout=5)
                    cloud_research.reserve_call(second["id"], attempt, 0.10, 10)
                    return True
                except cloud_research.CloudResearchUnavailable:
                    return False
                finally:
                    cloud_workspaces._CURRENT.reset(context)

            with ThreadPoolExecutor(max_workers=2) as pool:
                accepted = list(pool.map(spend, ("race-a", "race-b")))
            assert sorted(accepted) == [False, True], accepted
            accepted_call = "race-a" if accepted[0] else "race-b"
            cloud_research.mark_call_unknown(second["id"], accepted_call)
            summary = cloud_research.snapshot()
            assert summary["allowance_usd"] == 0.25
            assert summary["estimated_usage_usd"] == 0.15
            assert summary["held_usd"] == 0.10
            assert summary["remaining_usd"] == 0
            assert summary["unknown_provider_attempts"] == 1
            # A new Python process sees the same persisted accounting and unknown charge.
            script = (
                "import json; from pathlib import Path; from sigma import cloud_research, cloud_workspaces; "
                f"w=cloud_workspaces.Workspace('{owner.workspace_id}', 'subject', Path('{owner.path}')); "
                "t=cloud_workspaces._CURRENT.set(w); print(json.dumps(cloud_research.snapshot(), sort_keys=True)); "
                "cloud_workspaces._CURRENT.reset(t)"
            )
            child_env = {
                **os.environ,
                **env,
                "SIGMA_CLOUD_WORKSPACES_ROOT": str(ledger_root),
            }
            restarted = subprocess.run(
                [sys.executable, "-c", script],
                cwd=Path(__file__).resolve().parents[1],
                env=child_env,
                check=True,
                capture_output=True,
                text=True,
                timeout=10,
            )
            assert json.loads(restarted.stdout) == summary
            try:
                cloud_research.reserve_call(second["id"], "past-budget", 0.01, 1)
                raise AssertionError("exhausted user allowance admitted another call")
            except cloud_research.CloudResearchUnavailable as exc:
                assert "saved research remains available" in str(exc)
        finally:
            cloud_workspaces._CURRENT.reset(binding)

        # Workspace B has an independent allowance and cannot forge A's job ID.
        binding = cloud_workspaces._CURRENT.set(other)
        try:
            assert cloud_research.snapshot()["reserved_and_estimated_usd"] == 0
            try:
                cloud_research.reserve_call(second["id"], "forged-owner", 0.01, 1)
                raise AssertionError("cross-workspace spending reservation succeeded")
            except cloud_research.CloudResearchUnavailable:
                pass
        finally:
            cloud_workspaces._CURRENT.reset(binding)

    # Missing, malformed, and over-policy allowances fail closed before queueing.
    with patch.object(cloud_workspaces, "storage_root", return_value=ledger_root):
        binding = cloud_workspaces._CURRENT.set(owner)
        try:
            for invalid in (None, "nan", "-1", "15.01", "garbage"):
                overrides = (
                    {} if invalid is None else {"SIGMA_CLOUD_USER_SPEND_CEILING_USD": invalid}
                )
                with patch.dict(os.environ, overrides, clear=False):
                    if invalid is None:
                        os.environ.pop("SIGMA_CLOUD_USER_SPEND_CEILING_USD", None)
                    candidate = job(owner.workspace_id)
                    try:
                        cloud_research.prepare_job(candidate)
                        raise AssertionError(
                            f"invalid user spending configuration accepted: {invalid}"
                        )
                    except cloud_research.CloudResearchUnavailable:
                        pass
        finally:
            cloud_workspaces._CURRENT.reset(binding)

    with patch.object(cloud_workspaces, "storage_root", return_value=ledger_root):
        binding = cloud_workspaces._CURRENT.set(owner)
        try:
            for invalid in (None, "0", "1000.01", "inf", "not-money"):
                overrides = (
                    {} if invalid is None else {"SIGMA_CLOUD_GLOBAL_SPEND_CEILING_USD": invalid}
                )
                with patch.dict(os.environ, overrides, clear=False):
                    if invalid is None:
                        os.environ.pop("SIGMA_CLOUD_GLOBAL_SPEND_CEILING_USD", None)
                    candidate = job(owner.workspace_id)
                    try:
                        cloud_research.prepare_job(candidate)
                        raise AssertionError(
                            f"invalid global spending configuration accepted: {invalid}"
                        )
                    except cloud_research.CloudResearchUnavailable:
                        pass
        finally:
            cloud_workspaces._CURRENT.reset(binding)


def test_configured_session_and_account_budget_above_legacy_cap(
    root: Path, ledger_root: Path
) -> None:
    """A project and real account ledger may both safely exceed the old $0.25 cap."""
    owner = workspace(root, "a" * 32)
    project = initialize_project(owner.path / "above-legacy-cap.sigma", "Larger budget", "Question")
    env = {
        "SIGMA_CLOUD_AUTH_ENABLED": "true",
        "SIGMA_CLOUD_GLOBAL_SPEND_CEILING_USD": "1.00",
        "SIGMA_CLOUD_USER_SPEND_CEILING_USD": "0.50",
        "SIGMA_CLOUD_USER_MAX_CONCURRENT": "1",
        "SIGMA_CLOUD_GLOBAL_MAX_CONCURRENT": "2",
        "SIGMA_CLOUD_USER_MAX_QUEUED": "2",
        "SIGMA_CLOUD_GLOBAL_MAX_QUEUED": "16",
        "SIGMA_CLOUD_USER_TOKEN_BUDGET": "10000",
    }
    with (
        patch.dict(os.environ, env, clear=False),
        patch.object(cloud_workspaces, "storage_root", return_value=ledger_root),
    ):
        binding = cloud_workspaces._CURRENT.set(owner)
        try:
            record = job(owner.workspace_id)
            record.update(
                project_id=project.project.id,
                project_path=project.path,
                maximum_estimated_cost_usd=0.50,
                call_limit=30,
            )
            cloud_research.prepare_job(record)
            assert cloud_research.claim_job(record["id"])
            cloud_research.reserve_call(record["id"], "above-legacy-cap", 0.30, 100)
            summary = cloud_research.snapshot()
            assert summary["allowance_usd"] == 0.50
            assert summary["held_usd"] == 0.30
            assert summary["remaining_usd"] == 0.20
        finally:
            cloud_workspaces._CURRENT.reset(binding)


def test_pilot_global_spend_accepts_multiple_users(root: Path, ledger_root: Path) -> None:
    """Ten researchers can fund repeated sessions above $15 without disabling guardrails."""
    env = {
        "SIGMA_CLOUD_AUTH_ENABLED": "true",
        "SIGMA_CLOUD_GLOBAL_SPEND_CEILING_USD": "20.00",
        "SIGMA_CLOUD_USER_SPEND_CEILING_USD": "2.00",
        "SIGMA_CLOUD_USER_MAX_CONCURRENT": "1",
        "SIGMA_CLOUD_GLOBAL_MAX_CONCURRENT": "2",
        "SIGMA_CLOUD_USER_MAX_QUEUED": "2",
        "SIGMA_CLOUD_GLOBAL_MAX_QUEUED": "16",
        "SIGMA_CLOUD_USER_TOKEN_BUDGET": "10000",
    }
    with (
        patch.dict(os.environ, env, clear=False),
        patch.object(cloud_workspaces, "storage_root", return_value=ledger_root),
    ):
        assert cloud_research._spend_ceiling_decimal() == Decimal("20.00")
        for user_number in range(10):
            member = workspace(root, f"{user_number:032x}")
            project = initialize_project(
                member.path / "pilot.sigma", f"Pilot {user_number}", "Investigate a question"
            )
            binding = cloud_workspaces._CURRENT.set(member)
            try:
                for session_number in range(2):
                    record = job(member.workspace_id)
                    record.update(
                        project_id=project.project.id,
                        project_path=project.path,
                        maximum_estimated_cost_usd=None,
                    )
                    cloud_research.prepare_job(record)
                    assert cloud_research.claim_job(record["id"])
                    cloud_research.reserve_call(
                        record["id"], f"call-{user_number}-{session_number}", 0.80, 100
                    )
                    cloud_research.settle_call(
                        record["id"],
                        f"call-{user_number}-{session_number}",
                        input_tokens=40,
                        output_tokens=60,
                        estimated_cost_usd=0.80,
                    )
                    record["status"] = "ended"
                    cloud_research.sync_job(record)
                summary = cloud_research.snapshot()
                assert summary["estimated_usage_usd"] == 1.60, summary
                assert summary["held_usd"] == 0, summary
                assert summary["remaining_usd"] == 0.40, summary
                if user_number == 9:
                    assert summary["global_remaining_usd"] == 4.00, summary
            finally:
                cloud_workspaces._CURRENT.reset(binding)
        assert abs(global_reserved_spend() - 16.00) < 1e-6
        # Fill the global cap with separate users, then attempt one more call
        # from an account whose personal allowance is still untouched. A single
        # account would fail at its $2 per-user cap first and would not test the
        # $20 global boundary.
        for extra_number, amount in enumerate((2.00, 2.00, 0.01), start=10):
            member = workspace(root, f"{extra_number:032x}")
            project = initialize_project(
                member.path / "pilot.sigma", f"Pilot {extra_number}", "Question"
            )
            binding = cloud_workspaces._CURRENT.set(member)
            try:
                record = job(member.workspace_id)
                record.update(
                    project_id=project.project.id,
                    project_path=project.path,
                    maximum_estimated_cost_usd=None,
                )
                if extra_number < 12:
                    cloud_research.prepare_job(record)
                    assert cloud_research.claim_job(record["id"])
                    cloud_research.reserve_call(
                        record["id"], f"at-global-{extra_number}", amount, 100
                    )
                    assert cloud_research.snapshot()["held_usd"] == amount
                    if extra_number == 11:
                        # The final call consumes the global ceiling. A further
                        # provider reservation must fail before any dispatch,
                        # with a precise and actionable funding shortfall.
                        try:
                            cloud_research.reserve_call(
                                record["id"], "blocked-after-global-ceiling", 0.01, 1
                            )
                        except cloud_research.CloudResearchUnavailable as exc:
                            assert "Remaining global capacity: $0.0000" in str(exc)
                            assert "next call requires $0.0100" in str(exc)
                            assert "No provider call was made." in str(exc)
                        else:
                            raise AssertionError("A provider call bypassed the global ceiling")
                    # The reservation stays in the ledger, but should not
                    # occupy a live concurrency slot after the test job ends.
                    record["status"] = "ended"
                    cloud_research.sync_job(record)
                else:
                    assert abs(global_reserved_spend() - 20.00) < 1e-6
                    budget = cloud_research.snapshot()
                    assert budget["remaining_usd"] == 2.00
                    # Personal allowance is positive, but provider research
                    # is still blocked by the independent shared ceiling.
                    assert budget["global_remaining_usd"] == 0.00
                    try:
                        cloud_research.prepare_job(record)
                    except cloud_research.CloudResearchUnavailable as exc:
                        assert "global inference-spend ceiling" in str(exc), str(exc)
                    else:
                        raise AssertionError("An over-ceiling session was queued")
                    # A hopeless new session must not be saved in the ledger.
                    assert cloud_research.job_status(record["id"]) is None
            finally:
                cloud_workspaces._CURRENT.reset(binding)

        # Read-only diagnostic reconciles with admission while concealing IDs.
        diagnostic = subprocess.run(
            [
                sys.executable,
                str(Path(__file__).resolve().parents[1] / "scripts" / "inspect_cloud_spend.py"),
                "--ledger",
                str(ledger_root / "cloud-research.sqlite3"),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        report = json.loads(diagnostic.stdout)
        assert report["global_obligations_usd"] == 20.0, report
        assert report["held_or_unknown_usd"] == 4.0, report
        assert report["status_counts"]["usage_estimated"] == 20, report
        assert report["status_counts"]["reserved"] == 2, report
        assert '"workspace_id":' not in diagnostic.stdout
        assert '"call_id":' not in diagnostic.stdout


def test_admin_allowance_reload_preserves_provider_spend(root: Path, ledger_root: Path) -> None:
    """A reload starts a new user allowance period but never erases global spend."""
    owner = workspace(root, "9" * 32)
    project = initialize_project(owner.path / "reload.sigma", "Reload", "Check allowance reload")
    env = {
        "SIGMA_CLOUD_AUTH_ENABLED": "true",
        "SIGMA_CLOUD_GLOBAL_SPEND_CEILING_USD": "15.00",
        "SIGMA_CLOUD_USER_SPEND_CEILING_USD": "0.25",
        "SIGMA_CLOUD_USER_MAX_CONCURRENT": "1",
        "SIGMA_CLOUD_GLOBAL_MAX_CONCURRENT": "2",
        "SIGMA_CLOUD_USER_MAX_QUEUED": "2",
        "SIGMA_CLOUD_GLOBAL_MAX_QUEUED": "16",
        "SIGMA_CLOUD_USER_TOKEN_BUDGET": "12",
    }
    with (
        patch.dict(os.environ, env, clear=False),
        patch.object(cloud_workspaces, "storage_root", return_value=ledger_root),
    ):
        binding = cloud_workspaces._CURRENT.set(owner)
        try:
            first = job(owner.workspace_id)
            first.update(project_id=project.project.id, project_path=project.path)
            cloud_research.prepare_job(first)
            assert cloud_research.claim_job(first["id"])
            cloud_research.reserve_call(first["id"], "before-reload", 0.2, 10)
            cloud_research.settle_call(
                first["id"],
                "before-reload",
                input_tokens=5,
                output_tokens=5,
                estimated_cost_usd=0.2,
            )
            db = cloud_research._connect()
            db.execute("UPDATE jobs SET status='terminal' WHERE session_id=?", (first["id"],))
            db.close()
            assert cloud_research.snapshot()["remaining_usd"] == 0.05
            reset_at = cloud_research.admin_reload_workspace_allowance(
                owner.workspace_id, "admin@example.org"
            )
            summary = cloud_research.snapshot()
            assert summary["remaining_usd"] == 0.25, summary
            assert summary["estimated_usage_usd"] == 0, summary
            assert summary["reserved_and_estimated_usd"] == 0, summary
            assert summary["user_reserved_or_observed_tokens"] == 0, summary
            assert global_reserved_spend() == 0.2
            db = cloud_research._connect()
            event = db.execute(
                "SELECT reset_at,actor_email FROM allowance_reload_events WHERE workspace_id=?",
                (owner.workspace_id,),
            ).fetchone()
            db.close()
            assert event["reset_at"] == reset_at and event["actor_email"] == "admin@example.org"

            second = job(owner.workspace_id)
            second.update(project_id=project.project.id, project_path=project.path)
            cloud_research.prepare_job(second)
            assert cloud_research.claim_job(second["id"])
            cloud_research.reserve_call(second["id"], "after-reload", 0.25, 10)
            cloud_research.mark_call_unknown(second["id"], "after-reload")
            assert cloud_research.snapshot()["user_reserved_or_observed_tokens"] == 10
            cloud_research.admin_reload_workspace_allowance(owner.workspace_id, "admin@example.org")
            reloaded = cloud_research.snapshot()
            assert reloaded["remaining_usd"] == 0.25, reloaded
            assert reloaded["held_usd"] == 0, reloaded
            assert reloaded["user_reserved_or_observed_tokens"] == 0, reloaded
            admin_summary = cloud_research.admin_workspace_spending(owner.workspace_id, 0.25)
            assert admin_summary["reload_eligible"] is False, admin_summary
            assert global_reserved_spend() == 0.45

            # The post-reload token counter must not merely report zero:
            # admission must genuinely accept another funded call. Meanwhile
            # the previous unknown charge remains in the global ledger.
            second["status"] = "ended"
            cloud_research.sync_job(second)
            third = job(owner.workspace_id)
            third.update(project_id=project.project.id, project_path=project.path)
            cloud_research.prepare_job(third)
            assert cloud_research.claim_job(third["id"])
            cloud_research.reserve_call(third["id"], "fresh-window", 0.10, 10)
            after = cloud_research.snapshot()
            assert after["user_reserved_or_observed_tokens"] == 10, after
            assert after["held_usd"] == 0.10, after
            assert after["remaining_usd"] == 0.15, after
            assert abs(global_reserved_spend() - 0.55) < 1e-6
        finally:
            cloud_workspaces._CURRENT.reset(binding)


def test_explicit_account_allowance_does_not_require_default(root: Path, ledger_root: Path) -> None:
    """A member-specific cap works without configuring a fallback for other accounts."""
    from sigma import cloud_auth, cloud_sponsor

    member_email = "sponsored-member@example.test"
    member = workspace(root, "9" * 32, member_email)
    project = initialize_project(member.path / "explicit-allowance.sigma", "Explicit", "Question")
    auth_root = root / "auth-explicit-allowance"
    auth_root.mkdir(mode=0o700)
    env = {
        "SIGMA_CLOUD_AUTH_ENABLED": "true",
        "SIGMA_CLOUD_AUTH_LOCAL": "true",
        "SIGMA_CLOUD_PUBLIC_ORIGIN": "http://127.0.0.1:8000",
        "SIGMA_CLOUD_AUTH_HOME": str(auth_root),
        "SIGMA_CLOUD_GLOBAL_SPEND_CEILING_USD": "15.00",
        "SIGMA_CLOUD_USER_MAX_CONCURRENT": "1",
        "SIGMA_CLOUD_GLOBAL_MAX_CONCURRENT": "2",
        "SIGMA_CLOUD_USER_MAX_QUEUED": "2",
        "SIGMA_CLOUD_GLOBAL_MAX_QUEUED": "8",
    }
    with (
        patch.dict(os.environ, env, clear=False),
        patch.object(cloud_workspaces, "storage_root", return_value=ledger_root),
        patch.object(cloud_sponsor, "inference_provider", return_value="api_key"),
    ):
        os.environ.pop("SIGMA_CLOUD_USER_SPEND_CEILING_USD", None)
        cfg = cloud_auth.config()
        assert cfg.enabled and cfg.error is None and cfg.database is not None
        with cloud_auth._db(cfg) as db:
            db.execute(
                "INSERT INTO grants(kind,value,role,active,updated_at,allowance_usd) "
                "VALUES('email',?,'member',1,?,0.25)",
                (member_email, cloud_auth._now()),
            )
        binding = cloud_workspaces._CURRENT.set(member)
        try:
            candidate = job(member.workspace_id)
            candidate.update(
                project_id=project.project.id,
                project_path=project.path,
                maximum_estimated_cost_usd=None,
            )
            cloud_research.prepare_job(candidate)
            assert cloud_research.claim_job(candidate["id"])
            cloud_research.reserve_call(candidate["id"], "no-project-cap", 0.20, 10)
        finally:
            cloud_workspaces._CURRENT.reset(binding)


def test_rule_allowance_controls_reservation_and_reduction_keeps_unknown_hold(
    root: Path, ledger_root: Path
) -> None:
    owner = workspace(root, "9" * 32, "researcher@example.org")
    env = {
        "SIGMA_CLOUD_AUTH_ENABLED": "true",
        "SIGMA_CLOUD_GLOBAL_SPEND_CEILING_USD": "15.00",
        "SIGMA_CLOUD_USER_SPEND_CEILING_USD": "2.00",
        "SIGMA_CLOUD_USER_TOKEN_BUDGET": "10000",
    }
    with (
        patch.dict(os.environ, env, clear=False),
        patch.object(cloud_workspaces, "storage_root", return_value=ledger_root),
        patch("sigma.cloud_auth.effective_spending_allowance", return_value=5.0),
    ):
        binding = cloud_workspaces._CURRENT.set(owner)
        try:
            candidate = job(owner.workspace_id)
            cloud_research.prepare_job(candidate)
            assert cloud_research.claim_job(candidate["id"])
            cloud_research.reserve_call(candidate["id"], "above-default", 0.30, 10)
            cloud_research.mark_call_unknown(candidate["id"], "above-default")
            assert cloud_research.snapshot()["allowance_usd"] == 5.0
            with patch("sigma.cloud_auth.effective_spending_allowance", return_value=0.20):
                summary = cloud_research.snapshot()
                assert summary["allowance_usd"] == 0.20
                assert summary["remaining_usd"] == 0
                try:
                    cloud_research.reserve_call(candidate["id"], "after-reduction", 0.01, 1)
                    raise AssertionError("lowered allowance admitted another reservation")
                except cloud_research.CloudResearchUnavailable as exc:
                    assert "allowance" in str(exc)
            db = cloud_research._connect()
            try:
                row = db.execute(
                    "SELECT amount_usd,status FROM calls WHERE call_id='above-default'"
                ).fetchone()
                assert row["amount_usd"] == 0.30
                assert row["status"] == "unknown"
            finally:
                db.close()
        finally:
            cloud_workspaces._CURRENT.reset(binding)


def test_hosted_capacity_defaults_allow_eight_distinct_researchers() -> None:
    # Eight users must fit comfortably within the hosted global execution limit;
    # a separate per-user fairness cap prevents any one user taking all slots.
    with patch.dict(os.environ, {}, clear=True):
        per_user, global_slots, per_user_queue, global_queue = (
            cloud_research._evaluation_queue_limits()
        )
        assert per_user == 4
        assert global_slots == 32
        assert per_user * 8 == global_slots
        assert per_user_queue == 4 and global_queue == 16


def test_local_limits_remain_unmodified(root: Path) -> None:
    for user_cost_limit in (None, 0.01, 1.0):
        sponsored = cloud_research.evaluation_session_limits(
            {
                "research_rounds": 1,
                "model_calls": 30,
                "session_duration_minutes": 30,
                "maximum_estimated_cost_usd": user_cost_limit,
            }
        )
        assert sponsored["maximum_estimated_cost_usd"] == user_cost_limit
        assert sponsored["model_calls"] == 30 and sponsored["research_rounds"] == 1
        assert sponsored["session_duration_minutes"] == cloud_research.MAX_SESSION_MINUTES
    project = initialize_project(root / "local-unlimited.sigma", "Local", "Question")
    limits = {
        **research_sessions.DEFAULT_LIMITS,
        "research_rounds": 5,
        "model_calls": 30,
        "session_duration_minutes": 60,
        "output_tokens_per_call": 16384,
        "maximum_estimated_cost_usd": None,
    }
    with patch.dict(os.environ, {"SIGMA_CLOUD_AUTH_ENABLED": "false"}, clear=False):
        saved = research_sessions.save_limits(project.path, limits)
        assert saved == limits
        assert research_sessions.get_limits(project.path) == limits

    # Local sponsored sessions need the durable spend ledger, but the hosted
    # evaluation call cap must not silently rewrite their project setting.
    sponsored_limits = {
        **limits,
        "research_rounds": 3,
        "model_calls": 12,
        "session_duration_minutes": 15,
        "maximum_estimated_cost_usd": 0.25,
    }
    with (
        patch.object(cloud_workspaces, "enabled", return_value=False),
        patch.object(cloud_research, "billing_enabled", return_value=True),
    ):
        saved = research_sessions.save_limits(project.path, sponsored_limits)
        assert saved == sponsored_limits
        assert research_sessions.get_limits(project.path) == sponsored_limits
        assert cloud_research.session_call_ceiling() == cloud_research.MAX_PROJECT_SESSION_CALLS

    with patch.object(cloud_workspaces, "enabled", return_value=True):
        assert cloud_research.session_call_ceiling() == cloud_research.MAX_PROJECT_SESSION_CALLS

    hosted_duration = {**sponsored_limits, "session_duration_minutes": 60}
    with (
        patch.object(cloud_workspaces, "enabled", return_value=True),
        patch.object(cloud_research, "billing_enabled", return_value=True),
    ):
        assert research_sessions.save_limits(project.path, hosted_duration) == hosted_duration
        assert research_sessions.get_limits(project.path) == hosted_duration
        assert (
            cloud_research.evaluation_session_limits(hosted_duration)["session_duration_minutes"]
            == 15
        )
    with (
        patch.object(cloud_workspaces, "enabled", return_value=False),
        patch.object(cloud_research, "billing_enabled", return_value=True),
    ):
        assert research_sessions.get_limits(project.path)["session_duration_minutes"] == 60


def test_local_global_spend_default_supports_small_team_pilot() -> None:
    """The local pilot renews monthly, while explicit operator caps stay cumulative."""
    with patch("sigma.cloud_auth.local_sponsored_principal", return_value=object()):
        with patch.dict(os.environ, {"SIGMA_CLOUD_GLOBAL_SPEND_WINDOW": ""}, clear=False):
            os.environ.pop("SIGMA_CLOUD_GLOBAL_SPEND_CEILING_USD", None)
            assert cloud_research._spend_ceiling_decimal() == Decimal("50.00")
            assert cloud_research._global_spend_period() == "calendar_month"
            assert "$50 monthly" in cloud_research._global_ceiling_failure_message()
        with patch.dict(
            os.environ,
            {
                "SIGMA_CLOUD_GLOBAL_SPEND_CEILING_USD": "5.00",
                "SIGMA_CLOUD_GLOBAL_SPEND_WINDOW": "",
            },
        ):
            assert cloud_research._spend_ceiling_decimal() == Decimal("5.00")
            assert cloud_research._global_spend_period() == "cumulative"
        with patch.dict(
            os.environ,
            {
                "SIGMA_CLOUD_GLOBAL_SPEND_CEILING_USD": "5.00",
                "SIGMA_CLOUD_GLOBAL_SPEND_WINDOW": "calendar_month",
            },
        ):
            assert cloud_research._global_spend_period() == "calendar_month"
        with patch.dict(os.environ, {"SIGMA_CLOUD_GLOBAL_SPEND_WINDOW": "invalid"}):
            try:
                cloud_research._global_spend_period()
            except cloud_research.CloudResearchUnavailable:
                pass
            else:
                raise AssertionError("Invalid spend periods must fail closed")


def test_monthly_global_budget_retains_unknown_provider_holds(
    root: Path, ledger_root: Path
) -> None:
    """Old settled calls age out, but unresolved calls keep their full hold."""
    from datetime import UTC, datetime, timedelta

    owner = workspace(root / "monthly-global", "a" * 32)
    old = (datetime.now(UTC) - timedelta(days=40)).isoformat()
    with (
        patch.dict(
            os.environ,
            {
                "SIGMA_CLOUD_GLOBAL_SPEND_CEILING_USD": "1.00",
                "SIGMA_CLOUD_USER_SPEND_CEILING_USD": "2.00",
                "SIGMA_CLOUD_GLOBAL_SPEND_WINDOW": "calendar_month",
            },
        ),
        patch.object(cloud_workspaces, "storage_root", return_value=ledger_root),
    ):
        context = cloud_workspaces._CURRENT.set(owner)
        try:
            with cloud_research._connect() as db:
                db.execute(
                    "INSERT INTO jobs(session_id,workspace_id,project_id,idempotency_key,status,created_at,updated_at)"
                    " VALUES(?,?,?,?,?,?,?)",
                    (
                        "old-month-job",
                        owner.workspace_id,
                        "test-month",
                        "old-month-key",
                        "terminal",
                        old,
                        old,
                    ),
                )
                db.execute(
                    "INSERT INTO calls(call_id,session_id,workspace_id,amount_usd,status,token_reservation,"
                    "input_tokens,output_tokens,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                    (
                        "old-month-call",
                        "old-month-job",
                        owner.workspace_id,
                        0.9,
                        "usage_estimated",
                        1,
                        1,
                        0,
                        old,
                        old,
                    ),
                )
                db.commit()
            summary = cloud_research.snapshot()
            assert summary["global_remaining_usd"] == 1.00
            assert summary["global_spend_period"] == "calendar_month"
            assert summary["global_reset_at"] is not None
            with cloud_research._connect() as db:
                db.execute("UPDATE calls SET status='unknown' WHERE call_id='old-month-call'")
                db.commit()
            assert cloud_research.snapshot()["global_remaining_usd"] == 0.10
            with cloud_research._connect() as db:
                db.execute(
                    "UPDATE calls SET status='usage_estimated' WHERE call_id='old-month-call'"
                )
                db.commit()
            assert cloud_research.snapshot()["global_remaining_usd"] == 1.00
            # Cumulative remains the default for explicitly configured caps.
            with patch.dict(os.environ, {"SIGMA_CLOUD_GLOBAL_SPEND_WINDOW": "cumulative"}):
                summary = cloud_research.snapshot()
                assert summary["global_remaining_usd"] == 0.10
                assert summary["global_reset_at"] is None
        finally:
            cloud_workspaces._CURRENT.reset(context)


def test_admin_unlimited_allowance_survives_monthly_global_renewal(
    root: Path, ledger_root: Path
) -> None:
    """An admin's historical spend never creates an additional lifetime cap."""
    from datetime import UTC, datetime, timedelta

    owner = workspace(root / "admin-renewal", "b" * 32)
    old = (datetime.now(UTC) - timedelta(days=40)).isoformat()
    with (
        patch.dict(
            os.environ,
            {
                "SIGMA_CLOUD_AUTH_ENABLED": "true",
                "SIGMA_CLOUD_GLOBAL_SPEND_CEILING_USD": "1.00",
                "SIGMA_CLOUD_USER_SPEND_CEILING_USD": "0.25",
                "SIGMA_CLOUD_GLOBAL_SPEND_WINDOW": "calendar_month",
                "SIGMA_CLOUD_USER_TOKEN_BUDGET": "1000000",
            },
        ),
        patch.object(cloud_workspaces, "storage_root", return_value=ledger_root),
        patch.object(cloud_research, "_admin_has_unlimited_spend", return_value=True),
    ):
        binding = cloud_workspaces._CURRENT.set(owner)
        try:
            project = initialize_project(
                owner.path / "admin-monthly.sigma", "Admin renewal", "Check the global ceiling"
            )
            with cloud_research._connect() as db:
                db.execute(
                    "INSERT INTO jobs(session_id,workspace_id,project_id,idempotency_key,status,created_at,updated_at)"
                    " VALUES(?,?,?,?,?,?,?)",
                    (
                        "old-admin-month",
                        owner.workspace_id,
                        "old",
                        "admin-old",
                        "terminal",
                        old,
                        old,
                    ),
                )
                db.execute(
                    "INSERT INTO calls(call_id,session_id,workspace_id,amount_usd,status,token_reservation,"
                    "input_tokens,output_tokens,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                    (
                        "old-admin-spend",
                        "old-admin-month",
                        owner.workspace_id,
                        0.95,
                        "usage_estimated",
                        1100000,
                        1100000,
                        0,
                        old,
                        old,
                    ),
                )
            summary = cloud_research.snapshot()
            assert summary["global_remaining_usd"] == 1.00, summary
            assert summary["remaining_usd"] == 1.00, summary
            assert summary["user_reserved_or_observed_tokens"] > 1000000

            first = job(owner.workspace_id)
            first.update(
                project_id=project.project.id,
                project_path=project.path,
                maximum_estimated_cost_usd=None,
            )
            cloud_research.prepare_job(first)
            assert cloud_research.claim_job(first["id"])
            cloud_research.reserve_call(first["id"], "admin-new-month-first", 0.20, 20)
            cloud_research.settle_call(
                first["id"],
                "admin-new-month-first",
                input_tokens=10,
                output_tokens=10,
                estimated_cost_usd=0.20,
            )
            first["status"] = "ended"
            cloud_research.sync_job(first)

            second = job(owner.workspace_id)
            second.update(
                project_id=project.project.id,
                project_path=project.path,
                maximum_estimated_cost_usd=None,
            )
            cloud_research.prepare_job(second)
            assert cloud_research.claim_job(second["id"])
            cloud_research.reserve_call(second["id"], "admin-new-month-second", 0.75, 20)
            summary = cloud_research.snapshot()
            assert summary["global_remaining_usd"] == 0.05, summary
            assert summary["remaining_usd"] == 0.05, summary
            assert summary["reserved_and_estimated_usd"] == 1.90, summary
            try:
                cloud_research.reserve_call(second["id"], "admin-global-blocked", 0.10, 10)
            except cloud_research.CloudResearchUnavailable as exc:
                assert "global inference-spend ceiling" in str(exc)
            else:
                raise AssertionError("Admin bypassed the shared global spend ceiling")
        finally:
            cloud_workspaces._CURRENT.reset(binding)


def test_json_project_orphan_recovery(
    root: Path, ledger_root: Path, limits_env: dict[str, str]
) -> None:
    """JSON-backed projects must recover unpublished jobs without losing saved work."""
    member = workspace(root / "json-queue-recovery", "e" * 32)
    with (
        patch.dict(
            os.environ,
            {
                **limits_env,
                # This fixture preserves several historical queued rows to
                # exercise crash recovery, not hosted capacity enforcement.
                "SIGMA_CLOUD_USER_MAX_CONCURRENT": "4",
                "SIGMA_CLOUD_GLOBAL_MAX_CONCURRENT": "4",
                "SIGMA_CLOUD_USER_TOKEN_BUDGET": "1000000",
                "SIGMA_CLOUD_USER_MAX_QUEUED": "2",
                "SIGMA_CLOUD_GLOBAL_MAX_QUEUED": "8",
            },
            clear=False,
        ),
        patch.object(cloud_workspaces, "storage_root", return_value=ledger_root),
    ):
        binding = cloud_workspaces._CURRENT.set(member)
        try:
            project = initialize_project(
                member.path / "portable.json", "Portable research", "Check persistence"
            )

            def bundle_job() -> dict[str, Any]:
                record = job(member.workspace_id)
                record.update(
                    project_id=project.project.id,
                    project_path=project.path,
                    session_number=1,
                    status="queued",
                    max_concurrent_sessions=2,
                    steps=[],
                    events=[],
                    strategy_runs=[],
                )
                return record

            unpublished = bundle_job()
            assert cloud_research._project_relpath(unpublished, member.path) == "portable.json"
            cloud_research.prepare_job(unpublished)
            from sigma.project_bundle import read_bundle

            member_name = f"research-sessions/{unpublished['id']}.json"
            assert member_name not in read_bundle(project.path)["files"]
            with patch.object(cloud_research, "_PROCESS_EPOCH", uuid4().hex):
                removed = cloud_research.reconcile_orphaned_jobs()
            assert unpublished["id"] in removed
            assert cloud_research.job_status(unpublished["id"]) is None

            # Publishing a bundled session must keep its queued reservation.
            saved = bundle_job()
            cloud_research.prepare_job(saved)
            research_sessions._save(project.path, saved)
            assert f"research-sessions/{saved['id']}.json" in read_bundle(project.path)["files"]
            with patch.object(cloud_research, "_PROCESS_EPOCH", uuid4().hex):
                assert saved["id"] not in cloud_research.reconcile_orphaned_jobs()
            assert cloud_research.job_status(saved["id"]) == "queued"

            # A published-or-not call with uncertain provider dispatch always
            # retains both its spend hold and ledger row.
            uncertain = bundle_job()
            cloud_research.prepare_job(uncertain)
            assert cloud_research.claim_job(uncertain["id"])
            call_id = str(uuid4())
            cloud_research.reserve_call(uncertain["id"], call_id, 0.10, 10)
            cloud_research.mark_call_unknown(uncertain["id"], call_id)
            with cloud_research._transaction() as db:
                db.execute(
                    "UPDATE jobs SET status='queued' WHERE session_id=?",
                    (uncertain["id"],),
                )
            with patch.object(cloud_research, "_PROCESS_EPOCH", uuid4().hex):
                assert uncertain["id"] not in cloud_research.reconcile_orphaned_jobs()
            assert cloud_research.job_status(uncertain["id"]) == "queued"
            with cloud_research._connect() as db:
                row = db.execute(
                    "SELECT status,amount_usd FROM calls WHERE call_id=?", (call_id,)
                ).fetchone()
                assert row["status"] == "unknown" and row["amount_usd"] == 0.10
        finally:
            cloud_workspaces._CURRENT.reset(binding)


def test_json_project_session_playback(
    root: Path, ledger_root: Path, limits_env: dict[str, str]
) -> None:
    """Hosted JSON projects execute and reopen saved role calls as real sessions."""
    member = workspace(root / "json-playback", "f" * 32)
    with (
        patch.dict(
            os.environ,
            {
                **limits_env,
                "SIGMA_CLOUD_USER_TOKEN_BUDGET": "1000000",
            },
            clear=False,
        ),
        patch.object(cloud_workspaces, "storage_root", return_value=ledger_root),
    ):
        binding = cloud_workspaces._CURRENT.set(member)
        try:
            project = initialize_project(
                member.path / "playback.json", "Portable playback", "Check a bound"
            )
            strategy = create_strategy(
                project.path, "Investigation", "Derive the bound, then challenge it."
            ).project.strategies[0]
            limits = {
                "research_rounds": 1,
                "model_calls": 2,
                "session_duration_minutes": 5,
                "output_tokens_per_call": 256,
                "maximum_estimated_cost_usd": 0.25,
            }
            research_sessions.save_limits(project.path, limits)
            credential = {
                "mode": "api_key",
                "identity": "cloud_service_api_key:" + member.subject_hash,
                "token": "fake-service-key",
                "status": "connected",
            }
            configuration = {
                "available": True,
                "model": "gpt-6.1-sol",
                "reasoning_effort": "high",
            }
            outputs = research_outputs()

            async def provider(record, role, context, timeout_seconds=None, step_id=None):
                del record, context, timeout_seconds
                assert isinstance(step_id, str)
                return (
                    outputs[0] if role == "investigator" else outputs[1],
                    {
                        "input_tokens": 90,
                        "cached_input_tokens": 0,
                        "output_tokens": 30,
                    },
                )

            async def execute() -> dict[str, Any]:
                with (
                    patch.object(
                        research_sessions,
                        "auth_context",
                        new=AsyncMock(return_value=credential),
                    ),
                    patch.object(
                        research_sessions,
                        "configuration",
                        new=AsyncMock(return_value=configuration),
                    ),
                    patch.object(research_sessions, "execution_capabilities", return_value=[]),
                    patch.object(
                        research_sessions, "_call", new=AsyncMock(side_effect=provider)
                    ) as calls,
                ):
                    started = await research_sessions.start_session(
                        project.path,
                        strategy.id,
                        str(uuid4()),
                        project.project.id,
                        credential["identity"],
                        limits,
                    )
                    for _ in range(500):
                        current = research_sessions.get_session(project.path, started["id"])
                        if current["status"] in {"ended", "failed", "paused"}:
                            break
                        await asyncio.sleep(0.01)
                    else:
                        raise AssertionError("JSON-backed session never finished")
                    assert calls.await_count == 2, (current["status"], current["message"])
                    return current

            finished = asyncio.run(execute())
            assert finished["status"] == "ended"
            reopened = research_sessions.list_sessions(project.path)
            assert len(reopened) == 1
            played = reopened[0]
            assert played["id"] == finished["id"]
            assert played["status"] == "ended"
            assert len(played["steps"]) == 2
            assert len(played["artifacts"]) == 1
            assert played["estimated_cost_usd"] == finished["estimated_cost_usd"]
            assert any(event["kind"] == "call.completed" for event in played["events"])
            from sigma.project_bundle import read_bundle

            assert f"research-sessions/{played['id']}.json" in read_bundle(project.path)["files"]
        finally:
            cloud_workspaces._CURRENT.reset(binding)


def test_failed_session_releases_project_slot(
    root: Path, ledger_root: Path, limits_env: dict[str, str]
) -> None:
    """A terminal provider failure must not strand its durable project slot."""
    member = workspace(root / "failed-session-slot", "a" * 32)
    with (
        patch.dict(
            os.environ,
            {
                **limits_env,
                "SIGMA_CLOUD_USER_TOKEN_BUDGET": "1000000",
            },
            clear=False,
        ),
        patch.object(cloud_workspaces, "storage_root", return_value=ledger_root),
    ):
        binding = cloud_workspaces._CURRENT.set(member)
        try:
            project = initialize_project(
                member.path / "disconnect.sigma", "Disconnect recovery", "Check slot release"
            )
            strategy = create_strategy(
                project.path, "Bounded", "Inspect one finite case."
            ).project.strategies[0]
            limits = {
                "research_rounds": 1,
                "model_calls": 2,
                "session_duration_minutes": 5,
                "output_tokens_per_call": 256,
                "maximum_estimated_cost_usd": 0.25,
                "max_concurrent_sessions": 1,
            }
            research_sessions.save_limits(project.path, limits)
            credential = {
                "mode": "api_key",
                "identity": "cloud_service_api_key:" + member.subject_hash,
                "token": "fixture-service-key",
                "status": "connected",
            }
            model_config = {
                "available": True,
                "model": "gpt-6.1-sol",
                "reasoning_effort": "high",
            }

            async def disconnected_provider(*_args, **_kwargs):
                raise ProjectError("Provider connection was disconnected during Play.")

            async def healthy_provider(record, role, context, timeout_seconds=None, step_id=None):
                del record, context, timeout_seconds
                assert isinstance(step_id, str)
                outputs = research_outputs()
                return outputs[0] if role == "investigator" else outputs[1], {
                    "input_tokens": 90,
                    "cached_input_tokens": 0,
                    "output_tokens": 30,
                }

            async def exercise() -> tuple[dict[str, Any], dict[str, Any]]:
                with ExitStack() as stack:
                    stack.enter_context(
                        patch.object(
                            research_sessions,
                            "auth_context",
                            new=AsyncMock(return_value=credential),
                        )
                    )
                    stack.enter_context(
                        patch.object(
                            research_sessions,
                            "configuration",
                            new=AsyncMock(return_value=model_config),
                        )
                    )
                    stack.enter_context(
                        patch.object(research_sessions, "execution_capabilities", return_value=[])
                    )
                    stack.enter_context(
                        patch.object(
                            research_sessions,
                            "_call",
                            new=AsyncMock(side_effect=disconnected_provider),
                        )
                    )
                    failed_start = await research_sessions.start_session(
                        project.path,
                        strategy.id,
                        str(uuid4()),
                        project.project.id,
                        credential["identity"],
                        limits,
                    )
                    for _ in range(500):
                        failed = research_sessions.get_session(project.path, failed_start["id"])
                        if (
                            failed["status"] == "failed"
                            and failed_start["id"] not in research_sessions._tasks
                        ):
                            break
                        await asyncio.sleep(0.01)
                    else:
                        raise AssertionError("disconnected session did not reach failed state")
                assert failed["status"] == "failed"
                assert cloud_research.job_status(failed["id"]) == "terminal"
                # Recreate the reported invisible-occupant failure: the UI's
                # saved session is terminal, while an old execution ledger row
                # still claims to be running after its worker disappeared.
                with cloud_research._transaction() as db:
                    db.execute(
                        "UPDATE jobs SET status='running',process_epoch=? WHERE session_id=?",
                        (uuid4().hex, failed["id"]),
                    )
                assert (
                    research_sessions.get_session(project.path, failed["id"])["status"] == "failed"
                )
                assert cloud_research.job_status(failed["id"]) == "running"
                with patch.object(cloud_research, "_PROCESS_EPOCH", uuid4().hex):
                    cloud_research.reconcile_orphaned_jobs()
                assert cloud_research.job_status(failed["id"]) == "terminal"

                with ExitStack() as stack:
                    stack.enter_context(
                        patch.object(
                            research_sessions,
                            "auth_context",
                            new=AsyncMock(return_value=credential),
                        )
                    )
                    stack.enter_context(
                        patch.object(
                            research_sessions,
                            "configuration",
                            new=AsyncMock(return_value=model_config),
                        )
                    )
                    stack.enter_context(
                        patch.object(research_sessions, "execution_capabilities", return_value=[])
                    )
                    stack.enter_context(
                        patch.object(
                            research_sessions,
                            "_call",
                            new=AsyncMock(side_effect=healthy_provider),
                        )
                    )
                    next_start = await research_sessions.start_session(
                        project.path,
                        strategy.id,
                        str(uuid4()),
                        project.project.id,
                        credential["identity"],
                        limits,
                    )
                    for _ in range(500):
                        next_state = research_sessions.get_session(project.path, next_start["id"])
                        if next_state["status"] in {"ended", "failed", "paused"}:
                            break
                        await asyncio.sleep(0.01)
                    else:
                        raise AssertionError("follow-up session never reached a saved state")
                return failed, next_state

            failed, next_state = asyncio.run(exercise())
            assert failed["status"] == "failed"
            assert next_state["status"] == "ended"
            assert cloud_research.job_status(failed["id"]) == "terminal"
        finally:
            cloud_workspaces._CURRENT.reset(binding)


def test_issue289_global_funding_pause_can_resume(
    root: Path, ledger_root: Path, limits_env: dict[str, str]
) -> None:
    """A global reserve denial pauses a real sample session; replenishment resumes without replay."""
    from sigma.projects import update_project
    from sigma.samples import open_sample_project

    member = workspace(root / "issue289-funding", "9" * 32)
    export_root = os.environ.get("SIGMA_ISSUE_289_EXPORT_DIR")
    exported: list[dict[str, str]] = []
    with (
        patch.dict(
            os.environ,
            {
                **limits_env,
                "SIGMA_CLOUD_GLOBAL_SPEND_CEILING_USD": "0.06",
                "SIGMA_CLOUD_USER_TOKEN_BUDGET": "1000000",
            },
            clear=False,
        ),
        patch.object(cloud_workspaces, "storage_root", return_value=ledger_root),
        patch.object(cloud_research, "_admin_has_unlimited_spend", return_value=True),
    ):
        binding = cloud_workspaces._CURRENT.set(member)
        try:
            project = open_sample_project("operation-narrow-passage")
            # The built-in ONP sample now carries real, saved investigation
            # history for reviewers. This regression is specifically about a
            # fresh funding interruption, so remove that history only from
            # this disposable test copy while retaining its project setup.
            sample_session_dir = Path(project.path) / "research-sessions"
            for prior_session in research_sessions.list_sessions(project.path):
                (sample_session_dir / f"{prior_session['id']}.json").unlink()
            settings = project.project
            expected = {
                "title": settings.title,
                "problem": settings.problem,
                "investigation_type": settings.investigation_type.value,
                "ai_model": settings.ai_model,
                "reasoning_effort": settings.reasoning_effort,
                "difficulty": settings.difficulty.value if settings.difficulty else None,
                "show_advanced_outcome_details": settings.show_advanced_outcome_details,
            }
            project = update_project(
                project.path,
                "Operation Narrow Passage v2",
                settings.problem,
                settings.investigation_type.value,
                "gpt-6.1-sol",
                "high",
                expected,
                difficulty="hard",
            )
            limits = research_sessions.save_limits(
                project.path,
                {
                    **research_sessions.DEFAULT_LIMITS,
                    "research_rounds": 2,
                    "model_calls": 4,
                    "session_duration_minutes": 15,
                    "output_tokens_per_call": 4000,
                    "maximum_estimated_cost_usd": None,
                    "max_concurrent_sessions": 1,
                },
            )
            strategy = next(
                item
                for item in project.project.strategies
                if item.id in project.project.active_order
            )
            credential = {
                "mode": "api_key",
                "identity": "cloud_service_api_key:" + member.subject_hash,
                "token": "fixture-service-key",
                "status": "connected",
            }
            config = {"available": True, "model": "gpt-6.1-sol", "reasoning_effort": "high"}
            investigator, skeptic = research_outputs()
            investigator.update(
                {
                    "claim": "A time-limited humanitarian evacuation with parallel deconfliction is a conditional option, not an established solution.",
                    "method": "Compare the first response options against casualty protection, sovereignty, escalation risk, reversibility, and information gaps in the fictional brief.",
                    "assumptions": [
                        "The stated casualty and deadline details are scenario facts, not verified external intelligence."
                    ],
                    "evidence_status": "Fixture-reported analysis of the saved fictional scenario; no external sources or computations were used.",
                    "open_obligations": [
                        "Test whether a temporary evacuation arrangement can protect personnel without silently conceding the outpost question."
                    ],
                }
            )
            skeptic.update(
                {
                    "response": "The option depends on Chinese cooperation and Philippine consent, neither of which is established. It may save lives while leaving the outpost dispute unresolved.",
                    "objections": [
                        "The brief gives no verified command authority, evacuation capacity, or enforceable guarantee."
                    ],
                    "remaining_obligations": [
                        "Identify a reversible trigger and a credible fallback if the deadline or safe-passage terms change."
                    ],
                    "next_question": "Which decision trigger changes the recommendation without treating disputed video as verified evidence?",
                    "solution_claim": "No strategy is established; a reversible humanitarian option remains conditional and incomplete.",
                    "argument_summary": "The response preserves a possible humanitarian off-ramp but cannot establish its feasibility or settle the sovereignty dispute.",
                    "assumptions_reviewed": [
                        "The stated casualty and deadline details are scenario facts, not verified external intelligence."
                    ],
                    "proof_obligations": [
                        "Test the safe-passage guarantee, decision authority, and fallback conditions."
                    ],
                }
            )
            provider_outputs = [investigator, skeptic, investigator, skeptic]
            roles: list[str] = []

            async def fixture_call(record, role, context, timeout_seconds=None, step_id=None):
                del record, context, timeout_seconds
                assert isinstance(step_id, str)
                roles.append(role)
                output = provider_outputs.pop(0)
                return output, {
                    "input_tokens": 1200,
                    "cached_input_tokens": 200,
                    "output_tokens": 250,
                }

            async def launch() -> dict[str, Any]:
                with ExitStack() as stack:
                    stack.enter_context(
                        patch.object(
                            research_sessions,
                            "auth_context",
                            new=AsyncMock(return_value=credential),
                        )
                    )
                    stack.enter_context(
                        patch.object(
                            research_sessions, "configuration", new=AsyncMock(return_value=config)
                        )
                    )
                    stack.enter_context(
                        patch.object(research_sessions, "execution_capabilities", return_value=[])
                    )
                    stack.enter_context(
                        patch.object(research_sessions, "_reserve_cost", return_value=0.03)
                    )
                    stack.enter_context(
                        patch.object(research_sessions, "_estimate_cost", return_value=0.025)
                    )
                    stack.enter_context(
                        patch.object(
                            research_sessions, "_call", new=AsyncMock(side_effect=fixture_call)
                        )
                    )
                    stack.enter_context(
                        patch.object(openai_connection, "cloud_credential", return_value=True)
                    )
                    started = await research_sessions.start_session(
                        project.path,
                        strategy.id,
                        str(uuid4()),
                        project.project.id,
                        credential["identity"],
                        limits,
                    )
                    task = research_sessions._tasks[started["id"]]
                    await asyncio.wait_for(task, timeout=30)
                    return research_sessions.get_session(project.path, started["id"])

            # No provider is contacted: reserve_call and settlement use SIGMA's
            # real SQLite ledger while _call is a deterministic fixture.
            failed = asyncio.run(launch())
            assert failed["calls_used"] == 2, failed
            assert failed["estimated_cost_usd"] == 0.05, failed
            assert failed["status"] == "paused", failed
            assert "global inference-spend ceiling" in failed["message"], failed["message"]
            assert roles == ["investigator", "skeptic"], roles
            assert cloud_research.job_status(failed["id"]) == "paused"
            denied_steps = [
                step for step in failed["steps"] if step.get("failure_kind") == "budget_denied"
            ]
            assert len(denied_steps) == 1 and denied_steps[0]["attempt_status"] == "not_dispatched"
            with cloud_research._connect() as db:
                ledger_calls = db.execute(
                    "SELECT COUNT(*),SUM(amount_usd) FROM calls WHERE session_id=?",
                    (failed["id"],),
                ).fetchone()
            assert ledger_calls[0] == 2 and abs(ledger_calls[1] - 0.05) < 0.000001
            if export_root:
                destination = Path(export_root)
                destination.mkdir(mode=0o700, parents=True, exist_ok=True)
                bundle_path = destination / "deterministic-funding-denied.json"
                bundle_path.write_bytes(export_complete_project(project.path))
                exported.append({"path": str(bundle_path), "phase": "funding-denied"})

            # Replenish only the isolated fixture's global ceiling. Resume must
            # continue at the undispatched role and retain the earlier two calls.
            os.environ["SIGMA_CLOUD_GLOBAL_SPEND_CEILING_USD"] = "0.20"

            async def resume_and_wait() -> dict[str, Any]:
                with ExitStack() as stack:
                    stack.enter_context(
                        patch.object(
                            research_sessions,
                            "auth_context",
                            new=AsyncMock(return_value=credential),
                        )
                    )
                    stack.enter_context(
                        patch.object(
                            research_sessions, "configuration", new=AsyncMock(return_value=config)
                        )
                    )
                    stack.enter_context(
                        patch.object(research_sessions, "execution_capabilities", return_value=[])
                    )
                    stack.enter_context(
                        patch.object(research_sessions, "_reserve_cost", return_value=0.03)
                    )
                    stack.enter_context(
                        patch.object(research_sessions, "_estimate_cost", return_value=0.025)
                    )
                    stack.enter_context(
                        patch.object(
                            research_sessions, "_call", new=AsyncMock(side_effect=fixture_call)
                        )
                    )
                    stack.enter_context(
                        patch.object(openai_connection, "cloud_credential", return_value=True)
                    )
                    resumed = await research_sessions.control_session(
                        project.path, failed["id"], "resume"
                    )
                    if resumed["status"] == "queued":
                        await asyncio.wait_for(research_sessions._tasks[failed["id"]], timeout=30)
                        resumed = research_sessions.get_session(project.path, failed["id"])
                    return resumed

            resumed = asyncio.run(resume_and_wait())
            assert [step["role"] for step in resumed["steps"][:2]] == ["investigator", "skeptic"]
            assert len(resumed["steps"]) >= 4, resumed
            assert resumed["steps"][0]["id"] != resumed["steps"][2]["id"]
            assert resumed["status"] == "ended", resumed
            assert roles == ["investigator", "skeptic", "investigator", "skeptic"], roles
            assert len(resumed["artifacts"]) >= 2
            if export_root:
                destination = Path(export_root)
                bundle_path = destination / "deterministic-funding-resumed.json"
                bundle_path.write_bytes(export_complete_project(project.path))
                exported.append({"path": str(bundle_path), "phase": "resumed-terminal"})
                manifest = {
                    "fixture": "deterministic mocked provider; no paid or live calls",
                    "source_sample": "samples/operation-narrow-passage",
                    "project_id": project.project.id,
                    "session_id": failed["id"],
                    "session_number": failed["session_number"],
                    "model": "gpt-6.1-sol",
                    "reasoning_effort": "high",
                    "configured_rounds": 2,
                    "configured_agent_turns": 4,
                    "global_ceiling_usd": 0.06,
                    "fixture_call_estimate_usd": 0.025,
                    "rejected_reservation_usd": 0.03,
                    "activities": [
                        "2 successful fixture calls",
                        "3rd call rejected before dispatch",
                        "global ceiling replenished",
                        "same session resumed",
                    ],
                    "exports": exported,
                    "omissions": [
                        "Original production Session #1 is not present in the checkout or connected Drive; these exports reproduce the accounting boundary from a fresh copy of the shipped sample."
                    ],
                }
                (destination / "manifest.json").write_text(
                    json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
                )
        finally:
            cloud_workspaces._CURRENT.reset(binding)


def test_auxiliary_inference_ignores_full_research_slots_but_tracks_cost(
    root: Path, ledger_root: Path
) -> None:
    """Small AI calls remain available when every research worker slot is occupied."""
    owner = workspace(root, "a" * 32)
    settings = {
        "SIGMA_CLOUD_AUTH_ENABLED": "true",
        "SIGMA_CLOUD_INFERENCE_PROVIDER": "api_key",
        "SIGMA_CLOUD_OPENAI_API_KEY": "auxiliary-fixture-key",
        "SIGMA_CLOUD_GLOBAL_SPEND_CEILING_USD": "5.00",
        "SIGMA_CLOUD_USER_SPEND_CEILING_USD": "2.00",
        "SIGMA_CLOUD_USER_MAX_CONCURRENT": "1",
        "SIGMA_CLOUD_GLOBAL_MAX_CONCURRENT": "1",
        "SIGMA_CLOUD_USER_MAX_QUEUED": "1",
        "SIGMA_CLOUD_GLOBAL_MAX_QUEUED": "1",
        "SIGMA_CLOUD_USER_TOKEN_BUDGET": "1000000",
    }
    with (
        patch.dict(os.environ, settings, clear=False),
        patch.object(cloud_workspaces, "storage_root", return_value=ledger_root),
    ):
        binding = cloud_workspaces._CURRENT.set(owner)
        try:
            view = initialize_project(
                owner.path / "auxiliary.sigma", "Auxiliary inference", "Check capacity isolation"
            )
            research = job(owner.workspace_id)
            cloud_research.prepare_job(research)
            assert cloud_research.claim_job(research["id"])
            auxiliary_a = cloud_research.begin_standalone_inference(view.project.id, view.path)
            auxiliary_b = cloud_research.begin_standalone_inference(view.project.id, view.path)
            with cloud_research._connect() as db:
                rows = db.execute(
                    "SELECT job_kind,status FROM jobs WHERE status='running'"
                ).fetchall()
                assert [row["job_kind"] for row in rows].count("research") == 1
                assert [row["job_kind"] for row in rows].count("auxiliary") == 2
            cloud_research.reserve_call(auxiliary_a, "short-call-fixture", 0.01, 200)
            cloud_research.mark_call_not_dispatched(auxiliary_a, "short-call-fixture")
            cloud_research.finish_standalone_inference(auxiliary_a)
            cloud_research.finish_standalone_inference(auxiliary_b)
            with cloud_research._connect() as db:
                assert (
                    db.execute(
                        "SELECT COUNT(*) FROM jobs WHERE job_kind='auxiliary' AND status='terminal'"
                    ).fetchone()[0]
                    == 2
                )
        finally:
            cloud_workspaces._CURRENT.reset(binding)


def test_multiuser_parallel_cloud_worker_admission(root: Path, ledger_root: Path) -> None:
    """Reject excess before persisting; admit after another owner exits."""
    left = workspace(root, "e" * 32)
    right = workspace(root, "f" * 32)
    settings = {
        "SIGMA_CLOUD_AUTH_ENABLED": "true",
        "SIGMA_CLOUD_INFERENCE_PROVIDER": "api_key",
        "SIGMA_CLOUD_OPENAI_API_KEY": "multi-session-fixture-key",
        "SIGMA_CLOUD_GLOBAL_SPEND_CEILING_USD": "5.00",
        "SIGMA_CLOUD_USER_SPEND_CEILING_USD": "2.00",
        "SIGMA_CLOUD_USER_MAX_CONCURRENT": "2",
        "SIGMA_CLOUD_GLOBAL_MAX_CONCURRENT": "3",
        "SIGMA_CLOUD_USER_TOKEN_BUDGET": "1000000",
    }
    entries = [
        (left, job(left.workspace_id)),
        (left, job(left.workspace_id)),
        (right, job(right.workspace_id)),
        (right, job(right.workspace_id)),
    ]
    with (
        patch.dict(os.environ, settings, clear=False),
        patch.object(cloud_workspaces, "storage_root", return_value=ledger_root),
    ):
        for owner, record in entries[:3]:
            token = cloud_workspaces._CURRENT.set(owner)
            try:
                cloud_research.prepare_job(record)
            finally:
                cloud_workspaces._CURRENT.reset(token)

        # Pending execution claims already occupy a slot: no queue.
        token = cloud_workspaces._CURRENT.set(right)
        try:
            try:
                cloud_research.prepare_job(entries[3][1])
            except cloud_research.CloudResearchUnavailable as exc:
                assert "capacity is currently full" in str(exc)
            else:
                raise AssertionError("Fourth research job must be refused immediately")
            with cloud_research._connect() as db:
                assert db.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 3
                assert db.execute("SELECT COUNT(*) FROM calls").fetchone()[0] == 0
        finally:
            cloud_workspaces._CURRENT.reset(token)

        for owner, record in entries[:3]:
            token = cloud_workspaces._CURRENT.set(owner)
            try:
                assert cloud_research.claim_job(record["id"])
            finally:
                cloud_workspaces._CURRENT.reset(token)
        token = cloud_workspaces._CURRENT.set(left)
        try:
            cloud_research.release_job(entries[0][1]["id"], paused=True)
        finally:
            cloud_workspaces._CURRENT.reset(token)

        token = cloud_workspaces._CURRENT.set(right)
        try:
            cloud_research.prepare_job(entries[3][1])
            assert cloud_research.claim_job(entries[3][1]["id"])
        finally:
            cloud_workspaces._CURRENT.reset(token)

        with cloud_research._connect() as db:
            counts = db.execute(
                "SELECT workspace_id,COUNT(*) AS count FROM jobs "
                "WHERE status='running' GROUP BY workspace_id"
            ).fetchall()
            assert {row["workspace_id"]: row["count"] for row in counts} == {
                left.workspace_id: 1,
                right.workspace_id: 2,
            }


def test_hosted_deployment_forwards_global_spend_window() -> None:
    compose = (Path(__file__).resolve().parents[1] / "deploy" / "compose.yaml").read_text(
        encoding="utf-8"
    )
    assert (
        "SIGMA_CLOUD_GLOBAL_SPEND_WINDOW: ${SIGMA_CLOUD_GLOBAL_SPEND_WINDOW:-cumulative}" in compose
    ), "The hosted backend silently ignored the approved spending-window setting."


def main() -> None:
    # This suite validates the explicitly configured API-key admission path;
    # never inherit the repository's local ChatGPT provider default.
    os.environ.setdefault("SIGMA_CLOUD_INFERENCE_PROVIDER", "api_key")
    os.environ.setdefault("SIGMA_CLOUD_OPENAI_API_KEY", "cloud-research-fixture-key")
    test_hosted_deployment_forwards_global_spend_window()
    with TemporaryDirectory(prefix="sigma-cloud-research-", dir=Path.cwd().parent) as temp:
        base = Path(temp)
        persistent_root = (
            base / "persistent-disk"
            if os.environ.get("SIGMA_T100_PERSISTENT_DISK") == "1"
            else None
        )
        if persistent_root is not None:
            persistent_root.mkdir(mode=0o700)
            root = persistent_root / "workspaces"
            root.mkdir(mode=0o700)
            ledger_root = root
        else:
            root = base
            ledger_root = root / "service"
            ledger_root.mkdir(mode=0o700)
        a = workspace(root, "a" * 32)
        b = workspace(root, "b" * 32)
        settings = {
            "SIGMA_CLOUD_AUTH_ENABLED": "true",
            # These admission tests exercise the API-key funding path. Keep
            # ambient repository defaults (which may select ChatGPT) out of
            # their deterministic provider assertions.
            "SIGMA_CLOUD_INFERENCE_PROVIDER": "api_key",
            "SIGMA_CLOUD_OPENAI_API_KEY": "cloud-research-fixture-key",
            "SIGMA_CLOUD_GLOBAL_SPEND_CEILING_USD": "1.00",
            "SIGMA_CLOUD_USER_SPEND_CEILING_USD": "2.00",
            "SIGMA_CLOUD_USER_MAX_CONCURRENT": "1",
            "SIGMA_CLOUD_GLOBAL_MAX_CONCURRENT": "1",
            "SIGMA_CLOUD_USER_MAX_QUEUED": "2",
            "SIGMA_CLOUD_GLOBAL_MAX_QUEUED": "2",
            "SIGMA_CLOUD_USER_TOKEN_BUDGET": "1000",
        }
        if os.environ.get("SIGMA_T100_PERSISTENT_DISK") == "1":
            assert persistent_root is not None
            settings.update(
                {
                    "SIGMA_STORAGE_BACKEND": "persistent_disk",
                    "SIGMA_STORAGE_ROOT": str(persistent_root),
                    "SIGMA_CLOUD_WORKSPACES_ROOT": str(root),
                }
            )
        with patch.dict(
            os.environ,
            {
                "SIGMA_CLOUD_AUTH_ENABLED": "true",
                "SIGMA_CLOUD_INFERENCE_PROVIDER": "api_key",
                "OPENAI_API_KEY": "local-operator-key-must-not-be-used",
                "SIGMA_CLOUD_OPENAI_API_KEY": "",
            },
            clear=False,
        ):
            cloud_credential = asyncio.run(openai_connection.sponsored_auth_context(a.subject_hash))
            assert cloud_credential["status"] == "unconfigured"
            assert cloud_credential["token"] == ""
        with patch.dict(
            os.environ,
            {
                "SIGMA_CLOUD_AUTH_ENABLED": "true",
                "SIGMA_CLOUD_INFERENCE_PROVIDER": "api_key",
                "SIGMA_CLOUD_OPENAI_API_KEY": "explicit-cloud-fixture",
            },
            clear=False,
        ):
            cloud_credential = asyncio.run(openai_connection.sponsored_auth_context(a.subject_hash))
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
                # A running job must never be claimed by a second worker:
                # doing so could dispatch the same provider step twice.
                assert not cloud_research.claim_job(first["id"])
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
                try:
                    cloud_research.prepare_job(second)
                except cloud_research.CloudResearchUnavailable as exc:
                    assert "capacity is currently full" in str(exc)
                else:
                    raise AssertionError("Second research job must fail fast at capacity")
                assert cloud_research.job_status(second["id"]) is None
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
                try:
                    cloud_research.prepare_job(third)
                except cloud_research.CloudResearchUnavailable as exc:
                    assert "capacity is currently full" in str(exc)
                else:
                    raise AssertionError("Third research job must fail fast at global capacity")
                assert cloud_research.job_status(third["id"]) is None
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
                    "maximum_estimated_cost_usd": 0.25,
                    "maximum_input_tokens_per_session": 600_000,
                }
                research_sessions.save_limits(live_view.path, session_limits)
                credential = {
                    "mode": "api_key",
                    "identity": "cloud_service_api_key:" + a.subject_hash,
                    "token": "test-server-key",
                    "status": "connected",
                }
                model_config = {
                    "available": True,
                    "model": "gpt-6.1-sol",
                    "reasoning_effort": "high",
                }
                outputs = research_outputs()

                async def fake_call(record, role, context, timeout_seconds=None, step_id=None):
                    del record, context, timeout_seconds
                    assert isinstance(step_id, str)
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
                # Browser reload fetches a fresh projection from durable
                # project storage, not the task's in-memory result.
                reopened = research_sessions.list_sessions(live_view.path)
                saved = next(entry for entry in reopened if entry["id"] == integrated["id"])
                assert saved["status"] == "ended"
                assert len(saved["artifacts"]) == 1
                assert len(saved["steps"]) == 2
                assert saved["calls_used"] == 2
                assert [step["role"] for step in saved["steps"]] == ["investigator", "skeptic"]
                assert any(event["kind"] == "call.completed" for event in saved["events"])
                assert saved["outcome"]["metrics"]["operational"]
                assert saved["estimated_cost_usd"] == integrated["estimated_cost_usd"]
                # Hosted hard-budget and provider reservations describe the
                # same attempts. Both must settle without leaving a second
                # phantom token hold or rejecting the Skeptic call.
                assert integrated["tokens_reserved"] == 0, integrated["tokens_reserved"]
                assert len(integrated["hard_budget_ledger"]["calls"]) == 2
                assert all(
                    entry["status"] == "settled"
                    for entry in integrated["hard_budget_ledger"]["calls"]
                )
                assert cloud_research.snapshot()["user_reserved_and_estimated_usd"] < 1.0

                async def run_clipped_call() -> None:
                    """A provider response clipped at its output limit still settles usage."""
                    before = cloud_research.snapshot()
                    clipped = research_sessions.IncompleteResearchResponse(
                        "Provider response exceeded max output tokens.",
                        partial_text="Saved partial investigation output.",
                        usage={
                            "input_tokens": 90,
                            "cached_input_tokens": None,
                            "output_tokens": 256,
                        },
                    )
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
                        patch.object(research_sessions, "execution_capabilities", return_value=[]),
                        patch.object(
                            research_sessions, "_call", new=AsyncMock(side_effect=clipped)
                        ) as calls,
                    ):
                        started = await research_sessions.start_session(
                            live_view.path,
                            live_strategy.id,
                            str(uuid4()),
                            live_view.project.id,
                            credential["identity"],
                            session_limits,
                        )
                        for _ in range(300):
                            ended = research_sessions.get_session(live_view.path, started["id"])
                            if ended["status"] in {"ended", "failed", "paused"}:
                                break
                            await asyncio.sleep(0.01)
                        else:
                            raise AssertionError("clipped cloud call did not save a terminal state")
                        assert ended["status"] == "ended", ended["message"]
                        assert calls.await_count == 1
                        assert ended["steps"][0]["status"] == "incomplete"
                        assert ended["steps"][0]["attempt_status"] == "usage_estimated"
                        assert ended["tokens_reserved"] == 0
                        assert ended["estimated_cost_usd"] > 0
                        assert ended["steps"][0]["partial_output"] == clipped.partial_text
                        persisted = research_sessions.list_sessions(live_view.path)
                        assert any(
                            item["id"] == started["id"]
                            and item["steps"][0]["attempt_status"] == "usage_estimated"
                            for item in persisted
                        )
                        with cloud_research._connect() as db:
                            call = db.execute(
                                "SELECT status,input_tokens,output_tokens FROM calls WHERE call_id=?",
                                (ended["steps"][0]["id"],),
                            ).fetchone()
                            assert call["status"] == "usage_estimated"
                            assert call["input_tokens"] == 90
                            assert call["output_tokens"] == 256
                        after = cloud_research.snapshot()
                        assert after["held_usd"] == before["held_usd"], (before, after)

                with patch.dict(os.environ, {"SIGMA_CLOUD_USER_TOKEN_BUDGET": "1000000"}):
                    asyncio.run(run_clipped_call())

                async def run_invalid_response() -> None:
                    """Known usage must settle even when the agent violates an acknowledgment rule."""
                    before = cloud_research.snapshot()
                    outputs = research_outputs()

                    async def completed_call(
                        record, role, context, timeout_seconds=None, step_id=None
                    ):
                        del record, role, context, timeout_seconds
                        assert isinstance(step_id, str)
                        return outputs[0], {
                            "input_tokens": 90,
                            "cached_input_tokens": 0,
                            "output_tokens": 30,
                        }

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
                        patch.object(research_sessions, "execution_capabilities", return_value=[]),
                        patch.object(research_sessions, "_call", side_effect=completed_call),
                        patch.object(
                            research_sessions,
                            "_validate_guidance_acknowledgments",
                            side_effect=research_sessions.ProjectError(
                                "Agent response did not acknowledge delivered intervention"
                            ),
                        ),
                    ):
                        started = await research_sessions.start_session(
                            live_view.path,
                            live_strategy.id,
                            str(uuid4()),
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
                            raise AssertionError("invalid response did not reach a saved state")
                        assert failed["status"] == "failed", failed["message"]
                        assert failed["steps"][0]["failure_kind"] == "response_invalid"
                        assert failed["steps"][0]["attempt_status"] == "usage_estimated"
                        assert failed["steps"][0]["token_usage_status"] == "reported"
                        assert failed["token_usage_status"] == "complete"
                        assert failed["tokens_used"] == 120
                        assert failed["tokens_reserved"] == 0
                        assert "output" not in failed["steps"][0]
                        with cloud_research._connect() as db:
                            call = db.execute(
                                "SELECT status,input_tokens,output_tokens FROM calls WHERE call_id=?",
                                (failed["steps"][0]["id"],),
                            ).fetchone()
                            assert call["status"] == "usage_estimated"
                            assert call["input_tokens"] == 90
                            assert call["output_tokens"] == 30
                        assert cloud_research.snapshot()["held_usd"] == before["held_usd"]

                with patch.dict(os.environ, {"SIGMA_CLOUD_USER_TOKEN_BUDGET": "1000000"}):
                    asyncio.run(run_invalid_response())

                async def run_rejected_call() -> None:
                    """Explicit HTTP 429 cannot retain durable or session-local token holds."""
                    before = cloud_research.snapshot()
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
                        patch.object(research_sessions, "execution_capabilities", return_value=[]),
                        patch.object(
                            research_sessions,
                            "_call",
                            new=AsyncMock(
                                side_effect=research_sessions.ProjectError(
                                    "ChatGPT plan or app usage limit reached (HTTP 429)."
                                )
                            ),
                        ) as calls,
                    ):
                        started = await research_sessions.start_session(
                            live_view.path,
                            live_strategy.id,
                            str(uuid4()),
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
                            raise AssertionError(
                                "rejected provider call never reached a saved state"
                            )
                        assert calls.await_count == 1
                        assert failed["status"] in {"ended", "failed"}, failed["message"]
                        assert failed["steps"][0]["failure_kind"] == "provider_limited"
                        assert failed["steps"][0]["attempt_status"] == "provider_rejected"
                        assert failed["tokens_reserved"] == 0
                        assert failed["estimated_cost_reserved_usd"] == 0
                        with cloud_research._connect() as db:
                            call = db.execute(
                                "SELECT status,amount_usd,token_reservation FROM calls WHERE call_id=?",
                                (failed["steps"][0]["id"],),
                            ).fetchone()
                            assert call["status"] == "usage_estimated"
                            assert call["amount_usd"] == 0
                            assert call["token_reservation"] == 0
                        after = cloud_research.snapshot()
                        assert after["held_usd"] == before["held_usd"]
                        assert (
                            after["user_reserved_or_observed_tokens"]
                            == (before["user_reserved_or_observed_tokens"])
                        )

                with patch.dict(os.environ, {"SIGMA_CLOUD_USER_TOKEN_BUDGET": "1000000"}):
                    asyncio.run(run_rejected_call())

                async def run_aggregate_token_denial() -> None:
                    """Pre-dispatch session-token denial cannot retain a hard-budget hold."""
                    before = cloud_research.snapshot()
                    original_save = research_sessions._save

                    def save_with_tiny_token_limit(path, record):
                        if (
                            record.get("project_id") == live_view.project.id
                            and record.get("status") == "queued"
                            and record.get("calls_used") == 0
                        ):
                            record["total_token_limit"] = 1
                        return original_save(path, record)

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
                        patch.object(research_sessions, "execution_capabilities", return_value=[]),
                        patch.object(
                            research_sessions, "_save", side_effect=save_with_tiny_token_limit
                        ),
                        patch.object(research_sessions, "_call", new=AsyncMock()) as calls,
                    ):
                        started = await research_sessions.start_session(
                            live_view.path,
                            live_strategy.id,
                            str(uuid4()),
                            live_view.project.id,
                            credential["identity"],
                            session_limits,
                        )
                        for _ in range(300):
                            current = research_sessions.get_session(live_view.path, started["id"])
                            if current["status"] in {"ended", "failed", "paused"}:
                                break
                            await asyncio.sleep(0.01)
                        else:
                            raise AssertionError("session token preflight denial never terminated")
                        assert calls.await_count == 0
                        assert current["status"] in {"ended", "failed"}
                        assert current["calls_used"] == 0
                        assert current["tokens_reserved"] == 0
                        assert current["hard_budget_ledger"]["calls"] == []
                        after = cloud_research.snapshot()
                        assert after["held_usd"] == before["held_usd"]

                with patch.dict(os.environ, {"SIGMA_CLOUD_USER_TOKEN_BUDGET": "1000000"}):
                    asyncio.run(run_aggregate_token_denial())

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

                    async def hang(record, role, context, timeout_seconds=None, step_id=None):
                        del record, role, context, timeout_seconds
                        assert isinstance(step_id, str)
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
                with patch.dict(os.environ, {"SIGMA_CLOUD_USER_TOKEN_BUDGET": "1000000"}):
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

                with patch.dict(os.environ, {"SIGMA_CLOUD_USER_TOKEN_BUDGET": "1000000"}):
                    # Crash after cloud claim but before the queued session is
                    # published as running: the ledger is "running", its saved
                    # record is "queued", and no worker owns the advisory lock.
                    # Reading it must preserve playback and release the stale slot.
                    stale_project = initialize_project(
                        a.path / "queued-after-claim.sigma", "Stale queue", "Recover a queue"
                    )
                    stale = job(a.workspace_id)
                    stale.update(
                        project_id=stale_project.project.id,
                        project_path=stale_project.path,
                        session_number=1,
                        status="queued",
                        created_at="2026-01-01T00:00:00+00:00",
                        updated_at="2026-01-01T00:00:00+00:00",
                        current_action="Queued",
                        message="Research is queued.",
                        events=[],
                        steps=[],
                        strategy_runs=[{"status": "queued", "strategy_id": "strategy-stale"}],
                    )
                    cloud_research.prepare_job(stale)
                    assert cloud_research.claim_job(stale["id"])
                    assert not cloud_research.claim_job(stale["id"])
                    research_sessions._save(stale_project.path, stale)
                    recovered_queue = research_sessions._recover(stale)
                    assert recovered_queue["status"] == "paused"
                    assert recovered_queue["strategy_runs"][0]["status"] == "paused"
                    saved_queue = research_sessions._read(stale_project.path, stale["id"])
                    assert saved_queue["status"] == "paused"
                    assert saved_queue["steps"] == []
                    assert saved_queue["events"][-1]["kind"] == "interrupted"
                    assert cloud_research.job_status(stale["id"]) == "interrupted"

                    # A reconnect can spawn a worker before anyone opens the
                    # saved session. It must not repeatedly wait on a stale
                    # running ledger slot, or execute a duplicate provider call.
                    stale_worker_project = initialize_project(
                        a.path / "queued-worker.sigma", "Stale worker", "Recover a worker"
                    )
                    stale_worker = job(a.workspace_id)
                    stale_worker.update(
                        project_id=stale_worker_project.project.id,
                        project_path=stale_worker_project.path,
                        session_number=1,
                        status="queued",
                        created_at="2026-01-01T00:00:00+00:00",
                        updated_at="2026-01-01T00:00:00+00:00",
                        current_action="Queued",
                        message="Research is queued.",
                        events=[],
                        steps=[],
                        strategy_runs=[{"status": "queued", "strategy_id": "strategy-worker"}],
                    )
                    cloud_research.prepare_job(stale_worker)
                    assert cloud_research.claim_job(stale_worker["id"])
                    research_sessions._save(stale_worker_project.path, stale_worker)
                    assert (
                        asyncio.run(
                            research_sessions._claim_cloud_job(
                                stale_worker["id"], stale_worker_project.path
                            )
                        )
                        is False
                    )
                    worker_snapshot = research_sessions._read(
                        stale_worker_project.path, stale_worker["id"]
                    )
                    assert worker_snapshot["status"] == "paused"
                    assert worker_snapshot["strategy_runs"][0]["status"] == "paused"
                    assert worker_snapshot["steps"] == []
                    assert worker_snapshot["events"][-1]["kind"] == "interrupted"
                    assert cloud_research.job_status(stale_worker["id"]) == "interrupted"

                    # A legacy queued job that cannot claim a running slot
                    # is paused immediately, without waiting for its deadline.
                    # This is recovery behavior; new capacity-full requests
                    # are refused before a session is created.
                    expiry_project = initialize_project(
                        a.path / "queue-expiry.sigma", "Queue expiry", "Check expiry"
                    )
                    expired = job(a.workspace_id)
                    expired.update(
                        project_id=expiry_project.project.id,
                        project_path=expiry_project.path,
                        session_number=1,
                        status="queued",
                        deadline_at="2026-01-01T00:00:00+00:00",
                        created_at="2026-01-01T00:00:00+00:00",
                        updated_at="2026-01-01T00:00:00+00:00",
                        current_action="Queued",
                        message="Research is queued.",
                        events=[],
                        steps=[],
                        strategy_runs=[
                            {
                                "status": "queued",
                                "strategy_id": "strategy-expired",
                                "strategy_title": "Expired",
                                "artifacts": [],
                            }
                        ],
                    )
                    cloud_research.prepare_job(expired)
                    research_sessions._save(expiry_project.path, expired)
                    with (
                        patch.object(cloud_research, "claim_job", return_value=False),
                        patch.object(
                            research_sessions, "_outcome", return_value={"assessment": "pending"}
                        ),
                        patch.object(research_sessions, "_strategy_assessments", return_value=[]),
                        patch.object(research_sessions, "_portfolio_decision", return_value={}),
                    ):
                        assert (
                            asyncio.run(
                                research_sessions._claim_cloud_job(
                                    expired["id"], expiry_project.path
                                )
                            )
                            is False
                        )
                    played = research_sessions._read(expiry_project.path, expired["id"])
                    assert played["status"] == "paused"
                    assert played["strategy_runs"][0]["status"] == "paused"
                    assert played["events"][-1]["kind"] == "interrupted"
                    assert cloud_research.job_status(expired["id"]) == "paused"
            finally:
                cloud_workspaces._CURRENT.reset(token)

        # Concurrent owners race for one global execution slot. SQLite's
        # BEGIN IMMEDIATE admission must persist exactly one job; excess
        # work is rejected before any worker or call can start.
        with (
            patch.dict(
                os.environ,
                {**settings, "SIGMA_CLOUD_USER_TOKEN_BUDGET": "100000000"},
                clear=False,
            ),
            patch.object(cloud_workspaces, "storage_root", return_value=ledger_root),
        ):
            db = cloud_research._connect()
            db.execute("UPDATE jobs SET status='paused'")
            db.close()
            jobs = [job(a.workspace_id), job(b.workspace_id)]
            barrier = threading.Barrier(2)

            def admit(record: dict, owner: cloud_workspaces.Workspace) -> bool:
                context = cloud_workspaces._CURRENT.set(owner)
                try:
                    barrier.wait(timeout=5)
                    try:
                        cloud_research.prepare_job(record)
                    except cloud_research.CloudResearchUnavailable as exc:
                        assert "capacity is currently full" in str(exc)
                        return False
                    return True
                finally:
                    cloud_workspaces._CURRENT.reset(context)

            with ThreadPoolExecutor(max_workers=2) as pool:
                results = [pool.submit(admit, record, owner) for record, owner in zip(jobs, (a, b))]
                admitted = [future.result(timeout=10) for future in results]
            assert sorted(admitted) == [False, True], admitted
            for record, owner, accepted in zip(jobs, (a, b), admitted):
                token = cloud_workspaces._CURRENT.set(owner)
                try:
                    if accepted:
                        assert cloud_research.claim_job(record["id"])
                    else:
                        assert cloud_research.job_status(record["id"]) is None
                finally:
                    cloud_workspaces._CURRENT.reset(token)

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

        recovery_ledger = root / "orphan-recovery-ledger"
        recovery_ledger.mkdir(mode=0o700)
        test_orphaned_job_reconciliation(root, recovery_ledger, settings)
        json_ledger = root / "json-project-orphan-ledger"
        json_ledger.mkdir(mode=0o700)
        test_json_project_orphan_recovery(root, json_ledger, settings)
        json_playback_ledger = root / "json-playback-ledger"
        json_playback_ledger.mkdir(mode=0o700)
        test_json_project_session_playback(root, json_playback_ledger, settings)
        failed_session_ledger = root / "failed-session-ledger"
        failed_session_ledger.mkdir(mode=0o700)
        test_failed_session_releases_project_slot(root, failed_session_ledger, settings)
        issue289_ledger = root / "issue289-funding-ledger"
        issue289_ledger.mkdir(mode=0o700)
        test_issue289_global_funding_pause_can_resume(root, issue289_ledger, settings)

        budget_ledger = root / "user-budget-ledger"
        budget_ledger.mkdir(mode=0o700)
        test_workspace_spend_budget(root, budget_ledger)
        above_cap_ledger = root / "above-legacy-cap-ledger"
        above_cap_ledger.mkdir(mode=0o700)
        test_configured_session_and_account_budget_above_legacy_cap(root, above_cap_ledger)
        reload_ledger = root / "allowance-reload-ledger"
        reload_ledger.mkdir(mode=0o700)
        test_admin_allowance_reload_preserves_provider_spend(root, reload_ledger)
        parallel_ledger = root / "parallel-worker-ledger"
        parallel_ledger.mkdir(mode=0o700)
        test_multiuser_parallel_cloud_worker_admission(root, parallel_ledger)
        auxiliary_ledger = root / "auxiliary-inference-ledger"
        auxiliary_ledger.mkdir(mode=0o700)
        test_auxiliary_inference_ignores_full_research_slots_but_tracks_cost(root, auxiliary_ledger)
        pilot_ledger = root / "pilot-capacity-ledger"
        pilot_ledger.mkdir(mode=0o700)
        test_pilot_global_spend_accepts_multiple_users(root, pilot_ledger)
        explicit_allowance_ledger = root / "explicit-allowance-ledger"
        explicit_allowance_ledger.mkdir(mode=0o700)
        test_explicit_account_allowance_does_not_require_default(root, explicit_allowance_ledger)
        allowance_ledger = root / "allowance-ledger"
        allowance_ledger.mkdir(mode=0o700)
        test_rule_allowance_controls_reservation_and_reduction_keeps_unknown_hold(
            root, allowance_ledger
        )
        test_hosted_capacity_defaults_allow_eight_distinct_researchers()
        test_local_limits_remain_unmodified(root)
        test_local_global_spend_default_supports_small_team_pilot()
        monthly_ledger = root / "monthly-global-ledger"
        monthly_ledger.mkdir(mode=0o700)
        test_monthly_global_budget_retains_unknown_provider_holds(root, monthly_ledger)
        admin_monthly_ledger = root / "admin-monthly-ledger"
        admin_monthly_ledger.mkdir(mode=0o700)
        test_admin_unlimited_allowance_survives_monthly_global_renewal(root, admin_monthly_ledger)

    print(
        "PASS cloud research admission, user/global accounting, restart recovery, local compatibility, and workspace isolation"
    )


if __name__ == "__main__":
    main()
