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
from uuid import UUID, uuid4

from sigma import cloud_workspaces
from sigma.projects import ProjectError, inspect_project

_PROCESS_EPOCH = uuid4().hex


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
                project_relpath TEXT NOT NULL DEFAULT '',
                process_epoch TEXT NOT NULL DEFAULT '',
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
        columns = {row["name"] for row in db.execute("PRAGMA table_info(jobs)")}
        if "project_relpath" not in columns:
            db.execute("ALTER TABLE jobs ADD COLUMN project_relpath TEXT NOT NULL DEFAULT ''")
        if "process_epoch" not in columns:
            db.execute("ALTER TABLE jobs ADD COLUMN process_epoch TEXT NOT NULL DEFAULT ''")
        os.chmod(path, 0o600)
        return db
    except (OSError, sqlite3.Error) as exc:
        raise CloudResearchUnavailable("Cloud research ledger is unavailable.") from exc


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _project_relpath(record: dict[str, Any], owner_path: Path) -> str:
    value = record.get("project_path")
    if not isinstance(value, str) or not value:
        return ""
    try:
        root = owner_path.resolve(strict=True)
        project = Path(value).resolve(strict=True)
        if not project.is_dir() or not project.is_relative_to(root):
            return ""
        return project.relative_to(root).as_posix()
    except (OSError, RuntimeError, ValueError):
        return ""


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
    workspace = cloud_workspaces.current()
    if workspace is None:
        raise CloudResearchUnavailable("Authenticated research workspace is unavailable.")
    project_relpath = _project_relpath(record, workspace.path)
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
                        "UPDATE jobs SET status='queued',updated_at=?,project_relpath=?,process_epoch=? WHERE session_id=?",
                        (now, project_relpath, _PROCESS_EPOCH, record["id"]),
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
                "INSERT INTO jobs(session_id,workspace_id,project_id,idempotency_key,status,created_at,updated_at,project_relpath,process_epoch) VALUES(?,?,?,?,?,?,?,?,?)",
                (
                    record["id"],
                    owner,
                    record["project_id"],
                    record["idempotency_key"],
                    "queued",
                    now,
                    now,
                    project_relpath,
                    _PROCESS_EPOCH,
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
    workspace = cloud_workspaces.current()
    if workspace is None:
        raise CloudResearchUnavailable("Authenticated research workspace is unavailable.")
    project_relpath = _project_relpath(record, workspace.path)
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
                    "INSERT INTO jobs(session_id,workspace_id,project_id,idempotency_key,status,created_at,updated_at,project_relpath,process_epoch) VALUES(?,?,?,?,?,?,?,?,?)",
                    (
                        record["id"],
                        owner,
                        record["project_id"],
                        record.get("idempotency_key", record["id"]),
                        ledger_state,
                        record.get("created_at", now),
                        now,
                        project_relpath,
                        _PROCESS_EPOCH,
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
                "UPDATE jobs SET status=?,updated_at=?,project_relpath=CASE WHEN project_relpath='' THEN ? ELSE project_relpath END WHERE session_id=?",
                (ledger_state, now, project_relpath, record["id"]),
            )
    except sqlite3.Error as exc:
        raise CloudResearchUnavailable("Cloud research ledger is unavailable.") from exc


def reconcile_orphaned_jobs() -> list[str]:
    """Delete prior-process queued rows proven to have no session or call.

    The project admission lock closes the prepare_job/_save crash window. If a
    publisher is still live, recovery waits and observes its session file. Any
    uncertain path/state or any provider-call row is preserved; age is never
    evidence for releasing a job or spend reservation.
    """
    workspace = cloud_workspaces.current()
    if workspace is None:
        raise CloudResearchUnavailable("Authenticated research workspace is unavailable.")
    owner = workspace.workspace_id
    try:
        with _connect() as db:
            candidates = db.execute(
                "SELECT session_id,project_id,project_relpath FROM jobs WHERE workspace_id=? AND status='queued' AND process_epoch<>?",
                (owner, _PROCESS_EPOCH),
            ).fetchall()
    except sqlite3.Error as exc:
        raise CloudResearchUnavailable("Cloud research ledger is unavailable.") from exc

    removed: list[str] = []
    root = workspace.path.resolve(strict=True)
    for candidate in candidates:
        session_id = candidate["session_id"]
        try:
            if str(UUID(session_id)) != session_id:
                continue
        except (ValueError, TypeError, AttributeError):
            continue
        relative = candidate["project_relpath"]
        relative_path = Path(relative) if isinstance(relative, str) else Path("/")
        if (
            not isinstance(relative, str)
            or not relative
            or relative_path.is_absolute()
            or ".." in relative_path.parts
        ):
            continue
        lexical_project = root
        unsafe = False
        for part in relative_path.parts:
            lexical_project = lexical_project / part
            if lexical_project.is_symlink():
                unsafe = True
                break
        if unsafe:
            continue
        try:
            project = lexical_project.resolve(strict=True)
            if not project.is_dir() or not project.is_relative_to(root):
                continue
            project_document = project / "project.json"
            session_directory = project / "research-sessions"
            if (
                project_document.is_symlink()
                or not project_document.is_file()
                or session_directory.is_symlink()
                or not session_directory.is_dir()
            ):
                continue
            try:
                project_view = inspect_project(str(project))
            except ProjectError:
                continue
            if project_view.project.id != candidate["project_id"]:
                continue

            # This is the same lock held by start_session from before prepare_job
            # through _save, so a live publisher cannot be mistaken for a crash.
            from sigma import research_sessions

            with research_sessions._project_manager_lock(str(project)):
                session_record = session_directory / f"{session_id}.json"
                if session_record.exists() or session_record.is_symlink():
                    continue
                with _transaction() as db:
                    current = db.execute(
                        "SELECT workspace_id,status,project_id,project_relpath,process_epoch FROM jobs WHERE session_id=?",
                        (session_id,),
                    ).fetchone()
                    if (
                        not current
                        or current["workspace_id"] != owner
                        or current["status"] != "queued"
                        or current["project_id"] != candidate["project_id"]
                        or current["project_relpath"] != relative
                        or current["process_epoch"] == _PROCESS_EPOCH
                    ):
                        continue
                    has_call = db.execute(
                        "SELECT 1 FROM calls WHERE session_id=? LIMIT 1", (session_id,)
                    ).fetchone()
                    if has_call:
                        continue
                    db.execute(
                        "DELETE FROM jobs WHERE session_id=? AND workspace_id=? AND status='queued'",
                        (session_id, owner),
                    )
                    removed.append(session_id)
        except (OSError, RuntimeError, ValueError, sqlite3.Error, ProjectError):
            # Recovery is conservative: inability to prove absence keeps the row.
            continue
    return removed


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
