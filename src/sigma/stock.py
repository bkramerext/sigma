"""Discover shipped investigations and open each as one persistent managed investigation."""

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from sigma.investigations import (
    ROOT,
    STATE,
    InvestigationError,
    InvestigationView,
    _decode,
    _stage,
    _uses_checkout_root,
    inspect_investigation,
    investigations_root,
)

EXAMPLES = ROOT / "examples"


@dataclass(frozen=True)
class StockInvestigation:
    id: str
    title: str
    problem: str
    investigation_type: str
    strategy_count: int


def _investigations() -> list[tuple[str, Path]]:
    if not EXAMPLES.is_dir() or EXAMPLES.is_symlink():
        raise InvestigationError("Stock Investigations catalog is unavailable.")
    return [
        (directory.name, directory / STATE)
        for directory in sorted(
            EXAMPLES.iterdir(), key=lambda path: (path.name == "jesus-cannabis", path.name)
        )
        if directory.is_dir() and not directory.is_symlink() and (directory / STATE).is_file()
    ]


def _load(identifier: str) -> tuple[bytes, dict[str, Any], StockInvestigation]:
    match = next(((name, path) for name, path in _investigations() if name == identifier), None)
    if match is None or match[1].is_symlink():
        raise InvestigationError("Stock investigation was not found.")
    try:
        contents = match[1].read_bytes()
        raw = json.loads(contents)
        investigation = _decode(raw)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        raise InvestigationError(f"Stock investigation {identifier} is unavailable: {exc}") from exc
    return (
        contents,
        raw,
        StockInvestigation(
            identifier,
            investigation.title,
            investigation.problem,
            investigation.investigation_type.value,
            len(investigation.active_order),
        ),
    )


def _destination(identifier: str) -> Path:
    root = investigations_root()
    if root.is_relative_to(EXAMPLES):
        raise InvestigationError(
            "Stock investigations cannot be installed inside the source catalog."
        )
    legacy = ROOT / "projects" / f"{identifier}.sigma"
    if _uses_checkout_root() and os.path.lexists(legacy):
        return legacy
    return root / f"{identifier}.sigma"


def stock_investigations() -> dict[str, list[dict[str, Any]]]:
    listed = []
    for name, _ in _investigations():
        _, raw, stock = _load(name)
        destination = _destination(name)
        if destination.exists() or destination.is_symlink():
            try:
                view = inspect_investigation(destination)
                if view.investigation.id == raw["id"]:
                    stock = StockInvestigation(
                        name,
                        view.investigation.title,
                        view.investigation.problem,
                        view.investigation.investigation_type.value,
                        len(view.investigation.active_order),
                    )
            except InvestigationError:
                pass  # Opening the row reports a precise conflict; other rows remain usable.
        listed.append(asdict(stock))
    # Keep the former response key during the API transition.
    return {"investigations": listed, "projects": listed}


def stock_investigation_ids() -> set[str]:
    return {_load(name)[1]["id"] for name, _ in _investigations()}


def open_stock_investigation(identifier: str) -> InvestigationView:
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
        view = inspect_investigation(destination)
        if view.investigation.id != raw["id"]:
            raise InvestigationError(
                f"A different investigation occupies {destination}; existing research was not changed."
            )
        return view
    except OSError as exc:
        raise InvestigationError(f"Cannot open stock investigation: {exc}") from exc
    finally:
        if staged is not None:
            staged.unlink(missing_ok=True)
        if reserved:
            try:
                destination.rmdir()
            except OSError:
                pass
