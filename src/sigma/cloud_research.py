"""Durable cloud research admission and inference-spend ledger.

Research state and evidence remain in the existing project session records. This
small service-owned ledger adds cross-project, cross-process admission and
write-ahead cost reservations without creating a second research engine.
"""

from __future__ import annotations

import fcntl
import json
import os
import sqlite3
import stat
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal, InvalidOperation
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from sigma import cloud_workspaces
from sigma.projects import ProjectError, inspect_project

_PROCESS_EPOCH = uuid4().hex
USD_UNITS = 1_000_000_000
MAX_USER_SPEND_USD = Decimal("15.00")
MAX_GLOBAL_SPEND_USD = Decimal("1000.00")
LOCAL_PILOT_MONTHLY_SPEND_USD = Decimal("50.00")
MAX_PROJECT_SESSION_CALLS = 120
MAX_PROJECT_SESSION_DURATION_MINUTES = 7 * 24 * 60


class CloudResearchUnavailable(RuntimeError):
    """Cloud execution cannot be safely bounded or accounted for."""


def _workspace_id() -> str:
    workspace = _ledger_workspace()
    if workspace is None:
        raise CloudResearchUnavailable("Authenticated research workspace is unavailable.")
    return workspace.workspace_id


def _ledger_workspace():
    workspace = cloud_workspaces.current()
    if workspace is None:
        from sigma import cloud_auth

        principal = cloud_auth.local_sponsored_principal(require_selected=False)
        if principal is not None:
            from dataclasses import replace

            from sigma.projects import projects_root

            workspace = replace(
                cloud_workspaces.workspace_for_subject(principal.subject),
                path=projects_root(),
                email=principal.email,
                verified_subject=principal.subject,
            )
    return workspace


def billing_enabled() -> bool:
    """Whether provider calls must use the durable sponsored-spend ledger."""
    if cloud_workspaces.enabled():
        return True
    from sigma import cloud_auth

    return cloud_auth.local_sponsored_principal() is not None


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


def _money_ceiling(name: str, *, maximum: Decimal, message: str) -> Decimal:
    value = os.environ.get(name, "").strip()
    try:
        ceiling = Decimal(value)
    except (InvalidOperation, ValueError) as exc:
        raise CloudResearchUnavailable(message) from exc
    if not ceiling.is_finite() or not Decimal("0.01") <= ceiling <= maximum:
        raise CloudResearchUnavailable(message)
    return ceiling


def _spend_ceiling_decimal() -> Decimal:
    from sigma import cloud_auth

    # The mode-selection endpoint takes this snapshot before persisting the
    # user's first sponsored choice. Eligibility, rather than the previous
    # choice, determines whether the bounded local pilot ceiling applies.
    if cloud_auth.local_sponsored_principal(
        require_selected=False
    ) is not None and not os.environ.get("SIGMA_CLOUD_GLOBAL_SPEND_CEILING_USD"):
        # A small invited pilot should not be stopped by a $0.25 lifetime
        # API-rate-equivalent budget. The local default is bounded per month.
        return LOCAL_PILOT_MONTHLY_SPEND_USD
    return _money_ceiling(
        "SIGMA_CLOUD_GLOBAL_SPEND_CEILING_USD",
        maximum=MAX_GLOBAL_SPEND_USD,
        message="Cloud research is disabled until a valid global inference-spend ceiling of at most $1000 is configured.",
    )


def _global_ceiling_failure_message() -> str:
    """Give local sponsored operators the missing configured-cap diagnosis.

    The local default is an internal API-rate equivalent, not evidence of
    actual API charges or provider availability. Explicit ceilings are honored.
    """
    if (
        not os.environ.get("SIGMA_CLOUD_GLOBAL_SPEND_CEILING_USD", "").strip()
        and _global_spend_period() == "calendar_month"
    ):
        return (
            "The global inference-spend ceiling has been reached: local sponsored "
            "research exhausted its $50 monthly shared API-rate-equivalent budget. "
            "Saved research is available; unused provider reservations remain held "
            "across month boundaries. The budget renews next UTC month."
        )
    return "The global inference-spend ceiling has been reached; saved research remains available."


def _user_spend_ceiling_decimal() -> Decimal:
    return _money_ceiling(
        "SIGMA_CLOUD_USER_SPEND_CEILING_USD",
        maximum=MAX_USER_SPEND_USD,
        message="Cloud research is disabled until a valid default per-user inference allowance of at most $15 is configured.",
    )


def _admin_has_unlimited_spend() -> bool:
    """An active, verified administrator has no individual sponsored-dollar cap."""
    from sigma import cloud_auth

    workspace = _ledger_workspace()
    cfg = cloud_auth.config()
    if not cfg.enabled or cfg.error or workspace is None or not workspace.email:
        return False
    with cloud_auth._db(cfg) as db:
        state = (
            db.execute(
                "SELECT role,access_active,email FROM user_state WHERE subject=?",
                (workspace.verified_subject,),
            ).fetchone()
            if workspace.verified_subject
            else db.execute(
                "SELECT role,access_active,email FROM user_state WHERE workspace_id=?",
                (workspace.workspace_id,),
            ).fetchone()
        )
    return bool(
        state is not None
        and state["role"] == "admin"
        and state["access_active"]
        and state["email"] == workspace.email
    )


def _local_default_admin_global_exempt() -> bool:
    """Local verified admins are unlimited only under the default pilot budget.

    An explicitly configured global spending ceiling remains binding for *all*
    principals, including admins. Hosted billing never receives this exemption.
    """
    from sigma import cloud_auth

    return (
        not cloud_workspaces.enabled()
        and not os.environ.get("SIGMA_CLOUD_GLOBAL_SPEND_CEILING_USD", "").strip()
        and cloud_auth.local_sponsored_principal(require_selected=False) is not None
        and _admin_has_unlimited_spend()
    )


def _effective_user_spend_ceiling_decimal() -> Decimal:
    from sigma import cloud_auth

    workspace = _ledger_workspace()
    # This displayed nominal ceiling is not a cumulative admin allowance:
    # admission remains governed solely by the global spending ceiling.
    if _admin_has_unlimited_spend():
        return _spend_ceiling_decimal()
    try:
        default = _user_spend_ceiling_decimal()
    except CloudResearchUnavailable:
        if workspace is None or not workspace.email:
            raise
        default = None
    if workspace is None or not workspace.email:
        if default is None:
            raise CloudResearchUnavailable("Cloud research user allowance is unavailable.")
        return default
    try:
        from sigma.cloud_auth import effective_spending_allowance

        if default is None:
            from sigma.cloud_auth import _allowance_in_db, _configured_default_allowance, _db

            cfg = cloud_auth.config()
            with _db(cfg) as db:
                allowance = _allowance_in_db(
                    db,
                    cloud_auth._normalize_email(workspace.email),
                    _configured_default_allowance(),
                )
            if allowance is None:
                raise ValueError("No per-account sponsored allowance is configured.")
            value = Decimal(str(allowance))
        else:
            value = Decimal(str(effective_spending_allowance(workspace.email, float(default))))
    except Exception as exc:
        raise CloudResearchUnavailable("Cloud access spending policy is unavailable.") from exc
    if not value.is_finite() or not Decimal("0.01") <= value <= MAX_USER_SPEND_USD:
        raise CloudResearchUnavailable("Cloud access spending policy is invalid.")
    return value


def _spend_ceiling() -> float:
    """Retain the existing helper for callers and diagnostics."""
    return float(_spend_ceiling_decimal())


def _usd_units(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        raise CloudResearchUnavailable("Cloud inference cost is invalid.")
    try:
        amount = Decimal(str(value))
    except InvalidOperation as exc:
        raise CloudResearchUnavailable("Cloud inference cost is invalid.") from exc
    if not amount.is_finite() or amount < 0:
        raise CloudResearchUnavailable("Cloud inference cost is invalid.")
    return int((amount * USD_UNITS).to_integral_value(rounding=ROUND_CEILING))


def _ceiling_units(value: Decimal) -> int:
    return int((value * USD_UNITS).to_integral_value(rounding=ROUND_FLOOR))


def _call_amount_units(db: sqlite3.Connection, where: str, parameters: tuple[Any, ...] = ()) -> int:
    rows = db.execute(f"SELECT amount_usd FROM calls {where}", parameters).fetchall()
    return sum(_usd_units(row["amount_usd"]) for row in rows)


def _global_spend_period() -> str:
    """Renew only the local pilot or an explicitly opted-in hosted budget."""
    configured = os.environ.get("SIGMA_CLOUD_GLOBAL_SPEND_WINDOW", "").strip().lower()
    if configured in {"cumulative", "calendar_month"}:
        return configured
    if configured:
        raise CloudResearchUnavailable("Global inference spending window is invalid.")
    from sigma import cloud_auth

    if (
        cloud_auth.local_sponsored_principal(require_selected=False) is not None
        and not os.environ.get("SIGMA_CLOUD_GLOBAL_SPEND_CEILING_USD", "").strip()
    ):
        return "calendar_month"
    return "cumulative"


def _global_window_start() -> str | None:
    if _global_spend_period() == "cumulative":
        return None
    now = datetime.now(UTC)
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()


def _next_global_reset_at() -> str | None:
    if _global_spend_period() == "cumulative":
        return None
    now = datetime.now(UTC)
    year, month = (now.year + 1, 1) if now.month == 12 else (now.year, now.month + 1)
    return datetime(year, month, 1, tzinfo=UTC).isoformat()


def _global_call_amount_units(db: sqlite3.Connection) -> int:
    """Reserve worst-case liability globally; user allowances remain estimates."""
    window_start = _global_window_start()
    # Local default pilot admin calls are excluded from the *default* shared
    # ceiling. Explicit or hosted operator caps always count all calls, even
    # those previously exempt under the local default. Legacy rows from
    # before this schema migration are non-exempt and remain fully accounted.
    explicit_or_hosted = (
        bool(os.environ.get("SIGMA_CLOUD_GLOBAL_SPEND_CEILING_USD", "").strip())
        or cloud_workspaces.enabled()
    )
    query = "SELECT amount_usd, maximum_liability_usd, status FROM calls"
    filters = ["global_cap_exempt=0"] if not explicit_or_hosted else []
    params: tuple[Any, ...] = ()
    if window_start is not None:
        # An unsettled request remains an obligation across month boundaries.
        filters.append("(created_at>=? OR status IN ('reserved','unknown'))")
        params = (window_start,)
    if filters:
        query += " WHERE " + " AND ".join(filters)
    return sum(
        _usd_units(
            max(row["amount_usd"], row["maximum_liability_usd"])
            if row["status"] in {"reserved", "unknown"}
            else row["amount_usd"]
        )
        for row in db.execute(query, params)
    )


def _evaluation_queue_limits() -> tuple[int, int, int, int]:
    """Independent per-workspace and global worker/queue capacities.

    Project-specific session admission is enforced separately and atomically.
    Raising these limits does not bypass provider spend or per-user allowances.
    """
    per_user_running = _positive_int("SIGMA_CLOUD_USER_MAX_CONCURRENT", 4)
    global_running = _positive_int("SIGMA_CLOUD_GLOBAL_MAX_CONCURRENT", 32)
    per_user_queued = _positive_int("SIGMA_CLOUD_USER_MAX_QUEUED", 4)
    global_queued = _positive_int("SIGMA_CLOUD_GLOBAL_MAX_QUEUED", 16)
    return per_user_running, global_running, per_user_queued, global_queued


def evaluation_session_limits(limits: dict[str, Any]) -> dict[str, Any]:
    """Sponsorship affects spend allowance, not the user's research duration."""
    return dict(limits)


def local_sponsored_session_limits(limits: dict[str, Any]) -> dict[str, Any]:
    """Preserve the selected project duration for local sponsored research."""
    return dict(limits)


def session_call_ceiling() -> int:
    """Return the maximum call limit accepted by Project Settings."""
    return MAX_PROJECT_SESSION_CALLS


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
                session_slot INTEGER NOT NULL DEFAULT 0,
                job_kind TEXT NOT NULL DEFAULT 'research',
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
                updated_at TEXT NOT NULL,
                maximum_liability_usd REAL NOT NULL DEFAULT 0,
                global_cap_exempt INTEGER NOT NULL DEFAULT 0 CHECK(global_cap_exempt IN (0,1))
            );
            CREATE TABLE IF NOT EXISTS allowance_windows (
                workspace_id TEXT PRIMARY KEY,
                reset_at TEXT NOT NULL,
                updated_by TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS allowance_reload_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workspace_id TEXT NOT NULL,
                reset_at TEXT NOT NULL,
                actor_email TEXT NOT NULL
            );
        """)
        columns = {row["name"] for row in db.execute("PRAGMA table_info(jobs)")}
        if "project_relpath" not in columns:
            db.execute("ALTER TABLE jobs ADD COLUMN project_relpath TEXT NOT NULL DEFAULT ''")
        if "process_epoch" not in columns:
            db.execute("ALTER TABLE jobs ADD COLUMN process_epoch TEXT NOT NULL DEFAULT ''")
        if "session_slot" not in columns:
            db.execute("ALTER TABLE jobs ADD COLUMN session_slot INTEGER NOT NULL DEFAULT 0")
        if "job_kind" not in columns:
            db.execute("ALTER TABLE jobs ADD COLUMN job_kind TEXT NOT NULL DEFAULT 'research'")
        call_columns = {row["name"] for row in db.execute("PRAGMA table_info(calls)")}
        if "maximum_liability_usd" not in call_columns or "global_cap_exempt" not in call_columns:
            # Serialize one-time additive schema migrations across backend processes.
            db.execute("BEGIN IMMEDIATE")
            try:
                columns = {row["name"] for row in db.execute("PRAGMA table_info(calls)")}
                if "maximum_liability_usd" not in columns:
                    db.execute(
                        "ALTER TABLE calls ADD COLUMN maximum_liability_usd REAL NOT NULL DEFAULT 0"
                    )
                if "global_cap_exempt" not in columns:
                    db.execute(
                        "ALTER TABLE calls ADD COLUMN global_cap_exempt INTEGER NOT NULL DEFAULT 0"
                    )
                db.commit()
            except sqlite3.Error:
                db.rollback()
                raise
        os.chmod(path, 0o600)
        return db
    except (OSError, sqlite3.Error) as exc:
        raise CloudResearchUnavailable("Cloud research ledger is unavailable.") from exc


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _project_relpath(record: dict[str, Any], owner_path: Path) -> str:
    """Persist a relocatable, authorized workspace-relative project locator.

    A collaborator's Session is billed under their own workspace but the
    shared project lives under the verified owner's *different* workspace.
    Store that location with an explicit, safe prefix so restart recovery can
    find the saved record without ever trusting a client absolute path.
    """
    value = record.get("project_path")
    if not isinstance(value, str) or not value:
        return ""
    try:
        root = owner_path.resolve(strict=True)
        project = Path(value).resolve(strict=True)
        if not (project.is_dir() or (project.suffix == ".json" and project.is_file())):
            return ""
        if project.is_relative_to(root):
            return project.relative_to(root).as_posix()
        # Shared-project paths may reference a sibling identity workspace, but
        # never an arbitrary path outside the verified workspace collection.
        relative = project.relative_to(root.parent)
        if (
            len(relative.parts) < 2
            or len(relative.parts[0]) != 32
            or any(char not in "0123456789abcdef" for char in relative.parts[0])
        ):
            return ""
        from sigma import project_collaboration

        if not project_collaboration.authorized_shared_path(project):
            return ""
        return "@shared/" + relative.as_posix()
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


def job_status(session_id: str) -> str | None:
    """Return the owner's durable queue state, or None when no reservation exists."""
    owner = _workspace_id()
    try:
        with _connect() as db:
            row = db.execute(
                "SELECT status FROM jobs WHERE session_id=? AND workspace_id=?",
                (session_id, owner),
            ).fetchone()
            return row["status"] if row else None
    except sqlite3.Error as exc:
        raise CloudResearchUnavailable("Cloud research ledger is unavailable.") from exc


def job_is_foreign(session_id: str) -> bool:
    """Check ownership without returning another workspace's identity."""
    owner = _workspace_id()
    try:
        with _connect() as db:
            row = db.execute(
                "SELECT workspace_id FROM jobs WHERE session_id=?", (session_id,)
            ).fetchone()
            return row is not None and row["workspace_id"] != owner
    except sqlite3.Error as exc:
        raise CloudResearchUnavailable("Cloud research ledger is unavailable.") from exc


def has_reserved_calls(session_id: str) -> bool:
    """Unresolved write-ahead reservations must not become new dispatches."""
    owner = _workspace_id()
    try:
        with _connect() as db:
            return (
                db.execute(
                    "SELECT 1 FROM calls WHERE session_id=? AND workspace_id=? "
                    "AND status='reserved' LIMIT 1",
                    (session_id, owner),
                ).fetchone()
                is not None
            )
    except sqlite3.Error as exc:
        raise CloudResearchUnavailable("Cloud research ledger is unavailable.") from exc


def _legacy_session_status(project_path: str, project_id: str, session_id: str) -> str | None:
    """Distinguish pre-migration session jobs from standalone inference rows."""
    from sigma import research_sessions
    from sigma.projects import ProjectError

    project = Path(project_path)
    member = f"research-sessions/{session_id}.json"
    try:
        if project.suffix == ".json":
            from sigma.project_bundle import read_bundle

            if member not in read_bundle(project_path)["files"]:
                return None
        else:
            directory = project / "research-sessions"
            target = directory / f"{session_id}.json"
            if not target.exists() and not target.is_symlink():
                return None
            if directory.is_symlink() or target.is_symlink() or not target.is_file():
                raise CloudResearchUnavailable(
                    "An existing hosted session record cannot be inspected safely."
                )
        saved = research_sessions._read(project_path, session_id)
    except CloudResearchUnavailable:
        raise
    except (OSError, ValueError, ProjectError) as exc:
        raise CloudResearchUnavailable(
            "An existing hosted session record cannot be inspected safely."
        ) from exc
    if saved.get("id") != session_id or saved.get("project_id") != project_id:
        raise CloudResearchUnavailable(
            "An existing hosted session record does not match its ledger row."
        )
    return saved.get("status")


def _user_call_amount_units(
    db: sqlite3.Connection, workspace_id: str, status: str | None = None
) -> int:
    window = db.execute(
        "SELECT reset_at FROM allowance_windows WHERE workspace_id=?", (workspace_id,)
    ).fetchone()
    where = "WHERE workspace_id=?"
    parameters: list[Any] = [workspace_id]
    if window:
        where += " AND created_at>=?"
        parameters.append(window["reset_at"])
    if status:
        where += " AND status=?"
        parameters.append(status)
    return _call_amount_units(db, where, tuple(parameters))


def _user_call_tokens(db: sqlite3.Connection, workspace_id: str) -> int:
    """Count observed and reserved tokens in the current user allowance window.

    The full durable ledger is retained for the independent global spending
    ceiling; an authorized allowance reload also restores the per-user token
    allowance instead of silently exhausting it for the account's lifetime.
    """
    window = db.execute(
        "SELECT reset_at FROM allowance_windows WHERE workspace_id=?", (workspace_id,)
    ).fetchone()
    query = "SELECT COALESCE(SUM(token_reservation),0) FROM calls WHERE workspace_id=?"
    params: tuple[Any, ...] = (workspace_id,)
    if window:
        query += " AND created_at>=?"
        params = (workspace_id, window["reset_at"])
    return int(db.execute(query, params).fetchone()[0])


def admin_reload_workspace_allowance(workspace_id: str, actor_email: str) -> str:
    """Start a fresh per-user allowance window while preserving global cost history."""
    if not isinstance(workspace_id, str) or len(workspace_id) != 32:
        raise CloudResearchUnavailable("Workspace spending identity is invalid.")
    if not isinstance(actor_email, str) or not actor_email:
        raise CloudResearchUnavailable("Allowance reload actor is invalid.")
    try:
        with _transaction() as db:
            reset_at = _now()
            db.execute(
                "INSERT INTO allowance_windows(workspace_id,reset_at,updated_by) VALUES(?,?,?) "
                "ON CONFLICT(workspace_id) DO UPDATE SET reset_at=excluded.reset_at,updated_by=excluded.updated_by",
                (workspace_id, reset_at, actor_email),
            )
            db.execute(
                "INSERT INTO allowance_reload_events(workspace_id,reset_at,actor_email) VALUES(?,?,?)",
                (workspace_id, reset_at, actor_email),
            )
        return reset_at
    except sqlite3.Error as exc:
        raise CloudResearchUnavailable("Allowance could not be reloaded safely.") from exc


def _require_research_queue_capacity(db: sqlite3.Connection, owner: str, session_id: str) -> None:
    """Bound durable admission separately from active worker capacity.

    Waiting jobs have never dispatched a provider call and must not consume a
    running slot. The configured queue allowances are *additional* to the
    per-user and global running limits, including currently running jobs.
    """
    user_running, global_running, user_waiting, global_waiting = _evaluation_queue_limits()
    states = "('queued','running','stopping')"
    user = db.execute(
        "SELECT COUNT(*) FROM jobs WHERE workspace_id=? AND job_kind='research' "
        f"AND status IN {states} AND session_id<>?",
        (owner, session_id),
    ).fetchone()[0]
    total = db.execute(
        "SELECT COUNT(*) FROM jobs WHERE job_kind='research' "
        f"AND status IN {states} AND session_id<>?",
        (session_id,),
    ).fetchone()[0]
    if user >= user_running + user_waiting or total >= global_running + global_waiting:
        raise CloudResearchUnavailable(
            "Research queue is full. Saved work is safe; retry when queued work completes."
        )


def prepare_job(record: dict[str, Any]) -> None:
    """Durably admit a queued job without reserving running capacity or provider calls."""
    owner = _workspace_id()
    from sigma.cloud_sponsor import inference_provider

    auxiliary = record.get("job_kind") == "auxiliary"
    provider = inference_provider()
    if record.get("mode") != provider or provider not in {"api_key", "chatgpt"}:
        raise CloudResearchUnavailable(
            "Cloud research requires the explicitly configured sponsor provider."
        )
    if record.get("cost_status") != "available":
        raise CloudResearchUnavailable("Sponsored research requires a model with a reviewed price.")
    global_ceiling_units = _ceiling_units(_spend_ceiling_decimal())
    # An explicit account allowance is sufficient. Require the configured
    # default only when resolving an account that has no specific allowance.
    user_ceiling_units = _ceiling_units(_effective_user_spend_ceiling_decimal())
    unlimited_admin = _admin_has_unlimited_spend()
    global_exempt = _local_default_admin_global_exempt()
    token_budget = _positive_int("SIGMA_CLOUD_USER_TOKEN_BUDGET", 2_000_000)
    call_limit = record.get("call_limit")
    duration_limit = record.get("duration_limit_minutes")
    maximum_cost = record.get("maximum_estimated_cost_usd")
    # Historical shared-call sessions retain the original admission ceiling.
    # New sessions have an explicit, versioned per-strategy pair-slot ceiling.
    # 12 is the maximum permitted selected-strategy count in start_session.
    call_ceiling = (
        12 * 60 * 20 * 2 if record.get("scheduler_version") == 2 else session_call_ceiling()
    )
    if (
        type(call_limit) is not int
        or not 2 <= call_limit <= call_ceiling
        or (
            duration_limit is not None
            and (
                type(duration_limit) is not int
                or not 1 <= duration_limit <= MAX_PROJECT_SESSION_DURATION_MINUTES
            )
        )
        or (
            maximum_cost is not None
            and (
                type(maximum_cost) not in {int, float}
                or not isinstance(maximum_cost, (int, float))
                or not 0.01 <= maximum_cost <= 100
            )
        )
    ):
        if cloud_workspaces.enabled():
            raise CloudResearchUnavailable(
                "Hosted research duration must follow the project's valid research limits."
            )
        raise CloudResearchUnavailable(
            "Local research duration must follow the project's valid research limits."
        )
    workspace = _ledger_workspace()
    if workspace is None:
        raise CloudResearchUnavailable("Authenticated research workspace is unavailable.")
    project_relpath = _project_relpath(record, workspace.path)
    session_limit = record.get("max_concurrent_sessions")
    if session_limit is not None and (type(session_limit) is not int or session_limit < 1):
        raise CloudResearchUnavailable(
            "Maximum concurrent sessions must be a positive whole number."
        )
    session_slot = int(session_limit is not None)
    now = _now()
    try:
        with _transaction() as db:
            if session_slot:
                assert session_limit is not None
                legacy_rows = db.execute(
                    "SELECT session_id FROM jobs WHERE workspace_id=? AND project_id=? AND (project_relpath=? OR project_relpath='') AND session_slot=0 AND status IN ('queued','running','stopping') AND session_id<>?",
                    (owner, record["project_id"], project_relpath, record["id"]),
                ).fetchall()
                for legacy in legacy_rows:
                    saved_status = _legacy_session_status(
                        record["project_path"], record["project_id"], legacy["session_id"]
                    )
                    if saved_status is None:
                        # Standalone inference uses the same ledger but has no
                        # research-session record and consumes no project slot.
                        continue
                    if saved_status in {"stopped", "failed", "ended", "completed"}:
                        db.execute(
                            "UPDATE jobs SET status='terminal',session_slot=1,project_relpath=?,updated_at=? WHERE session_id=? AND workspace_id=? AND session_slot=0",
                            (project_relpath, now, legacy["session_id"], owner),
                        )
                    elif saved_status in {"paused", "interrupted"}:
                        db.execute(
                            "UPDATE jobs SET status=?,session_slot=1,project_relpath=?,updated_at=? WHERE session_id=? AND workspace_id=? AND session_slot=0",
                            (saved_status, project_relpath, now, legacy["session_id"], owner),
                        )
                    else:
                        # Unknown or active states fail closed as occupied slots.
                        db.execute(
                            "UPDATE jobs SET session_slot=1,project_relpath=?,updated_at=? WHERE session_id=? AND workspace_id=? AND session_slot=0",
                            (project_relpath, now, legacy["session_id"], owner),
                        )
                # Project-level running capacity is checked at worker claim, not
                # at admission. Independent accepted sessions can wait here.
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
                    # Resuming a saved session must not silently queue work
                    # when its funding is already exhausted. Keep the saved
                    # terminal/interrupted state intact for playback.
                    if not global_exempt and _global_call_amount_units(db) >= global_ceiling_units:
                        raise CloudResearchUnavailable(_global_ceiling_failure_message())
                    if (
                        not unlimited_admin
                        and _user_call_amount_units(db, owner) >= user_ceiling_units
                    ):
                        raise CloudResearchUnavailable(
                            "Your cumulative cloud research allowance has been reached; saved research remains available."
                        )
                    if not unlimited_admin and _user_call_tokens(db, owner) >= token_budget:
                        raise CloudResearchUnavailable(
                            "The per-user research token budget has been reached."
                        )
                    if not auxiliary:
                        _require_research_queue_capacity(db, owner, record["id"])
                    db.execute(
                        "UPDATE jobs SET status='queued',updated_at=?,project_relpath=?,process_epoch=?,session_slot=? WHERE session_id=?",
                        (now, project_relpath, _PROCESS_EPOCH, session_slot, record["id"]),
                    )
                return
            # A budget already exhausted before launch cannot fund any call.
            # Reject the request *before* creating a saved zero-call session.
            # A nonzero remainder may still be too small for this model's
            # actual first-call reservation; reserve_call remains authoritative.
            if not global_exempt and _global_call_amount_units(db) >= global_ceiling_units:
                raise CloudResearchUnavailable(_global_ceiling_failure_message())
            if not unlimited_admin and _user_call_amount_units(db, owner) >= user_ceiling_units:
                raise CloudResearchUnavailable(
                    "Your cumulative cloud research allowance has been reached; saved research remains available."
                )
            if not unlimited_admin and _user_call_tokens(db, owner) >= token_budget:
                raise CloudResearchUnavailable(
                    "The per-user research token budget has been reached."
                )
            if not auxiliary:
                _require_research_queue_capacity(db, owner, record["id"])
            # "queued" is a durable waiting state; worker slots are acquired
            # separately in claim_job only immediately before execution.
            db.execute(
                "INSERT INTO jobs(session_id,workspace_id,project_id,idempotency_key,status,created_at,updated_at,project_relpath,process_epoch,session_slot,job_kind) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
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
                    session_slot,
                    "auxiliary" if auxiliary else "research",
                ),
            )
    except sqlite3.Error as exc:
        raise CloudResearchUnavailable("Cloud research ledger is unavailable.") from exc


def claim_job(session_id: str, *, project_limit: int | None = None) -> bool:
    """Atomically claim user, global and shared-project running capacity."""
    if project_limit is not None and (type(project_limit) is not int or project_limit < 1):
        raise CloudResearchUnavailable("Project concurrency limit is invalid.")
    owner = _workspace_id()
    user_limit, global_limit, _user_queue, _global_queue = _evaluation_queue_limits()
    try:
        with _transaction() as db:
            job = db.execute("SELECT * FROM jobs WHERE session_id=?", (session_id,)).fetchone()
            if not job or job["workspace_id"] != owner:
                raise CloudResearchUnavailable("Research job is unavailable.")
            # A running job belongs to an already claimed worker. Returning
            # True here lets a second worker repeat provider calls after an
            # interrupted process while the durable status is still running.
            # Only a queued job can be claimed; the caller must recover stale
            # running slots under the exclusive per-session worker lock.
            if job["status"] != "queued":
                return False
            # Fencing in the worker is not sufficient: a crashed backend
            # may have left an unsettled call under an outer queued status.
            if db.execute(
                "SELECT 1 FROM calls WHERE session_id=? AND workspace_id=? "
                "AND status='reserved' LIMIT 1",
                (session_id, owner),
            ).fetchone():
                raise CloudResearchUnavailable(
                    "Queued research has an unsettled provider reservation. "
                    "Recover the interrupted Session before another dispatch."
                )
            if job["job_kind"] != "auxiliary":
                # The project limit applies to *running* work, not queued
                # admissions. Match by immutable project ID across creator
                # workspaces, so a collaborator cannot bypass its limit.
                if job["session_slot"]:
                    limit = project_limit or 1
                    project_running = db.execute(
                        """SELECT COUNT(*) FROM jobs
                           WHERE project_id=? AND session_slot=1
                           AND job_kind='research'
                           AND status IN ('running','stopping') AND session_id<>?""",
                        (job["project_id"], session_id),
                    ).fetchone()[0]
                    if project_running >= limit:
                        return False
                user_running = db.execute(
                    "SELECT COUNT(*) FROM jobs WHERE workspace_id=? AND job_kind='research' AND status IN ('running','stopping')",
                    (owner,),
                ).fetchone()[0]
                global_running = db.execute(
                    "SELECT COUNT(*) FROM jobs WHERE job_kind='research' AND status IN ('running','stopping')"
                ).fetchone()[0]
                if user_running >= user_limit or global_running >= global_limit:
                    return False
            # A queued job may have survived a previous backend process.
            # Claiming it transfers execution ownership to this process in
            # the same transaction as the running-slot reservation. Otherwise
            # orphan reconciliation may classify a freshly claimed worker as
            # belonging to the old process and interrupt its billing ledger.
            db.execute(
                "UPDATE jobs SET status='running',process_epoch=?,updated_at=? "
                "WHERE session_id=? AND workspace_id=? AND status='queued'",
                (_PROCESS_EPOCH, _now(), session_id, owner),
            )
            return True
    except sqlite3.Error as exc:
        raise CloudResearchUnavailable("Cloud research ledger is unavailable.") from exc


def begin_standalone_inference(project_id: str, project_path: str) -> str:
    """Reserve an owner-scoped execution slot for one non-session AI operation."""
    if not isinstance(project_id, str) or not project_id or not isinstance(project_path, str):
        raise CloudResearchUnavailable("Cloud inference project identity is invalid.")
    from sigma.cloud_sponsor import inference_provider

    session_id = str(uuid4())
    prepare_job(
        {
            "id": session_id,
            "mode": inference_provider(),
            "project_id": project_id,
            "project_path": project_path,
            "idempotency_key": str(uuid4()),
            "maximum_estimated_cost_usd": 0.25,
            "cost_status": "available",
            "call_limit": 2,
            "duration_limit_minutes": 1,
            "job_kind": "auxiliary",
        }
    )
    if not claim_job(session_id):
        try:
            with _transaction() as db:
                db.execute("DELETE FROM jobs WHERE session_id=? AND status='queued'", (session_id,))
        except sqlite3.Error as exc:
            raise CloudResearchUnavailable("Cloud inference ledger is unavailable.") from exc
        raise CloudResearchUnavailable(
            "Cloud inference is at its concurrency limit; retry shortly."
        )
    return session_id


def finish_standalone_inference(session_id: str) -> None:
    """Release a standalone operation's concurrency slot after provider I/O ends."""
    owner = _workspace_id()
    try:
        with _transaction() as db:
            db.execute(
                "UPDATE jobs SET status='terminal',updated_at=? WHERE session_id=? AND workspace_id=? AND status IN ('running','stopping')",
                (_now(), session_id, owner),
            )
    except sqlite3.Error as exc:
        raise CloudResearchUnavailable("Cloud inference ledger is unavailable.") from exc


def standalone_call_reservation(
    model: str, input_bytes: int, output_tokens: int
) -> tuple[float, int]:
    """Estimate a conservative per-attempt cap from reviewed model prices."""
    if (
        type(input_bytes) is not int
        or input_bytes < 0
        or type(output_tokens) is not int
        or output_tokens < 1
    ):
        raise CloudResearchUnavailable("Cloud inference reservation is invalid.")
    from sigma.research_sessions import TOKEN_PRICES_PER_MILLION

    prices = TOKEN_PRICES_PER_MILLION.get(model)
    if prices is None:
        raise CloudResearchUnavailable("Selected model has no reviewed cloud price.")
    # UTF-8 bytes bound tokenizer input conservatively; round to cents and add
    # 15% headroom before provider I/O. Input is reserved as uncached.
    estimate = Decimal(input_bytes) * Decimal(str(prices["input"]))
    estimate += Decimal(output_tokens) * Decimal(str(prices["output"]))
    estimate = estimate / Decimal(1_000_000) * Decimal("1.15")
    rounded = estimate.quantize(Decimal("0.01"), rounding=ROUND_CEILING)
    return float(max(rounded, Decimal("0.01"))), input_bytes + output_tokens


@dataclass
class ProviderAttempt:
    job_id: str
    call_id: str
    model: str
    dispatched: bool = False
    settled: bool = False


def provider_request_input_bytes(payload: Any) -> int:
    """Return a conservative UTF-8 bound for all billable structured input."""
    if not isinstance(payload, dict):
        raise CloudResearchUnavailable("Cloud inference request is invalid.")
    # Responses charges for instructions, input, and structured-output format
    # content. Keep all three in the same deterministic encoding used by the
    # request; transport and sampling metadata are not prompt input.
    billable = {key: payload[key] for key in ("instructions", "input", "text") if key in payload}
    if not all(key in billable for key in ("instructions", "input", "text")):
        raise CloudResearchUnavailable("Cloud inference request is incomplete.")
    try:
        encoded = json.dumps(billable, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    except (TypeError, ValueError, UnicodeEncodeError) as exc:
        raise CloudResearchUnavailable("Cloud inference request is invalid.") from exc
    return len(encoded)


def start_provider_attempt(
    project_id: str, project_path: str, model: str, payload: Any, output_tokens: int
) -> ProviderAttempt | None:
    """Reserve one non-session provider attempt; local calls remain unchanged."""
    if not billing_enabled():
        return None
    job_id = begin_standalone_inference(project_id, project_path)
    call_id = uuid4().hex
    try:
        input_bytes = provider_request_input_bytes(payload)
        amount, tokens = standalone_call_reservation(model, input_bytes, output_tokens)
        reserve_call(job_id, call_id, amount, tokens)
    except Exception:
        finish_standalone_inference(job_id)
        raise
    return ProviderAttempt(job_id, call_id, model)


def settle_provider_attempt(attempt: ProviderAttempt | None, response: Any) -> None:
    """Reconcile response usage, retaining the reservation when price/usage is absent."""
    if attempt is None:
        return
    from sigma.research_sessions import _estimate_cost

    usage = response.get("usage") if isinstance(response, dict) else None
    details = usage.get("input_tokens_details", {}) if isinstance(usage, dict) else {}
    input_tokens = usage.get("input_tokens") if isinstance(usage, dict) else None
    output_tokens = usage.get("output_tokens") if isinstance(usage, dict) else None
    cached = details.get("cached_tokens", 0) if isinstance(details, dict) else None
    valid = (
        type(input_tokens) is int
        and input_tokens >= 0
        and type(output_tokens) is int
        and output_tokens >= 0
        and type(cached) is int
        and 0 <= cached <= input_tokens
    )
    parsed = (
        {
            "input_tokens": input_tokens,
            "cached_input_tokens": cached,
            "output_tokens": output_tokens,
        }
        if valid
        else None
    )
    settle_call(
        attempt.job_id,
        attempt.call_id,
        input_tokens=input_tokens if type(input_tokens) is int else None,
        output_tokens=output_tokens if type(output_tokens) is int else None,
        estimated_cost_usd=_estimate_cost(attempt.model, parsed) if parsed else None,
    )
    attempt.settled = True


def finish_provider_attempt(attempt: ProviderAttempt | None) -> None:
    """Release its concurrency slot and preserve any dispatched uncertain charge."""
    if attempt is None:
        return
    try:
        if not attempt.settled:
            if attempt.dispatched:
                mark_call_unknown(attempt.job_id, attempt.call_id)
            else:
                mark_call_not_dispatched(attempt.job_id, attempt.call_id)
    finally:
        finish_standalone_inference(attempt.job_id)


def sync_job(record: dict[str, Any]) -> None:
    """Persist lifecycle transitions as an owner-checked ledger projection."""
    owner = _workspace_id()
    workspace = _ledger_workspace()
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


def _reconcile_foreign_job(candidate: sqlite3.Row, project: Path, owner: str) -> None:
    """Fence a dead foreign worker in the ledger, never in project data.

    Only server-owned, path-validated ledger records enter this maintenance
    path. The triggering browser identity never becomes the run creator.
    """
    from sigma import research_sessions

    with cloud_workspaces.without_workspace():
        view = inspect_project(str(project))
        if view.project.id != candidate["project_id"]:
            return
        with (
            research_sessions._project_manager_lock(str(project)),
            research_sessions._idle_worker_lock(str(project), candidate["session_id"]),
        ):
            # The admission lock rules out a concurrent unpublished
            # Session receipt. Retire it only if no provider call exists.
            if project.suffix == ".json":
                from sigma.project_bundle import read_bundle

                has_session = (
                    f"research-sessions/{candidate['session_id']}.json"
                    in read_bundle(str(project))["files"]
                )
            else:
                session_dir = project / "research-sessions"
                if session_dir.is_symlink() or not session_dir.is_dir():
                    return
                record_path = session_dir / f"{candidate['session_id']}.json"
                if record_path.is_symlink():
                    return  # Unsafe state is never evidence of absence.
                has_session = record_path.is_file()
            with _transaction() as db:
                row = db.execute(
                    "SELECT workspace_id,project_id,project_relpath,process_epoch,status "
                    "FROM jobs WHERE session_id=?",
                    (candidate["session_id"],),
                ).fetchone()
                if (
                    row is None
                    or row["workspace_id"] != owner
                    or row["project_id"] != candidate["project_id"]
                    or row["project_relpath"] != candidate["project_relpath"]
                    # A newer process may claim this slot after the stale
                    # candidate snapshot but before the OS-lock/SQL fence.
                    or row["process_epoch"] != candidate["process_epoch"]
                    or row["process_epoch"] == _PROCESS_EPOCH
                    or row["status"] not in {"queued", "running", "stopping"}
                ):
                    return
                unsettled = db.execute(
                    "SELECT 1 FROM calls WHERE session_id=? AND status='reserved' LIMIT 1",
                    (candidate["session_id"],),
                ).fetchone()
                if row["status"] == "queued" and not unsettled and has_session:
                    return
                has_call = db.execute(
                    "SELECT 1 FROM calls WHERE session_id=? LIMIT 1",
                    (candidate["session_id"],),
                ).fetchone()
                if row["status"] == "queued" and not has_session and not has_call:
                    db.execute(
                        "DELETE FROM jobs WHERE session_id=? AND workspace_id=? "
                        "AND status='queued' AND process_epoch=?",
                        (candidate["session_id"], owner, row["process_epoch"]),
                    )
                    return
                stamp = _now()
                changed = db.execute(
                    "UPDATE jobs SET status='interrupted',updated_at=? "
                    "WHERE session_id=? AND workspace_id=? AND process_epoch=? "
                    "AND status IN ('queued','running','stopping')",
                    (stamp, candidate["session_id"], owner, row["process_epoch"]),
                )
                if changed.rowcount != 1:
                    return
                db.execute(
                    "UPDATE calls SET status='unknown',updated_at=? "
                    "WHERE session_id=? AND workspace_id=? AND status='reserved'",
                    (stamp, candidate["session_id"], owner),
                )


def reconcile_orphaned_jobs(*, ledger_only_foreign: bool = False) -> list[str]:
    """Reconcile prior-process queued and running session reservations.

    The project admission lock closes the prepare_job/_save crash window. If a
    publisher is still live, recovery waits and observes its session file. Any
    uncertain path/state or any provider-call row is preserved; age is never
    evidence for releasing a job or spend reservation.
    """
    from sigma import cloud_auth, project_collaboration

    workspace = _ledger_workspace()
    if workspace is None:
        raise CloudResearchUnavailable("Authenticated research workspace is unavailable.")
    owner = workspace.workspace_id
    try:
        with _connect() as db:
            candidates = db.execute(
                "SELECT session_id,project_id,project_relpath,status,process_epoch FROM jobs WHERE "
                "workspace_id=? AND job_kind='research' "
                "AND status IN ('queued','running','stopping') AND process_epoch<>?",
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
        is_shared = isinstance(relative, str) and relative.startswith("@shared/")
        raw_relative = relative[len("@shared/") :] if is_shared else relative
        relative_path = Path(raw_relative) if isinstance(raw_relative, str) else Path("/")
        if (
            not isinstance(raw_relative, str)
            or not raw_relative
            or relative_path.is_absolute()
            or ".." in relative_path.parts
        ):
            continue
        base = root.parent if is_shared else root
        if is_shared:
            # Background cross-workspace recovery cannot impersonate a creator.
            # A verified, still-authorized collaborator may safely recover
            # their own durable Session on reconnect.
            owner_name = relative_path.parts[0] if relative_path.parts else ""
            if (
                (not ledger_only_foreign and cloud_auth.current_principal() is None)
                or len(relative_path.parts) < 2
                or len(owner_name) != 32
                or any(char not in "0123456789abcdef" for char in owner_name)
            ):
                continue
        lexical_project = base
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
            if not project.is_relative_to(base):
                continue
            if ledger_only_foreign:
                # Cross-account maintenance is ledger-only even for a private
                # project owned by another workspace.
                _reconcile_foreign_job(candidate, project, owner)
                continue
            if is_shared and not project_collaboration.authorized_shared_path(project):
                continue
            bundle_project = project.suffix == ".json" and project.is_file()
            if not bundle_project:
                if not project.is_dir():
                    continue
                project_document = project / "project.json"
                session_directory = project / "research-sessions"
                if (
                    project_document.is_symlink()
                    or not project_document.is_file()
                    or session_directory.is_symlink()
                    or (session_directory.exists() and not session_directory.is_dir())
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
                if bundle_project:
                    # A single-file project stores sessions as JSON bundle
                    # members. Read under the same admission lock as _save so
                    # missing members are proof of an unpublished request.
                    from sigma.project_bundle import read_bundle

                    members = read_bundle(str(project))["files"]
                    has_session = f"research-sessions/{session_id}.json" in members
                else:
                    session_record = project / "research-sessions" / f"{session_id}.json"
                    has_session = session_record.exists() or session_record.is_symlink()
                if candidate["status"] in {"running", "stopping"}:
                    # Even an unpublished/missing session record can belong to
                    # a live worker. Never free its slot while its OS lock is held.
                    lock_path = research_sessions._worker_lock_path(str(project), session_id)
                    try:
                        fd = os.open(
                            lock_path,
                            os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0),
                            0o600,
                        )
                    except OSError:
                        continue
                    try:
                        try:
                            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                        except BlockingIOError:
                            continue
                        else:
                            fcntl.flock(fd, fcntl.LOCK_UN)
                    finally:
                        os.close(fd)
                    if has_session:
                        try:
                            saved = research_sessions._read(str(project), session_id)
                        except (OSError, ValueError, ProjectError):
                            continue
                        research_sessions._recover(saved)
                        if saved.get("status") == "running":
                            continue
                        if saved.get("status") in {"ended", "completed", "failed", "stopped"}:
                            recovered_state = "terminal"
                        elif saved.get("status") == "paused":
                            recovered_state = "paused"
                        else:
                            # _recover handles an abandoned running record and
                            # marks its uncertain calls interrupted. Any other
                            # ambiguous state remains occupied for inspection.
                            if saved.get("status") in {"queued", "running"}:
                                continue
                            recovered_state = "interrupted"
                        with _transaction() as db:
                            db.execute(
                                "UPDATE jobs SET status=?,updated_at=? WHERE session_id=? AND workspace_id=? AND process_epoch=? AND status IN ('queued','running','stopping')",
                                (
                                    recovered_state,
                                    _now(),
                                    session_id,
                                    owner,
                                    candidate["process_epoch"],
                                ),
                            )
                    else:
                        # Keep the job and call ledger as spending history;
                        # recover_job marks uncertain reservations unknown.
                        recover_job(session_id, expected_epoch=candidate["process_epoch"])
                    continue
                if has_session:
                    # A saved queued Session may conceal a provider attempt.
                    # Do not reclassify legacy "running" snapshots with no
                    # in-flight step or reserved call during unrelated scans.
                    # They cannot be auto-dispatched and remain recoverable
                    # on their creator's next explicit read.
                    try:
                        saved = research_sessions._read(str(project), session_id)
                        in_flight = any(
                            isinstance(step, dict) and step.get("status") == "running"
                            for step in saved.get("steps", [])
                        )
                        if (
                            saved.get("status") == "queued"
                            or in_flight
                            or has_reserved_calls(session_id)
                        ):
                            research_sessions._recover(saved)
                    except (OSError, ValueError, ProjectError):
                        pass  # Keep uncertain accepted work fail-closed.
                    continue
                # The admission lock proves no publisher is concurrently
                # writing this record; also require the worker OS fence.
                with (
                    research_sessions._idle_worker_lock(str(project), session_id),
                    _transaction() as db,
                ):
                    current = db.execute(
                        "SELECT workspace_id,status,project_id,project_relpath,process_epoch "
                        "FROM jobs WHERE session_id=?",
                        (session_id,),
                    ).fetchone()
                    if (
                        not current
                        or current["workspace_id"] != owner
                        or current["status"] != "queued"
                        or current["project_id"] != candidate["project_id"]
                        or current["project_relpath"] != relative
                        or current["process_epoch"] != candidate["process_epoch"]
                        or current["process_epoch"] == _PROCESS_EPOCH
                    ):
                        continue
                    has_call = db.execute(
                        "SELECT 1 FROM calls WHERE session_id=? LIMIT 1", (session_id,)
                    ).fetchone()
                    if has_call:
                        # No published Session exists, but billing history
                        # remains held. Retire the orphaned queue slot.
                        stamp = _now()
                        db.execute(
                            "UPDATE jobs SET status='interrupted',updated_at=? "
                            "WHERE session_id=? AND workspace_id=? AND status='queued' "
                            "AND process_epoch=?",
                            (stamp, session_id, owner, candidate["process_epoch"]),
                        )
                        if db.execute("SELECT changes()").fetchone()[0] != 1:
                            continue
                        db.execute(
                            "UPDATE calls SET status='unknown',updated_at=? "
                            "WHERE session_id=? AND workspace_id=? AND status='reserved'",
                            (stamp, session_id, owner),
                        )
                        continue
                    db.execute(
                        "DELETE FROM jobs WHERE session_id=? AND workspace_id=? AND status='queued' "
                        "AND process_epoch=?",
                        (session_id, owner, candidate["process_epoch"]),
                    )
                    if db.execute("SELECT changes()").fetchone()[0] == 1:
                        removed.append(session_id)
        except (OSError, RuntimeError, ValueError, sqlite3.Error, ProjectError):
            # Recovery is conservative: inability to prove absence keeps the row.
            continue
    return removed


def reconcile_all_orphaned_jobs() -> None:
    """Recover old research workers across workspaces before new admission.

    Reuse the existing per-workspace recovery and OS worker locks. An active
    request only triggers maintenance; it cannot choose another workspace or
    receive that workspace's records. Unknown owners fail closed.
    """
    current = _ledger_workspace()
    if current is None:
        raise CloudResearchUnavailable("Authenticated research workspace is unavailable.")
    if not cloud_workspaces.enabled():
        # Local sponsored operation is not partitioned into cloud workspace
        # directories. Preserve its original single-workspace recovery path.
        reconcile_orphaned_jobs()
        return
    try:
        parent = current.path.parent.resolve(strict=True)
        with _connect() as db:
            owners = [
                row["workspace_id"]
                for row in db.execute(
                    "SELECT DISTINCT workspace_id FROM jobs "
                    "WHERE job_kind='research' AND status IN ('queued','running','stopping') "
                    "AND process_epoch<>?",
                    (_PROCESS_EPOCH,),
                ).fetchall()
            ]
    except (OSError, sqlite3.Error) as exc:
        raise CloudResearchUnavailable("Research worker recovery is unavailable.") from exc

    for owner in owners:
        if (
            not isinstance(owner, str)
            or len(owner) != 32
            or any(character not in "0123456789abcdef" for character in owner)
        ):
            continue
        owner_path = parent / owner
        try:
            info = owner_path.lstat()
            if (
                not stat.S_ISDIR(info.st_mode)
                or owner_path.is_symlink()
                or info.st_uid != os.geteuid()
                or info.st_mode & 0o077
            ):
                continue
            resolved = owner_path.resolve(strict=True)
            if resolved.parent != parent:
                continue
        except (OSError, RuntimeError, ValueError):
            continue
        if owner == current.workspace_id:
            reconcile_orphaned_jobs()
            continue
        # Only the server's durable ledger supplies owner IDs. Use a tightly
        # scoped internal binding so existing recovery cannot cross owner roots.
        recovery = cloud_workspaces.Workspace(owner, "", resolved)
        token = cloud_workspaces.bind_workspace(recovery)
        try:
            # The triggering user is not this creator. Only worker/ledger
            # maintenance is allowed for a foreign shared project.
            reconcile_orphaned_jobs(ledger_only_foreign=True)
        finally:
            cloud_workspaces.reset(token)


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


def recover_job(session_id: str, *, expected_epoch: str | None = None) -> None:
    """Reclaim a dead slot without changing a newer worker's ownership.

    Callers must first prove the OS worker lock is free. When reconciliation
    began with a prior-epoch snapshot, an epoch mismatch leaves both the slot
    and its in-flight billing reservations untouched.
    """
    owner = _workspace_id()
    try:
        with _transaction() as db:
            row = db.execute(
                "SELECT workspace_id,process_epoch FROM jobs WHERE session_id=?",
                (session_id,),
            ).fetchone()
            if (
                not row
                or row["workspace_id"] != owner
                or (expected_epoch is not None and row["process_epoch"] != expected_epoch)
            ):
                return
            db.execute(
                "UPDATE jobs SET status='interrupted',updated_at=? "
                "WHERE session_id=? AND workspace_id=? AND status IN ('running','stopping')",
                (_now(), session_id, owner),
            )
            db.execute(
                "UPDATE calls SET status='unknown',updated_at=? "
                "WHERE session_id=? AND workspace_id=? AND status='reserved'",
                (_now(), session_id, owner),
            )
    except sqlite3.Error as exc:
        raise CloudResearchUnavailable("Cloud research ledger is unavailable.") from exc


def reserve_call(
    session_id: str,
    call_id: str,
    amount_usd: float,
    token_reservation: int,
    *,
    maximum_liability_usd: float | None = None,
) -> None:
    """Write a conservative cost reservation before making provider I/O."""
    owner = _workspace_id()
    global_ceiling = _spend_ceiling_decimal()
    user_ceiling = _effective_user_spend_ceiling_decimal()
    global_ceiling_units = _ceiling_units(global_ceiling)
    user_ceiling_units = _ceiling_units(user_ceiling)
    unlimited_admin = _admin_has_unlimited_spend()
    global_exempt = _local_default_admin_global_exempt()
    amount_units = _usd_units(amount_usd)
    liability_units = _usd_units(
        amount_usd if maximum_liability_usd is None else maximum_liability_usd
    )
    if liability_units < amount_units:
        raise CloudResearchUnavailable("Provider liability cannot be below estimated usage.")
    reserved_amount = amount_units / USD_UNITS
    token_budget = _positive_int("SIGMA_CLOUD_USER_TOKEN_BUDGET", 2_000_000)
    if amount_units <= 0 or (not global_exempt and liability_units > global_ceiling_units):
        raise CloudResearchUnavailable(
            "The next provider call cannot be reserved within the global spend ceiling."
        )
    if type(token_reservation) is not int or token_reservation <= 0:
        raise CloudResearchUnavailable("Cloud provider token reservation is invalid.")
    if not unlimited_admin and token_reservation > token_budget:
        raise CloudResearchUnavailable("The next provider call exceeds the per-user token budget.")
    try:
        with _transaction() as db:
            job = db.execute(
                "SELECT workspace_id,status,process_epoch FROM jobs WHERE session_id=?",
                (session_id,),
            ).fetchone()
            if (
                not job
                or job["workspace_id"] != owner
                or job["status"] != "running"
                or job["process_epoch"] != _PROCESS_EPOCH
            ):
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
            used_units = _global_call_amount_units(db)
            if not global_exempt and used_units + liability_units > global_ceiling_units:
                remaining_units = max(0, global_ceiling_units - used_units)
                requirement = (
                    f"next call requires ${amount_units / USD_UNITS:.4f}"
                    if liability_units == amount_units
                    else f"next call may require up to ${liability_units / USD_UNITS:.4f}"
                )
                raise CloudResearchUnavailable(
                    f"{_global_ceiling_failure_message()} "
                    f"Remaining global capacity: ${remaining_units / USD_UNITS:.4f}; "
                    f"{requirement}. No provider call was made."
                )
            user_used_units = _user_call_amount_units(db, owner)
            if not unlimited_admin and user_used_units + amount_units > user_ceiling_units:
                raise CloudResearchUnavailable(
                    "Your cumulative cloud research allowance has been reached; saved research remains available."
                )
            user_tokens = _user_call_tokens(db, owner)
            if not unlimited_admin and user_tokens + token_reservation > token_budget:
                raise CloudResearchUnavailable(
                    "The per-user research token budget has been reached."
                )
            now = _now()
            # Explicit column names keep reservations compatible with
            # previously migrated ledgers that may have extra columns.
            db.execute(
                "INSERT INTO calls "
                "(call_id,session_id,workspace_id,amount_usd,status,"
                "token_reservation,input_tokens,output_tokens,created_at,"
                "updated_at,maximum_liability_usd,global_cap_exempt) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    call_id,
                    session_id,
                    owner,
                    reserved_amount,
                    "reserved",
                    token_reservation,
                    None,
                    None,
                    now,
                    now,
                    liability_units / USD_UNITS,
                    int(global_exempt),
                ),
            )
    except sqlite3.Error as exc:
        # A storage/schema failure is not an exhausted allowance. Preserve
        # fail-closed admission and surface a bounded diagnostic category.
        sqlite_code = getattr(exc, "sqlite_errorname", "SQLITE_ERROR")
        raise CloudResearchUnavailable(
            f"Cloud research ledger reservation failed ({sqlite_code}). "
            "No provider call was dispatched; inspect backend SQLite diagnostics."
        ) from exc


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
    if estimated_cost_usd is not None:
        _usd_units(estimated_cost_usd)
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


def mark_call_provider_rejected(session_id: str, call_id: str) -> None:
    """Release reservations after an explicit provider rejection (HTTP 429).

    A received quota rejection is not an unknown in-flight attempt: the provider
    rejected it before inference, so it must not consume the user's allowance.
    Keep the call row as an auditable zero-cost usage estimate.
    """
    owner = _workspace_id()
    try:
        with _transaction() as db:
            row = db.execute("SELECT * FROM calls WHERE call_id=?", (call_id,)).fetchone()
            if not row or row["session_id"] != session_id or row["workspace_id"] != owner:
                raise CloudResearchUnavailable("Provider attempt is unavailable.")
            db.execute(
                "UPDATE calls SET amount_usd=0,status='usage_estimated',token_reservation=0,input_tokens=NULL,output_tokens=NULL,updated_at=? WHERE call_id=?",
                (_now(), call_id),
            )
    except sqlite3.Error as exc:
        raise CloudResearchUnavailable("Cloud research ledger is unavailable.") from exc


def snapshot() -> dict[str, Any]:
    """Return only the current principal's job, token, and spending summary."""
    owner = _workspace_id()
    allowance = _effective_user_spend_ceiling_decimal()
    allowance_units = _ceiling_units(allowance)
    unlimited_admin = _admin_has_unlimited_spend()
    global_exempt = _local_default_admin_global_exempt()
    try:
        with _connect() as db:
            own = db.execute(
                "SELECT status,COUNT(*) AS count FROM jobs WHERE workspace_id=? GROUP BY status",
                (owner,),
            ).fetchall()
            total_units = _user_call_amount_units(db, owner)
            estimated_units = _user_call_amount_units(db, owner, "usage_estimated")
            held_units = _user_call_amount_units(db, owner, "reserved") + _user_call_amount_units(
                db, owner, "unknown"
            )
            window = db.execute(
                "SELECT reset_at FROM allowance_windows WHERE workspace_id=?", (owner,)
            ).fetchone()
            unknown_query = "SELECT COUNT(*) FROM calls WHERE workspace_id=? AND status='unknown'"
            unknown_parameters: tuple[Any, ...] = (owner,)
            if window:
                unknown_query += " AND created_at>=?"
                unknown_parameters = (owner, window["reset_at"])
            unknown = db.execute(unknown_query, unknown_parameters).fetchone()[0]
            tokens = _user_call_tokens(db, owner)
            to_usd = lambda units: round(units / USD_UNITS, 9)
            # An individual can have remaining allowance after the shared
            # inference ceiling is exhausted. Expose aggregate *capacity*
            # only, never another account's usage or identity, so the UI
            # cannot suggest that research is fundable when it is not.
            global_remaining_units = max(
                0, _ceiling_units(_spend_ceiling_decimal()) - _global_call_amount_units(db)
            )
            return {
                "jobs": {row["status"]: row["count"] for row in own},
                "global_remaining_usd": to_usd(global_remaining_units),
                "global_ceiling_usd": float(_spend_ceiling_decimal()),
                "global_spend_period": _global_spend_period(),
                "global_cap_exempt": global_exempt,
                "global_reset_at": _next_global_reset_at(),
                "allowance_usd": float(allowance),
                "estimated_usage_usd": to_usd(estimated_units),
                "held_usd": to_usd(held_units),
                "reserved_and_estimated_usd": to_usd(total_units),
                "remaining_usd": (
                    None
                    if global_exempt
                    else to_usd(
                        global_remaining_units
                        if unlimited_admin
                        else max(0, allowance_units - total_units)
                    )
                ),
                # Kept for existing audit consumers; new clients use the explicit name.
                "user_reserved_and_estimated_usd": to_usd(total_units),
                "user_reserved_or_observed_tokens": int(tokens),
                "unknown_provider_attempts": unknown,
            }
    except sqlite3.Error as exc:
        raise CloudResearchUnavailable("Cloud research ledger is unavailable.") from exc


def admin_workspace_spending(
    workspace_id: str, allowance: float | None
) -> dict[str, float | int | None]:
    """Admin-only aggregate for an identity resolved from a verified session."""
    if not isinstance(workspace_id, str) or len(workspace_id) != 32:
        raise CloudResearchUnavailable("Workspace spending identity is invalid.")
    allowance_units = _ceiling_units(Decimal(str(allowance))) if allowance is not None else None
    try:
        with _connect() as db:
            total = _user_call_amount_units(db, workspace_id)
            estimated = _user_call_amount_units(db, workspace_id, "usage_estimated")
            held = _user_call_amount_units(db, workspace_id, "reserved") + _user_call_amount_units(
                db, workspace_id, "unknown"
            )
            window = db.execute(
                "SELECT reset_at FROM allowance_windows WHERE workspace_id=?", (workspace_id,)
            ).fetchone()
            reload_query = "SELECT 1 FROM calls WHERE workspace_id=? AND amount_usd>0"
            reload_parameters: tuple[Any, ...] = (workspace_id,)
            if window:
                reload_query += " AND created_at>=?"
                reload_parameters = (workspace_id, window["reset_at"])
            reload_eligible = bool(
                db.execute(reload_query + " LIMIT 1", reload_parameters).fetchone()
            )
            return {
                "estimated_usage_usd": round(estimated / USD_UNITS, 9),
                "held_usd": round(held / USD_UNITS, 9),
                "remaining_usd": round(max(0, allowance_units - total) / USD_UNITS, 9)
                if allowance_units is not None
                else None,
                "reserved_and_estimated_usd": round(total / USD_UNITS, 9),
                "reload_eligible": reload_eligible,
            }
    except sqlite3.Error as exc:
        raise CloudResearchUnavailable("Cloud research ledger is unavailable.") from exc
