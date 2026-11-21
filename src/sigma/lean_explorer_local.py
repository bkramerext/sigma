"""Local, filesystem-backed Lean source tree for Lean Explorer.

Explicitly configured for a LOCAL SIGMA process. Index paths, not source
contents; read selected Lean modules on demand. .lake/build trees and symlinks
are never followed. The working directory remains mutable, not verified Lean.
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
from functools import lru_cache
from pathlib import Path, PurePosixPath
from typing import Any, Callable

from sigma import cloud_auth, cloud_workspaces
from sigma.projects import ProjectError
from sigma.recents import state_directory
from sigma.ui_instance import private_directory

MAX_FILES = 400_000
MAX_INDEX_BYTES = 80 * 1024 * 1024
MAX_SOURCE_BYTES = 3 * 1024 * 1024
MAX_QUERY_RESULTS = 250
_EXCLUDE = {
    ".git", ".lake", ".venv", ".idea", ".vscode", "__pycache__",
    "node_modules", "build", "_build", "dist", "target",
}


def require_local() -> None:
    # Refuse hosted/prod deployments, even when their proxy connects on loopback.
    if not cloud_auth.config().local or cloud_workspaces.enabled():
        raise ProjectError("Local Lean directories are available only in local SIGMA.")


def _directory() -> Path:
    require_local()
    root = state_directory() / "lean-explorer-local"
    try:
        private_directory(root)
    except (OSError, RuntimeError) as exc:
        raise ProjectError("Local Lean Explorer state directory is unavailable.") from exc
    return root


def _validate_root(path: str) -> Path:
    if not isinstance(path, str) or not path.strip() or len(path) > 4096:
        raise ProjectError("Enter an absolute local Lean directory path.")
    candidate = Path(path.strip()).expanduser()
    if not candidate.is_absolute():
        raise ProjectError("Enter an absolute directory path, such as ~/rh-lean/lean.")
    try:
        resolved = candidate.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise ProjectError("The selected directory does not exist.") from exc
    if not resolved.is_dir() or resolved == Path(resolved.anchor):
        raise ProjectError("Choose the Lean project directory, not the filesystem root.")
    # No directory above the user's home: prevent scanning an entire device.
    home = Path.home().resolve()
    if resolved == home or resolved in home.parents:
        raise ProjectError("Choose the extracted Lean directory, not your home directory.")
    return resolved


def _config_file() -> Path:
    return _directory() / "source.json"


def _index_file() -> Path:
    return _directory() / "modules.json"


def _read_json(path: Path, limit: int) -> Any:
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(fd, "rb") as stream:
            info = os.fstat(stream.fileno())
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_uid != os.getuid()
                or info.st_mode & 0o077
                or info.st_nlink != 1
            ):
                raise ProjectError("Local Lean Explorer state is not private.")
            data = stream.read(limit + 1)
        if len(data) > limit:
            raise ProjectError("Local Lean Explorer source index is too large.")
        return json.loads(data)
    except FileNotFoundError:
        return None
    except (OSError, ValueError, UnicodeError) as exc:
        raise ProjectError("The saved local Lean directory index could not be read.") from exc


def _atomic_json(path: Path, value: Any) -> None:
    data = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if len(data) > MAX_INDEX_BYTES:
        raise ProjectError("The local Lean source index exceeds its storage limit.")
    temp = path.with_name(path.name + "." + os.urandom(8).hex() + ".tmp")
    try:
        fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        if temp.exists():
            temp.unlink()


def _root_id(root: Path) -> str:
    return hashlib.sha256(str(root).encode("utf-8")).hexdigest()[:20]


def source() -> dict[str, Any] | None:
    record = _read_json(_config_file(), 16_384)
    if record is None:
        return None
    if not isinstance(record, dict) or record.get("mode") != "local":
        raise ProjectError("Invalid local Lean Explorer source configuration.")
    resolved = _validate_root(record.get("directory", ""))
    if record.get("root_id") != _root_id(resolved):
        raise ProjectError("The configured Lean directory identity changed.")
    return {"mode": "local", "directory": str(resolved), "root_id": record["root_id"],
            "indexed_at": record.get("indexed_at"), "file_count": record.get("file_count", 0)}


@lru_cache(maxsize=3)
def _cached_modules(root_id: str, index_mtime_ns: int) -> tuple[list[str], frozenset[str]]:
    blob = _read_json(_index_file(), MAX_INDEX_BYTES)
    if not isinstance(blob, dict) or blob.get("root_id") != root_id:
        raise ProjectError("The local directory must be indexed again.")
    names = blob.get("files")
    if not isinstance(names, list) or not all(isinstance(v, str) for v in names):
        raise ProjectError("The local Lean source index is invalid.")
    if len(names) > MAX_FILES:
        raise ProjectError("The Lean index exceeds its module limit.")
    return names, frozenset(names)


def _modules() -> tuple[list[str], frozenset[str]]:
    cfg = source()
    if cfg is None:
        raise ProjectError("Select a local Lean directory first.")
    index_path = _index_file()
    try:
        mtime = index_path.stat().st_mtime_ns
    except OSError as exc:
        raise ProjectError("The local directory must be indexed again.") from exc
    return _cached_modules(cfg["root_id"], mtime)


def _paths(root: Path, progress: Callable[[int, int, str], None] | None) -> list[str]:
    paths: list[str] = []
    scanned_dirs = 0
    for current, dirs, files in os.walk(root, topdown=True, followlinks=False):
        current_path = Path(current)
        depth = len(current_path.relative_to(root).parts)
        if depth > 36:
            dirs.clear()
            continue
        dirs[:] = [
            name for name in dirs
            if name not in _EXCLUDE and not name.startswith(".")
            and not (current_path / name).is_symlink()
        ]
        scanned_dirs += 1
        for filename in files:
            if not filename.endswith(".lean") or filename.startswith("."):
                continue
            candidate = current_path / filename
            if candidate.is_symlink() or not candidate.is_file():
                continue
            relative = candidate.relative_to(root).as_posix()
            paths.append(relative)
            if len(paths) > MAX_FILES:
                raise ProjectError("The directory exceeds the supported 400,000 Lean files.")
        if progress is not None and scanned_dirs % 250 == 0:
            progress(scanned_dirs, len(paths), current_path.relative_to(root).as_posix())
    paths.sort()
    if not paths:
        raise ProjectError("No .lean files were found under the selected directory.")
    if progress is not None:
        progress(scanned_dirs, len(paths), "complete")
    return paths


def configure(directory: str, progress: Callable[[int, int, str], None] | None = None) -> dict:
    require_local()
    root = _validate_root(directory)
    found = _paths(root, progress)
    cfg = {
        "mode": "local",
        "directory": str(root),
        "root_id": _root_id(root),
        "file_count": len(found),
    }
    index_path = _index_file()
    _atomic_json(index_path, {"root_id": cfg["root_id"], "files": found})
    _atomic_json(_config_file(), cfg)
    _cached_modules.cache_clear()
    return {**cfg, "sample": found[:30], "index_type": "local filesystem file inventory"}


def list_files(query: str = "", offset: int = 0, limit: int = 100) -> dict:
    if len(query) > 250 or not 0 <= offset <= MAX_FILES or not 1 <= limit <= MAX_QUERY_RESULTS:
        raise ProjectError("Invalid file search query or page.")
    cfg = source()
    if cfg is None:
        raise ProjectError("Select a local Lean directory first.")
    paths, _ = _modules()
    needle = query.strip().casefold()
    matches = [name for name in paths if needle in name.casefold()] if needle else paths
    return {
        "root_id": cfg["root_id"],
        "directory": cfg["directory"],
        "total_files": len(paths),
        "total_matches": len(matches),
        "offset": offset,
        "limit": limit,
        "files": matches[offset:offset + limit],
    }


def read_module(relative: str) -> tuple[bytes, str, str, str]:
    cfg = source()
    if cfg is None:
        raise ProjectError("Select a local Lean directory first.")
    if not relative or len(relative) > 800 or not relative.endswith(".lean"):
        raise ProjectError("Select a .lean module within the indexed directory.")
    pure = PurePosixPath(relative)
    if pure.is_absolute() or ".." in pure.parts or "." in pure.parts:
        raise ProjectError("Lean file path must remain under the selected directory.")
    _, module_set = _modules()
    if relative not in module_set:
        raise ProjectError("This Lean file is not in the local module index. Rescan the directory.")
    root = Path(cfg["directory"])
    candidate = root.joinpath(*pure.parts)
    try:
        check_path = root
        for component in pure.parts:
            check_path = check_path / component
            if check_path.is_symlink():
                raise ProjectError("Symlinked Lean modules are not supported.")
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(root)
        if not resolved.is_file():
            raise ProjectError("The selected Lean module is not a regular file.")
        if resolved.stat().st_size > MAX_SOURCE_BYTES:
            raise ProjectError("This Lean module exceeds the per-file source limit.")
        payload = resolved.read_bytes()
    except (OSError, ValueError, RuntimeError) as exc:
        raise ProjectError("The selected local Lean module could not be read.") from exc
    if len(payload) > MAX_SOURCE_BYTES:
        raise ProjectError("This Lean module exceeds the per-file source limit.")
    # Local roots are not immutable snapshots. Each opened file is hashed.
    return payload, "local/" + cfg["root_id"] + "/" + relative, "local:" + cfg["root_id"], ""
