"""Discover shipped projects and open each as one persistent managed project."""

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

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

EXAMPLES = ROOT / "examples"


@dataclass(frozen=True)
class StockProject:
    id: str
    title: str
    problem: str
    research_mode: str
    strategy_count: int


def _projects() -> list[tuple[str, Path]]:
    if not EXAMPLES.is_dir() or EXAMPLES.is_symlink():
        raise ProjectError("Stock Projects catalog is unavailable.")
    return [
        (directory.name, directory / STATE)
        for directory in sorted(
            EXAMPLES.iterdir(), key=lambda path: (path.name == "jesus-cannabis", path.name)
        )
        if directory.is_dir() and not directory.is_symlink() and (directory / STATE).is_file()
    ]


def _load(identifier: str) -> tuple[bytes, dict[str, Any], StockProject]:
    match = next(((name, path) for name, path in _projects() if name == identifier), None)
    if match is None or match[1].is_symlink():
        raise ProjectError("Stock project was not found.")
    try:
        contents = match[1].read_bytes()
        raw = json.loads(contents)
        project = _decode(raw)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        raise ProjectError(f"Stock project {identifier} is unavailable: {exc}") from exc
    return (
        contents,
        raw,
        StockProject(
            identifier,
            project.title,
            project.problem,
            project.research_mode.value,
            len(project.active_order),
        ),
    )


def _destination(identifier: str) -> Path:
    root = projects_root()
    if root.is_relative_to(EXAMPLES):
        raise ProjectError("Stock projects cannot be installed inside the source catalog.")
    return root / f"{identifier}.sigma"


def stock_projects() -> dict[str, list[dict[str, Any]]]:
    listed = []
    for name, _ in _projects():
        _, raw, stock = _load(name)
        destination = _destination(name)
        if destination.exists() or destination.is_symlink():
            try:
                view = inspect_project(destination)
                if view.project.id == raw["id"]:
                    stock = StockProject(
                        name,
                        view.project.title,
                        view.project.problem,
                        view.project.research_mode.value,
                        len(view.project.active_order),
                    )
            except ProjectError:
                pass  # Opening the row reports a precise conflict; other rows remain usable.
        listed.append(asdict(stock))
    return {"projects": listed}


def stock_project_ids() -> set[str]:
    return {_load(name)[1]["id"] for name, _ in _projects()}


def open_stock_project(identifier: str) -> ProjectView:
    """Install once with the canonical identity; subsequent opens preserve user edits."""
    contents, raw, _ = _load(identifier)
    destination = _destination(identifier)
    reserved = False
    staged: Path | None = None
    try:
        try:
            destination.mkdir(mode=0o700)
            reserved = True
        except FileExistsError:
            pass
        if reserved:
            staged = _stage(destination, contents)
            os.link(staged, destination / STATE)
        view = inspect_project(destination)
        if view.project.id != raw["id"]:
            raise ProjectError(
                f"A different project occupies {destination}; existing research was not changed."
            )
        return view
    except OSError as exc:
        raise ProjectError(f"Cannot open stock project: {exc}") from exc
    finally:
        if staged is not None:
            staged.unlink(missing_ok=True)
        if reserved:
            try:
                destination.rmdir()
            except OSError:
                pass
