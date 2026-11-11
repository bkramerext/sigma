"""Adversarial owner/ledger recovery probes, with no paid inference."""

from __future__ import annotations

import fcntl
import json
import os
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from uuid import uuid4

from sigma import cloud_research, cloud_workspaces, research_sessions
from sigma.projects import initialize_project

ROOT = Path(__file__).resolve().parents[1]
ALICE = "a" * 32
BOB = "b" * 32


def _workspace(root: Path, user: str) -> cloud_workspaces.Workspace:
    path = root / user
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    return cloud_workspaces.Workspace(user, user, path)


def _job(session_id: str, project_id: str, project_path: str) -> dict:
    return {
        "id": session_id,
        "project_id": project_id,
        "project_path": project_path,
        "idempotency_key": session_id,
        "mode": "api_key",
        "maximum_estimated_cost_usd": 1.0,
        "call_limit": 6,
        "duration_limit_minutes": 15,
        "cost_status": "available",
    }


def _settings() -> dict[str, str]:
    return {
        "SIGMA_CLOUD_AUTH_ENABLED": "true",
        "SIGMA_CLOUD_INFERENCE_PROVIDER": "api_key",
        "SIGMA_CLOUD_OPENAI_API_KEY": "not-real-provider-free-recovery-test",
        "SIGMA_CLOUD_GLOBAL_SPEND_CEILING_USD": "5.00",
        "SIGMA_CLOUD_USER_SPEND_CEILING_USD": "5.00",
        "SIGMA_CLOUD_USER_TOKEN_BUDGET": "100000",
        "SIGMA_CLOUD_GLOBAL_MAX_CONCURRENT": "1",
        "SIGMA_CLOUD_USER_MAX_CONCURRENT": "1",
        "SIGMA_CLOUD_GLOBAL_MAX_QUEUED": "8",
        "SIGMA_CLOUD_USER_MAX_QUEUED": "8",
    }


def test_foreign_collaborator_crash() -> None:
    """Observer can free a dead creator's slot but cannot rewrite their work."""
    with TemporaryDirectory(prefix="sigma-foreign-recovery-", dir=ROOT.parent) as temp:
        root = Path(temp)
        alice = _workspace(root, ALICE)
        bob = _workspace(root, BOB)
        with (
            patch.dict(os.environ, _settings(), clear=False),
            patch.object(cloud_workspaces, "storage_root", return_value=root),
            patch.object(
                cloud_research,
                "_effective_user_spend_ceiling_decimal",
                return_value=Decimal("5.00"),
            ),
        ):
            owner_token = cloud_workspaces._CURRENT.set(alice)
            try:
                project = initialize_project(
                    alice.path / "shared.sigma",
                    "Shared recovery",
                    "Verify crash fencing for foreign creator",
                    research_mode="mathematical",
                )
            finally:
                cloud_workspaces._CURRENT.reset(owner_token)

            session_id = str(uuid4())
            attempt_id = str(uuid4())
            creator_token = cloud_workspaces._CURRENT.set(bob)
            try:
                with patch(
                    "sigma.project_collaboration.authorized_shared_path",
                    return_value=True,
                ):
                    record = _job(session_id, project.project.id, project.path)
                    cloud_research.prepare_job(record)
                    assert cloud_research.claim_job(session_id)
                    cloud_research.reserve_call(session_id, attempt_id, 0.04, 40)
                with cloud_research._connect() as db:
                    assert (
                        db.execute(
                            "SELECT project_relpath FROM jobs WHERE session_id=?",
                            (session_id,),
                        ).fetchone()["project_relpath"]
                        == f"@shared/{ALICE}/shared.sigma"
                    )
            finally:
                cloud_workspaces._CURRENT.reset(creator_token)

            session_dir = Path(project.path) / "research-sessions"
            session_dir.mkdir(mode=0o700, exist_ok=True)
            saved = {
                **record,
                "session_number": 3,
                "created_by": BOB,
                "created_at": "2026-11-11T00:00:00+00:00",
                "updated_at": "2026-11-11T00:00:00+00:00",
                "status": "running",
                "steps": [
                    {
                        "id": attempt_id,
                        "role": "investigator",
                        "status": "running",
                        "attempt_status": "reserved",
                        "cost_reserve": 0.04,
                    }
                ],
                "strategy_runs": [],
                "events": [],
                "artifacts": [{"id": "checkpoint-untouched"}],
            }
            session_file = session_dir / f"{session_id}.json"
            original = json.dumps(saved) + "\n"
            session_file.write_text(original, encoding="utf-8")
            lock = session_dir / f"{session_id}.worker.lock"
            fd = os.open(lock, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            observer_token = cloud_workspaces._CURRENT.set(alice)
            try:
                with patch.object(cloud_research, "_PROCESS_EPOCH", uuid4().hex):
                    # Account A's maintenance pass cannot steal B's live lock.
                    cloud_research.reconcile_all_orphaned_jobs()
                    with cloud_research._connect() as db:
                        assert (
                            db.execute(
                                "SELECT status FROM jobs WHERE session_id=?",
                                (session_id,),
                            ).fetchone()["status"]
                            == "running"
                        )
                    assert (
                        research_sessions._recover(
                            research_sessions._read(project.path, session_id)
                        )["status"]
                        == "running"
                    )

                    fcntl.flock(fd, fcntl.LOCK_UN)
                    os.close(fd)
                    fd = -1

                    # Same observer, new process epoch: no impersonation, but
                    # dead worker and unknown billing obligations are fenced.
                    cloud_research.reconcile_all_orphaned_jobs()
                    with cloud_research._connect() as db:
                        state = db.execute(
                            "SELECT status,workspace_id FROM jobs WHERE session_id=?",
                            (session_id,),
                        ).fetchone()
                        charge = db.execute(
                            "SELECT status,amount_usd,token_reservation FROM calls WHERE call_id=?",
                            (attempt_id,),
                        ).fetchone()
                        assert (state["status"], state["workspace_id"]) == (
                            "interrupted",
                            BOB,
                        )
                        assert (charge["status"], charge["amount_usd"]) == (
                            "unknown",
                            0.04,
                        )
                        assert charge["token_reservation"] == 40

                    # Viewing collaborator sees truthful interrupted state,
                    # but the creator's immutable saved record is untouched.
                    preview = research_sessions._recover(
                        research_sessions._read(project.path, session_id)
                    )
                    assert preview["status"] == "paused"
                    assert preview["id"] == session_id
                    assert preview["created_by"] == BOB
                    assert session_file.read_text(encoding="utf-8") == original
                    assert cloud_research.job_status(session_id) is None
            finally:
                if fd >= 0:
                    fcntl.flock(fd, fcntl.LOCK_UN)
                    os.close(fd)
                cloud_workspaces._CURRENT.reset(observer_token)


def test_queued_call_fence() -> None:
    """No direct claim is permitted with an unresolved dispatch reservation."""
    with TemporaryDirectory(prefix="sigma-queue-fence-", dir=ROOT.parent) as temp:
        root = Path(temp)
        creator = _workspace(root, BOB)
        with (
            patch.dict(os.environ, _settings(), clear=False),
            patch.object(cloud_workspaces, "storage_root", return_value=root),
            patch.object(
                cloud_research,
                "_effective_user_spend_ceiling_decimal",
                return_value=Decimal("5.00"),
            ),
        ):
            token = cloud_workspaces._CURRENT.set(creator)
            try:
                view = initialize_project(
                    creator.path / "queued.sigma",
                    "Queued uncertainty",
                    "Verify no replay after crash",
                    research_mode="mathematical",
                )
                session_id = str(uuid4())
                attempt_id = str(uuid4())
                cloud_research.prepare_job(_job(session_id, view.project.id, view.path))
                assert cloud_research.claim_job(session_id)
                cloud_research.reserve_call(session_id, attempt_id, 0.04, 40)
                with cloud_research._transaction() as db:
                    db.execute(
                        "UPDATE jobs SET status='queued' WHERE session_id=?",
                        (session_id,),
                    )
                try:
                    cloud_research.claim_job(session_id)
                except cloud_research.CloudResearchUnavailable as exc:
                    assert "unsettled" in str(exc)
                else:
                    raise AssertionError("unsettled queued call was claimed")
                # No published session exists; stale queue ownership must be
                # released while the uncertain attempt remains a full hold.
                with patch.object(cloud_research, "_PROCESS_EPOCH", uuid4().hex):
                    cloud_research.reconcile_orphaned_jobs()
                assert cloud_research.job_status(session_id) == "interrupted"
                with cloud_research._connect() as db:
                    call = db.execute(
                        "SELECT status,amount_usd,token_reservation FROM calls WHERE call_id=?",
                        (attempt_id,),
                    ).fetchone()
                    assert (call["status"], call["amount_usd"]) == (
                        "unknown",
                        0.04,
                    )
                    assert call["token_reservation"] == 40
            finally:
                cloud_workspaces._CURRENT.reset(token)


def main() -> None:
    test_foreign_collaborator_crash()
    test_queued_call_fence()
    print("PASS adversarial shared-creator recovery, queued dispatch fencing, retained liability")


if __name__ == "__main__":
    main()
