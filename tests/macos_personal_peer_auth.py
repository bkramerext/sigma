"""Native Darwin acceptance for the actual Unix-socket broker credential check.

Run this on a macOS runner, not Linux with mocked platform attributes. It
reproduces the local --prod mechanism=none / peer_auth_unsupported regression.
"""

from __future__ import annotations

import importlib.util
import os
import socket
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    assert sys.platform == "darwin", "This smoke test requires a native macOS host"

    spec = importlib.util.spec_from_file_location(
        "sigma_shared_broker_darwin_smoke", ROOT / "auth-poc" / "shared_broker.py"
    )
    assert spec and spec.loader
    broker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(broker)

    with tempfile.TemporaryDirectory(prefix="sigma-peer-") as directory:
        path = str(Path(directory) / "broker.sock")
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener:
            listener.bind(path)
            listener.listen(1)
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
                client.connect(path)
                with listener.accept()[0] as connection:
                    handler = SimpleNamespace(connection=connection)
                    # Force the same macOS ctypes/libSystem path that the
                    # user's native Python lacks. No forged peer UID fallback.
                    with (
                        patch.object(broker, "socket", SimpleNamespace()),
                        patch.dict(
                            os.environ,
                            {"SIGMA_AUTH_BROKER_CLIENT_UID": str(os.geteuid())},
                        ),
                    ):
                        assert broker.Handler._authorized(handler), (
                            "Darwin getpeereid(2) did not authorize the actual local peer"
                        )
                        with patch.dict(
                            os.environ,
                            {"SIGMA_AUTH_BROKER_CLIENT_UID": str(os.geteuid() + 1)},
                        ):
                            assert not broker.Handler._authorized(handler), (
                                "Incorrect Unix-socket peer UID was accepted"
                            )

    print("PASS real macOS AF_UNIX peer authentication through libSystem getpeereid")


if __name__ == "__main__":
    main()
