"""Per-user workspace preference for exclusive top-level project sections.

This is presentation state, not project metadata or a research-execution option.
It follows the same authenticated workspace boundary as unattended execution.
"""

from __future__ import annotations

import json
import os
import stat
import tempfile
from pathlib import Path

from sigma import research_preferences
from sigma.projects import ProjectError

PREFERENCES = ".sigma-section-layout.json"


def _read(root: Path) -> bool:
    path = root / PREFERENCES
    try:
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    except FileNotFoundError:
        return False
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or info.st_mode & 0o077:
            raise ProjectError("Section layout preferences file is unsafe")
        with os.fdopen(fd, "rb", closefd=False) as handle:
            content = handle.read(4097)
        if len(content) > 4096:
            raise ProjectError("Section layout preferences file exceeds size limit")
        raw = json.loads(content)
        if (
            not isinstance(raw, dict)
            or set(raw) != {"version", "expand_one_project_section_at_a_time"}
            or type(raw["version"]) is not int
            or raw["version"] != 1
            or type(raw["expand_one_project_section_at_a_time"]) is not bool
        ):
            raise ProjectError("Section layout preferences file is invalid")
        return raw["expand_one_project_section_at_a_time"]
    except (ValueError, UnicodeError) as exc:
        raise ProjectError("Section layout preferences file is invalid") from exc
    finally:
        os.close(fd)


def expand_one_project_section_at_a_time() -> bool:
    root = research_preferences._root()
    fd = research_preferences._lock(root)
    try:
        return _read(root)
    finally:
        os.close(fd)


def update_expand_one_project_section_at_a_time(enabled: bool) -> bool:
    if type(enabled) is not bool:
        raise ProjectError("Project section layout preference must be a boolean")
    root = research_preferences._root()
    fd = research_preferences._lock(root)
    temporary: str | None = None
    try:
        _read(root)
        output = json.dumps(
            {"version": 1, "expand_one_project_section_at_a_time": enabled},
            separators=(",", ":"),
        ).encode("utf-8")
        out, temporary = tempfile.mkstemp(prefix=".sigma-section-layout-", dir=root)
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
