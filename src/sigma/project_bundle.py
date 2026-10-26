"""Lossless, portable snapshot of a legacy SIGMA project directory.

This module deliberately does not mutate live storage. The snapshot includes all
regular files, including research sessions, evidence and artifacts, so callers
can verify round trips before migrating project paths.
"""

from __future__ import annotations

import base64
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
        os.rename(temporary, destination)
    finally:
        if temporary.exists():
            import shutil
            shutil.rmtree(temporary)
