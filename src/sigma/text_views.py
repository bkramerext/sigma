"""Portable, lazy Plain/Markdown representations alongside project.json.

The project document remains the authority for the current body. A locked,
versioned companion stores format identity and prior/derived bodies. Companion
metadata is written before an authored project edit, so a crash cannot label
an old project body as a new source; unused future metadata is harmless.
"""

import fcntl
import hashlib
import json
import os
import re
import stat
import threading
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from sigma.projects import (
    MAX_STRATEGY_APPROACH,
    Project,
    ProjectError,
    ProjectView,
    _stage,
    edit_strategy,
    inspect_project,
    project_settings,
    update_project,
)

Format = Literal["plain", "markdown"]
STATE = "text-representations.json"
_gate = threading.Lock()


def digest(body: str) -> str:
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _format(value: str) -> Format:
    if value not in {"plain", "markdown"}:
        raise ProjectError("Text format must be plain or markdown")
    return value  # type: ignore[return-value]


def _body(project: Project, key: str) -> str:
    if key == "project":
        return project.problem
    if not key.startswith("strategy:"):
        raise ProjectError("Text scope must be a project or strategy")
    strategy = next((item for item in project.strategies if item.id == key[9:]), None)
    if strategy is None:
        raise ProjectError("Strategy not found in this project")
    return strategy.approach


def _empty(project: Project) -> dict[str, Any]:
    return {"schema_version": 1, "project_id": project.id, "entries": {}}


def _load(path: Path, project: Project) -> dict[str, Any]:
    if path.suffix == ".json":
        member = "artifacts/" + STATE
        try:
            from sigma.project_bundle import read_file

            contents = read_file(path, member)
        except (OSError, ValueError) as exc:
            try:
                bundle = json.loads(path.read_text(encoding="utf-8"))
                if (
                    isinstance(bundle, dict)
                    and isinstance(bundle.get("files"), dict)
                    and member not in bundle["files"]
                ):
                    return _empty(project)
            except (OSError, ValueError):
                pass
            raise ProjectError("Text representations are corrupt") from exc
        try:
            raw = json.loads(contents)
        except (ValueError, UnicodeDecodeError) as exc:
            raise ProjectError("Text representations are corrupt") from exc
    else:
        state = path / STATE
        if not state.exists() and not state.is_symlink():
            return _empty(project)
        if state.is_symlink() or not state.is_file():
            raise ProjectError("Text representations must be a regular file")
        try:
            raw = json.loads(state.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ProjectError("Text representations are corrupt") from exc
    if (
        not isinstance(raw, dict)
        or set(raw) != {"schema_version", "project_id", "entries"}
        or type(raw["schema_version"]) is not int
        or raw["schema_version"] != 1
        or raw["project_id"] != project.id
        or not isinstance(raw["entries"], dict)
    ):
        raise ProjectError("Text representations do not match this project")
    for key, entry in raw["entries"].items():
        if not isinstance(key, str) or (key != "project" and not key.startswith("strategy:")):
            raise ProjectError("Invalid text representation scope")
        if not isinstance(entry, dict) or set(entry) != {"sources", "versions"}:
            raise ProjectError("Invalid text representation entry")
        if not isinstance(entry["sources"], list) or not isinstance(entry["versions"], dict):
            raise ProjectError("Invalid text representation history")
        if set(entry["versions"]) != {"plain", "markdown"}:
            raise ProjectError("Invalid text representation formats")
        for source in entry["sources"]:
            if (
                not isinstance(source, dict)
                or set(source) != {"digest", "format", "timestamp"}
                or not isinstance(source["digest"], str)
                or not re.fullmatch(r"[0-9a-f]{64}", source["digest"])
            ):
                raise ProjectError("Invalid source revision")
            _format(source["format"])
            try:
                datetime.fromisoformat(source["timestamp"])
            except (ValueError, TypeError) as exc:
                raise ProjectError("Invalid source timestamp") from exc
        for versions in entry["versions"].values():
            if not isinstance(versions, list):
                raise ProjectError("Invalid text versions")
            for version in versions:
                if not isinstance(version, dict) or set(version) != {
                    "body",
                    "kind",
                    "source_digest",
                    "source_format",
                    "created_at",
                    "provenance",
                    "warnings",
                }:
                    raise ProjectError("Invalid text version")
                limit = 20000 if key == "project" else MAX_STRATEGY_APPROACH
                if (
                    not isinstance(version["body"], str)
                    or not version["body"].strip()
                    or len(version["body"]) > limit
                ):
                    raise ProjectError("Invalid text body")
                if version["kind"] not in {"authored", "ai_derived"} or version[
                    "source_format"
                ] not in {"plain", "markdown"}:
                    raise ProjectError("Invalid text origin")
                if not isinstance(version["source_digest"], str) or not re.fullmatch(
                    r"[0-9a-f]{64}", version["source_digest"]
                ):
                    raise ProjectError("Invalid text source digest")
                try:
                    datetime.fromisoformat(version["created_at"])
                except (ValueError, TypeError) as exc:
                    raise ProjectError("Invalid text version timestamp") from exc
                if not isinstance(version["warnings"], list) or any(
                    not isinstance(note, str) or len(note) > 300 for note in version["warnings"]
                ):
                    raise ProjectError("Invalid text conversion notes")
                attribution = version["provenance"]
                if version["kind"] == "ai_derived":
                    if (
                        not isinstance(attribution, dict)
                        or set(attribution) != {"provider", "model", "reasoning_effort"}
                        or attribution["provider"] != "openai"
                        or not isinstance(attribution["model"], str)
                        or not attribution["model"]
                        or not isinstance(attribution["reasoning_effort"], str)
                        or not attribution["reasoning_effort"]
                    ):
                        raise ProjectError("Invalid conversion attribution")
                elif attribution is not None:
                    raise ProjectError("Authored text cannot claim AI conversion")
    return raw


def _save(path: Path, project: Project, raw: dict[str, Any]) -> None:
    contents = (json.dumps(raw, ensure_ascii=False, indent=2) + "\n").encode()
    if path.suffix == ".json":
        from sigma.projects import save_project_artifacts

        save_project_artifacts(path, {"artifacts/" + STATE: contents})
        return
    staged = _stage(path, contents)
    try:
        state = path / STATE
        if state.is_symlink():
            raise ProjectError("Text representations must not be a symlink")
        os.replace(staged, state)
    finally:
        staged.unlink(missing_ok=True)


def _entry(raw: dict[str, Any], key: str) -> dict[str, Any]:
    return raw["entries"].setdefault(
        key, {"sources": [], "versions": {"plain": [], "markdown": []}}
    )


def _source_format(entry: dict[str, Any] | None, body: str) -> Format:
    if entry:
        for item in reversed(entry["sources"]):
            if item["digest"] == digest(body):
                return _format(item["format"])
        if entry["sources"]:
            raise ProjectError(
                "Text source changed outside a representation-aware save; reopen and choose its format"
            )
    return "plain"


def _authored(body: str, fmt: Format, timestamp: str) -> dict[str, Any]:
    return {
        "body": body,
        "kind": "authored",
        "source_digest": digest(body),
        "source_format": fmt,
        "created_at": timestamp,
        "provenance": None,
        "warnings": [],
    }


def _record_source(entry: dict[str, Any], old: str, new: str, fmt: Format) -> None:
    old_format = _source_format(entry, old)
    stamp = datetime.now(UTC).isoformat()
    if not entry["sources"]:
        entry["sources"].append({"digest": digest(old), "format": old_format, "timestamp": stamp})
    if not entry["versions"][old_format] or entry["versions"][old_format][-1]["body"] != old:
        entry["versions"][old_format].append(_authored(old, old_format, stamp))
    entry["sources"].append({"digest": digest(new), "format": fmt, "timestamp": stamp})
    entry["versions"][fmt].append(_authored(new, fmt, stamp))


def sync_source_changes(
    path: Path, before: Project, after: Project, text_edit: tuple[str, str] | None
) -> None:
    """Called with the stable project write lock, before publishing an edit."""
    state = path / STATE
    if not state.exists() and text_edit is None:
        return
    raw = _load(path, before)
    keys = ["project", *(f"strategy:{item.id}" for item in before.strategies)]
    changed = False
    for key in keys:
        old = _body(before, key)
        new = _body(after, key)
        selected = _format(text_edit[1]) if text_edit and text_edit[0] == key else None
        if old == new and selected is None:
            continue
        entry = _entry(raw, key)
        fmt = selected or _source_format(entry, old)
        if old != new or fmt != _source_format(entry, old):
            _record_source(entry, old, new, fmt)
            changed = True
    if changed:
        _save(path, before, raw)


def inspect_text(value: str | Path, scope: str, strategy_id: str | None = None) -> dict[str, Any]:
    view = inspect_project(value)
    key = (
        "project"
        if scope == "project"
        else f"strategy:{strategy_id}"
        if scope == "strategy" and strategy_id
        else ""
    )
    source = _body(view.project, key)
    entry = _load(Path(view.path), view.project)["entries"].get(key)
    source_format = _source_format(entry, source)
    source_digest = digest(source)
    formats: dict[str, Any] = {}
    for fmt in ("plain", "markdown"):
        if fmt == source_format:
            versions = entry["versions"][fmt] if entry else []
            stored = next(
                (
                    item
                    for item in reversed(versions)
                    if item["body"] == source and item["kind"] == "authored"
                ),
                None,
            )
            formats[fmt] = {
                **(stored or _authored(source, source_format, view.project.events[-1].timestamp)),
                "current": True,
            }
        else:
            versions = entry["versions"][fmt] if entry else []
            current = next(
                (
                    item
                    for item in reversed(versions)
                    if item["kind"] == "ai_derived"
                    and item["source_digest"] == source_digest
                    and item["source_format"] == source_format
                ),
                None,
            )
            chosen = current or (versions[-1] if versions else None)
            formats[fmt] = {**chosen, "current": bool(current)} if chosen else None
    return {
        "scope": scope,
        "strategy_id": strategy_id,
        "source_format": source_format,
        "source_digest": source_digest,
        "plain": formats["plain"],
        "markdown": formats["markdown"],
    }


def save_source(
    value: str | Path,
    scope: str,
    body: str,
    fmt: str,
    expected_digest: str,
    strategy_id: str | None = None,
) -> ProjectView:
    fmt = _format(fmt)
    view = inspect_project(value)
    key = (
        "project"
        if scope == "project"
        else f"strategy:{strategy_id}"
        if scope == "strategy" and strategy_id
        else ""
    )
    current = _body(view.project, key)
    if digest(current) != expected_digest:
        raise ProjectError("Text changed elsewhere. Reopen it before saving")
    if scope == "project":
        settings = project_settings(view.project)
        return update_project(
            value,
            settings.title,
            body,
            getattr(settings.research_mode, "value", settings.research_mode),
            settings.ai_model,
            settings.reasoning_effort,
            asdict(settings),
            fmt,
        )
    strategy = next(item for item in view.project.strategies if item.id == strategy_id)
    return edit_strategy(value, strategy.id, strategy.title, body, fmt, expected_digest)


def _lock(path: Path):
    lock_path = (
        path.with_name("." + path.name + ".text-representations.lock")
        if path.suffix == ".json"
        else path / ".write.lock"
    )
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    lock = os.fdopen(fd, "rb")
    if not stat.S_ISREG(os.fstat(lock.fileno()).st_mode):
        lock.close()
        raise ProjectError("Project write lock must be a regular file")
    fcntl.flock(lock, fcntl.LOCK_EX)
    return lock


def store_conversion(
    value: str | Path,
    scope: str,
    strategy_id: str | None,
    target: Format,
    expected_digest: str,
    expected_format: Format,
    body: str,
    provenance: dict[str, str | None],
    warnings: list[str],
) -> dict[str, Any]:
    view = inspect_project(value)
    path = Path(view.path)
    with _lock(path):
        current = inspect_text(path, scope, strategy_id)
        if (
            current["source_digest"] != expected_digest
            or current["source_format"] != expected_format
        ):
            raise ProjectError(
                "Source changed during conversion. Previous text was kept; retry from the current source"
            )
        latest_project = inspect_project(path).project
        if latest_project.id != view.project.id or (
            latest_project.ai_model,
            latest_project.reasoning_effort,
        ) != (provenance["model"], provenance["reasoning_effort"]):
            raise ProjectError(
                "Project model/Thinking changed during conversion; nothing was saved"
            )
        if current[target] and current[target]["current"]:
            return current
        raw = _load(path, latest_project)
        key = "project" if scope == "project" else f"strategy:{strategy_id}"
        entry = _entry(raw, key)
        if not entry["sources"]:
            entry["sources"].append(
                {
                    "digest": expected_digest,
                    "format": expected_format,
                    "timestamp": datetime.now(UTC).isoformat(),
                }
            )
        entry["versions"][target].append(
            {
                "body": body,
                "kind": "ai_derived",
                "source_digest": expected_digest,
                "source_format": expected_format,
                "created_at": datetime.now(UTC).isoformat(),
                "provenance": provenance,
                "warnings": warnings,
            }
        )
        _save(path, latest_project, raw)
    return inspect_text(path, scope, strategy_id)
