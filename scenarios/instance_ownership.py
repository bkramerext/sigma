"""Control ownership boundaries without starting servers or touching real state."""

import json
import os
import socket
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
from unittest.mock import patch

from sigma.ui_instance import Instance, identity, private_directory

with (
    TemporaryDirectory(dir="/tmp") as temporary,
    patch("sigma.ui_instance.STATE_ROOT", Path(temporary)),
):
    base = Path(temporary)
    root = base / "checkout"
    other = base / "other"
    root.mkdir()
    other.mkdir()
    link = base / "alias"
    link.symlink_to(root, target_is_directory=True)
    assert identity(link) == identity(root) != identity(other)
    link.unlink()
    link.symlink_to(other, target_is_directory=True)
    assert identity(link) == identity(other)
    unsafe = base / "unsafe"
    unsafe.mkdir(mode=0o755)
    alias = base / "unsafe-alias"
    alias.symlink_to(root, target_is_directory=True)
    for path in (unsafe, alias):
        try:
            private_directory(path)
            raise AssertionError("Unsafe directory accepted")
        except RuntimeError:
            pass
    instance = Instance(root)
    instance.path.write_text("not an ownership record")
    try:
        with instance:
            raise AssertionError("Non-socket ownership record accepted")
    except RuntimeError:
        pass
    assert instance.path.read_text() == "not an ownership record"
    instance.path.unlink()
    # A refused, private owned socket is safely recoverable; no PID is consulted.
    with socket.socket(socket.AF_UNIX) as stale:
        stale.bind(str(instance.path))
    with Instance(root) as recovered:
        assert recovered.path.exists()
    assert not instance.path.exists()
    # A live endpoint with a different handshake never receives shutdown.
    received = []
    with socket.socket(socket.AF_UNIX) as foreign:
        foreign.bind(str(instance.path))
        foreign.listen()

        def reply():
            client, _ = foreign.accept()
            with client:
                received.append(Instance.receive(client))
                client.sendall(
                    json.dumps({"identity": "different", "status": "owned"}).encode() + b"\n"
                )
                assert client.recv(1024) == b""

        thread = Thread(target=reply)
        thread.start()
        try:
            with Instance(root):
                raise AssertionError("Unverified live endpoint accepted")
        except RuntimeError as error:
            assert "identity mismatch" in str(error)
        thread.join(timeout=3)
        assert not thread.is_alive() and len(received) == 1
        assert instance.path.exists()  # The unverified socket was not removed.
    instance.path.unlink()
    lock = instance.directory / "launch.lock"
    lock.unlink()
    target = base / "unrelated"
    target.write_text("retain")
    lock.symlink_to(target)
    try:
        with Instance(root):
            raise AssertionError("Symlink launch lock accepted")
    except OSError:
        pass
    assert target.read_text() == "retain"
    assert os.stat(instance.directory).st_mode & 0o777 == 0o700
print(
    "PASS canonical checkout identity/symlink changes, private state, stale recovery, wrong handshake/no shutdown and unsafe lock rejection"
)
