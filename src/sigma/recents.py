"""Four-entry application access index and exclusive, one-time example installation."""

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
    STATE,
    ProjectError,
    ProjectView,
    _decode,
    _stage,
    inspect_project,
    projects_root,
)
from sigma.ui_instance import private_directory

TEMPLATE = ROOT / "examples/nonconsecutive-subset-sums/project.json"
EXAMPLE_ID = "7a8cbb3b-da78-4249-8e9e-8f7c15b8ae7a"
EXAMPLE_NAME = "nonconsecutive-subset-sums.sigma"
HISTORY_TEMPLATE = ROOT / "examples/jesus-cannabis/project.json"
HISTORY_ID = "2b7628b3-9e25-445a-a3b4-54d69239e8bf"
HISTORY_NAME = "jesus-cannabis.sigma"


def state_directory() -> Path:
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
        or len(value["entries"]) > 4
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
    try:
        with _index() as index:
            index["entries"] = [
                {
                    "id": str(UUID(view.project.id)),
                    "path": view.path,
                    "accessed_at": datetime.now(UTC).isoformat(),
                    "included_example": False,
                },
                *(entry for entry in index["entries"] if entry["id"] != str(UUID(view.project.id))),
            ][:4]
    except ProjectError:
        print(
            "Recent Projects could not be updated. The project operation succeeded; check application state permissions.",
            file=sys.stderr,
        )


def forget_recent(project_id: str) -> None:
    with _index() as index:
        index["entries"] = [entry for entry in index["entries"] if entry["id"] != project_id]


def _install(root: Path, template: Path = TEMPLATE, example_id: str = EXAMPLE_ID, example_name: str = EXAMPLE_NAME, expected_strategies: int = 3) -> ProjectView:
    if template.is_symlink() or not template.is_file():
        raise ProjectError("Included example template must be a regular source file.")
    contents = template.read_bytes()
    project = _decode(json.loads(contents))
    if project.id != example_id or project.schema_version != 5 or len(project.strategies) != expected_strategies:
        raise ProjectError("Included example template failed its identity/schema checks.")
    destination = root / example_name
    reserved = False
    staged = None
    try:
        try:
            destination.mkdir(mode=0o700)
            reserved = True
        except FileExistsError:
            info = destination.lstat()
            if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid():
                raise ProjectError(
                    "Included example destination is not an owned regular directory."
                ) from None
            existing = inspect_project(destination)
            if existing.project.id != example_id:
                raise ProjectError(
                    "A different project occupies the included example location; it was not replaced."
                )
            return existing
        staged = _stage(destination, contents)
        os.link(staged, destination / STATE)  # Exclusive publication; exact template bytes.
        return ProjectView(str(destination), project)
    finally:
        if staged:
            staged.unlink(missing_ok=True)
        if reserved:
            try:
                destination.rmdir()  # Only an empty reservation from this attempt.
            except OSError:
                pass


def bootstrap_example() -> str:
    """One fact per configured root; reads never recreate a deleted/forgotten sample."""
    root = projects_root()
    with _index() as index:
        key = str(root)
        if key in index["bootstrapped_roots"]:
            return index["bootstrapped_roots"][key]
        try:
            view = _install(root)
        except (ProjectError, OSError, ValueError, TypeError, KeyError):
            message = "Included example could not be installed. Check the template, project-root permissions, or an existing destination; nothing was overwritten."
            # A collision is a durable bootstrap decision; transient errors may be retried.
            if (root / EXAMPLE_NAME).exists() or (root / EXAMPLE_NAME).is_symlink():
                index["bootstrapped_roots"][key] = message
            return message
        index["bootstrapped_roots"][key] = ""
        if len(index["entries"]) < 4 and not any(
            entry["id"] == view.project.id for entry in index["entries"]
        ):
            index["entries"].append(
                {
                    "id": str(UUID(view.project.id)),
                    "path": view.path,
                    "accessed_at": None,
                    "included_example": True,
                }
            )
    return ""


def bootstrap_history_example() -> str:
    """Install the second included sample once, including for previously bootstrapped roots."""
    root = projects_root()
    with _index() as index:
        key = str(root / HISTORY_NAME)
        if key in index["bootstrapped_roots"]:
            return index["bootstrapped_roots"][key]
        try:
            view = _install(root, HISTORY_TEMPLATE, HISTORY_ID, HISTORY_NAME, 5)
        except (ProjectError, OSError, ValueError, TypeError, KeyError):
            message = "Historical example could not be installed; no existing project was overwritten."
            if (root / HISTORY_NAME).exists() or (root / HISTORY_NAME).is_symlink():
                index["bootstrapped_roots"][key] = message
            return message
        index["bootstrapped_roots"][key] = ""
        if len(index["entries"]) < 4 and not any(
            entry["id"] == view.project.id for entry in index["entries"]
        ):
            index["entries"].append(
                {
                    "id": str(UUID(view.project.id)),
                    "path": view.path,
                    "accessed_at": None,
                    "included_example": True,
                }
            )
    return ""


@dataclass(frozen=True)
class RecentProject:
    id: str
    path: str
    title: str
    research_mode: str | None
    accessed_at: str | None
    included_example: bool
    available: bool
    error: str | None = None


def recent_projects() -> dict:
    with _index() as index:
        entries = [dict(entry) for entry in index["entries"]]
    recent = []
    for entry in entries:
        try:
            view = inspect_project(entry["path"])
            if str(UUID(view.project.id)) != entry["id"]:
                raise ProjectError("Project identity changed")
            recent.append(
                asdict(
                    RecentProject(
                        **entry,
                        title=view.project.title,
                        research_mode=view.project.research_mode,
                        available=True,
                    )
                )
            )
        except (ProjectError, OSError):
            recent.append(
                asdict(
                    RecentProject(
                        **entry,
                        title=Path(entry["path"]).name,
                        research_mode=None,
                        available=False,
                        error="Unavailable or changed identity. Use Open Project to locate it, or forget this entry.",
                    )
                )
            )
    return {"projects": recent}


def home_projects() -> dict:
    try:
        notice = bootstrap_example()
        historical_notice = bootstrap_history_example()
        notice = "; ".join(part for part in (notice, historical_notice) if part)
    except ProjectError as error:
        notice = str(error)
    return {**recent_projects(), "notice": notice}
