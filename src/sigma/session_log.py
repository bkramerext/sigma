"""Append-only, best-effort session diagnostics, isolated from research storage."""

from __future__ import annotations

import atexit
import fcntl
import json
import os
import queue
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
_work: queue.Queue[tuple[str, tuple[Any, ...], threading.Event | None, list[Exception] | None]] = (
    queue.Queue()
)
_worker_guard = threading.Lock()
_worker_started = False
_SECRET = re.compile(
    r"(?i)(authorization\s*:\s*bearer\s+|\bbearer\s+|\b(?:access_token|refresh_token|api_key|client_secret|password)\b\s*[=:]\s*)([^\s,;]+)"
)
_SECRET_VALUES = (
    re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b"),
    re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b"),
)


def _lock(path: Path) -> threading.Lock:
    with _locks_guard:
        return _locks.setdefault(str(path), threading.Lock())


def _root(project_file: Path) -> Path:
    workspace = cloud_workspaces.current()
    if workspace is not None:
        return workspace.path / ".sigma-session-logs"
    return project_file.parent / ".sigma-session-logs"


def _path(
    project_file: Path, project_id: str, session_id: str, root_hint: Path | None = None
) -> Path:
    # Both identifiers are server-validated UUIDs. User titles/paths never form components.
    UUID(project_id)
    UUID(session_id)
    root = root_hint or _root(project_file)
    project_dir = root / project_id
    if root.is_symlink() or project_dir.is_symlink():
        raise OSError("Session log directory is a symbolic link")
    return project_dir / f"{session_id}.md"


def subject_name_from_claim(claim: str) -> str:
    """Extract a compact subject label from the already validated model claim."""
    sentence = re.split(r"[.!?\n]", claim, maxsplit=1)[0]
    sentence = re.sub(
        r"(?i)^\s*(?:(?:the|this|our)\s+)?"
        r"(?:evidence|results|analysis|findings|claim|answer|study|research|investigation)\s+"
        r"(?:suggests?|indicates?|shows?|demonstrates?|supports?|establishes?|finds?|concludes?|is|are)\s+"
        r"(?:that\s+)?|(?:we|i)\s+(?:find|conclude|suggest|indicate|show|demonstrate|support)\s+(?:that\s+)?",
        "",
        sentence,
    )
    stopwords = {
        "a",
        "an",
        "the",
        "and",
        "or",
        "but",
        "of",
        "for",
        "by",
        "with",
        "from",
        "to",
        "in",
        "on",
        "at",
        "as",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "suggests",
        "suggest",
        "indicates",
        "indicate",
        "shows",
        "show",
        "demonstrates",
        "demonstrate",
        "supports",
        "support",
        "that",
        "which",
        "this",
        "these",
        "those",
        "it",
        "its",
        "may",
        "might",
        "can",
        "could",
        "would",
        "should",
        "has",
        "have",
        "had",
        "does",
        "do",
        "did",
        "there",
        "here",
        "under",
        "after",
        "using",
        "use",
        "based",
        "likely",
        "appears",
        "remain",
        "remains",
        "consistent",
        "claim",
        "candidate",
        "follows",
        "forms",
        "form",
        "formed",
        "finds",
        "find",
        "concludes",
        "conclude",
    }
    words = re.findall(r"[\w]+(?:[-'][\w]+)*", sentence, flags=re.UNICODE)
    selected = [word for word in words if word.casefold() not in stopwords][:4]
    label = " ".join(word.upper() if word.isupper() else word.capitalize() for word in selected)
    return label[:64].rstrip() or "Research Project"


def _short_name(project_file: Path, project_id: str, root_hint: Path | None = None) -> str:
    root = root_hint or _root(project_file)
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
    # Until an Investigator claim is available, callers receive a placeholder.
    # Do not persist the project title as a weaker substitute for an AI-derived name.
    return "Research Project"


def _save_short_name(
    project_file: Path, project_id: str, name: str, root_hint: Path | None = None
) -> None:
    root = root_hint or _root(project_file)
    directory = root / project_id
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    from sigma.ui_instance import private_directory

    private_directory(root)
    private_directory(directory)
    name_file = directory / ".short-name"
    if name_file.is_symlink():
        raise OSError("Session log project metadata is a symbolic link")
    if name_file.exists():
        return
    temporary = name_file.with_name(f".short-name-{uuid4().hex}.tmp")
    with temporary.open("x", encoding="utf-8") as stream:
        stream.write(name[:64].strip() + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    try:
        os.link(temporary, name_file)
        directory_fd = os.open(directory, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except FileExistsError:
        pass
    finally:
        temporary.unlink(missing_ok=True)


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
        value = _SECRET.sub(r"\1[REDACTED]", value)
        for pattern in _SECRET_VALUES:
            value = pattern.sub("[REDACTED]", value)
        return value
    return value


def _ensure(path: Path, project_id: str, session_id: str, session_number: int) -> None:
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
    header = f"# SIGMA Session {session_number} Log\n\nProject: `{project_id}`  \nSession: `{session_id}`\n\nEvents below are framed JSON records; payload strings preserve original multiline Markdown.\n"
    temporary = path.with_name(f".session-header-{session_id}-{uuid4().hex}.tmp")
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(header.encode())
        stream.flush()
        os.fsync(stream.fileno())
    try:
        os.link(temporary, path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except FileExistsError:
        pass
    finally:
        temporary.unlink(missing_ok=True)


def append(path_value: str, session: dict[str, Any], event: dict[str, Any]) -> None:
    """Queue a diagnostic append; disk work never runs on the research task."""
    try:
        _enqueue("append", path_value, dict(session), dict(event), _root(Path(path_value)))
    except Exception:  # noqa: BLE001 - logging must never change a research call's outcome.
        return


def record_ai_name(project_path_value: str, project_id: str, claim: str) -> None:
    try:
        _enqueue(
            "name",
            project_path_value,
            project_id,
            subject_name_from_claim(claim),
            _root(Path(project_path_value)),
        )
    except Exception:  # noqa: BLE001
        return


def _enqueue(
    kind: str,
    *args: Any,
    completion: threading.Event | None = None,
    errors: list[Exception] | None = None,
) -> None:
    global _worker_started
    with _worker_guard:
        if not _worker_started:
            threading.Thread(target=_worker, name="sigma-session-log", daemon=True).start()
            _worker_started = True
    _work.put((kind, args, completion, errors))


def _worker() -> None:
    while True:
        kind, args, completion, errors = _work.get()
        try:
            if kind == "append":
                _append_sync(*args)
            elif kind == "name":
                project_path_value, project_id, name, root_hint = args
                project_file = Path(str(project_path_value)).resolve(strict=True)
                UUID(str(project_id))
                _save_short_name(project_file, str(project_id), str(name), root_hint)
            elif kind == "delete_session":
                _delete_session_sync(*args)
            elif kind == "delete_project":
                _delete_project_sync(*args)
        except Exception as exc:  # noqa: BLE001 - worker failure never reaches research.
            if errors is not None:
                errors.append(exc)
        finally:
            _work.task_done()
            if completion is not None:
                completion.set()


def _append_sync(
    path_value: str, session: dict[str, Any], event: dict[str, Any], root_hint: Path
) -> None:
    project_file = Path(path_value).resolve(strict=True)
    project_id, session_id = str(session["project_id"]), str(session["id"])
    target = _path(project_file, project_id, session_id, root_hint)
    root_hint.mkdir(mode=0o700, parents=True, exist_ok=True)
    target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    lock = _lock(target)
    with lock:
        lockfile_fd = os.open(target.with_suffix(".lock"), os.O_CREAT | os.O_RDWR, 0o600)
        try:
            fcntl.flock(lockfile_fd, fcntl.LOCK_EX)
            _ensure(target, project_id, session_id, int(session.get("session_number", 1)))
            data = _redact(
                {"seq": _next_sequence(target), "timestamp": datetime.now(UTC).isoformat(), **event}
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
            if target.stat().st_size + len(body) + 32 > MAX_LOG_BYTES:
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
    """Read valid frames and skip torn records without changing stored bytes."""
    del repair  # Retained as a compatibility parameter; recovery is strictly read-only.
    file_size = path.stat().st_size
    base = start_offset if 0 <= start_offset <= file_size else 0
    with path.open("rb") as stream:
        stream.seek(base)
        raw = stream.read()
    marker = b"\n<!-- SIGMA_EVENT "
    terminator = b"\n<!-- END_SIGMA_EVENT -->"
    cursor = raw.find(marker)
    events: list[dict[str, Any]] = []
    while cursor >= 0:
        line_end = raw.find(b" -->\n", cursor)
        if line_end < 0:
            cursor = raw.find(marker, cursor + len(marker))
            continue
        size_text = raw[cursor + len(marker) : line_end]
        start = line_end + 5
        try:
            size = int(size_text)
        except ValueError:
            cursor = raw.find(marker, cursor + len(marker))
            continue
        end = start + size
        if end + len(terminator) > len(raw) or raw[end : end + len(terminator)] != terminator:
            cursor = raw.find(marker, cursor + len(marker))
            continue
        try:
            item = json.loads(raw[start:end])
        except (ValueError, UnicodeDecodeError):
            cursor = raw.find(marker, cursor + len(marker))
            continue
        if isinstance(item, dict):
            events.append(item)
        cursor = raw.find(marker, end + len(terminator))
    return events, file_size


def _next_sequence(path: Path) -> int:
    events, _ = _frames(path)
    return (events[-1].get("seq", len(events)) if events else 0) + 1


def _has_limit_marker(path: Path) -> bool:
    events, _ = _frames(path)
    return any(row.get("type") == "retention_limit" for row in events)


def read(path_value: str, session_id: str, after: int = 0) -> dict[str, Any]:
    _work.join()
    UUID(session_id)
    view = inspect_project(path_value)
    project_file = project_path(path_value).resolve(strict=True)
    # Project bundles keep session records internally; use the established authorized reader.
    from sigma.research_sessions import get_session

    session = get_session(path_value, session_id)
    target = _path(project_file, view.project.id, session_id)
    short_name = _short_name(project_file, view.project.id)
    lockfile_fd = os.open(target.with_suffix(".lock"), os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(lockfile_fd, fcntl.LOCK_EX)
        if not target.exists():
            _ensure(target, view.project.id, session_id, int(session.get("session_number", 1)))
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


def flush() -> None:
    """Wait for queued writes; intended for controlled shutdown and verification."""
    _work.join()


atexit.register(flush)


def delete_project(project_id: str, project_file: str | Path) -> None:
    completion = threading.Event()
    errors: list[Exception] = []
    file_path = Path(project_file)
    _enqueue(
        "delete_project",
        project_id,
        str(file_path),
        _root(file_path),
        completion=completion,
        errors=errors,
    )
    completion.wait()
    if errors:
        raise errors[0]


def _delete_project_sync(project_id: str, project_file: str | Path, root_hint: Path) -> None:
    UUID(project_id)
    root = root_hint / project_id
    if root.is_symlink():
        raise OSError("Session log project directory is a symbolic link")
    if root.exists():
        for child in root.iterdir():
            if child.is_symlink() or not (
                child.suffix in {".md", ".lock"}
                or child.name == ".short-name"
                or child.name.startswith(".short-name-")
                and child.suffix == ".tmp"
                or child.name.startswith(".session-header-")
                and child.suffix == ".tmp"
            ):
                raise OSError("Unexpected session log entry")
            child.unlink()
        root.rmdir()


def delete_session(path_value: str, project_id: str, session_id: str) -> None:
    _enqueue("delete_session", path_value, project_id, session_id, _root(Path(path_value)))


def _delete_session_sync(
    path_value: str, project_id: str, session_id: str, root_hint: Path
) -> None:
    target = _path(Path(path_value).resolve(strict=True), project_id, session_id, root_hint)
    for item in (target, target.with_suffix(".lock")):
        if item.is_symlink():
            raise OSError("Session log path is a symbolic link")
        item.unlink(missing_ok=True)
    for temporary in target.parent.glob(f".session-header-{session_id}-*.tmp"):
        if temporary.is_symlink() or not temporary.is_file():
            raise OSError("Session log temporary path is unsafe")
        temporary.unlink()


def log_path(path_value: str, project_id: str, session_id: str) -> Path:
    return _path(project_path(path_value).resolve(strict=True), project_id, session_id)
