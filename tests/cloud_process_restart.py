"""Actual SIGKILL/replacement-process recovery acceptance without paid inference.

The first process persists accepted work while holding OS worker locks. A
second process observes those live locks. After SIGKILL, a third process
reconciles the same ledger and session artifacts, asserting exact zero replay.
"""

from __future__ import annotations

import asyncio
import fcntl
import hashlib
import json
import os
import select
import subprocess
import sys
import time
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from sigma import cloud_research, cloud_workspaces, research_qa, research_sessions
from sigma.projects import ProjectError, initialize_project, inspect_project

REPOSITORY = Path(__file__).resolve().parents[1]
CREATOR = "b" * 32
OBSERVER = "a" * 32
ENVIRONMENT = {
    "SIGMA_CLOUD_AUTH_ENABLED": "true",
    "SIGMA_CLOUD_INFERENCE_PROVIDER": "api_key",
    "SIGMA_CLOUD_OPENAI_API_KEY": "not-a-real-key-provider-free-test",
    "SIGMA_CLOUD_GLOBAL_SPEND_CEILING_USD": "5.00",
    "SIGMA_CLOUD_USER_SPEND_CEILING_USD": "5.00",
    "SIGMA_CLOUD_USER_TOKEN_BUDGET": "100000",
    "SIGMA_CLOUD_GLOBAL_MAX_CONCURRENT": "1",
    "SIGMA_CLOUD_USER_MAX_CONCURRENT": "1",
    "SIGMA_CLOUD_GLOBAL_MAX_QUEUED": "8",
    "SIGMA_CLOUD_USER_MAX_QUEUED": "8",
}


def _project(root: Path, user: str, name: str):
    path = root / user / f"{name}.sigma"
    if path.exists():
        return inspect_project(str(path))
    return initialize_project(
        path,
        "Recovery acceptance",
        "Verify durable crash recovery",
        research_mode="mathematical",
    )


def _admit(root: Path, user: str, name: str, session_id: str) -> tuple[dict, str]:
    view = _project(root, user, name)
    job = {
        "id": session_id,
        "project_id": view.project.id,
        "project_path": view.path,
        "idempotency_key": session_id,
        "mode": "api_key",
        "maximum_estimated_cost_usd": 1.0,
        "call_limit": 6,
        "duration_limit_minutes": 15,
        "cost_status": "available",
    }
    cloud_research.prepare_job(job)
    return job, view.path


def _record(job: dict, *, status: str, attempt: str = "", creator: str = CREATOR) -> dict:
    stamp = datetime.now(UTC).isoformat()
    return {
        **job,
        "session_number": 1,
        "status": status,
        "created_by": creator,
        "created_at": stamp,
        "updated_at": stamp,
        "calls_used": 1 if attempt else 0,
        "estimated_cost_usd": 0.0,
        "estimated_cost_reserved_usd": 0.04 if attempt else 0.0,
        "events": [],
        "steps": (
            [
                {
                    "id": attempt,
                    "role": "investigator",
                    "status": "running",
                    "attempt_status": "sent",
                    "cost_reserve": 0.04,
                }
            ]
            if attempt
            else []
        ),
        "strategy_runs": [],
        "artifacts": [{"id": "saved-checkpoint", "claim": "Persisted before crash"}],
    }


def _worker_lock(path: str, session_id: str) -> int:
    fd = os.open(
        research_sessions._worker_lock_path(path, session_id),
        os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    return fd


def _execute(stage: str) -> None:
    root = Path(os.environ["SIGMA_RESTART_ROOT"])
    ids = json.loads(os.environ["SIGMA_RESTART_IDS"])
    identity = CREATOR if stage == "worker" else OBSERVER
    current = cloud_workspaces.Workspace(identity, identity, root / identity)
    token = cloud_workspaces._CURRENT.set(current)
    try:
        with (
            patch.object(cloud_workspaces, "storage_root", return_value=root),
            patch.object(
                cloud_research,
                "_effective_user_spend_ceiling_decimal",
                return_value=Decimal("5.00"),
            ),
        ):
            if stage == "worker":
                # Crash window: queued outer state + a dispatched, unsettled
                # provider step must NOT be interpreted as pre-dispatch work.
                ambiguous, ambiguous_path = _admit(root, CREATOR, "ambiguous", ids["ambiguous"])
                assert cloud_research.claim_job(ambiguous["id"])
                cloud_research.reserve_call(ambiguous["id"], ids["ambiguous_call"], 0.04, 40)
                saved = _record(ambiguous, status="running", attempt=ids["ambiguous_call"])
                research_sessions._save(ambiguous_path, saved)
                saved["status"] = "queued"
                research_sessions._save(ambiguous_path, saved)
                with cloud_research._transaction() as db:
                    db.execute(
                        "UPDATE jobs SET status='queued' WHERE session_id=?",
                        (ambiguous["id"],),
                    )
                fd_a = _worker_lock(ambiguous_path, ambiguous["id"])

                active, active_path = _admit(root, CREATOR, "active", ids["active"])
                assert cloud_research.claim_job(active["id"])
                cloud_research.reserve_call(active["id"], ids["active_call"], 0.04, 40)
                research_sessions._save(
                    active_path,
                    _record(active, status="running", attempt=ids["active_call"]),
                )
                fd_b = _worker_lock(active_path, active["id"])

                queued, queued_path = _admit(root, CREATOR, "queued", ids["queued"])
                research_sessions._save(queued_path, _record(queued, status="queued"))
                fd_c = _worker_lock(queued_path, queued["id"])

                qa_path = _project(root, CREATOR, "questions").path
                question_hash = hashlib.sha256(b"Persist this question").hexdigest()
                research_qa._save(
                    qa_path,
                    [],
                    [
                        {
                            "request_id": ids["qa"],
                            "question_sha256": question_hash,
                            "creator": CREATOR,
                            "started_at": datetime.now(UTC).isoformat(),
                            "model": "gpt-6-luna",
                            "thinking": "low",
                        }
                    ],
                )
                with research_qa._ask_worker(qa_path, ids["qa"]):
                    research_qa._publish_ask_activity(
                        qa_path,
                        ids["qa"],
                        creator=CREATOR,
                        model="gpt-6-luna",
                        thinking="low",
                    )
                    with (root / "provider-attempts").open("w") as stream:
                        stream.write("ambiguous\nactive\n")
                        stream.flush()
                        os.fsync(stream.fileno())
                    print("READY", flush=True)
                    assert all(fd >= 0 for fd in (fd_a, fd_b, fd_c))
                    while True:
                        time.sleep(0.2)

            cloud_research.reconcile_all_orphaned_jobs()
            with cloud_research._connect() as db:
                running = db.execute(
                    "SELECT status FROM jobs WHERE session_id=?",
                    (ids["active"],),
                ).fetchone()["status"]
                ambiguous_state = db.execute(
                    "SELECT status FROM jobs WHERE session_id=?",
                    (ids["ambiguous"],),
                ).fetchone()["status"]
                charge = db.execute(
                    "SELECT status,amount_usd,token_reservation FROM calls WHERE call_id=?",
                    (ids["active_call"],),
                ).fetchone()
            qa_path = str(root / CREATOR / "questions.sigma")
            queued_path = str(root / CREATOR / "queued.sigma")
            active_path = str(root / CREATOR / "active.sigma")
            # An observer has no access to a foreign private project.
            try:
                research_qa.list_pending_answers(qa_path)
            except ProjectError:
                pass
            else:
                raise AssertionError("foreign Q/A project was readable")

            creator_view = cloud_workspaces._CURRENT.set(
                cloud_workspaces.Workspace(CREATOR, CREATOR, root / CREATOR)
            )
            try:
                pending_activity = research_qa.list_pending_answers(qa_path)
                active_is_live = research_sessions.has_active_session(active_path)
                queued_is_live = research_sessions.has_active_session(queued_path)
                if stage == "observe":
                    # Even with a creator workspace binding, the observer's
                    # foreign process epoch must not reserve a paid attempt.
                    try:
                        cloud_research.reserve_call(ids["active"], str(uuid4()), 0.01, 10)
                    except cloud_research.CloudResearchUnavailable:
                        pass
                    else:
                        raise AssertionError("retired epoch admitted a provider call")
            finally:
                cloud_workspaces._CURRENT.reset(creator_view)

            if stage == "observe":
                assert running == "running", running
                assert ambiguous_state == "queued", ambiguous_state
                assert charge["status"] == "reserved"
                assert active_is_live
                assert queued_is_live
                assert [row["request_id"] for row in pending_activity] == [ids["qa"]]
                waiting, waiting_path = _admit(root, OBSERVER, "waiting", ids["waiting"])
                research_sessions._save(
                    waiting_path,
                    _record(waiting, status="queued", creator=OBSERVER),
                )
                assert not cloud_research.claim_job(waiting["id"])
                assert cloud_research.job_status(ids["active"]) is None

            elif stage == "recover":
                # The ledger records an interrupted owner, while the saved
                # Session itself is safely paused for explicit recovery.
                assert running == "interrupted", running
                # Cross-account maintenance is ledger-only: it retires the
                # uncertain slot without rewriting creator B's project file.
                assert ambiguous_state == "interrupted", ambiguous_state
                assert charge["status"] == "unknown", dict(charge)
                assert charge["amount_usd"] == 0.04
                assert charge["token_reservation"] == 40
                assert not active_is_live
                assert not queued_is_live
                assert pending_activity == [], pending_activity
                assert cloud_research.job_status(ids["active"]) is None
                assert cloud_research.claim_job(ids["waiting"])

                # Recover the creator's historical saved evidence using only
                # an internal fixture binding, not the observer's API rights.
                creator_token = cloud_workspaces._CURRENT.set(
                    cloud_workspaces.Workspace(CREATOR, CREATOR, root / CREATOR)
                )
                try:
                    active_raw = research_sessions._read(active_path, ids["active"])
                    assert active_raw["status"] == "running"
                    active_saved = research_sessions._recover(active_raw)
                    assert active_saved["status"] == "paused"
                    assert active_saved["created_by"] == CREATOR
                    assert active_saved["artifacts"][0]["id"] == "saved-checkpoint"
                    ambiguous_path = str(root / CREATOR / "ambiguous.sigma")
                    # Exercise the actual queued-worker restoration entrypoint.
                    # Its creator admission is supplied by this synthetic
                    # owner fixture rather than an HTTP auth middleware.
                    async def reconnect() -> None:
                        with (
                            patch(
                                "sigma.project_collaboration.require_execution_operator"
                            ),
                            patch.object(
                                research_sessions, "_worker", new_callable=AsyncMock
                            ) as scheduled,
                        ):
                            await research_sessions.ensure_queued_workers(ambiguous_path)
                            await asyncio.sleep(0)
                            assert scheduled.await_count == 0

                    asyncio.run(reconnect())
                    uncertain = research_sessions._read(ambiguous_path, ids["ambiguous"])
                    assert uncertain["status"] == "paused", uncertain
                    assert uncertain["steps"][0]["attempt_status"] == "unknown"
                    assert uncertain["steps"][0]["id"] == ids["ambiguous_call"]
                    queued_saved = research_sessions._read(queued_path, ids["queued"])
                    assert queued_saved["status"] == "queued"
                    assert queued_saved["id"] == ids["queued"]
                    assert queued_saved["created_by"] == CREATOR
                    with cloud_research._connect() as db:
                        unknown = db.execute(
                            "SELECT status,amount_usd,token_reservation FROM calls WHERE call_id=?",
                            (ids["ambiguous_call"],),
                        ).fetchone()
                        assert unknown["status"] == "unknown", dict(unknown)
                        assert unknown["amount_usd"] == 0.04
                        assert unknown["token_reservation"] == 40
                    _answers, pending = research_qa._load_archive(qa_path)
                    assert [item["request_id"] for item in pending] == [ids["qa"]]
                    try:
                        research_qa._check_pending_request(
                            pending,
                            ids["qa"],
                            hashlib.sha256(b"Persist this question").hexdigest(),
                            creator=CREATOR,
                        )
                    except ProjectError as exc:
                        assert "provider" in str(exc)
                    else:
                        raise AssertionError("uncertain Q/A attempt became replayable")
                finally:
                    cloud_workspaces._CURRENT.reset(creator_token)

                try:
                    cloud_research.reserve_call(ids["active"], ids["active_call"], 0.01, 10)
                except cloud_research.CloudResearchUnavailable:
                    pass
                else:
                    raise AssertionError("observer reserved another creator's provider call")
            else:
                raise AssertionError("unknown fixture stage")

            assert (root / "provider-attempts").read_text().splitlines() == [
                "ambiguous",
                "active",
            ]
            print(
                json.dumps({"stage": stage, "active": running, "attempts": 2}),
                flush=True,
            )
    finally:
        cloud_workspaces._CURRENT.reset(token)


def test_real_process_recovery() -> None:
    """SIGKILL a live owner, then verify durable recovery in another process."""
    with TemporaryDirectory(prefix="sigma-process-restart-", dir=REPOSITORY.parent) as temporary:
        root = Path(temporary)
        for identity in (CREATOR, OBSERVER):
            (root / identity).mkdir(mode=0o700)
        ids = {
            "active": str(uuid4()),
            "active_call": str(uuid4()),
            "queued": str(uuid4()),
            "ambiguous": str(uuid4()),
            "ambiguous_call": str(uuid4()),
            "waiting": str(uuid4()),
            "qa": uuid4().hex,
        }
        environment = {
            **os.environ,
            **ENVIRONMENT,
            "SIGMA_RESTART_ROOT": str(root),
            "SIGMA_RESTART_IDS": json.dumps(ids),
            "PYTHONPATH": str(REPOSITORY / "src") + os.pathsep + os.environ.get("PYTHONPATH", ""),
        }
        worker = subprocess.Popen(
            [sys.executable, str(Path(__file__)), "worker"],
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            assert worker.stdout is not None
            readable, _, _ = select.select([worker.stdout], [], [], 8)
            if not readable:
                raise AssertionError("worker did not persist its checkpoint in eight seconds")
            line = worker.stdout.readline().strip()
            if line != "READY":
                raise AssertionError(f"worker failed before checkpoint: {line!r}")
            for stage in ("observe", "recover"):
                if stage == "recover":
                    worker.kill()
                    worker.wait(timeout=3)
                    assert worker.returncode != 0
                result = subprocess.run(
                    [sys.executable, str(Path(__file__)), stage],
                    env=environment,
                    capture_output=True,
                    text=True,
                    timeout=10,
                    check=False,
                )
                assert result.returncode == 0, f"{stage}: {result.stdout}\n{result.stderr}"
                report = json.loads(result.stdout.strip().splitlines()[-1])
                assert report["attempts"] == 2
                assert report["active"] == ("running" if stage == "observe" else "interrupted")
        finally:
            if worker.poll() is None:
                worker.kill()
            worker.communicate(timeout=3)


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in {
        "worker",
        "observe",
        "recover",
    }:
        raise SystemExit("call test_real_process_recovery instead")
    _execute(sys.argv[1])
