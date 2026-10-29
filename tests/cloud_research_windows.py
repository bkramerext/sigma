"""Adversarial rollover and concurrent-reservation tests for global spend policy."""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from uuid import uuid4


def _insert_job(db, *, session_id: str, workspace_id: str, now: str) -> None:
    db.execute(
        "INSERT INTO jobs(session_id,workspace_id,project_id,idempotency_key,status,created_at,updated_at) "
        "VALUES(?,?,?,?,'running',?,?)",
        (session_id, workspace_id, str(uuid4()), str(uuid4()), now, now),
    )


def _insert_call(
    db, *, session_id: str, workspace_id: str, amount: float, status: str, created_at: str
) -> None:
    db.execute(
        "INSERT INTO calls(call_id,session_id,workspace_id,amount_usd,status,token_reservation,input_tokens,output_tokens,created_at,updated_at) "
        "VALUES(?,?,?,?,?,0,NULL,NULL,?,?)",
        (str(uuid4()), session_id, workspace_id, amount, status, created_at, created_at),
    )


def main() -> None:
    from sigma import cloud_auth, cloud_research, cloud_workspaces

    with TemporaryDirectory(prefix="sigma-spend-window-") as temporary:
        root = Path(temporary)
        workspace_root = root / "workspaces"
        workspace_root.mkdir(mode=0o700)
        db_path = root / "research.sqlite3"
        environment = {
            "SIGMA_CLOUD_AUTH_ENABLED": "false",
            "SIGMA_CLOUD_WORKSPACES_ROOT": str(workspace_root),
            "SIGMA_CLOUD_GLOBAL_SPEND_CEILING_USD": "0.10",
            "SIGMA_CLOUD_USER_SPEND_CEILING_USD": "1.00",
            "SIGMA_CLOUD_USER_TOKEN_BUDGET": "1000000",
            "SIGMA_CLOUD_GLOBAL_SPEND_WINDOW": "calendar_month",
        }
        with (
            patch.dict(os.environ, environment, clear=False),
            patch.object(cloud_research, "_database", return_value=db_path),
            patch.object(
                cloud_research,
                "_effective_user_spend_ceiling_decimal",
                return_value=Decimal("1.00"),
            ),
            patch.object(cloud_research, "_admin_has_unlimited_spend", return_value=False),
        ):
            now = datetime.now(UTC)
            month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            old = (month_start - timedelta(microseconds=1)).isoformat()
            current = now.isoformat()
            principal_a = cloud_auth.Principal("window-a", "a@example.test", "member")
            principal_b = cloud_auth.Principal("window-b", "b@example.test", "member")
            workspace_a = cloud_workspaces.workspace_for_subject(principal_a.subject)
            workspace_b = cloud_workspaces.workspace_for_subject(principal_b.subject)

            db = cloud_research._connect()
            old_settled_job, old_reserved_job, old_unknown_job, current_job = (
                str(uuid4()) for _ in range(4)
            )
            for session, workspace in (
                (old_settled_job, workspace_a),
                (old_reserved_job, workspace_a),
                (old_unknown_job, workspace_a),
                (current_job, workspace_a),
            ):
                _insert_job(
                    db,
                    session_id=session,
                    workspace_id=workspace.workspace_id,
                    now=current,
                )
            _insert_call(
                db,
                session_id=old_settled_job,
                workspace_id=workspace_a.workspace_id,
                amount=0.08,
                status="usage_estimated",
                created_at=old,
            )
            _insert_call(
                db,
                session_id=old_reserved_job,
                workspace_id=workspace_a.workspace_id,
                amount=0.01,
                status="reserved",
                created_at=old,
            )
            _insert_call(
                db,
                session_id=old_unknown_job,
                workspace_id=workspace_a.workspace_id,
                amount=0.01,
                status="unknown",
                created_at=old,
            )
            db.close()

            # Calendar-month policy drops only old settled usage. An unresolved
            # reservation and an unknown provider outcome remain obligations.
            with cloud_research._connect() as db:
                assert cloud_research._global_call_amount_units(db) == 20_000_000
            token = cloud_workspaces.bind(principal_a)
            try:
                cloud_research.reserve_call(current_job, str(uuid4()), 0.06, 100)
                second_job = str(uuid4())
                with cloud_research._connect() as db:
                    _insert_job(
                        db,
                        session_id=second_job,
                        workspace_id=workspace_a.workspace_id,
                        now=current,
                    )
                try:
                    cloud_research.reserve_call(second_job, str(uuid4()), 0.03, 100)
                except cloud_research.CloudResearchUnavailable as exc:
                    assert "global inference-spend ceiling" in str(exc)
                else:
                    raise AssertionError("Old unresolved obligations did not hold global capacity")
            finally:
                cloud_workspaces.reset(token)

            # Cumulative policy retains settled history too; it never silently
            # renews based on month rollover.
            with (
                patch.dict(os.environ, {"SIGMA_CLOUD_GLOBAL_SPEND_WINDOW": "cumulative"}),
                cloud_research._connect() as db,
            ):
                assert cloud_research._global_call_amount_units(db) == 160_000_000

            # Cross-workspace concurrent reservations serialize at BEGIN
            # IMMEDIATE: a $0.10 ceiling admits only one $0.06 reservation.
            concurrent_db = root / "concurrent.sqlite3"
            with patch.object(cloud_research, "_database", return_value=concurrent_db):
                db = cloud_research._connect()
                session_a, session_b = str(uuid4()), str(uuid4())
                _insert_job(
                    db,
                    session_id=session_a,
                    workspace_id=workspace_a.workspace_id,
                    now=current,
                )
                _insert_job(
                    db,
                    session_id=session_b,
                    workspace_id=workspace_b.workspace_id,
                    now=current,
                )
                db.close()

                def reserve(principal, session_id):
                    workspace_token = cloud_workspaces.bind(principal)
                    try:
                        cloud_research.reserve_call(session_id, str(uuid4()), 0.06, 100)
                        return "reserved"
                    except cloud_research.CloudResearchUnavailable:
                        return "blocked"
                    finally:
                        cloud_workspaces.reset(workspace_token)

                with ThreadPoolExecutor(max_workers=2) as pool:
                    results = list(
                        pool.map(
                            lambda pair: reserve(*pair),
                            ((principal_a, session_a), (principal_b, session_b)),
                        )
                    )
                assert sorted(results) == ["blocked", "reserved"], results
                with cloud_research._connect() as db:
                    assert db.execute("SELECT COUNT(*) FROM calls").fetchone()[0] == 1
                    assert cloud_research._global_call_amount_units(db) == 60_000_000

    print(
        "PASS calendar-month rollover excludes old settled usage only by policy, preserves reserved/unknown obligations, and serializes global concurrent reservations"
    )


if __name__ == "__main__":
    main()
