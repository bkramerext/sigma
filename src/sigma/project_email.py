"""Importable SIGMA project mail with optional saved-paper attachments.

Only the explicit SMTP configuration on the SIGMA server is used. Saved
papers are intentionally excluded from the importable project attachment:
recipients can resume the research and generate their own papers.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import time
from contextlib import contextmanager
from email.message import EmailMessage
from pathlib import Path
from typing import Literal
from uuid import UUID, uuid4

from sigma import cloud_auth, papers
from sigma.project_bundle import download_bytes, encode
from sigma.projects import ProjectError, inspect_project, project_path

MailMode = Literal["project", "pdf", "pdf_tex"]
MAX_RECIPIENTS = 10
MAX_ATTACHMENT_BYTES = 18 * 1024 * 1024
HOURLY_SEND_LIMIT = 5
DAILY_SEND_LIMIT = 20
DAILY_GLOBAL_LIMIT = 100
DAILY_RECIPIENT_LIMIT = 100
RECORD_TTL_SECONDS = 7 * 24 * 3600
MAX_SEND_ATTEMPTS = 3


class MailRateLimit(RuntimeError):
    """The verified sender or service has exhausted its mail allowance."""


class MailDispatchConflict(RuntimeError):
    """The request has already been processed or has uncertain delivery."""


class MailDeliveryNotSent(RuntimeError):
    """SMTP definitely did not deliver this request; an explicit retry is safe."""


def _delivery_database_path() -> Path:
    from sigma.projects import projects_root

    cfg = cloud_auth.config()
    path = cfg.database if cfg.enabled else projects_root() / ".project-email.sqlite3"
    if path is None:
        raise RuntimeError("Project email delivery storage is unavailable.")
    return path


@contextmanager
def _delivery_connection():
    """A durable, process-shared reservation ledger. Never store recipients or body."""
    path = _delivery_database_path()
    if path is None or path.is_symlink() or not path.parent.is_dir():
        raise RuntimeError("Project email delivery storage is unavailable.")
    if not path.exists():
        try:
            fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_EXCL, 0o600)
            os.close(fd)
        except FileExistsError:
            pass
    if path.is_symlink() or not path.is_file() or path.stat().st_mode & 0o077:
        raise RuntimeError("Project email delivery storage is not private.")
    db = sqlite3.connect(path, timeout=5, isolation_level=None)
    try:
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=5000")
        db.execute("BEGIN IMMEDIATE")
        db.execute(
            """CREATE TABLE IF NOT EXISTS project_email_dispatches (
                sender_hash TEXT NOT NULL,
                request_id TEXT NOT NULL,
                payload_hash TEXT NOT NULL,
                started_at INTEGER NOT NULL,
                recipients INTEGER NOT NULL,
                accepted INTEGER NOT NULL DEFAULT 0,
                attempts INTEGER NOT NULL DEFAULT 1,
                state TEXT NOT NULL CHECK(state IN ('sending','sent','partial','unknown','failed')),
                PRIMARY KEY(sender_hash, request_id)
            )"""
        )
        # Preserve ledgers from earlier development builds of this feature.
        columns = {item["name"] for item in db.execute("PRAGMA table_info(project_email_dispatches)")}
        if "attempts" not in columns:
            db.execute(
                "ALTER TABLE project_email_dispatches ADD COLUMN attempts INTEGER NOT NULL DEFAULT 1"
            )
        yield db
        db.execute("COMMIT")
    except BaseException:
        db.execute("ROLLBACK")
        raise
    finally:
        db.close()


def _reserve_delivery(sender: str, request_id: str, digest: str, recipients: int) -> int | None:
    """Atomically check idempotency and hourly/daily sender and global quotas."""
    try:
        if str(UUID(request_id)) != request_id:
            raise ValueError("Noncanonical UUID")
    except (ValueError, TypeError) as exc:
        raise ProjectError("Invalid email request identity.") from exc
    sender_hash = hashlib.sha256(sender.encode()).hexdigest()
    now = int(time.time())
    with _delivery_connection() as db:
        db.execute(
            "DELETE FROM project_email_dispatches WHERE started_at < ?",
            (now - RECORD_TTL_SECONDS,),
        )
        prior = db.execute(
            """SELECT payload_hash, state, accepted, attempts FROM project_email_dispatches
               WHERE sender_hash=? AND request_id=?""",
            (sender_hash, request_id),
        ).fetchone()
        if prior:
            if prior["payload_hash"] != digest:
                raise MailDispatchConflict("This email request ID has different content.")
            if prior["state"] == "sent":
                return int(prior["accepted"])
            if prior["state"] == "failed" and prior["attempts"] < MAX_SEND_ATTEMPTS:
                # A documented no-send can be retried without changing UUID.
                # Attempt caps prevent unlimited SMTP requests under one quota entry.
                db.execute(
                    """UPDATE project_email_dispatches
                       SET state='sending', attempts=attempts+1
                       WHERE sender_hash=? AND request_id=?""",
                    (sender_hash, request_id),
                )
                return None
            raise MailDispatchConflict(
                "This email request was already attempted; delivery is not confirmed. "
                "Check recipients before starting a new send."
            )
        hour = now - 3600
        day = now - 24 * 3600
        per_hour = db.execute(
            "SELECT COUNT(*) FROM project_email_dispatches WHERE sender_hash=? AND started_at>?",
            (sender_hash, hour),
        ).fetchone()[0]
        per_day, recipient_day = db.execute(
            "SELECT COUNT(*), COALESCE(SUM(recipients),0) FROM project_email_dispatches WHERE sender_hash=? AND started_at>?",
            (sender_hash, day),
        ).fetchone()
        global_daily = db.execute(
            "SELECT COUNT(*) FROM project_email_dispatches WHERE started_at>?", (day,)
        ).fetchone()[0]
        if (
            per_hour >= HOURLY_SEND_LIMIT
            or per_day >= DAILY_SEND_LIMIT
            or recipient_day + recipients > DAILY_RECIPIENT_LIMIT
            or global_daily >= DAILY_GLOBAL_LIMIT
        ):
            raise MailRateLimit("Project email sending limit reached. Try again later.")
        db.execute(
            """INSERT INTO project_email_dispatches
               (sender_hash,request_id,payload_hash,started_at,recipients,state)
               VALUES (?,?,?,?,?,'sending')""",
            (sender_hash, request_id, digest, now, recipients),
        )
    return None


def _finish_delivery(sender: str, request_id: str, state: str, accepted: int) -> None:
    sender_hash = hashlib.sha256(sender.encode()).hexdigest()
    with _delivery_connection() as db:
        db.execute(
            """UPDATE project_email_dispatches SET state=?, accepted=?
               WHERE sender_hash=? AND request_id=? AND state='sending'""",
            (state, accepted, sender_hash, request_id),
        )


def parse_recipients(raw: str) -> list[str]:
    """Comma- or whitespace-separated, distinct, validated mailboxes."""
    parts = [part for part in re.split(r"[\s,]+", raw.strip()) if part]
    if not parts:
        raise ProjectError("Enter at least one email address.")
    if len(parts) > MAX_RECIPIENTS:
        raise ProjectError(f"Enter at most {MAX_RECIPIENTS} email addresses.")
    recipients: list[str] = []
    for part in parts:
        try:
            address = cloud_auth._normalize_email(part)
        except ValueError as exc:
            raise ProjectError(f"Invalid recipient email address: {part[:80]}") from exc
        if address not in recipients:
            recipients.append(address)
    return recipients


def email_project_bundle(path: str) -> tuple[bytes, str]:
    """Use Export's portable format, retaining all sessions but not saved papers."""
    authorized = project_path(path)
    project = inspect_project(authorized).project
    if authorized.suffix == ".json":
        raw = download_bytes(authorized)
    elif authorized.suffix == ".sigma" and authorized.is_dir():
        raw = encode(authorized)
    else:
        raise ProjectError("Unsupported project storage format")
    bundle = json.loads(raw)
    # Paper artifacts travel as *separate* attachments when requested. Do not
    # put them in the project import, even for a sender with saved versions.
    files = bundle["files"]
    for name in tuple(files):
        if name.startswith(("artifacts/papers/", "papers/")):
            del files[name]
    content = (json.dumps(bundle, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode(
        "utf-8"
    )
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", project.title).strip("-")[:80] or "project"
    return content, f"sigma-{slug}.json"


def send_project_email(
    path: str,
    raw_recipients: str,
    body: str,
    mode: MailMode,
    paper_id: str | None,
    request_id: str | None = None,
) -> int:
    """Send project + requested attachments; reject invalid inputs before SMTP."""
    recipients = parse_recipients(raw_recipients)
    if mode not in {"project", "pdf", "pdf_tex"}:
        raise ProjectError("Choose a supported attachment option.")
    if len(body) > 10_000:
        raise ProjectError("Email body is too long.")
    project = inspect_project(path).project
    project_bytes, project_filename = email_project_bundle(path)
    attachments: list[tuple[str, bytes, str, str]] = [
        (project_filename, project_bytes, "application", "json")
    ]
    if mode != "project":
        if not paper_id:
            raise ProjectError("Select a generated paper.")
        available = next(
            (
                item
                for item in papers.list_papers(path)
                if item["paper_id"] == paper_id and item["pdf_available"]
            ),
            None,
        )
        if available is None:
            raise ProjectError("The selected paper is no longer available.")
        basename = papers.paper_download_basename(path, paper_id)
        attachments.append(
            (f"{basename}.pdf", papers.get_pdf(path, paper_id), "application", "pdf")
        )
        if mode == "pdf_tex":
            attachments.append(
                (
                    f"{basename}.tex",
                    papers.paper_tex(path, paper_id).encode("utf-8"),
                    "application",
                    "x-tex",
                )
            )
    if sum(len(item[1]) for item in attachments) > MAX_ATTACHMENT_BYTES:
        raise ProjectError(
            "Attachments exceed the email size limit (18 MB). Export the project instead."
        )
    title = re.sub(r"[\r\n\x00-\x1f]+", " ", project.title).strip()[:180] or "Untitled project"
    message = EmailMessage()
    message["Subject"] = f"SIGMA project: {title}"
    introduction = body.strip()
    instructions = (
        f"Attached: SIGMA project '{title}'.\n"
        "Import the attached .json file in SIGMA to continue the research, "
        "including stopped sessions. Papers can be generated from the imported project.\n"
    )
    message.set_content(f"{introduction}\n\n{instructions}" if introduction else instructions)
    for filename, data, maintype, subtype in attachments:
        message.add_attachment(data, maintype=maintype, subtype=subtype, filename=filename)
    principal = cloud_auth.current_principal()
    sender = "subject:" + principal.subject if principal is not None else "local"
    reply_to = (
        principal.email
        if principal is not None
        else (
            os.environ.get("SIGMA_PROJECT_EMAIL_REPLY_TO", "").strip()
            or os.environ.get("SIGMA_INVITATION_SMTP_USERNAME", "").strip()
        )
    )
    if reply_to:
        try:
            reply_to = cloud_auth._normalize_email(reply_to)
        except ValueError as exc:
            raise ProjectError("A verified return email address is required.") from exc
    digest = hashlib.sha256(
        repr((path, recipients, body, mode, paper_id)).encode()
        + b"\0"
        + b"".join(hashlib.sha256(data).digest() for _, data, _, _ in attachments)
    ).hexdigest()
    identity = request_id or str(uuid4())
    prior_count = _reserve_delivery(sender, identity, digest, len(recipients))
    if prior_count is not None:
        return prior_count
    try:
        cloud_auth.send_smtp_message(message, recipients, reply_to=reply_to or None)
    except cloud_auth.SMTPDeliveryError as exc:
        _finish_delivery(sender, identity, exc.state, exc.accepted_count)
        refused = (
            " Not delivered to: " + ", ".join(exc.refused_recipients) + "."
            if exc.refused_recipients
            else ""
        )
        if exc.state == "failed":
            raise MailDeliveryNotSent(
                "Project email was not delivered." + refused + " You can retry Send."
            ) from exc
        raise MailDispatchConflict(
            "Project email delivery was "
            + ("partial" if exc.state == "partial" else "uncertain")
            + "."
            + refused
            + " Check recipients before starting a new send."
        ) from exc
    except Exception as exc:
        # Unexpected failures after the reservation might follow SMTP DATA.
        _finish_delivery(sender, identity, "unknown", 0)
        raise MailDispatchConflict(
            "Project email delivery is uncertain. Check recipients before starting a new send."
        ) from exc
    except BaseException:
        _finish_delivery(sender, identity, "unknown", 0)
        raise
    _finish_delivery(sender, identity, "sent", len(recipients))
    return len(recipients)
