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
    _occupied_titles,
    _stage,
    _title_key,
    _title_registry_lock,
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
    """Create an independent copy named 'Title (copy)', then '(copy 1)', etc."""
    raw, _ = _load(identifier)
    root = projects_root()
    if root.is_relative_to(EXAMPLES):
        raise ProjectError("Stock projects cannot be installed inside the source catalog.")

    with _title_registry_lock(root):
        occupied = _occupied_titles(root)
        copied_title = ""
        for number in range(10000):
            suffix = " (copy)" if number == 0 else f" (copy {number})"
            title = raw["title"][: 200 - len(suffix)].rstrip() + suffix
            if _title_key(title) not in occupied:
                copied_title = title
                break
        if not copied_title:
            raise ProjectError("Too many copies of this stock project.")

        # Display-name suffixes are independent of directory numbering. A
        # previous release may have installed a stock project at sample.sigma.
        destination: Path | None = None
        for number in range(1, 10001):
            directory_suffix = "" if number == 1 else f"-{number}"
            candidate = root / f"{identifier}{directory_suffix}.sigma"
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
            copied = {**raw, "id": str(uuid4()), "title": copied_title}
            # Keep the strategies and their history, but give this project
            # its own identity and a distinct display name.
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
                destination.rmdir()  # Only removes an unpublished, empty directory.
            except OSError:
                pass

    from sigma.recents import record_access

    record_access(view)
    return view
