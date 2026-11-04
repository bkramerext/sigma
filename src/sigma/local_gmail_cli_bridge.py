"""Private one-time handoff for Gmail CLI when a local SIGMA UI already owns port 5173.

The callback only relays an OAuth *code* to the CLI that initiated the flow.
Token exchange, account verification, and grant saving remain CLI-owned.
This file is not used for hosted SIGMA.
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from tempfile import NamedTemporaryFile

MAX_AGE_SECONDS = 300


def _path(home: Path, state: str) -> Path | None:
    if not (20 <= len(state) <= 256) or not state.isascii():
        return None
    digest = hashlib.sha256(state.encode("ascii")).hexdigest()
    return home / f".gmail-cli-flow-{digest}.json"


def _private_home(home: Path) -> bool:
    try:
        info = home.lstat()
    except OSError:
        return False
    return (
        stat.S_ISDIR(info.st_mode)
        and info.st_uid == os.getuid()
        and not (stat.S_IMODE(info.st_mode) & 0o077)
    )


def _read(home: Path, state: str) -> dict[str, object] | None:
    path = _path(home, state)
    if path is None or not _private_home(home):
        return None
    try:
        info = path.lstat()
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.getuid()
            or stat.S_IMODE(info.st_mode) & 0o077
            or info.st_size > 16_384
        ):
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    created = data.get("created")
    if (
        not isinstance(created, (int, float))
        or isinstance(created, bool)
        or created > time.time() + 5
        or time.time() - created > MAX_AGE_SECONDS
        or data.get("state_hash") != hashlib.sha256(state.encode("ascii")).hexdigest()
    ):
        return None
    return data


@contextmanager
def pending_flow(home: Path, state: str) -> Iterator[None]:
    """Register the CLI's unpredictable state in a private, exclusive file."""
    path = _path(home, state)
    if path is None or not _private_home(home):
        raise ValueError("Local auth storage must be private and owned by this user.")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(
                {
                    "created": time.time(),
                    "state_hash": hashlib.sha256(state.encode("ascii")).hexdigest(),
                    "status": "pending",
                },
                stream,
            )
            stream.flush()
            os.fsync(stream.fileno())
        yield
    finally:
        path.unlink(missing_ok=True)


def ready(home: Path, state: str) -> bool:
    flow = _read(home, state)
    return flow is not None and flow.get("status") == "pending"


def receive(home: Path, state: str, *, code: str, error: str) -> bool:
    """Claim a pending flow without disclosing its code in browser output."""
    old = _read(home, state)
    path = _path(home, state)
    if path is None or old is None or old.get("status") != "pending":
        return False
    if not code and not error:
        return False
    if len(code) > 8192:
        return False
    data = {
        "created": old["created"],
        "state_hash": old["state_hash"],
        "status": "complete",
        "code": code if not error else "",
        "error": bool(error),
    }
    temporary: Path | None = None
    try:
        with NamedTemporaryFile(
            "w", encoding="utf-8", prefix=".gmail-cli-reply-", dir=home, delete=False
        ) as stream:
            temporary = Path(stream.name)
            os.fchmod(stream.fileno(), 0o600)
            json.dump(data, stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        temporary = None
        return True
    except OSError:
        return False
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def result(home: Path, state: str) -> tuple[str, bool] | None:
    flow = _read(home, state)
    if flow is None or flow.get("status") != "complete":
        return None
    code = flow.get("code")
    if not isinstance(code, str):
        return None
    return code, flow.get("error") is True
