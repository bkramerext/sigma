"""Per-user research execution settings, never stored in a portable project.

Authenticated users are isolated by the same private catalog identity boundary as
Project Types. Missing files get new-user defaults; legacy project limits are
intentionally not imported.
"""
from __future__ import annotations

import json
import os
import stat
import tempfile
from pathlib import Path
from typing import Any

from sigma import project_types
from sigma.projects import ProjectError

_FILENAME = ".sigma-global-research-settings.json"

def _path() -> Path:
    # The project types store already resolves trusted principal identity in
    # hosted, local signed-in, and single-user anonymous deployment modes.
    return project_types._store_path().parent / _FILENAME

def load() -> dict[str, Any]:
    from sigma.research_sessions import NEW_DEFAULT_LIMITS, _validate_limits

    target = _path()
    try:
        fd = os.open(target, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    except FileNotFoundError:
        return dict(NEW_DEFAULT_LIMITS)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077 or info.st_size > 4096:
            raise ProjectError("Global research settings file is unsafe")
        with os.fdopen(fd, "rb", closefd=False) as handle:
            raw = json.loads(handle.read(4097))
    except (ValueError, OSError) as exc:
        raise ProjectError("Global research settings are invalid") from exc
    finally:
        os.close(fd)
    if not isinstance(raw, dict) or raw.get("version") != 1 or not isinstance(raw.get("limits"), dict):
        raise ProjectError("Global research settings are invalid")
    if set(raw["limits"]) - set(NEW_DEFAULT_LIMITS):
        raise ProjectError("Global research settings contain unknown limits")
    return _validate_limits({**NEW_DEFAULT_LIMITS, **raw["limits"]})

def save(raw: dict[str, Any]) -> dict[str, Any]:
    from sigma.research_sessions import NEW_DEFAULT_LIMITS, _validate_limits

    limits = _validate_limits({**NEW_DEFAULT_LIMITS, **raw})
    target = _path()
    # Validate existing data instead of overwriting corruption.
    load()
    encoded = json.dumps({"version": 1, "limits": limits}, separators=(",", ":")).encode()
    fd, tmp = tempfile.mkstemp(prefix=".sigma-global-research-", dir=target.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(tmp, 0o600)
        os.replace(tmp, target)
        parent_fd = os.open(target.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(parent_fd)
        finally:
            os.close(parent_fd)
    finally:
        Path(tmp).unlink(missing_ok=True)
    return limits
