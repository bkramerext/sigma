"""Private local control endpoint and serialized checkout instance replacement."""

import errno
import fcntl
import hashlib
import json
import os
import socket
import stat
import time
from pathlib import Path
from types import TracebackType
from typing import Self

from sigma.projects import ROOT

STATE_ROOT = Path("/tmp")


def identity(root: Path) -> str:
    resolved = root.resolve(strict=True)
    info = resolved.stat()
    return hashlib.sha256(f"{resolved}:{info.st_dev}:{info.st_ino}".encode()).hexdigest()


def private_directory(path: Path) -> None:
    try:
        path.mkdir(mode=0o700)
    except FileExistsError:
        pass
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise RuntimeError(
            "Unsafe SIGMA instance directory; expected an owned private 0700 directory."
        )


class Instance:
    def __init__(self, root: Path = ROOT):
        self.identity = identity(root)
        # Short Unix socket path, independently private for each OS account and checkout.
        base = STATE_ROOT / f"sigma-ui-{os.getuid()}"
        private_directory(base)
        self.directory = base / self.identity[:24]
        private_directory(self.directory)
        self.path = self.directory / "control.sock"
        self.lock: int | None = None
        self.listener: socket.socket | None = None

    def __enter__(self) -> Self:
        self.lock = os.open(
            self.directory / "launch.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600
        )
        info = os.fstat(self.lock)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
            os.close(self.lock)
            self.lock = None
            raise RuntimeError("Unsafe SIGMA launch lock; refusing startup.")
        try:
            deadline = time.monotonic() + 45
            while True:
                try:
                    fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    if time.monotonic() >= deadline:
                        raise RuntimeError(
                            "Another SIGMA launch is still starting or stopping; retry shortly."
                        ) from None
                    time.sleep(0.1)
            self.replace()
            self.listener = socket.socket(socket.AF_UNIX)
            self.listener.bind(str(self.path))
            self.listener.listen(8)
            self.listener.settimeout(0.1)
            return self
        except BaseException:
            self.__exit__(None, None, None)
            raise

    def replace(self) -> None:
        try:
            info = self.path.lstat()
        except FileNotFoundError:
            return
        if not stat.S_ISSOCK(info.st_mode) or info.st_uid != os.getuid():
            raise RuntimeError("Unverifiable SIGMA control record; refusing takeover.")
        with socket.socket(socket.AF_UNIX) as client:
            client.settimeout(15)
            try:
                client.connect(str(self.path))
            except OSError as exc:
                if exc.errno not in (errno.ECONNREFUSED, errno.ENOENT):
                    raise RuntimeError(
                        "Cannot verify previous SIGMA instance; refusing takeover."
                    ) from None
            else:
                client.sendall(
                    json.dumps({"identity": self.identity, "command": "identify"}).encode() + b"\n"
                )
                if self.receive(client) != {"identity": self.identity, "status": "owned"}:
                    raise RuntimeError("Previous instance identity mismatch; refusing takeover.")
                print("Restarting existing SIGMA instance…", flush=True)
                client.sendall(
                    json.dumps({"identity": self.identity, "command": "shutdown"}).encode() + b"\n"
                )
                if self.receive(client) != {"identity": self.identity, "status": "stopped"}:
                    raise RuntimeError(
                        "Previous SIGMA instance did not confirm cleanup; retry startup."
                    )
        # Only while holding the launch lock, after confirmed cleanup or refused socket.
        self.path.unlink(missing_ok=True)

    @staticmethod
    def receive(client: socket.socket) -> dict[str, str]:
        data = bytearray()
        while len(data) < 1024:
            chunk = client.recv(1)
            if not chunk:
                raise RuntimeError(
                    "SIGMA control connection closed before confirmation; retry startup."
                )
            if chunk == b"\n":
                try:
                    value = json.loads(data)
                except (ValueError, UnicodeError):
                    break
                if isinstance(value, dict):
                    return value
                break
            data.extend(chunk)
        raise RuntimeError("Invalid SIGMA control response; refusing takeover.")

    def replacement_request(self) -> socket.socket | None:
        assert self.listener is not None
        try:
            client, _ = self.listener.accept()
        except TimeoutError:
            return None
        client.settimeout(1)
        try:
            if self.receive(client) != {"identity": self.identity, "command": "identify"}:
                client.close()
                return None
            client.sendall(
                json.dumps({"identity": self.identity, "status": "owned"}).encode() + b"\n"
            )
            if self.receive(client) == {"identity": self.identity, "command": "shutdown"}:
                return client
        except (OSError, RuntimeError):
            pass
        client.close()
        return None

    def unlock(self) -> None:
        if self.lock is not None:
            os.close(self.lock)
            self.lock = None

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if self.listener is not None:
            self.listener.close()
            self.path.unlink(missing_ok=True)
            self.listener = None
        self.unlock()
