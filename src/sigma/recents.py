"""Six-entry application access index for projects the user opened or created."""

import fcntl
import json
import os
import stat
import sys
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from sigma.projects import (
    ROOT,
    ProjectError,
    ProjectView,
    ResearchMode,
    _stage,
    inspect_project,
)
from sigma.ui_instance import private_directory

MAX_PER_CATEGORY = 4
MAX_ENTRIES = MAX_PER_CATEGORY * (len(ResearchMode) + 1)


def state_directory() -> Path:
    from sigma import cloud_workspaces
    from sigma.storage import persistent_disk_enabled

    workspace_path = cloud_workspaces.private_state_directory()
    if workspace_path is not None:
        return workspace_path
    if persistent_disk_enabled():
        raise ProjectError("Authenticated persistent workspace is unavailable.")
    configured = os.environ.get("SIGMA_STATE_DIR")
    if configured:
        path = Path(configured).expanduser()
        if (
            not path.is_absolute()
            or path.resolve().is_relative_to(ROOT)
            or any(part.endswith(".sigma") for part in path.resolve().parts)
        ):
            raise ProjectError(
                "SIGMA_STATE_DIR must be absolute and outside the checkout/project packages."
            )
    else:
        base = Path(os.environ.get("XDG_STATE_HOME", str(Path.home().resolve() / ".local/state")))
        if not base.is_absolute():
            raise ProjectError("XDG_STATE_HOME must be absolute.")
        # Create missing application-state parents; refuse symlinks and foreign owners.
        for parent in reversed((base, *base.parents)):
            if parent == Path(parent.anchor):
                continue
            if not parent.exists():
                parent.mkdir(mode=0o700)
            info = parent.lstat()
            if not stat.S_ISDIR(info.st_mode) or (parent == base and info.st_uid != os.getuid()):
                raise ProjectError("Unsafe application state parent.")
        path = base / "sigma"
    if path.resolve().is_relative_to(ROOT) or any(
        part.endswith(".sigma") for part in path.resolve().parts
    ):
        raise ProjectError("Application state must remain outside the checkout/project packages.")
    try:
        private_directory(path)
    except (OSError, RuntimeError):
        raise ProjectError("Recent Projects needs an owned private 0700 state directory.") from None
    return path


def _validate(value: Any) -> dict:
    if (
        not isinstance(value, dict)
        or set(value) != {"version", "entries", "bootstrapped_roots"}
        or value["version"] != 1
    ):
        raise ValueError()
    if (
        not isinstance(value["entries"], list)
        or len(value["entries"]) > MAX_ENTRIES
        or not isinstance(value["bootstrapped_roots"], dict)
    ):
        raise ValueError()
    seen = set()
    for item in value["entries"]:
        if not isinstance(item, dict) or set(item) != {
            "id",
            "path",
            "accessed_at",
            "included_example",
        }:
            raise ValueError()
        if not isinstance(item["id"], str):
            raise TypeError()
        UUID(item["id"])
        if (
            item["id"] in seen
            or not isinstance(item["path"], str)
            or not Path(item["path"]).is_absolute()
            or type(item["included_example"]) is not bool
        ):
            raise ValueError()
        seen.add(item["id"])
        if item["accessed_at"] is not None:
            if (
                datetime.fromisoformat(item["accessed_at"]).tzinfo is None
                or item["included_example"]
            ):
                raise ValueError()
        elif not item["included_example"]:
            raise ValueError()
    if any(
        not isinstance(key, str) or not Path(key).is_absolute() or not isinstance(message, str)
        for key, message in value["bootstrapped_roots"].items()
    ):
        raise ValueError()
    return value


@contextmanager
def _index():
    descriptor = None
    try:
        directory = state_directory()
        descriptor = os.open(
            directory / "recents.lock",
            os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK,
            0o600,
        )
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise ValueError()
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        path = directory / "recents.json"
        try:
            read_fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        except FileNotFoundError:
            value = {"version": 1, "entries": [], "bootstrapped_roots": {}}
        else:
            with os.fdopen(read_fd, encoding="utf-8") as stream:
                info = os.fstat(stream.fileno())
                if (
                    not stat.S_ISREG(info.st_mode)
                    or info.st_uid != os.getuid()
                    or info.st_mode & 0o077
                ):
                    raise ValueError()
                raw = stream.read(1000001)
                if len(raw) > 1000000:
                    raise ValueError()
                value = _validate(json.loads(raw))
        original = json.dumps(value, sort_keys=True)
        # Older releases inserted canonical sample examples in Recents. Keep
        # their directories but show only independent user work here.
        from sigma.samples import sample_project_ids

        try:
            sample_ids = sample_project_ids()
        except (ProjectError, OSError, ValueError, TypeError, KeyError):
            sample_ids = set()
        value["entries"] = [
            entry
            for entry in value["entries"]
            if not entry["included_example"] and entry["id"] not in sample_ids
        ]
        yield value
        _validate(value)
        encoded = json.dumps(value, indent=2).encode()
        if len(encoded) > 1000000:
            raise ValueError()
        if json.dumps(value, sort_keys=True) != original:
            staged = _stage(directory, encoded)
            try:
                os.replace(staged, path)
                parent_fd = os.open(directory, os.O_RDONLY)
                try:
                    os.fsync(parent_fd)
                finally:
                    os.close(parent_fd)
            finally:
                staged.unlink(missing_ok=True)
    except (OSError, ValueError, TypeError, KeyError):
        raise ProjectError(
            "Recent Projects index is unavailable. Check its owned 0700 directory/0600 files; research was not altered."
        ) from None
    finally:
        if descriptor is not None:
            os.close(descriptor)


def record_access(view: ProjectView) -> None:
    """A secondary index failure must not turn a successful research write into a retry."""
    from sigma.samples import sample_project_ids

    try:
        if view.project.id in sample_project_ids():
            return
    except (ProjectError, OSError, ValueError, TypeError, KeyError):
        pass
    try:
        with _index() as index:
            entries = [
                {
                    "id": str(UUID(view.project.id)),
                    "path": view.path,
                    "accessed_at": datetime.now(UTC).isoformat(),
                    "included_example": False,
                },
                *(entry for entry in index["entries"] if entry["id"] != str(UUID(view.project.id))),
            ]
            category_counts: dict[str | None, int] = {}
            retained = []
            for entry in entries:
                category: str | None
                if entry["id"] == str(UUID(view.project.id)):
                    category = view.project.investigation_type.value
                else:
                    try:
                        existing = inspect_project(entry["path"])
                        if str(UUID(existing.project.id)) != entry["id"]:
                            category = None
                        else:
                            category = existing.project.investigation_type.value
                    except (ProjectError, OSError, ValueError):
                        category = None
                count = category_counts.get(category, 0)
                if count >= MAX_PER_CATEGORY:
                    continue
                category_counts[category] = count + 1
                retained.append(entry)
            index["entries"] = retained
    except ProjectError:
        print(
            "Recent Projects could not be updated. The project operation succeeded; check application state permissions.",
            file=sys.stderr,
        )


def forget_recent(project_id: str) -> None:
    with _index() as index:
        index["entries"] = [entry for entry in index["entries"] if entry["id"] != project_id]


@dataclass(frozen=True)
class RecentProject:
    id: str
    path: str
    title: str
    investigation_type: str | None
    strategy_count: int | None
    running: bool
    difficulty: str | None
    research_running: bool
    accessed_at: str | None
    included_example: bool
    available: bool
    error: str | None = None


def recent_projects() -> dict:
    with _index() as index:
        from sigma import cloud_workspaces

        workspace = cloud_workspaces.current()
        entries = []
        for entry in index["entries"]:
            copied = dict(entry)
            if workspace is not None:
                old_path = Path(copied["path"])
                try:
                    marker = old_path.parts.index(workspace.workspace_id)
                    suffix = old_path.parts[marker + 1 :]
                    if suffix and all(part not in {".", ".."} for part in suffix):
                        rebased = workspace.path.joinpath(*suffix)
                        if rebased.is_relative_to(workspace.path):
                            copied["path"] = str(rebased)
                            entry["path"] = str(rebased)
                except ValueError:
                    pass
            entries.append(copied)
    from sigma.research_sessions import has_active_session

    recent = []
    category_counts: dict[str | None, int] = {}
    for entry in entries:
        try:
            view = inspect_project(entry["path"])
            if str(UUID(view.project.id)) != entry["id"]:
                raise ProjectError("Project identity changed")
            category = view.project.investigation_type.value
            from sigma.research_sessions import read_session_snapshot

            sessions, _ = read_session_snapshot(entry["path"])
            if category_counts.get(category, 0) >= MAX_PER_CATEGORY:
                continue
            category_counts[category] = category_counts.get(category, 0) + 1
            recent.append(
                asdict(
                    RecentProject(
                        **entry,
                        title=view.project.title,
                        investigation_type=view.project.investigation_type,
                        strategy_count=len(view.project.active_order),
                        running=any(session.get("status") == "running" for session in sessions),
                        difficulty=view.project.difficulty,
                        research_running=has_active_session(view.path),
                        available=True,
                    )
                )
            )
        except (ProjectError, OSError):
            if category_counts.get(None, 0) >= MAX_PER_CATEGORY:
                continue
            category_counts[None] = category_counts.get(None, 0) + 1
            recent.append(
                asdict(
                    RecentProject(
                        **entry,
                        title=Path(entry["path"]).name,
                        investigation_type=None,
                        strategy_count=None,
                        running=False,
                        difficulty=None,
                        research_running=False,
                        available=False,
                        error="Unavailable or changed identity. Use Open Project to locate it, or forget this entry.",
                    )
                )
            )
    return {"projects": recent}


def home_projects() -> dict:
    return recent_projects()
