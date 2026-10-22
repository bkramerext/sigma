"""Offline tests for conservative SIGMA orphan-server recovery."""

import os
import signal
from pathlib import Path
from unittest.mock import call, patch

from sigma.ui_orphans import _verified, recover_orphans

ROOT = Path("/tmp/sigma-fixture-checkout")
BACKEND = (
    str(os.getuid()),
    "Wed Oct 21 11:00:00 2026",
    (
        "/tmp/sigma-fixture-checkout/.venv/bin/python -m uvicorn "
        "sigma.server:create_app --factory --host 127.0.0.1 --port 8000"
    ),
    "/tmp/sigma-fixture-checkout",
)
FRONTEND = (
    str(os.getuid()),
    "Wed Oct 21 11:00:01 2026",
    (
        "node /tmp/sigma-fixture-checkout/frontend/node_modules/.bin/vite "
        "--host 127.0.0.1 --port 5173 --strictPort"
    ),
    "/tmp/sigma-fixture-checkout/frontend",
)


def main() -> None:
    with (
        patch("sigma.ui_orphans._process", return_value=BACKEND),
        patch("sigma.ui_orphans._sigma_instance", return_value="a" * 32),
    ):
        assert _verified(8000, 123, ROOT) == BACKEND
        assert _verified(5173, 123, ROOT) is None
    with patch("sigma.ui_orphans._process", return_value=FRONTEND):
        assert _verified(5173, 124, ROOT) == FRONTEND
        assert _verified(8000, 124, ROOT) is None
    with (
        patch("sigma.ui_orphans._process", return_value=BACKEND),
        patch("sigma.ui_orphans._sigma_instance", return_value=None),
    ):
        assert _verified(8000, 123, ROOT) is None

    active = {8000: {123}, 5173: {124}}

    def only_backend(port: int) -> set[int]:
        return {123} if port == 8000 else set()

    def listeners(port: int) -> set[int]:
        return active[port].copy()

    def kill(pid: int, sig: signal.Signals) -> None:
        assert sig == signal.SIGTERM
        active[8000 if pid == 123 else 5173].remove(pid)

    with (
        patch("sigma.ui_orphans._listeners", side_effect=listeners),
        patch(
            "sigma.ui_orphans._process",
            side_effect=lambda pid: BACKEND if pid == 123 else FRONTEND,
        ),
        patch("sigma.ui_orphans._sigma_instance", return_value="a" * 32),
        patch("sigma.ui_orphans.os.kill", side_effect=kill) as sent,
        patch("pathlib.Path.resolve", return_value=ROOT),
    ):
        recover_orphans(ROOT)
    assert sent.call_args_list == [
        call(123, signal.SIGTERM),
        call(124, signal.SIGTERM),
    ]

    with (
        patch("sigma.ui_orphans._listeners", side_effect=only_backend),
        patch("sigma.ui_orphans._process", return_value=BACKEND),
        patch("sigma.ui_orphans._sigma_instance", return_value=None),
        patch("sigma.ui_orphans.os.kill") as sent,
        patch("pathlib.Path.resolve", return_value=ROOT),
    ):
        recover_orphans(ROOT)
        sent.assert_not_called()

    changed = (BACKEND[0], BACKEND[1], BACKEND[2], "/different-checkout")
    with (
        patch("sigma.ui_orphans._listeners", side_effect=only_backend),
        patch("sigma.ui_orphans._process", side_effect=[BACKEND, changed]),
        patch("sigma.ui_orphans._sigma_instance", return_value="a" * 32),
        patch("sigma.ui_orphans.os.kill") as sent,
        patch("pathlib.Path.resolve", return_value=ROOT),
    ):
        recover_orphans(ROOT)
        sent.assert_not_called()

    with (
        patch("sigma.ui_orphans._listeners", side_effect=only_backend),
        patch("sigma.ui_orphans._process", return_value=BACKEND),
        patch("sigma.ui_orphans._sigma_instance", return_value="a" * 32),
        patch("sigma.ui_orphans.os.kill") as sent,
        patch("sigma.ui_orphans.time.monotonic", side_effect=[0, 5]),
        patch("pathlib.Path.resolve", return_value=ROOT),
    ):
        recover_orphans(ROOT)
    assert sent.call_args_list == [
        call(123, signal.SIGTERM),
        call(123, signal.SIGKILL),
    ]
    print(
        "PASS verified SIGMA orphan shutdown, same-checkout checks, "
        "PID reuse and unrelated listeners"
    )


if __name__ == "__main__":
    main()
