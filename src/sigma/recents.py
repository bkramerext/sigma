"""Application access index for projects the user opened or created."""

import fcntl
import json
import os
import re
import stat
import sys
import unicodedata
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
    _stage,
    inspect_project,
)
from sigma.ui_instance import private_directory


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


def project_family(title: str) -> str:
    """Group case-insensitive project titles differing only in a terminal version."""
    normalized = " ".join(unicodedata.normalize("NFKC", title).casefold().split())
    base = re.sub(
        r"\s+(?:v(?:ersion)?\s*\d+(?:\.\d+)*|\(\s*v(?:ersion)?\s*\d+(?:\.\d+)*\s*\))$",
        "",
        normalized,
    ).strip()
    return base or normalized


def _paper_test_defaults() -> dict[str, str]:
    """Reviewed project choices checked into source control; never modify archived projects."""
    manifest_path = ROOT / "projects" / "paper-test-pins.json"
    if not manifest_path.exists():
        return {}
    value = json.loads(manifest_path.read_text(encoding="utf-8"))
    if (
        not isinstance(value, dict)
        or value.get("schema_version") != 1
        or not isinstance(value.get("projects"), list)
    ):
        raise ValueError("Invalid paper-test pin manifest")
    selected: dict[str, str] = {}
    for record in value["projects"]:
        if (
            not isinstance(record, dict)
            or not isinstance(record.get("title"), str)
            or not isinstance(record.get("id"), str)
            or not isinstance(record.get("source"), str)
        ):
            raise TypeError("Invalid paper-test pin record")
        family = project_family(record["title"])
        project_id = str(UUID(record["id"]))
        if project_id != record["id"] or not family or family in selected:
            raise ValueError("Conflicting paper-test pin defaults")
        selected[family] = project_id
    return selected


def _effective_pins(index: dict) -> dict[str, str]:
    """Default pins apply only after the specific project has been opened."""
    pins = dict(index["pins"])
    saved_ids = {entry["id"] for entry in index["entries"]}
    dismissed = set(index.get("dismissed_default_pins", []))
    for family, project_id in _paper_test_defaults().items():
        if family not in pins and family not in dismissed and project_id in saved_ids:
            pins[family] = project_id
    return pins


def _validate(value: Any) -> dict:
    if not isinstance(value, dict) or value.get("version") not in (1, 2):
        raise ValueError()
    required = {"version", "entries", "bootstrapped_roots"}
    if value["version"] == 2:
        required.add("pins")
    if value["version"] == 2 and "dismissed_default_pins" in value:
        required.add("dismissed_default_pins")
    if set(value) != required:
        raise ValueError()
    if value["version"] == 2 and "dismissed_default_pins" in value:
        dismissed = value["dismissed_default_pins"]
        if (
            not isinstance(dismissed, list)
            or len(dismissed) > 10000
            or len(set(dismissed)) != len(dismissed)
            or any(
                not isinstance(family, str) or not family or project_family(family) != family
                for family in dismissed
            )
        ):
            raise ValueError()
    if value["version"] == 2:
        pins = value["pins"]
        if not isinstance(pins, dict) or len(pins) > 10000:
            raise ValueError()
        if any(
            not isinstance(family, str)
            or not family
            or family != project_family(family)
            or not isinstance(project_id, str)
            for family, project_id in pins.items()
        ):
            raise ValueError()
        try:
            ids = [str(UUID(project_id)) for project_id in pins.values()]
        except ValueError as exc:
            raise ValueError() from exc
        if len(set(ids)) != len(ids) or any(
            raw != canonical for raw, canonical in zip(pins.values(), ids)
        ):
            raise ValueError()
    if not isinstance(value["entries"], list) or not isinstance(value["bootstrapped_roots"], dict):
        raise TypeError()
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
            value = {
                "version": 2,
                "entries": [],
                "bootstrapped_roots": {},
                "pins": {},
                "dismissed_default_pins": [],
            }
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
        if value["version"] == 1:
            value["version"] = 2
            value["pins"] = {}
        if "dismissed_default_pins" not in value:
            value["dismissed_default_pins"] = []
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
    except ProjectError:
        raise
    except (OSError, ValueError, TypeError, KeyError):
        raise ProjectError(
            "Recent Projects index is unavailable. Check its owned 0700 directory/0600 files; research was not altered."
        ) from None
    finally:
        if descriptor is not None:
            os.close(descriptor)


def record_access(view: ProjectView) -> None:
    """A secondary index failure must not turn a successful research write into a retry."""
    from sigma import cloud_workspaces

    workspace = cloud_workspaces.current()
    if workspace is not None and workspace.guest:
        return
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
            index["entries"] = entries
    except ProjectError:
        print(
            "Recent Projects could not be updated. The project operation succeeded; check application state permissions.",
            file=sys.stderr,
        )


def forget_recent(project_id: str, path: str | None = None) -> None:
    """Forget a saved entry by identity, or by its saved path if identity drifted."""
    with _index() as index:
        matched = [
            entry
            for entry in index["entries"]
            if entry["id"] == project_id or (path is not None and entry["path"] == path)
        ]
        if any(entry["id"] in _effective_pins(index).values() for entry in matched):
            raise ProjectError("Unpin this project before removing it from Saved Projects.")
        index["entries"] = [
            entry
            for entry in index["entries"]
            if entry["id"] != project_id and (path is None or entry["path"] != path)
        ]


@dataclass(frozen=True)
class RecentProject:
    id: str
    path: str
    title: str
    investigation_type: str | None
    strategy_count: int | None
    difficulty: str | None
    research_running: bool
    accessed_at: str | None
    included_example: bool
    available: bool
    pin_state: str = "remove"
    hidden_by_family_pin: bool = False
    error: str | None = None
    project_type_snapshot: dict | None = None


def recent_projects() -> dict:
    from sigma import cloud_workspaces

    workspace = cloud_workspaces.current()
    if workspace is not None and workspace.guest:
        return {"projects": []}
    with _index() as index:
        pins = _effective_pins(index)
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
                        investigation_type=view.project.investigation_type,
                        project_type_snapshot=view.project.project_type_snapshot,
                        strategy_count=len(view.project.active_order),
                        difficulty=view.project.difficulty,
                        research_running=has_active_session(view.path),
                        available=True,
                        pin_state=(
                            "unpin"
                            if view.project.id in pins.values()
                            else "remove"
                            if project_family(view.project.title) in pins
                            else "pin_remove"
                        ),
                        hidden_by_family_pin=(
                            project_family(view.project.title) in pins
                            and pins[project_family(view.project.title)] != view.project.id
                        ),
                    )
                )
            )
        except (ProjectError, OSError):
            recent.append(
                asdict(
                    RecentProject(
                        **entry,
                        title=Path(entry["path"]).name,
                        investigation_type=None,
                        project_type_snapshot=None,
                        strategy_count=None,
                        difficulty=None,
                        research_running=False,
                        available=False,
                        pin_state="unpin" if entry["id"] in pins.values() else "remove",
                        error="Unavailable or changed identity. Restore the saved project file, or forget this entry.",
                    )
                )
            )
    return {"projects": recent}


def home_projects() -> dict:
    return recent_projects()


def pinned_projects() -> dict:
    """Paper-test source selection; does not launch or authorize generation."""
    return {
        "projects": [
            item
            for item in recent_projects()["projects"]
            if item["pin_state"] == "unpin" and item["available"]
        ]
    }


def assert_project_unpinned(project_id: str) -> None:
    """Protect pinned records from destructive deletion and title changes."""
    with _index() as index:
        if project_id in _effective_pins(index).values():
            raise ProjectError("Unpin this project before removing or renaming it.")


def set_project_pin(project_id: str, path: str, pinned: bool) -> None:
    """Atomically select at most one Saved Project per version family."""
    if type(pinned) is not bool:
        raise ProjectError("Pin state must be true or false.")
    with _index() as index:
        entry = next(
            (row for row in index["entries"] if row["id"] == project_id and row["path"] == path),
            None,
        )
        if entry is None:
            raise ProjectError("Project is not in Saved Projects. Open it before pinning.")
        pins = index["pins"]
        active = _effective_pins(index)
        if not pinned:
            family = next((key for key, value in active.items() if value == project_id), None)
            if family is None:
                raise ProjectError("Only the pinned version can be unpinned.")
            pins.pop(family, None)
            if family not in index["dismissed_default_pins"]:
                index["dismissed_default_pins"].append(family)
            return
        view = inspect_project(path)
        if view.project.id != project_id:
            raise ProjectError("Project identity changed. Reopen it before pinning.")
        family = project_family(view.project.title)
        if active.get(family) == project_id:
            return
        if family in active:
            raise ProjectError("Another version of this project is pinned. Unpin it first.")
        pins[family] = project_id
        if family in index["dismissed_default_pins"]:
            index["dismissed_default_pins"].remove(family)
