"""Read a configured secret from the process environment or a mounted file."""

from __future__ import annotations

import os
import stat
from contextlib import closing
from pathlib import Path


class SecretConfigurationError(ValueError):
    """A secret has conflicting, unsafe, or unreadable configuration."""


def secret_value(name: str, *, max_bytes: int = 16_384) -> str | None:
    """Return one secret source; never fall back when file configuration is bad."""
    value = os.environ.get(name, "").strip()
    file_name = os.environ.get(f"{name}_FILE", "").strip()
    if value and file_name:
        raise SecretConfigurationError(f"{name} and {name}_FILE cannot both be configured")
    if not file_name:
        return value or None

    path = Path(file_name)
    if not path.is_absolute():
        raise SecretConfigurationError(f"{name}_FILE must be an absolute path")
    try:
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode):
            raise SecretConfigurationError(f"{name}_FILE must name a regular file")
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        with closing(os.fdopen(descriptor, "rb")) as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                raise SecretConfigurationError(f"{name}_FILE must name a regular file")
            raw = stream.read(max_bytes + 1)
    except OSError as exc:
        raise SecretConfigurationError(f"{name}_FILE could not be read") from exc
    if len(raw) > max_bytes:
        raise SecretConfigurationError(f"{name}_FILE is too large")
    try:
        secret = raw.decode("utf-8").strip()
    except UnicodeDecodeError as exc:
        raise SecretConfigurationError(f"{name}_FILE is not UTF-8 text") from exc
    return secret or None
