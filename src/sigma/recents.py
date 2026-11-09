"""Application access index for projects the user opened or created."""

import fcntl
import json
import os
import re
import stat
import sys
import threading
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

# Only guard same-thread recursion; other workers still serialize with flock.
_INDEX_STACK = threading.local()


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


def _legacy_pins_before_lock(directory: Path) -> tuple[str, dict[str, str]] | None:
    """Resolve v1 pin titles before taking the Recent-index file lock.

    Modern v2 indexes need no project reads. Check the exact source text again
    under the lock before publishing a migration, since another process may
    have upgraded or edited the file in between.
    """
    path = directory / "recents.json"
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except FileNotFoundError:
        return None
    with os.fdopen(fd, encoding="utf-8") as stream:
        _check_index_file(stream.fileno())
        raw = stream.read(1000001)
    if len(raw) > 1000000:
        raise ValueError("Saved Projects index is too large")
    value = _validate(json.loads(raw))
    if value["version"] != 1:
        return None
    pins: dict[str, str] = {}
    for entry in value["entries"]:
        if not entry.get("pinned", False):
            continue
        view = inspect_project(entry["path"])
        if view.project.id != entry["id"]:
            raise ValueError("Legacy pin project identity changed")
        family = project_family(view.project.title)
        if family in pins and pins[family] != entry["id"]:
            raise ValueError("Conflicting legacy project pins")
        pins[family] = entry["id"]
    return raw, pins


@contextmanager
def _index(*, blocking: bool = True):
    descriptor = None
    directory = state_directory()
    lock_path = directory / "recents.lock"
    held = getattr(_INDEX_STACK, "paths", None)
    if held is None:
        held = set()
        _INDEX_STACK.paths = held
    if lock_path in held:
        raise ProjectError("Recent Projects index cannot be reopened during an index transaction.")
    held.add(lock_path)
    try:
        # No project/sample inspection belongs to an index transaction.
        v1_pins = _legacy_pins_before_lock(directory)
        descriptor = os.open(
            directory / "recents.lock",
            os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK,
            0o600,
        )
        _check_index_file(descriptor)
        fcntl.flock(
            descriptor,
            fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB),
        )
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
            if v1_pins is None or v1_pins[0] != raw:
                raise ProjectError("Legacy Saved Projects index changed during upgrade; retry.")
            value["entries"] = [
                {key: item for key, item in entry.items() if key != "pinned"}
                for entry in value["entries"]
            ]
            value["version"] = 2
            value["pins"] = v1_pins[1]
        if "dismissed_default_pins" not in value:
            value["dismissed_default_pins"] = []
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
    except (ProjectError, BlockingIOError):
        raise
    except (OSError, ValueError, TypeError, KeyError):
        raise ProjectError(
            "Saved Projects index is unavailable. Verify its entries and private state directory; the original index and research were preserved."
        ) from None
    finally:
        if descriptor is not None:
            os.close(descriptor)
        held.remove(lock_path)


def _snapshot() -> dict:
    """Read the atomically published index without taking a writer lock."""
    directory = state_directory()
    try:
        try:
            fd = os.open(
                directory / "recents.json",
                os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
            )
        except FileNotFoundError:
            return {
                "version": 2,
                "entries": [],
                "bootstrapped_roots": {},
                "pins": {},
                "dismissed_default_pins": [],
            }
        with os.fdopen(fd, encoding="utf-8") as stream:
            _check_index_file(stream.fileno())
            raw = stream.read(1000001)
        if len(raw) > 1000000:
            raise ValueError("Index too large")
        index = _validate(json.loads(raw))
        if index["version"] == 1:
            # The original one-time migration is the only reader requiring a write lock.
            with _index() as migrated:
                index = dict(migrated)
        index.setdefault("dismissed_default_pins", [])
        return index
    except ProjectError:
        raise
    except (OSError, ValueError, TypeError, KeyError):
        raise ProjectError(
            "Saved Projects index is unavailable; original data was preserved."
        ) from None


def record_access(view: ProjectView) -> None:
    """A secondary index failure must not turn a successful research write into a retry."""
    from sigma import cloud_workspaces

    workspace = cloud_workspaces.current()
    if workspace is not None and workspace.guest:
        return
    from sigma.samples import SAMPLES

    if Path(view.path).is_relative_to(SAMPLES):
        return
    try:
        with _index(blocking=False) as index:
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
    except BlockingIOError:
        return  # Last-opened ordering is advisory.
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


def _import_local_admin_recents() -> set[str]:
    """Copy the original local index and return its authorized project paths.

    The original local index and its pin choices are preserved. A signed-in
    administrator then manages its own copy under the verified workspace.
    """
    from sigma import cloud_workspaces

    if not cloud_workspaces.local_legacy_owner_access():
        return set()
    with cloud_workspaces.without_workspace():
        legacy_directory = state_directory()
        legacy = _snapshot()
        entries = list(legacy["entries"])
        pins = dict(_effective_pins(legacy))
        dismissed = list(legacy.get("dismissed_default_pins", []))
    marker = str(legacy_directory)
    if marker in _snapshot()["bootstrapped_roots"]:
        return {entry["path"] for entry in entries}
    with _index() as index:
        if marker not in index["bootstrapped_roots"]:
            existing_ids = {entry["id"] for entry in index["entries"]}
            index["entries"].extend(entry for entry in entries if entry["id"] not in existing_ids)
            for family, project_id in pins.items():
                index["pins"].setdefault(family, project_id)
            index["dismissed_default_pins"] = sorted(
                set(index.get("dismissed_default_pins", [])) | set(dismissed)
            )
            index["bootstrapped_roots"][marker] = "Imported original local Saved Projects index"
    # Return this snapshot after releasing both file locks. The caller must
    # never re-open the legacy index while holding its own recents.lock.
    return {entry["path"] for entry in entries}


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


def recent_project_titles(*, exclude_id: str | None = None) -> set[str]:
    """Accessible saved titles for name allocation; never load paper metadata.

    Snapshot paths under the index lock, then release it before inspecting a
    project. This prevents the naming lock from waiting on a full Home scan
    and avoids re-entering the Recent index through legacy authorization.
    """
    from sigma import cloud_workspaces, project_collaboration
    from sigma.projects import _title_key

    workspace = cloud_workspaces.current()
    if workspace is not None and workspace.guest:
        return set()
    if workspace is not None:
        _import_local_admin_recents()
    shared = project_collaboration.shared_with_me() if workspace is not None else []
    paths = {
        entry["path"]
        for entry in _snapshot()["entries"]
        if entry["id"] != exclude_id and not entry["included_example"]
    }
    paths.update(
        row["path"] for row in shared if row["id"] != exclude_id
    )
    titles: set[str] = set()
    for path in paths:
        try:
            view = inspect_project(path)
            if view.project.id != exclude_id:
                titles.add(_title_key(view.project.title))
        except (ProjectError, OSError):
            continue
    return titles


def recent_projects() -> dict:
    from sigma import cloud_workspaces, project_collaboration

    workspace = cloud_workspaces.current()
    if workspace is not None and workspace.guest:
        return {"projects": []}
    # Resolve legacy ownership once, before acquiring the current index lock.
    # A path-specific local_legacy_owner_access() lookup can acquire the legacy
    # recents.lock, which is the *same file* in unpartitioned local mode.
    legacy_owner = workspace is not None and cloud_workspaces.local_legacy_owner_access()
    legacy_paths = _import_local_admin_recents() if legacy_owner else set()
    from sigma.projects import local_projects_root

    legacy_root = local_projects_root() if legacy_owner else None
    shared_rows = project_collaboration.shared_with_me() if workspace is not None else []
    shared_paths = project_collaboration.shared_project_paths() if workspace is not None else set()
    shared_by_path = {row["path"]: row for row in shared_rows}
    from sigma.samples import sample_project_ids

    try:
        sample_ids = sample_project_ids()
    except (ProjectError, OSError, ValueError, TypeError, KeyError):
        sample_ids = set()
    index = _snapshot()
    pins = _effective_pins(index)
    entries = []
    for entry in index["entries"]:
        if entry["included_example"] or entry["id"] in sample_ids:
            continue
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
        if (
            workspace is not None
            and not Path(copied["path"]).is_relative_to(workspace.path)
            and copied["path"] not in shared_by_path
            and not (
                legacy_root is not None
                and (
                    Path(copied["path"]).is_relative_to(legacy_root)
                    or copied["path"] in legacy_paths
                )
            )
        ):
            continue
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
    from sigma.research_sessions import has_active_session

    recent = []
    for entry in entries:
        try:
            view = inspect_project(entry["path"])
            if str(UUID(view.project.id)) != entry["id"]:
                raise ProjectError("Project identity changed")
            from sigma import paper_scores, papers

            paper_metadata = paper_scores.project_metadata(view.path)
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
                        paper_activity=papers.activity_status(view.path),
                        difficulty=view.project.difficulty,
                        research_running=has_active_session(view.path, project_id=view.project.id),
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
    # Project validation can consult the legacy access index; never call it
    # from inside the active recents.lock transaction.
    view = inspect_project(path) if pinned else None
    if view is not None and view.project.id != project_id:
        raise ProjectError("Project identity changed. Reopen it before pinning.")
    family = project_family(view.project.title) if view is not None else None
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
        assert family is not None
        if active.get(family) == project_id:
            return
        if family in active:
            raise ProjectError("Another version of this project is pinned. Unpin it first.")
        pins[family] = project_id
        if family in index["dismissed_default_pins"]:
            index["dismissed_default_pins"].remove(family)
