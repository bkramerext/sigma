"""Cross-account project membership, revisions, and renewable execution leases.

Projects and their checkpoints stay in the creator's existing private workspace.
The central SQLite catalog is an ACL, not a second copy of project data.
All identities come from verified Google authentication; client emails are only
membership invitations, never authorization assertions.
"""
from __future__ import annotations

import logging
import re
import sqlite3
import time
from contextlib import contextmanager
from email.message import EmailMessage
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import quote
from uuid import uuid4

from sigma import cloud_auth, cloud_workspaces
from sigma.model_catalog import validate_pair

LEASE_SECONDS = 120
EMAIL = re.compile(r"^[a-z0-9][a-z0-9._+%-]{0,63}@[a-z0-9](?:[a-z0-9.-]{0,251}[a-z0-9])?$")
LOGGER = logging.getLogger("sigma.collaboration")


def normalize_collaborator(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("Enter a valid Google account email address.")
    email = value.strip().casefold()
    if len(email) > 254 or not EMAIL.fullmatch(email):
        raise ValueError("Enter a valid Google account email address.")
    local, domain = email.rsplit("@", 1)
    if (
        ".." in local or local.endswith(".") or ".." in domain
        or any(not part or len(part) > 63 or part.startswith("-") or part.endswith("-")
               for part in domain.split("."))
        or "." not in domain or len(domain.rsplit(".", 1)[1]) < 2
    ):
        raise ValueError("Enter a valid Google account email address.")
    if domain in {"gmail.com", "googlemail.com"} and (
        not 6 <= len(local) <= 30 or not re.fullmatch(r"[a-z0-9]+(?:\.[a-z0-9]+)*", local)
    ):
        raise ValueError("Gmail names must be 6–30 characters of letters, digits and dots.")
    return email


def _identity() -> tuple[cloud_workspaces.Workspace, str]:
    workspace = cloud_workspaces.current()
    principal = cloud_auth.current_principal()
    if (
        workspace is None or workspace.guest or principal is None
        or principal.role == "guest" or not workspace.verified_subject
        or principal.subject != workspace.verified_subject
    ):
        raise ValueError("Authenticated Google account required for project collaboration.")
    return workspace, principal.email.casefold()


@contextmanager
def _db() -> Iterator[sqlite3.Connection]:
    db = cloud_workspaces._connect(cloud_workspaces.storage_root())
    try:
        db.execute("""CREATE TABLE IF NOT EXISTS shared_projects (
            path TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            owner_hash TEXT NOT NULL,
            owner_email TEXT NOT NULL,
            revision INTEGER NOT NULL DEFAULT 0,
            model TEXT NOT NULL,
            thinking TEXT NOT NULL,
            last_writer TEXT NOT NULL,
            updated_at REAL NOT NULL
        )""")
        db.execute("""CREATE TABLE IF NOT EXISTS shared_collaborators (
            path TEXT NOT NULL,
            email TEXT NOT NULL,
            PRIMARY KEY(path, email),
            FOREIGN KEY(path) REFERENCES shared_projects(path)
        )""")
        db.execute("""CREATE TABLE IF NOT EXISTS shared_leases (
            path TEXT PRIMARY KEY,
            token TEXT NOT NULL,
            email TEXT NOT NULL,
            activity TEXT NOT NULL,
            started_at REAL NOT NULL,
            expires_at REAL NOT NULL
        )""")
        db.execute("""CREATE TABLE IF NOT EXISTS shared_email_outbox (
            id TEXT PRIMARY KEY,
            recipient TEXT NOT NULL,
            project_path TEXT NOT NULL,
            project_title TEXT NOT NULL,
            event TEXT NOT NULL,
            created_at REAL NOT NULL,
            sent_at REAL
        )""")
        yield db
    finally:
        db.close()


def register_owner(view: Any) -> None:
    """Lazily register existing as well as newly created private projects."""
    workspace = cloud_workspaces.current()
    principal = cloud_auth.current_principal()
    if workspace is None or workspace.guest or principal is None or principal.role == "guest":
        return
    path = Path(view.path)
    if not path.is_relative_to(workspace.path):
        return
    with _db() as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute(
            "SELECT project_id, owner_hash FROM shared_projects WHERE path=?", (view.path,)
        ).fetchone()
        if row is None:
            from sigma import global_research_settings

            config = global_research_settings.load_config()
            db.execute(
                """INSERT INTO shared_projects
                (path, project_id, owner_hash, owner_email, model, thinking, last_writer, updated_at)
                VALUES (?,?,?,?,?,?,?,?)""",
                (view.path, view.project.id, workspace.subject_hash, principal.email.casefold(),
                 config["ai_model"], config["reasoning_effort"], principal.email.casefold(), time.time()),
            )
        elif row["project_id"] != view.project.id or row["owner_hash"] != workspace.subject_hash:
            db.rollback()
            raise ValueError("Project identity has changed; collaboration access is unavailable.")
        db.commit()


def authorized_shared_path(path: Path) -> bool:
    """The caller already checked for traversal and symlinks; accept exact ACL paths only."""
    workspace = cloud_workspaces.current()
    principal = cloud_auth.current_principal()
    if workspace is None or workspace.guest or principal is None or principal.role == "guest":
        return False
    with _db() as db:
        row = db.execute(
            """SELECT 1 FROM shared_collaborators c
            JOIN shared_projects p ON p.path=c.path
            WHERE c.path=? AND c.email=?""", (str(path), principal.email.casefold())
        ).fetchone()
        return row is not None


def _row(db: sqlite3.Connection, path: str) -> sqlite3.Row:
    row = db.execute("SELECT * FROM shared_projects WHERE path=?", (path,)).fetchone()
    if row is None:
        raise ValueError("Collaboration metadata unavailable. Reopen the project.")
    return row


def _membership(db: sqlite3.Connection, path: str) -> tuple[sqlite3.Row, str]:
    workspace, email = _identity()
    row = _row(db, path)
    if row["owner_hash"] == workspace.subject_hash:
        return row, email
    if db.execute(
        "SELECT 1 FROM shared_collaborators WHERE path=? AND email=?", (path, email)
    ).fetchone() is None:
        raise ValueError("Project not found or access denied.")
    return row, email


def _lease(db: sqlite3.Connection, path: str) -> dict[str, Any] | None:
    current = db.execute(
        "SELECT email, activity, started_at, expires_at FROM shared_leases WHERE path=?", (path,)
    ).fetchone()
    if current is None or current["expires_at"] <= time.time():
        return None
    return dict(current)


def summary(path: str) -> dict[str, Any]:
    from sigma.projects import inspect_project

    view = inspect_project(path)
    if cloud_workspaces.current() is None:
        return {
            "owner": None, "collaborators": [], "revision": 0,
            "model": view.project.ai_model, "thinking": view.project.reasoning_effort,
            "lease": None, "shared": False,
        }
    with _db() as db:
        row, email = _membership(db, view.path)
        members = [
            record["email"] for record in db.execute(
                "SELECT email FROM shared_collaborators WHERE path=? ORDER BY email", (view.path,)
            )
        ]
        return {
            "owner": row["owner_email"], "collaborators": members, "revision": row["revision"],
            "model": row["model"], "thinking": row["thinking"], "lease": _lease(db, view.path),
            "shared": bool(members), "you": email,
        }


def model_settings(path: str) -> dict[str, str] | None:
    if cloud_workspaces.current() is None:
        return None
    with _db() as db:
        row, _email = _membership(db, path)
        return {"ai_model": row["model"], "reasoning_effort": row["thinking"]}


def require_revision(path: str, expected: int) -> None:
    if type(expected) is not int or expected < 0:
        raise ValueError("Project revision is missing or invalid.")
    with _db() as db:
        row, _ = _membership(db, path)
        if row["revision"] != expected:
            raise ValueError(
                f"Project was saved by {row['last_writer']}. Reopen it and redo your changes."
            )


def save_settings(
    path: str, expected: int, collaborators: list[str], model: str, thinking: str,
    title: str,
) -> dict[str, Any]:
    """Called while the existing project write lock is held."""
    from sigma.projects import ProjectError

    if not isinstance(collaborators, list) or len(collaborators) > 50:
        raise ProjectError("A project supports at most 50 collaborators.")
    try:
        emails = [normalize_collaborator(item) for item in collaborators]
        validate_pair(model, thinking)
    except ValueError as exc:
        raise ProjectError(str(exc)) from exc
    if len(set(emails)) != len(emails):
        raise ProjectError("Each collaborator may appear only once.")
    with _db() as db:
        db.execute("BEGIN IMMEDIATE")
        row, actor = _membership(db, path)
        if row["revision"] != expected:
            raise ProjectError(
                f"Project was saved by {row['last_writer']}. Reopen it and redo your changes."
            )
        if row["owner_email"] in emails:
            raise ProjectError("The project owner is already included automatically.")
        previous = {
            member["email"] for member in db.execute(
                "SELECT email FROM shared_collaborators WHERE path=?", (path,)
            )
        }
        new_members = set(emails)
        changed = (
            new_members != previous or row["model"] != model or row["thinking"] != thinking
        )
        if changed:
            db.execute("DELETE FROM shared_collaborators WHERE path=?", (path,))
            db.executemany(
                "INSERT INTO shared_collaborators (path,email) VALUES (?,?)",
                [(path, member) for member in sorted(new_members)],
            )
            db.execute(
                """UPDATE shared_projects SET revision=revision+1, model=?, thinking=?,
                   last_writer=?, updated_at=? WHERE path=?""",
                (model, thinking, actor, time.time(), path),
            )
            for recipient in sorted(previous ^ new_members):
                db.execute(
                    """INSERT INTO shared_email_outbox
                    (id,recipient,project_path,project_title,event,created_at)
                    VALUES (?,?,?,?,?,?)""",
                    (uuid4().hex, recipient, path, title,
                     "added" if recipient in new_members else "removed", time.time()),
                )
        db.commit()
        return {"changed": changed, "revision": expected + int(changed)}


def note_change(path: str) -> None:
    """Advance revision after an ordinary validated project write."""
    workspace = cloud_workspaces.current()
    if workspace is None or workspace.guest:
        return
    try:
        with _db() as db:
            db.execute("BEGIN IMMEDIATE")
            row, actor = _membership(db, path)
            db.execute(
                "UPDATE shared_projects SET revision=?,last_writer=?,updated_at=? WHERE path=?",
                (row["revision"] + 1, actor, time.time(), path),
            )
            db.commit()
    except ValueError as exc:
        from sigma.projects import ProjectError

        raise ProjectError(str(exc)) from exc


def shared_with_me() -> list[dict[str, str]]:
    workspace = cloud_workspaces.current()
    if workspace is None or workspace.guest:
        return []
    _ws, email = _identity()
    with _db() as db:
        return [
            {"path": row["path"], "id": row["project_id"]}
            for row in db.execute(
                """SELECT p.path,p.project_id FROM shared_projects p JOIN shared_collaborators c
                ON c.path=p.path WHERE c.email=? ORDER BY p.updated_at DESC""", (email,)
            )
        ]


def acquire_lease(path: str, activity: str) -> str | None:
    """Atomic, renewable per-project single-operator admission. Unshared projects retain normal behavior."""
    if cloud_workspaces.current() is None:
        return None
    if activity not in {"Research session", "Paper generation"}:
        raise ValueError("Unsupported collaboration activity.")
    from sigma.projects import ProjectError

    with _db() as db:
        db.execute("BEGIN IMMEDIATE")
        row, actor = _membership(db, path)
        shared = db.execute(
            "SELECT 1 FROM shared_collaborators WHERE path=? LIMIT 1", (path,)
        ).fetchone()
        if not shared:
            db.commit()
            return None
        active = _lease(db, path)
        if active is not None:
            db.rollback()
            raise ProjectError(
                f"Project is being used by {active['email']} ({active['activity']}). "
                "Wait for that activity to finish before starting another."
            )
        token = uuid4().hex
        now = time.time()
        db.execute(
            """INSERT INTO shared_leases(path,token,email,activity,started_at,expires_at)
               VALUES(?,?,?,?,?,?) ON CONFLICT(path) DO UPDATE SET
               token=excluded.token,email=excluded.email,activity=excluded.activity,
               started_at=excluded.started_at,expires_at=excluded.expires_at""",
            (path, token, actor, activity, now, now + LEASE_SECONDS),
        )
        db.execute(
            "UPDATE shared_projects SET revision=revision+1,last_writer=?,updated_at=? WHERE path=?",
            (actor, now, path),
        )
        db.commit()
        return token


def renew_lease(path: str, token: str) -> bool:
    with _db() as db:
        db.execute("BEGIN IMMEDIATE")
        now = time.time()
        changed = db.execute(
            """UPDATE shared_leases SET expires_at=?
               WHERE path=? AND token=? AND expires_at>?""",
            (now + LEASE_SECONDS, path, token, now),
        ).rowcount
        db.commit()
        return changed == 1


def release_lease(path: str, token: str | None) -> None:
    if token is None:
        return
    with _db() as db:
        db.execute("BEGIN IMMEDIATE")
        db.execute("DELETE FROM shared_leases WHERE path=? AND token=?", (path, token))
        db.commit()


def require_not_leased(path: str) -> None:
    if cloud_workspaces.current() is None:
        return
    from sigma.projects import ProjectError

    with _db() as db:
        active = _lease(db, path)
        if active is not None:
            raise ProjectError(
                f"Project is being used by {active['email']} ({active['activity']}). "
                "Wait for that activity to finish."
            )


def forget_project(path: str) -> None:
    if cloud_workspaces.current() is None:
        return
    with _db() as db:
        db.execute("BEGIN IMMEDIATE")
        db.execute("DELETE FROM shared_leases WHERE path=?", (path,))
        db.execute("DELETE FROM shared_collaborators WHERE path=?", (path,))
        db.execute("DELETE FROM shared_email_outbox WHERE project_path=?", (path,))
        db.execute("DELETE FROM shared_projects WHERE path=?", (path,))
        db.commit()


def drain_notifications() -> list[str]:
    """Best effort delivery; failed messages stay queued for the next attempt."""
    if cloud_workspaces.current() is None:
        return []
    with _db() as db:
        pending = list(db.execute(
            "SELECT * FROM shared_email_outbox WHERE sent_at IS NULL ORDER BY created_at LIMIT 20"
        ))
    warnings: list[str] = []
    for event in pending:
        message = EmailMessage()
        added = event["event"] == "added"
        message["Subject"] = (
            f"SIGMA: Added to {event['project_title']}" if added
            else f"SIGMA: Removed from {event['project_title']}"
        )
        origin = (cloud_auth.config().origin or "").rstrip("/")
        project_link = (
            f"{origin}/project?path={quote(event['project_path'], safe='')}"
            if origin.startswith("https://") or origin.startswith("http://localhost")
            else ""
        )
        text = (
            f"You have been added as a collaborator on SIGMA project "
            f"“{event['project_title']}”.\n\n"
            + (f"Open project: {project_link}\n\n" if project_link else
               "Sign in to SIGMA with this Google account to find the shared project.\n\n")
            if added else
            f"You have been removed as a collaborator on SIGMA project "
            f"“{event['project_title']}”.\n"
        )
        message.set_content(text)
        try:
            cloud_auth.send_smtp_message(message, [event["recipient"]])
        except (cloud_auth.SMTPDeliveryError, RuntimeError, OSError) as exc:
            LOGGER.warning("Collaboration notification queued: %s", type(exc).__name__)
            warnings.append("Some collaboration notification emails are queued for retry.")
            break
        with _db() as db:
            db.execute(
                "UPDATE shared_email_outbox SET sent_at=? WHERE id=? AND sent_at IS NULL",
                (time.time(), event["id"]),
            )
    return warnings
