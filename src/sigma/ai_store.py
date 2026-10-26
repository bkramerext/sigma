"""Owner-only, atomic application credentials. Never stored in a research project."""

import asyncio
import fcntl
import json
import os
import stat
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from uuid import uuid4

from sigma.projects import ROOT, ProjectError
from sigma.ui_instance import private_directory


def directory() -> Path:
    from sigma import cloud_workspaces

    if cloud_workspaces.enabled():
        # Hosted sponsor storage is explicit and never uses the local operator's store.
        override = os.environ.get("SIGMA_CLOUD_CHATGPT_AUTH_HOME", "")
        if not override:
            raise ProjectError("Hosted ChatGPT sponsor storage is not configured.")
    else:
        override = os.environ.get("SIGMA_AUTH_HOME")
    if override:
        path = Path(override)
        if (
            not path.is_absolute()
            or path.resolve().is_relative_to(ROOT)
            or any(part.endswith(".sigma") for part in path.resolve().parts)
        ):
            raise ProjectError(
                "SIGMA_AUTH_HOME must be an absolute private directory outside projects."
            )
        # The explicit override's parent must exist; never create an unexpected tree.
    else:
        parent = Path.home().resolve() / ".config"
        if not parent.exists():
            parent.mkdir(mode=0o700)
        info = parent.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid():
            raise ProjectError("Unsafe SIGMA configuration parent directory.")
        path = parent / "sigma"
    try:
        private_directory(path)
    except (OSError, RuntimeError):
        raise ProjectError(
            "Cannot open private SIGMA account storage. Check directory ownership/0700 permissions."
        ) from None
    return path


def read(path: Path) -> dict[str, Any]:
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except FileNotFoundError:
        return {
            "version": 1,
            "ext_agent_host_id": "urn:uuid:" + str(uuid4()),
            "mode": "chatgpt",
            "active": None,
            "accounts": {},
            "welcome_seen": False,
        }
    with os.fdopen(descriptor, encoding="utf-8") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise ValueError()
        raw = stream.read(1000001)
        if len(raw) > 1000000:
            raise ValueError()
        value = json.loads(raw)
    if (
        value.get("version") != 1
        or value.get("mode") not in {"chatgpt", "api_key"}
        or not isinstance(value.get("accounts"), dict)
        or not isinstance(value.get("ext_agent_host_id"), str)
        or not value["ext_agent_host_id"].startswith("urn:uuid:")
    ):
        raise ValueError()
    return value


def write(path: Path, value: dict[str, Any]) -> None:
    encoded = json.dumps(value).encode("utf-8")
    if len(encoded) > 1000000:
        raise ProjectError("Account storage limit reached; existing credentials were retained.")
    fd, temporary = tempfile.mkstemp(prefix=".credentials-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(encoded.decode("utf-8"))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        Path(temporary).unlink(missing_ok=True)


@asynccontextmanager
async def transaction():
    """Cross-process serialization also covers rotating-token network exchanges."""
    fd = None
    try:
        path = directory()
        fd = os.open(path / "credentials.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise ValueError()
        async with asyncio.timeout(30):
            while True:
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    await asyncio.sleep(0.05)
        state_path = path / "credentials.json"
        value = read(state_path)
        # Persist a newly allocated host ID even before first authorization.
        if not state_path.exists():
            write(state_path, value)
        previous = json.dumps(value, sort_keys=True)
        yield value
        if json.dumps(value, sort_keys=True) != previous:
            write(state_path, value)
    except (OSError, ValueError, TypeError, KeyError, TimeoutError):
        raise ProjectError(
            "Cannot safely read/write SIGMA account storage. Check owned 0700 directory/0600 files; existing credentials were not printed."
        ) from None
    finally:
        if fd is not None:
            os.close(fd)
