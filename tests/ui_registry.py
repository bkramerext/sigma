"""Cross-checkout launcher registry, stale state, and shutdown regressions."""

import fcntl
import json
import os
import socket
import stat
import tempfile
import threading
from pathlib import Path
from unittest.mock import patch

from sigma.ui_instance import Instance, identity, stop_registered_instances


def serve(instance: Instance, stopped: list[str]) -> None:
    assert instance.listener is not None
    client, _ = instance.listener.accept()
    with client:
        request = Instance.receive(client)
        assert request == {"identity": instance.identity, "command": "identify"}
        client.sendall(
            json.dumps({"identity": instance.identity, "status": "owned"}).encode() + b"\n"
        )
        request = Instance.receive(client)
        assert request == {"identity": instance.identity, "command": "shutdown"}
        stopped.append(str(instance.root))
        client.sendall(
            json.dumps({"identity": instance.identity, "status": "stopped"}).encode() + b"\n"
        )
    instance.owner_path.unlink(missing_ok=True)
    instance.path.unlink(missing_ok=True)


def register_fixture(root: Path, pid: int, *, include_root: bool = True) -> Instance:
    root.mkdir()
    instance = Instance(root, register_owner=True)
    command = f"{root}/.venv/bin/python {root}/.venv/bin/sigma start"
    instance.listener = socket.socket(socket.AF_UNIX)
    instance.listener.bind(str(instance.path))
    instance.listener.listen(1)
    record = {
        "identity": instance.identity,
        "pid": pid,
        "start": f"2026-10-23 test process {pid}",
        "command": command,
    }
    if include_root:
        record["root"] = str(root.resolve())
    instance.owner_path.write_text(json.dumps(record), encoding="utf-8")
    instance.owner_path.chmod(0o600)
    return instance


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="u", dir="/tmp") as temporary:
        base = Path(temporary)
        state = base / "state"
        state.mkdir(mode=0o700)
        roots = [base / "red-checkout", base / "blue-checkout", base / "legacy-checkout"]
        with patch("sigma.ui_instance.STATE_ROOT", state):
            instances = [
                register_fixture(root, 101 + index, include_root=index != 2)
                for index, root in enumerate(roots)
            ]
            stopped: list[str] = []
            threads = [
                threading.Thread(target=serve, args=(instance, stopped)) for instance in instances
            ]
            for thread in threads:
                thread.start()

            def process(pid: int):
                for instance in instances:
                    if instance.owner_path.exists():
                        record = json.loads(instance.owner_path.read_text(encoding="utf-8"))
                        if record["pid"] == pid:
                            return {
                                "uid": str(os.getuid()),
                                "start": record["start"],
                                "stat": "S",
                                "command": record["command"],
                            }
                return None

            with patch("sigma.ui_instance.Instance._process", side_effect=process):
                failures = stop_registered_instances()
                assert failures == [], failures
            for thread in threads:
                thread.join(timeout=3)
                assert not thread.is_alive()
            assert set(stopped) == {str(root.resolve()) for root in roots}, stopped

            stale_root = base / "stale-checkout"
            stale_root.mkdir()
            stale = Instance(stale_root)
            stale.owner_path.write_text(
                json.dumps(
                    {
                        "identity": identity(stale_root),
                        "root": str(stale_root.resolve()),
                        "pid": 999999,
                        "start": "old process birth",
                        "command": f"{stale_root}/.venv/bin/python {stale_root}/.venv/bin/sigma start",
                    }
                ),
                encoding="utf-8",
            )
            stale.owner_path.chmod(stat.S_IRUSR | stat.S_IWUSR)
            with socket.socket(socket.AF_UNIX) as abandoned:
                abandoned.bind(str(stale.path))
            temporary_owner = stale.directory / "owner.999999.tmp"
            temporary_owner.write_text("partial", encoding="utf-8")
            temporary_owner.chmod(0o600)
            with (
                patch("sigma.ui_instance.Instance._process", return_value=None),
                patch("sigma.ui_instance.os.kill") as send,
            ):
                failures = stop_registered_instances()
                assert failures == [], failures
                send.assert_not_called()
            assert not stale.owner_path.exists()
            assert not stale.path.exists()
            assert not temporary_owner.exists()
            # Kernel flock state is released on close; its inode is retained as
            # the stable per-checkout synchronization primitive.
            lock_path = stale.directory / "launch.lock"
            assert lock_path.exists()
            lock_fd = os.open(lock_path, os.O_RDWR)
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
            finally:
                os.close(lock_fd)

    print(
        "PASS global cross-checkout shutdown, stale owner/socket/temp cleanup and no PID signaling"
    )


if __name__ == "__main__":
    main()
