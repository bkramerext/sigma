"""Typed investigation commands shared by every adapter; reads never change history."""

import fcntl
import hashlib
import json
import os
import re
import stat
import tempfile
import unicodedata
from collections.abc import Callable
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any, Literal
from uuid import UUID, uuid4

from sigma.model_catalog import EFFORTS, legacy_model, validate_pair, validate_stored


class InvestigationError(ValueError):
    """An invalid request or investigation that cannot safely be used."""


class ResearchMode(str, Enum):
    DEFAULT = "default"
    MATHEMATICAL = "mathematical"


def _research_mode(value: str) -> ResearchMode:
    try:
        return ResearchMode(value)
    except (ValueError, TypeError) as exc:
        raise InvestigationError("Research mode must be default or mathematical") from exc


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
class InvestigationSettings:
    title: str
    problem: str
    investigation_type: ResearchMode
    ai_model: str
    reasoning_effort: str

    @property
    def research_mode(self) -> ResearchMode:
        """Compatibility alias for existing integrations."""
        return self.investigation_type


@dataclass(frozen=True)
class InvestigationChange:
    previous: InvestigationSettings
    current: InvestigationSettings


def _settings(raw: Any) -> InvestigationSettings:
    if isinstance(raw, dict) and "research_mode" in raw and "investigation_type" not in raw:
        raw = {**raw, "investigation_type": raw["research_mode"]}
        del raw["research_mode"]
    if not isinstance(raw, dict) or set(raw) != {
        "title",
        "problem",
        "investigation_type",
        "ai_model",
        "reasoning_effort",
    }:
        raise InvestigationError("Invalid investigation settings fields")
    try:
        validate_stored(raw["ai_model"], raw["reasoning_effort"])
    except (ValueError, TypeError) as exc:
        raise InvestigationError(str(exc)) from exc
    return InvestigationSettings(
        _text(raw["title"], "Investigation name", 200),
        _text(raw["problem"], "Research problem", 20000),
        _research_mode(raw["investigation_type"]),
        raw["ai_model"],
        raw["reasoning_effort"],
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
    investigation_change: InvestigationChange | None = None

    @property
    def project_change(self) -> InvestigationChange | None:
        """Read-only compatibility alias for historical event consumers."""
        return self.investigation_change


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


@dataclass(frozen=True)
class Investigation:
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

    @property
    def research_mode(self) -> ResearchMode:
        """Compatibility alias for existing integrations."""
        return self.investigation_type

    @property
    def project_id(self) -> str:
        """Compatibility alias; investigation identity has not changed."""
        return self.id


@dataclass(frozen=True)
class InvestigationView:
    path: str
    investigation: Investigation

    @property
    def project(self) -> Investigation:
        """Compatibility alias for Python integrations using the former object name."""
        return self.investigation


def investigation_payload(view: InvestigationView) -> dict[str, Any]:
    """Return canonical API/CLI data plus the explicitly retained legacy wrapper key."""
    payload = asdict(view)
    payload["project"] = payload["investigation"]
    return payload


ROOT = Path(__file__).resolve().parents[2]
SEED = ROOT / "investigations/rh.sigma"
STATE = "investigation.json"
LEGACY_STATE = "project.json"


def investigation_path(value: str | Path) -> Path:
    try:
        path = Path(value).expanduser().absolute()
        if path.is_symlink():
            raise InvestigationError("Investigation directory must not be a symbolic link")
        path = path.resolve()
        legacy_root = (ROOT / "projects").resolve()
        if not path.exists() and path.is_relative_to(legacy_root):
            migrated = (ROOT / "investigations" / path.relative_to(legacy_root)).resolve()
            if migrated.exists():
                path = migrated
        if path.suffix != ".sigma":
            raise InvestigationError("Investigation path must end in .sigma")
        return path
    except (OSError, ValueError, RuntimeError) as exc:
        raise InvestigationError(f"Invalid investigation path: {exc}") from exc


def _timestamp(value: Any) -> datetime:
    if not isinstance(value, str):
        raise InvestigationError("Timestamp must be a string")
    stamp = datetime.fromisoformat(value)
    if stamp.tzinfo is None:
        raise InvestigationError("Timestamps must include a timezone")
    return stamp


def _text(value: Any, name: str, limit: int) -> str:
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > limit:
        raise InvestigationError(f"{name} must contain 1–{limit} characters")
    return value.strip()


def _decode(raw: Any) -> Investigation:
    if (
        not isinstance(raw, dict)
        or type(raw.get("schema_version")) is not int
        or raw["schema_version"] not in (1, 2, 3, 4, 5, 6, 7)
    ):
        raise InvestigationError(
            "Unsupported or missing investigation schema_version (expected 1, 2, 3, 4, 5, 6 or 7)"
        )
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
    if set(raw) != fields:
        raise InvestigationError("Invalid investigation fields")
    for key in ("id", "title", "problem"):
        if not isinstance(raw[key], str) or not raw[key].strip():
            raise InvestigationError(f"Investigation {key} must be a nonempty string")
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
            }
        )
        if version >= 6
        else InvestigationSettings(raw["title"], raw["problem"], mode, legacy_model(), "high")
    )
    if version >= 6 and (raw["title"] != settings.title or raw["problem"] != settings.problem):
        raise InvestigationError("Investigation settings text must be canonical")
    strategies: list[Strategy] = []
    seen: set[str] = set()
    if version >= 2:
        if not isinstance(raw["strategies"], list):
            raise InvestigationError("Strategies must be a list")
        for item in raw["strategies"]:
            strategy_fields = {"id", "title", "approach", "author_kind", "created_at"}
            if version >= 3:
                strategy_fields.add("removed_at")
            if version >= 5:
                strategy_fields.update({"stage", "summary", "provenance"})
            if not isinstance(item, dict) or set(item) != strategy_fields:
                raise InvestigationError("Invalid strategy fields")
            if not isinstance(item["id"], str) or item["id"] in seen:
                raise InvestigationError("Strategy identities must be unique strings")
            UUID(item["id"])
            seen.add(item["id"])
            _text(item["title"], "Strategy title", 200)
            _text(item["approach"], "Hypothesis / approach", 10000)
            if item["author_kind"] != "human":
                raise InvestigationError("Only human-authored strategies are supported")
            _timestamp(item["created_at"])
            if item.get("removed_at") is not None:
                _timestamp(item["removed_at"])
            values = dict(item)
            if version >= 5:
                try:
                    values["stage"] = Stage(item["stage"])
                except (ValueError, TypeError) as exc:
                    raise InvestigationError("Invalid manual stage") from exc
                if (
                    not isinstance(item["summary"], str)
                    or len(item["summary"]) > 300
                    or "\n" in item["summary"]
                    or "\r" in item["summary"]
                ):
                    raise InvestigationError("Summary must be one line, at most 300 characters")
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
                        raise InvestigationError("Invalid generation provenance")
                    _text(provenance["model"], "Model", 100)
                    if (
                        provenance.get("reasoning_effort") is not None
                        and provenance["reasoning_effort"] not in EFFORTS
                    ):
                        raise InvestigationError("Invalid generation reasoning effort")
                    values["provenance"] = Provenance(**provenance)
            strategies.append(Strategy(**values))
    if not isinstance(raw["events"], list) or not raw["events"]:
        raise InvestigationError("Investigation requires an initialization event")
    created: set[str] = set()
    removed: set[str] = set()
    edits: dict[str, StrategyChange] = {}
    by_id = {strategy.id: strategy for strategy in strategies}
    events: list[Event] = []
    previous = None
    active_order: list[str] = []
    stages: dict[str, str] = {}
    investigation_change: InvestigationChange | None = None
    for index, item in enumerate(raw["events"], 1):
        if not isinstance(item, dict):
            raise InvestigationError("Invalid event")
        expected = {"sequence", "kind", "timestamp"}
        update_kinds = {"investigation.updated", "project.updated"}
        if index > 1 and item.get("kind") not in {"strategies.reordered", *update_kinds}:
            expected.add("strategy_id")
        if item.get("kind") == "strategies.reordered":
            expected.add("order")
        if item.get("kind") == "strategy.stage_changed":
            expected.add("stage_change")
        if item.get("kind") in update_kinds:
            expected.add(
                "project_change"
                if item.get("kind") == "project.updated"
                else "investigation_change"
            )
        if item.get("kind") == "strategy.updated":
            expected.add("change")
        if set(item) != expected:
            raise InvestigationError("Invalid event fields")
        if type(item["sequence"]) is not int or item["sequence"] != index:
            raise InvestigationError("Event sequence must be contiguous and ordered")
        stamp = _timestamp(item["timestamp"])
        if previous is not None and stamp < previous:
            raise InvestigationError("Event timestamps must be ordered")
        previous = stamp
        if index == 1:
            allowed_initialization = {
                "investigation.initialized",
                "project.initialized",
            }
            if item["kind"] not in allowed_initialization:
                raise InvestigationError("First event must initialize the investigation")
        elif item["kind"] == "strategy.created":
            if len(created) >= len(strategies):
                raise InvestigationError("Unexpected strategy creation event")
            strategy = strategies[len(created)]
            if (
                item["strategy_id"] != strategy.id
                or strategy.id in created
                or item["timestamp"] != strategy.created_at
            ):
                raise InvestigationError("Strategy creation event does not match its record")
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
                raise InvestigationError("Invalid strategy edit event")
            for field, limit in (
                ("previous_title", 200),
                ("title", 200),
                ("previous_approach", 10000),
                ("approach", 10000),
            ):
                _text(change[field], field, limit)
            previous_edit = edits.get(strategy_id)
            if previous_edit and (
                previous_edit.title != change["previous_title"]
                or previous_edit.approach != change["previous_approach"]
            ):
                raise InvestigationError("Strategy edit history is inconsistent")
            edits[strategy_id] = StrategyChange(**change)
        elif item["kind"] == "strategy.removed" and version >= 3:
            strategy_id = item["strategy_id"]
            if (
                not isinstance(strategy_id, str)
                or strategy_id not in created
                or strategy_id in removed
                or by_id[strategy_id].removed_at != item["timestamp"]
            ):
                raise InvestigationError("Strategy removal event does not match its record")
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
                raise InvestigationError("Invalid active strategy order event")
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
                raise InvestigationError("Invalid manual stage event")
            if (
                change["previous"] != stages[strategy_id]
                or change["stage"] not in {s.value for s in Stage}
                or change["stage"] == change["previous"]
            ):
                raise InvestigationError("Manual stage history is inconsistent")
            stages[strategy_id] = change["stage"]
        elif item["kind"] in update_kinds and version >= 6:
            change_key = (
                "project_change"
                if item.get("kind") == "project.updated"
                else "investigation_change"
            )
            change = item[change_key]
            if not isinstance(change, dict) or set(change) != {"previous", "current"}:
                raise InvestigationError("Invalid investigation edit event")
            next_change = InvestigationChange(
                _settings(change["previous"]), _settings(change["current"])
            )
            # Normalize legacy event keys before checking their canonical contents.
            normalized_change = {
                key: {
                    ("investigation_type" if field == "research_mode" else field): val
                    for field, val in value.items()
                }
                for key, value in change.items()
            }
            if asdict(next_change) != normalized_change:
                raise InvestigationError("Investigation change text must be canonical")
            if next_change.previous == next_change.current or (
                investigation_change and investigation_change.current != next_change.previous
            ):
                raise InvestigationError("Investigation settings edit chain is inconsistent")
            investigation_change = next_change
        else:
            raise InvestigationError("Unsupported strategy event")
        event_data = {
            ("investigation_change" if key == "project_change" else key): value
            for key, value in item.items()
            if key not in {"change", "stage_change", "order"}
        }
        event = Event(
            **{key: value for key, value in event_data.items() if key != "investigation_change"}
        )
        if "change" in item:
            event = replace(event, change=StrategyChange(**item["change"]))
        if "stage_change" in item:
            event = replace(event, stage_change=StageChange(**item["stage_change"]))
        if "order" in item:
            event = replace(event, order=tuple(item["order"]))
        if "investigation_change" in event_data:
            event = replace(event, investigation_change=investigation_change)
        events.append(event)
    if created != seen or removed != {s.id for s in strategies if s.removed_at is not None}:
        raise InvestigationError("Strategy records and history do not match")
    for strategy_id, change in edits.items():
        strategy = by_id[strategy_id]
        if strategy.title != change.title or strategy.approach != change.approach:
            raise InvestigationError("Latest edit does not match the strategy record")
    if version >= 5 and (
        raw["active_order"] != active_order or any(s.stage != stages[s.id] for s in strategies)
    ):
        raise InvestigationError("Strategy order/stages do not match history")
    if investigation_change and investigation_change.current != settings:
        raise InvestigationError("Latest investigation edit does not match settings")
    return Investigation(
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
    )


def _document(investigation: Investigation) -> bytes:
    raw = asdict(investigation)
    if investigation.schema_version < 6:
        del raw["ai_model"]
        del raw["reasoning_effort"]
        for strategy in raw["strategies"]:
            if strategy["provenance"] is not None:
                del strategy["provenance"]["reasoning_effort"]
    if investigation.schema_version < 5:
        del raw["active_order"]
        for strategy in raw["strategies"]:
            for key in ("stage", "summary", "provenance"):
                del strategy[key]
    if investigation.schema_version < 4:
        del raw["investigation_type"]
    if investigation.schema_version < 3:
        for strategy in raw["strategies"]:
            del strategy["removed_at"]
    for event in raw["events"]:
        if event.get("kind") == "project.updated" and event.get("investigation_change") is not None:
            event["project_change"] = event.pop("investigation_change")
        for key in ("stage_change", "order", "investigation_change"):
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


def _state_for_read(path: Path) -> Path:
    current = path / STATE
    legacy = path / LEGACY_STATE
    for candidate in (current, legacy):
        if (candidate.exists() or candidate.is_symlink()) and (
            candidate.is_symlink() or not candidate.is_file()
        ):
            raise InvestigationError(f"Investigation state {candidate.name} is not a regular file")
    if current.is_file() and legacy.is_file() and current.read_bytes() != legacy.read_bytes():
        raise InvestigationError(
            "Both investigation.json and legacy project.json exist with different contents; neither was changed"
        )
    if current.is_file():
        return current
    if legacy.is_file():
        return legacy
    raise InvestigationError(
        "Investigation has no regular investigation.json; initialize it explicitly"
    )


def _migrate_legacy_state(path: Path, expected: bytes) -> Path:
    """Publish the new filename without replacement; tolerate an interrupted hard-link migration."""
    current = path / STATE
    legacy = path / LEGACY_STATE
    if legacy.is_symlink() or not legacy.is_file():
        if current.is_file() and not current.is_symlink() and current.read_bytes() == expected:
            return current
        raise InvestigationError("Legacy project.json changed during investigation migration")
    if legacy.read_bytes() != expected:
        raise InvestigationError("Legacy project.json changed during investigation migration")
    if current.exists() or current.is_symlink():
        if current.is_symlink() or not current.is_file() or current.read_bytes() != expected:
            raise InvestigationError(
                "Both investigation.json and legacy project.json conflict; neither was changed"
            )
        legacy.unlink()
        return current
    os.link(legacy, current)
    legacy.unlink()
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    return current


def inspect_investigation(value: str | Path) -> InvestigationView:
    path = investigation_path(value)
    try:
        state = _state_for_read(path)
        investigation = _decode(json.loads(state.read_text(encoding="utf-8")))
        return InvestigationView(str(path), investigation)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        raise InvestigationError(f"Cannot open {path}: {exc}") from exc


def initialize_investigation(
    value: str | Path,
    title: str,
    problem: str,
    research_mode: str = "default",
    ai_model: str | None = None,
    reasoning_effort: str = "high",
) -> InvestigationView:
    mode = _research_mode(research_mode)
    resolved_model = legacy_model() if ai_model is None else ai_model
    try:
        validate_pair(resolved_model, reasoning_effort)
    except ValueError as exc:
        raise InvestigationError(str(exc)) from exc
    path = investigation_path(value)
    if not title.strip() or not problem.strip():
        raise InvestigationError("Title and problem must be nonempty")
    created = False
    temporary: str | None = None
    try:
        if not path.exists():
            path.mkdir()  # Parent must exist; do not create unrelated directories.
            created = True
        if not path.is_dir():
            raise InvestigationError("Investigation path is not a directory")
        if any(p.name != ".gitkeep" for p in path.iterdir()):
            raise InvestigationError(
                "Initialization requires an empty directory (or .gitkeep only)"
            )
        investigation = Investigation(
            7,
            str(uuid4()),
            title.strip(),
            problem.strip(),
            (Event(1, "investigation.initialized", datetime.now(UTC).isoformat()),),
            investigation_type=mode,
            ai_model=resolved_model,
            reasoning_effort=reasoning_effort,
        )
        # Stage and fsync before atomic, no-replace publication. Concurrent initializers
        # cannot overwrite one another; the final link fails if investigation.json exists.
        fd, temporary = tempfile.mkstemp(prefix=".sigma-init-", dir=path)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(_document(investigation).decode("utf-8"))
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, path / STATE)
        return InvestigationView(str(path), investigation)
    except OSError as exc:
        raise InvestigationError(f"Cannot initialize {path}: {exc}") from exc
    finally:
        if temporary is not None:
            Path(temporary).unlink(missing_ok=True)
        if created:
            try:
                path.rmdir()  # Only remove an empty directory owned by this attempt.
            except OSError:
                pass


def _open_investigation(value: str | Path) -> InvestigationView:
    path = investigation_path(value)
    # Only the checked-in RH seed has implicit initialization. Unknown/corrupt
    # directories always require an explicit init command and are never repaired.
    if (
        path == SEED
        and path.is_dir()
        and not (path / STATE).exists()
        and not (path / LEGACY_STATE).exists()
    ):
        try:
            return initialize_investigation(
                path,
                "Riemann Hypothesis",
                (
                    "Investigate approaches to the Riemann Hypothesis. "
                    "Evidence and finite experiments are not proofs."
                ),
            )
        except InvestigationError:
            if (path / STATE).is_file():
                return inspect_investigation(path)
            raise
    return inspect_investigation(path)


def open_investigation(value: str | Path) -> InvestigationView:
    view = _open_investigation(value)
    from sigma.recents import record_access

    record_access(view)
    return view


def list_events(value: str | Path) -> tuple[Event, ...]:
    return inspect_investigation(value).investigation.events


def close_investigation() -> None:
    """Release the caller's view; services retain no handles or global session."""


def list_strategies(value: str | Path) -> tuple[Strategy, ...]:
    """List the active pool; inspect retains removed records and their history."""
    investigation = inspect_investigation(value).investigation
    by_id = {s.id: s for s in investigation.strategies}
    return tuple(by_id[i] for i in investigation.active_order)


def create_strategy(
    value: str | Path,
    title: str,
    approach: str,
    summary: str = "",
    provenance: Provenance | None = None,
) -> InvestigationView:
    """Append a human strategy and event together; migrate legacy investigations on write."""
    title = _text(title, "Strategy title", 200)
    approach = _text(approach, "Hypothesis / approach", 10000)

    if not isinstance(summary, str) or len(summary) > 300 or "\n" in summary or "\r" in summary:
        raise InvestigationError("Summary must be one line, at most 300 characters")

    def append(investigation: Investigation) -> Investigation:
        timestamp = _next_timestamp(investigation)
        strategy = Strategy(
            str(uuid4()),
            title,
            approach,
            "human",
            timestamp,
            summary=summary.strip(),
            provenance=provenance,
        )
        return replace(
            investigation,
            schema_version=max(
                investigation.schema_version,
                6
                if provenance and provenance.reasoning_effort
                else 5
                if summary or provenance
                else 2,
            ),
            active_order=(*investigation.active_order, strategy.id),
            strategies=(*investigation.strategies, strategy),
            events=(
                *investigation.events,
                Event(len(investigation.events) + 1, "strategy.created", timestamp, strategy.id),
            ),
        )

    return _update_investigation(value, append)


def remove_strategy(value: str | Path, strategy_id: str) -> InvestigationView:
    """Remove from the active pool, retaining research and an explicit audit event."""

    def remove(investigation: Investigation) -> Investigation:
        strategy = next((s for s in investigation.strategies if s.id == strategy_id), None)
        if strategy is None:
            raise InvestigationError("Strategy not found in this investigation")
        if strategy.removed_at is not None:
            raise InvestigationError("Strategy has already been removed")
        timestamp = _next_timestamp(investigation)
        return replace(
            investigation,
            schema_version=max(3, investigation.schema_version),
            active_order=tuple(i for i in investigation.active_order if i != strategy_id),
            strategies=tuple(
                replace(s, removed_at=timestamp) if s.id == strategy_id else s
                for s in investigation.strategies
            ),
            events=(
                *investigation.events,
                Event(len(investigation.events) + 1, "strategy.removed", timestamp, strategy_id),
            ),
        )

    return _update_investigation(value, remove)


def edit_strategy(
    value: str | Path,
    strategy_id: str,
    title: str,
    approach: str,
    text_format: str | None = None,
    expected_digest: str | None = None,
) -> InvestigationView:
    """Update name/description while preserving identity and earlier text in history."""
    title = _text(title, "Strategy name", 200)
    approach = _text(approach, "Strategy description", 10000)

    def edit(investigation: Investigation) -> Investigation:
        strategy = next((s for s in investigation.strategies if s.id == strategy_id), None)
        if strategy is None:
            raise InvestigationError("Strategy not found in this investigation")
        if strategy.removed_at is not None:
            raise InvestigationError("Removed strategies cannot be edited")
        if (
            expected_digest is not None
            and hashlib.sha256(strategy.approach.encode()).hexdigest() != expected_digest
        ):
            raise InvestigationError(
                "Strategy description changed elsewhere. Reopen it before saving"
            )
        if (title, approach) == (strategy.title, strategy.approach):
            return investigation
        change = StrategyChange(strategy.title, strategy.approach, title, approach)
        return replace(
            investigation,
            schema_version=max(3, investigation.schema_version),
            strategies=tuple(
                replace(
                    s,
                    title=title,
                    approach=approach,
                    summary="" if approach != s.approach else s.summary,
                )
                if s.id == strategy_id
                else s
                for s in investigation.strategies
            ),
            events=(
                *investigation.events,
                Event(
                    len(investigation.events) + 1,
                    "strategy.updated",
                    _next_timestamp(investigation),
                    strategy_id,
                    change,
                ),
            ),
        )

    return _update_investigation(
        value, edit, (f"strategy:{strategy_id}", text_format) if text_format else None
    )


def _next_timestamp(investigation: Investigation) -> str:
    return (
        max(datetime.now(UTC), _timestamp(investigation.events[-1].timestamp))
        .astimezone(UTC)
        .isoformat()
    )


def _update_investigation(
    value: str | Path,
    update: Callable[[Investigation], Investigation],
    text_edit: tuple[str, str] | None = None,
) -> InvestigationView:
    view = inspect_investigation(value)
    path = Path(view.path)
    temporary: Path | None = None
    backup_temporary: Path | None = None
    try:
        # Lock a stable inode, separate from the atomically replaced document.
        fd = os.open(path / ".write.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "rb") as lock:
            if not stat.S_ISREG(os.fstat(lock.fileno()).st_mode):
                raise InvestigationError("Investigation write lock must be a regular file")
            fcntl.flock(lock, fcntl.LOCK_EX)
            source_state = _state_for_read(path)
            before = source_state.read_bytes()
            investigation = _decode(json.loads(before))
            updated = update(investigation)
            if updated == investigation:
                return InvestigationView(str(path), investigation)
            updated = replace(updated, schema_version=max(7, updated.schema_version))
            from sigma.text_views import sync_source_changes

            sync_source_changes(path, investigation, updated, text_edit)
            target_state = _migrate_legacy_state(path, before)
            contents = _document(updated)
            _decode(json.loads(contents))  # Validate the complete next document before publication.
            temporary = _stage(path, contents)
            if investigation.schema_version != updated.schema_version:
                backup = path / f"investigation.v{investigation.schema_version}.json"
                backup_temporary = _stage(path, before)
                try:
                    os.link(backup_temporary, backup)
                except FileExistsError:
                    if backup.is_symlink() or backup.read_bytes() != before:
                        raise InvestigationError(
                            "Version backup already exists with different contents"
                        )
            if target_state.is_symlink() or target_state.read_bytes() != before:
                raise InvestigationError("Investigation changed during save; reopen and retry")
            os.replace(temporary, target_state)
            return InvestigationView(str(path), updated)
    except OSError as exc:
        raise InvestigationError(f"Cannot save strategy change: {exc}") from exc
    finally:
        for staged in (temporary, backup_temporary):
            if staged is not None:
                staged.unlink(missing_ok=True)


@dataclass(frozen=True)
class InvestigationDestination:
    root: str
    path: str | None
    exists: bool


def investigations_root() -> Path:
    """Explicit server-side location, independent of the browser or current directory."""
    try:
        configured_value = os.environ.get("SIGMA_INVESTIGATIONS_ROOT")
        if configured_value is None:
            # Keep the former setting as an explicit compatibility alias.
            configured_value = os.environ.get("SIGMA_PROJECTS_ROOT", str(ROOT / "investigations"))
        configured = Path(configured_value).expanduser()
        if not configured.is_absolute() or configured.is_symlink():
            raise InvestigationError(
                "SIGMA_INVESTIGATIONS_ROOT must be an absolute directory, not a symlink"
            )
        root = configured.resolve()
        if not root.is_dir() or root.stat().st_uid != os.geteuid():
            raise InvestigationError(
                "Investigations root must already exist and be owned by the server user"
            )
        return root
    except (OSError, ValueError, RuntimeError) as exc:
        raise InvestigationError(f"Investigations location unavailable: {exc}") from exc


def _uses_checkout_root() -> bool:
    return not os.environ.get("SIGMA_INVESTIGATIONS_ROOT") and not os.environ.get(
        "SIGMA_PROJECTS_ROOT"
    )


def _investigation_name(title: str) -> tuple[str, str]:
    title = _text(title, "Investigation name", 200)
    if any(char in "/\\" or ord(char) < 32 or ord(char) == 127 for char in title):
        raise InvestigationError(
            "Investigation name cannot contain path separators or control characters"
        )
    slug = re.sub(r"[^\w]+", "-", unicodedata.normalize("NFKC", title).casefold()).strip("-_")[:80]
    while len(slug.encode("utf-8")) > 180:
        slug = slug[:-1]
    slug = slug.rstrip("-_")
    if not slug or not any(char.isalnum() for char in slug):
        raise InvestigationError("Investigation name must contain a letter or number")
    return title, slug + ".sigma"


def investigation_destination(title: str = "") -> InvestigationDestination:
    root = investigations_root()
    if not title:
        return InvestigationDestination(str(root), None, False)
    _, name = _investigation_name(title)
    path = root / name
    legacy = ROOT / "projects" / name
    legacy_exists = _uses_checkout_root() and os.path.lexists(legacy)
    exists = os.path.lexists(path) or legacy_exists
    destination = legacy if legacy_exists else path
    return InvestigationDestination(str(root), str(destination), exists)


def create_investigation(
    title: str,
    problem: str,
    research_mode: str = "default",
    ai_model: str | None = None,
    reasoning_effort: str = "high",
) -> InvestigationView:
    """Reserve a name beneath the configured root; never reuse an existing directory."""
    title, name = _investigation_name(title)
    problem = _text(problem, "Research problem", 20000)
    mode = _research_mode(research_mode)
    root = investigations_root()
    destination = root / name
    legacy_destination = ROOT / "projects" / name
    if _uses_checkout_root() and os.path.lexists(legacy_destination):
        raise InvestigationError(
            f"An existing legacy project occupies {legacy_destination}; open or move it before creating another investigation"
        )
    reserved = False
    try:
        destination.mkdir(mode=0o700)  # Exclusive reservation also rejects files/broken symlinks.
        reserved = True
        view = initialize_investigation(
            destination, title, problem, mode, ai_model, reasoning_effort
        )
        from sigma.recents import record_access

        record_access(view)
        return view
    except FileExistsError as exc:
        raise InvestigationError(
            f"An investigation or file already exists at {destination}; choose another name"
        ) from exc
    except OSError as exc:
        raise InvestigationError(f"Cannot create investigation: {exc}") from exc
    finally:
        if reserved:
            try:
                destination.rmdir()  # Remove only this attempt's still-empty directory on failure.
            except OSError:
                pass


def change_stage(value: str | Path, strategy_id: str, stage: str) -> InvestigationView:
    try:
        chosen = Stage(stage)
    except (ValueError, TypeError) as exc:
        raise InvestigationError(
            "Stage must be draft, ready, exploring or hold (manually tracked)"
        ) from exc

    def update(investigation: Investigation) -> Investigation:
        strategy = next(
            (s for s in investigation.strategies if s.id == strategy_id and not s.removed_at), None
        )
        if strategy is None:
            raise InvestigationError("Active strategy not found")
        if strategy.stage == chosen:
            return investigation
        return replace(
            investigation,
            schema_version=max(5, investigation.schema_version),
            strategies=tuple(
                replace(s, stage=chosen) if s.id == strategy_id else s
                for s in investigation.strategies
            ),
            events=(
                *investigation.events,
                Event(
                    len(investigation.events) + 1,
                    "strategy.stage_changed",
                    _next_timestamp(investigation),
                    strategy_id,
                    stage_change=StageChange(strategy.stage, chosen),
                ),
            ),
        )

    return _update_investigation(value, update)


def reorder_strategies(
    value: str | Path, order: list[str], expected_order: list[str]
) -> InvestigationView:
    def update(investigation: Investigation) -> Investigation:
        if (
            not isinstance(order, list)
            or any(not isinstance(i, str) for i in order)
            or len(order) != len(investigation.active_order)
            or set(order) != set(investigation.active_order)
        ):
            raise InvestigationError("Order must contain every active strategy exactly once")
        if expected_order != list(investigation.active_order):
            raise InvestigationError(
                "Strategy order changed elsewhere; reopen the investigation and retry"
            )
        if order == list(investigation.active_order):
            return investigation
        return replace(
            investigation,
            schema_version=max(5, investigation.schema_version),
            active_order=tuple(order),
            events=(
                *investigation.events,
                Event(
                    len(investigation.events) + 1,
                    "strategies.reordered",
                    _next_timestamp(investigation),
                    order=tuple(order),
                ),
            ),
        )

    return _update_investigation(value, update)


def investigation_settings(investigation: Investigation) -> InvestigationSettings:
    return InvestigationSettings(
        investigation.title,
        investigation.problem,
        investigation.investigation_type,
        investigation.ai_model,
        investigation.reasoning_effort,
    )


def update_investigation(
    value: str | Path,
    title: str,
    problem: str,
    research_mode: str,
    ai_model: str,
    reasoning_effort: str,
    expected: dict[str, Any],
    text_format: str | None = None,
) -> InvestigationView:
    wanted = _settings(
        {
            "title": title,
            "problem": problem,
            "investigation_type": research_mode,
            "ai_model": ai_model,
            "reasoning_effort": reasoning_effort,
        }
    )
    prior = _settings(expected)

    def update(investigation: Investigation) -> Investigation:
        current = investigation_settings(investigation)
        if current != prior:
            raise InvestigationError(
                "Investigation settings changed elsewhere. Refresh/reopen before editing again; your changes have not been saved"
            )
        if current == wanted:
            return investigation
        if (wanted.ai_model, wanted.reasoning_effort) != (
            current.ai_model,
            current.reasoning_effort,
        ):
            try:
                validate_pair(wanted.ai_model, wanted.reasoning_effort)
            except ValueError as exc:
                raise InvestigationError(str(exc)) from exc
        return replace(
            investigation,
            schema_version=max(6, investigation.schema_version),
            title=wanted.title,
            problem=wanted.problem,
            investigation_type=wanted.investigation_type,
            ai_model=wanted.ai_model,
            reasoning_effort=wanted.reasoning_effort,
            events=(
                *investigation.events,
                Event(
                    len(investigation.events) + 1,
                    "investigation.updated",
                    _next_timestamp(investigation),
                    investigation_change=InvestigationChange(current, wanted),
                ),
            ),
        )

    return _update_investigation(
        value, update, ("investigation", text_format) if text_format else None
    )
