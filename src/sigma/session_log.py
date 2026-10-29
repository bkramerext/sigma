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
_queues_guard = threading.RLock()
_queues: dict[
    str, queue.Queue[tuple[str, tuple[Any, ...], threading.Event | None, list[Exception] | None]]
] = {}
_queue_running: set[str] = set()
_closing_projects: set[str] = set()
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


_NAME_STOPWORDS = {
    "a",
    "an",
    "why",
    "how",
    "what",
    "when",
    "where",
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


def subject_name_from_context(title: str, problem: str, claim: str) -> str | None:
    """Use an existing validated claim to corroborate a project-context subject.

    Names come from the project title/problem, never from generic claim framing or
    incidental result words. The existing AI response is used only as evidence
    that a project subject is relevant; no schema or provider call is added.
    """

    def subject_tokens(value: str) -> list[tuple[str, str]]:
        words = re.findall(r"[\w]+(?:[-'][\w]+)*", value, flags=re.UNICODE)
        return [
            (word.casefold().rstrip("s"), word)
            for word in words
            if word.casefold() not in _NAME_STOPWORDS
            and word.casefold().rstrip("s") not in _NAME_STOPWORDS
            and len(word) >= 3
        ]

    claim_tokens = [word for word, _original in subject_tokens(claim)]
    for context in (title, problem):
        tokens = subject_tokens(context)
        for width in range(2, min(4, len(tokens)) + 1):
            for start in range(len(tokens) - width + 1):
                candidate = [word for word, _original in tokens[start : start + width]]
                if any(
                    claim_tokens[offset : offset + width] == candidate
                    for offset in range(len(claim_tokens) - width + 1)
                ):
                    words = [original for _word, original in tokens[start : start + width]]
                    return " ".join(
                        word.upper() if word.isupper() else word.capitalize() for word in words
                    )[:64]
    return None


def fallback_project_name(title: str, problem: str = "") -> str:
    """Return a deterministic, title-derived display fallback (not AI naming)."""
    words = re.findall(r"[\w]+(?:[-'][\w]+)*", title, flags=re.UNICODE)
    selected = [
        word
        for word in words
        if word.casefold() not in _NAME_STOPWORDS
        and word.casefold().rstrip("s") not in _NAME_STOPWORDS
    ]
    if len(selected) < 2:
        selected.extend(
            word
            for word in re.findall(r"[\w]+(?:[-'][\w]+)*", problem, flags=re.UNICODE)
            if word.casefold().rstrip("s") not in _NAME_STOPWORDS
            and word.casefold() not in {item.casefold() for item in selected}
        )
    selected = selected[:2]
    if not selected:
        return "Research Project"
    return " ".join(word.upper() if word.isupper() else word.capitalize() for word in selected)


def _short_name(
    project_file: Path,
    project_id: str,
    root_hint: Path | None = None,
    title: str = "",
    problem: str = "",
) -> str:
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
    # This is a display-only fallback. The first matching validated claim is
    # persisted separately as the stable project name without changing schema.
    return fallback_project_name(title, problem)


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


def record_ai_name(
    project_path_value: str, project_id: str, title: str, problem: str, claim: str
) -> None:
    try:
        name = subject_name_from_context(title, problem, claim)
        if name is None:
            return
        _enqueue(
            "name",
            project_path_value,
            project_id,
            name,
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
    key = _queue_key(kind, args)
    project_dir = _project_dir_for(kind, args)
    with _queues_guard:
        if project_dir is not None and str(project_dir) in _closing_projects:
            if completion is not None:
                if errors is not None:
                    errors.append(OSError("Project session logs are being deleted"))
                completion.set()
            return
        work = _queues.get(key)
        if work is None:
            work = queue.Queue()
            _queues[key] = work
        work.put((kind, args, completion, errors))
        if key not in _queue_running:
            _queue_running.add(key)
            threading.Thread(
                target=_worker, args=(key, work), name="sigma-session-log", daemon=True
            ).start()


def _project_dir_for(kind: str, args: tuple[Any, ...]) -> Path | None:
    if kind in {"append", "delete_session"}:
        project_id = str(args[1]["project_id"]) if kind == "append" else str(args[1])
        return Path(args[3]) / project_id
    if kind == "name":
        return Path(args[3]) / str(args[1])
    if kind == "delete_project":
        return Path(args[2]) / str(args[0])
    return None


def _queue_key(kind: str, args: tuple[Any, ...]) -> str:
    project_dir = _project_dir_for(kind, args)
    if project_dir is None:
        raise ValueError(f"Unsupported session log work kind: {kind}")
    if kind in {"append", "delete_session"}:
        session_id = str(args[1]["id"]) if kind == "append" else str(args[2])
        return str(project_dir / f"{session_id}.md")
    if kind == "name":
        return str(project_dir / ".short-name")
    return str(project_dir / ".delete")


def _worker(key: str, work: queue.Queue) -> None:
    while True:
        try:
            kind, args, completion, errors = work.get(timeout=0.1)
        except queue.Empty:
            with _queues_guard:
                if work.empty() and _queues.get(key) is work:
                    del _queues[key]
                    _queue_running.discard(key)
                    return
            continue
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
            work.task_done()
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
    UUID(session_id)
    view = inspect_project(path_value)
    project_file = project_path(path_value).resolve(strict=True)
    # Project bundles keep session records internally; use the established authorized reader.
    from sigma.research_sessions import get_session

    session = get_session(path_value, session_id)
    target = _path(project_file, view.project.id, session_id)
    project_dir = target.parent
    with _lock(project_dir / ".project-read-guard"):
        with _queues_guard:
            if str(project_dir) in _closing_projects:
                raise OSError("Project session logs are being deleted")
        short_name = _short_name(
            project_file, view.project.id, title=view.project.title, problem=view.project.problem
        )
        target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        with _lock(target):
            lockfile_fd = os.open(target.with_suffix(".lock"), os.O_CREAT | os.O_RDWR, 0o600)
            try:
                fcntl.flock(lockfile_fd, fcntl.LOCK_EX)
                if not target.exists():
                    _ensure(
                        target, view.project.id, session_id, int(session.get("session_number", 1))
                    )
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
    while True:
        with _queues_guard:
            pending = tuple(_queues.values())
        if not pending:
            return
        for work in pending:
            work.join()


atexit.register(flush)


def delete_project(project_id: str, project_file: str | Path) -> None:
    UUID(project_id)
    file_path = Path(project_file)
    root_hint = _root(file_path)
    project_dir = root_hint / project_id
    with _queues_guard:
        _closing_projects.add(str(project_dir))
    try:
        while True:
            with _queues_guard:
                pending = tuple(
                    work
                    for key, work in _queues.items()
                    if key == str(project_dir / ".short-name") or Path(key).parent == project_dir
                )
            if not pending:
                break
            for work in pending:
                work.join()
        with _lock(project_dir / ".project-read-guard"):
            _delete_project_sync(project_id, file_path, root_hint)
    finally:
        with _queues_guard:
            _closing_projects.discard(str(project_dir))


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
    lockfile = target.with_suffix(".lock")
    if target.is_symlink() or lockfile.is_symlink():
        raise OSError("Session log path is a symbolic link")
    with _lock(target):
        lockfile_fd = os.open(lockfile, os.O_CREAT | os.O_RDWR, 0o600)
        try:
            fcntl.flock(lockfile_fd, fcntl.LOCK_EX)
            target.unlink(missing_ok=True)
        finally:
            fcntl.flock(lockfile_fd, fcntl.LOCK_UN)
            os.close(lockfile_fd)
    for temporary in target.parent.glob(f".session-header-{session_id}-*.tmp"):
        if temporary.is_symlink() or not temporary.is_file():
            raise OSError("Session log temporary path is unsafe")
        temporary.unlink()


def log_path(path_value: str, project_id: str, session_id: str) -> Path:
    return _path(project_path(path_value).resolve(strict=True), project_id, session_id)
