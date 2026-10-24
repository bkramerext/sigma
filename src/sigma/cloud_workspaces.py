"""Durable per-subject private storage for authenticated cloud requests.

The module consumes the trusted ``request.state.cloud_principal`` populated by
the cloud-auth middleware. It does not parse cookies or browser identity claims.
When cloud auth is disabled, no workspace context is installed and local SIGMA
continues to use its existing project root and Recents index.
"""

from __future__ import annotations

import hashlib
import os
import re
import sqlite3
import stat
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from sigma.cloud_auth import Principal
from sigma.ui_instance import private_directory

_SAFE_ID = re.compile(r"^[0-9a-f]{32}$")


class WorkspaceUnavailable(RuntimeError):
    """Cloud workspace storage cannot safely serve the request."""


@dataclass(frozen=True)
class Workspace:
    workspace_id: str
    subject_hash: str
    path: Path
    email: str | None = None


_CURRENT: ContextVar[Workspace | None] = ContextVar("sigma_cloud_workspace", default=None)


def enabled() -> bool:
    """Cloud auth is an explicit opt-in; local SIGMA does not need cloud config."""
    enabled = os.environ.get("SIGMA_CLOUD_AUTH_ENABLED", "").strip().casefold() in {
        "1",
        "true",
        "yes",
    }
    local_auth = os.environ.get("SIGMA_CLOUD_AUTH_LOCAL", "").strip().casefold() in {
        "1",
        "true",
        "yes",
    }
    return enabled and not local_auth


def current() -> Workspace | None:
    return _CURRENT.get()


def bind(principal: Principal) -> Token[Workspace | None]:
    """Provision or load the private workspace for a verified auth principal."""
    subject = getattr(principal, "subject", None)
    if not isinstance(subject, str) or not subject or len(subject) > 255:
        raise WorkspaceUnavailable("Workspace identity is unavailable.")
    workspace = workspace_for_subject(subject)
    from dataclasses import replace

    workspace = replace(workspace, email=getattr(principal, "email", None))
    return _CURRENT.set(workspace)


def reset(token: Token[Workspace | None]) -> None:
    _CURRENT.reset(token)


def storage_root() -> Path:
    """Return the private persistent root, defaulting beside the T22.2 auth DB."""
    from sigma.projects import ROOT

    configured = os.environ.get("SIGMA_CLOUD_WORKSPACES_ROOT")
    if configured:
        candidate = Path(configured).expanduser()
    else:
        auth_home = os.environ.get("SIGMA_CLOUD_AUTH_HOME")
        if not auth_home:
            raise WorkspaceUnavailable("Private workspace storage is not configured.")
        candidate = Path(auth_home).expanduser() / "workspaces"
    if not candidate.is_absolute() or candidate == Path(candidate.anchor):
        raise WorkspaceUnavailable("Private workspace storage is not configured safely.")
    lexical = candidate
    if lexical.is_symlink():
        raise WorkspaceUnavailable("Private workspace storage is unavailable.")
    try:
        if not lexical.exists():
            parent = lexical.parent
            parent_info = parent.lstat()
            if (
                not stat.S_ISDIR(parent_info.st_mode)
                or parent_info.st_uid != os.geteuid()
                or parent_info.st_mode & 0o077
            ):
                raise WorkspaceUnavailable("Private workspace storage is unavailable.")
            lexical.mkdir(mode=0o700)
        private_directory(lexical)
        root = lexical.resolve(strict=True)
        if root.is_relative_to(ROOT.resolve()):
            raise WorkspaceUnavailable("Private workspace storage is unavailable.")
        if root.stat().st_uid != os.geteuid():
            raise WorkspaceUnavailable("Private workspace storage is unavailable.")
        return root
    except WorkspaceUnavailable:
        raise
    except (OSError, RuntimeError, ValueError) as exc:
        raise WorkspaceUnavailable("Private workspace storage is unavailable.") from exc


def _connect(root: Path) -> sqlite3.Connection:
    database = root / "workspaces.sqlite3"
    try:
        if database.is_symlink():
            raise WorkspaceUnavailable("Private workspace storage is unavailable.")
        connection = sqlite3.connect(database, timeout=30, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout=30000")
        connection.execute("PRAGMA journal_mode=DELETE")
        connection.execute(
            """CREATE TABLE IF NOT EXISTS workspaces (
                subject_hash TEXT PRIMARY KEY,
                workspace_id TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL
            )"""
        )
        os.chmod(database, 0o600)
        info = database.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or info.st_mode & 0o077:
            connection.close()
            raise WorkspaceUnavailable("Private workspace storage is unavailable.")
        return connection
    except WorkspaceUnavailable:
        raise
    except (OSError, sqlite3.Error) as exc:
        raise WorkspaceUnavailable("Private workspace storage is unavailable.") from exc


def workspace_for_subject(subject: str) -> Workspace:
    """Get a stable server-generated workspace mapping for a verified subject."""
    if not isinstance(subject, str) or not subject or len(subject) > 255:
        raise WorkspaceUnavailable("Workspace identity is unavailable.")
    root = storage_root()
    subject_hash = hashlib.sha256(b"sigma-cloud-workspace-v1\0" + subject.encode()).hexdigest()
    connection = _connect(root)
    try:
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute(
            "SELECT workspace_id FROM workspaces WHERE subject_hash=?", (subject_hash,)
        ).fetchone()
        if row is None:
            workspace_id = uuid4().hex
            path = root / workspace_id
            try:
                path.mkdir(mode=0o700)
                connection.execute(
                    "INSERT INTO workspaces(subject_hash,workspace_id,created_at) VALUES(?,?,?)",
                    (subject_hash, workspace_id, datetime.now(UTC).isoformat()),
                )
            except BaseException:
                try:
                    path.rmdir()
                except (OSError, UnboundLocalError):
                    pass
                connection.rollback()
                raise
            connection.commit()
        else:
            workspace_id = row["workspace_id"]
            if not isinstance(workspace_id, str) or not _SAFE_ID.fullmatch(workspace_id):
                raise WorkspaceUnavailable("Private workspace storage is unavailable.")
            connection.commit()
        path = root / workspace_id
        try:
            info = path.lstat()
        except OSError as exc:
            # An existing mapping with missing files may indicate data loss. Never
            # turn it into a silently fresh workspace.
            raise WorkspaceUnavailable("Private workspace storage is unavailable.") from exc
        if (
            not stat.S_ISDIR(info.st_mode)
            or info.st_uid != os.geteuid()
            or info.st_mode & 0o077
            or path.is_symlink()
        ):
            raise WorkspaceUnavailable("Private workspace storage is unavailable.")
        return Workspace(workspace_id, subject_hash, path.resolve(strict=True))
    except WorkspaceUnavailable:
        connection.rollback()
        raise
    except (OSError, sqlite3.Error) as exc:
        connection.rollback()
        raise WorkspaceUnavailable("Private workspace storage is unavailable.") from exc
    finally:
        connection.close()


def assert_project_path(value: str | Path, resolved: Path) -> None:
    """Reject paths outside the current owner root without disclosing existence."""
    workspace = current()
    if workspace is None:
        return
    try:
        original = Path(value).expanduser()
        if ".." in original.parts:
            raise ValueError("traversal")
        candidate = original if original.is_absolute() else Path.cwd() / original
        current_path = Path(candidate.anchor)
        for part in candidate.parts[1:]:
            current_path /= part
            try:
                metadata = current_path.lstat()
            except FileNotFoundError:
                continue
            if stat.S_ISLNK(metadata.st_mode):
                raise ValueError("symlink")
        if not resolved.is_relative_to(workspace.path):
            raise ValueError("owner")
    except (OSError, RuntimeError, ValueError) as exc:
        raise ValueError("Project not found or access denied.") from exc


def private_state_directory() -> Path | None:
    """Per-workspace Recent index location, or None for the unchanged local mode."""
    workspace = current()
    if workspace is None:
        return None
    path = workspace.path / ".sigma-state"
    try:
        private_directory(path)
    except (OSError, RuntimeError) as exc:
        raise WorkspaceUnavailable("Private workspace storage is unavailable.") from exc
    return path


@contextmanager
def request_scope(principal: Principal) -> Iterator[Workspace]:
    token = bind(principal)
    try:
        workspace = current()
        assert workspace is not None
        yield workspace
    finally:
        reset(token)
