"""User-scoped progress email preferences and idempotent delivery.

Notifications are advisory: delivery must never change a research or paper
outcome. No address or message body is persisted in the dispatch ledger.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import re
import sqlite3
from email.message import EmailMessage
from typing import Literal
from urllib.parse import urlencode

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


def _configured() -> bool:
    # SMTP_HOST has a default in the shared transport; it is optional even
    # when SMTP_USERNAME and SMTP_PASSWORD are configured correctly.
    if cloud_auth.email_env("GMAIL_TOKEN_FILE"):
        return True
    if not cloud_auth.email_env("SMTP_USERNAME"):
        return False
    try:
        return bool(cloud_auth.email_secret("SMTP_PASSWORD"))
    except (OSError, RuntimeError, ValueError):
        return False


def eligible_session_event(record: dict) -> Event | None:
    """Report only settled outcomes and pauses requiring user intervention."""
    status = record.get("status")
    if status in {"completed", "ended"}:
        return "session_finished"
    if status == "failed":
        return "session_failed"
    if status == "paused":
        # The explicit Pause control is not an unexpected interruption.
        # Automatically paused sessions cannot continue without intervention.
        message = str(record.get("message") or "")
        if message.startswith(("Paused by user.", "Simulated research paused.")):
            return None
        return "session_paused"
    return None


def preference(principal: cloud_auth.Principal | None) -> dict:
    """Return an authenticated identity's setting, independent of project."""
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


def update_preference(principal: cloud_auth.Principal, enabled: bool) -> dict:
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
            """INSERT INTO progress_email_preferences(subject,enabled)
               VALUES (?,?) ON CONFLICT(subject) DO UPDATE SET enabled=excluded.enabled""",
            (principal.subject, int(enabled)),
        )
    return preference(principal)


_COPY = {
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


def message_for(event: Event, project: str, number: int, link: str) -> EmailMessage:
    if event not in _COPY or type(number) is not int or number < 1:
        raise ValueError("Unsupported notification.")
    if not link.startswith(("https://", "http://localhost:", "http://127.0.0.1:")):
        raise ValueError("Invalid notification link.")
    clean = re.sub(r"[\x00-\x1f\x7f]+", " ", project).strip()[:140] or "Untitled project"
    subject, body, action = _COPY[event]
    message = EmailMessage()
    message["Subject"] = f"SIGMA: {subject.format(number=number)} · {clean}"
    message.set_content(f"{body.format(number=number)}\n\n{action}: {link}\n")
    return message


def deep_link(
    origin: str, path: str, *, session_id: str | None = None, paper_id: str | None = None
) -> str:
    """Use the configured Google auth origin, never an untrusted Host header."""
    from urllib.parse import urlsplit

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
    params: dict[str, str] = {"path": path}
    if session_id:
        params["reveal_session"] = session_id
    elif paper_id:
        params["reveal_paper"] = paper_id
    return f"{origin.rstrip('/')}/project?{urlencode(params)}"


def dispatch(
    principal: cloud_auth.Principal | None,
    event: Event,
    *,
    event_id: str,
    project_title: str,
    number: int,
    path: str,
    session_id: str | None = None,
    paper_id: str | None = None,
) -> None:
    """Exactly one send attempt per event; ambiguous mail results never retry.

    Invoke in a separate thread from a completed generation stage. Storage and
    network errors are logged without breaking the successful research write.
    """
    if principal is None or principal.role == "guest" or not event_id:
        return
    try:
        cfg = cloud_auth.config()
        if not cfg.origin or not preference(principal)["enabled"]:
            return
        # Bind to the verified principal from the job, not the latest browser.
        recipient = cloud_auth._normalize_email(principal.email)
        link = deep_link(cfg.origin, path, session_id=session_id, paper_id=paper_id)
        message = message_for(event, project_title, number, link)
        digest = hashlib.sha256(event_id.encode("utf-8")).hexdigest()
        # Reserve before network I/O, preventing duplicates even on uncertain
        # API or SMTP responses and across multiple app processes.
        with cloud_auth._db(cfg) as db:
            cursor = db.execute(
                """INSERT OR IGNORE INTO progress_email_dispatches(subject,event_hash,state)
                   VALUES (?,?, 'sending')""",
                (principal.subject, digest),
            )
            if cursor.rowcount != 1:
                return
        try:
            from sigma.mail_transport import send_message

            send_message(message, recipients=[recipient])
        except Exception as exc:  # noqa: BLE001
            # Delivery could have succeeded before the connection failed.
            with cloud_auth._db(cfg) as db:
                db.execute(
                    "UPDATE progress_email_dispatches SET state='unknown' "
                    "WHERE subject=? AND event_hash=?",
                    (principal.subject, digest),
                )
            _LOG.warning(
                "progress_email.delivery_unknown event=%s error_type=%s",
                event,
                type(exc).__name__,
            )
            return
        with cloud_auth._db(cfg) as db:
            db.execute(
                "UPDATE progress_email_dispatches SET state='sent' "
                "WHERE subject=? AND event_hash=?",
                (principal.subject, digest),
            )
    except Exception as exc:  # noqa: BLE001
        _LOG.warning(
            "progress_email.dispatch_unavailable event=%s error_type=%s",
            event,
            type(exc).__name__,
        )


def schedule(
    principal: cloud_auth.Principal | None,
    event: Event,
    *,
    event_id: str,
    project_title: str,
    number: int,
    path: str,
    session_id: str | None = None,
    paper_id: str | None = None,
) -> None:
    """Detached nonblocking delivery: never hold up provider execution or persistence."""
    if principal is None:
        return
    try:
        task = asyncio.create_task(
            asyncio.to_thread(
                dispatch,
                principal,
                event,
                event_id=event_id,
                project_title=project_title,
                number=number,
                path=path,
                session_id=session_id,
                paper_id=paper_id,
            )
        )
        task.add_done_callback(lambda done: None if done.cancelled() else done.exception())
    except RuntimeError:
        # No running event loop: no background worker is available.
        return
