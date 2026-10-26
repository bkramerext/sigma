"""Lossless, portable snapshot of a legacy SIGMA project directory.

This module deliberately does not mutate live storage. The snapshot includes all
regular files, including research sessions, evidence and artifacts, so callers
can verify round trips before migrating project paths.
"""

from __future__ import annotations

import base64
import fcntl
import json
import os
import stat
import tempfile
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
    return entries


def snapshot(directory: str | Path) -> dict[str, Any]:
    """Capture every project file, without omitting binary evidence or artifacts."""
    return {"format": FORMAT, "version": VERSION, "files": _files(Path(directory))}


def encode(directory: str | Path) -> bytes:
    return (json.dumps(snapshot(directory), sort_keys=True, indent=2) + "\n").encode("utf-8")


def _decode(bundle: dict[str, Any]) -> dict[str, bytes]:
    if not isinstance(bundle, dict) or set(bundle) != {"format", "version", "files"}:
        raise BundleError("Invalid project bundle")
    if bundle["format"] != FORMAT or type(bundle["version"]) is not int or bundle["version"] != VERSION:
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
        if not isinstance(encoded, str):
            raise BundleError("Invalid encoded file")
        try:
            result[name] = base64.b64decode(encoded, validate=True)
        except (ValueError, base64.binascii.Error) as exc:
            raise BundleError("Invalid encoded file") from exc
    try:
        document = json.loads(result["project.json"])
    except (ValueError, UnicodeDecodeError) as exc:
        raise BundleError("Invalid project document") from exc
    if not isinstance(document, dict) or "schema_version" not in document:
        raise BundleError("Invalid project document")
    return result


def restore(bundle: dict[str, Any], destination: str | Path) -> None:
    """Restore only to a nonexistent directory; never overwrite live project data."""
    destination = Path(destination)
    files = _decode(bundle)
    if os.path.lexists(destination):
        raise BundleError("Project destination already exists")
    if destination.parent.is_symlink() or not destination.parent.is_dir():
        raise BundleError("Project destination parent must be a real directory")
    temporary = Path(tempfile.mkdtemp(prefix=".sigma-restore-", dir=destination.parent))
    try:
        for name, data in files.items():
            target = temporary / name
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("xb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
        # Never replace an existing destination, even if another writer raced us.
        if os.path.lexists(destination):
            raise BundleError("Project destination already exists")
        os.rename(temporary, destination)
    finally:
        if temporary.exists():
            import shutil
            shutil.rmtree(temporary)


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
        contents = (json.dumps({"format": FORMAT, "version": VERSION, "files": before},
                               sort_keys=True, indent=2) + "\n").encode("utf-8")
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
        payload = {
            "format": FORMAT,
            "version": VERSION,
            "files": {
                name: base64.b64encode(data).decode("ascii")
                for name, data in sorted(members.items())
            },
        }
        fd, name = tempfile.mkstemp(prefix=".sigma-update-", dir=path.parent)
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
