"""Six-entry application access index for investigations the user opened or created."""

import fcntl
import json
import os
import stat
import sys
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from sigma.investigations import (
    ROOT,
    InvestigationError,
    InvestigationView,
    _stage,
    inspect_investigation,
)
from sigma.ui_instance import private_directory


def state_directory() -> Path:
    configured = os.environ.get("SIGMA_STATE_DIR")
    if configured:
        path = Path(configured).expanduser()
        if (
            not path.is_absolute()
            or path.resolve().is_relative_to(ROOT)
            or any(part.endswith(".sigma") for part in path.resolve().parts)
        ):
            raise InvestigationError(
                "SIGMA_STATE_DIR must be absolute and outside the checkout/investigation packages."
            )
    else:
        base = Path(os.environ.get("XDG_STATE_HOME", str(Path.home().resolve() / ".local/state")))
        if not base.is_absolute():
            raise InvestigationError("XDG_STATE_HOME must be absolute.")
        # Create missing application-state parents; refuse symlinks and foreign owners.
        for parent in reversed((base, *base.parents)):
            if parent == Path(parent.anchor):
                continue
            if not parent.exists():
                parent.mkdir(mode=0o700)
            info = parent.lstat()
            if not stat.S_ISDIR(info.st_mode) or (parent == base and info.st_uid != os.getuid()):
                raise InvestigationError("Unsafe application state parent.")
        path = base / "sigma"
    if path.resolve().is_relative_to(ROOT) or any(
        part.endswith(".sigma") for part in path.resolve().parts
    ):
        raise InvestigationError(
            "Application state must remain outside the checkout/investigation packages."
        )
    try:
        private_directory(path)
    except (OSError, RuntimeError):
        raise InvestigationError(
            "Recent Investigations needs an owned private 0700 state directory."
        ) from None
    return path


def _validate(value: Any) -> dict:
    if (
        not isinstance(value, dict)
        or set(value) != {"version", "entries", "bootstrapped_roots"}
        or value["version"] != 1
    ):
        raise ValueError()
    if (
        not isinstance(value["entries"], list)
        or len(value["entries"]) > 6
        or not isinstance(value["bootstrapped_roots"], dict)
    ):
        raise ValueError()
    seen = set()
    for item in value["entries"]:
        if not isinstance(item, dict) or set(item) != {
            "id",
            "path",
            "accessed_at",
            "included_example",
        }:
            raise ValueError()
        if not isinstance(item["id"], str):
            raise TypeError()
        UUID(item["id"])
        if (
            item["id"] in seen
            or not isinstance(item["path"], str)
            or not Path(item["path"]).is_absolute()
            or type(item["included_example"]) is not bool
        ):
            raise ValueError()
        seen.add(item["id"])
        if item["accessed_at"] is not None:
            if (
                datetime.fromisoformat(item["accessed_at"]).tzinfo is None
                or item["included_example"]
            ):
                raise ValueError()
        elif not item["included_example"]:
            raise ValueError()
    if any(
        not isinstance(key, str) or not Path(key).is_absolute() or not isinstance(message, str)
        for key, message in value["bootstrapped_roots"].items()
    ):
        raise ValueError()
    return value


@contextmanager
def _index():
    descriptor = None
    try:
        directory = state_directory()
        descriptor = os.open(
            directory / "recents.lock",
            os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK,
            0o600,
        )
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise ValueError()
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        path = directory / "recents.json"
        try:
            read_fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        except FileNotFoundError:
            value = {"version": 1, "entries": [], "bootstrapped_roots": {}}
        else:
            with os.fdopen(read_fd, encoding="utf-8") as stream:
                info = os.fstat(stream.fileno())
                if (
                    not stat.S_ISREG(info.st_mode)
                    or info.st_uid != os.getuid()
                    or info.st_mode & 0o077
                ):
                    raise ValueError()
                raw = stream.read(1000001)
                if len(raw) > 1000000:
                    raise ValueError()
                value = _validate(json.loads(raw))
        original = json.dumps(value, sort_keys=True)
        # Older releases inserted canonical stock examples in Recents. Keep
        # their directories but show only independent user work here.
        from sigma.stock import stock_investigation_ids

        try:
            stock_ids = stock_investigation_ids()
        except (InvestigationError, OSError, ValueError, TypeError, KeyError):
            stock_ids = set()
        value["entries"] = [
            entry
            for entry in value["entries"]
            if not entry["included_example"] and entry["id"] not in stock_ids
        ]
        yield value
        _validate(value)
        encoded = json.dumps(value, indent=2).encode()
        if len(encoded) > 1000000:
            raise ValueError()
        if json.dumps(value, sort_keys=True) != original:
            staged = _stage(directory, encoded)
            try:
                os.replace(staged, path)
                parent_fd = os.open(directory, os.O_RDONLY)
                try:
                    os.fsync(parent_fd)
                finally:
                    os.close(parent_fd)
            finally:
                staged.unlink(missing_ok=True)
    except (OSError, ValueError, TypeError, KeyError):
        raise InvestigationError(
            "Recent Investigations index is unavailable. Check its owned 0700 directory/0600 files; research was not altered."
        ) from None
    finally:
        if descriptor is not None:
            os.close(descriptor)


def record_access(view: InvestigationView) -> None:
    """A secondary index failure must not turn a successful research write into a retry."""
    from sigma.stock import stock_investigation_ids

    try:
        if view.investigation.id in stock_investigation_ids():
            return
    except (InvestigationError, OSError, ValueError, TypeError, KeyError):
        pass
    try:
        with _index() as index:
            index["entries"] = [
                {
                    "id": str(UUID(view.investigation.id)),
                    "path": view.path,
                    "accessed_at": datetime.now(UTC).isoformat(),
                    "included_example": False,
                },
                *(
                    entry
                    for entry in index["entries"]
                    if entry["id"] != str(UUID(view.investigation.id))
                ),
            ][:6]
    except InvestigationError:
        print(
            "Recent Investigations could not be updated. The investigation operation succeeded; check application state permissions.",
            file=sys.stderr,
        )


def forget_recent(investigation_id: str) -> None:
    with _index() as index:
        index["entries"] = [entry for entry in index["entries"] if entry["id"] != investigation_id]


@dataclass(frozen=True)
class RecentInvestigation:
    id: str
    path: str
    title: str
    investigation_type: str | None
    strategy_count: int | None
    accessed_at: str | None
    included_example: bool
    available: bool
    error: str | None = None


def recent_investigations() -> dict:
    with _index() as index:
        entries = [dict(entry) for entry in index["entries"]]
    recent = []
    for entry in entries:
        try:
            view = inspect_investigation(entry["path"])
            if str(UUID(view.investigation.id)) != entry["id"]:
                raise InvestigationError("Investigation identity changed")
            recent.append(
                asdict(
                    RecentInvestigation(
                        **entry,
                        title=view.investigation.title,
                        investigation_type=view.investigation.investigation_type,
                        strategy_count=len(view.investigation.active_order),
                        available=True,
                    )
                )
            )
        except (InvestigationError, OSError):
            recent.append(
                asdict(
                    RecentInvestigation(
                        **entry,
                        title=Path(entry["path"]).name,
                        investigation_type=None,
                        strategy_count=None,
                        available=False,
                        error="Unavailable or changed identity. Use Open Investigation to locate it, or forget this entry.",
                    )
                )
            )
    # Keep the former response key during the API transition.
    return {"investigations": recent, "projects": recent}


def home_investigations() -> dict:
    return recent_investigations()
