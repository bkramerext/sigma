"""Bounded, sanitized, project-scoped diagnostics for failures before a session exists.

A diagnostic is a project audit record, not a research session or a provider call.
The local/cloud project authorization is always checked before reading or writing.
"""

from __future__ import annotations

import json
import os
import re
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from sigma import cloud_workspaces, session_log
from sigma.projects import inspect_project

MAX_BYTES = 1024 * 1024
MAX_MESSAGE = 900
MAX_RECORD = 2400
_LOCK = threading.RLock()
_SECRET = re.compile(
    r"(?i)(bearer\s+|(?:api[_-]?key|access[_-]?token|refresh[_-]?token|password|secret)\s*[:=]\s*)([^\s,;]+)"
)
_URL_SECRET = re.compile(r"(?i)([?&](?:token|key|secret|auth|password|signature)=)[^&#\s]+")
_SK = re.compile(r"\bsk-[a-zA-Z0-9_-]{10,}\b")
_VALID_CODE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_VALID_ID = re.compile(r"^[a-zA-Z0-9_-]{1,80}$")


def sanitize(text: Any, limit: int = MAX_MESSAGE) -> str:
    value = str(text or "")
    value = _SECRET.sub(r"\1[REDACTED]", value)
    value = _URL_SECRET.sub(r"\1[REDACTED]", value)
    value = _SK.sub("[REDACTED]", value)
    value = "".join(c if c == "\n" or ord(c) >= 32 else " " for c in value)
    return value[:limit] + (" [truncated]" if len(value) > limit else "")


def _file(path: str) -> tuple[str, Path]:
    project = inspect_project(path).project
    workspace = cloud_workspaces.current()
    project_file = Path(path).resolve()
    root = (
        workspace.path / ".sigma-session-logs"
        if workspace
        else project_file.parent / ".sigma-session-logs"
    )
    folder = root / project.id
    if root.is_symlink() or folder.is_symlink():
        raise OSError("Unsafe diagnostics directory")
    return project.id, folder / "project-diagnostics.jsonl"


def append(
    path: str,
    *,
    stage: str,
    code: str,
    message: str,
    session_id: str | None = None,
    correlation_id: str | None = None,
    http_status: int | None = None,
    reference_url: str | None = None,
) -> dict[str, Any]:
    """Return the exact canonical record persisted, or raise; never fake success."""
    project_id, target = _file(path)
    record: dict[str, Any] = {
        "id": str(uuid4()),
        "timestamp": datetime.now(UTC).isoformat(),
        "project_id": project_id,
        "session_id": session_id if session_id and _VALID_ID.fullmatch(session_id) else None,
        "stage": stage[:40] if _VALID_CODE.fullmatch(stage) else "unknown",
        "code": code[:64] if _VALID_CODE.fullmatch(code) else "request_error",
        "message": sanitize(message),
        "correlation_id": correlation_id
        if correlation_id and _VALID_ID.fullmatch(correlation_id)
        else None,
        "http_status": http_status
        if isinstance(http_status, int) and 100 <= http_status <= 599
        else None,
        "reference_url": sanitize(reference_url, 300) if reference_url else None,
    }
    data = (json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
    if len(data) > MAX_RECORD:
        record["message"] = sanitize("Diagnostic exceeded the per-record size limit.")
        data = (json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n").encode(
            "utf-8"
        )
    project_dir = target.parent
    # Match session_log.delete_project's project-level guard; do not recreate
    # diagnostic state after deletion begins.
    with session_log._lock(project_dir / ".project-read-guard"):
        with session_log._queues_guard:
            if str(project_dir) in session_log._closing_projects:
                raise OSError("Project diagnostics are being deleted")
        with _LOCK:
            return _write_record(target, record, data)


def _write_record(target: Path, record: dict[str, Any], data: bytes) -> dict[str, Any]:
    target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if target.is_symlink() or (target.exists() and not target.is_file()):
        raise OSError("Unsafe diagnostics file")
    # Retries on one correlation must not create duplicate error records.
    if target.exists() and record["correlation_id"]:
        # Open by descriptor with O_NOFOLLOW, and inspect that same inode.
        # Path.stat()/read_bytes() could follow a swapped-in symlink.
        fd = os.open(target, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(fd, "rb") as stream:
            if os.fstat(stream.fileno()).st_size > MAX_BYTES:
                raise OSError("Project diagnostics capacity reached; event was not recorded")
            for line in stream.read(MAX_BYTES + 1).splitlines():
                try:
                    previous = json.loads(line)
                except (ValueError, UnicodeDecodeError):
                    continue
                if not isinstance(previous, dict):
                    continue
                if all(
                    previous.get(key) == record[key]
                    for key in ("correlation_id", "stage", "code", "message", "session_id")
                ):
                    return previous
    if target.exists():
        fd = os.open(target, os.O_RDONLY | os.O_NOFOLLOW)
        try:
            existing_bytes = os.fstat(fd).st_size
        finally:
            os.close(fd)
    else:
        existing_bytes = 0
    if existing_bytes + len(data) > MAX_BYTES:
        raise OSError("Project diagnostics capacity reached; event was not recorded")
    fd = os.open(target, os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "ab") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    return record


def read(path: str) -> list[dict[str, Any]]:
    _, target = _file(path)
    project_dir = target.parent
    with session_log._lock(project_dir / ".project-read-guard"):
        with session_log._queues_guard:
            if str(project_dir) in session_log._closing_projects:
                raise OSError("Project diagnostics are being deleted")
        with _LOCK:
            if target.is_symlink() or (target.exists() and not target.is_file()):
                raise OSError("Unsafe diagnostics file")
            try:
                # O_NOFOLLOW is required even if the earlier symlink check raced.
                fd = os.open(target, os.O_RDONLY | os.O_NOFOLLOW)
            except FileNotFoundError:
                return []
            with os.fdopen(fd, "rb") as stream:
                payload = stream.read(MAX_BYTES + 1)
    if len(payload) > MAX_BYTES:
        raise OSError("Project diagnostic log exceeds safe size")
    results: list[dict[str, Any]] = []
    for line in payload.splitlines():
        try:
            item = json.loads(line)
            if isinstance(item, dict) and isinstance(item.get("id"), str):
                results.append(item)
        except (ValueError, UnicodeDecodeError):
            continue
    return results


def _markdown_literal(message: str) -> str:
    """Keep untrusted diagnostic text inside one unmistakable quoted message."""
    return "\\n".join(message.splitlines()) if "\n" in message else message


def export(path: str) -> str:
    items = read(path)
    lines = [
        "# Project diagnostics",
        "",
        "Sanitized exportable errors (not the full append-only provider wire log).",
        "",
    ]
    for item in items:
        lines.extend(
            [
                f"## {item['timestamp']} · {item['stage']} · {item['code']}",
                f"Event ID: {item['id']}",
                f"Project ID: {item['project_id']}",
                f"Session ID: {item.get('session_id') or 'none (pre-session)'}",
                f"Correlation ID: {item.get('correlation_id') or 'not recorded'}",
                f"HTTP status: {item.get('http_status') or 'not recorded'}",
                f"Message (escaped newlines): {_markdown_literal(str(item['message']))}",
                *(
                    [f"Reference: {_markdown_literal(str(item['reference_url']))}"]
                    if item.get("reference_url")
                    else []
                ),
                "",
            ]
        )
    return "\n".join(lines)
