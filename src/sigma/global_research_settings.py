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


def _defaults() -> dict[str, Any]:
    from sigma.model_catalog import DEFAULT_MODEL
    from sigma.research_sessions import NEW_DEFAULT_LIMITS

    return {
        "limits": dict(NEW_DEFAULT_LIMITS),
        "ai_model": DEFAULT_MODEL,
        "reasoning_effort": "high",
        "show_advanced_outcome_details": False,
    }


def load_config() -> dict[str, Any]:
    from sigma.research_sessions import DEFAULT_LIMITS, NEW_DEFAULT_LIMITS, _validate_limits

    target = _path()
    try:
        fd = os.open(target, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    except FileNotFoundError:
        return _defaults()
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
    if (
        not isinstance(raw, dict)
        or raw.get("version") != 1
        or not isinstance(raw.get("limits"), dict)
    ):
        raise ProjectError("Global research settings are invalid")
    if set(raw["limits"]) - set(NEW_DEFAULT_LIMITS):
        raise ProjectError("Global research settings contain unknown limits")
    settings = _defaults()
    stored_limits = raw["limits"]
    defaults = NEW_DEFAULT_LIMITS if stored_limits.get("scheduler_version") == 2 else DEFAULT_LIMITS
    settings["limits"] = _validate_limits({**defaults, **stored_limits})
    from sigma.model_catalog import validate_pair

    model = raw.get("ai_model", settings["ai_model"])
    effort = raw.get("reasoning_effort", settings["reasoning_effort"])
    if type(model) is not str or type(effort) is not str:
        raise ProjectError("Global research model settings are invalid")
    try:
        validate_pair(model, effort)
    except ValueError as exc:
        raise ProjectError("Global research model settings are invalid") from exc
    settings["ai_model"] = model
    settings["reasoning_effort"] = effort
    advanced = raw.get("show_advanced_outcome_details", False)
    if type(advanced) is not bool:
        raise ProjectError("Global Outcome display preference is invalid")
    settings["show_advanced_outcome_details"] = advanced
    return settings


def load() -> dict[str, Any]:
    return load_config()["limits"]


def save_config(raw: dict[str, Any]) -> dict[str, Any]:
    from sigma.model_catalog import validate_pair
    from sigma.research_sessions import DEFAULT_LIMITS, NEW_DEFAULT_LIMITS, _validate_limits

    current = load_config()
    if "limits" in raw:
        if not isinstance(raw["limits"], dict) or set(raw["limits"]) - set(NEW_DEFAULT_LIMITS):
            raise ProjectError("Global research settings contain unknown limits")
        # model_calls is derived in scheduler v2; clients editing rounds or turns
        # must not carry a stale display value into validation.
        supplied = raw["limits"]
        # Legacy callers without an explicit scheduler retain the original
        # paired-call ceiling; new Settings use scheduler v2 explicitly.
        defaults = NEW_DEFAULT_LIMITS if supplied.get("scheduler_version") == 2 else DEFAULT_LIMITS
        candidate = {**defaults, **supplied}
        if candidate.get("scheduler_version") == 2:
            candidate["model_calls"] = (
                2 * candidate["research_rounds"] * candidate["turns_per_round"]
            )
        current["limits"] = _validate_limits(candidate)
    model = raw.get("ai_model", current["ai_model"])
    effort = raw.get("reasoning_effort", current["reasoning_effort"])
    try:
        validate_pair(model, effort)
    except ValueError as exc:
        raise ProjectError("Unsupported research model or thinking level") from exc
    current["ai_model"] = model
    current["reasoning_effort"] = effort
    if "show_advanced_outcome_details" in raw:
        if type(raw["show_advanced_outcome_details"]) is not bool:
            raise ProjectError("Outcome preference must be a boolean")
        current["show_advanced_outcome_details"] = raw["show_advanced_outcome_details"]
    target = _path()
    encoded = json.dumps({"version": 1, **current}, separators=(",", ":")).encode()
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
    return current


def save(raw: dict[str, Any]) -> dict[str, Any]:
    return save_config({"limits": raw})["limits"]
