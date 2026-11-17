"""Private, append-only Markdown transcripts for interactive chat sessions."""

from __future__ import annotations

import fcntl
import os
import re
import stat
from typing import Any
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from sigma.projects import ProjectError
from sigma.recents import state_directory
from sigma.ui_instance import private_directory

MAX_TRANSCRIPT_BYTES = 64 * 1024 * 1024
SPEAKER_LABELS = {
    "human": "Human",
    "ai_1": "AI #1",
    "ai_2": "AI #2",
    "objective": "Research Objective",
    "supervisor": "Supervisor",
}
TRANSCRIPT_FILENAME = re.compile(r"^\d{8}_\d{6}(?:_\d+)?\.md$")


def _directory() -> Path:
    directory = state_directory() / "chat-transcripts"
    try:
        private_directory(directory)
    except (OSError, RuntimeError) as exc:
        raise ProjectError("The private chat transcript directory is unavailable.") from exc
    return directory


def _check_file(fd: int) -> os.stat_result:
    info = os.fstat(fd)
    if (
        not stat.S_ISREG(info.st_mode)
        or info.st_uid != os.getuid()
        or info.st_nlink != 1
        or info.st_mode & 0o077
    ):
        raise ProjectError("The chat transcript file is not a private, owned regular file.")
    return info


def _write_all(fd: int, data: bytes) -> None:
    view = memoryview(data)
    while view:
        written = os.write(fd, view)
        if written <= 0:
            raise OSError("Chat transcript write made no progress")
        view = view[written:]


def open_transcript() -> dict[str, str]:
    """Create a private timestamped transcript and return its session ID and name."""
    conversation_id = str(uuid4())
    started = datetime.now().astimezone()
    directory = _directory()
    timestamp = started.strftime("%Y%m%d_%H%M%S")
    header = (
        f"# SIGMA two-agent chat transcript\n\nStarted: {started.isoformat()}\n"
        f"Session ID: {conversation_id}\n\n"
    ).encode()
    try:
        collision = 1
        while True:
            suffix = "" if collision == 1 else f"_{collision}"
            name = f"{timestamp}{suffix}.md"
            path = directory / name
            try:
                fd = os.open(
                    path,
                    os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                    0o600,
                )
                break
            except FileExistsError:
                collision += 1
        with os.fdopen(fd, "ab") as stream:
            _check_file(stream.fileno())
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
            _write_all(stream.fileno(), header)
            stream.flush()
            os.fsync(stream.fileno())
    except OSError as exc:
        raise ProjectError("The timestamped chat transcript could not be created.") from exc
    return {
        "conversation_id": conversation_id,
        "transcript_name": name,
        "transcript_path": str(path.resolve()),
    }


def append_message(conversation_id: str, speaker: str, text: str) -> None:
    """Append exactly one participant message to its session's private transcript."""
    try:
        parsed = UUID(conversation_id)
    except (ValueError, TypeError, AttributeError) as exc:
        raise ProjectError("Invalid chat transcript session.") from exc
    canonical_id = str(parsed)
    if conversation_id != canonical_id or speaker not in SPEAKER_LABELS:
        raise ProjectError("Invalid chat transcript message.")
    if not isinstance(text, str) or not text.strip():
        raise ProjectError("A chat message must contain nonempty text.")

    directory = _directory()
    matches = []
    try:
        for candidate in directory.iterdir():
            if not TRANSCRIPT_FILENAME.fullmatch(candidate.name):
                continue
            fd = os.open(candidate, os.O_RDONLY | os.O_NOFOLLOW)
            try:
                _check_file(fd)
                header = os.read(fd, 1024)
            finally:
                os.close(fd)
            if f"Session ID: {canonical_id}\n".encode() in header:
                matches.append(candidate)
    except OSError as exc:
        raise ProjectError("The private chat transcript could not be located safely.") from exc
    if len(matches) != 1:
        raise ProjectError("The chat transcript session was not found or is ambiguous.")
    path = matches[0]
    timestamp = datetime.now(UTC).isoformat(timespec="milliseconds")
    record = f"## {SPEAKER_LABELS[speaker]} · {timestamp}\n\n{text}\n\n".encode()

    try:
        fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_NOFOLLOW)
        with os.fdopen(fd, "ab") as stream:
            info = _check_file(stream.fileno())
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
            info = _check_file(stream.fileno())
            if info.st_size + len(record) > MAX_TRANSCRIPT_BYTES:
                raise ProjectError("The chat transcript reached its 64 MiB size limit.")
            _write_all(stream.fileno(), record)
            stream.flush()
            os.fsync(stream.fileno())
    except OSError as exc:
        raise ProjectError("The private chat transcript could not be updated.") from exc


# Only SIGMA-owned files in the private transcript directory may be resumed.
_RECORD = re.compile(
    r"^## (Human|AI #1|AI #2|Research Objective|Supervisor) · "
    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[^\n]*$",
    re.MULTILINE,
)
_LABEL_SPEAKERS = {label: speaker for speaker, label in SPEAKER_LABELS.items()}
_SESSION_ID = re.compile(
    r"^Session ID: ([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})$",
    re.MULTILINE,
)


def _read_private_file(name: str) -> str:
    if not TRANSCRIPT_FILENAME.fullmatch(name):
        raise ProjectError("Invalid chat transcript filename.")
    path = _directory() / name
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(fd, "rb") as stream:
            info = _check_file(stream.fileno())
            if info.st_size > MAX_TRANSCRIPT_BYTES:
                raise ProjectError("Chat transcript exceeds the supported size.")
            fcntl.flock(stream.fileno(), fcntl.LOCK_SH)
            data = stream.read(MAX_TRANSCRIPT_BYTES + 1)
            if len(data) > MAX_TRANSCRIPT_BYTES:
                raise ProjectError("Chat transcript exceeds the supported size.")
            return data.decode("utf-8")
    except (OSError, UnicodeError) as exc:
        raise ProjectError("The private chat transcript could not be read safely.") from exc


def list_transcripts() -> list[dict[str, str]]:
    """List resumable private transcripts without exposing arbitrary paths."""
    result = []
    for candidate in _directory().iterdir():
        if not TRANSCRIPT_FILENAME.fullmatch(candidate.name):
            continue
        try:
            content = _read_private_file(candidate.name)
            match = _SESSION_ID.search(content[:1024])
            if match and str(UUID(match.group(1))) == match.group(1):
                result.append({"name": candidate.name})
        except (ProjectError, ValueError):
            continue
    return sorted(result, key=lambda item: item["name"], reverse=True)


def load_transcript(name: str) -> dict[str, Any]:
    """Restore a private session and its chronological message history."""
    content = _read_private_file(name)
    header = _SESSION_ID.search(content[:1024])
    if not header:
        raise ProjectError("The chat transcript is missing its session ID.")
    conversation_id = header.group(1)
    try:
        if str(UUID(conversation_id)) != conversation_id:
            raise ValueError("Noncanonical session ID")
    except ValueError as exc:
        raise ProjectError("The chat transcript has an invalid session ID.") from exc

    entries = list(_RECORD.finditer(content))
    messages = []
    for index, match in enumerate(entries):
        start = match.end() + 1
        end = entries[index + 1].start() if index + 1 < len(entries) else len(content)
        body = content[start:end]
        if body.startswith("\n"):
            body = body[1:]
        body = body.removesuffix("\n\n")
        if not body.strip():
            raise ProjectError("The chat transcript contains an empty entry.")
        messages.append({"speaker": _LABEL_SPEAKERS[match.group(1)], "text": body})

    objective = ""
    for message in messages:
        if message["speaker"] == "objective":
            objective = "" if message["text"] == "(cleared)" else message["text"]
    last_ai = next((m["speaker"] for m in reversed(messages)
                    if m["speaker"] in {"ai_1", "ai_2"}), None)
    next_speaker = "ai_2" if last_ai == "ai_1" else "ai_1"
    return {
        "conversation_id": conversation_id,
        "transcript_name": name,
        "transcript_path": str((_directory() / name).resolve()),
        "messages": messages,
        "research_objective": objective,
        "next_speaker": next_speaker,
        "has_supervisor": any(m["speaker"] == "supervisor" for m in messages),
    }
