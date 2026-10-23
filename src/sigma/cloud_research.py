"""Durable cloud research admission and inference-spend ledger.

Research state and evidence remain in the existing project session records. This
small service-owned ledger adds cross-project, cross-process admission and
write-ahead cost reservations without creating a second research engine.
"""

from __future__ import annotations

import os
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sigma import cloud_workspaces


class CloudResearchUnavailable(RuntimeError):
    """Cloud execution cannot be safely bounded or accounted for."""


def _workspace_id() -> str:
    workspace = cloud_workspaces.current()
    if workspace is None:
        raise CloudResearchUnavailable("Authenticated research workspace is unavailable.")
    return workspace.workspace_id


def _positive_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    if value is None:
        return default
    try:
        parsed = int(value)
    except ValueError as exc:
        raise CloudResearchUnavailable("Cloud research limits are invalid.") from exc
    if parsed < 1 or parsed > 1_000_000_000:
        raise CloudResearchUnavailable("Cloud research limits are invalid.")
    return parsed


def _spend_ceiling() -> float:
    value = os.environ.get("SIGMA_CLOUD_GLOBAL_SPEND_CEILING_USD", "").strip()
    try:
        ceiling = float(value)
    except ValueError as exc:
        raise CloudResearchUnavailable(
            "Cloud research is disabled until a global inference-spend ceiling is configured."
        ) from exc
    if not 0 < ceiling <= 1_000_000:
        raise CloudResearchUnavailable(
            "Cloud research is disabled until a valid global inference-spend ceiling is configured."
        )
    return ceiling


def _database() -> Path:
    try:
        root = cloud_workspaces.storage_root()
        path = root / "cloud-research.sqlite3"
        if path.is_symlink():
            raise CloudResearchUnavailable("Cloud research ledger is unavailable.")
        return path
    except CloudResearchUnavailable:
        raise
    except Exception as exc:
        raise CloudResearchUnavailable("Cloud research ledger is unavailable.") from exc


class _Connection(sqlite3.Connection):
    def __exit__(self, exc_type, exc_value, traceback):
        try:
            return super().__exit__(exc_type, exc_value, traceback)
        finally:
            self.close()


def _connect() -> sqlite3.Connection:
    try:
        path = _database()
        db = sqlite3.connect(path, timeout=30, isolation_level=None, factory=_Connection)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=30000")
        db.execute("PRAGMA journal_mode=DELETE")
        db.executescript("""
            CREATE TABLE IF NOT EXISTS jobs (
                session_id TEXT PRIMARY KEY,
                workspace_id TEXT NOT NULL,
                project_id TEXT NOT NULL,
                idempotency_key TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('queued','running','stopping','paused','interrupted','terminal')),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(workspace_id, idempotency_key)
            );
            CREATE INDEX IF NOT EXISTS jobs_workspace_status ON jobs(workspace_id, status);
            CREATE TABLE IF NOT EXISTS calls (
                call_id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL REFERENCES jobs(session_id),
                workspace_id TEXT NOT NULL,
                amount_usd REAL NOT NULL CHECK(amount_usd >= 0),
                status TEXT NOT NULL CHECK(status IN ('reserved','usage_estimated','unknown','not_dispatched')),
                token_reservation INTEGER NOT NULL CHECK(token_reservation >= 0),
                input_tokens INTEGER,
                output_tokens INTEGER,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
        """)
        os.chmod(path, 0o600)
        return db
    except (OSError, sqlite3.Error) as exc:
        raise CloudResearchUnavailable("Cloud research ledger is unavailable.") from exc


def _now() -> str:
    return datetime.now(UTC).isoformat()


@contextmanager
def _transaction() -> Iterator[sqlite3.Connection]:
    db = _connect()
    try:
        db.execute("BEGIN IMMEDIATE")
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def prepare_job(record: dict[str, Any]) -> None:
    """Atomically reserve a bounded queue slot for a persisted session ID."""
    owner = _workspace_id()
    if record.get("mode") != "api_key":
        raise CloudResearchUnavailable(
            "Cloud research requires an explicitly configured server API credential; plan credentials are not shared across identities."
        )
    if record.get("maximum_estimated_cost_usd") is None or record.get("cost_status") != "available":
        raise CloudResearchUnavailable(
            "Cloud research requires a per-session cost limit and a model with a reviewed price."
        )
    _positive_int("SIGMA_CLOUD_USER_MAX_CONCURRENT", 1)
    _positive_int("SIGMA_CLOUD_GLOBAL_MAX_CONCURRENT", 4)
    per_user_queue = _positive_int("SIGMA_CLOUD_USER_MAX_QUEUED", 2)
    global_queue = _positive_int("SIGMA_CLOUD_GLOBAL_MAX_QUEUED", 16)
    _spend_ceiling()
    now = _now()
    try:
        with _transaction() as db:
            existing = db.execute(
                "SELECT * FROM jobs WHERE session_id=? OR (workspace_id=? AND idempotency_key=?)",
                (record["id"], owner, record["idempotency_key"]),
            ).fetchone()
            if existing:
                if (
                    existing["session_id"] != record["id"]
                    or existing["workspace_id"] != owner
                    or existing["project_id"] != record["project_id"]
                ):
                    raise CloudResearchUnavailable(
                        "Research request identity conflicts with a saved job."
                    )
                if existing["status"] in {"paused", "interrupted", "terminal"}:
                    per_user = db.execute(
                        "SELECT COUNT(*) FROM jobs WHERE workspace_id=? AND status='queued'",
                        (owner,),
                    ).fetchone()[0]
                    total = db.execute(
                        "SELECT COUNT(*) FROM jobs WHERE status='queued'"
                    ).fetchone()[0]
                    if per_user >= per_user_queue or total >= global_queue:
                        raise CloudResearchUnavailable(
                            "Research queue is full; retry when capacity is available."
                        )
                    db.execute(
                        "UPDATE jobs SET status='queued',updated_at=? WHERE session_id=?",
                        (now, record["id"]),
                    )
                return
            user_queued = db.execute(
                "SELECT COUNT(*) FROM jobs WHERE workspace_id=? AND status='queued'", (owner,)
            ).fetchone()[0]
            total_queued = db.execute("SELECT COUNT(*) FROM jobs WHERE status='queued'").fetchone()[
                0
            ]
            if user_queued >= per_user_queue or total_queued >= global_queue:
                raise CloudResearchUnavailable(
                    "Research queue is full; retry when capacity is available."
                )
            # Jobs are initially queued. Claiming uses an atomic running-slot test.
            db.execute(
                "INSERT INTO jobs VALUES(?,?,?,?,?,?,?)",
                (
                    record["id"],
                    owner,
                    record["project_id"],
                    record["idempotency_key"],
                    "queued",
                    now,
                    now,
                ),
            )
    except sqlite3.Error as exc:
        raise CloudResearchUnavailable("Cloud research ledger is unavailable.") from exc


def claim_job(session_id: str) -> bool:
    """Acquire a per-user and global worker slot for one queued session."""
    owner = _workspace_id()
    user_limit = _positive_int("SIGMA_CLOUD_USER_MAX_CONCURRENT", 1)
    global_limit = _positive_int("SIGMA_CLOUD_GLOBAL_MAX_CONCURRENT", 4)
    try:
        with _transaction() as db:
            job = db.execute("SELECT * FROM jobs WHERE session_id=?", (session_id,)).fetchone()
            if not job or job["workspace_id"] != owner:
                raise CloudResearchUnavailable("Research job is unavailable.")
            if job["status"] == "running":
                return True
            if job["status"] != "queued":
                return False
            user_running = db.execute(
                "SELECT COUNT(*) FROM jobs WHERE workspace_id=? AND status IN ('running','stopping')",
                (owner,),
            ).fetchone()[0]
            global_running = db.execute(
                "SELECT COUNT(*) FROM jobs WHERE status IN ('running','stopping')"
            ).fetchone()[0]
            if user_running >= user_limit or global_running >= global_limit:
                return False
            db.execute(
                "UPDATE jobs SET status='running',updated_at=? WHERE session_id=?",
                (_now(), session_id),
            )
            return True
    except sqlite3.Error as exc:
        raise CloudResearchUnavailable("Cloud research ledger is unavailable.") from exc


def sync_job(record: dict[str, Any]) -> None:
    """Persist lifecycle transitions as an owner-checked ledger projection."""
    owner = _workspace_id()
    now = _now()
    state = record.get("status")
    try:
        with _transaction() as db:
            row = db.execute("SELECT * FROM jobs WHERE session_id=?", (record["id"],)).fetchone()
            if not row:
                state = record.get("status")
                ledger_state = (
                    "terminal"
                    if state in {"ended", "completed", "failed"}
                    else "paused"
                    if state in {"paused", "stopped"}
                    else "queued"
                )
                db.execute(
                    "INSERT INTO jobs VALUES(?,?,?,?,?,?,?)",
                    (
                        record["id"],
                        owner,
                        record["project_id"],
                        record.get("idempotency_key", record["id"]),
                        ledger_state,
                        record.get("created_at", now),
                        now,
                    ),
                )
                return
            if row["workspace_id"] != owner or row["project_id"] != record["project_id"]:
                raise CloudResearchUnavailable("Research job is unavailable.")
            if state in {"ended", "completed", "failed"}:
                ledger_state = "terminal"
            elif state in {"paused", "stopped"}:
                ledger_state = "stopping" if row["status"] == "running" else "paused"
            elif state == "queued" and row["status"] in {"paused", "interrupted"}:
                ledger_state = "queued"
            else:
                ledger_state = row["status"]
            db.execute(
                "UPDATE jobs SET status=?,updated_at=? WHERE session_id=?",
                (ledger_state, now, record["id"]),
            )
    except sqlite3.Error as exc:
        raise CloudResearchUnavailable("Cloud research ledger is unavailable.") from exc


def release_job(session_id: str, *, paused: bool = False) -> None:
    """Release a worker slot after its task has actually left provider I/O."""
    owner = _workspace_id()
    try:
        with _transaction() as db:
            row = db.execute(
                "SELECT workspace_id,status FROM jobs WHERE session_id=?", (session_id,)
            ).fetchone()
            if not row or row["workspace_id"] != owner:
                return
            if row["status"] in {"terminal", "paused"}:
                return
            next_state = "paused" if paused else row["status"]
            db.execute(
                "UPDATE jobs SET status=?,updated_at=? WHERE session_id=?",
                (next_state, _now(), session_id),
            )
    except sqlite3.Error as exc:
        raise CloudResearchUnavailable("Cloud research ledger is unavailable.") from exc


def recover_job(session_id: str) -> None:
    """Release a process-dead worker slot only after its project lock is free."""
    owner = _workspace_id()
    try:
        with _transaction() as db:
            row = db.execute(
                "SELECT workspace_id FROM jobs WHERE session_id=?", (session_id,)
            ).fetchone()
            if row and row["workspace_id"] == owner:
                db.execute(
                    "UPDATE jobs SET status='interrupted',updated_at=? WHERE session_id=? AND status IN ('running','stopping')",
                    (_now(), session_id),
                )
                db.execute(
                    "UPDATE calls SET status='unknown',updated_at=? WHERE session_id=? AND status='reserved'",
                    (_now(), session_id),
                )
    except sqlite3.Error as exc:
        raise CloudResearchUnavailable("Cloud research ledger is unavailable.") from exc


def reserve_call(session_id: str, call_id: str, amount_usd: float, token_reservation: int) -> None:
    """Write a conservative cost reservation before making provider I/O."""
    owner = _workspace_id()
    ceiling = _spend_ceiling()
    token_budget = _positive_int("SIGMA_CLOUD_USER_TOKEN_BUDGET", 2_000_000)
    if not 0 < amount_usd <= ceiling:
        raise CloudResearchUnavailable(
            "The next provider call cannot be reserved within the global spend ceiling."
        )
    if type(token_reservation) is not int or token_reservation <= 0:
        raise CloudResearchUnavailable("Cloud provider token reservation is invalid.")
    if token_reservation > token_budget:
        raise CloudResearchUnavailable("The next provider call exceeds the per-user token budget.")
    try:
        with _transaction() as db:
            job = db.execute(
                "SELECT workspace_id,status FROM jobs WHERE session_id=?", (session_id,)
            ).fetchone()
            if not job or job["workspace_id"] != owner or job["status"] != "running":
                raise CloudResearchUnavailable(
                    "Research worker has no active execution reservation."
                )
            existing = db.execute(
                "SELECT session_id FROM calls WHERE call_id=?", (call_id,)
            ).fetchone()
            if existing:
                if existing["session_id"] != session_id:
                    raise CloudResearchUnavailable(
                        "Provider attempt identity conflicts with saved evidence."
                    )
                raise CloudResearchUnavailable(
                    "This provider attempt was already reserved and cannot be replayed."
                )
            used = db.execute("SELECT COALESCE(SUM(amount_usd),0) FROM calls").fetchone()[0]
            if used + amount_usd > ceiling:
                raise CloudResearchUnavailable(
                    "The configured global inference-spend ceiling has been reached."
                )
            user_tokens = db.execute(
                "SELECT COALESCE(SUM(token_reservation),0) FROM calls WHERE workspace_id=?",
                (owner,),
            ).fetchone()[0]
            if user_tokens + token_reservation > token_budget:
                raise CloudResearchUnavailable(
                    "The per-user research token budget has been reached."
                )
            now = _now()
            db.execute(
                "INSERT INTO calls VALUES(?,?,?,?,?,?,?,?,?,?)",
                (
                    call_id,
                    session_id,
                    owner,
                    amount_usd,
                    "reserved",
                    token_reservation,
                    None,
                    None,
                    now,
                    now,
                ),
            )
    except sqlite3.Error as exc:
        raise CloudResearchUnavailable("Cloud research ledger is unavailable.") from exc


def settle_call(
    session_id: str,
    call_id: str,
    *,
    input_tokens: int | None,
    output_tokens: int | None,
    estimated_cost_usd: float | None,
) -> None:
    """Reconcile known usage; otherwise retain the full reservation as unknown."""
    owner = _workspace_id()
    status = "usage_estimated" if estimated_cost_usd is not None else "unknown"
    try:
        with _transaction() as db:
            row = db.execute("SELECT * FROM calls WHERE call_id=?", (call_id,)).fetchone()
            if not row or row["session_id"] != session_id or row["workspace_id"] != owner:
                raise CloudResearchUnavailable("Provider attempt is unavailable.")
            db.execute(
                "UPDATE calls SET amount_usd=?,status=?,token_reservation=?,input_tokens=?,output_tokens=?,updated_at=? WHERE call_id=?",
                (
                    estimated_cost_usd if estimated_cost_usd is not None else row["amount_usd"],
                    status,
                    (input_tokens + output_tokens)
                    if input_tokens is not None and output_tokens is not None
                    else row["token_reservation"],
                    input_tokens,
                    output_tokens,
                    _now(),
                    call_id,
                ),
            )
    except sqlite3.Error as exc:
        raise CloudResearchUnavailable("Cloud research ledger is unavailable.") from exc


def mark_call_unknown(session_id: str, call_id: str) -> None:
    owner = _workspace_id()
    try:
        with _transaction() as db:
            row = db.execute("SELECT * FROM calls WHERE call_id=?", (call_id,)).fetchone()
            if row and row["session_id"] == session_id and row["workspace_id"] == owner:
                db.execute(
                    "UPDATE calls SET status='unknown',updated_at=? WHERE call_id=?",
                    (_now(), call_id),
                )
    except sqlite3.Error as exc:
        raise CloudResearchUnavailable("Cloud research ledger is unavailable.") from exc


def mark_call_not_dispatched(session_id: str, call_id: str) -> None:
    """Release a write-ahead reservation when the provider request never started."""
    owner = _workspace_id()
    try:
        with _transaction() as db:
            row = db.execute("SELECT * FROM calls WHERE call_id=?", (call_id,)).fetchone()
            if (
                row
                and row["session_id"] == session_id
                and row["workspace_id"] == owner
                and row["status"] == "reserved"
            ):
                db.execute(
                    "UPDATE calls SET amount_usd=0,token_reservation=0,status='not_dispatched',updated_at=? WHERE call_id=?",
                    (_now(), call_id),
                )
    except sqlite3.Error as exc:
        raise CloudResearchUnavailable("Cloud research ledger is unavailable.") from exc


def snapshot() -> dict[str, Any]:
    """Return only the current principal's job and usage summary."""
    owner = _workspace_id()
    try:
        with _connect() as db:
            own = db.execute(
                "SELECT status,COUNT(*) AS count FROM jobs WHERE workspace_id=? GROUP BY status",
                (owner,),
            ).fetchall()
            used = db.execute(
                "SELECT COALESCE(SUM(amount_usd),0) FROM calls WHERE workspace_id=?", (owner,)
            ).fetchone()[0]
            unknown = db.execute(
                "SELECT COUNT(*) FROM calls WHERE workspace_id=? AND status='unknown'", (owner,)
            ).fetchone()[0]
            tokens = db.execute(
                "SELECT COALESCE(SUM(token_reservation),0) FROM calls WHERE workspace_id=?",
                (owner,),
            ).fetchone()[0]
            return {
                "jobs": {row["status"]: row["count"] for row in own},
                "user_reserved_and_estimated_usd": round(float(used), 9),
                "user_reserved_or_observed_tokens": int(tokens),
                "unknown_provider_attempts": unknown,
            }
    except sqlite3.Error as exc:
        raise CloudResearchUnavailable("Cloud research ledger is unavailable.") from exc
