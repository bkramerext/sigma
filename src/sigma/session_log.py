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
    header = f"# SIGMA Session {session_number} Log\n\nProject: `{project_id}`  \nSession: `{session_id}`\n\nEvents are appended as readable Markdown with canonical structured records in collapsible JSON sections.\n"
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
            prior_events, _ = _frames(target)
            data = _redact(
                {
                    "seq": (prior_events[-1].get("seq", len(prior_events)) if prior_events else 0)
                    + 1,
                    "timestamp": datetime.now(UTC).isoformat(),
                    **event,
                }
            )
            body = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            markdown = _event_markdown(data, prior_events)
            if len(body) > MAX_EVENT_BYTES:
                data = {
                    "seq": data["seq"],
                    "timestamp": data["timestamp"],
                    "type": "event_omitted",
                    "reason": "event exceeds 18 MiB bound",
                }
                body = json.dumps(data, separators=(",", ":")).encode()
                markdown = _event_markdown(data, prior_events)
            growth = _frame_growth(data, markdown)
            if target.stat().st_size + growth > MAX_LOG_BYTES:
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
            _append_frame(target, data, markdown)
        finally:
            fcntl.flock(lockfile_fd, fcntl.LOCK_UN)
            os.close(lockfile_fd)


def _append_frame(path: Path, value: dict[str, Any], markdown: str = "") -> None:
    body = _encoded_event(value, pretty=bool(markdown))
    if markdown:
        markdown = _escape_frame_markers(markdown)
    with path.open("ab") as stream:
        stream.write(f"\n<!-- SIGMA_EVENT {len(body)} -->\n".encode())
        if markdown:
            stream.write(markdown.encode("utf-8"))
            stream.write(b"\n\n")
            stream.write(b"<details><summary>Canonical structured event data (JSON)</summary>\n\n")
            stream.write(f"<!-- SIGMA_JSON {len(body)} -->\n```json\n".encode())
        stream.write(body)
        if markdown:
            stream.write(b"\n```\n</details>")
        stream.write(b"\n<!-- END_SIGMA_EVENT -->")
        stream.flush()
        os.fsync(stream.fileno())


def _frame_growth(value: dict[str, Any], markdown: str) -> int:
    body_size = len(_encoded_event(value, pretty=True))
    return body_size + len(markdown.encode("utf-8")) + 256


def _encoded_event(value: dict[str, Any], *, pretty: bool) -> bytes:
    rendered = json.dumps(
        value,
        ensure_ascii=False,
        indent=2 if pretty else None,
        separators=None if pretty else (",", ":"),
    )
    # Prevent a provider-controlled string from impersonating a frame marker.
    for marker in ("<!-- SIGMA_EVENT", "<!-- SIGMA_JSON", "<!-- END_SIGMA_EVENT"):
        rendered = rendered.replace(marker, r"\u003c" + marker[1:])
    return rendered.encode("utf-8")


def _escape_frame_markers(markdown: str) -> str:
    for marker in ("<!-- SIGMA_EVENT", "<!-- SIGMA_JSON", "<!-- END_SIGMA_EVENT"):
        markdown = markdown.replace(marker, "&lt;!--" + marker[len("<!--") :])
    return markdown


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
        legacy_end = start + size
        legacy = raw[legacy_end : legacy_end + len(terminator)] == terminator
        if legacy:
            end = legacy_end
            terminator_start = legacy_end
        else:
            next_frame = raw.find(marker, cursor + len(marker))
            json_marker = raw.find(b"<!-- SIGMA_JSON ", start)
            if json_marker < 0 or (next_frame >= 0 and json_marker > next_frame):
                cursor = raw.find(marker, cursor + len(marker))
                continue
            json_line_end = raw.find(b" -->\n", json_marker)
            if json_line_end < 0 or not raw[json_line_end + 5 :].startswith(b"```json\n"):
                cursor = raw.find(marker, cursor + len(marker))
                continue
            start = json_line_end + 5 + len(b"```json\n")
            end = start + size
            closing = b"\n```\n</details>"
            if raw[end : end + len(closing)] != closing:
                cursor = raw.find(marker, cursor + len(marker))
                continue
            terminator_start = end + len(closing)
        if (
            terminator_start + len(terminator) > len(raw)
            or raw[terminator_start : terminator_start + len(terminator)] != terminator
        ):
            cursor = raw.find(marker, cursor + len(marker))
            continue
        try:
            item = json.loads(raw[start:end])
        except (ValueError, UnicodeDecodeError):
            cursor = raw.find(marker, cursor + len(marker))
            continue
        if isinstance(item, dict):
            events.append(item)
        cursor = raw.find(marker, terminator_start + len(terminator))
    return events, file_size


def _event_role_label(event: dict[str, Any]) -> str:
    role = str(event.get("role") or "Session")
    return role.capitalize() if role.casefold() in {"investigator", "skeptic", "session"} else role


def _response_text(value: Any) -> str:
    """Extract provider-authored text from a captured Responses or Chat payload."""
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except (json.JSONDecodeError, ValueError):
            return value
        return _response_text(decoded) if isinstance(decoded, (dict, list)) else value
    if isinstance(value, list):
        return "\n\n".join(text for item in value if (text := _response_text(item)))
    if not isinstance(value, dict):
        return ""
    output: list[str] = []
    for item in value.get("output", []) if isinstance(value.get("output"), list) else []:
        if not isinstance(item, dict):
            continue
        for content in item.get("content", []) if isinstance(item.get("content"), list) else []:
            if isinstance(content, dict) and isinstance(content.get("text"), str):
                output.append(content["text"])
    if output:
        return "\n\n".join(output)
    if isinstance(value.get("output_text"), str):
        return str(value["output_text"])
    choices = value.get("choices")
    if isinstance(choices, list):
        for choice in choices:
            if isinstance(choice, dict):
                message = choice.get("message") or choice.get("delta") or {}
                if isinstance(message, dict) and isinstance(message.get("content"), str):
                    output.append(message["content"])
    if output:
        return "\n\n".join(output)
    if isinstance(value.get("content"), str):
        return str(value["content"])
    return ""


def _readable_response(value: Any) -> str:
    raw = _response_text(value)
    try:
        decoded = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return raw
    if not isinstance(decoded, dict):
        return raw
    parts: list[str] = []
    for key, item in decoded.items():
        label = key.replace("_", " ").capitalize()
        if isinstance(item, str):
            body = item.strip()
        elif isinstance(item, list):
            body = "\n".join(f"- {entry}" for entry in item if isinstance(entry, (str, int, float)))
            if not body:
                body = "```json\n" + json.dumps(item, ensure_ascii=False, indent=2) + "\n```"
        elif isinstance(item, dict):
            body = "```json\n" + json.dumps(item, ensure_ascii=False, indent=2) + "\n```"
        else:
            body = str(item)
        parts.append(f"#### {label}\n\n{body}")
    return "\n\n".join(parts)


def _request_text(value: Any) -> str:
    if not isinstance(value, dict):
        return str(value) if isinstance(value, str) else ""
    parts: list[str] = []
    instructions = value.get("instructions")
    if isinstance(instructions, str) and instructions.strip():
        parts.append(instructions)
    input_value = value.get("input")
    if isinstance(input_value, str):
        parts.append(input_value)
    elif isinstance(input_value, list):
        for item in input_value:
            if isinstance(item, dict):
                content = item.get("content", item.get("text", ""))
                if isinstance(content, str):
                    parts.append(content)
                elif isinstance(content, list):
                    parts.extend(
                        str(part.get("text", "")) for part in content if isinstance(part, dict)
                    )
    return "\n\n".join(part for part in parts if part.strip())


def _markdown_payload(text: str, label: str) -> str:
    if not text:
        return f"_{label} text was not present in the captured provider payload._"
    # Preserve provider-authored Markdown and equations. Normalize only complete
    # legacy TeX delimiter pairs, leaving unmatched delimiter characters literal.
    text = re.sub(
        r"(?<!\\)\\\[([\s\S]*?)(?<!\\)\\\]",
        lambda match: "$$\n" + match.group(1).strip() + "\n$$",
        text,
    )
    text = re.sub(
        r"(?<!\\)\\\(([^\n]*?)(?<!\\)\\\)", lambda match: "$" + match.group(1) + "$", text
    )
    # A block opener on its own line is unambiguous. Close it at the paragraph
    # boundary, before another opener, or at end-of-input for old malformed notes.
    text = re.sub(
        r"(?m)(?<!\\)\\\[[ \t]*\n([\s\S]*?)(?=\n[ \t]*\n|\n[ \t]*\\\[|\Z)",
        lambda match: "$$\n" + match.group(1).strip() + "\n$$",
        text,
    )
    # Unmatched legacy display delimiters are source text, not the start of
    # math. Escape the bracket so Markdown/KaTeX previews cannot consume them.
    text = re.sub(r"(?<!\\)\\(?=[\[\]])", lambda match: "\\" + match.group(0), text)
    text = _escape_unmatched_dollars(text)
    return text


def _escape_unmatched_dollars(text: str) -> str:
    """Escape unmatched math/currency markers outside Markdown code spans."""
    escape_positions: set[int] = set()
    fence: str | None = None
    display_open: int | None = None
    offset = 0
    for line in text.splitlines(keepends=True):
        fence_match = re.match(r"^[ \t]*(`{3,}|~{3,})", line)
        if fence_match:
            marker = fence_match.group(1)[0]
            if fence is None:
                fence = marker
            elif marker == fence:
                fence = None
            offset += len(line)
            continue
        if fence is not None:
            offset += len(line)
            continue
        code_ranges = [match.span() for match in re.finditer(r"(`+)[^`\n]*?\1", line)]
        inline_positions: list[int] = []
        position = 0
        while position < len(line):
            if any(start <= position < end for start, end in code_ranges):
                active = next(end for start, end in code_ranges if start <= position < end)
                position = active
                continue
            if line[position] != "$":
                position += 1
                continue
            prior_slashes = 0
            prior = position - 1
            while prior >= 0 and line[prior] == "\\":
                prior_slashes += 1
                prior -= 1
            if prior_slashes % 2:
                position += 1
                continue
            width = 2 if line[position : position + 2] == "$$" else 1
            if width == 1 and line[position + 1 : position + 2].isdigit():
                escape_positions.add(offset + position)
            elif width == 2:
                if display_open is None:
                    display_open = offset + position
                else:
                    display_open = None
            else:
                inline_positions.append(position)
            position += width
        for index in range(0, len(inline_positions), 2):
            if index + 1 >= len(inline_positions):
                escape_positions.add(offset + inline_positions[index])
        offset += len(line)
    if display_open is not None:
        escape_positions.add(display_open)
    if not escape_positions:
        return text
    return "".join(
        ("\\" if index in escape_positions else "") + char for index, char in enumerate(text)
    )


def _event_markdown(event: dict[str, Any], prior_events: list[dict[str, Any]]) -> str:
    event_type = str(event.get("type", "event"))
    role = _event_role_label(event)
    round_label = str(event.get("round", "—"))
    turn = str(event.get("turn", event.get("step_id", event.get("request_id", event.get("seq")))))
    stamp = str(event.get("timestamp", ""))
    if event_type == "provider_request":
        return (
            f"### Provider request dispatched · {role} · Round {round_label} · Turn {turn}\n\n"
            f"`{stamp}` · Request `{event.get('request_id', 'unknown')}` · {event.get('provider', 'provider')} / {event.get('model', 'unknown')} · Awaiting response."
        )
    if event_type in {"provider_response", "provider_failure"}:
        request = next(
            (
                row
                for row in reversed(prior_events)
                if row.get("type") == "provider_request"
                and row.get("request_id") == event.get("request_id")
            ),
            None,
        )
        request = request or {}
        role = _event_role_label(request or event)
        request_text = _request_text(request.get("request"))
        response_text = (
            _readable_response(event.get("response"))
            if event_type == "provider_response"
            else str(event.get("provider_error", event.get("message", "Provider call failed.")))
        )
        result_heading = (
            "Provider response" if event_type == "provider_response" else "Provider failure"
        )
        request_section = _markdown_payload(request_text, "Request")
        response_section = _markdown_payload(response_text, result_heading)
        usage = event.get("usage") if isinstance(event.get("usage"), dict) else {}
        cost = event.get("estimated_cost_usd", "unavailable")
        metadata = (
            f"**{role} · Round {request.get('round', event.get('round', '—'))} · Turn {request.get('turn', request.get('step_id', event.get('seq')))}**  \n"
            f"Request `{event.get('request_id', 'unknown')}` · {request.get('provider', 'provider')} / {request.get('model', event.get('model', 'unknown'))} · "
            f"{event.get('duration_seconds', '—')} s · Usage `{json.dumps(usage, ensure_ascii=False, sort_keys=True)}` · Estimated cost `${cost}`"
        )
        return (
            f"<details>\n<summary>{role} · Round {request.get('round', event.get('round', '—'))} · Turn {request.get('turn', request.get('step_id', event.get('seq')))} · Request + response</summary>\n\n"
            f"{metadata}\n\n#### Actual request\n\n{request_section}\n\n#### {result_heading}\n\n{response_section}\n\n</details>"
        )
    if event_type == "session_event":
        detail = str(event.get("message", event.get("event_kind", "Session event")))
        return f"### {role} · Round {round_label} · {event.get('event_kind', 'Session event')}\n\n`{stamp}` · {detail}"
    detail = str(event.get("message", event.get("status", event_type)))
    return f"### {event_type.replace('_', ' ').capitalize()} · Round {round_label} · {role}\n\n`{stamp}` · {detail}"


def markdown_export(events: list[dict[str, Any]], session: dict[str, Any], short_name: str) -> str:
    """Render old or new canonical frames as a readable, disposable Markdown download."""
    output = [
        f"# {short_name}, Session {session.get('number', '—')}",
        "",
        "Provider requests, responses, and metadata are paired below. The persistent append-only log keeps complete structured events and raw response wire for retained events; this download summarizes duplicate raw-wire strings to keep Markdown previews readable.",
        "",
    ]
    completed: set[str] = set()
    by_request: dict[str, dict[str, Any]] = {
        str(event["request_id"]): event
        for event in events
        if event.get("type") == "provider_request" and event.get("request_id")
    }
    for event in events:
        if event.get("type") in {"provider_response", "provider_failure"}:
            request_id = str(event.get("request_id", ""))
            if request_id in completed:
                continue
            output.extend(
                [
                    _event_markdown(
                        event, [by_request[request_id]] if request_id in by_request else []
                    ),
                    "",
                ]
            )
            completed.add(request_id)
            continue
        if event.get("type") == "provider_request" and any(
            row.get("request_id") == event.get("request_id")
            and row.get("type") in {"provider_response", "provider_failure"}
            for row in events
        ):
            continue
        output.extend(
            [
                _event_markdown(
                    event, [row for row in events if row.get("type") == "provider_request"]
                ),
                "",
            ]
        )
    output.append("## Canonical event records\n")
    for event in events:
        display_event = dict(event)
        wire = display_event.get("response_wire")
        if isinstance(wire, str) and len(wire) > 4096:
            display_event["response_wire"] = (
                f"[{len(wire)} characters retained in the persistent append-only session log]"
            )
        output.extend(
            [
                f"<details><summary>Event {event.get('seq', '—')} · {event.get('type', 'event')} · canonical JSON</summary>",
                "",
                "```json",
                json.dumps(display_event, ensure_ascii=False, indent=2),
                "```",
                "</details>",
                "",
            ]
        )
    return "\n".join(output).rstrip() + "\n"


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
        "project_title": view.project.title,
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
