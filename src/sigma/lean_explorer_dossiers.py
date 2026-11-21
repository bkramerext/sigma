"""Private, durable expository dossiers created by Lean Explorer.

A dossier is evidence/interpretation, not Lean verification. All source links
refer to pinned repository revisions and actual snippets retrieved on insertion.
"""

from __future__ import annotations

import fcntl
import json
import os
import stat
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from sigma import lean_explorer, lean_explorer_local
from sigma.projects import ProjectError
from sigma.recents import state_directory
from sigma.ui_instance import private_directory

MAX_DOSSIER_BYTES = 4 * 1024 * 1024
MAX_ENTRIES = 160
MAX_NOTE_CHARS = 24_000


def _directory() -> Path:
    path = state_directory() / "lean-explorer-dossiers"
    try:
        private_directory(path)
    except (OSError, RuntimeError) as exc:
        raise ProjectError("The private Lean Explorer dossier directory is unavailable.") from exc
    return path


def _identifier(value: str) -> str:
    try:
        identifier = str(UUID(value))
    except (ValueError, AttributeError, TypeError) as exc:
        raise ProjectError("Invalid Lean Explorer dossier identifier.") from exc
    if identifier != value:
        raise ProjectError("Noncanonical Lean Explorer dossier identifier.")
    return identifier


def _check(fd: int) -> None:
    info = os.fstat(fd)
    if (
        not stat.S_ISREG(info.st_mode)
        or info.st_uid != os.getuid()
        or info.st_nlink != 1
        or info.st_mode & 0o077
    ):
        raise ProjectError("Lean Explorer dossier file is not a private regular file.")


def _read(identifier: str) -> dict:
    path = _directory() / (_identifier(identifier) + ".json")
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(fd, "rb") as stream:
            _check(stream.fileno())
            data = stream.read(MAX_DOSSIER_BYTES + 1)
        if len(data) > MAX_DOSSIER_BYTES:
            raise ProjectError("The dossier exceeds the supported size.")
        record = json.loads(data)
    except (OSError, ValueError, UnicodeError) as exc:
        raise ProjectError("The requested Lean Explorer dossier could not be read.") from exc
    if not isinstance(record, dict) or record.get("id") != identifier:
        raise ProjectError("The dossier has invalid metadata.")
    return record


def _revision(source_mode: str) -> str:
    if source_mode == "mirror":
        return lean_explorer.MIRROR_SHA
    if source_mode == "local":
        active = lean_explorer_local.source()
        if active is None:
            raise ProjectError("Select a local Lean directory first.")
        return "local:" + active["root_id"]
    raise ProjectError("Unknown Lean Explorer source mode.")


def create(source_mode: str = "mirror") -> dict:
    revision = _revision(source_mode)
    identifier = str(uuid4())
    timestamp = datetime.now(UTC).isoformat()
    document = {
        "id": identifier,
        "title": "Alpöge RH — Expository Dossier",
        "created_at": timestamp,
        "updated_at": timestamp,
        "formal_repository": lean_explorer.MIRROR,
        "formal_commit": revision,
        "source_mode": source_mode,
        "entries": [],
    }
    data = json.dumps(document, ensure_ascii=False, indent=2).encode("utf-8")
    path = _directory() / (identifier + ".json")
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "wb") as stream:
            _check(stream.fileno())
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
    except OSError as exc:
        raise ProjectError("The Lean Explorer dossier could not be created.") from exc
    return document


def get(identifier: str) -> dict:
    return _read(identifier)


def list_dossiers() -> list[dict]:
    root = _directory()
    items: list[dict] = []
    for path in root.glob("*.json"):
        if len(items) >= 1000:
            break
        try:
            record = _read(path.stem)
        except ProjectError:
            continue
        items.append(
            {
                "id": record["id"],
                "title": record["title"],
                "created_at": record["created_at"],
                "updated_at": record["updated_at"],
                "entry_count": len(record.get("entries", [])),
                "source_mode": record.get("source_mode", "mirror"),
            }
        )
    return sorted(items, key=lambda item: item["updated_at"], reverse=True)


def append(
    identifier: str,
    *,
    formal_path: str,
    declaration_name: str,
    mode: str,
    text: str,
    supplementary_sources: list[dict] | None = None,
    source_mode: str = "mirror",
) -> dict:
    if mode not in {"note", "explain", "audit"}:
        raise ProjectError("Unknown dossier entry type.")
    if not isinstance(text, str) or not text.strip() or len(text) > MAX_NOTE_CHARS:
        raise ProjectError("The exposition text must be nonempty and within 24,000 characters.")

    # Re-read the declaration server-side; never trust client-supplied proof
    # locations, commit identifiers, declaration snippets or source hashes.
    selected = lean_explorer.declaration(formal_path, declaration_name, source_mode=source_mode)
    source = {
        key: selected[key]
        for key in (
            "path",
            "name",
            "kind",
            "commit",
            "url",
            "sha256",
            "start_line",
            "end_line",
            "complete",
            "excerpt",
        )
    }
    root = _directory()
    identifier = _identifier(identifier)
    # A separate stable lockfile protects writers across atomic JSON replacement.
    lock_path = root / (identifier + ".lock")
    try:
        lock_fd = os.open(lock_path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        with os.fdopen(lock_fd, "rb+") as lock:
            _check(lock.fileno())
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            record = _read(identifier)
            if (
                record.get("formal_commit") != _revision(source_mode)
                or record.get("source_mode", "mirror") != source_mode
            ):
                raise ProjectError("Dossier source differs from the selected formal source.")
            entries = record.get("entries")
            if not isinstance(entries, list) or len(entries) >= MAX_ENTRIES:
                raise ProjectError("The dossier has reached its entry limit.")
            item = {
                "id": str(uuid4()),
                "created_at": datetime.now(UTC).isoformat(),
                "mode": mode,
                "interpretation_status": "unverified commentary",
                "text": text.strip(),
                "source": source,
                "supplementary_sources": supplementary_sources or [],
            }
            entries.append(item)
            record["updated_at"] = item["created_at"]
            data = json.dumps(record, ensure_ascii=False, indent=2).encode("utf-8")
            if len(data) > MAX_DOSSIER_BYTES:
                raise ProjectError("The dossier exceeds its 4 MiB size limit.")
            temp = root / (identifier + "." + str(uuid4()) + ".tmp")
            try:
                fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
                with os.fdopen(fd, "wb") as stream:
                    _check(stream.fileno())
                    stream.write(data)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temp, root / (identifier + ".json"))
            finally:
                if temp.exists():
                    temp.unlink()
            return item
    except OSError as exc:
        raise ProjectError("The Lean Explorer dossier could not be updated.") from exc


def markdown(identifier: str) -> str:
    record = _read(identifier)
    parts = [
        f"# {record['title']}",
        "",
        f"Formal source: {record['formal_repository']}",
        f"Source revision: `{record['formal_commit']}`",
        f"Created: {record['created_at']}",
        "",
        (
            "> This dossier contains source excerpts and unverified human/AI "
            "interpretation. Lean Explorer has not kernel-checked or "
            "mapped dependencies for these statements."
        ),
        "",
    ]
    for index, item in enumerate(record.get("entries", []), 1):
        src = item["source"]
        parts.extend(
            [
                f"## {index}. {src['name']} — {item['mode']}",
                "",
                (
                    f"Source: [{src['path']} lines {src['start_line']}-"
                    f"{src['end_line']}]({src['url']}#L{src['start_line']})"
                    if src.get("url", "").startswith("https://")
                    else f"Local source: {src['path']} lines {src['start_line']}-{src['end_line']}"
                ),
                f"Commit: `{src['commit']}` · SHA256: `{src['sha256']}`",
                f"Source excerpt complete: {src['complete']}",
                f"Interpretation: **{item['interpretation_status']}**",
                "",
                "### Actual Lean source excerpt",
                "",
                "```lean",
                src["excerpt"],
                "```",
                "",
                "### Commentary",
                "",
                item["text"],
                "",
            ]
        )
        for supp in item.get("supplementary_sources", []):
            parts.append(
                f"Supplementary: {supp['kind']} · [{supp['path']}]({supp['url']})"
                f" · revision `{supp['commit']}` · SHA256 `{supp['sha256']}`"
            )
        parts.append("")
    return "\n".join(parts)
