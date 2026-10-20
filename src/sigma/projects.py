"""Typed project commands shared by every adapter; reads never change history."""

import fcntl
import json
import os
import stat
import tempfile
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal
from uuid import UUID, uuid4


class ProjectError(ValueError):
    """An invalid request or a project that cannot safely be used."""


@dataclass(frozen=True)
class Event:
    sequence: int
    kind: str
    timestamp: str
    strategy_id: str | None = None


@dataclass(frozen=True)
class Strategy:
    id: str
    title: str
    approach: str
    author_kind: Literal["human"]
    created_at: str


@dataclass(frozen=True)
class Project:
    schema_version: int
    id: str
    title: str
    problem: str
    events: tuple[Event, ...]
    strategies: tuple[Strategy, ...] = ()


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


def _timestamp(value: Any) -> datetime:
    if not isinstance(value, str):
        raise ProjectError("Timestamp must be a string")
    stamp = datetime.fromisoformat(value)
    if stamp.tzinfo is None:
        raise ProjectError("Timestamps must include a timezone")
    return stamp


def _text(value: Any, name: str, limit: int) -> str:
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > limit:
        raise ProjectError(f"{name} must contain 1–{limit} characters")
    return value.strip()


def _decode(raw: Any) -> Project:
    if (
        not isinstance(raw, dict)
        or type(raw.get("schema_version")) is not int
        or raw["schema_version"] not in (1, 2)
    ):
        raise ProjectError("Unsupported or missing project schema_version (expected 1 or 2)")
    version = raw["schema_version"]
    fields = {"schema_version", "id", "title", "problem", "events"}
    if version == 2:
        fields.add("strategies")
    if set(raw) != fields:
        raise ProjectError("Invalid project fields")
    for key in ("id", "title", "problem"):
        if not isinstance(raw[key], str) or not raw[key].strip():
            raise ProjectError(f"Project {key} must be a nonempty string")
    UUID(raw["id"])
    strategies: list[Strategy] = []
    seen: set[str] = set()
    if version == 2:
        if not isinstance(raw["strategies"], list):
            raise ProjectError("Strategies must be a list")
        for item in raw["strategies"]:
            if not isinstance(item, dict) or set(item) != {
                "id",
                "title",
                "approach",
                "author_kind",
                "created_at",
            }:
                raise ProjectError("Invalid strategy fields")
            if not isinstance(item["id"], str) or item["id"] in seen:
                raise ProjectError("Strategy identities must be unique strings")
            UUID(item["id"])
            seen.add(item["id"])
            _text(item["title"], "Strategy title", 200)
            _text(item["approach"], "Hypothesis / approach", 10000)
            if item["author_kind"] != "human":
                raise ProjectError("Only human-authored strategies are supported")
            _timestamp(item["created_at"])
            strategies.append(Strategy(**item))
    if not isinstance(raw["events"], list) or len(raw["events"]) != len(strategies) + 1:
        raise ProjectError("Project requires an initialization event and one event per strategy")
    events: list[Event] = []
    previous = None
    for index, item in enumerate(raw["events"], 1):
        if not isinstance(item, dict):
            raise ProjectError("Invalid event")
        expected = {"sequence", "kind", "timestamp"}
        if index > 1:
            expected.add("strategy_id")
        if set(item) != expected:
            raise ProjectError("Invalid event fields")
        if type(item["sequence"]) is not int or item["sequence"] != index:
            raise ProjectError("Event sequence must be contiguous and ordered")
        stamp = _timestamp(item["timestamp"])
        if previous is not None and stamp < previous:
            raise ProjectError("Event timestamps must be ordered")
        previous = stamp
        if index == 1:
            if item["kind"] != "project.initialized":
                raise ProjectError("First event must initialize the project")
        else:
            strategy = strategies[index - 2]
            if (
                item["kind"] != "strategy.created"
                or item["strategy_id"] != strategy.id
                or item["timestamp"] != strategy.created_at
            ):
                raise ProjectError("Strategy creation event does not match its record")
        events.append(Event(**item))
    return Project(
        version, raw["id"], raw["title"], raw["problem"], tuple(events), tuple(strategies)
    )


def _document(project: Project) -> bytes:
    raw = asdict(project)
    for event in raw["events"]:
        if event["strategy_id"] is None:
            del event["strategy_id"]
    return (json.dumps(raw, indent=2) + "\n").encode("utf-8")


def _stage(path: Path, contents: bytes) -> Path:
    fd, name = tempfile.mkstemp(prefix=".sigma-write-", dir=path)
    temporary = Path(name)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(contents)
            stream.flush()
            os.fsync(stream.fileno())
        return temporary
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


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
            2,
            str(uuid4()),
            title.strip(),
            problem.strip(),
            (Event(1, "project.initialized", datetime.now(UTC).isoformat()),),
        )
        # Stage and fsync before atomic, no-replace publication. Concurrent initializers
        # cannot overwrite one another; the final link fails if project.json exists.
        fd, temporary = tempfile.mkstemp(prefix=".sigma-init-", dir=path)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(_document(project).decode("utf-8"))
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


def list_strategies(value: str | Path) -> tuple[Strategy, ...]:
    return inspect_project(value).project.strategies


def create_strategy(value: str | Path, title: str, approach: str) -> ProjectView:
    """Append a human strategy and event together; migrate legacy projects on write."""
    title = _text(title, "Strategy title", 200)
    approach = _text(approach, "Hypothesis / approach", 10000)
    view = inspect_project(value)
    path = Path(view.path)
    temporary: Path | None = None
    backup_temporary: Path | None = None
    try:
        # Lock a stable inode, separate from the atomically replaced document.
        fd = os.open(path / ".write.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "rb") as lock:
            if not stat.S_ISREG(os.fstat(lock.fileno()).st_mode):
                raise ProjectError("Project write lock must be a regular file")
            fcntl.flock(lock, fcntl.LOCK_EX)
            before = (path / STATE).read_bytes()
            project = inspect_project(path).project
            timestamp = (
                max(datetime.now(UTC), _timestamp(project.events[-1].timestamp))
                .astimezone(UTC)
                .isoformat()
            )
            strategy = Strategy(str(uuid4()), title, approach, "human", timestamp)
            updated = replace(
                project,
                schema_version=2,
                strategies=(*project.strategies, strategy),
                events=(
                    *project.events,
                    Event(len(project.events) + 1, "strategy.created", timestamp, strategy.id),
                ),
            )
            contents = _document(updated)
            _decode(json.loads(contents))  # Validate the complete next document before publication.
            temporary = _stage(path, contents)
            if project.schema_version == 1:
                backup = path / "project.v1.json"
                backup_temporary = _stage(path, before)
                try:
                    os.link(backup_temporary, backup)
                except FileExistsError:
                    if backup.is_symlink() or backup.read_bytes() != before:
                        raise ProjectError("Legacy backup already exists with different contents")
            if (path / STATE).is_symlink() or (path / STATE).read_bytes() != before:
                raise ProjectError("Project changed during save; reopen and retry")
            os.replace(temporary, path / STATE)
            return ProjectView(str(path), updated)
    except OSError as exc:
        raise ProjectError(f"Cannot save strategy: {exc}") from exc
    finally:
        for staged in (temporary, backup_temporary):
            if staged is not None:
                staged.unlink(missing_ok=True)
