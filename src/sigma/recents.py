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
from time import monotonic, sleep
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


def _tighten_owned_state_directory(path: Path) -> None:
    """Repair old local state directory modes without trusting paths or ownership.

    Only a directory owned by this process is eligible. Use a descriptor to
    prevent a symlink swap between verification and chmod.
    """
    try:
        fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    except FileNotFoundError:
        return  # private_directory will create the directory.
    try:
        info = os.fstat(fd)
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid():
            raise ProjectError("Recent Projects state directory is not owned by SIGMA.")
        if (info.st_mode & 0o777) != 0o700:
            os.fchmod(fd, 0o700)
    finally:
        os.close(fd)


def _check_index_file(fd: int) -> None:
    """Tighten legacy owner-owned index files; reject unsafe file identities."""
    info = os.fstat(fd)
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or info.st_nlink != 1:
        raise ValueError("Unsafe Recent Projects file identity")
    if info.st_mode & 0o077:
        os.fchmod(fd, 0o600)
        info = os.fstat(fd)
    if info.st_mode & 0o077:
        raise ValueError("Recent Projects file could not be made private")


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
        _tighten_owned_state_directory(path)
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
        expected_keys = {
            "id",
            "path",
            "accessed_at",
            "included_example",
        }
        if not isinstance(item, dict) or set(item) not in (
            expected_keys,
            expected_keys | ({"pinned"} if value["version"] == 1 else set()),
        ):
            raise ValueError()
        if value["version"] == 1 and "pinned" in item and type(item["pinned"]) is not bool:
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
    # Sample files are immutable templates. Read them before acquiring the saved-index
    # lock, so concurrent Home polling and project creation never hold that lock
    # while decoding every sample project.
    from sigma.samples import sample_project_ids

    try:
        sample_ids = sample_project_ids()
    except (ProjectError, OSError, ValueError, TypeError, KeyError):
        sample_ids = set()
    descriptor = None
    try:
        directory = state_directory()
        descriptor = os.open(
            directory / "recents.lock",
            os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK,
            0o600,
        )
        _check_index_file(descriptor)
        # A stuck index writer must not hold Saved or project creation forever.
        deadline = monotonic() + 5
        while True:
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError as exc:
                if monotonic() >= deadline:
                    raise ProjectError(
                        "Saved Projects index is busy. Retry or check backend logs."
                    ) from exc
                sleep(0.05)
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
                _check_index_file(stream.fileno())
                raw = stream.read(1000001)
                if len(raw) > 1000000:
                    raise ValueError()
                value = _validate(json.loads(raw))
        original = json.dumps(value, sort_keys=True)
        if value["version"] == 1:
            legacy_pins: dict[str, str] = {}
            for entry in value["entries"]:
                if not entry.get("pinned", False):
                    continue
                view = inspect_project(entry["path"])
                if view.project.id != entry["id"]:
                    raise ValueError("Legacy pin project identity changed")
                family = project_family(view.project.title)
                if family in legacy_pins and legacy_pins[family] != entry["id"]:
                    raise ValueError("Conflicting legacy project pins")
                legacy_pins[family] = entry["id"]
            value["entries"] = [
                {key: item for key, item in entry.items() if key != "pinned"}
                for entry in value["entries"]
            ]
            value["version"] = 2
            value["pins"] = legacy_pins
        if "dismissed_default_pins" not in value:
            value["dismissed_default_pins"] = []
        # Older releases inserted canonical sample examples in Recents. Keep
        # their directories but show only independent user work here.
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
            "Saved Projects index is unavailable. Verify its entries and private state directory; the original index and research were preserved."
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
        # Retired Saved pins must not prevent removal of a project.
        forgotten = {entry["id"] for entry in matched}
        index["pins"] = {
            family: project_id
            for family, project_id in index["pins"].items()
            if project_id not in forgotten
        }
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
    pinned: bool = False
    pin_state: str = "remove"
    hidden_by_family_pin: bool = False
    error: str | None = None
    project_type_snapshot: dict | None = None
    paper_count: int = 0
    best_paper_score: int | None = None
    paper_activity: str | None = None
    shared: bool = False


def recent_projects(*, lightweight: bool = False, activity_only: bool = False) -> dict:
    """Render project identity first; expensive status and paper details are optional."""
    from sigma import cloud_workspaces, papers, project_collaboration
    from sigma.research_sessions import has_active_session

    workspace = cloud_workspaces.current()
    if workspace is not None and workspace.guest:
        return {"projects": []}
    shared_rows, shared_paths = project_collaboration.shared_listing()
    shared_by_path = {row["path"]: row for row in shared_rows}
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
        known_paths = {entry["path"] for entry in entries}
        for row in shared_rows:
            if row["path"] not in known_paths:
                entries.append(
                    {
                        "id": row["id"],
                        "path": row["path"],
                        "accessed_at": datetime.now(UTC).isoformat(),
                        "included_example": False,
                    }
                )
    # Private entries belong to this workspace. Cross-workspace entries must
    # originate from the authorized collaboration directory only.
    if workspace is not None:
        entries = [
            entry
            for entry in entries
            if Path(entry["path"]).is_relative_to(workspace.path) or entry["path"] in shared_by_path
        ]

    recent = []
    for entry in entries:
        try:
            view = inspect_project(entry["path"])
            if str(UUID(view.project.id)) != entry["id"]:
                raise ProjectError("Project identity changed")
            paper_metadata = {"paper_count": 0, "best_paper_score": None}
            if not lightweight and not activity_only:
                from sigma import paper_scores

                try:
                    paper_metadata = paper_scores.project_metadata(view.path)
                except Exception:  # noqa: BLE001 - paper decoration must never block project access
                    # Broken paper decoration must never make the project unavailable.
                    paper_metadata = {"paper_count": 0, "best_paper_score": None}
            recent.append(
                asdict(
                    RecentProject(
                        **entry,
                        title=view.project.title,
                        investigation_type=view.project.investigation_type,
                        project_type_snapshot=view.project.project_type_snapshot,
                        strategy_count=len(view.project.active_order),
                        paper_count=paper_metadata["paper_count"],
                        best_paper_score=paper_metadata["best_paper_score"],
                        paper_activity=(
                            papers.activity_status(view.path) if not lightweight else None
                        ),
                        difficulty=view.project.difficulty,
                        research_running=(
                            has_active_session(view.path, project_id=view.project.id)
                            if not lightweight
                            else False
                        ),
                        available=True,
                        shared=view.path in shared_paths,
                        pinned=(view.project.id in pins.values()),
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
                        pinned=(entry["id"] in pins.values()),
                        pin_state="unpin" if entry["id"] in pins.values() else "remove",
                        error="Unavailable or changed identity. Restore the saved project file, or forget this entry.",
                    )
                )
            )
    return {"projects": recent}


def home_projects(*, lightweight: bool = False) -> dict:
    return recent_projects(lightweight=lightweight)


def recent_activity() -> dict:
    """Return activity without reading paper records; intended for UI polling."""
    return {
        "projects": [
            {
                "id": item["id"],
                "research_running": item["research_running"],
                "paper_activity": item["paper_activity"],
            }
            for item in recent_projects(activity_only=True)["projects"]
            if item["available"]
        ]
    }


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
