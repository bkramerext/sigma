"""Initialize an empty shared Personal vault as the unprivileged worker UID.

Never inspect, import or migrate the experimental per-user Docker stores.
"""
from __future__ import annotations

import os
import stat
from pathlib import Path

UID = 10001


def main() -> None:
    if os.geteuid() != UID:
        raise SystemExit("Vault initialization must run as the credential worker")
    for path in (
        Path("/var/lib/sigma-shared/records"),
        Path("/var/lib/sigma-shared/workspaces"),
        Path("/var/lib/sigma-shared-key"),
    ):
        info = path.lstat()
        if (
            not stat.S_ISDIR(info.st_mode)
            or info.st_uid != UID
            or stat.S_IMODE(info.st_mode) != 0o700
        ):
            raise SystemExit("Private Personal vault directory is unsafe")
    key_path = Path("/var/lib/sigma-shared-key/master")
    try:
        fd = os.open(key_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    except FileExistsError:
        fd = -1
    if fd >= 0:
        with os.fdopen(fd, "wb") as stream:
            stream.write(os.urandom(32))
            stream.flush()
            os.fsync(stream.fileno())
        # A credential record without its durable encryption key is
        # unrecoverable. fsync the directory entry before the worker starts.
        parent_fd = os.open(key_path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(parent_fd)
        finally:
            os.close(parent_fd)
    fd = os.open(key_path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(stream.fileno())
        key = stream.read(33)
    if (
        not stat.S_ISREG(info.st_mode)
        or info.st_uid != UID
        or stat.S_IMODE(info.st_mode) != 0o600
        or len(key) != 32
    ):
        raise SystemExit("Private Personal encryption key is unsafe")


if __name__ == "__main__":
    main()
