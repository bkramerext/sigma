"""Discover shipped stock projects and copy them into independent user projects."""

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
    investigation_type: str
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


def _load(identifier: str) -> tuple[dict[str, Any], StockProject]:
    match = next(((name, path) for name, path in _projects() if name == identifier), None)
    if match is None or match[1].is_symlink():
        raise ProjectError("Stock project was not found.")
    try:
        raw = json.loads(match[1].read_bytes())
        project = _decode(raw)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        raise ProjectError(f"Stock project {identifier} is unavailable: {exc}") from exc
    return (
        raw,
        StockProject(
            identifier,
            project.title,
            project.problem,
            project.investigation_type.value,
            len(project.active_order),
        ),
    )


def stock_projects() -> dict[str, list[dict[str, Any]]]:
    """The Stock list always describes the untouched templates, not user copies."""
    return {"projects": [asdict(_load(name)[1]) for name, _ in _projects()]}


def stock_project_ids() -> set[str]:
    return {_load(name)[0]["id"] for name, _ in _projects()}


def open_stock_project(identifier: str) -> ProjectView:
    """Create a fresh, independently identified copy and add it to Recent Projects.

    Never reopen or modify a prior copy, including copies created by older releases
    with the stock template's original identity.
    """
    raw, _ = _load(identifier)
    root = projects_root()
    if root.is_relative_to(EXAMPLES):
        raise ProjectError("Stock projects cannot be installed inside the source catalog.")

    # A stock template may be opened repeatedly. Allocate a new directory with
    # exclusive mkdir, so neither existing research nor a concurrent open is replaced.
    destination: Path | None = None
    for number in range(1, 10001):
        suffix = "" if number == 1 else f"-{number}"
        candidate = root / f"{identifier}{suffix}.sigma"
        try:
            candidate.mkdir(mode=0o700)
            destination = candidate
            break
        except FileExistsError:
            continue
        except OSError as exc:
            raise ProjectError(f"Cannot create stock project copy: {exc}") from exc
    if destination is None:
        raise ProjectError("Too many copies of this stock project.")

    staged: Path | None = None
    try:
        copied = {**raw, "id": str(uuid4())}
        # The project document contains its strategies and event history.
        # Retain those contents, changing only the enclosing project's identity.
        _decode(copied)
        staged = _stage(destination, (json.dumps(copied, indent=2) + "\n").encode("utf-8"))
        os.link(staged, destination / STATE)
        view = inspect_project(destination)
    except OSError as exc:
        raise ProjectError(f"Cannot open stock project copy: {exc}") from exc
    finally:
        if staged is not None:
            staged.unlink(missing_ok=True)
        try:
            destination.rmdir()  # Only removes the directory if publication failed.
        except OSError:
            pass

    from sigma.recents import record_access

    record_access(view)
    return view
