"""Check maintenance failure handling without installing or changing dependencies."""

import subprocess
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from unittest.mock import Mock, patch

from sigma.projects import ROOT
from sigma.tooling import run_tooling
from sigma.ui import run_ui, stop_servers


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
    with (
        patch("pathlib.Path.is_dir", return_value=True),
        patch("sigma.ui.shutil.which", return_value="npm"),
        patch("sigma.ui.check_ports", side_effect=RuntimeError("port occupied")),
        patch("sigma.ui.subprocess.Popen") as launch,
        patch("sigma.ui.stop_servers"),
    ):
        assert run_ui() == 1
        launch.assert_not_called()
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
        with (
            patch("pathlib.Path.is_dir", return_value=True),
            patch("sigma.ui.shutil.which", return_value="npm"),
            patch("sigma.ui.check_ports"),
            patch(
                "sigma.ui.subprocess.Popen",
                side_effect=[backend, OSError("failed")]
                if outcome == "launch failure"
                else [backend, frontend],
            ),
            patch("sigma.ui.ready", return_value=True),
            patch("sigma.ui.time.sleep", side_effect=KeyboardInterrupt),
            patch("sigma.ui.stop_servers") as stop,
        ):
            assert run_ui() == (0 if outcome == "interrupt" else 1)
            stop.assert_called_once_with(
                [backend] if outcome == "launch failure" else [backend, frontend]
            )
    child = Mock(pid=12345)
    child.wait.side_effect = [subprocess.TimeoutExpired("server", 5), 0]
    with patch("sigma.ui.os.killpg") as kill:
        stop_servers([child])
        assert kill.call_count == 2  # Escalates if a server fails to stop gracefully.
        assert child.wait.call_count == 2


def main() -> None:
    output = StringIO()
    with redirect_stdout(output), redirect_stderr(output):
        check_failures()
        check_ui()
    for message in ("Missing prerequisite", "exit 7", "Could not start"):
        assert message in output.getvalue()
    print("PASS maintenance failures and UI launch, early exit, interrupt and cleanup")


if __name__ == "__main__":
    main()
