"""Private, bounded, token-free sponsor diagnostics for the local checkout."""

import fcntl
import logging
import os
import re
import stat
from datetime import UTC, datetime

from sigma.projects import ROOT

_LOG = logging.getLogger("sigma.sponsor")
_FIELD = re.compile(r"[a-z0-9_]{1,64}\Z")
_MAX_BYTES = 64 * 1024
LOG_NAME = "sponsor-diagnostics.log"


def record(event: str, status: str) -> None:
    """Log fixed status codes to the terminal and an owned 0600 checkout file."""
    if not _FIELD.fullmatch(event) or not _FIELD.fullmatch(status):
        raise ValueError("Sponsor diagnostic fields must be bounded status codes.")
    _LOG.warning("%s status=%s", event, status)
    from sigma import cloud_auth

    if not cloud_auth.config().local:
        return
    line = f"{datetime.now(UTC).isoformat(timespec='seconds')} {event} status={status}\n".encode()
    try:
        descriptor = os.open(
            ROOT / LOG_NAME,
            os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW,
            0o600,
        )
        try:
            info = os.fstat(descriptor)
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
                raise OSError("Unsafe sponsor diagnostic log")
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            if os.fstat(descriptor).st_size + len(line) > _MAX_BYTES:
                os.ftruncate(descriptor, 0)
            os.write(descriptor, line)
        finally:
            os.close(descriptor)
    except OSError:
        # Diagnostics must never block research or weaken credential handling.
        _LOG.warning("sponsor_diagnostics status=file_unavailable")
