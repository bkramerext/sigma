"""Append-only, best-effort session diagnostics, isolated from research storage."""

from __future__ import annotations

import fcntl
import json
import os
import re
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from sigma import cloud_workspaces
from sigma.projects import inspect_project, project_path

MAX_LOG_BYTES = 32 * 1024 * 1024
MAX_EVENT_BYTES = 18 * 1024 * 1024
_locks_guard = threading.Lock()
_locks: dict[str, threading.Lock] = {}
_SECRET = re.compile(
    r"(?i)(authorization\s*:\s*bearer\s+|\b(?:access_token|refresh_token|api_key|client_secret|password)\b\s*[=:]\s*)([^\s,;]+)"
)


def _lock(path: Path) -> threading.Lock:
    with _locks_guard:
        return _locks.setdefault(str(path), threading.Lock())


def _root(project_file: Path) -> Path:
    workspace = cloud_workspaces.current()
    if workspace is not None:
        return workspace.path / ".sigma-session-logs"
    return project_file.parent / ".sigma-session-logs"


def _path(project_file: Path, project_id: str, session_id: str) -> Path:
    # Both identifiers are server-validated UUIDs. User titles/paths never form components.
    UUID(project_id)
    UUID(session_id)
    root = _root(project_file)
    project_dir = root / project_id
    if root.is_symlink() or project_dir.is_symlink():
        raise OSError("Session log directory is a symbolic link")
    return project_dir / f"{session_id}.md"


def _short_name(project_file: Path, project_id: str, title: str) -> str:
    root = _root(project_file)
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    from sigma.ui_instance import private_directory

    private_directory(root)
    directory = root / project_id
    directory.mkdir(mode=0o700, exist_ok=True)
    private_directory(directory)
    name_file = directory / ".short-name"
    if name_file.is_symlink():
        raise OSError("Session log project metadata is a symbolic link")
    if name_file.is_file() and not name_file.is_symlink():
        value = name_file.read_text(encoding="utf-8").strip()
        if value:
            return value
    words = re.findall(r"[\w]+(?:[-'][\w]+)*", title, flags=re.UNICODE)
    stopwords = {
        "a",
        "an",
        "the",
        "project",
        "research",
        "why",
        "what",
        "when",
        "where",
        "how",
        "who",
        "do",
        "does",
        "did",
        "is",
        "are",
        "was",
        "were",
        "of",
        "for",
        "by",
        "with",
        "from",
        "to",
        "in",
        "on",
        "temporarily",
        "lose",
        "loses",
        "form",
        "forms",
        "formed",
    }
    words = [word for word in words if word.casefold() not in stopwords]
    value = " ".join(words[:4]) or "Research Project"
    temporary = name_file.with_name(f".short-name-{uuid4().hex}.tmp")
    with temporary.open("x", encoding="utf-8") as stream:
        stream.write(value + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    try:
        os.link(temporary, name_file)
    except FileExistsError:
        value = name_file.read_text(encoding="utf-8").strip()
    finally:
        temporary.unlink(missing_ok=True)
    return value


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            if re.search(
                r"(?i)(authorization|cookie|access[_-]?token|refresh[_-]?token|client[_-]?secret|api[_-]?key|password|credential)",
                str(key),
            ):
                result[str(key)] = "[REDACTED]"
            else:
                result[str(key)] = _redact(item)
        return result
    if isinstance(value, list):
        return [_redact(item) for item in value]
    if isinstance(value, str):
        return _SECRET.sub(r"\1[REDACTED]", value)
    return value


def _ensure(
    path: Path, project_id: str, session_id: str, session_number: int, short_name: str
) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    from sigma.ui_instance import private_directory

    private_directory(path.parent.parent)
    private_directory(path.parent)
    if path.exists():
        info = path.lstat()
        if (
            not path.is_file()
            or path.is_symlink()
            or info.st_uid != os.geteuid()
            or info.st_mode & 0o077
        ):
            raise OSError("Session log file has unsafe ownership or permissions")
        return
    header = f"# {short_name}, Session {session_number}\n\nProject: `{project_id}`  \nSession: `{session_id}`\n\nEvents below are framed JSON records; payload strings preserve original multiline Markdown.\n"
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        return
    with os.fdopen(fd, "wb") as stream:
        stream.write(header.encode())
        stream.flush()
        os.fsync(stream.fileno())


def append(path_value: str, session: dict[str, Any], event: dict[str, Any]) -> None:
    """Append one complete framed event; any diagnostic failure is intentionally swallowed."""
    try:
        project_file = project_path(path_value).resolve(strict=True)
        target = _path(project_file, str(session["project_id"]), str(session["id"]))
        name = _short_name(
            project_file,
            str(session["project_id"]),
            str(session.get("project_title") or "Research Project"),
        )
        number = int(session.get("session_number", 1))
        lock = _lock(target)
        with lock:
            lockfile = target.with_suffix(".lock")
            lockfile_fd = os.open(lockfile, os.O_CREAT | os.O_RDWR, 0o600)
            try:
                fcntl.flock(lockfile_fd, fcntl.LOCK_EX)
                _ensure(target, str(session["project_id"]), str(session["id"]), number, name)
                data = _redact(
                    {
                        "seq": _next_sequence(target),
                        "timestamp": datetime.now(UTC).isoformat(),
                        **event,
                    }
                )
                body = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
                if len(body) > MAX_EVENT_BYTES:
                    data = {
                        "seq": data["seq"],
                        "timestamp": data["timestamp"],
                        "type": "event_omitted",
                        "reason": "event exceeds 18 MiB bound",
                    }
                    body = json.dumps(data, separators=(",", ":")).encode()
                size = target.stat().st_size
                if size + len(body) + 32 > MAX_LOG_BYTES:
                    if not _has_limit_marker(target):
                        _append_frame(
                            target,
                            {
                                "seq": _next_sequence(target),
                                "timestamp": datetime.now(UTC).isoformat(),
                                "type": "retention_limit",
                                "message": "32 MiB session log limit reached; later events are omitted.",
                            },
                        )
                    return
                _append_frame(target, data)
            finally:
                fcntl.flock(lockfile_fd, fcntl.LOCK_UN)
                os.close(lockfile_fd)
    except Exception:  # noqa: BLE001 - logging must never change a research call's outcome.
        # Diagnostics are best-effort; never escape into provider/session execution.
        return


def _append_frame(path: Path, value: dict[str, Any]) -> None:
    body = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    with path.open("ab") as stream:
        stream.write(f"\n<!-- SIGMA_EVENT {len(body)} -->\n".encode())
        stream.write(body)
        stream.write(b"\n<!-- END_SIGMA_EVENT -->")
        stream.flush()
        os.fsync(stream.fileno())


def _frames(
    path: Path, repair: bool = False, start_offset: int = 0
) -> tuple[list[dict[str, Any]], int]:
    file_size = path.stat().st_size
    base = start_offset if 0 <= start_offset <= file_size else 0
    with path.open("rb") as stream:
        stream.seek(base)
        raw = stream.read()
    marker = b"\n<!-- SIGMA_EVENT "
    cursor = raw.find(marker)
    events: list[dict[str, Any]] = []
    good = base + len(raw) if cursor < 0 else base + cursor
    while cursor >= 0:
        line_end = raw.find(b" -->\n", cursor)
        if line_end < 0:
            good = base + cursor
            break
        try:
            size = int(raw[cursor + len(marker) : line_end])
        except ValueError:
            good = base + cursor
            break
        start = line_end + 5
        end = start + size
        terminator = b"\n<!-- END_SIGMA_EVENT -->"
        if end + len(terminator) > len(raw) or raw[end : end + len(terminator)] != terminator:
            good = base + cursor
            break
        try:
            item = json.loads(raw[start:end])
        except (ValueError, UnicodeDecodeError):
            good = base + cursor
            break
        if isinstance(item, dict):
            events.append(item)
        cursor = raw.find(marker, end + len(terminator))
        good = base + len(raw) if cursor < 0 else base + cursor
    if repair and good < file_size:
        with path.open("r+b") as stream:
            stream.truncate(good)
            stream.flush()
            os.fsync(stream.fileno())
    return events, good


def _next_sequence(path: Path) -> int:
    events, _ = _frames(path, repair=True)
    return (events[-1].get("seq", len(events)) if events else 0) + 1


def _has_limit_marker(path: Path) -> bool:
    events, _ = _frames(path, repair=True)
    return any(row.get("type") == "retention_limit" for row in events)


def read(path_value: str, session_id: str, after: int = 0) -> dict[str, Any]:
    UUID(session_id)
    view = inspect_project(path_value)
    project_file = project_path(path_value).resolve(strict=True)
    # Project bundles keep session records internally; use the established authorized reader.
    from sigma.research_sessions import get_session

    session = get_session(path_value, session_id)
    target = _path(project_file, view.project.id, session_id)
    short_name = _short_name(project_file, view.project.id, view.project.title)
    lockfile_fd = os.open(target.with_suffix(".lock"), os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(lockfile_fd, fcntl.LOCK_EX)
        if not target.exists():
            _ensure(
                target,
                view.project.id,
                session_id,
                int(session.get("session_number", 1)),
                short_name,
            )
        fcntl.flock(lockfile_fd, fcntl.LOCK_SH)
        events, cursor = _frames(target, start_offset=max(0, after))
    finally:
        fcntl.flock(lockfile_fd, fcntl.LOCK_UN)
        os.close(lockfile_fd)
    return {
        "events": events,
        "cursor": cursor,
        "short_name": short_name,
        "session": {
            "id": session_id,
            "number": session.get("session_number"),
            "status": session.get("status"),
        },
    }


def delete_project(project_id: str, project_file: str | Path) -> None:
    UUID(project_id)
    root = _root(Path(project_file).resolve(strict=False)) / project_id
    if root.is_symlink():
        raise OSError("Session log project directory is a symbolic link")
    if root.exists():
        for child in root.iterdir():
            if child.is_symlink() or not (
                child.suffix in {".md", ".lock"}
                or child.name == ".short-name"
                or child.name.startswith(".short-name-")
                and child.suffix == ".tmp"
            ):
                raise OSError("Unexpected session log entry")
            child.unlink()
        root.rmdir()


def delete_session(path_value: str, project_id: str, session_id: str) -> None:
    target = _path(project_path(path_value).resolve(strict=True), project_id, session_id)
    for item in (target, target.with_suffix(".lock")):
        if item.is_symlink():
            raise OSError("Session log path is a symbolic link")
        item.unlink(missing_ok=True)


def log_path(path_value: str, project_id: str, session_id: str) -> Path:
    return _path(project_path(path_value).resolve(strict=True), project_id, session_id)
