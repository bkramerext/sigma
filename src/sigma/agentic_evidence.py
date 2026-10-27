"""Bounded, private, per-project records of public agentic run evidence."""

import fcntl
import json
import os
import re
import stat
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from sigma.projects import ProjectError, _stage, inspect_project, project_path

DIRECTORY = "agentic-runs"
LOCK = ".agentic-runs.lock"
MAX_RECORD_BYTES = 512 * 1024
MAX_RECORDS = 32
MAX_TOTAL_BYTES = 8 * 1024 * 1024


def now() -> str:
    return datetime.now(UTC).isoformat()


def _run_id(value: Any) -> str:
    try:
        return UUID(hex=value).hex
    except (ValueError, TypeError, AttributeError) as exc:
        raise ProjectError("Invalid agentic run ID") from exc


def _directory(path: Path, create: bool) -> Path:
    directory = path / DIRECTORY
    if create:
        try:
            directory.mkdir(mode=0o700, exist_ok=True)
        except OSError as exc:
            raise ProjectError(f"Cannot create agentic evidence directory: {exc}") from exc
    if directory.is_symlink() or not directory.is_dir():
        if not create and not directory.exists() and not directory.is_symlink():
            return directory
        raise ProjectError("Agentic evidence directory must be a regular directory")
    mode = stat.S_IMODE(directory.stat(follow_symlinks=False).st_mode)
    if directory.stat(follow_symlinks=False).st_uid != os.getuid() or mode & 0o077:
        raise ProjectError("Agentic evidence directory permissions must be private (0700)")
    return directory


def _lock(path: Path):
    lock_path = (
        path.with_name("." + path.name + LOCK)
        if path.suffix == ".json"
        else path / LOCK
    )
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    stream = os.fdopen(fd, "rb")
    lock_stat = os.fstat(stream.fileno())
    if (
        not stat.S_ISREG(lock_stat.st_mode)
        or lock_stat.st_uid != os.getuid()
        or stat.S_IMODE(lock_stat.st_mode) & 0o077
    ):
        stream.close()
        raise ProjectError("Agentic evidence lock must be a regular file")
    fcntl.flock(stream, fcntl.LOCK_EX)
    return stream


def _encoded(record: dict[str, Any]) -> bytes:
    try:
        contents = (
            json.dumps(record, ensure_ascii=False, indent=2) + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ProjectError("Agentic evidence is not valid JSON") from exc
    if len(contents) > MAX_RECORD_BYTES:
        raise ProjectError("Agentic evidence record exceeds the 512 KB limit")
    return contents


def _entries(directory: Path, project_id: str) -> list[tuple[Path, int, dict[str, Any]]]:
    entries = []
    for file in directory.iterdir():
        if not re.fullmatch(r"[0-9a-f]{32}\.json", file.name):
            continue
        if file.is_symlink() or not file.is_file():
            raise ProjectError("Agentic evidence contains an unsafe record path")
        file_stat = file.stat(follow_symlinks=False)
        if file_stat.st_uid != os.getuid() or stat.S_IMODE(file_stat.st_mode) & 0o077:
            raise ProjectError("Agentic evidence record permissions must be private (0600)")
        size = file_stat.st_size
        if size > MAX_RECORD_BYTES:
            raise ProjectError("Agentic evidence record exceeds the 512 KB limit")
        try:
            record = json.loads(file.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ProjectError(f"Agentic evidence record {file.name} is unreadable") from exc
        if (
            not isinstance(record, dict)
            or record.get("schema_version") != 1
            or record.get("project_id") != project_id
            or record.get("run_id") != file.stem
        ):
            raise ProjectError(f"Agentic evidence record {file.name} does not match this project")
        entries.append((file, size, record))
    entries.sort(key=lambda entry: (entry[2].get("started_at", ""), entry[0].name))
    return entries


def _bundle_entries(path: Path, project_id: str) -> list[tuple[str, int, dict[str, Any]]]:
    from sigma.project_bundle import list_files, read_file

    prefix = "evidence/agentic-runs/"
    entries: list[tuple[str, int, dict[str, Any]]] = []
    for name in list_files(path):
        if not name.startswith(prefix) or not re.fullmatch(
            r"[0-9a-f]{32}\.json",
            name[len(prefix) :],
        ):
            continue
        contents = read_file(path, name)
        if len(contents) > MAX_RECORD_BYTES:
            raise ProjectError("Agentic evidence record exceeds the 512 KB limit")
        try:
            record = json.loads(contents)
        except (OSError, ValueError, UnicodeDecodeError) as exc:
            raise ProjectError(f"Agentic evidence record {name} is unreadable") from exc
        if (
            not isinstance(record, dict)
            or record.get("schema_version") != 1
            or record.get("project_id") != project_id
            or record.get("run_id") != Path(name).stem
        ):
            raise ProjectError(f"Agentic evidence record {name} does not match this project")
        entries.append((name, len(contents), record))
    entries.sort(key=lambda item: (item[2].get("started_at", ""), item[0]))
    return entries


def save(path_value: str | Path, record: dict[str, Any]) -> None:
    from sigma.samples import SAMPLES

    try:
        candidate = Path(path_value).expanduser().absolute().resolve()
        sample_root = SAMPLES.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise ProjectError(f"Invalid agentic evidence project path: {exc}") from exc
    if candidate.is_relative_to(sample_root):
        raise ProjectError(
            "Sample source projects are immutable; open a copy to record agentic runs"
        )
    view = inspect_project(path_value)
    path = project_path(path_value)
    if record.get("project_id") != view.project.id:
        raise ProjectError("Agentic evidence does not match this project copy")
    run_id = _run_id(record.get("run_id"))
    contents = _encoded(record)
    if path.suffix == ".json":
        from sigma.projects import save_project_artifacts

        destination = f"evidence/agentic-runs/{run_id}.json"
        with _lock(path):
            entries = _bundle_entries(path, view.project.id)
            retained = [
                (name, size, item)
                for name, size, item in entries
                if name != destination
            ]
            retained.append((destination, len(contents), record))
            retained.sort(key=lambda item: (item[2].get("started_at", ""), item[0]))
            total = sum(size for _, size, _ in retained)
            changes: dict[str, bytes | None] = {destination: contents}
            while len(retained) > MAX_RECORDS or total > MAX_TOTAL_BYTES:
                oldest = retained.pop(0)
                if oldest[0] == destination:
                    raise ProjectError("Agentic evidence record exceeds total retention capacity")
                changes[oldest[0]] = None
                total -= oldest[1]
            save_project_artifacts(path, changes)
        return
    directory = _directory(path, create=True)
    with _lock(path):
        entries = _entries(directory, view.project.id)
        destination = directory / f"{run_id}.json"
        if destination.is_symlink():
            raise ProjectError("Agentic evidence destination must not be a symlink")
        if destination.exists() and not destination.is_file():
            raise ProjectError("Agentic evidence destination must be a regular file")
        retained = [(file, size, item) for file, size, item in entries if file != destination]
        retained.append((destination, len(contents), record))
        retained.sort(key=lambda entry: (entry[2].get("started_at", ""), entry[0].name))
        total = sum(size for _, size, _ in retained)
        prune: list[Path] = []
        while len(retained) > MAX_RECORDS or total > MAX_TOTAL_BYTES:
            oldest = retained.pop(0)
            if oldest[0] == destination:
                raise ProjectError("Agentic evidence record exceeds total retention capacity")
            prune.append(oldest[0])
            total -= oldest[1]
        staged = _stage(directory, contents)
        try:
            if destination.exists():
                os.replace(staged, destination)
            else:
                os.link(staged, destination)
                staged.unlink()
            descriptor = os.open(directory, os.O_RDONLY)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
        except OSError as exc:
            raise ProjectError(f"Cannot save agentic evidence record: {exc}") from exc
        finally:
            staged.unlink(missing_ok=True)
        try:
            for old_record in prune:
                old_record.unlink()
        except OSError as exc:
            raise ProjectError(
                f"Saved this run, but could not prune expired evidence: {exc}"
            ) from exc


def list_runs(path_value: str | Path) -> list[dict[str, Any]]:
    view = inspect_project(path_value)
    path = project_path(path_value)
    if path.suffix == ".json":
        with _lock(path):
            entries = _bundle_entries(path, view.project.id)
    else:
        directory = _directory(path, create=False)
        if not directory.exists():
            return []
        with _lock(path):
            entries = _entries(directory, view.project.id)
    return [
        {
            "run_id": record["run_id"],
            "started_at": record["started_at"],
            "finished_at": record.get("finished_at"),
            "status": (record.get("terminal") or {}).get("status", "running"),
            "project_id": record["project_id"],
        }
        for _, _, record in reversed(entries)
    ]


def get_run(path_value: str | Path, run_id: str) -> dict[str, Any]:
    view = inspect_project(path_value)
    path = project_path(path_value)
    identifier = _run_id(run_id)
    if path.suffix == ".json":
        with _lock(path):
            entries = _bundle_entries(path, view.project.id)
    else:
        directory = _directory(path, create=False)
        if not directory.exists():
            raise ProjectError("Agentic run was not found in this project")
        with _lock(path):
            entries = _entries(directory, view.project.id)
    match = next((record for _, _, record in entries if record["run_id"] == identifier), None)
    if match is None:
        raise ProjectError("Agentic run was not found in this project")
    return match
