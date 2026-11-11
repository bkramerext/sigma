"""Cross-account project membership, revisions, and renewable execution leases.

Projects and their checkpoints stay in the creator's existing private workspace.
The central SQLite catalog is an ACL, not a second copy of project data.
All identities come from verified Google authentication; client emails are only
membership invitations, never authorization assertions.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import re
import sqlite3
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from email.message import EmailMessage
from functools import wraps
from html import escape as html_escape
from pathlib import Path
from threading import Event, Lock, Thread
from typing import Any, TypeVar
from urllib.parse import urlencode
from uuid import uuid4

from sigma import cloud_auth, cloud_workspaces

LEASE_SECONDS = 120
MAX_NOTIFICATION_ATTEMPTS = 3
EMAIL = re.compile(r"^[a-z0-9][a-z0-9._+%-]{0,63}@[a-z0-9](?:[a-z0-9.-]{0,251}[a-z0-9])?$")
LOGGER = logging.getLogger("sigma.collaboration")
_SCHEMA_LOCK = Lock()
_SCHEMA_READY: set[tuple[str, int, int, int]] = set()
_LEASE_CONTEXT: ContextVar[tuple[str, str] | None] = ContextVar(
    "sigma_project_execution_lease", default=None
)
_WRITE_CONTEXT: ContextVar[tuple[str, sqlite3.Connection, tuple[int, int | None]] | None] = (
    ContextVar("sigma_project_write_transaction", default=None)
)
_T = TypeVar("_T")


def _write_context_owner() -> tuple[int, int | None]:
    """Inherited asyncio contexts must not reuse another task's SQLite txn."""
    try:
        task = asyncio.current_task()
    except RuntimeError:
        task = None
    return threading.get_ident(), id(task) if task is not None else None


def _current_write_transaction() -> tuple[str, sqlite3.Connection] | None:
    current = _WRITE_CONTEXT.get()
    if current is None or current[2] != _write_context_owner():
        return None
    return current[0], current[1]


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


def _document_digest(contents: bytes) -> str:
    """Hash project JSON independently of bundle member serialization.

    Portable and stored bundles normalize JSON whitespace on read. The
    metadata revision must track semantic project changes, not that encoding.
    """
    document = json.loads(contents)
    canonical = json.dumps(
        document, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _project_digest(path: str) -> str | None:
    """Digest persisted project metadata, not large paper/session sidecars."""
    from sigma.project_bundle import read_file

    project = Path(path)
    file = project / "project.json" if project.suffix == ".sigma" else project
    if not file.is_file() or file.is_symlink():
        return None
    # Single-file .json projects are bundles whose session and paper members
    # change independently. Hash just their project.json member, matching
    # _update_project's published member bytes.
    contents = (
        read_file(project, "project.json") if project.suffix == ".json" else file.read_bytes()
    )
    return _document_digest(contents)


def _reconcile_project_digest(db: sqlite3.Connection, path: str) -> None:
    """Recover an interrupted file/SQLite publication before a revision compare.

    A crashed write may have replaced project.json before SQLite committed.
    Preserve the published file and advance the catalog revision so a stale
    collaborator cannot silently overwrite it. Missing projects are handled
    by their normal project validation.
    """
    row = db.execute("SELECT project_sha256 FROM shared_projects WHERE path=?", (path,)).fetchone()
    if row is None:
        return
    digest = _project_digest(path)
    if digest is None:
        return
    if row["project_sha256"] is None:
        db.execute("UPDATE shared_projects SET project_sha256=? WHERE path=?", (digest, path))
    elif digest != row["project_sha256"]:
        db.execute(
            """UPDATE shared_projects
               SET project_sha256=?, revision=revision+1,
                   last_writer=?, updated_at=? WHERE path=?""",
            (digest, "recovered project file update", time.time(), path),
        )


def note_project_published(path: str, contents: bytes) -> None:
    """Commit a project's new digest in its enclosing collaboration transaction."""
    transaction = _current_write_transaction()
    if transaction is None or transaction[0] != str(path):
        return
    db = transaction[1]
    db.execute(
        "UPDATE shared_projects SET project_sha256=? WHERE path=?",
        (_document_digest(contents), str(path)),
    )


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
    elif lease is not None and lease["expires_at"] > time.time():
        raise ProjectError(
            f"Project is being used by {lease['email']} ({lease['activity']}). "
            "Wait for that activity to finish."
        )


@contextmanager
def write_guard(
    path: str,
    expected_revision: int | None = None,
    *,
    advance_revision: bool = True,
    allow_acl_mutation: bool = False,
) -> Iterator[sqlite3.Connection | None]:
    """Fence a persisted mutation and revision under one SQLite writer transaction.

    Lease acquisition also requires BEGIN IMMEDIATE. A new owner cannot claim
    the project between fencing verification and the actual checkpoint write.
    Nested mutations on the same project reuse the transaction.
    """
    from sigma.projects import ProjectError

    path = str(path)
    existing = _current_write_transaction()
    if existing is not None:
        if existing[0] != path:
            raise ProjectError("Nested writes across shared projects are unsupported.")
        db = existing[1]
        row = _row(db, path)
        if expected_revision is not None and (
            type(expected_revision) is not int or row["revision"] != expected_revision
        ):
            raise ProjectError(
                f"Project was saved by {row['last_writer']}. Reopen it and redo your changes."
            )
        yield db
        return
    workspace = cloud_workspaces.current()
    binding = _LEASE_CONTEXT.get()
    bound_worker = binding is not None and binding[0] == path
    if workspace is None or workspace.guest:
        if bound_worker:
            raise ProjectError("Project execution context was lost; checkpoint refused.")
        yield None
        return
    with _db() as db:
        if db.execute("SELECT 1 FROM shared_projects WHERE path=?", (path,)).fetchone() is None:
            # Unregistered projects may still be new private projects. A worker
            # carrying an old lease, however, must never fall through this
            # path after project deletion or ACL cleanup.
            if bound_worker:
                raise ProjectError("Project was deleted or its execution lease was lost.")
            yield None
            return
        db.execute("BEGIN IMMEDIATE")
        try:
            row, actor = _membership(db, path)
            if expected_revision is not None:
                _reconcile_project_digest(db, path)
                row = _row(db, path)
            if expected_revision is not None and (
                type(expected_revision) is not int
                or expected_revision < 0
                or row["revision"] != expected_revision
            ):
                raise ProjectError(
                    f"Project was saved by {row['last_writer']}. Reopen it and redo your changes."
                )
            if allow_acl_mutation:
                # Only an ACL mutation may bypass an active research lease.
                # Workers cannot use this path, nor may settings race deletion.
                if binding is not None:
                    raise ProjectError("Workers cannot bypass execution fencing for ACL changes.")
                lease = db.execute(
                    "SELECT activity,expires_at FROM shared_leases WHERE path=?", (path,)
                ).fetchone()
                if (
                    lease is not None
                    and lease["expires_at"] > time.time()
                    and lease["activity"] == "Project deletion"
                ):
                    raise ProjectError("Project deletion is in progress.")
            else:
                _verify_fence(db, path, actor)
            # A project-wide file mutex protects the short shared write, while
            # the reservation proves which collaborator owns the Paper's
            # checkpoint. Never allow a valid collaborator to impersonate
            # another run merely by choosing its directory.
            from sigma import papers

            run_id = papers._paper_run_id.get()
            if run_id is not None:
                reserved = db.execute(
                    """SELECT creator_hash,status FROM shared_run_reservations
                       WHERE path=? AND kind='paper' AND run_id=?""",
                    (path, run_id),
                ).fetchone()
                if (
                    reserved is None
                    or reserved["creator_hash"] != _identity()[0].subject_hash
                    or reserved["status"] == "discarded"
                ):
                    raise ProjectError(
                        "Paper checkpoint belongs to another creator or was discarded."
                    )
            binding = _WRITE_CONTEXT.set((path, db, _write_context_owner()))
            try:
                yield db
                if advance_revision:
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

    transient_status = func.__name__ in {
        "_write_progress_status",
        "_clear_progress_status",
        "_write_queue_status",
        "_clear_queue_status",
    }

    @wraps(func)
    def guarded(path: str, *args: Any, **kwargs: Any) -> _T:
        if _current_write_transaction() is not None or cloud_workspaces.current() is None:
            # Already inside a serialized mutation, or the established local
            # single-user/test persistence path without a collaboration DB.
            with write_guard(path, advance_revision=not transient_status):
                return func(path, *args, **kwargs)
        # Ordinary checkpoint writes must not hold a global SQLite writer
        # while waiting for this project's filesystem lock.
        from sigma.projects import project_write_lock

        with project_write_lock(path, advance_revision=not transient_status):
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
                    await asyncio.wait_for(asyncio.shield(worker), timeout=LEASE_SECONDS / 3)
                except TimeoutError:
                    if not renew_lease(path, token):
                        worker.cancel()
                        break
                except (Exception, asyncio.CancelledError):  # noqa: BLE001 - worker errors end lease monitoring
                    break
            if not worker.done():
                await asyncio.gather(worker, return_exceptions=True)
        finally:
            release_lease(path, token)

    asyncio.create_task(monitor())


def normalize_collaborator(value: str) -> str:
    if not isinstance(value, str):
        raise TypeError("Enter a valid Google account email address.")
    email = value.strip().casefold()
    if len(email) > 254 or not EMAIL.fullmatch(email):
        raise ValueError("Enter a valid Google account email address.")
    local, domain = email.rsplit("@", 1)
    if (
        ".." in local
        or local.endswith(".")
        or ".." in domain
        or any(
            not part or len(part) > 63 or part.startswith("-") or part.endswith("-")
            for part in domain.split(".")
        )
        or "." not in domain
        or len(domain.rsplit(".", 1)[1]) < 2
    ):
        raise ValueError("Enter a valid Google account email address.")
    return email


def _identity() -> tuple[cloud_workspaces.Workspace, str]:
    workspace = cloud_workspaces.current()
    principal = cloud_auth.current_principal()
    if (
        workspace is None
        or workspace.guest
        or principal is None
        or principal.role == "guest"
        or not workspace.verified_subject
        or principal.subject != workspace.verified_subject
    ):
        raise ValueError("Authenticated Google account required for project collaboration.")
    return workspace, principal.email.casefold()


@contextmanager
def _db() -> Iterator[sqlite3.Connection]:
    db = cloud_workspaces._connect(cloud_workspaces.storage_root())
    try:
        db.execute("PRAGMA foreign_keys=ON")
        # Schema migration happens once per actual database inode, not on
        # every read, activity poll, or unrelated account request.
        db_file = next(
            (row[2] for row in db.execute("PRAGMA database_list") if row[1] == "main"), ""
        )
        identity = None
        if db_file:
            info = os.stat(db_file)
            # The inode alone cannot detect an in-place legacy schema restore.
            # SQLite bumps schema_version whenever DDL changes the catalog.
            schema_generation = db.execute("PRAGMA schema_version").fetchone()[0]
            identity = (db_file, info.st_dev, info.st_ino, schema_generation)
        if identity is None or identity not in _SCHEMA_READY:
            with _SCHEMA_LOCK:
                if identity is None or identity not in _SCHEMA_READY:
                    db.execute("""CREATE TABLE IF NOT EXISTS shared_projects (
                        path TEXT PRIMARY KEY,
                        project_id TEXT NOT NULL,
                        owner_hash TEXT NOT NULL,
                        owner_email TEXT NOT NULL,
                        revision INTEGER NOT NULL DEFAULT 0,
                        project_sha256 TEXT,
                        model TEXT NOT NULL,
                        thinking TEXT NOT NULL,
                        last_writer TEXT NOT NULL,
                        updated_at REAL NOT NULL
                    )""")
                    project_columns = {
                        column["name"]
                        for column in db.execute("PRAGMA table_info(shared_projects)")
                    }
                    if "project_sha256" not in project_columns:
                        db.execute("ALTER TABLE shared_projects ADD COLUMN project_sha256 TEXT")
                    db.execute("""CREATE TABLE IF NOT EXISTS shared_collaborators (
                        path TEXT NOT NULL,
                        email TEXT NOT NULL,
                        PRIMARY KEY(path, email),
                        FOREIGN KEY(path) REFERENCES shared_projects(path)
                    )""")
                    # Historical collaborators predate inviter tracking. Keep their author
                    # unknown rather than assigning a possibly incorrect collaborator.
                    # Such legacy entries remain removable by the owner.
                    member_columns = {
                        column["name"]
                        for column in db.execute("PRAGMA table_info(shared_collaborators)")
                    }
                    if "added_by" not in member_columns:
                        db.execute("ALTER TABLE shared_collaborators ADD COLUMN added_by TEXT")
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
                        sent_at REAL,
                        attempts INTEGER NOT NULL DEFAULT 0,
                        retry_after REAL NOT NULL DEFAULT 0,
                        failed_at REAL
                    )""")
                    db.execute("""CREATE TABLE IF NOT EXISTS shared_artifact_authors (
                        path TEXT NOT NULL,
                        kind TEXT NOT NULL,
                        artifact_id TEXT NOT NULL,
                        email TEXT NOT NULL,
                        updated_at REAL NOT NULL,
                        PRIMARY KEY(path, kind, artifact_id),
                        FOREIGN KEY(path) REFERENCES shared_projects(path)
                    )""")
                    # Durable admission identity is independent of the temporary
                    # project execution lease. These rows are never recycled when
                    # a run fails or is discarded: later runs keep their numbers.
                    db.execute("""CREATE TABLE IF NOT EXISTS shared_run_reservations (
                        path TEXT NOT NULL,
                        kind TEXT NOT NULL CHECK(kind IN ('session', 'paper')),
                        run_id TEXT NOT NULL,
                        number INTEGER NOT NULL CHECK(number > 0),
                        creator_hash TEXT NOT NULL,
                        creator_email TEXT NOT NULL,
                        model TEXT NOT NULL,
                        thinking TEXT NOT NULL,
                        created_at REAL NOT NULL,
                        status TEXT NOT NULL DEFAULT 'reserved',
                        artifact_id TEXT,
                        PRIMARY KEY(path, kind, run_id),
                        UNIQUE(path, kind, number),
                        FOREIGN KEY(path) REFERENCES shared_projects(path) ON DELETE CASCADE
                    )""")
                    run_columns = {
                        item["name"]
                        for item in db.execute("PRAGMA table_info(shared_run_reservations)")
                    }
                    if "status" not in run_columns:
                        db.execute(
                            "ALTER TABLE shared_run_reservations "
                            "ADD COLUMN status TEXT NOT NULL DEFAULT 'reserved'"
                        )
                    if "artifact_id" not in run_columns:
                        db.execute(
                            "ALTER TABLE shared_run_reservations ADD COLUMN artifact_id TEXT"
                        )
                    # Existing hosted databases have the earlier outbox schema.
                    fields = {
                        row["name"] for row in db.execute("PRAGMA table_info(shared_email_outbox)")
                    }
                    if "attempts" not in fields:
                        db.execute(
                            "ALTER TABLE shared_email_outbox ADD COLUMN attempts INTEGER NOT NULL DEFAULT 0"
                        )
                    if "retry_after" not in fields:
                        db.execute(
                            "ALTER TABLE shared_email_outbox ADD COLUMN retry_after REAL NOT NULL DEFAULT 0"
                        )
                    if "failed_at" not in fields:
                        db.execute("ALTER TABLE shared_email_outbox ADD COLUMN failed_at REAL")
                    if identity is not None:
                        # DDL increments schema_version. Cache the *post-migration*
                        # generation; another process or a legacy restore changing
                        # the schema will trigger validation again.
                        latest_generation = db.execute("PRAGMA schema_version").fetchone()[0]
                        _SCHEMA_READY.add(
                            (identity[0], identity[1], identity[2], latest_generation)
                        )
        yield db
    finally:
        db.close()


def register_owner(view: Any) -> None:
    """Lazily register existing as well as newly created private projects."""
    workspace = cloud_workspaces.current()
    principal = cloud_auth.current_principal()
    if (
        workspace is None
        or workspace.guest
        or principal is None
        or principal.role == "guest"
        or not workspace.verified_subject
        or workspace.verified_subject != principal.subject
    ):
        return
    path = Path(view.path)
    if not path.is_relative_to(workspace.path):
        return
    with _db() as db:
        row = db.execute(
            "SELECT project_id, owner_hash FROM shared_projects WHERE path=?", (view.path,)
        ).fetchone()
        if row is not None:
            if row["project_id"] != view.project.id or row["owner_hash"] != workspace.subject_hash:
                raise ValueError(
                    "Project identity has changed; collaboration access is unavailable."
                )
            return  # Opening and polling an existing project must not take a writer lock.
        digest = _project_digest(view.path)
        db.execute("BEGIN IMMEDIATE")
        row = db.execute(
            "SELECT project_id, owner_hash FROM shared_projects WHERE path=?", (view.path,)
        ).fetchone()
        if row is None:
            db.execute(
                """INSERT INTO shared_projects
                (path, project_id, owner_hash, owner_email, project_sha256, model, thinking,
                 last_writer, updated_at)
                VALUES (?,?,?,?,?,?,?,?,?)""",
                (
                    view.path,
                    view.project.id,
                    workspace.subject_hash,
                    principal.email.casefold(),
                    digest,
                    view.project.ai_model,
                    view.project.reasoning_effort,
                    principal.email.casefold(),
                    time.time(),
                ),
            )
        elif row["project_id"] != view.project.id or row["owner_hash"] != workspace.subject_hash:
            db.rollback()
            raise ValueError("Project identity has changed; collaboration access is unavailable.")
        db.commit()


def authorized_shared_path(path: Path) -> bool:
    """Require verified owner identity or explicit collaborator membership."""
    try:
        workspace, email = _identity()
    except ValueError:
        return False
    with _db() as db:
        row = db.execute(
            """SELECT 1 FROM shared_projects p
            WHERE p.path=? AND (
                p.owner_hash=?
                OR EXISTS (
                    SELECT 1 FROM shared_collaborators c
                    WHERE c.path=p.path AND c.email=?
                )
            )""",
            (str(path), workspace.subject_hash, email),
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
    if (
        db.execute(
            "SELECT 1 FROM shared_collaborators WHERE path=? AND email=?", (path, email)
        ).fetchone()
        is None
    ):
        raise ValueError("Project not found or access denied.")
    return row, email


def _lease(db: sqlite3.Connection, path: str) -> dict[str, Any] | None:
    current = db.execute(
        "SELECT email, activity, started_at, expires_at FROM shared_leases WHERE path=?", (path,)
    ).fetchone()
    if current is None or current["expires_at"] <= time.time():
        return None
    return dict(current)


def summary(path: str, *, verify_revision: bool = False) -> dict[str, Any]:
    from sigma.projects import inspect_project

    view = inspect_project(path)
    if cloud_workspaces.current() is None:
        return {
            "owner": None,
            "collaborators": [],
            "revision": 0,
            "model": view.project.ai_model,
            "thinking": view.project.reasoning_effort,
            "lease": None,
            "shared": False,
            "failed_notifications": 0,
        }
    # Comparing project bytes is read-only. In the common case, opening
    # Project Settings must not reserve the global SQLite writer slot.
    digest = _project_digest(view.path) if verify_revision else None
    with _db() as db:
        row, email = _membership(db, view.path)
        if verify_revision and digest is not None and digest != row["project_sha256"]:
            # Reconciliation writes only when interrupted publication actually
            # changed the project document; re-read under the transaction.
            db.execute("BEGIN IMMEDIATE")
            _reconcile_project_digest(db, view.path)
            row = _row(db, view.path)
            db.commit()
        membership = list(
            db.execute(
                "SELECT email,added_by FROM shared_collaborators WHERE path=? ORDER BY email",
                (view.path,),
            )
        )
        members = [record["email"] for record in membership]
        is_owner = row["owner_hash"] == _identity()[0].subject_hash
        removable = [
            record["email"]
            for record in membership
            if is_owner or record["added_by"] == email or record["email"] == email
        ]
        return {
            "owner": row["owner_email"],
            "collaborators": members,
            "removable_collaborators": removable,
            "revision": row["revision"],
            "model": row["model"],
            "thinking": row["thinking"],
            "lease": _lease(db, view.path),
            "shared": bool(members),
            "artifact_authors": {
                kind: {
                    record["artifact_id"]: record["email"]
                    for record in db.execute(
                        "SELECT artifact_id, email FROM shared_artifact_authors "
                        "WHERE path=? AND kind=?",
                        (view.path, kind),
                    )
                }
                for kind in ("strategy", "session", "paper", "paper_draft", "answer")
            },
            "failed_notifications": db.execute(
                """SELECT COUNT(*) FROM shared_email_outbox
                   WHERE project_path=? AND failed_at IS NOT NULL""",
                (view.path,),
            ).fetchone()[0],
            "you": email,
        }


def note_artifact_author(
    path: str, kind: str, artifact_id: str, *, created_only: bool = False
) -> None:
    """Persist the verified human responsible for an artifact change.

    Autonomous checkpoints must not overwrite the initiating human's identity.
    """
    if kind not in {"strategy", "session", "paper", "answer"} or not artifact_id:
        raise ValueError("Invalid artifact attribution")
    if cloud_workspaces.current() is None or cloud_auth.current_principal() is None:
        return
    with _db() as db:
        # Private/unregistered projects do not have collaboration provenance.
        if db.execute("SELECT 1 FROM shared_projects WHERE path=?", (path,)).fetchone() is None:
            return
        _row, actor = _membership(db, path)
        # A run's creator never changes when another collaborator resumes,
        # scores or views it. Strategy edits retain their historical behavior.
        verb = (
            "INSERT OR IGNORE"
            if created_only or kind in {"session", "paper", "answer"}
            else "INSERT OR REPLACE"
        )
        db.execute(
            f"{verb} INTO shared_artifact_authors "
            "(path, kind, artifact_id, email, updated_at) VALUES (?, ?, ?, ?, ?)",
            (path, kind, artifact_id, actor, time.time()),
        )
        db.commit()


def require_project_classification_owner(path: str) -> None:
    """Only the verified owner may change the project's category or difficulty."""
    from sigma.projects import ProjectError

    if cloud_workspaces.current() is None or cloud_auth.current_principal() is None:
        return
    with _db() as db:
        row, _actor = _membership(db, path)
        if row["owner_hash"] != _identity()[0].subject_hash:
            raise ProjectError(
                "Only the project owner can change the research category or difficulty."
            )


def require_project_title_owner(path: str) -> None:
    """The project owner alone may rename a shared project.

    Collaborators may still edit the project research description and other
    shared fields. This check belongs at the storage boundary, not just the UI.
    """
    from sigma.projects import ProjectError

    if cloud_workspaces.current() is None or cloud_auth.current_principal() is None:
        return
    with _db() as db:
        row, _actor = _membership(db, path)
        if row["owner_hash"] != _identity()[0].subject_hash:
            raise ProjectError("Only the project owner can change the project title.")


def collaborator_identity(path: str) -> str | None:
    """Verified collaborator email for durable, human-authored output metadata."""
    if cloud_workspaces.current() is None or cloud_auth.current_principal() is None:
        return None
    try:
        with _db() as db:
            _row_value, actor = _membership(db, path)
            # Creator provenance is recorded before a project is shared.
            # Otherwise inviting collaborators later would lose the owner.
            return actor
    except ValueError:
        return None


def reserve_execution_run(
    path: str,
    kind: str,
    run_id: str,
    saved_max_number: int,
    *,
    model: str,
    thinking: str,
) -> dict[str, Any] | None:
    """Reserve a stable run identity and display number before provider dispatch.

    This is the admission primitive for per-run Paper/Session persistence.
    Callers must supply the maximum number in existing saved artifacts, not a
    client-provided guess. Reservation is idempotent, never reassigns creator
    or model settings, and never reuses a number from an abandoned run.

    The legacy project-scoped execution guard must remain in place until
    checkpoints, task registries, controls and API admissions use this ledger.
    """
    from uuid import UUID

    from sigma.projects import ProjectError

    if kind not in {"paper", "session"}:
        raise ValueError("Unsupported execution kind")
    if not isinstance(run_id, str):
        raise TypeError("Run identifier must be a UUID")
    try:
        UUID(run_id)
    except ValueError as exc:
        raise ValueError("Run identifier must be a UUID") from exc
    if type(saved_max_number) is not int or saved_max_number < 0:
        raise ValueError("Saved maximum number must be nonnegative")
    if not isinstance(model, str) or not model or not isinstance(thinking, str):
        raise ValueError("Actual model and thinking must be provided")
    if cloud_workspaces.current() is None or cloud_auth.current_principal() is None:
        return None  # Local or provider-fixture state has its own numbering.

    with _db() as db:
        db.execute("BEGIN IMMEDIATE")
        _row_value, email = _membership(db, path)
        creator_hash = _identity()[0].subject_hash
        existing = db.execute(
            """SELECT run_id, number, creator_hash, creator_email, model, thinking
               FROM shared_run_reservations
               WHERE path=? AND kind=? AND run_id=?""",
            (path, kind, run_id),
        ).fetchone()
        if existing is not None:
            if existing["creator_hash"] != creator_hash:
                raise ProjectError("Only the original execution creator can resume this run.")
            status = db.execute(
                "SELECT status FROM shared_run_reservations WHERE path=? AND kind=? AND run_id=?",
                (path, kind, run_id),
            ).fetchone()
            if status is not None and status["status"] == "discarded":
                raise ProjectError("Discarded work cannot be resumed. Start a new run.")
            db.commit()
            return dict(existing)
        latest = db.execute(
            "SELECT MAX(number) FROM shared_run_reservations WHERE path=? AND kind=?",
            (path, kind),
        ).fetchone()[0]
        number = max(saved_max_number, latest or 0) + 1
        db.execute(
            """INSERT INTO shared_run_reservations
               (path, kind, run_id, number, creator_hash, creator_email,
                model, thinking, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (path, kind, run_id, number, creator_hash, email, model, thinking, time.time()),
        )
        db.commit()
        return {
            "run_id": run_id,
            "number": number,
            "creator_hash": creator_hash,
            "creator_email": email,
            "model": model,
            "thinking": thinking,
        }


def list_execution_runs(path: str, kind: str) -> list[dict[str, Any]]:
    """Authorized, bounded Paper/Session reservations for activity and recovery.

    This is a read, not an admission lock. Never poll the session/paper record
    files while holding the collaboration database transaction.
    """
    if kind not in {"paper", "session"}:
        raise ValueError("Unknown run kind")
    workspace = cloud_workspaces.current()
    if workspace is None or workspace.guest or cloud_auth.current_principal() is None:
        return []
    with _db() as db:
        if db.execute("SELECT 1 FROM shared_projects WHERE path=?", (path,)).fetchone() is None:
            return []
        _membership(db, path)
        rows = db.execute(
            """SELECT run_id, number, creator_email, model, thinking, created_at, status, artifact_id
               FROM shared_run_reservations WHERE path=? AND kind=?
               ORDER BY number""",
            (path, kind),
        ).fetchall()
        return [dict(row) for row in rows]


def execution_run(
    path: str, kind: str, run_id: str, *, operator: bool = False, missing_ok: bool = False
) -> dict[str, Any] | None:
    """A reserved run has one permanent owner, including before invitations."""
    from sigma.projects import ProjectError, project_path

    if kind not in {"paper", "session"}:
        raise ValueError("Unknown run kind")
    workspace = cloud_workspaces.current()
    if workspace is None or cloud_auth.current_principal() is None:
        return None
    if workspace.guest:
        raise ProjectError("Execution not found or access denied.")
    path = str(project_path(path))
    with _db() as db:
        _membership(db, path)
        row = db.execute(
            """SELECT run_id, number, creator_hash, creator_email, model, thinking, created_at,
                      status, artifact_id
               FROM shared_run_reservations WHERE path=? AND kind=? AND run_id=?""",
            (path, kind, run_id),
        ).fetchone()
        if row is None:
            if missing_ok:
                return None
            raise ProjectError("Execution not found or access denied.")
        if operator and row["creator_hash"] != _identity()[0].subject_hash:
            raise ProjectError("Only the original execution creator may control this run.")
        return dict(row)


def discard_execution_run(path: str, kind: str, run_id: str) -> None:
    """Tombstone an explicitly discarded unpublished run; never reuse its number."""
    from sigma.projects import ProjectError, project_path

    if kind not in {"paper", "session"}:
        raise ValueError("Unknown run kind")
    if cloud_workspaces.current() is None or cloud_auth.current_principal() is None:
        return
    path = str(project_path(path))
    with _db() as db:
        db.execute("BEGIN IMMEDIATE")
        _membership(db, path)
        changed = db.execute(
            """UPDATE shared_run_reservations SET status='discarded'
               WHERE path=? AND kind=? AND run_id=? AND creator_hash=?
               AND artifact_id IS NULL""",
            (path, kind, run_id, _identity()[0].subject_hash),
        ).rowcount
        if changed != 1:
            raise ProjectError("Only the creator can discard an unpublished execution.")
        db.commit()


def note_execution_artifact_author(path: str, kind: str, run_id: str, artifact_id: str) -> None:
    """Attribute publication to the *reserved creator*, not the current viewer."""
    if not artifact_id or kind not in {"paper", "session"}:
        raise ValueError("Invalid execution artifact attribution")
    if cloud_workspaces.current() is None:
        return
    with _db() as db:
        db.execute("BEGIN IMMEDIATE")
        _membership(db, path)
        run = db.execute(
            "SELECT creator_email FROM shared_run_reservations "
            "WHERE path=? AND kind=? AND run_id=?",
            (path, kind, run_id),
        ).fetchone()
        if run is None:
            raise ValueError("Published run has no creator reservation")
        db.execute(
            "INSERT OR IGNORE INTO shared_artifact_authors "
            "(path,kind,artifact_id,email,updated_at) VALUES (?,?,?,?,?)",
            (path, kind, artifact_id, run["creator_email"], time.time()),
        )
        db.execute(
            """UPDATE shared_run_reservations
               SET artifact_id=?,
                   status=CASE WHEN kind='paper' THEN 'complete' ELSE status END
               WHERE path=? AND kind=? AND run_id=? AND status!='discarded'""",
            (artifact_id, path, kind, run_id),
        )
        db.commit()


def require_execution_operator(
    path: str,
    kind: str,
    artifact_id: str,
    activity: str,
    *,
    require_active_lease: bool = False,
) -> None:
    """Authorize an executor independently of the owner's artifact-delete privilege."""
    from sigma.projects import ProjectError, project_path

    if cloud_workspaces.current() is None or cloud_auth.current_principal() is None:
        return
    # Check the canonical workspace ACL before reading shared authorship.
    # An uninvited account gets the normal hidden 404 instead of ValueError.
    path = str(project_path(path))
    with _db() as db:
        if db.execute("SELECT 1 FROM shared_projects WHERE path=?", (path,)).fetchone() is None:
            return  # Private, unregistered projects have no collaboration ACL.
        row, actor = _membership(db, path)
        creator = db.execute(
            "SELECT email FROM shared_artifact_authors WHERE path=? AND kind=? AND artifact_id=?",
            (path, kind, artifact_id),
        ).fetchone()
        reserved = (
            db.execute(
                "SELECT creator_hash FROM shared_run_reservations "
                "WHERE path=? AND kind=? AND run_id=?",
                (path, kind, artifact_id),
            ).fetchone()
            if kind in {"paper", "session"}
            else None
        )
        if reserved is not None:
            if reserved["creator_hash"] != _identity()[0].subject_hash:
                raise ProjectError("Only the original execution creator can control this run.")
            return
        lease = db.execute(
            "SELECT email,activity,expires_at FROM shared_leases WHERE path=?", (path,)
        ).fetchone()
        active = lease is not None and lease["expires_at"] > time.time()
        shared = (
            db.execute(
                "SELECT 1 FROM shared_collaborators WHERE path=? LIMIT 1", (path,)
            ).fetchone()
            is not None
        )
        if (
            active
            and lease is not None
            and (lease["email"] != actor or lease["activity"] != activity)
        ):
            raise ProjectError("Only the current execution owner can control this operation.")
        if require_active_lease and shared and not active:
            raise ProjectError("Active execution has no valid owner lease; wait for recovery.")
        if creator is not None:
            if creator["email"] != actor:
                raise ProjectError(
                    "Only the original execution creator can control this operation."
                )
        elif (
            creator is None
            and row["owner_hash"] != _identity()[0].subject_hash
            and not (require_active_lease and active)
        ):
            # Legacy creatorless work may be stopped by its live lease holder;
            # paused/restart work with no active worker is owner-only.
            raise ProjectError(
                "Execution creator is unknown; only the project owner can recover it."
            )


def paper_draft_creator(path: str, project_id: str) -> str | None:
    """Server-owned original draft identity, independent of the resumed account."""
    if cloud_workspaces.current() is None or cloud_auth.current_principal() is None:
        return None
    with _db() as db:
        if db.execute("SELECT 1 FROM shared_projects WHERE path=?", (path,)).fetchone() is None:
            return None
        _membership(db, path)
        row = db.execute(
            "SELECT email FROM shared_artifact_authors "
            "WHERE path=? AND kind='paper_draft' AND artifact_id=?",
            (path, project_id),
        ).fetchone()
        return row["email"] if row is not None else None


def reserve_paper_draft(path: str, project_id: str, *, resuming: bool) -> None:
    """Bind the original paper draft owner before dispatching any provider call."""
    from sigma.projects import ProjectError

    if cloud_workspaces.current() is None or cloud_auth.current_principal() is None:
        return
    with _db() as db:
        db.execute("BEGIN IMMEDIATE")
        if db.execute("SELECT 1 FROM shared_projects WHERE path=?", (path,)).fetchone() is None:
            db.commit()
            return
        row, actor = _membership(db, path)
        if row["project_id"] != project_id:
            raise ProjectError("Paper project identity changed before admission.")
        saved = db.execute(
            "SELECT email FROM shared_artifact_authors "
            "WHERE path=? AND kind='paper_draft' AND artifact_id=?",
            (path, project_id),
        ).fetchone()
        if resuming:
            if saved is None:
                if row["owner_hash"] != _identity()[0].subject_hash:
                    raise ProjectError("Legacy paper draft can only be recovered by the owner.")
                # An uncredited legacy draft remains owner-controlled.
            elif saved["email"] != actor:
                raise ProjectError("Only the original paper creator can resume this draft.")
        else:
            db.execute(
                "INSERT INTO shared_artifact_authors "
                "(path,kind,artifact_id,email,updated_at) VALUES (?, 'paper_draft', ?, ?, ?) "
                "ON CONFLICT(path,kind,artifact_id) DO UPDATE SET "
                "email=excluded.email,updated_at=excluded.updated_at",
                (path, project_id, actor, time.time()),
            )
        db.commit()


def require_paper_draft_operator(
    path: str, project_id: str, *, controlling_active: bool = False
) -> None:
    """Allow destructive draft operations only for its original creator."""
    from sigma.projects import ProjectError

    if cloud_workspaces.current() is None or cloud_auth.current_principal() is None:
        return
    with _db() as db:
        if db.execute("SELECT 1 FROM shared_projects WHERE path=?", (path,)).fetchone() is None:
            return
        row, actor = _membership(db, path)
        saved = db.execute(
            "SELECT email FROM shared_artifact_authors "
            "WHERE path=? AND kind='paper_draft' AND artifact_id=?",
            (path, project_id),
        ).fetchone()
        if saved is not None and saved["email"] != actor:
            raise ProjectError("Only the original paper creator can change unfinished paper work.")
        if saved is None and row["owner_hash"] != _identity()[0].subject_hash:
            lease = db.execute(
                "SELECT email,activity,expires_at FROM shared_leases WHERE path=?", (path,)
            ).fetchone()
            live_holder = (
                controlling_active
                and lease is not None
                and lease["email"] == actor
                and lease["activity"] == "Paper generation"
                and lease["expires_at"] > time.time()
            )
            if not live_holder:
                raise ProjectError(
                    "Unattributed paper work can only be managed by the project owner."
                )


def attribute_published_paper(path: str, project_id: str, paper_id: str) -> None:
    """Record the first paper author's identity in the enclosing fenced SQLite write."""
    transaction = _current_write_transaction()
    if transaction is None or transaction[0] != str(path):
        # Unshared/local project saves do not use a collaboration transaction.
        return
    db = transaction[1]
    original = db.execute(
        "SELECT email FROM shared_artifact_authors "
        "WHERE path=? AND kind='paper_draft' AND artifact_id=?",
        (path, project_id),
    ).fetchone()
    if original is not None:
        db.execute(
            "INSERT OR IGNORE INTO shared_artifact_authors "
            "(path,kind,artifact_id,email,updated_at) VALUES (?, 'paper', ?, ?, ?)",
            (path, paper_id, original["email"], time.time()),
        )


def require_artifact_manager(
    path: str, kind: str, artifact_id: str, *, owner_terminal: bool = True
) -> None:
    """Creators manage their own artifacts; owners remove others' terminal work only."""
    from sigma.projects import ProjectError, project_path

    if cloud_workspaces.current() is None or cloud_auth.current_principal() is None:
        return
    if kind not in {"session", "paper", "answer"}:
        raise ValueError("Unknown artifact kind")
    # Validate the workspace ACL before the creator/owner lookup, including
    # forged cross-workspace deletes for Papers, Sessions, and Q/A.
    path = str(project_path(path))
    with _db() as db:
        if db.execute("SELECT 1 FROM shared_projects WHERE path=?", (path,)).fetchone() is None:
            return  # Unregistered private projects have no collaboration ACL.
        row, actor = _membership(db, path)
        creator = db.execute(
            "SELECT email FROM shared_artifact_authors WHERE path=? AND kind=? AND artifact_id=?",
            (path, kind, artifact_id),
        ).fetchone()
        if creator is not None and creator["email"] == actor:
            return
        if row["owner_hash"] == _identity()[0].subject_hash and owner_terminal:
            # Ownership of the project is not ownership of a running or
            # recoverable collaborator execution.
            if kind == "session" and re.fullmatch(
                r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", artifact_id
            ):
                from sigma import research_sessions

                record = research_sessions._read(path, artifact_id)
                if record.get("status") not in {"ended", "completed"}:
                    raise ProjectError(
                        "The project owner may remove another creator's Session only after it ends."
                    )
            elif kind == "paper" and re.fullmatch(r"[0-9a-f]{32}", artifact_id):
                from sigma import papers

                published = papers.get_paper(path, artifact_id, include_tex=False)
                run_id = published.get("generation", {}).get("progress_run_id")
                if isinstance(run_id, str) and len(run_id) == 32:
                    with papers.paper_run_scope(run_id):
                        progress = papers.progress_status(path)
                    if progress is not None and progress.get("status") in {"active", "queued"}:
                        raise ProjectError(
                            "The project owner cannot remove another creator's active Paper."
                        )
            return
        raise ProjectError(
            "Only the creator may remove unfinished work. "
            "The project owner may remove finished or ended work."
        )


def leave_project(path: str, expected_project_id: str) -> None:
    """Leave the collaboration using the same revision-fenced settings mutation."""
    from sigma.projects import ProjectError, inspect_project

    view = inspect_project(path)
    if view.project.id != expected_project_id:
        raise ProjectError("Project changed. Refresh My Work and try again.")
    data = summary(view.path, verify_revision=True)
    actor = data.get("you")
    if not actor or data.get("owner") == actor or actor not in data["collaborators"]:
        raise ProjectError("Only a collaborator can stop collaborating on this project.")
    save_settings(
        view.path,
        data["revision"],
        [address for address in data["collaborators"] if address != actor],
        data["model"],
        data["thinking"],
        view.project.title,
    )


@contextmanager
def bind_session_control_lease(
    path: str, activity: str, *, require_active_lease: bool = False
) -> Iterator[None]:
    """Bind a control request to its own active execution without transferring ownership.

    Cancellation requests arrive independently from the background worker.
    Only the currently verified holder of the project lease can borrow its
    token to stop/pause the exact kind of operation they started.
    """
    from sigma.projects import ProjectError

    if cloud_workspaces.current() is None or cloud_auth.current_principal() is None:
        # Non-cloud/local test mode has no authenticated collaboration lease.
        yield
        return
    lease_token: str | None = None
    with _db() as db:
        registered = (
            db.execute("SELECT 1 FROM shared_projects WHERE path=?", (path,)).fetchone() is not None
        )
        if registered:
            _row_value, actor = _membership(db, path)
            lease = db.execute(
                "SELECT token,email,activity,expires_at FROM shared_leases WHERE path=?",
                (path,),
            ).fetchone()
            has_members = (
                db.execute(
                    "SELECT 1 FROM shared_collaborators WHERE path=? LIMIT 1", (path,)
                ).fetchone()
                is not None
            )
            if lease is not None and lease["expires_at"] > time.time():
                if lease["email"] != actor or lease["activity"] != activity:
                    raise ProjectError(
                        f"Project is being used by {lease['email']} ({lease['activity']}). "
                        "Wait for that activity to finish."
                    )
                lease_token = lease["token"]
            elif require_active_lease and has_members:
                raise ProjectError("Active execution has no valid owner lease; wait for recovery.")
    with bind_lease(path, lease_token):
        yield


def model_settings(path: str) -> dict[str, str] | None:
    if cloud_workspaces.current() is None or cloud_auth.current_principal() is None:
        return None
    with _db() as db:
        # Unregistered private projects have no shared model configuration.
        # Their research must not fail due to missing collaboration metadata.
        if db.execute("SELECT 1 FROM shared_projects WHERE path=?", (path,)).fetchone() is None:
            return None
        row, _email = _membership(db, path)
        shared = db.execute(
            "SELECT 1 FROM shared_collaborators WHERE path=? LIMIT 1", (path,)
        ).fetchone()
        return {"ai_model": row["model"], "reasoning_effort": row["thinking"]} if shared else None


def require_edit_revision(path: str, expected: int | None) -> None:
    """Prevent unversioned legacy settings clients from bypassing shared-project CAS."""
    from sigma.projects import ProjectError

    transaction = _current_write_transaction()
    if transaction is not None and transaction[0] == str(path):
        db = transaction[1]
        row = _row(db, str(path))
        shared = (
            db.execute(
                "SELECT 1 FROM shared_collaborators WHERE path=? LIMIT 1", (str(path),)
            ).fetchone()
            is not None
        )
    elif cloud_workspaces.current() is not None:
        with _db() as db:
            row = db.execute("SELECT * FROM shared_projects WHERE path=?", (str(path),)).fetchone()
            if row is None:
                return
            shared = (
                db.execute(
                    "SELECT 1 FROM shared_collaborators WHERE path=? LIMIT 1", (str(path),)
                ).fetchone()
                is not None
            )
    else:
        return
    if shared and expected is None:
        raise ProjectError("Shared project settings require a current revision. Reopen settings.")
    if expected is not None and (
        type(expected) is not int or expected < 0 or row["revision"] != expected
    ):
        raise ProjectError(
            f"Project was saved by {row['last_writer']}. Reopen it and redo your changes."
        )


def require_revision(path: str, expected: int) -> None:
    if type(expected) is not int or expected < 0:
        raise ValueError("Project revision is missing or invalid.")
    with _db() as db:
        db.execute("BEGIN IMMEDIATE")
        _membership(db, path)
        _reconcile_project_digest(db, path)
        row = _row(db, path)
        db.commit()
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
    *,
    allow_active_lease: bool = False,
) -> dict[str, Any]:
    """Atomically update ACL metadata; allow revocation during active research."""
    from sigma.projects import ProjectError

    if not isinstance(collaborators, list) or len(collaborators) > 50:
        raise ProjectError("A project supports at most 50 collaborators.")
    try:
        emails = [normalize_collaborator(item) for item in collaborators]
    except (TypeError, ValueError) as exc:
        raise ProjectError(str(exc)) from exc
    if len(set(emails)) != len(emails):
        raise ProjectError("Each collaborator may appear only once.")
    with write_guard(path, expected, allow_acl_mutation=allow_active_lease) as db:
        if db is None:
            raise ProjectError("Collaboration is not available for this project.")
        row, actor = _membership(db, path)
        if row["owner_email"] in emails:
            raise ProjectError("The project owner is already included automatically.")
        membership = {
            member["email"]: member["added_by"]
            for member in db.execute(
                "SELECT email,added_by FROM shared_collaborators WHERE path=?", (path,)
            )
        }
        previous = set(membership)
        new_members = set(emails)
        removed = previous - new_members
        is_owner = row["owner_hash"] == _identity()[0].subject_hash
        for member in removed:
            if not is_owner and membership[member] != actor and member != actor:
                raise ProjectError(
                    "Only the owner, the inviter, or the account itself can remove a collaborator."
                )
        # User-specific model preferences must never be written by shared settings.
        changed = new_members != previous
        if changed:
            db.executemany(
                "DELETE FROM shared_collaborators WHERE path=? AND email=?",
                [(path, member) for member in sorted(removed)],
            )
            db.executemany(
                "INSERT INTO shared_collaborators (path,email,added_by) VALUES (?,?,?)",
                [(path, member, actor) for member in sorted(new_members - previous)],
            )
            db.execute(
                "UPDATE shared_projects SET last_writer=? WHERE path=?",
                (actor, path),
            )
            for member in previous - new_members:
                db.execute("DELETE FROM shared_leases WHERE path=? AND email=?", (path, member))
            for recipient in sorted(previous ^ new_members):
                db.execute(
                    """INSERT INTO shared_email_outbox
                    (id,recipient,project_path,project_title,event,created_at)
                    VALUES (?,?,?,?,?,?)""",
                    (
                        uuid4().hex,
                        recipient,
                        path,
                        title,
                        "added" if recipient in new_members else "removed",
                        time.time(),
                    ),
                )
        return {"changed": changed, "revision": expected + 1}


def note_change(path: str) -> None:
    """Record a validated mutation (or join an enclosing write transaction)."""
    with write_guard(path):
        pass


def has_invited_collaborator(email: str) -> bool:
    """Check a verified Google email's invitation independently of owner login.

    Used only by local Google authentication to admit a project-only invitee
    as a member. Individual project access still requires the exact ACL.
    """
    try:
        normalized = normalize_collaborator(email)
    except (TypeError, ValueError):
        return False
    with _db() as db:
        return (
            db.execute(
                "SELECT 1 FROM shared_collaborators WHERE email=? LIMIT 1",
                (normalized,),
            ).fetchone()
            is not None
        )


def shared_listing() -> tuple[list[dict[str, str]], set[str]]:
    """Read collaborator membership and shared-owner paths in one DB snapshot.

    Saved/Recent opens frequently. Using two separately initialized SQLite
    connections amplified schema contention and the cost of opening Home.
    """
    workspace = cloud_workspaces.current()
    if workspace is None or workspace.guest:
        return [], set()
    try:
        owner, email = _identity()
    except ValueError:
        return [], set()
    with _db() as db:
        invited = [
            {"path": row["path"], "id": row["project_id"]}
            for row in db.execute(
                """SELECT p.path,p.project_id FROM shared_projects p
                JOIN shared_collaborators c ON c.path=p.path
                WHERE c.email=? ORDER BY p.updated_at DESC""",
                (email,),
            )
        ]
        visible_shared_paths = {
            row["path"]
            for row in db.execute(
                """SELECT p.path FROM shared_projects p
                WHERE EXISTS (SELECT 1 FROM shared_collaborators c WHERE c.path=p.path)
                AND (p.owner_hash=? OR EXISTS (
                    SELECT 1 FROM shared_collaborators c
                    WHERE c.path=p.path AND c.email=?
                ))""",
                (owner.subject_hash, email),
            )
        }
        return invited, visible_shared_paths


def shared_project_paths() -> set[str]:
    """Paths with collaborators visible to their owner or a listed collaborator."""
    try:
        workspace, email = _identity()
    except ValueError:
        return set()
    with _db() as db:
        return {
            row["path"]
            for row in db.execute(
                """SELECT p.path FROM shared_projects p
                WHERE EXISTS (SELECT 1 FROM shared_collaborators c WHERE c.path=p.path)
                AND (p.owner_hash=? OR EXISTS (
                    SELECT 1 FROM shared_collaborators c
                    WHERE c.path=p.path AND c.email=?
                ))""",
                (workspace.subject_hash, email),
            )
        }


def shared_with_me() -> list[dict[str, str]]:
    workspace = cloud_workspaces.current()
    if workspace is None or workspace.guest:
        return []
    try:
        _ws, email = _identity()
    except ValueError:
        # Without verified identity, no external projects are visible.
        return []
    with _db() as db:
        return [
            {"path": row["path"], "id": row["project_id"]}
            for row in db.execute(
                """SELECT p.path,p.project_id FROM shared_projects p JOIN shared_collaborators c
                ON c.path=p.path WHERE c.email=? ORDER BY p.updated_at DESC""",
                (email,),
            )
        ]


def acquire_lease(path: str, activity: str) -> str | None:
    """Atomic, renewable per-project single-operator admission. Unshared projects retain normal behavior."""
    if cloud_workspaces.current() is None:
        return None
    from sigma.projects import inspect_project

    register_owner(inspect_project(path))
    if activity not in {"Research session", "Paper generation", "Project deletion"}:
        raise ValueError("Unsupported collaboration activity.")
    from sigma.projects import ProjectError

    with _db() as db:
        db.execute("BEGIN IMMEDIATE")
        registered = db.execute("SELECT 1 FROM shared_projects WHERE path=?", (path,)).fetchone()
        if registered is None:
            db.commit()
            return None
        row, actor = _membership(db, path)
        if activity == "Project deletion":
            workspace, _ = _identity()
            if row["owner_hash"] != workspace.subject_hash:
                raise ProjectError("Only the project owner may delete a shared project.")
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


@contextmanager
def keep_lease(path: str, token: str | None) -> Iterator[None]:
    """Renew a long-running deletion lease even when the event loop is blocked.

    The final deletion transaction independently verifies the token before
    publishing removal; a failed heartbeat cannot authorize a stale delete.
    """
    if token is None:
        yield
        return
    stopped = Event()

    def heartbeat() -> None:
        while not stopped.wait(LEASE_SECONDS / 3):
            try:
                if not renew_lease(path, token):
                    return
            except (OSError, RuntimeError, sqlite3.Error) as exc:
                LOGGER.warning("Project deletion lease renewal failed: %s", type(exc).__name__)
                return

    worker = Thread(target=heartbeat, name="sigma-deletion-lease", daemon=True)
    worker.start()
    try:
        yield
    finally:
        stopped.set()
        worker.join(timeout=1)


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


def _forget_project_locked(
    db: sqlite3.Connection, path: str, row: sqlite3.Row, title: str | None
) -> None:
    members = [
        item["email"]
        for item in db.execute("SELECT email FROM shared_collaborators WHERE path=?", (path,))
    ]
    # A successful deletion supersedes queued additions and unsent updates.
    db.execute("DELETE FROM shared_email_outbox WHERE project_path=?", (path,))
    db.execute("DELETE FROM shared_leases WHERE path=?", (path,))
    db.execute("DELETE FROM shared_collaborators WHERE path=?", (path,))
    db.execute("DELETE FROM shared_artifact_authors WHERE path=?", (path,))
    db.execute("DELETE FROM shared_projects WHERE path=?", (path,))
    now = time.time()
    db.executemany(
        """INSERT INTO shared_email_outbox
           (id,recipient,project_path,project_title,event,created_at)
           VALUES (?,?,?,?,?,?)""",
        [
            (uuid4().hex, member, path, title or row["project_id"], "removed", now)
            for member in members
        ],
    )


def forget_project(path: str, title: str | None = None) -> None:
    """Revoke the owner's deleted project and queue removal notices."""
    if cloud_workspaces.current() is None or cloud_auth.current_principal() is None:
        return
    from sigma.projects import ProjectError

    with _db() as db:
        db.execute("BEGIN IMMEDIATE")
        row, _actor = _membership(db, path)
        workspace, _ = _identity()
        if row["owner_hash"] != workspace.subject_hash:
            raise ProjectError("Only the project owner may delete a shared project.")
        _forget_project_locked(db, path, row, title)
        db.commit()


@contextmanager
def finalize_deletion(path: str, title: str) -> Iterator[None]:
    """Fence the physical deletion and ACL cleanup in the same write admission.

    Session shutdown happens before entry. Nobody can acquire a new lease
    between the final token check, filesystem removal, and ACL revocation.
    """
    if cloud_workspaces.current() is None or cloud_auth.current_principal() is None:
        yield
        return
    from sigma.projects import ProjectError

    with _db() as db:
        db.execute("BEGIN IMMEDIATE")
        try:
            row, actor = _membership(db, path)
            workspace, _ = _identity()
            if row["owner_hash"] != workspace.subject_hash:
                raise ProjectError("Only the project owner may delete a shared project.")
            _verify_fence(db, path, actor)
            yield
            _forget_project_locked(db, path, row, title)
            db.commit()
        except BaseException:
            db.rollback()
            raise


def drain_notifications() -> list[str]:
    """Send pending notices with bounded retries, backoff and crash-safe claims.

    Claims are serialized in SQLite. A stale claim can be replayed after
    a crash, so delivery is at least once in ambiguous transport failures.
    """
    if not cloud_workspaces.account_scoping_enabled():
        return []
    from sigma.mail_transport import send_message
    from sigma.progress_notifications import deep_link

    warnings: list[str] = []
    for _ in range(20):
        with _db() as db:
            db.execute("BEGIN IMMEDIATE")
            now = time.time()
            event = db.execute(
                """SELECT * FROM shared_email_outbox
                   WHERE failed_at IS NULL AND attempts < ?
                   AND (
                       (sent_at IS NULL AND retry_after <= ?)
                       OR (sent_at < 0 AND sent_at >= ?)
                   )
                   ORDER BY created_at, id LIMIT 1""",
                (MAX_NOTIFICATION_ATTEMPTS, now, -(now - 600)),
            ).fetchone()
            if event is None:
                db.commit()
                return warnings
            claim = -now
            db.execute(
                """UPDATE shared_email_outbox
                   SET sent_at=?,attempts=attempts+1 WHERE id=?""",
                (claim, event["id"]),
            )
            db.commit()

        try:
            message = EmailMessage()
            added = event["event"] == "added"
            message["Subject"] = (
                f"SIGMA: Added to {event['project_title']}"
                if added
                else f"SIGMA: Removed from {event['project_title']}"
            )
            origin = cloud_auth.config().origin
            try:
                project_link = deep_link(origin, event["project_path"]) if origin else ""
                if project_link and added:
                    project_link += "&" + urlencode(
                        {
                            "invited_email": event["recipient"],
                            "project_title": event["project_title"],
                        }
                    )
            except ValueError:
                # Malformed origins are never embedded as clickable links.
                project_link = ""
            if added:
                # The title itself is the link in HTML-capable mail clients.
                # Keep a usable plain-text alternative for text-only mail.
                body = (
                    f"You have been added as a collaborator on SIGMA project "
                    f"{event['project_title']}.\n\n"
                    + (
                        f"Open project: {project_link}\n\n"
                        if project_link
                        else "Sign in to SIGMA with this Google account to find the shared project.\n\n"
                    )
                )
                message.set_content(body)
                if project_link:
                    message.add_alternative(
                        "<p>You have been added as a collaborator on SIGMA project "
                        f'<a href="{html_escape(project_link, quote=True)}">'
                        f"{html_escape(event['project_title'])}</a>.</p>",
                        subtype="html",
                    )
            else:
                message.set_content(
                    f"You have been removed as a collaborator on SIGMA project "
                    f"“{event['project_title']}”.\n"
                )
            send_message(message, recipients=[event["recipient"]])
        except (cloud_auth.SMTPDeliveryError, RuntimeError, OSError, ValueError) as exc:
            attempts = int(event["attempts"]) + 1
            exhausted = attempts >= MAX_NOTIFICATION_ATTEMPTS
            LOGGER.warning(
                "Collaboration notice failed: %s attempt=%s exhausted=%s",
                type(exc).__name__,
                attempts,
                exhausted,
            )
            with _db() as db:
                db.execute(
                    """UPDATE shared_email_outbox
                       SET sent_at=NULL,failed_at=?,retry_after=?
                       WHERE id=? AND sent_at=?""",
                    (
                        time.time() if exhausted else None,
                        0 if exhausted else time.time() + min(3600, 60 * 2 ** (attempts - 1)),
                        event["id"],
                        claim,
                    ),
                )
            warnings.append("Some collaboration notification emails are queued for retry.")
            continue
        with _db() as db:
            db.execute(
                "UPDATE shared_email_outbox SET sent_at=? WHERE id=? AND sent_at=?",
                (time.time(), event["id"], claim),
            )
    return warnings


def retry_failed_notifications(path: str) -> int:
    """Explicitly requeue terminally failed notices for a current collaborator."""
    from sigma.projects import ProjectError

    if cloud_workspaces.current() is None:
        raise ProjectError("Collaboration notifications require verified sign-in.")
    with _db() as db:
        db.execute("BEGIN IMMEDIATE")
        _membership(db, path)
        changed = db.execute(
            """UPDATE shared_email_outbox
               SET failed_at=NULL, attempts=0, retry_after=0
               WHERE project_path=? AND failed_at IS NOT NULL AND sent_at IS NULL""",
            (path,),
        ).rowcount
        db.commit()
    return changed
