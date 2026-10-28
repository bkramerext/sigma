"""Deterministic concurrency, idempotency and accounting tests for Gate B."""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
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
        "maximum_estimated_cost_usd": 0.25,
        "call_limit": 6,
        "duration_limit_minutes": 15,
        "cost_status": "available",
    }


def workspace(root: Path, identifier: str, email: str | None = None) -> cloud_workspaces.Workspace:
    path = root / identifier
    path.mkdir(mode=0o700, exist_ok=True)
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
                "SIGMA_CLOUD_USER_MAX_CONCURRENT": "1",
                "SIGMA_CLOUD_GLOBAL_MAX_CONCURRENT": "2",
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
                item["max_concurrent_sessions"] = 3
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
            ambiguous = derived_job("running")
            cloud_research.prepare_job(ambiguous)
            # Seed a historical concurrent-running state while exercising recovery;
            # admission itself correctly permits only one live session per owner.
            db = cloud_research._connect()
            db.execute("UPDATE jobs SET status='paused' WHERE session_id=?", (running["id"],))
            db.close()
            assert cloud_research.claim_job(ambiguous["id"])
            db = cloud_research._connect()
            db.execute("UPDATE jobs SET status='running' WHERE session_id=?", (running["id"],))
            db.close()
            call_id = str(uuid4())
            cloud_research.reserve_call(ambiguous["id"], call_id, 0.25, 100)
            cloud_research.mark_call_unknown(ambiguous["id"], call_id)
            db = cloud_research._connect()
            db.execute(
                "UPDATE jobs SET process_epoch=? WHERE session_id IN (?,?,?)",
                (old_epoch, valid["id"], running["id"], ambiguous["id"]),
            )
            db.execute("UPDATE jobs SET status='queued' WHERE session_id=?", (ambiguous["id"],))
            db.close()
            with patch.object(cloud_research, "_PROCESS_EPOCH", next_epoch):
                removed = cloud_research.reconcile_orphaned_jobs()
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
                    assert cloud_research.snapshot()["remaining_usd"] == 2.00
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


def test_local_global_spend_default_stays_at_legacy_safe_ceiling() -> None:
    """Raising project session caps does not implicitly raise the local aggregate ceiling."""
    with patch("sigma.cloud_auth.local_sponsored_principal", return_value=object()):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("SIGMA_CLOUD_GLOBAL_SPEND_CEILING_USD", None)
            assert cloud_research._spend_ceiling_decimal() == Decimal("0.25")
            assert "$0.25" in cloud_research._global_ceiling_failure_message()
            assert "SIGMA_CLOUD_GLOBAL_SPEND_CEILING_USD" in (
                cloud_research._global_ceiling_failure_message()
            )
        with patch.dict(os.environ, {"SIGMA_CLOUD_GLOBAL_SPEND_CEILING_USD": "5.00"}):
            assert cloud_research._spend_ceiling_decimal() == Decimal("5.00")


def main() -> None:
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
                    "maximum_estimated_cost_usd": 0.25,
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
            finally:
                cloud_workspaces._CURRENT.reset(token)

        # Concurrent owners race for one global execution slot. SQLite's
        # BEGIN IMMEDIATE transaction must admit exactly one claimant.
        # Prior tests can exhaust the intentionally tiny token allowance;
        # the race tests execution slots rather than token exhaustion.
        with (
            patch.dict(
                os.environ,
                {**settings, "SIGMA_CLOUD_USER_TOKEN_BUDGET": "100000000"},
                clear=False,
            ),
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

        recovery_ledger = root / "orphan-recovery-ledger"
        recovery_ledger.mkdir(mode=0o700)
        test_orphaned_job_reconciliation(root, recovery_ledger, settings)

        budget_ledger = root / "user-budget-ledger"
        budget_ledger.mkdir(mode=0o700)
        test_workspace_spend_budget(root, budget_ledger)
        above_cap_ledger = root / "above-legacy-cap-ledger"
        above_cap_ledger.mkdir(mode=0o700)
        test_configured_session_and_account_budget_above_legacy_cap(root, above_cap_ledger)
        reload_ledger = root / "allowance-reload-ledger"
        reload_ledger.mkdir(mode=0o700)
        test_admin_allowance_reload_preserves_provider_spend(root, reload_ledger)
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
        test_local_limits_remain_unmodified(root)
        test_local_global_spend_default_stays_at_legacy_safe_ceiling()

    print(
        "PASS cloud research admission, user/global accounting, restart recovery, local compatibility, and workspace isolation"
    )


if __name__ == "__main__":
    main()
