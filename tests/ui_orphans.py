"""Offline ownership and cross-checkout recovery checks for local UI servers."""

import os
import signal
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import call, patch

from sigma.ui_orphans import _process, _verified, recover_orphans

MARKER = "a" * 32


def checkout(root: Path) -> None:
    (root / "src/sigma").mkdir(parents=True)
    (root / "frontend/node_modules/.bin").mkdir(parents=True)
    (root / ".venv/bin").mkdir(parents=True)
    (root / "pyproject.toml").touch()
    (root / "src/sigma/server.py").touch()
    (root / "frontend/package.json").touch()
    (root / "sigma").touch()
    (root / ".venv/bin/python").symlink_to(sys.executable)
    (root / "frontend/node_modules/.bin/vite").touch()


def main() -> None:
    with TemporaryDirectory() as temporary:
        base = Path(temporary)
        root = base / "checkout-a"
        other = base / "checkout-b"
        root.mkdir()
        other.mkdir()
        checkout(root)
        checkout(other)
        backend = (
            str(os.getuid()),
            "Wed Oct 21 11:00:00 2026",
            (
                f"{root}/.venv/bin/python -m uvicorn sigma.server:create_app --factory "
                "--host 127.0.0.1 --port 8000"
            ),
            str(root),
            MARKER,
        )
        frontend = (
            str(os.getuid()),
            "Wed Oct 21 11:00:01 2026",
            (
                f"node {other}/frontend/node_modules/.bin/vite "
                "--host 127.0.0.1 --port 5173 --strictPort"
            ),
            str(other / "frontend"),
            MARKER,
        )
        with patch("sigma.ui_orphans._sigma_instance", return_value=MARKER):
            with patch("sigma.ui_orphans._process", return_value=backend):
                assert _verified(8000, 123) == backend
                assert _verified(5173, 123) is None
            with patch("sigma.ui_orphans._process", return_value=frontend):
                assert _verified(5173, 124) == frontend
                assert _verified(8000, 124) is None
                assert _verified(5173, 124, other) == frontend
                assert _verified(5173, 124, root) is None

        def process_command(*args: str) -> str:
            joined = " ".join(args)
            if "uid=" in joined:
                return str(os.getuid())
            if "lstart=" in joined:
                return "Wed Oct 21 11:00:00 2026"
            if "-d cwd" in joined:
                return f"p123\nn{root}"
            if args[:2] == ("ps", "eww"):
                return f"{backend[2]} SIGMA_UI_INSTANCE_ID={MARKER} HOME=/private"
            return backend[2]

        with patch("sigma.ui_orphans._command", side_effect=process_command):
            assert _process(123) == backend

        active = {8000: {123}, 5173: {124}}

        def listeners(port: int) -> set[int]:
            return active[port].copy()

        def kill(pid: int, sig: signal.Signals) -> None:
            assert sig == signal.SIGTERM
            active[8000 if pid == 123 else 5173].remove(pid)

        def process(pid: int):
            return backend if pid == 123 else frontend

        with (
            patch("sigma.ui_orphans._listeners", side_effect=listeners),
            patch("sigma.ui_orphans._process", side_effect=process),
            patch("sigma.ui_orphans._sigma_instance", return_value=MARKER),
            patch("sigma.ui_orphans.os.kill", side_effect=kill) as sent,
        ):
            assert recover_orphans() == []
        assert sent.call_args_list == [call(123, signal.SIGTERM), call(124, signal.SIGTERM)]

        # Same server command and port do not establish ownership without a
        # matching launch marker returned by the process environment and API.
        unknown = (backend[0], backend[1], backend[2], backend[3], "")
        with (
            patch(
                "sigma.ui_orphans._listeners",
                side_effect=lambda port: {123} if port == 8000 else set(),
            ),
            patch("sigma.ui_orphans._process", return_value=unknown),
            patch("sigma.ui_orphans._sigma_instance", return_value=None),
            patch("sigma.ui_orphans.os.kill") as sent,
        ):
            failures = recover_orphans()
        assert sent.call_args_list == []
        assert len(failures) == 1 and "Port 8000" in failures[0] and "PID 123" in failures[0]

        # PID reuse between initial discovery and signal is detected.
        changed = (backend[0], "different start", backend[2], backend[3], MARKER)
        with (
            patch(
                "sigma.ui_orphans._listeners",
                side_effect=lambda port: {123} if port == 8000 else set(),
            ),
            patch("sigma.ui_orphans._process", side_effect=[backend, changed, changed]),
            patch("sigma.ui_orphans._sigma_instance", return_value=MARKER),
            patch("sigma.ui_orphans.os.kill") as sent,
        ):
            failures = recover_orphans()
        assert sent.call_args_list == []
        assert failures and "Port 8000" in failures[0]

    print(
        "PASS cross-checkout orphan discovery, command/marker verification, occupied-port reporting and PID reuse protection"
    )


if __name__ == "__main__":
    main()
