"""Private local control endpoint and serialized checkout instance replacement."""

import errno
import fcntl
import hashlib
import json
import os
import signal
import socket
import subprocess
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
    def __init__(self, root: Path = ROOT, shutdown_only: bool = False):
        self.root = root.resolve(strict=True)
        self.shutdown_only = shutdown_only
        self.registered = False
        self.identity = identity(root)
        # Short Unix socket path, independently private for each OS account and checkout.
        base = STATE_ROOT / f"sigma-ui-{os.getuid()}"
        private_directory(base)
        self.directory = base / self.identity[:24]
        private_directory(self.directory)
        self.path = self.directory / "control.sock"
        self.owner_path = self.directory / "owner.json"
        self.lock: int | None = None
        self.listener: socket.socket | None = None

    @staticmethod
    def _process(pid: int) -> dict[str, str] | None:
        """Inspect process birth and command so stale PIDs cannot be reused."""
        if pid <= 1:
            return None
        try:
            def field(name: str) -> str:
                return subprocess.check_output(
                    ["ps", "-ww", "-p", str(pid), "-o", f"{name}="],
                    text=True,
                    stderr=subprocess.DEVNULL,
                    timeout=2,
                ).strip()

            return {
                "uid": field("uid"),
                "start": field("lstart"),
                "stat": field("stat"),
                "command": field("command"),
            }
        except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
            return None

    def _verified_owner(self) -> tuple[int, dict[str, str]] | None:
        """Only signal the exact same-checkout launcher with the same birth time."""
        try:
            info = self.owner_path.lstat()
        except FileNotFoundError:
            return None
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise RuntimeError("Unsafe SIGMA owner record; refusing to signal.")
        try:
            record = json.loads(self.owner_path.read_text(encoding="utf-8"))
            if record["identity"] != self.identity or type(record["pid"]) is not int:
                raise ValueError("identity")
            pid = record["pid"]
            current = self._process(pid)
            if current is None:
                return None
            command = current["command"]
            entry = str(self.root / ".venv" / "bin" / "sigma")
            if (
                current["uid"] != str(os.getuid())
                or current["start"] != record["start"]
                or current["command"] != record["command"]
                or entry not in command
                or not command.endswith(" ui")
            ):
                raise RuntimeError("SIGMA owner process identity changed; refusing to signal.")
            return pid, current
        except (ValueError, TypeError, KeyError, UnicodeError, OSError) as exc:
            raise RuntimeError("Cannot verify SIGMA owner record; refusing takeover.") from exc

    def _resume_suspended(self) -> bool:
        owner = self._verified_owner()
        if owner is None or "T" not in owner[1]["stat"].upper():
            return False
        print("Resuming suspended SIGMA launcher for clean shutdown…", flush=True)
        os.kill(owner[0], signal.SIGCONT)
        return True

    def _force_stopped(self) -> bool:
        owner = self._verified_owner()
        if owner is None or "T" not in owner[1]["stat"].upper():
            return False
        print("Suspended SIGMA launcher remained unresponsive; terminating it…", flush=True)
        os.kill(owner[0], signal.SIGKILL)
        return True

    def _register_owner(self) -> None:
        process = self._process(os.getpid())
        if process is None:
            raise RuntimeError("Cannot verify current SIGMA launcher.")
        record = {
            "identity": self.identity,
            "pid": os.getpid(),
            "start": process["start"],
            "command": process["command"],
        }
        if str(self.root / ".venv" / "bin" / "sigma") not in process["command"]:
            raise RuntimeError("Cannot identify current SIGMA launcher; refusing registration.")
        temporary = self.directory / f"owner.{os.getpid()}.tmp"
        fd = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(record, stream)
            os.replace(temporary, self.owner_path)
            self.registered = True
        finally:
            temporary.unlink(missing_ok=True)

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
            deadline = time.monotonic() + 12
            recovered = False
            while True:
                try:
                    fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    if not recovered and self._resume_suspended():
                        recovered = True
                    if time.monotonic() >= deadline:
                        if self._force_stopped():
                            deadline = time.monotonic() + 6
                        else:
                            raise RuntimeError(
                                "Another SIGMA launcher still holds the startup lock. "
                                "Check its terminal; no unverified process was killed."
                            ) from None
                    time.sleep(0.1)
            self._resume_suspended()
            self.replace()
            if not self.shutdown_only:
                self.listener = socket.socket(socket.AF_UNIX)
                self.listener.bind(str(self.path))
                self.listener.listen(8)
                self.listener.settimeout(0.1)
                self._register_owner()
            return self
        except BaseException:
            self.__exit__(None, None, None)
            raise

    def _terminate_unresponsive_owner(self) -> None:
        """Escalate only against the verified owner of this checkout."""
        owner = self._verified_owner()
        if owner is None:
            # The old launcher already exited, leaving a stale control socket.
            return
        pid = owner[0]
        print("Verified SIGMA launcher is unresponsive; requesting shutdown…", flush=True)
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            return
        deadline = time.monotonic() + 4
        while time.monotonic() < deadline:
            if self._verified_owner() is None:
                return
            time.sleep(0.1)
        if self._verified_owner() is not None:
            print("Verified launcher did not stop; forcing shutdown…", flush=True)
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass

    def replace(self) -> None:
        try:
            info = self.path.lstat()
        except FileNotFoundError:
            return
        if not stat.S_ISSOCK(info.st_mode) or info.st_uid != os.getuid():
            raise RuntimeError("Unverifiable SIGMA control record; refusing takeover.")
        with socket.socket(socket.AF_UNIX) as client:
            client.settimeout(8)
            try:
                client.connect(str(self.path))
            except TimeoutError:
                self._terminate_unresponsive_owner()
            except OSError as exc:
                if exc.errno not in (errno.ECONNREFUSED, errno.ENOENT):
                    raise RuntimeError(
                        "Cannot verify previous SIGMA instance; refusing takeover."
                    ) from None
            else:
                try:
                    client.sendall(
                        json.dumps({"identity": self.identity, "command": "identify"}).encode()
                        + b"\n"
                    )
                    owned = self.receive(client)
                except (OSError, TimeoutError):
                    self._terminate_unresponsive_owner()
                else:
                    if owned != {"identity": self.identity, "status": "owned"}:
                        raise RuntimeError(
                            "Previous instance identity mismatch; refusing takeover."
                        )
                    print("Stopping existing SIGMA instance…", flush=True)
                    try:
                        client.sendall(
                            json.dumps(
                                {"identity": self.identity, "command": "shutdown"}
                            ).encode() + b"\n"
                        )
                        stopped = self.receive(client)
                    except (OSError, TimeoutError):
                        self._terminate_unresponsive_owner()
                    else:
                        if stopped != {"identity": self.identity, "status": "stopped"}:
                            raise RuntimeError(
                                "Previous SIGMA instance did not confirm cleanup."
                            )
        # Only while holding the launch lock, after confirmed or forced cleanup.
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
        if self.registered:
            self.owner_path.unlink(missing_ok=True)
            self.registered = False
        self.unlock()
