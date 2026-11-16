"""Local --prod Personal browser diagnostics (redacted by construction).

No provider URL, header, token, workspace ID, email, request body, Docker
stderr or filesystem path is ever recorded as an event field. Events contain
only allowlisted stage/status identifiers, durations and HTTP status codes.
A private, bounded per-launch log is available to the local signed-in SIGMA
member through the connection dialog. Production never enables this channel.
"""

from __future__ import annotations

import os
import re
import secrets
import stat
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterator

_ATTEMPT: ContextVar[str] = ContextVar("sigma_personal_diagnostic_attempt", default="-")
_SAFE = re.compile(r"[a-zA-Z0-9_.:-]{1,64}\Z")
_REQUEST = re.compile(r"[0-9a-f]{12,32}\Z")
_PREFIX = "SIGMA_PERSONAL_DIAG"
_MAX_LOG_BYTES = 2 * 1024 * 1024


def attempt(value: str | None) -> str:
    return value if isinstance(value, str) and _REQUEST.fullmatch(value) else secrets.token_hex(6)


@contextmanager
def attempt_scope(value: str) -> Iterator[None]:
    token = _ATTEMPT.set(attempt(value))
    try:
        yield
    finally:
        _ATTEMPT.reset(token)


def current_attempt() -> str:
    return _ATTEMPT.get()


def _field(value: object) -> str:
    raw = str(value)
    return raw if _SAFE.fullmatch(raw) else "redacted"


def _log_path() -> Path | None:
    raw = os.environ.get("SIGMA_PERSONAL_DIAGNOSTICS_FILE", "")
    if not raw:
        return None
    path = Path(raw)
    allowed = Path.home() / ".sigma" / "personal-shared-poc" / "diagnostics"
    if path.parent != allowed or not path.name.startswith("personal-") or path.suffix != ".log":
        return None
    return path


def _fd(path: Path, flags: int) -> int:
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags | nofollow)
    details = os.fstat(descriptor)
    if (
        not stat.S_ISREG(details.st_mode)
        or details.st_uid != os.geteuid()
        or stat.S_IMODE(details.st_mode) != 0o600
    ):
        os.close(descriptor)
        raise OSError("Unsafe Personal diagnostic log")
    return descriptor


def emit(stage: str, event: str, **fields: object) -> None:
    """Emit a restricted one-line diagnostic, including across child processes."""
    if not os.environ.get("SIGMA_PERSONAL_DIAGNOSTICS_FILE"):
        return
    line = (
        f"{_PREFIX} utc={datetime.now(UTC).strftime('%Y-%m-%dT%H:%M:%S.%fZ')}"
        f" pid={os.getpid()} attempt={_field(current_attempt())}"
        f" stage={_field(stage)} event={_field(event)}"
    )
    for name, value in sorted(fields.items()):
        if _SAFE.fullmatch(name):
            line += f" {name}={_field(value)}"
    print(line, flush=True)
    path = _log_path()
    if path is None:
        return
    try:
        descriptor = _fd(path, os.O_WRONLY | os.O_APPEND)
        try:
            if os.fstat(descriptor).st_size < _MAX_LOG_BYTES:
                os.write(descriptor, (line + "\n").encode("ascii"))
        finally:
            os.close(descriptor)
    except OSError:
        # Observability must not block SIGMA startup or model requests.
        print(f"{_PREFIX} event=log_write_failed", flush=True)


def create_capture(root: Path) -> Path:
    """Create a new private file; keep recent evidence without retaining secrets."""
    folder = root / "diagnostics"
    folder.mkdir(mode=0o700, exist_ok=True)
    info = folder.lstat()
    if (
        not stat.S_ISDIR(info.st_mode)
        or folder.is_symlink()
        or info.st_uid != os.geteuid()
        or stat.S_IMODE(info.st_mode) != 0o700
    ):
        raise OSError("Unsafe Personal diagnostic directory")
    filename = (
        "personal-" + datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        + "-" + secrets.token_hex(4) + ".log"
    )
    target = folder / filename
    descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.close(descriptor)
    # At most eight historical logs, all created here with mode 0600.
    previous = sorted(folder.glob("personal-*.log"), key=lambda f: f.name)
    for old in previous[:-8]:
        try:
            stat_info = old.lstat()
            if stat.S_ISREG(stat_info.st_mode) and stat_info.st_uid == os.geteuid():
                old.unlink()
        except OSError:
            pass
    return target


def report() -> str:
    """Return a bounded credential-free excerpt for the Copy diagnostics action."""
    path = _log_path()
    if path is None:
        return "Personal diagnostics not active in this SIGMA process."
    try:
        descriptor = _fd(path, os.O_RDONLY)
        try:
            size = os.fstat(descriptor).st_size
            os.lseek(descriptor, max(0, size - 96 * 1024), os.SEEK_SET)
            data = os.read(descriptor, 96 * 1024)
        finally:
            os.close(descriptor)
    except OSError:
        return "Personal diagnostic log is unavailable; see SIGMA terminal."
    lines = data.decode("ascii", errors="replace").splitlines()
    # Reject any unexpected injected data before returning it to the browser.
    safe = [line for line in lines if line.startswith(_PREFIX + " ") and len(line) < 1024]
    return (
        "SIGMA local Personal ChatGPT diagnostics (no credentials)\n"
        + "log=" + path.name + "\n"
        + "\n".join(safe[-500:])
    )
