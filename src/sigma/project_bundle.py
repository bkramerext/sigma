"""Lossless, portable snapshot of a legacy SIGMA project directory.

This module deliberately does not mutate live storage. The snapshot includes all
regular files, including research sessions, evidence and artifacts, so callers
can verify round trips before migrating project paths.
"""

from __future__ import annotations

import base64
import binascii
import fcntl
import json
import os
import stat
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

FORMAT = "sigma.project.bundle"
VERSION = 1


class BundleError(ValueError):
    """A project cannot be bundled or restored safely."""


def _files(directory: Path) -> dict[str, str]:
    if directory.is_symlink() or not directory.is_dir():
        raise BundleError("Project source must be a real directory")
    entries: dict[str, str] = {}
    for root, dirs, files in os.walk(directory, followlinks=False):
        dirs.sort()
        files.sort()
        if any(name in files for name in dirs):
            raise BundleError("Project contains conflicting file and directory names")
        for name in dirs:
            child = Path(root) / name
            if child.is_symlink():
                raise BundleError("Symbolic links are not allowed in project storage")
        for name in files:
            child = Path(root) / name
            if not stat.S_ISREG(child.lstat().st_mode):
                raise BundleError("Only regular project files can be bundled")
            relative = child.relative_to(directory).as_posix()
            entries[relative] = base64.b64encode(child.read_bytes()).decode("ascii")
    if "project.json" not in entries:
        raise BundleError("Project has no project.json")
    try:
        document = json.loads(base64.b64decode(entries["project.json"]))
    except (ValueError, UnicodeDecodeError) as exc:
        raise BundleError("Invalid source project document") from exc
    if not isinstance(document, dict) or type(document.get("schema_version")) is not int:
        raise BundleError("Invalid source project schema")
    if not 1 <= document["schema_version"] <= 9:
        raise BundleError("Unsupported source project schema")
    return entries


def snapshot(directory: str | Path) -> dict[str, Any]:
    """Capture every project file, without omitting binary evidence or artifacts."""
    return {"format": FORMAT, "version": VERSION, "files": _files(Path(directory))}


def encode(directory: str | Path) -> bytes:
    return (json.dumps(snapshot(directory), sort_keys=True, indent=2) + "\n").encode("utf-8")


def _decode(bundle: dict[str, Any]) -> dict[str, bytes]:
    if not isinstance(bundle, dict) or set(bundle) != {"format", "version", "files"}:
        raise BundleError("Invalid project bundle")
    if (
        bundle["format"] != FORMAT
        or type(bundle["version"]) is not int
        or bundle["version"] != VERSION
    ):
        raise BundleError("Unsupported project bundle format")
    files = bundle["files"]
    if not isinstance(files, dict) or "project.json" not in files:
        raise BundleError("Project bundle has no project document")
    result: dict[str, bytes] = {}
    for name, encoded in files.items():
        if not isinstance(name, str) or not name or "\\" in name:
            raise BundleError("Unsafe bundle path")
        path = Path(name)
        if path.is_absolute() or any(part in ("", ".", "..") for part in name.split("/")):
            raise BundleError("Unsafe bundle path")
        if any(other != name and other.startswith(name + "/") for other in files):
            raise BundleError("Bundle member conflicts with a directory")
        if not isinstance(encoded, str):
            raise BundleError("Invalid encoded file")
        try:
            result[name] = base64.b64decode(encoded, validate=True)
        except (ValueError, binascii.Error) as exc:
            raise BundleError("Invalid encoded file") from exc
    try:
        document = json.loads(result["project.json"])
    except (ValueError, UnicodeDecodeError) as exc:
        raise BundleError("Invalid project document") from exc
    if not isinstance(document, dict) or type(document.get("schema_version")) is not int:
        raise BundleError("Invalid project document")
    if not 1 <= document["schema_version"] <= 9:
        raise BundleError("Unsupported project schema version")
    return result


def restore(bundle: dict[str, Any], destination: str | Path) -> None:
    """Restore only to a nonexistent directory; never overwrite live project data."""
    destination = Path(destination)
    files = _decode(bundle)
    if os.path.lexists(destination):
        raise BundleError("Project destination already exists")
    if destination.parent.is_symlink() or not destination.parent.is_dir():
        raise BundleError("Project destination parent must be a real directory")
    # Create the final destination exclusively. This cannot replace a competing
    # directory. On an interrupted restore, an incomplete destination remains
    # visible and must be handled explicitly rather than silently overwritten.
    try:
        destination.mkdir()
    except FileExistsError as exc:
        raise BundleError("Project destination already exists") from exc
    try:
        for name, data in files.items():
            target = destination / name
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("xb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
        directory_fd = os.open(destination, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except BaseException as exc:
        raise BundleError(f"Restore incomplete at {destination}; inspect before retrying") from exc


def migrate(directory: str | Path, destination: str | Path) -> Path:
    """Publish a verified, immutable single-file snapshot without deleting source.

    A cooperative exclusive lock prevents another migration from publishing the
    same destination concurrently. Callers must quiesce live research writers
    before migrating: a directory snapshot cannot freeze independent writers.
    """
    source = Path(directory)
    target = Path(destination)
    if target.suffix != ".json" or target.is_symlink():
        raise BundleError("Migration destination must be a regular JSON path")
    if not target.parent.is_dir() or target.parent.is_symlink():
        raise BundleError("Migration destination parent is unavailable")
    lock = target.with_name("." + target.name + ".migration.lock")
    flags = os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0)
    lock_fd = os.open(lock, flags, 0o600)
    with os.fdopen(lock_fd, "a+b") as stream:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        if os.path.lexists(target):
            raise BundleError("Migration destination already exists")
        before = _files(source)
        # A directory-based research writer must be stopped by the caller.
        # Detect ordinary concurrent mutations before publishing.
        contents = (
            json.dumps(
                {"format": FORMAT, "version": VERSION, "files": before},
                sort_keys=True,
                indent=2,
            )
            + "\n"
        ).encode("utf-8")
        fd, name = tempfile.mkstemp(prefix=".sigma-migrate-", dir=target.parent)
        staged = Path(name)
        try:
            with os.fdopen(fd, "wb") as output:
                output.write(contents)
                output.flush()
                os.fsync(output.fileno())
            decoded = _decode(json.loads(staged.read_text(encoding="utf-8")))
            if decoded != {key: base64.b64decode(value) for key, value in before.items()}:
                raise BundleError("Migration verification failed")
            if _files(source) != before:
                raise BundleError("Project changed during migration")
            os.link(staged, target)
            directory_fd = os.open(target.parent, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        finally:
            staged.unlink(missing_ok=True)
    return target


def read_file(bundle_path: str | Path, relative_path: str) -> bytes:
    """Read one member of an authoritative JSON bundle."""
    path = Path(bundle_path)
    if path.is_symlink() or not path.is_file():
        raise BundleError("Project JSON must be a regular file")
    try:
        return _decode(json.loads(path.read_text(encoding="utf-8")))[relative_path]
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise BundleError("Cannot read project bundle member") from exc


def write_file(bundle_path: str | Path, relative_path: str, contents: bytes) -> None:
    """Atomically update a bundle member while preserving concurrent member writes.

    Every cooperating writer takes a stable sidecar lock, re-reads the complete
    bundle while locked, then replaces it with a fsynced new version. The
    replace does not invalidate the sidecar lock.
    """
    path = Path(bundle_path)
    if path.suffix != ".json" or path.is_symlink() or not path.is_file():
        raise BundleError("Project JSON must be a regular file")
    if not isinstance(contents, bytes):
        raise BundleError("Project member contents must be bytes")
    if (
        not isinstance(relative_path, str)
        or not relative_path
        or "\\" in relative_path
        or relative_path.startswith("/")
        or any(part in ("", ".", "..") for part in relative_path.split("/"))
    ):
        raise BundleError("Unsafe bundle path")
    lock = path.with_name("." + path.name + ".write.lock")
    flags = os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(lock, flags, 0o600)
    with os.fdopen(fd, "a+b") as stream:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        if path.is_symlink() or not path.is_file():
            raise BundleError("Project JSON is no longer a regular file")
        members = _decode(json.loads(path.read_text(encoding="utf-8")))
        members[relative_path] = contents
        _publish_members(path, members, ".sigma-update-")


def _publish_members(path: Path, members: dict[str, bytes], prefix: str) -> None:
    """Replace a validated bundle with one fsynced atomic write."""
    payload = {
        "format": FORMAT,
        "version": VERSION,
        "files": {
            name: base64.b64encode(data).decode("ascii") for name, data in sorted(members.items())
        },
    }
    fd, name = tempfile.mkstemp(prefix=prefix, dir=path.parent)
    staged = Path(name)
    try:
        with os.fdopen(fd, "wb") as output:
            output.write((json.dumps(payload, sort_keys=True, indent=2) + "\n").encode("utf-8"))
            output.flush()
            os.fsync(output.fileno())
        os.replace(staged, path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        staged.unlink(missing_ok=True)


def list_files(bundle_path: str | Path) -> tuple[str, ...]:
    """Enumerate all persisted members of a single-file project."""
    path = Path(bundle_path)
    if path.is_symlink() or not path.is_file():
        raise BundleError("Project JSON must be a regular file")
    try:
        members = _decode(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError, TypeError) as exc:
        raise BundleError("Cannot inspect project bundle") from exc
    return tuple(sorted(members))


def delete_file(bundle_path: str | Path, relative_path: str) -> None:
    """Remove a member without losing unrelated session or evidence files.

    The project document is mandatory and cannot be removed.
    """
    path = Path(bundle_path)
    if relative_path == "project.json":
        raise BundleError("Cannot remove the project document")
    if (
        not isinstance(relative_path, str)
        or not relative_path
        or chr(92) in relative_path
        or relative_path.startswith("/")
        or any(part in ("", ".", "..") for part in relative_path.split("/"))
    ):
        raise BundleError("Unsafe bundle path")
    if path.is_symlink() or not path.is_file():
        raise BundleError("Project JSON must be a regular file")
    lock = path.with_name("." + path.name + ".write.lock")
    flags = os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(lock, flags, 0o600)
    with os.fdopen(fd, "a+b") as stream:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        if path.is_symlink() or not path.is_file():
            raise BundleError("Project JSON is no longer a regular file")
        members = _decode(json.loads(path.read_text(encoding="utf-8")))
        if relative_path not in members:
            raise BundleError("Project member does not exist")
        del members[relative_path]
        _publish_members(path, members, ".sigma-delete-")


def update_files(
    bundle_path: str | Path,
    changes: dict[str, bytes | None],
) -> None:
    """Apply a group of member writes/deletions in one atomic JSON replacement.

    None means delete; project.json must always remain present. This is the
    transaction boundary for saving a session alongside its evidence.
    """
    if not isinstance(changes, dict):
        raise BundleError("Bundle changes must be a dictionary")
    if not changes:
        return
    transform_members(bundle_path, lambda members: changes)


def transform_file(
    bundle_path: str | Path,
    relative_path: str,
    transform: Callable[[bytes], bytes],
) -> bytes:
    """Apply a read-modify-write transaction to one bundle member.

    The callback executes under the stable bundle lock, so concurrent strategy
    edits cannot both read the same version and lose one another's changes.
    """
    path = Path(bundle_path)
    if path.suffix != ".json" or path.is_symlink() or not path.is_file():
        raise BundleError("Project JSON must be a regular file")
    if (
        not isinstance(relative_path, str)
        or not relative_path
        or chr(92) in relative_path
        or relative_path.startswith("/")
        or any(part in ("", ".", "..") for part in relative_path.split("/"))
    ):
        raise BundleError("Unsafe bundle path")
    lock = path.with_name("." + path.name + ".write.lock")
    flags = os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(lock, flags, 0o600)
    with os.fdopen(fd, "a+b") as stream:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        if path.is_symlink() or not path.is_file():
            raise BundleError("Project JSON is no longer a regular file")
        members = _decode(json.loads(path.read_text(encoding="utf-8")))
        if relative_path not in members:
            raise BundleError("Project member does not exist")
        previous = members[relative_path]
        updated = transform(previous)
        if not isinstance(updated, bytes):
            raise BundleError("Transform must return bytes")
        if updated != previous:
            members[relative_path] = updated
            _publish_members(path, members, ".sigma-transform-")
        return updated


def read_bundle(bundle_path: str | Path) -> dict[str, Any]:
    """Read and validate a complete single-file project."""
    path = Path(bundle_path)
    if path.suffix != ".json" or path.is_symlink() or not path.is_file():
        raise BundleError("Project JSON must be a regular file")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        _decode(payload)
        return payload
    except (OSError, UnicodeDecodeError, ValueError, TypeError) as exc:
        raise BundleError("Cannot read project JSON") from exc


def download_bytes(bundle_path: str | Path) -> bytes:
    """Serialize every project member, including binary artifacts."""
    payload = read_bundle(bundle_path)
    return (json.dumps(payload, sort_keys=True, indent=2) + "\n").encode("utf-8")


def import_bundle(payload: dict[str, Any], destination: str | Path) -> Path:
    """Import a complete JSON project with atomic no-replace publication."""
    members = _decode(payload)
    path = Path(destination)
    if path.suffix != ".json" or path.parent.is_symlink() or not path.parent.is_dir():
        raise BundleError("Invalid JSON project destination")
    if os.path.lexists(path):
        raise BundleError("Project destination already exists")
    # Session provenance includes the project path. Rebase only owned session
    # records when importing a complete project to a new location.
    project_document = json.loads(members["project.json"])
    project_id = project_document.get("id")
    for member, raw in list(members.items()):
        if not (member.startswith("research-sessions/") and member.endswith(".json")):
            continue
        if member in {"research-sessions/limits.json", "research-sessions/sequence.json"}:
            continue
        try:
            session = json.loads(raw)
        except (ValueError, UnicodeDecodeError) as exc:
            raise BundleError("Cannot import unreadable research session") from exc
        if not isinstance(session, dict) or session.get("project_id") != project_id:
            raise BundleError("Cannot import foreign research session")
        session_id = member.removeprefix("research-sessions/").removesuffix(".json")
        from uuid import UUID

        try:
            if str(UUID(session_id)) != session_id:
                raise ValueError("Noncanonical session identifier")
        except (ValueError, TypeError) as exc:
            raise BundleError("Cannot import invalid research session identifier") from exc
        if (
            session.get("id") != session_id
            or type(session.get("session_number")) is not int
            or session["session_number"] < 1
            or not isinstance(session.get("status"), str)
            or not isinstance(session.get("project_path"), str)
        ):
            raise BundleError("Cannot import malformed research session")
        session["project_path"] = str(path.resolve())
        members[member] = (
            json.dumps(session, ensure_ascii=False, separators=(",", ":")) + "\n"
        ).encode()
    canonical = {
        "format": FORMAT,
        "version": VERSION,
        "files": {
            name: base64.b64encode(data).decode("ascii") for name, data in sorted(members.items())
        },
    }
    fd, name = tempfile.mkstemp(prefix=".sigma-import-", dir=path.parent)
    staged = Path(name)
    try:
        with os.fdopen(fd, "wb") as output:
            output.write((json.dumps(canonical, sort_keys=True, indent=2) + "\n").encode("utf-8"))
            output.flush()
            os.fsync(output.fileno())
        try:
            os.link(staged, path)
        except FileExistsError as exc:
            raise BundleError("Project destination already exists") from exc
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        staged.unlink(missing_ok=True)
    return path


def transform_members(
    bundle_path: str | Path,
    update: Callable[[dict[str, bytes]], dict[str, bytes | None]],
) -> None:
    """Transactionally update bundle members after inspecting the locked snapshot.

    The callback sees a copy of every member and returns changed members only.
    Validation and quota decisions are made under the same lock as publication.
    """
    path = Path(bundle_path)
    if path.suffix != ".json" or path.is_symlink() or not path.is_file():
        raise BundleError("Project JSON must be a regular file")
    lock = path.with_name("." + path.name + ".write.lock")
    fd = os.open(lock, os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(fd, "a+b") as stream:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        if path.is_symlink() or not path.is_file():
            raise BundleError("Project JSON is no longer a regular file")
        members = _decode(json.loads(path.read_text(encoding="utf-8")))
        changes = update(dict(members))
        if not isinstance(changes, dict):
            raise BundleError("Bundle transaction must return a dictionary")
        for name, value in changes.items():
            if (
                not isinstance(name, str)
                or not name
                or chr(92) in name
                or name.startswith("/")
                or any(part in ("", ".", "..") for part in name.split("/"))
            ):
                raise BundleError("Unsafe bundle path")
            if value is not None and not isinstance(value, bytes):
                raise BundleError("Bundle transaction values must be bytes or None")
            if name == "project.json" and value is None:
                raise BundleError("Cannot remove project document")
            if value is None:
                members.pop(name, None)
            else:
                members[name] = value
        if changes:
            _decode(
                {
                    "format": FORMAT,
                    "version": VERSION,
                    "files": {
                        name: base64.b64encode(data).decode("ascii")
                        for name, data in members.items()
                    },
                }
            )
            _publish_members(path, members, ".sigma-transaction-")
