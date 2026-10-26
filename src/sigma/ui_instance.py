"""Private local control endpoint and serialized checkout instance replacement."""

import errno
import fcntl
import hashlib
import json
import os
import shlex
import signal
import socket
import stat
import subprocess
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


def recognized_launcher(command: str, entry: str) -> bool:
    """Recognize supported launch flags without weakening process identity checks."""
    try:
        args = shlex.split(command)
    except ValueError:
        return False
    if entry not in args:
        return False
    args = args[args.index(entry) + 1:]
    if not args or args[0] not in ("start", "ui"):
        return False
    return len(args) == 1 or (
        args[0] == "start"
        and len(args[1:]) == len(set(args[1:]))
        and all(flag in ("--nav", "--navigate", "--signin") for flag in args[1:])
    )


class Instance:
    def __init__(
        self, root: Path = ROOT, shutdown_only: bool = False, register_owner: bool = False
    ):
        self.root = root.resolve(strict=True)
        self.shutdown_only = shutdown_only
        self.register_owner = register_owner
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
            if record.get("root", str(self.root)) != str(self.root):
                raise ValueError("root")
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
                or not recognized_launcher(command, entry)
            ):
                raise RuntimeError(f"SIGMA owner process identity changed (PID {pid}); refusing to signal.")
            return pid, current
        except (ValueError, TypeError, KeyError, UnicodeError, OSError) as exc:
            raise RuntimeError("Cannot verify SIGMA owner record; refusing takeover.") from exc

    def _legacy_lock_owners(self) -> list[tuple[int, dict[str, str]]]:
        """Verify every pre-registration process holding this checkout's lock.

        Multiple suspended launches are expected after repeated Ctrl+Z. Do not
        signal *any* process unless every reported holder is identifiable.
        """
        try:
            output = subprocess.check_output(
                ["lsof", "-nP", "-F", "p", "--", str(self.directory / "launch.lock")],
                text=True,
                stderr=subprocess.DEVNULL,
                timeout=3,
            )
        except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
            return []
        pids = {
            int(line[1:])
            for line in output.splitlines()
            if line.startswith("p") and line[1:].isdigit()
        }
        pids.discard(os.getpid())
        owners: list[tuple[int, dict[str, str]]] = []
        entry = str(self.root / ".venv" / "bin" / "sigma")
        for pid in sorted(pids):
            process = self._process(pid)
            if process is None:
                # Process disappeared while inspecting the lock.
                continue
            if (
                process["uid"] != str(os.getuid())
                or not recognized_launcher(process["command"], entry)
                or not process["start"]
            ):
                raise RuntimeError(
                    f"Startup lock has an unverified holder (PID {pid}); no process was signalled."
                )
            owners.append((pid, process))
        return owners

    def _recoverable_owners(self) -> list[tuple[int, dict[str, str]]]:
        owners = {pid: process for pid, process in self._legacy_lock_owners()}
        registered = self._verified_owner()
        if registered is not None:
            owners[registered[0]] = registered[1]
        return sorted(owners.items())

    def _terminate_suspended_lock_holders(self) -> bool:
        """Stop dormant launch attempts without letting them start servers.

        SIGCONT was unsafe: waking multiple old invocations let all of them
        race to start FastAPI/Vite. The verified suspended owners are instead
        terminated directly. Their pipe guardians clean up any child servers.
        """
        owners = self._recoverable_owners()
        suspended = [(pid, process) for pid, process in owners if "T" in process["stat"].upper()]
        if not suspended:
            return False
        # Validate every identity before signalling any of them.
        for pid, original in suspended:
            current = self._process(pid)
            if current is None:
                continue
            if (
                current["uid"] != original["uid"]
                or current["start"] != original["start"]
                or current["command"] != original["command"]
                or "T" not in current["stat"].upper()
            ):
                raise RuntimeError(
                    "SIGMA launcher identity changed during recovery; nothing was killed."
                )
        print(f"Cleaning up {len(suspended)} suspended SIGMA launcher(s)…", flush=True)
        for pid, original in suspended:
            current = self._process(pid)
            if current is None:
                continue
            if (
                current["uid"] != original["uid"]
                or current["start"] != original["start"]
                or current["command"] != original["command"]
                or "T" not in current["stat"].upper()
            ):
                raise RuntimeError(
                    "SIGMA launcher identity changed during recovery; stopping safely."
                )
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        return True

    def _register_owner(self) -> None:
        process = self._process(os.getpid())
        if process is None:
            raise RuntimeError("Cannot verify current SIGMA launcher.")
        record = {
            "identity": self.identity,
            "root": str(self.root),
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
            while True:
                try:
                    fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    if self._terminate_suspended_lock_holders():
                        deadline = time.monotonic() + 8
                    if time.monotonic() >= deadline:
                        raise RuntimeError(
                            "Another active SIGMA launch holds the startup lock. "
                            "No unverified process was killed."
                        ) from None
                    time.sleep(0.1)
            self.replace()
            if not self.shutdown_only:
                self.listener = socket.socket(socket.AF_UNIX)
                self.listener.bind(str(self.path))
                self.listener.listen(8)
                self.listener.settimeout(0.1)
                if self.register_owner:
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
                            json.dumps({"identity": self.identity, "command": "shutdown"}).encode()
                            + b"\n"
                        )
                        stopped = self.receive(client)
                    except (OSError, TimeoutError):
                        self._terminate_unresponsive_owner()
                    else:
                        if stopped != {"identity": self.identity, "status": "stopped"}:
                            raise RuntimeError("Previous SIGMA instance did not confirm cleanup.")
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


def _record_root(record: object) -> Path | None:
    """Resolve a checkout from an owner record, including pre-root records."""
    if not isinstance(record, dict) or not isinstance(record.get("identity"), str):
        return None
    raw_root = record.get("root")
    if isinstance(raw_root, str):
        root = Path(raw_root)
    else:
        command = record.get("command")
        if not isinstance(command, str):
            return None
        try:
            tokens = shlex.split(command)
        except ValueError:
            return None
        entry = next((Path(token) for token in tokens if token.endswith("/.venv/bin/sigma")), None)
        if entry is None:
            return None
        root = entry.parents[2]
    try:
        root = root.resolve(strict=True)
        if identity(root) != record["identity"]:
            return None
    except (OSError, RuntimeError, KeyError):
        return None
    return root


def _safe_state_directory(path: Path) -> bool:
    try:
        info = path.lstat()
    except OSError:
        return False
    return stat.S_ISDIR(info.st_mode) and info.st_uid == os.getuid() and info.st_mode & 0o077 == 0


def _clean_stale_files(directory: Path, owner_path: Path) -> None:
    """Remove stale metadata only while its per-checkout lock is held."""
    owner_path.unlink(missing_ok=True)
    for temporary in directory.glob("owner.*.tmp"):
        try:
            info = temporary.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid():
            temporary.unlink(missing_ok=True)


def _clean_unregistered_state(directory: Path) -> bool:
    """Remove abandoned sockets/temporary files when no launcher owns the lock."""
    lock_path = directory / "launch.lock"
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise RuntimeError("Unsafe SIGMA launch lock; refusing stale-state cleanup.")
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return False
        socket_path = directory / "control.sock"
        try:
            socket_info = socket_path.lstat()
        except FileNotFoundError:
            socket_info = None
        if socket_info is not None:
            if not stat.S_ISSOCK(socket_info.st_mode) or socket_info.st_uid != os.getuid():
                raise RuntimeError("Unverifiable SIGMA control record; refusing stale cleanup.")
            with socket.socket(socket.AF_UNIX) as probe:
                probe.settimeout(0.2)
                try:
                    probe.connect(str(socket_path))
                except OSError as exc:
                    if exc.errno not in (errno.ECONNREFUSED, errno.ENOENT):
                        raise RuntimeError("Cannot verify SIGMA control socket; leaving it intact.")
                    socket_path.unlink(missing_ok=True)
                else:
                    return False
        for temporary in directory.glob("owner.*.tmp"):
            try:
                temporary_info = temporary.lstat()
            except FileNotFoundError:
                continue
            if stat.S_ISREG(temporary_info.st_mode) and temporary_info.st_uid == os.getuid():
                temporary.unlink(missing_ok=True)
        return True
    finally:
        os.close(fd)


def _clean_stale_registered_state(directory: Path, owner_path: Path) -> bool:
    """Clear a dead owner record only when its control socket is also dead."""
    fd = os.open(directory / "launch.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        lock_info = os.fstat(fd)
        if (
            not stat.S_ISREG(lock_info.st_mode)
            or lock_info.st_uid != os.getuid()
            or lock_info.st_mode & 0o077
        ):
            raise RuntimeError("Unsafe SIGMA launch lock; refusing stale-state cleanup.")
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return False
        try:
            owner_info = owner_path.lstat()
        except FileNotFoundError:
            return True
        if not stat.S_ISREG(owner_info.st_mode) or owner_info.st_uid != os.getuid():
            raise RuntimeError("Unsafe SIGMA owner record; refusing stale-state cleanup.")
        socket_path = directory / "control.sock"
        try:
            socket_info = socket_path.lstat()
        except FileNotFoundError:
            socket_info = None
        if socket_info is not None:
            if not stat.S_ISSOCK(socket_info.st_mode) or socket_info.st_uid != os.getuid():
                raise RuntimeError("Unverifiable SIGMA control record; refusing stale cleanup.")
            with socket.socket(socket.AF_UNIX) as probe:
                probe.settimeout(0.2)
                try:
                    probe.connect(str(socket_path))
                except OSError as exc:
                    if exc.errno not in (errno.ECONNREFUSED, errno.ENOENT):
                        raise RuntimeError("Cannot verify SIGMA control socket; leaving it intact.")
                    socket_path.unlink(missing_ok=True)
                else:
                    return False
        owner_path.unlink(missing_ok=True)
        for temporary in directory.glob("owner.*.tmp"):
            try:
                temporary_info = temporary.lstat()
            except FileNotFoundError:
                continue
            if stat.S_ISREG(temporary_info.st_mode) and temporary_info.st_uid == os.getuid():
                temporary.unlink(missing_ok=True)
        return True
    finally:
        os.close(fd)


def stop_registered_instances(*, exclude_identity: str | None = None) -> list[str]:
    """Stop every verifiable UI launcher registered by this OS user.

    Per-checkout control sockets and owner records are stored below one private
    directory, so a launcher in any local checkout can request an orderly stop
    without guessing PIDs or treating a port as ownership evidence.
    """
    base = STATE_ROOT / f"sigma-ui-{os.getuid()}"
    if not base.exists():
        return []
    if not _safe_state_directory(base):
        raise RuntimeError("Unsafe SIGMA instance registry; refusing global cleanup.")
    failures: list[str] = []
    for directory in sorted(base.iterdir()):
        if not _safe_state_directory(directory):
            failures.append(f"Unverifiable instance state at {directory}; left untouched.")
            continue
        owner_path = directory / "owner.json"
        try:
            info = owner_path.lstat()
        except FileNotFoundError:
            try:
                cleaned = _clean_unregistered_state(directory)
                if not cleaned:
                    failures.append(
                        f"SIGMA state at {directory} is locked by an unregistered launcher; "
                        "left untouched. Retry after it finishes starting."
                    )
            except (OSError, RuntimeError) as exc:
                failures.append(f"Could not clean stale SIGMA state at {directory}: {exc}")
            continue
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
            failures.append(f"Unsafe SIGMA owner record at {owner_path}; left untouched.")
            continue
        try:
            record = json.loads(owner_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, UnicodeError):
            failures.append(f"Unreadable SIGMA owner record at {owner_path}; left untouched.")
            continue
        if not isinstance(record, dict):
            failures.append(f"Malformed SIGMA owner record at {owner_path}; left untouched.")
            continue
        owner_identity = record.get("identity")
        if not isinstance(owner_identity, str) or len(owner_identity) != 64:
            failures.append(f"Malformed SIGMA owner identity at {owner_path}; left untouched.")
            continue
        if directory.name != owner_identity[:24]:
            failures.append(f"SIGMA owner identity mismatch at {owner_path}; left untouched.")
            continue
        if exclude_identity is not None and owner_identity == exclude_identity:
            continue
        root = _record_root(record)
        if root is None:
            pid = record.get("pid")
            current = Instance._process(pid) if type(pid) is int else None
            if (
                current is None
                or current.get("uid") != str(os.getuid())
                or current.get("start") != record.get("start")
                or current.get("command") != record.get("command")
            ):
                try:
                    if _clean_stale_registered_state(directory, owner_path):
                        print(f"Removed stale SIGMA owner metadata at {directory}.", flush=True)
                except (OSError, RuntimeError) as exc:
                    failures.append(f"Could not clean stale SIGMA state at {directory}: {exc}")
            else:
                failures.append(
                    f"SIGMA launcher PID {pid} is live but its checkout cannot be verified; left untouched."
                )
            continue
        try:
            instance = Instance(root, shutdown_only=True)
            with instance:
                # A refused/stale control socket is removed by replace(). The
                # exclusive lock makes removing its dead owner record race-safe.
                try:
                    verified = instance._verified_owner()
                except RuntimeError as exc:
                    if "identity changed" not in str(exc):
                        raise
                    verified = None
                if verified is None:
                    _clean_stale_files(directory, owner_path)
        except (OSError, RuntimeError) as exc:
            failures.append(f"Could not stop SIGMA instance at {root}: {exc}")
    return failures
