"""Typed project commands shared by every adapter; reads never change history."""

import json
import os
import tempfile
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4


class ProjectError(ValueError):
    """An invalid request or a project that cannot safely be used."""


@dataclass(frozen=True)
class Event:
    sequence: int
    kind: str
    timestamp: str


@dataclass(frozen=True)
class Project:
    schema_version: int
    id: str
    title: str
    problem: str
    events: tuple[Event, ...]


@dataclass(frozen=True)
class ProjectView:
    path: str
    project: Project


ROOT = Path(__file__).resolve().parents[2]
SEED = ROOT / "projects/rh.sigma"
STATE = "project.json"


def project_path(value: str | Path) -> Path:
    try:
        path = Path(value).expanduser().absolute()
        if path.is_symlink():
            raise ProjectError("Project directory must not be a symbolic link")
        path = path.resolve()
        if path.suffix != ".sigma":
            raise ProjectError("Project path must end in .sigma")
        return path
    except (OSError, ValueError, RuntimeError) as exc:
        raise ProjectError(f"Invalid project path: {exc}") from exc


def _decode(raw: Any) -> Project:
    if (
        not isinstance(raw, dict)
        or type(raw.get("schema_version")) is not int
        or raw["schema_version"] != 1
    ):
        raise ProjectError("Unsupported or missing project schema_version (expected 1)")
    if set(raw) != {"schema_version", "id", "title", "problem", "events"}:
        raise ProjectError("Invalid project fields")
    for key in ("id", "title", "problem"):
        if not isinstance(raw[key], str) or not raw[key].strip():
            raise ProjectError(f"Project {key} must be a nonempty string")
    UUID(raw["id"])
    if not isinstance(raw["events"], list) or not raw["events"]:
        raise ProjectError("Project requires an initialization event")
    events: list[Event] = []
    previous = None
    for index, item in enumerate(raw["events"], 1):
        if not isinstance(item, dict) or set(item) != {"sequence", "kind", "timestamp"}:
            raise ProjectError("Invalid event fields")
        if type(item["sequence"]) is not int or item["sequence"] != index:
            raise ProjectError("Event sequence must be contiguous and ordered")
        if item["kind"] != "project.initialized" or index != 1:
            raise ProjectError("Unsupported lifecycle event")
        stamp = datetime.fromisoformat(item["timestamp"])
        if stamp.tzinfo is None or (previous is not None and stamp < previous):
            raise ProjectError("Event timestamps must be timezone-aware and ordered")
        previous = stamp
        events.append(Event(index, item["kind"], item["timestamp"]))
    return Project(1, raw["id"], raw["title"], raw["problem"], tuple(events))


def inspect_project(value: str | Path) -> ProjectView:
    path = project_path(value)
    state = path / STATE
    try:
        if state.is_symlink() or not state.is_file():
            raise ProjectError("Project has no regular project.json; initialize it explicitly")
        project = _decode(json.loads(state.read_text(encoding="utf-8")))
        return ProjectView(str(path), project)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        raise ProjectError(f"Cannot open {path}: {exc}") from exc


def initialize_project(value: str | Path, title: str, problem: str) -> ProjectView:
    path = project_path(value)
    if not title.strip() or not problem.strip():
        raise ProjectError("Title and problem must be nonempty")
    created = False
    temporary: str | None = None
    try:
        if not path.exists():
            path.mkdir()  # Parent must exist; do not create unrelated directories.
            created = True
        if not path.is_dir():
            raise ProjectError("Project path is not a directory")
        if any(p.name != ".gitkeep" for p in path.iterdir()):
            raise ProjectError("Initialization requires an empty directory (or .gitkeep only)")
        project = Project(
            1,
            str(uuid4()),
            title.strip(),
            problem.strip(),
            (Event(1, "project.initialized", datetime.now(UTC).isoformat()),),
        )
        # Stage and fsync before atomic, no-replace publication. Concurrent initializers
        # cannot overwrite one another; the final link fails if project.json exists.
        fd, temporary = tempfile.mkstemp(prefix=".sigma-init-", dir=path)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(asdict(project), stream, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, path / STATE)
        return ProjectView(str(path), project)
    except OSError as exc:
        raise ProjectError(f"Cannot initialize {path}: {exc}") from exc
    finally:
        if temporary is not None:
            Path(temporary).unlink(missing_ok=True)
        if created:
            try:
                path.rmdir()  # Only remove an empty directory owned by this attempt.
            except OSError:
                pass


def open_project(value: str | Path) -> ProjectView:
    path = project_path(value)
    # Only the checked-in RH seed has implicit initialization. Unknown/corrupt
    # directories always require an explicit init command and are never repaired.
    if path == SEED and path.is_dir() and not (path / STATE).exists():
        try:
            return initialize_project(
                path,
                "Riemann Hypothesis",
                (
                    "Investigate approaches to the Riemann Hypothesis. "
                    "Evidence and finite experiments are not proofs."
                ),
            )
        except ProjectError:
            if (path / STATE).is_file():
                return inspect_project(path)
            raise
    return inspect_project(path)


def list_events(value: str | Path) -> tuple[Event, ...]:
    return inspect_project(value).project.events


def close_project() -> None:
    """Release the caller's view; services retain no handles or global session."""
