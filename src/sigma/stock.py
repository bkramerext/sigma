"""Read-only catalog of shipped investigations and explicit working copies."""

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from sigma.projects import (
    ROOT,
    STATE,
    ProjectError,
    ProjectView,
    _decode,
    _project_name,
    _stage,
    projects_root,
)

EXAMPLES = ROOT / "examples"


@dataclass(frozen=True)
class StockProject:
    id: str
    title: str
    problem: str
    research_mode: str
    strategy_count: int


def _templates() -> list[tuple[str, Path]]:
    if not EXAMPLES.is_dir() or EXAMPLES.is_symlink():
        raise ProjectError("Stock Projects catalog is unavailable.")
    return [
        (directory.name, directory / STATE)
        for directory in sorted(
            EXAMPLES.iterdir(), key=lambda path: (path.name == "jesus-cannabis", path.name)
        )
        if directory.is_dir() and not directory.is_symlink() and (directory / STATE).is_file()
    ]


def _load(identifier: str) -> tuple[dict[str, Any], StockProject]:
    match = next(((name, path) for name, path in _templates() if name == identifier), None)
    if match is None or match[1].is_symlink():
        raise ProjectError("Stock project was not found.")
    try:
        raw = json.loads(match[1].read_text(encoding="utf-8"))
        project = _decode(raw)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        raise ProjectError(f"Stock project {identifier} is unavailable: {exc}") from exc
    return raw, StockProject(
        identifier,
        project.title,
        project.problem,
        project.research_mode.value,
        len(project.active_order),
    )


def stock_projects() -> dict[str, list[dict[str, Any]]]:
    return {"projects": [asdict(_load(name)[1]) for name, _ in _templates()]}


def stock_project_ids() -> set[str]:
    return {_load(name)[0]["id"] for name, _ in _templates()}


def create_stock_copy(identifier: str, title: str) -> ProjectView:
    """Publish a new identity under the configured project root, never over a source."""
    raw, stock = _load(identifier)
    title, name = _project_name(title)
    root = projects_root()
    if root.is_relative_to(EXAMPLES):
        raise ProjectError("Working copies cannot be created inside the stock examples directory.")
    destination = root / name
    identities = {raw["id"]: str(uuid4())}
    identities.update({item["id"]: str(uuid4()) for item in raw["strategies"]})

    def replace_ids(value: Any) -> Any:
        if isinstance(value, str):
            return identities.get(value, value)
        if isinstance(value, list):
            return [replace_ids(item) for item in value]
        if isinstance(value, dict):
            return {key: replace_ids(item) for key, item in value.items()}
        return value

    copied = replace_ids(raw)
    copied["title"] = title
    project = _decode(copied)
    if project.id == raw["id"] or project.title != title or project.problem != stock.problem:
        raise ProjectError("Stock copy validation failed.")
    contents = (json.dumps(copied, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    reserved = False
    staged: Path | None = None
    try:
        destination.mkdir(mode=0o700)
        reserved = True
        staged = _stage(destination, contents)
        os.link(staged, destination / STATE)
        view = ProjectView(str(destination), project)
        from sigma.recents import record_access

        record_access(view)
        return view
    except FileExistsError as exc:
        raise ProjectError(
            f"A project or file already exists at {destination}; choose another name"
        ) from exc
    except OSError as exc:
        raise ProjectError(f"Cannot create stock working copy: {exc}") from exc
    finally:
        if staged is not None:
            staged.unlink(missing_ok=True)
        if reserved:
            try:
                destination.rmdir()
            except OSError:
                pass
