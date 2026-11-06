"""Account-scoped progress emails with persistent ownership and an outbox.

An email notification never changes the outcome of research or paper generation.
SMTP known-no-delivery failures are retried; uncertain deliveries are not
blindly replayed, since SMTP/Gmail provide no idempotency token.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import re
import sqlite3
import time
from email.message import EmailMessage
from typing import Literal
from urllib.parse import urlencode, urlsplit

from sigma import cloud_auth

Event = Literal[
    "session_finished",
    "session_failed",
    "session_paused",
    "paper_finished",
    "paper_failed",
    "paper_paused",
]
_LOG = logging.getLogger("sigma.lifecycle")
_MAX_ATTEMPTS = 3
_PAUSE_SETTLE_SECONDS = 60
_PUMP: asyncio.Task[None] | None = None


def _configured() -> bool:
    # Progress notifications use the existing Gmail API sender exclusively.
    # Do not silently fall back to SMTP when its credentials happen to exist.
    return bool(cloud_auth.email_env("GMAIL_TOKEN_FILE"))


def eligible_session_event(record: dict) -> Event | None:
    """Only settled outcomes and unexpected pauses should cause email."""
    status = record.get("status")
    if status in {"completed", "ended"}:
        return "session_finished"
    if status == "failed":
        return "session_failed"
    if status == "paused":
        message = str(record.get("message") or "")
        if message.startswith(("Paused by user.", "Simulated research paused.")):
            return None
        return "session_paused"
    return None


def preference(principal: cloud_auth.Principal | None) -> dict[str, bool]:
    cfg = cloud_auth.config()
    if principal is None or principal.role == "guest" or not cfg.enabled or cfg.error:
        return {"enabled": False, "available": False}
    try:
        cloud_auth._normalize_email(principal.email)
        with cloud_auth._db(cfg) as db:
            row = db.execute(
                "SELECT enabled FROM progress_email_preferences WHERE subject=?",
                (principal.subject,),
            ).fetchone()
        return {"enabled": bool(row["enabled"]) if row else False, "available": _configured()}
    except (ValueError, OSError, RuntimeError, sqlite3.Error) as exc:
        _LOG.warning("progress_email.preference_unavailable error_type=%s", type(exc).__name__)
        return {"enabled": False, "available": False}


def update_preference(principal: cloud_auth.Principal, enabled: bool) -> dict[str, bool]:
    if type(enabled) is not bool:
        raise ValueError("Email preference must be a boolean.")
    cfg = cloud_auth.config()
    if principal.role == "guest" or not cfg.enabled or cfg.error:
        raise ValueError("Sign in with Google to enable progress emails.")
    cloud_auth._normalize_email(principal.email)
    if enabled and not _configured():
        raise ValueError("Progress email delivery is not configured.")
    with cloud_auth._db(cfg) as db:
        db.execute(
            "INSERT INTO progress_email_preferences(subject,enabled) VALUES (?,?) "
            "ON CONFLICT(subject) DO UPDATE SET enabled=excluded.enabled",
            (principal.subject, int(enabled)),
        )
    return preference(principal)


def bind_job(principal: cloud_auth.Principal | None, job_id: str) -> None:
    """Freeze the initiating verified account, not the eventual viewer."""
    if principal is None or principal.role == "guest" or not job_id:
        return
    try:
        cfg = cloud_auth.config()
        if not cfg.enabled or cfg.error:
            return
        cloud_auth._normalize_email(principal.email)
        with cloud_auth._db(cfg) as db:
            # Never reassign an existing job to a different account on Resume.
            db.execute(
                "INSERT OR IGNORE INTO progress_email_jobs(job_id,subject) VALUES (?,?)",
                (job_id, principal.subject),
            )
    except (ValueError, OSError, RuntimeError, sqlite3.Error) as exc:
        _LOG.warning("progress_email.owner_unavailable error_type=%s", type(exc).__name__)


_COPY: dict[Event, tuple[str, str, str]] = {
    "session_finished": (
        "Session {number} completed",
        (
            "Research session {number} completed successfully.\n"
            "Review the findings, outcome, and remaining questions."
        ),
        "View session",
    ),
    "session_failed": (
        "Session {number} failed",
        (
            "Research session {number} stopped because of an error.\n"
            "Open the session to review the problem and any saved progress."
        ),
        "View session",
    ),
    "session_paused": (
        "Session {number} paused",
        (
            "Research session {number} was paused because SIGMA could not continue automatically.\n"
            "Your research progress has been preserved. Open the session to review its status."
        ),
        "View session",
    ),
    "paper_finished": (
        "Paper {number} generated",
        "Paper {number} has been generated successfully.\nYour paper is ready to review.",
        "View paper",
    ),
    "paper_failed": (
        "Paper {number} failed",
        (
            "Paper generation stopped because of an error.\n"
            "Open the project to review the problem and any saved work."
        ),
        "View paper",
    ),
    "paper_paused": (
        "Paper {number} paused",
        (
            "Paper generation has been paused.\nYour completed work has been preserved. "
            "Open the paper to review its status and resume when possible."
        ),
        "View paper",
    ),
}


def message_for(
    event: Event, project: str, number: int, link: str, *, incomplete: bool = False
) -> EmailMessage:
    if event not in _COPY or type(number) is not int or number < 1:
        raise ValueError("Unsupported notification.")
    if not link.startswith(("https://", "http://localhost:", "http://127.0.0.1:")):
        raise ValueError("Invalid notification link.")
    clean = re.sub(r"[\x00-\x1f\x7f]+", " ", project).strip()[:140] or "Untitled project"
    subject, body, action = _COPY[event]
    if event == "session_finished" and incomplete:
        subject = "Session {number} finished"
        body = (
            "Research session {number} stopped at its configured limit or conclusion.\n"
            "Review the outcome, saved findings, and remaining questions."
        )
    message = EmailMessage()
    message["Subject"] = f"SIGMA: {subject.format(number=number)} · {clean}"
    message.set_content(f"{body.format(number=number)}\n\n{action}: {link}\n")
    return message


def deep_link(
    origin: str, path: str, *, session_id: str | None = None, paper_id: str | None = None
) -> str:
    """Construct a local or hosted link from a trusted configured origin."""
    parsed = urlsplit(origin)
    if parsed.scheme != "https" and not (
        parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1"}
    ):
        raise ValueError("Notification origin is invalid.")
    if (
        not origin
        or parsed.path not in ("", "/")
        or parsed.query
        or parsed.fragment
        or parsed.username
    ):
        raise ValueError("Notification origin is invalid.")
    params = {"path": path}
    if session_id:
        params["reveal_session"] = session_id
    elif paper_id:
        params["reveal_paper"] = paper_id
    return f"{origin.rstrip('/')}/project?{urlencode(params)}"


def enqueue(
    job_id: str,
    event: Event,
    *,
    event_id: str,
    project_title: str,
    number: int,
    path: str,
    session_id: str | None = None,
    paper_id: str | None = None,
    incomplete: bool = False,
) -> None:
    """Persist an event against its original owner, independently of the browser."""
    if not job_id or not event_id:
        return
    try:
        cfg = cloud_auth.config()
        if not cfg.enabled or cfg.error or not cfg.origin:
            return
        # Validate the final link before inserting work into the queue.
        deep_link(cfg.origin, path, session_id=session_id, paper_id=paper_id)
        digest = hashlib.sha256(event_id.encode("utf-8")).hexdigest()
        with cloud_auth._db(cfg) as db:
            db.execute(
                """INSERT OR IGNORE INTO progress_email_dispatches
                (subject,event_hash,state,event,project_title,number,path,session_id,
                 paper_id,incomplete,attempts,retry_after,job_id)
                SELECT jobs.subject,?,'pending',?,?,?,?,?,?,?,0,?,?
                FROM progress_email_jobs AS jobs
                JOIN progress_email_preferences AS prefs ON prefs.subject=jobs.subject
                WHERE jobs.job_id=? AND prefs.enabled=1""",
                (
                    digest,
                    event,
                    project_title[:160],
                    number,
                    path,
                    session_id,
                    paper_id,
                    int(incomplete),
                    int(time.time()) + _PAUSE_SETTLE_SECONDS if event.endswith("_paused") else 0,
                    job_id,
                    job_id,
                ),
            )
    except (ValueError, OSError, RuntimeError, sqlite3.Error) as exc:
        _LOG.warning("progress_email.enqueue_unavailable error_type=%s", type(exc).__name__)


def _pause_still_actionable(row: sqlite3.Row) -> bool:
    """Suppress a queued pause if its exact job already resumed or settled.

    Missing/unreadable state is not proof of recovery; prefer delivering a
    potentially important notification over silently losing it.
    """
    try:
        if row["event"] == "session_paused" and row["session_id"]:
            from sigma import research_sessions

            session = research_sessions._read(row["path"], row["session_id"])
            return eligible_session_event(session) == "session_paused"
        if row["event"] == "paper_paused" and row["paper_id"]:
            from sigma import papers

            progress = papers._read_progress_status(row["path"])
            if progress is None:
                return True
            return (
                progress.get("status") == "paused"
                and f"paper:{progress.get('run_id')}" == row["job_id"]
            )
    except Exception as exc:  # noqa: BLE001 - missing state must not drop an important email
        _LOG.warning("progress_email.pause_state_unavailable error_type=%s", type(exc).__name__)
    return True


def _deliver_pending() -> None:
    """Claim one pending delivery atomically; preserve ambiguous outcomes."""
    cfg = cloud_auth.config()
    if not cfg.enabled or cfg.error or not cfg.origin:
        return
    for _ in range(10):
        try:
            with cloud_auth._db(cfg) as db:
                now = int(time.time())
                row = db.execute(
                    """SELECT d.*,u.email AS verified_email,u.access_active,u.role,
                       p.enabled AS opted_in
                       FROM progress_email_dispatches d
                       LEFT JOIN user_state u ON u.subject=d.subject
                       LEFT JOIN progress_email_preferences p ON p.subject=d.subject
                       WHERE d.state='pending' AND d.retry_after<=?
                       ORDER BY d.rowid LIMIT 1""",
                    (now,),
                ).fetchone()
                if row is None:
                    return
                changed = db.execute(
                    """UPDATE progress_email_dispatches
                       SET state='sending',attempts=attempts+1
                       WHERE subject=? AND event_hash=? AND state='pending'""",
                    (row["subject"], row["event_hash"]),
                ).rowcount
            if changed != 1:
                continue
            key = (row["subject"], row["event_hash"])
            if not row["access_active"] or not row["opted_in"] or row["role"] == "guest":
                state = "cancelled"
            elif row["event"] in {"session_paused", "paper_paused"} and not _pause_still_actionable(row):
                state = "cancelled"
            else:
                state = "unknown"
                try:
                    from sigma.mail_transport import send_message

                    recipient = cloud_auth._normalize_email(row["verified_email"])
                    link = deep_link(
                        cfg.origin,
                        row["path"],
                        session_id=row["session_id"],
                        paper_id=row["paper_id"],
                    )
                    message = message_for(
                        row["event"],
                        row["project_title"],
                        row["number"],
                        link,
                        incomplete=bool(row["incomplete"]),
                    )
                    send_message(message, recipients=[recipient])
                    state = "sent"
                except cloud_auth.SMTPDeliveryError as exc:
                    if exc.state == "failed":
                        state = "pending" if row["attempts"] + 1 < _MAX_ATTEMPTS else "failed"
                    _LOG.warning(
                        "progress_email.transport_failed state=%s error_type=%s",
                        exc.state,
                        type(exc).__name__,
                    )
                except (OSError, RuntimeError, ValueError, KeyError, TypeError) as exc:
                    # Gmail failures can be ambiguous even when they look like HTTP errors.
                    _LOG.warning(
                        "progress_email.transport_unknown error_type=%s", type(exc).__name__
                    )
            with cloud_auth._db(cfg) as db:
                db.execute(
                    """UPDATE progress_email_dispatches SET state=?,retry_after=?
                       WHERE subject=? AND event_hash=? AND state='sending'""",
                    (
                        state,
                        now + 60 * (2 ** row["attempts"]) if state == "pending" else 0,
                        *key,
                    ),
                )
        except (OSError, RuntimeError, sqlite3.Error) as exc:
            _LOG.warning("progress_email.outbox_unavailable error_type=%s", type(exc).__name__)
            return


async def _run_outbox() -> None:
    while True:
        try:
            await asyncio.to_thread(_deliver_pending)
        except Exception:  # noqa: BLE001 - background email must never crash SIGMA
            _LOG.exception("progress_email.outbox_worker_failed")
        await asyncio.sleep(30)


def start_outbox() -> None:
    """Replay the outbox only when email delivery and authentication are configured."""
    global _PUMP
    if not _configured():
        return
    cfg = cloud_auth.config()
    if not cfg.enabled or cfg.error or cfg.database is None:
        return
    if _PUMP is None or _PUMP.done():
        _PUMP = asyncio.create_task(_run_outbox())


def stop_outbox() -> None:
    global _PUMP
    if _PUMP is not None:
        _PUMP.cancel()
        _PUMP = None


def schedule(
    job_id: str,
    event: Event,
    *,
    event_id: str,
    project_title: str,
    number: int,
    path: str,
    session_id: str | None = None,
    paper_id: str | None = None,
    incomplete: bool = False,
) -> None:
    """Persist the event and kick an asynchronous transport without blocking research."""
    enqueue(
        job_id,
        event,
        event_id=event_id,
        project_title=project_title,
        number=number,
        path=path,
        session_id=session_id,
        paper_id=paper_id,
        incomplete=incomplete,
    )
    try:
        task = asyncio.create_task(asyncio.to_thread(_deliver_pending))
        task.add_done_callback(lambda done: None if done.cancelled() else done.exception())
    except RuntimeError:
        # A worker started without an event loop will be drained on startup.
        return
