"""Check maintenance failure handling without installing or changing dependencies."""

import json
import os
import signal
import subprocess
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, Mock, call, patch

from sigma.projects import ROOT
from sigma.tooling import run_tooling
from sigma.ui import run_shutdown, run_ui, stop_servers
from sigma.ui_instance import Instance


def check_failures() -> None:
    with (
        patch("sigma.tooling.shutil.which", return_value=None),
        patch("sigma.tooling.subprocess.run") as run,
    ):
        assert run_tooling("setup") == 2
        run.assert_not_called()
    with (
        patch("sigma.tooling.shutil.which", return_value="tool"),
        patch(
            "sigma.tooling.subprocess.run", return_value=subprocess.CompletedProcess([], 7)
        ) as run,
    ):
        assert run_tooling("test") == 7
        assert run.call_count == 1  # No later steps run after a failure.
        assert run.call_args.kwargs["cwd"] == ROOT
    with (
        patch("sigma.tooling.shutil.which", return_value="tool"),
        patch("sigma.tooling.subprocess.run", side_effect=OSError("cannot launch")),
    ):
        assert run_tooling("setup") == 2


def check_ui() -> None:
    # Process lifecycle/ownership is exercised separately with real processes.

    with (
        patch("sigma.ui.Instance", return_value=MagicMock()),
        patch("sigma.ui.load_local_config"),
        patch("pathlib.Path.is_dir", return_value=True),
        patch("sigma.ui.shutil.which", return_value="npm"),
        patch("sigma.ui.wait_for_ports", side_effect=RuntimeError("port occupied")),
        patch("sigma.ui.subprocess.Popen") as launch,
        patch("sigma.ui.webbrowser.open") as open_browser,
        patch("sigma.ui.stop_servers"),
    ):
        assert run_ui() == 1
        launch.assert_not_called()
        open_browser.assert_not_called()
    with (
        patch("pathlib.Path.is_dir", return_value=False),
        patch("sigma.ui.subprocess.Popen") as launch,
    ):
        assert run_ui() == 2
        launch.assert_not_called()
    for outcome in ("launch failure", "early exit", "interrupt"):
        backend = Mock()
        backend.poll.return_value = 7 if outcome == "early exit" else None
        frontend = Mock()
        frontend.poll.return_value = None
        owner = MagicMock()
        owner.__enter__.return_value.replacement_request.return_value = None
        with (
            patch("sigma.ui.Instance", return_value=owner),
            patch("sigma.ui.load_local_config"),
            patch("pathlib.Path.is_dir", return_value=True),
            patch("sigma.ui.shutil.which", return_value="npm"),
            patch("sigma.ui.wait_for_ports"),
            patch(
                "sigma.ui.subprocess.Popen",
                side_effect=[backend, OSError("failed")]
                if outcome == "launch failure"
                else [backend, frontend],
            ),
            patch("sigma.ui.ready", return_value=True),
            patch("sigma.ui.webbrowser.open", return_value=True) as open_browser,
            patch("sigma.ui.time.sleep", side_effect=KeyboardInterrupt),
            patch("sigma.ui.stop_servers") as stop,
        ):
            assert run_ui() == (0 if outcome == "interrupt" else 1)
            stop.assert_called_once_with(
                [backend] if outcome == "launch failure" else [backend, frontend]
            )
            if outcome == "interrupt":
                open_browser.assert_called_once_with("http://127.0.0.1:5173", new=2)
            else:
                open_browser.assert_not_called()
    child = Mock()
    stop_servers([child])
    child.stdin.close.assert_called_once()
    child.wait.assert_called_once_with(timeout=8)


def check_shutdown_and_suspended() -> None:
    # SIGKILL verified dormant launchers directly, so they cannot wake
    # simultaneously and compete to start servers. No real signals are sent.
    with TemporaryDirectory() as directory, patch("sigma.ui_instance.STATE_ROOT", Path(directory)):
        instance = Instance()
        command = (
            str(ROOT / ".venv" / "bin" / "python")
            + " "
            + str(ROOT / ".venv" / "bin" / "sigma")
            + " ui"
        )
        processes = {
            123456: {
                "uid": str(os.getuid()),
                "start": "Wed Oct 21 12:53:00 2026",
                "stat": "T",
                "command": command,
            },
            123457: {
                "uid": str(os.getuid()),
                "start": "Wed Oct 21 12:54:00 2026",
                "stat": "T",
                "command": command,
            },
        }
        with (
            patch(
                "sigma.ui_instance.subprocess.check_output",
                return_value="p123456\\np123457\\n",
            ),
            patch.object(Instance, "_process", side_effect=lambda pid: processes.get(pid)),
            patch("sigma.ui_instance.os.kill") as send,
        ):
            assert len(instance._legacy_lock_owners()) == 2
            assert instance._terminate_suspended_lock_holders()
            assert send.call_args_list == [
                call(123456, signal.SIGKILL),
                call(123457, signal.SIGKILL),
            ]
            send.reset_mock()
            processes[123456]["stat"] = "S"
            processes[123457]["stat"] = "S"
            assert not instance._terminate_suspended_lock_holders()
            send.assert_not_called()
            processes[123457]["command"] = "/usr/bin/unrelated ui"
            try:
                instance._terminate_suspended_lock_holders()
            except RuntimeError as exc:
                assert "unverified holder" in str(exc)
            else:
                raise AssertionError("Unrelated process holding lock was trusted")
            send.assert_not_called()

    owner = MagicMock()
    with patch("sigma.ui.Instance", return_value=owner) as factory:
        assert run_shutdown() == 0
        factory.assert_called_once_with(shutdown_only=True)
        owner.__enter__.assert_called_once()
        owner.__exit__.assert_called_once()


def main() -> None:
    output = StringIO()
    with redirect_stdout(output), redirect_stderr(output):
        check_failures()
        check_ui()
        check_shutdown_and_suspended()
    for message in ("Missing prerequisite", "exit 7", "Could not start"):
        assert message in output.getvalue()
    assert "FastAPI API server: http://127.0.0.1:8000" in output.getvalue()
    assert "Vite UI server:    http://127.0.0.1:5173" in output.getvalue()
    print("PASS maintenance, UI lifecycle, verified suspended-owner recovery and shutdown")


if __name__ == "__main__":
    main()
