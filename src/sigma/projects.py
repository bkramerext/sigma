"""Typed project commands shared by every adapter; reads never change history."""

import fcntl
import hashlib
import json
import os
import re
import stat
import tempfile
import unicodedata
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any, Literal
from uuid import UUID, uuid4

from sigma.model_catalog import EFFORTS, legacy_model, validate_pair, validate_stored

MAX_STRATEGY_APPROACH = 50_000


class ProjectError(ValueError):
    """An invalid request or a project that cannot safely be used."""


class WorkspaceAccessError(ProjectError):
    """A cloud request addressed a project outside its private workspace."""


class ResearchMode(str, Enum):
    DEFAULT = "default"
    BIOLOGY = "biology"
    CHEMISTRY = "chemistry"
    COMPUTER_SCIENCE = "computer_science"
    ECONOMICS = "economics"
    ENGINEERING = "engineering"
    LAW = "law"
    MATHEMATICAL = "mathematical"
    MILITARY = "military"
    PHILOSOPHY = "philosophy"
    PHYSICS = "physics"
    RELIGION = "religion"


class Difficulty(str, Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


def _difficulty(value: str | None) -> Difficulty | None:
    if value is None:
        return None
    try:
        return Difficulty(value)
    except (ValueError, TypeError) as exc:
        raise ProjectError("Difficulty must be Easy, Medium, or Hard") from exc


def _research_mode(value: str) -> ResearchMode:
    try:
        return ResearchMode(value)
    except (ValueError, TypeError) as exc:
        raise ProjectError(
            "Research category must be Biology, Chemistry, Computer Science, Economics, Engineering, Law, Mathematics, Military, Philosophy, Physics, Religion, or Other"
        ) from exc


@dataclass(frozen=True)
class StrategyChange:
    previous_title: str
    previous_approach: str
    title: str
    approach: str


class Stage(str, Enum):
    DRAFT = "draft"
    READY = "ready"
    EXPLORING = "exploring"
    HOLD = "hold"


@dataclass(frozen=True)
class Provenance:
    provider: str
    model: str
    reasoning_effort: str | None = None


@dataclass(frozen=True)
class StageChange:
    previous: str
    stage: str


@dataclass(frozen=True)
class StrategyEnabledChange:
    previous: bool
    enabled: bool


@dataclass(frozen=True)
class ProjectSettings:
    title: str
    problem: str
    investigation_type: ResearchMode
    ai_model: str
    reasoning_effort: str
    difficulty: Difficulty | None = None
    show_advanced_outcome_details: bool = False

    @property
    def research_mode(self) -> ResearchMode:
        """Compatibility alias for existing integrations."""
        return self.investigation_type


@dataclass(frozen=True)
class ProjectChange:
    previous: ProjectSettings
    current: ProjectSettings


def _settings(raw: Any) -> ProjectSettings:
    if isinstance(raw, dict) and "research_mode" in raw and "investigation_type" not in raw:
        raw = {**raw, "investigation_type": raw["research_mode"]}
        del raw["research_mode"]
    required = {
        "title",
        "problem",
        "investigation_type",
        "ai_model",
        "reasoning_effort",
    }
    if (
        not isinstance(raw, dict)
        or not required <= set(raw)
        or set(raw) - required - {"difficulty", "show_advanced_outcome_details"}
    ):
        raise ProjectError("Invalid project settings fields")
    advanced_outcome = raw.get("show_advanced_outcome_details", False)
    if type(advanced_outcome) is not bool:
        raise ProjectError("Advanced Outcome preference must be a boolean")
    try:
        validate_stored(raw["ai_model"], raw["reasoning_effort"])
    except (ValueError, TypeError) as exc:
        raise ProjectError(str(exc)) from exc
    return ProjectSettings(
        _text(raw["title"], "Project name", 200),
        _text(raw["problem"], "Research problem", 20000),
        _research_mode(raw["investigation_type"]),
        raw["ai_model"],
        raw["reasoning_effort"],
        _difficulty(raw.get("difficulty")),
        advanced_outcome,
    )


@dataclass(frozen=True)
class Event:
    sequence: int
    kind: str
    timestamp: str
    strategy_id: str | None = None
    change: StrategyChange | None = None
    stage_change: StageChange | None = None
    order: tuple[str, ...] | None = None
    project_change: ProjectChange | None = None
    enabled_change: StrategyEnabledChange | None = None


@dataclass(frozen=True)
class Strategy:
    id: str
    title: str
    approach: str
    author_kind: Literal["human"]
    created_at: str
    removed_at: str | None = None
    stage: Stage = Stage.DRAFT
    summary: str = ""
    provenance: Provenance | None = None
    enabled: bool = True


@dataclass(frozen=True)
class Project:
    schema_version: int
    id: str
    title: str
    problem: str
    events: tuple[Event, ...]
    strategies: tuple[Strategy, ...] = ()
    investigation_type: ResearchMode = ResearchMode.DEFAULT
    active_order: tuple[str, ...] = ()
    ai_model: str = "gpt-6.1-sol"
    reasoning_effort: str = "high"
    difficulty: Difficulty | None = None
    show_advanced_outcome_details: bool = False

    @property
    def research_mode(self) -> ResearchMode:
        """Compatibility alias for existing integrations."""
        return self.investigation_type


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
            from sigma import cloud_workspaces

            if cloud_workspaces.current() is not None:
                raise WorkspaceAccessError("Project not found or access denied.")
            raise ProjectError("Project directory must not be a symbolic link")
        path = path.resolve()
        from sigma import cloud_workspaces

        try:
            cloud_workspaces.assert_project_path(value, path)
        except ValueError as exc:
            raise WorkspaceAccessError("Project not found or access denied.") from exc
        if path.suffix not in (".sigma", ".json"):
            raise ProjectError("Project path must end in .sigma or .json")
        return path
    except WorkspaceAccessError:
        raise
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
        or raw["schema_version"] not in (1, 2, 3, 4, 5, 6, 7, 8, 9)
    ):
        raise ProjectError("Unsupported or missing project schema_version (expected 1 through 9)")
    version = raw["schema_version"]
    fields = {"schema_version", "id", "title", "problem", "events"}
    if version >= 2:
        fields.add("strategies")
    if version >= 4:
        fields.add("investigation_type" if "investigation_type" in raw else "research_mode")
    if version >= 5:
        fields.add("active_order")
    if version >= 6:
        fields.update({"ai_model", "reasoning_effort"})
    if version >= 8:
        fields.add("difficulty")
    if version >= 9:
        fields.add("show_advanced_outcome_details")
    if set(raw) != fields:
        raise ProjectError("Invalid project fields")
    if version == 8 and raw["difficulty"] is None:
        raise ProjectError("Schema v8 projects must have an Easy, Medium, or Hard difficulty")
    if version >= 9 and type(raw["show_advanced_outcome_details"]) is not bool:
        raise ProjectError("Advanced Outcome preference must be a boolean")
    for key in ("id", "title", "problem"):
        if not isinstance(raw[key], str) or not raw[key].strip():
            raise ProjectError(f"Project {key} must be a nonempty string")
    UUID(raw["id"])
    mode = _research_mode(raw.get("investigation_type", raw.get("research_mode", "default")))
    settings = (
        _settings(
            {
                "title": raw["title"],
                "problem": raw["problem"],
                "investigation_type": mode,
                "ai_model": raw.get("ai_model", legacy_model()),
                "reasoning_effort": raw.get("reasoning_effort", "high"),
                "difficulty": raw.get("difficulty"),
                "show_advanced_outcome_details": raw.get("show_advanced_outcome_details", False),
            }
        )
        if version >= 6
        else ProjectSettings(raw["title"], raw["problem"], mode, legacy_model(), "high", None)
    )
    if version >= 6 and (raw["title"] != settings.title or raw["problem"] != settings.problem):
        raise ProjectError("Project settings text must be canonical")
    strategies: list[Strategy] = []
    seen: set[str] = set()
    if version >= 2:
        if not isinstance(raw["strategies"], list):
            raise ProjectError("Strategies must be a list")
        for item in raw["strategies"]:
            strategy_fields = {"id", "title", "approach", "author_kind", "created_at"}
            if version >= 3:
                strategy_fields.add("removed_at")
            if version >= 5:
                strategy_fields.update({"stage", "summary", "provenance"})
            if version >= 7:
                strategy_fields.add("enabled")
            if not isinstance(item, dict) or set(item) != strategy_fields:
                raise ProjectError("Invalid strategy fields")
            if not isinstance(item["id"], str) or item["id"] in seen:
                raise ProjectError("Strategy identities must be unique strings")
            UUID(item["id"])
            seen.add(item["id"])
            _text(item["title"], "Strategy title", 200)
            _text(item["approach"], "Hypothesis / approach", MAX_STRATEGY_APPROACH)
            if item["author_kind"] != "human":
                raise ProjectError("Only human-authored strategies are supported")
            _timestamp(item["created_at"])
            if item.get("removed_at") is not None:
                _timestamp(item["removed_at"])
            values = dict(item)
            values.setdefault("enabled", True)
            if type(values["enabled"]) is not bool:
                raise ProjectError("Strategy enabled state must be a boolean")
            if version >= 5:
                try:
                    values["stage"] = Stage(item["stage"])
                except (ValueError, TypeError) as exc:
                    raise ProjectError("Invalid manual stage") from exc
                if (
                    not isinstance(item["summary"], str)
                    or len(item["summary"]) > 300
                    or "\n" in item["summary"]
                    or "\r" in item["summary"]
                ):
                    raise ProjectError("Summary must be one line, at most 300 characters")
                provenance = item["provenance"]
                if provenance is not None:
                    if (
                        not isinstance(provenance, dict)
                        or set(provenance)
                        != (
                            {"provider", "model", "reasoning_effort"}
                            if version >= 6
                            else {"provider", "model"}
                        )
                        or provenance["provider"] != "openai"
                    ):
                        raise ProjectError("Invalid generation provenance")
                    _text(provenance["model"], "Model", 100)
                    if (
                        provenance.get("reasoning_effort") is not None
                        and provenance["reasoning_effort"] not in EFFORTS
                    ):
                        raise ProjectError("Invalid generation reasoning effort")
                    values["provenance"] = Provenance(**provenance)
            strategies.append(Strategy(**values))
    if not isinstance(raw["events"], list) or not raw["events"]:
        raise ProjectError("Project requires an initialization event")
    created: set[str] = set()
    removed: set[str] = set()
    edits: dict[str, StrategyChange] = {}
    by_id = {strategy.id: strategy for strategy in strategies}
    events: list[Event] = []
    previous = None
    active_order: list[str] = []
    stages: dict[str, str] = {}
    enabled_states = {strategy.id: True for strategy in strategies}
    project_change: ProjectChange | None = None
    for index, item in enumerate(raw["events"], 1):
        if not isinstance(item, dict):
            raise ProjectError("Invalid event")
        expected = {"sequence", "kind", "timestamp"}
        if index > 1 and item.get("kind") not in {"strategies.reordered", "project.updated"}:
            expected.add("strategy_id")
        if item.get("kind") == "strategies.reordered":
            expected.add("order")
        if item.get("kind") == "strategy.stage_changed":
            expected.add("stage_change")
        if item.get("kind") == "project.updated":
            expected.add("project_change")
        if item.get("kind") == "strategy.updated":
            expected.add("change")
        if item.get("kind") == "strategy.enabled_changed":
            expected.add("enabled_change")
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
        elif item["kind"] == "strategy.created":
            if len(created) >= len(strategies):
                raise ProjectError("Unexpected strategy creation event")
            strategy = strategies[len(created)]
            if (
                item["strategy_id"] != strategy.id
                or strategy.id in created
                or item["timestamp"] != strategy.created_at
            ):
                raise ProjectError("Strategy creation event does not match its record")
            created.add(strategy.id)
            active_order.append(strategy.id)
            stages[strategy.id] = "draft"
        elif item["kind"] == "strategy.updated" and version >= 3:
            strategy_id = item["strategy_id"]
            change = item["change"]
            if (
                not isinstance(strategy_id, str)
                or strategy_id not in created
                or strategy_id in removed
                or not isinstance(change, dict)
                or set(change) != {"previous_title", "previous_approach", "title", "approach"}
            ):
                raise ProjectError("Invalid strategy edit event")
            for field, limit in (
                ("previous_title", 200),
                ("title", 200),
                ("previous_approach", MAX_STRATEGY_APPROACH),
                ("approach", MAX_STRATEGY_APPROACH),
            ):
                _text(change[field], field, limit)
            previous_edit = edits.get(strategy_id)
            if previous_edit and (
                previous_edit.title != change["previous_title"]
                or previous_edit.approach != change["previous_approach"]
            ):
                raise ProjectError("Strategy edit history is inconsistent")
            edits[strategy_id] = StrategyChange(**change)
        elif item["kind"] == "strategy.removed" and version >= 3:
            strategy_id = item["strategy_id"]
            if (
                not isinstance(strategy_id, str)
                or strategy_id not in created
                or strategy_id in removed
                or by_id[strategy_id].removed_at != item["timestamp"]
            ):
                raise ProjectError("Strategy removal event does not match its record")
            removed.add(strategy_id)
            active_order.remove(strategy_id)
        elif item["kind"] == "strategies.reordered" and version >= 5:
            order = item["order"]
            if (
                not isinstance(order, list)
                or any(not isinstance(i, str) for i in order)
                or len(order) != len(active_order)
                or set(order) != set(active_order)
                or order == active_order
            ):
                raise ProjectError("Invalid active strategy order event")
            active_order = order.copy()
        elif item["kind"] == "strategy.stage_changed" and version >= 5:
            strategy_id = item["strategy_id"]
            change = item["stage_change"]
            if (
                not isinstance(strategy_id, str)
                or strategy_id not in active_order
                or not isinstance(change, dict)
                or set(change) != {"previous", "stage"}
            ):
                raise ProjectError("Invalid manual stage event")
            if (
                change["previous"] != stages[strategy_id]
                or change["stage"] not in {s.value for s in Stage}
                or change["stage"] == change["previous"]
            ):
                raise ProjectError("Manual stage history is inconsistent")
            stages[strategy_id] = change["stage"]
        elif item["kind"] == "strategy.enabled_changed" and version >= 7:
            strategy_id = item["strategy_id"]
            change = item["enabled_change"]
            if (
                not isinstance(strategy_id, str)
                or strategy_id not in active_order
                or not isinstance(change, dict)
                or set(change) != {"previous", "enabled"}
                or type(change["previous"]) is not bool
                or type(change["enabled"]) is not bool
                or change["previous"] != enabled_states[strategy_id]
                or change["enabled"] == change["previous"]
            ):
                raise ProjectError("Strategy enabled-state history is inconsistent")
            enabled_states[strategy_id] = change["enabled"]
        elif item["kind"] == "project.updated" and version >= 6:
            change = item["project_change"]
            if not isinstance(change, dict) or set(change) != {"previous", "current"}:
                raise ProjectError("Invalid project edit event")
            next_change = ProjectChange(_settings(change["previous"]), _settings(change["current"]))
            # Normalize legacy event keys before checking their canonical contents.
            normalized_change = {}
            for key, value in change.items():
                normalized = {
                    ("investigation_type" if field == "research_mode" else field): val
                    for field, val in value.items()
                }
                normalized.setdefault("difficulty", None)
                normalized_change[key] = normalized
            if asdict(next_change) != normalized_change:
                raise ProjectError("Project change text must be canonical")
            if next_change.previous == next_change.current or (
                project_change and project_change.current != next_change.previous
            ):
                raise ProjectError("Project settings edit chain is inconsistent")
            project_change = next_change
        else:
            raise ProjectError("Unsupported strategy event")
        event = Event(
            **{
                key: value
                for key, value in item.items()
                if key not in {"change", "stage_change", "order", "project_change"}
            }
        )
        if "change" in item:
            event = replace(event, change=StrategyChange(**item["change"]))
        if "stage_change" in item:
            event = replace(event, stage_change=StageChange(**item["stage_change"]))
        if "order" in item:
            event = replace(event, order=tuple(item["order"]))
        if "project_change" in item:
            event = replace(event, project_change=project_change)
        if "enabled_change" in item:
            event = replace(event, enabled_change=StrategyEnabledChange(**item["enabled_change"]))
        events.append(event)
    if created != seen or removed != {s.id for s in strategies if s.removed_at is not None}:
        raise ProjectError("Strategy records and history do not match")
    for strategy_id, change in edits.items():
        strategy = by_id[strategy_id]
        if strategy.title != change.title or strategy.approach != change.approach:
            raise ProjectError("Latest edit does not match the strategy record")
    if version >= 5 and (
        raw["active_order"] != active_order or any(s.stage != stages[s.id] for s in strategies)
    ):
        raise ProjectError("Strategy order/stages do not match history")
    if version >= 7 and any(
        strategy.enabled != enabled_states[strategy.id] for strategy in strategies
    ):
        raise ProjectError("Strategy enabled states do not match history")
    if project_change and project_change.current != settings:
        raise ProjectError("Latest project edit does not match settings")
    return Project(
        version,
        raw["id"],
        raw["title"],
        raw["problem"],
        tuple(events),
        tuple(strategies),
        mode,
        tuple(active_order),
        settings.ai_model,
        settings.reasoning_effort,
        settings.difficulty,
        settings.show_advanced_outcome_details,
    )


def _document(project: Project) -> bytes:
    raw = asdict(project)
    if project.schema_version < 8:
        del raw["difficulty"]
    if project.schema_version < 9:
        del raw["show_advanced_outcome_details"]
    if project.schema_version < 7:
        for strategy in raw["strategies"]:
            del strategy["enabled"]
    if project.schema_version < 6:
        del raw["ai_model"]
        del raw["reasoning_effort"]
        for strategy in raw["strategies"]:
            if strategy["provenance"] is not None:
                del strategy["provenance"]["reasoning_effort"]
    if project.schema_version < 5:
        del raw["active_order"]
        for strategy in raw["strategies"]:
            for key in ("stage", "summary", "provenance"):
                del strategy[key]
    if project.schema_version < 4:
        del raw["investigation_type"]
    if project.schema_version < 3:
        for strategy in raw["strategies"]:
            del strategy["removed_at"]
    for event in raw["events"]:
        if project.schema_version < 8 and event.get("project_change") is not None:
            for settings in event["project_change"].values():
                settings.pop("difficulty", None)
        for key in ("stage_change", "order", "project_change", "enabled_change"):
            if event[key] is None:
                del event[key]
        if event["change"] is None:
            del event["change"]
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
        if path.suffix == ".json":
            from sigma.project_bundle import read_file

            project = _decode(json.loads(read_file(path, STATE)))
            return ProjectView(str(path), project)
        if state.is_symlink() or not state.is_file():
            raise ProjectError("Project has no regular project.json; initialize it explicitly")
        project = _decode(json.loads(state.read_text(encoding="utf-8")))
        return ProjectView(str(path), project)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        raise ProjectError(f"Cannot open {path}: {exc}") from exc


def initialize_project(
    value: str | Path,
    title: str,
    problem: str,
    research_mode: str = "default",
    ai_model: str | None = None,
    reasoning_effort: str = "high",
    difficulty: str = "medium",
    show_advanced_outcome_details: bool = False,
) -> ProjectView:
    mode = _research_mode(research_mode)
    selected_difficulty = _difficulty(difficulty)
    if selected_difficulty is None:
        raise ProjectError("New projects must have a difficulty")
    resolved_model = legacy_model() if ai_model is None else ai_model
    try:
        validate_pair(resolved_model, reasoning_effort)
    except ValueError as exc:
        raise ProjectError(str(exc)) from exc
    path = project_path(value)
    if not title.strip() or not problem.strip():
        raise ProjectError("Title and problem must be nonempty")
    if path.suffix == ".json":
        from sigma.project_bundle import FORMAT, VERSION

        if os.path.lexists(path):
            raise ProjectError("Project destination already exists")
        if not path.parent.is_dir() or path.parent.is_symlink():
            raise ProjectError("Project destination parent is unavailable")
        project = Project(
            9, str(uuid4()), title.strip(), problem.strip(),
            (Event(1, "project.initialized", datetime.now(UTC).isoformat()),),
            investigation_type=mode, ai_model=resolved_model,
            reasoning_effort=reasoning_effort, difficulty=selected_difficulty,
            show_advanced_outcome_details=show_advanced_outcome_details,
        )
        import base64

        bundle = {
            "format": FORMAT, "version": VERSION,
            "files": {STATE: base64.b64encode(_document(project)).decode("ascii")},
        }
        fd, staged_name = tempfile.mkstemp(prefix=".sigma-init-", dir=path.parent)
        staged = Path(staged_name)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write((json.dumps(bundle, sort_keys=True, indent=2) + "\n").encode("utf-8"))
                stream.flush()
                os.fsync(stream.fileno())
            os.link(staged, path)
            directory_fd = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
            return ProjectView(str(path), project)
        except OSError as exc:
            raise ProjectError(f"Cannot initialize {path}: {exc}") from exc
        finally:
            staged.unlink(missing_ok=True)
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
            9,
            str(uuid4()),
            title.strip(),
            problem.strip(),
            (Event(1, "project.initialized", datetime.now(UTC).isoformat()),),
            investigation_type=mode,
            ai_model=resolved_model,
            reasoning_effort=reasoning_effort,
            difficulty=selected_difficulty,
            show_advanced_outcome_details=show_advanced_outcome_details,
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


def _open_project(value: str | Path) -> ProjectView:
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


def open_project(value: str | Path) -> ProjectView:
    view = _open_project(value)
    from sigma.recents import record_access

    record_access(view)
    return view


def list_events(value: str | Path) -> tuple[Event, ...]:
    return inspect_project(value).project.events


def close_project() -> None:
    """Release the caller's view; services retain no handles or global session."""


def list_strategies(value: str | Path) -> tuple[Strategy, ...]:
    """List the active pool; inspect retains removed records and their history."""
    project = inspect_project(value).project
    by_id = {s.id: s for s in project.strategies}
    return tuple(by_id[i] for i in project.active_order)


def create_strategy(
    value: str | Path,
    title: str,
    approach: str,
    summary: str = "",
    provenance: Provenance | None = None,
    *,
    _continuation_writer: Callable[[Project, Strategy], None] | None = None,
) -> ProjectView:
    """Append a human strategy and event together; migrate legacy projects on write."""
    title = _text(title, "Strategy title", 200)
    approach = _text(approach, "Hypothesis / approach", MAX_STRATEGY_APPROACH)

    if not isinstance(summary, str) or len(summary) > 300 or "\n" in summary or "\r" in summary:
        raise ProjectError("Summary must be one line, at most 300 characters")

    def append(project: Project) -> Project:
        timestamp = _next_timestamp(project)
        strategy = Strategy(
            str(uuid4()),
            title,
            approach,
            "human",
            timestamp,
            summary=summary.strip(),
            provenance=provenance,
        )
        if _continuation_writer is not None:
            _continuation_writer(project, strategy)
        return replace(
            project,
            schema_version=max(
                project.schema_version,
                6
                if provenance and provenance.reasoning_effort
                else 5
                if summary or provenance
                else 2,
            ),
            active_order=(*project.active_order, strategy.id),
            strategies=(*project.strategies, strategy),
            events=(
                *project.events,
                Event(len(project.events) + 1, "strategy.created", timestamp, strategy.id),
            ),
        )

    return _update_project(value, append)


def set_strategy_enabled(value: str | Path, strategy_id: str, enabled: bool) -> ProjectView:
    """Persist a strategy's eligibility without changing its content or history."""
    if type(enabled) is not bool:
        raise ProjectError("Strategy enabled state must be a boolean")

    def update(project: Project) -> Project:
        strategy = next((item for item in project.strategies if item.id == strategy_id), None)
        if strategy is None or strategy.removed_at is not None:
            raise ProjectError("Strategy not found in this project")
        if strategy.enabled is enabled:
            return project
        timestamp = _next_timestamp(project)
        return replace(
            project,
            schema_version=max(7, project.schema_version),
            strategies=tuple(
                replace(item, enabled=enabled) if item.id == strategy_id else item
                for item in project.strategies
            ),
            events=(
                *project.events,
                Event(
                    len(project.events) + 1,
                    "strategy.enabled_changed",
                    timestamp,
                    strategy_id,
                    enabled_change=StrategyEnabledChange(strategy.enabled, enabled),
                ),
            ),
        )

    return _update_project(value, update)


def remove_strategy(value: str | Path, strategy_id: str) -> ProjectView:
    """Remove from the active pool, retaining research and an explicit audit event."""

    def remove(project: Project) -> Project:
        strategy = next((s for s in project.strategies if s.id == strategy_id), None)
        if strategy is None:
            raise ProjectError("Strategy not found in this project")
        if strategy.removed_at is not None:
            raise ProjectError("Strategy has already been removed")
        timestamp = _next_timestamp(project)
        return replace(
            project,
            schema_version=max(3, project.schema_version),
            active_order=tuple(i for i in project.active_order if i != strategy_id),
            strategies=tuple(
                replace(s, removed_at=timestamp) if s.id == strategy_id else s
                for s in project.strategies
            ),
            events=(
                *project.events,
                Event(len(project.events) + 1, "strategy.removed", timestamp, strategy_id),
            ),
        )

    return _update_project(value, remove)


def edit_strategy(
    value: str | Path,
    strategy_id: str,
    title: str,
    approach: str,
    text_format: str | None = None,
    expected_digest: str | None = None,
) -> ProjectView:
    """Update name/description while preserving identity and earlier text in history."""
    title = _text(title, "Strategy name", 200)
    approach = _text(approach, "Strategy description", MAX_STRATEGY_APPROACH)

    def edit(project: Project) -> Project:
        strategy = next((s for s in project.strategies if s.id == strategy_id), None)
        if strategy is None:
            raise ProjectError("Strategy not found in this project")
        if strategy.removed_at is not None:
            raise ProjectError("Removed strategies cannot be edited")
        if (
            expected_digest is not None
            and hashlib.sha256(strategy.approach.encode()).hexdigest() != expected_digest
        ):
            raise ProjectError("Strategy description changed elsewhere. Reopen it before saving")
        if (title, approach) == (strategy.title, strategy.approach):
            return project
        change = StrategyChange(strategy.title, strategy.approach, title, approach)
        return replace(
            project,
            schema_version=max(3, project.schema_version),
            strategies=tuple(
                replace(
                    s,
                    title=title,
                    approach=approach,
                    summary="" if approach != s.approach else s.summary,
                )
                if s.id == strategy_id
                else s
                for s in project.strategies
            ),
            events=(
                *project.events,
                Event(
                    len(project.events) + 1,
                    "strategy.updated",
                    _next_timestamp(project),
                    strategy_id,
                    change,
                ),
            ),
        )

    return _update_project(
        value, edit, (f"strategy:{strategy_id}", text_format) if text_format else None
    )


def _next_timestamp(project: Project) -> str:
    return (
        max(datetime.now(UTC), _timestamp(project.events[-1].timestamp)).astimezone(UTC).isoformat()
    )


def _update_project(
    value: str | Path,
    update: Callable[[Project], Project],
    text_edit: tuple[str, str] | None = None,
) -> ProjectView:
    view = inspect_project(value)
    path = Path(view.path)
    if path.suffix == ".json":
        if text_edit is not None:
            raise ProjectError("Text-view editing is not yet supported for single-file projects")
        from sigma.project_bundle import transform_file

        def transform(previous: bytes) -> bytes:
            project = _decode(json.loads(previous))
            updated = update(project)
            return _document(updated)

        contents = transform_file(path, STATE, transform)
        return ProjectView(str(path), _decode(json.loads(contents)))
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
            updated = update(project)
            from sigma.text_views import sync_source_changes

            if updated != project or text_edit is not None:
                sync_source_changes(path, project, updated, text_edit)
            if updated == project:
                return ProjectView(str(path), project)
            contents = _document(updated)
            _decode(json.loads(contents))  # Validate the complete next document before publication.
            temporary = _stage(path, contents)
            if project.schema_version != updated.schema_version:
                backup = path / f"project.v{project.schema_version}.json"
                backup_temporary = _stage(path, before)
                try:
                    os.link(backup_temporary, backup)
                except FileExistsError:
                    if backup.is_symlink() or backup.read_bytes() != before:
                        raise ProjectError("Version backup already exists with different contents")
            if (path / STATE).is_symlink() or (path / STATE).read_bytes() != before:
                raise ProjectError("Project changed during save; reopen and retry")
            os.replace(temporary, path / STATE)
            return ProjectView(str(path), updated)
    except OSError as exc:
        raise ProjectError(f"Cannot save strategy change: {exc}") from exc
    finally:
        for staged in (temporary, backup_temporary):
            if staged is not None:
                staged.unlink(missing_ok=True)


@dataclass(frozen=True)
class ProjectDestination:
    root: str
    path: str | None
    exists: bool


def projects_root() -> Path:
    """Explicit server-side location, independent of the browser or current directory."""
    from sigma import cloud_workspaces

    workspace = cloud_workspaces.current()
    if workspace is not None:
        return workspace.path
    from sigma.storage import persistent_disk_enabled

    if persistent_disk_enabled():
        raise ProjectError("Authenticated persistent workspace is unavailable.")
    try:
        configured = Path(
            os.environ.get("SIGMA_PROJECTS_ROOT", str(ROOT / "projects"))
        ).expanduser()
        if not configured.is_absolute() or configured.is_symlink():
            raise ProjectError("SIGMA_PROJECTS_ROOT must be an absolute directory, not a symlink")
        root = configured.resolve()
        if not root.is_dir() or root.stat().st_uid != os.geteuid():
            raise ProjectError("Projects root must already exist and be owned by the server user")
        return root
    except (OSError, ValueError, RuntimeError) as exc:
        raise ProjectError(f"Projects location unavailable: {exc}") from exc


def _project_name(title: str) -> tuple[str, str]:
    title = _text(title, "Project name", 200)
    if any(char in "/\\" or ord(char) < 32 or ord(char) == 127 for char in title):
        raise ProjectError("Project name cannot contain path separators or control characters")
    slug = re.sub(r"[^\w]+", "-", unicodedata.normalize("NFKC", title).casefold()).strip("-_")[:80]
    while len(slug.encode("utf-8")) > 180:
        slug = slug[:-1]
    slug = slug.rstrip("-_")
    if not slug or not any(char.isalnum() for char in slug):
        raise ProjectError("Project name must contain a letter or number")
    return title, slug + ".sigma"


@contextmanager
def _title_registry_lock(root: Path):
    """Serialize naming changes across copies, creates and renames."""
    descriptor = os.open(root / ".names.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or info.st_mode & 0o077:
            raise ProjectError("Project naming lock is unsafe")
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        os.close(descriptor)


def _title_key(title: str) -> str:
    return unicodedata.normalize("NFKC", title).strip().casefold()


def _occupied_titles(root: Path, exclude_id: str | None = None) -> set[str]:
    """Include sample, recent (even outside the root), and local saved projects."""
    from sigma.recents import recent_projects
    from sigma.samples import sample_projects

    names = {_title_key(item["title"]) for item in sample_projects()["projects"]}
    for item in recent_projects()["projects"]:
        if item["available"] and item["id"] != exclude_id:
            names.add(_title_key(item["title"]))
    for directory in root.iterdir():
        if directory.is_symlink() or not (
            (directory.suffix == ".sigma" and directory.is_dir())
            or (directory.suffix == ".json" and directory.is_file())
        ):
            continue
        try:
            view = inspect_project(directory)
        except ProjectError:
            continue
        if view.project.id != exclude_id:
            names.add(_title_key(view.project.title))
    return names


def _require_available_title(title: str, root: Path, exclude_id: str | None = None) -> None:
    if _title_key(title) in _occupied_titles(root, exclude_id):
        raise ProjectError(
            "A sample, recent, or saved project already uses that name. Choose another name."
        )


def project_destination(title: str = "") -> ProjectDestination:
    root = projects_root()
    if not title:
        return ProjectDestination(str(root), None, False)
    _, name = _project_name(title)
    path = root / name
    taken = os.path.lexists(path) or _title_key(title) in _occupied_titles(root)
    return ProjectDestination(str(root), str(path), taken)


def create_project(
    title: str,
    problem: str,
    research_mode: str = "default",
    ai_model: str | None = None,
    reasoning_effort: str = "high",
    difficulty: str = "medium",
    show_advanced_outcome_details: bool = False,
) -> ProjectView:
    """Reserve a unique project name beneath the configured root."""
    title, name = _project_name(title)
    problem = _text(problem, "Research problem", 20000)
    mode = _research_mode(research_mode)
    root = projects_root()
    destination = root / name
    # Reject an existing destination before entering initialization. In particular,
    # never treat a pre-existing file or symlink as an empty project directory.
    if os.path.lexists(destination):
        raise ProjectError(f"A project or file already exists at {destination}; choose another name")
    with _title_registry_lock(root):
        _require_available_title(title, root)
        try:
            view = initialize_project(
                destination,
                title,
                problem,
                mode,
                ai_model,
                reasoning_effort,
                difficulty,
                show_advanced_outcome_details,
            )
            from sigma.recents import record_access

            record_access(view)
            return view
        except FileExistsError as exc:
            raise ProjectError(
                f"A project or file already exists at {destination}; choose another name"
            ) from exc
        except OSError as exc:
            raise ProjectError(f"Cannot create project: {exc}") from exc


def change_stage(value: str | Path, strategy_id: str, stage: str) -> ProjectView:
    try:
        chosen = Stage(stage)
    except (ValueError, TypeError) as exc:
        raise ProjectError(
            "Stage must be draft, ready, exploring or hold (manually tracked)"
        ) from exc

    def update(project: Project) -> Project:
        strategy = next(
            (s for s in project.strategies if s.id == strategy_id and not s.removed_at), None
        )
        if strategy is None:
            raise ProjectError("Active strategy not found")
        if strategy.stage == chosen:
            return project
        return replace(
            project,
            schema_version=max(5, project.schema_version),
            strategies=tuple(
                replace(s, stage=chosen) if s.id == strategy_id else s for s in project.strategies
            ),
            events=(
                *project.events,
                Event(
                    len(project.events) + 1,
                    "strategy.stage_changed",
                    _next_timestamp(project),
                    strategy_id,
                    stage_change=StageChange(strategy.stage, chosen),
                ),
            ),
        )

    return _update_project(value, update)


def reorder_strategies(
    value: str | Path, order: list[str], expected_order: list[str]
) -> ProjectView:
    def update(project: Project) -> Project:
        if (
            not isinstance(order, list)
            or any(not isinstance(i, str) for i in order)
            or len(order) != len(project.active_order)
            or set(order) != set(project.active_order)
        ):
            raise ProjectError("Order must contain every active strategy exactly once")
        if expected_order != list(project.active_order):
            raise ProjectError("Strategy order changed elsewhere; reopen the project and retry")
        if order == list(project.active_order):
            return project
        return replace(
            project,
            schema_version=max(5, project.schema_version),
            active_order=tuple(order),
            events=(
                *project.events,
                Event(
                    len(project.events) + 1,
                    "strategies.reordered",
                    _next_timestamp(project),
                    order=tuple(order),
                ),
            ),
        )

    return _update_project(value, update)


def project_settings(project: Project) -> ProjectSettings:
    return ProjectSettings(
        project.title,
        project.problem,
        project.investigation_type,
        project.ai_model,
        project.reasoning_effort,
        project.difficulty,
        project.show_advanced_outcome_details,
    )


def update_project(
    value: str | Path,
    title: str,
    problem: str,
    research_mode: str,
    ai_model: str,
    reasoning_effort: str,
    expected: dict[str, Any],
    text_format: str | None = None,
    difficulty: str | None = None,
    show_advanced_outcome_details: bool | None = None,
) -> ProjectView:
    wanted = _settings(
        {
            "title": title,
            "problem": problem,
            "investigation_type": research_mode,
            "ai_model": ai_model,
            "reasoning_effort": reasoning_effort,
            "difficulty": difficulty if difficulty is not None else expected.get("difficulty"),
            "show_advanced_outcome_details": (
                show_advanced_outcome_details
                if show_advanced_outcome_details is not None
                else expected.get("show_advanced_outcome_details", False)
            ),
        }
    )
    prior = _settings(expected)

    def update(project: Project) -> Project:
        current = project_settings(project)
        if current != prior:
            raise ProjectError(
                "Project settings changed elsewhere. Refresh/reopen before editing again; your changes have not been saved"
            )
        if current == wanted:
            return project
        if wanted.title != current.title:
            _require_available_title(wanted.title, projects_root(), exclude_id=project.id)
        if (wanted.ai_model, wanted.reasoning_effort) != (
            current.ai_model,
            current.reasoning_effort,
        ):
            try:
                validate_pair(wanted.ai_model, wanted.reasoning_effort)
            except ValueError as exc:
                raise ProjectError(str(exc)) from exc
        return replace(
            project,
            schema_version=max(
                9
                if wanted.show_advanced_outcome_details
                else 8
                if wanted.difficulty is not None
                else 7,
                project.schema_version,
            ),
            title=wanted.title,
            problem=wanted.problem,
            investigation_type=wanted.investigation_type,
            ai_model=wanted.ai_model,
            reasoning_effort=wanted.reasoning_effort,
            difficulty=wanted.difficulty,
            show_advanced_outcome_details=wanted.show_advanced_outcome_details,
            events=(
                *project.events,
                Event(
                    len(project.events) + 1,
                    "project.updated",
                    _next_timestamp(project),
                    project_change=ProjectChange(current, wanted),
                ),
            ),
        )

    edit = ("project", text_format) if text_format else None
    if wanted.title != prior.title:
        with _title_registry_lock(projects_root()):
            return _update_project(value, update, edit)
    return _update_project(value, update, edit)
