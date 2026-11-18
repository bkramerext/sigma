"""Private user-level Scratchpad notes, independent of individual projects."""

from __future__ import annotations

import json
import os
import stat
import tempfile
from pathlib import Path
from typing import Any

from sigma import research_preferences
from sigma.projects import ProjectError

FILENAME = ".sigma-scratchpad.json"
MAX_ENTRIES = 100
MAX_CHARS = 50_000
MAX_BYTES = MAX_ENTRIES * MAX_CHARS * 4 + 4096


def _validate(entries: Any) -> list[dict[str, str]]:
    if not isinstance(entries, list) or len(entries) > MAX_ENTRIES:
        raise ProjectError("Scratchpad must have at most 100 notes.")
    seen: set[str] = set()
    result: list[dict[str, str]] = []
    for item in entries:
        if (
            not isinstance(item, dict)
            or set(item) != {"id", "text"}
            or not isinstance(item["id"], str)
            or len(item["id"]) != 32
            or any(char not in "0123456789abcdef" for char in item["id"])
            or item["id"] in seen
            or not isinstance(item["text"], str)
            or len(item["text"]) > MAX_CHARS
            or "\x00" in item["text"]
        ):
            raise ProjectError("Invalid Scratchpad note.")
        seen.add(item["id"])
        result.append({"id": item["id"], "text": item["text"]})
    return result


def _read(root: Path) -> list[dict[str, str]]:
    try:
        fd = os.open(root / FILENAME, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    except FileNotFoundError:
        return []
    try:
        info = os.fstat(fd)
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.geteuid()
            or info.st_mode & 0o077
            or info.st_size > MAX_BYTES
        ):
            raise ProjectError("Scratchpad file is unsafe.")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            data = stream.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise ProjectError("Scratchpad file is too large.")
        raw = json.loads(data)
        if not isinstance(raw, dict) or set(raw) != {"version", "entries"} or raw["version"] != 1:
            raise ProjectError("Scratchpad file is invalid.")
        return _validate(raw["entries"])
    except (ValueError, UnicodeError) as exc:
        raise ProjectError("Scratchpad file is invalid.") from exc
    finally:
        os.close(fd)


def current() -> dict[str, list[dict[str, str]]]:
    root = research_preferences._root()
    fd = research_preferences._lock(root)
    try:
        return {"entries": _read(root)}
    finally:
        os.close(fd)


def save(
    entries: list[dict[str, str]], expected: list[dict[str, str]]
) -> dict[str, list[dict[str, str]]]:
    """Use one user-scoped file lock and compare the prior version before replacing."""
    wanted = _validate(entries)
    baseline = _validate(expected)
    root = research_preferences._root()
    fd = research_preferences._lock(root)
    temp: str | None = None
    try:
        existing = _read(root)
        if existing != baseline:
            raise ProjectError("Scratchpad changed elsewhere. Reopen User Settings before saving.")
        data = json.dumps({"version": 1, "entries": wanted}, ensure_ascii=False).encode("utf-8")
        out, temp = tempfile.mkstemp(prefix=".sigma-scratchpad-", dir=root)
        with os.fdopen(out, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, root / FILENAME)
        temp = None
        parent = os.open(root, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(parent)
        finally:
            os.close(parent)
        return {"entries": wanted}
    finally:
        if temp is not None:
            Path(temp).unlink(missing_ok=True)
        os.close(fd)
