"""Durable cloud research admission and inference-spend ledger.

Research state and evidence remain in the existing project session records. This
small service-owned ledger adds cross-project, cross-process admission and
write-ahead cost reservations without creating a second research engine.
"""

from __future__ import annotations

import json
import os
import sqlite3
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
MAX_GLOBAL_SPEND_USD = Decimal("15.00")
MAX_SESSION_SPEND_USD = 0.25
MAX_SESSION_CALLS = 6
MAX_LOCAL_SESSION_CALLS = 30
MAX_SESSION_MINUTES = 15


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

    if cloud_auth.local_sponsored_principal() is not None and not os.environ.get(
        "SIGMA_CLOUD_GLOBAL_SPEND_CEILING_USD"
    ):
        return Decimal(str(MAX_SESSION_SPEND_USD))
    return _money_ceiling(
        "SIGMA_CLOUD_GLOBAL_SPEND_CEILING_USD",
        maximum=MAX_GLOBAL_SPEND_USD,
        message="Cloud research is disabled until a valid global inference-spend ceiling of at most $15 is configured.",
    )


def _user_spend_ceiling_decimal() -> Decimal:
    return _money_ceiling(
        "SIGMA_CLOUD_USER_SPEND_CEILING_USD",
        maximum=MAX_USER_SPEND_USD,
        message="Cloud research is disabled until a valid default per-user inference allowance of at most $15 is configured.",
    )


def _effective_user_spend_ceiling_decimal() -> Decimal:
    from sigma import cloud_auth

    workspace = _ledger_workspace()
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
    if not value.is_finite() or not Decimal("0.01") <= value <= MAX_GLOBAL_SPEND_USD:
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


def _evaluation_queue_limits() -> tuple[int, int, int, int]:
    per_user_running = _positive_int("SIGMA_CLOUD_USER_MAX_CONCURRENT", 1)
    global_running = _positive_int("SIGMA_CLOUD_GLOBAL_MAX_CONCURRENT", 2)
    per_user_queued = _positive_int("SIGMA_CLOUD_USER_MAX_QUEUED", 2)
    global_queued = _positive_int("SIGMA_CLOUD_GLOBAL_MAX_QUEUED", 16)
    if per_user_running > 1 or global_running > 2 or per_user_queued > 2:
        raise CloudResearchUnavailable(
            "Cloud research concurrency and queue limits exceed the external-evaluation policy."
        )
    return per_user_running, global_running, per_user_queued, global_queued


def evaluation_session_limits(limits: dict[str, Any]) -> dict[str, Any]:
    """Apply administrator-controlled hosted inference caps to sponsored work."""
    result = dict(limits)
    # Even legacy project records with a one-call allowance need room for the
    # minimum Investigator/Skeptic pair; cloud limits never exceed the cap.
    calls = min(max(int(result["model_calls"]), 2), MAX_SESSION_CALLS)
    result["model_calls"] = calls
    result["research_rounds"] = min(max(int(result["research_rounds"]), 1), calls // 2)
    result["session_duration_minutes"] = min(
        int(result["session_duration_minutes"]), MAX_SESSION_MINUTES
    )
    # This is sponsored service usage, not user API-key billing. A project-level
    # estimate must never lower or raise the administrator's hosted allowance.
    result["maximum_estimated_cost_usd"] = MAX_SESSION_SPEND_USD
    return result


def local_sponsored_session_limits(limits: dict[str, Any]) -> dict[str, Any]:
    """Bound local sponsored work without applying the hosted six-call cap."""
    result = dict(limits)
    calls = min(max(int(result["model_calls"]), 2), MAX_LOCAL_SESSION_CALLS)
    result["model_calls"] = calls
    result["research_rounds"] = min(max(int(result["research_rounds"]), 1), calls // 2)
    result["session_duration_minutes"] = min(
        int(result["session_duration_minutes"]), MAX_SESSION_MINUTES
    )
    result["maximum_estimated_cost_usd"] = MAX_SESSION_SPEND_USD
    return result


def session_call_ceiling() -> int:
    """Keep the hosted evaluation cap local to hosted workspaces.

    Local sponsored inference still uses the durable per-account spend ledger,
    but its project call limit is governed by the saved project setting.
    """
    return MAX_SESSION_CALLS if cloud_workspaces.enabled() else MAX_LOCAL_SESSION_CALLS


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
    from sigma.cloud_sponsor import inference_provider

    provider = inference_provider()
    if record.get("mode") != provider or provider not in {"api_key", "chatgpt"}:
        raise CloudResearchUnavailable(
            "Cloud research requires the explicitly configured sponsor provider."
        )
    if record.get("maximum_estimated_cost_usd") is None or record.get("cost_status") != "available":
        raise CloudResearchUnavailable(
            "Cloud research requires a per-session cost limit and a model with a reviewed price."
        )
    _spend_ceiling_decimal()
    _user_spend_ceiling_decimal()
    _, _, per_user_queue, global_queue = _evaluation_queue_limits()
    call_limit = record.get("call_limit")
    duration_limit = record.get("duration_limit_minutes")
    maximum_cost = record.get("maximum_estimated_cost_usd")
    call_ceiling = session_call_ceiling()
    if (
        type(call_limit) is not int
        or not 2 <= call_limit <= call_ceiling
        or type(duration_limit) is not int
        or not 1 <= duration_limit <= MAX_SESSION_MINUTES
        or type(maximum_cost) not in {int, float}
        or not isinstance(maximum_cost, (int, float))
        or not 0.01 <= maximum_cost <= MAX_SESSION_SPEND_USD
    ):
        if cloud_workspaces.enabled():
            raise CloudResearchUnavailable(
                "Hosted cloud research sessions are capped at six calls, 15 minutes, and $0.25. Update Project Settings → Limits."
            )
        raise CloudResearchUnavailable(
            "Local sponsored research sessions are capped at 30 calls, 15 minutes, and $0.25. Update Project Settings → Limits."
        )
    workspace = _ledger_workspace()
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
    user_limit, global_limit, _user_queue, _global_queue = _evaluation_queue_limits()
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


def reconcile_orphaned_jobs() -> list[str]:
    """Delete prior-process queued rows proven to have no session or call.

    The project admission lock closes the prepare_job/_save crash window. If a
    publisher is still live, recovery waits and observes its session file. Any
    uncertain path/state or any provider-call row is preserved; age is never
    evidence for releasing a job or spend reservation.
    """
    workspace = _ledger_workspace()
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
    global_ceiling = _spend_ceiling_decimal()
    user_ceiling = _effective_user_spend_ceiling_decimal()
    global_ceiling_units = _ceiling_units(global_ceiling)
    user_ceiling_units = _ceiling_units(user_ceiling)
    amount_units = _usd_units(amount_usd)
    reserved_amount = amount_units / USD_UNITS
    token_budget = _positive_int("SIGMA_CLOUD_USER_TOKEN_BUDGET", 2_000_000)
    if amount_units <= 0 or amount_units > global_ceiling_units:
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
            used_units = _call_amount_units(db, "")
            if used_units + amount_units > global_ceiling_units:
                raise CloudResearchUnavailable(
                    "The global inference-spend ceiling has been reached; saved research remains available."
                )
            user_used_units = _call_amount_units(db, "WHERE workspace_id=?", (owner,))
            if user_used_units + amount_units > user_ceiling_units:
                raise CloudResearchUnavailable(
                    "Your cumulative cloud research allowance has been reached; saved research remains available."
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
                    reserved_amount,
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


def snapshot() -> dict[str, Any]:
    """Return only the current principal's job, token, and spending summary."""
    owner = _workspace_id()
    allowance = _effective_user_spend_ceiling_decimal()
    allowance_units = _ceiling_units(allowance)
    try:
        with _connect() as db:
            own = db.execute(
                "SELECT status,COUNT(*) AS count FROM jobs WHERE workspace_id=? GROUP BY status",
                (owner,),
            ).fetchall()
            total_units = _call_amount_units(db, "WHERE workspace_id=?", (owner,))
            estimated_units = _call_amount_units(
                db, "WHERE workspace_id=? AND status='usage_estimated'", (owner,)
            )
            held_units = _call_amount_units(
                db, "WHERE workspace_id=? AND status IN ('reserved','unknown')", (owner,)
            )
            unknown = db.execute(
                "SELECT COUNT(*) FROM calls WHERE workspace_id=? AND status='unknown'", (owner,)
            ).fetchone()[0]
            tokens = db.execute(
                "SELECT COALESCE(SUM(token_reservation),0) FROM calls WHERE workspace_id=?",
                (owner,),
            ).fetchone()[0]
            to_usd = lambda units: round(units / USD_UNITS, 9)
            return {
                "jobs": {row["status"]: row["count"] for row in own},
                "allowance_usd": float(allowance),
                "estimated_usage_usd": to_usd(estimated_units),
                "held_usd": to_usd(held_units),
                "reserved_and_estimated_usd": to_usd(total_units),
                "remaining_usd": to_usd(max(0, allowance_units - total_units)),
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
            total = _call_amount_units(db, "WHERE workspace_id=?", (workspace_id,))
            estimated = _call_amount_units(
                db, "WHERE workspace_id=? AND status='usage_estimated'", (workspace_id,)
            )
            held = _call_amount_units(
                db, "WHERE workspace_id=? AND status IN ('reserved','unknown')", (workspace_id,)
            )
            return {
                "estimated_usage_usd": round(estimated / USD_UNITS, 9),
                "held_usd": round(held / USD_UNITS, 9),
                "remaining_usd": round(max(0, allowance_units - total) / USD_UNITS, 9)
                if allowance_units is not None
                else None,
                "reserved_and_estimated_usd": round(total / USD_UNITS, 9),
            }
    except sqlite3.Error as exc:
        raise CloudResearchUnavailable("Cloud research ledger is unavailable.") from exc
