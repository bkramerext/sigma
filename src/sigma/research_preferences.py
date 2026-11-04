"""Account/workspace-scoped research execution preferences (not project metadata).

The local operator or authenticated workspace owns one settings file, independent
of provider accounts and portable projects. Persist only explicit opt-in; missing
state means unattended execution is disabled.
"""

from __future__ import annotations

import fcntl
import json
import os
import stat
import tempfile
from pathlib import Path

from sigma.projects import ProjectError, projects_root

PREFERENCES = ".sigma-user-preferences.json"
LOCK = ".sigma-user-preferences.lock"


def _root() -> Path:
    root = projects_root()
    if root.is_symlink() or not root.is_dir():
        raise ProjectError("User preferences directory is unsafe")
    return root


def _lock(root: Path) -> int:
    fd = os.open(root / LOCK, os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o600)
    info = os.fstat(fd)
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or info.st_mode & 0o077:
        os.close(fd)
        raise ProjectError("User preferences lock is unsafe")
    fcntl.flock(fd, fcntl.LOCK_EX)
    return fd


def _read(root: Path) -> bool:
    path = root / PREFERENCES
    try:
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    except FileNotFoundError:
        return False
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or info.st_mode & 0o077:
            raise ProjectError("User preferences file is unsafe")
        with os.fdopen(fd, "rb", closefd=False) as handle:
            content = handle.read(4097)
        if len(content) > 4096:
            raise ProjectError("User preferences file exceeds size limit")
        raw = json.loads(content)
        if (
            not isinstance(raw, dict)
            or set(raw) != {"version", "allow_unattended_background_execution"}
            or type(raw["version"]) is not int
            or raw["version"] != 1
            or type(raw["allow_unattended_background_execution"]) is not bool
        ):
            raise ProjectError("User preferences file is invalid")
        return raw["allow_unattended_background_execution"]
    except (ValueError, UnicodeError) as exc:
        raise ProjectError("User preferences file is invalid") from exc
    finally:
        os.close(fd)


def allow_unattended_background_execution() -> bool:
    root = _root()
    fd = _lock(root)
    try:
        return _read(root)
    finally:
        os.close(fd)


def update_unattended_background_execution(enabled: bool) -> bool:
    if type(enabled) is not bool:
        raise ProjectError("Unattended background execution preference must be a boolean")
    root = _root()
    fd = _lock(root)
    temporary: str | None = None
    try:
        # Fail closed on any malformed existing setting rather than silently overwrite.
        _read(root)
        output = json.dumps(
            {"version": 1, "allow_unattended_background_execution": enabled},
            separators=(",", ":"),
        ).encode("utf-8")
        out, temporary = tempfile.mkstemp(prefix=".sigma-preferences-", dir=root)
        with os.fdopen(out, "wb") as handle:
            handle.write(output)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, root / PREFERENCES)
        temporary = None
        parent_fd = os.open(root, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(parent_fd)
        finally:
            os.close(parent_fd)
        return enabled
    finally:
        if temporary is not None:
            Path(temporary).unlink(missing_ok=True)
        os.close(fd)
