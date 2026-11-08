"""Cross-account project membership, revisions, and renewable execution leases.

Projects and their checkpoints stay in the creator's existing private workspace.
The central SQLite catalog is an ACL, not a second copy of project data.
All identities come from verified Google authentication; client emails are only
membership invitations, never authorization assertions.
"""
from __future__ import annotations

import asyncio
import logging
import re
import sqlite3
import time
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
from email.message import EmailMessage
from pathlib import Path
from collections.abc import Callable
from typing import Any, Iterator, TypeVar
from urllib.parse import quote
from uuid import uuid4

from sigma import cloud_auth, cloud_workspaces
from sigma.model_catalog import validate_pair

LEASE_SECONDS = 120
EMAIL = re.compile(r"^[a-z0-9][a-z0-9._+%-]{0,63}@[a-z0-9](?:[a-z0-9.-]{0,251}[a-z0-9])?$")
LOGGER = logging.getLogger("sigma.collaboration")
_LEASE_CONTEXT: ContextVar[tuple[str, str] | None] = ContextVar(
    "sigma_project_execution_lease", default=None
)
_WRITE_CONTEXT: ContextVar[tuple[str, sqlite3.Connection] | None] = ContextVar(
    "sigma_project_write_transaction", default=None
)
_T = TypeVar("_T")


@contextmanager
def bind_lease(path: str, token: str | None) -> Iterator[None]:
    """Bind a worker's fencing token into asyncio child tasks."""
    if token is None:
        yield
        return
    binding = _LEASE_CONTEXT.set((str(path), token))
    try:
        yield
    finally:
        _LEASE_CONTEXT.reset(binding)


def _verify_fence(db: sqlite3.Connection, path: str, actor: str) -> None:
    from sigma.projects import ProjectError

    lease = db.execute(
        "SELECT token,email,activity,expires_at FROM shared_leases WHERE path=?",
        (path,),
    ).fetchone()
    binding = _LEASE_CONTEXT.get()
    token = binding[1] if binding is not None and binding[0] == path else None
    if token is not None:
        if lease is None or lease["token"] != token or lease["expires_at"] <= time.time():
            raise ProjectError("Project execution lease was lost. Resume from saved progress.")
    elif lease is not None and lease["expires_at"] > time.time() and lease["email"] != actor:
        raise ProjectError(
            f"Project is being used by {lease['email']} ({lease['activity']}). "
            "Wait for that activity to finish."
        )


@contextmanager
def write_guard(
    path: str, expected_revision: int | None = None
) -> Iterator[sqlite3.Connection | None]:
    """Fence a persisted mutation and revision under one SQLite writer transaction.

    Lease acquisition also requires BEGIN IMMEDIATE. A new owner cannot claim
    the project between fencing verification and the actual checkpoint write.
    Nested mutations on the same project reuse the transaction.
    """
    from sigma.projects import ProjectError

    path = str(path)
    existing = _WRITE_CONTEXT.get()
    if existing is not None:
        if existing[0] != path:
            raise ProjectError("Nested writes across shared projects are unsupported.")
        db = existing[1]
        row = _row(db, path)
        if expected_revision is not None and (
            type(expected_revision) is not int or row["revision"] != expected_revision
        ):
            raise ProjectError(
                f"Project was saved by {row['last_writer']}. "
                "Reopen it and redo your changes."
            )
        yield db
        return
    workspace = cloud_workspaces.current()
    if workspace is None or workspace.guest:
        yield None
        return
    with _db() as db:
        if db.execute("SELECT 1 FROM shared_projects WHERE path=?", (path,)).fetchone() is None:
            # Registration happens on open/create and at execution admission.
            # Unregistered, private or newly initialized projects are unchanged.
            yield None
            return
        db.execute("BEGIN IMMEDIATE")
        try:
            row, actor = _membership(db, path)
            if expected_revision is not None and (
                type(expected_revision) is not int
                or expected_revision < 0
                or row["revision"] != expected_revision
            ):
                raise ProjectError(
                    f"Project was saved by {row['last_writer']}. "
                    "Reopen it and redo your changes."
                )
            _verify_fence(db, path, actor)
            binding = _WRITE_CONTEXT.set((path, db))
            try:
                yield db
                db.execute(
                    """UPDATE shared_projects SET revision=revision+1,
                       last_writer=?,updated_at=? WHERE path=?""",
                    (actor, time.time(), path),
                )
                db.commit()
            finally:
                _WRITE_CONTEXT.reset(binding)
        except BaseException:
            db.rollback()
            raise


def fenced_checkpoint(func: Callable[..., _T]) -> Callable[..., _T]:
    """Fence checkpoint sidecars that bypass the main project write lock."""

    @wraps(func)
    def guarded(path: str, *args: Any, **kwargs: Any) -> _T:
        with write_guard(path):
            return func(path, *args, **kwargs)

    return guarded


def watch_lease(path: str, token: str | None, worker: asyncio.Task[Any]) -> None:
    """Renew a backend-owned lease regardless of browser connection state."""
    if token is None:
        return

    async def monitor() -> None:
        try:
            while not worker.done():
                try:
                    await asyncio.wait_for(
                        asyncio.shield(worker), timeout=LEASE_SECONDS / 3
                    )
                except TimeoutError:
                    if not renew_lease(path, token):
                        worker.cancel()
                        break
                except BaseException:
                    break
            if not worker.done():
                await asyncio.gather(worker, return_exceptions=True)
        finally:
            release_lease(path, token)

    asyncio.create_task(monitor())




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
        db.execute("PRAGMA foreign_keys=ON")
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
    if (
        workspace is None or workspace.guest or principal is None or principal.role == "guest"
        or not workspace.verified_subject or workspace.verified_subject != principal.subject
    ):
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
    try:
        _workspace, email = _identity()
    except ValueError:
        return False
    with _db() as db:
        row = db.execute(
            """SELECT 1 FROM shared_collaborators c
            JOIN shared_projects p ON p.path=c.path
            WHERE c.path=? AND c.email=?""", (str(path), email)
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
    path: str,
    expected: int,
    collaborators: list[str],
    model: str,
    thinking: str,
    title: str,
) -> dict[str, Any]:
    """Validate and stage shared metadata in the surrounding fenced write."""
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
    with write_guard(path, expected) as db:
        if db is None:
            raise ProjectError("Collaboration is not available for this project.")
        row, actor = _membership(db, path)
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
                """UPDATE shared_projects SET model=?,thinking=?,last_writer=? WHERE path=?""",
                (model, thinking, actor, path),
            )
            for member in previous - new_members:
                db.execute(
                    "DELETE FROM shared_leases WHERE path=? AND email=?", (path, member)
                )
            for recipient in sorted(previous ^ new_members):
                db.execute(
                    """INSERT INTO shared_email_outbox
                    (id,recipient,project_path,project_title,event,created_at)
                    VALUES (?,?,?,?,?,?)""",
                    (uuid4().hex, recipient, path, title,
                     "added" if recipient in new_members else "removed", time.time()),
                )
        return {"changed": changed, "revision": expected + 1}



def note_change(path: str) -> None:
    """Record a validated mutation (or join an enclosing write transaction)."""
    with write_guard(path):
        pass



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
    from sigma.projects import inspect_project

    register_owner(inspect_project(path))
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
        _row, actor = _membership(db, path)
        active = _lease(db, path)
        if active is not None and active["email"] != actor:
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
