"""Check maintenance failure handling without installing or changing dependencies."""

import os
import signal
import subprocess
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, Mock, call, patch

from sigma.cli import main as cli_main
from sigma.projects import ROOT
from sigma.tooling import _safe_independent_test_step, run_tooling
from sigma.ui import local_google_configuration_warning, run_shutdown, run_ui, stop_servers
from sigma.ui_instance import Instance


def check_failures() -> None:
    assert _safe_independent_test_step(
        ["uv", "run", "--locked", "--no-sync", "python", "tests/gce_host.py"]
    )
    assert _safe_independent_test_step(
        ["uv", "run", "--locked", "--no-sync", "python", "tests/state_backup.py"]
    )
    assert not _safe_independent_test_step(["bash", "deploy/install-gce-host.sh"])
    assert not _safe_independent_test_step(
        ["uv", "run", "--locked", "--no-sync", "python", "scripts/increment15_offline_pairs.py"]
    )
    assert not _safe_independent_test_step(["npm", "--prefix", "frontend", "run", "build"])
    with (
        patch("sigma.tooling.shutil.which", return_value=None),
        patch("sigma.tooling.subprocess.run") as run,
    ):
        assert run_tooling("setup") == 2
        run.assert_not_called()
    with (
        patch("sigma.tooling.shutil.which", return_value="tool"),
        patch("sigma.tooling.subprocess.run") as run,
    ):

        def fail_independent_checks(command, **kwargs):
            returncode = (
                7 if "tests/lifecycle.py" in command else 3 if "tests/recents.py" in command else 0
            )
            return subprocess.CompletedProcess(command, returncode)

        run.side_effect = fail_independent_checks
        assert run_tooling("test") == 7
        assert run.call_count > 40
        completed = [item.args[0] for item in run.call_args_list]
        assert any("tests/gce_host.py" in command for command in completed)
        assert any("tests/state_backup.py" in command for command in completed)
        assert any(command[-2:] == ["run", "typecheck"] for command in completed)
        assert not any("increment15_offline_pairs.py" in command for command in completed)
        assert not any(command[-2:] == ["run", "build"] for command in completed)
        assert run.call_args.kwargs["cwd"] == ROOT
    with (
        patch("sigma.tooling.shutil.which", return_value="tool"),
        patch("sigma.tooling.subprocess.run", side_effect=OSError("cannot launch")),
    ):
        assert run_tooling("setup") == 2


def check_start_cli() -> None:
    output = StringIO()
    with patch("sys.argv", ["sigma", "start", "--help"]), redirect_stdout(output):
        try:
            cli_main()
        except SystemExit as exc:
            assert exc.code == 0
        else:
            raise AssertionError("start --help did not exit")
    help_text = output.getvalue()
    assert "--nav" in help_text and "--navigate" in help_text
    assert "--admin" not in help_text and "--google-auth" not in help_text
    output = StringIO()
    with patch("sys.argv", ["sigma", "start", "--admin"]), redirect_stderr(output):
        try:
            cli_main()
        except SystemExit as exc:
            assert exc.code == 2
        else:
            raise AssertionError("removed admin option was accepted")
    assert "unrecognized arguments" in output.getvalue()
    output = StringIO()
    with patch("sys.argv", ["sigma", "--help"]), redirect_stdout(output):
        try:
            cli_main()
        except SystemExit as exc:
            assert exc.code == 0
        else:
            raise AssertionError("shutdown --help did not exit")
    assert "identifiable local SIGMA UI servers" in output.getvalue()


def check_command_help() -> None:
    for argv in (
        ["sigma", "-h", "create"],
        ["sigma", "create", "-h"],
        ["sigma", "create", "--help"],
    ):
        output = StringIO()
        with patch("sys.argv", argv), redirect_stdout(output):
            try:
                cli_main()
            except SystemExit as exc:
                assert exc.code == 0
            else:
                raise AssertionError(f"{argv} did not exit")
        help_text = output.getvalue()
        assert "Create a project in the configured projects root" in help_text
        assert "--title TITLE         Set title (required)" in help_text
        assert "(default: medium)" in help_text
        assert "Example:" in help_text and "SIGMA_PROJECTS_ROOT" in help_text

    output = StringIO()
    with patch("sys.argv", ["sigma", "-h"]), redirect_stdout(output):
        try:
            cli_main()
        except SystemExit as exc:
            assert exc.code == 0
        else:
            raise AssertionError("top-level -h did not exit")
    top_help = output.getvalue()
    assert "SIGMA projects and repository maintenance" in top_help
    assert "Use `sigma -h COMMAND`" in top_help
    assert "SIGMA_PROJECTS_ROOT selects the root" not in top_help

    # Every registered command has the same detailed-help structure.
    from sigma.cli import COMMAND_DETAILS

    for command in COMMAND_DETAILS:
        output = StringIO()
        with patch("sys.argv", ["sigma", "-h", command]), redirect_stdout(output):
            try:
                cli_main()
            except SystemExit as exc:
                assert exc.code == 0
            else:
                raise AssertionError(f"help for {command} did not exit")
        help_text = output.getvalue()
        assert "Example:" in help_text, command
        assert "Notes:" in help_text, command


def check_ui() -> None:
    # Host shells may export an admin address without the paired OAuth test
    # credentials. These lifecycle tests exercise ordinary local startup.
    with patch.dict(
        "os.environ",
        {
            "SIGMA_CLOUD_BOOTSTRAP_ADMIN_EMAIL": "",
            "GOOGLE_OIDC_CLIENT_ID": "",
            "GOOGLE_OIDC_CLIENT_SECRET": "",
        },
    ):
        _check_ui()


def _check_ui() -> None:
    # Process lifecycle/ownership is exercised separately with real processes.

    with (
        patch("sigma.ui.Instance", return_value=MagicMock()),
        patch("sigma.ui.load_local_config"),
        patch("sigma.ui.recover_orphans", return_value=[]),
        patch("sigma.ui.stop_registered_instances", return_value=[]),
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
    for outcome in ("launch failure", "early exit", "interrupt", "navigate"):
        backend = Mock()
        backend.poll.return_value = 7 if outcome == "early exit" else None
        frontend = Mock()
        frontend.poll.return_value = None
        owner = MagicMock()
        owner.__enter__.return_value.replacement_request.return_value = None
        with (
            patch("sigma.ui.Instance", return_value=owner),
            patch("sigma.ui.load_local_config"),
            patch("sigma.ui.recover_orphans", return_value=[]),
            patch("sigma.ui.stop_registered_instances", return_value=[]),
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
            assert run_ui(navigate=outcome == "navigate") == (
                0 if outcome in {"interrupt", "navigate"} else 1
            )
            stop.assert_called_once_with(
                [backend] if outcome == "launch failure" else [backend, frontend]
            )
            if outcome == "navigate":
                open_browser.assert_called_once_with("http://127.0.0.1:5173", new=2)
            else:
                open_browser.assert_not_called()
    child = Mock()
    stop_servers([child])
    child.stdin.close.assert_called_once()
    child.wait.assert_called_once_with(timeout=8)


def check_local_google_startup() -> None:
    backend, frontend = Mock(), Mock()
    backend.poll.return_value = None
    frontend.poll.return_value = None
    owner = MagicMock()
    owner.__enter__.return_value.replacement_request.return_value = None
    with (
        patch.dict(
            "os.environ",
            {
                "SIGMA_CLOUD_BOOTSTRAP_ADMIN_EMAIL": "owner@gmail.com",
                "GOOGLE_OIDC_CLIENT_ID": "client-id",
                "GOOGLE_OIDC_CLIENT_SECRET": "server-secret",
                "SIGMA_CLOUD_AUTH_ENABLED": "false",
            },
            clear=True,
        ),
        patch("sigma.ui.Instance", return_value=owner),
        patch("sigma.ui.load_local_config"),
        patch("sigma.ui.recover_orphans", return_value=[]),
        patch("sigma.ui.stop_registered_instances", return_value=[]),
        patch("pathlib.Path.is_dir", return_value=True),
        patch("sigma.ui.shutil.which", return_value="npm"),
        patch("sigma.ui.wait_for_ports"),
        patch("sigma.ui.subprocess.Popen", side_effect=[backend, frontend]) as launch,
        patch("sigma.ui.ready", return_value=True),
        patch("sigma.ui.webbrowser.open", return_value=True),
        patch("sigma.ui.time.sleep", side_effect=KeyboardInterrupt),
        patch("sigma.ui.stop_servers"),
    ):
        assert run_ui(navigate=True) == 0
    backend_env = launch.call_args_list[0].kwargs["env"]
    frontend_env = launch.call_args_list[1].kwargs["env"]
    for key, value in {
        "SIGMA_CLOUD_AUTH_ENABLED": "true",
        "SIGMA_CLOUD_AUTH_LOCAL": "true",
        "SIGMA_CLOUD_PUBLIC_ORIGIN": "http://127.0.0.1:5173",
        "SIGMA_CLOUD_BOOTSTRAP_ADMIN_EMAIL": "owner@gmail.com",
    }.items():
        assert backend_env[key] == value
    assert backend_env["GOOGLE_OIDC_CLIENT_SECRET"] == "server-secret"
    assert "GOOGLE_OIDC_CLIENT_SECRET" not in frontend_env
    assert "SIGMA_CLOUD_BOOTSTRAP_ADMIN_EMAIL" not in frontend_env
    assert frontend_env["SIGMA_CLOUD_AUTH_LOCAL"] == "true"


def check_local_google_setup_warning() -> None:
    with patch.dict(
        "os.environ",
        {
            "GOOGLE_OIDC_CLIENT_ID": "client-id",
            "GOOGLE_OIDC_CLIENT_SECRET": "server-secret",
            "SIGMA_CLOUD_BOOTSTRAP_ADMIN_EMAIL": "",
        },
        clear=True,
    ):
        warning = local_google_configuration_warning()
    assert warning is not None
    assert "SIGMA_CLOUD_BOOTSTRAP_ADMIN_EMAIL" in warning
    assert "source ~/.bashrc" in warning
    assert "server-secret" not in warning
    with patch.dict(
        "os.environ",
        {
            "GOOGLE_OIDC_CLIENT_ID": "client-id",
            "GOOGLE_OIDC_CLIENT_SECRET": "server-secret",
            "SIGMA_CLOUD_BOOTSTRAP_ADMIN_EMAIL": "owner@gmail.com",
        },
        clear=True,
    ):
        assert local_google_configuration_warning() is None


def check_partial_google_startup_warns_without_enabling_auth() -> None:
    backend, frontend = Mock(), Mock()
    backend.poll.return_value = None
    frontend.poll.return_value = None
    owner = MagicMock()
    owner.__enter__.return_value.replacement_request.return_value = None
    warning_output = StringIO()
    with (
        patch.dict(
            "os.environ",
            {
                "GOOGLE_OIDC_CLIENT_ID": "client-id",
                "GOOGLE_OIDC_CLIENT_SECRET": "server-secret",
                "SIGMA_CLOUD_BOOTSTRAP_ADMIN_EMAIL": "",
            },
            clear=True,
        ),
        patch("sigma.ui.Instance", return_value=owner),
        patch("sigma.ui.load_local_config"),
        patch("sigma.ui.recover_orphans", return_value=[]),
        patch("sigma.ui.stop_registered_instances", return_value=[]),
        patch("pathlib.Path.is_dir", return_value=True),
        patch("sigma.ui.shutil.which", return_value="npm"),
        patch("sigma.ui.wait_for_ports"),
        patch("sigma.ui.subprocess.Popen", side_effect=[backend, frontend]) as launch,
        patch("sigma.ui.ready", return_value=True),
        patch("sigma.ui.time.sleep", side_effect=KeyboardInterrupt),
        patch("sigma.ui.stop_servers"),
        redirect_stderr(warning_output),
    ):
        assert run_ui() == 0
    assert "SIGMA_CLOUD_BOOTSTRAP_ADMIN_EMAIL" in warning_output.getvalue()
    backend_env = launch.call_args_list[0].kwargs["env"]
    assert "SIGMA_CLOUD_AUTH_ENABLED" not in backend_env
    assert backend_env["GOOGLE_OIDC_CLIENT_SECRET"] == "server-secret"


def check_shutdown_and_suspended() -> None:
    # SIGKILL verified dormant launchers directly, so they cannot wake
    # simultaneously and compete to start servers. No real signals are sent.
    with TemporaryDirectory() as directory, patch("sigma.ui_instance.STATE_ROOT", Path(directory)):
        instance = Instance()
        command = (
            str(ROOT / ".venv" / "bin" / "python")
            + " "
            + str(ROOT / ".venv" / "bin" / "sigma")
            + " start"
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
                return_value="p123456\np123457\n",
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
            processes[123456]["command"] = command.removesuffix(" start") + " ui"
            assert len(instance._legacy_lock_owners()) == 2
            processes[123456]["command"] = command + " --nav"
            assert len(instance._legacy_lock_owners()) == 2
            processes[123456]["command"] = command
            processes[123457]["command"] = "/usr/bin/unrelated ui"
            try:
                instance._terminate_suspended_lock_holders()
            except RuntimeError as exc:
                assert "unverified holder" in str(exc)
            else:
                raise AssertionError("Unrelated process holding lock was trusted")
            send.assert_not_called()

    with (
        patch("sigma.ui.stop_registered_instances", return_value=[]) as cleanup_all,
        patch("sigma.ui.recover_orphans", return_value=[]) as cleanup,
    ):
        assert run_shutdown() == 0
        cleanup_all.assert_called_once_with()
        cleanup.assert_called_once_with()


def main() -> None:
    output = StringIO()
    with redirect_stdout(output), redirect_stderr(output):
        check_failures()
        check_start_cli()
        check_command_help()
        check_ui()
        check_local_google_startup()
        check_local_google_setup_warning()
        check_partial_google_startup_warns_without_enabling_auth()
        check_shutdown_and_suspended()
    for message in ("Missing prerequisite", "exit 7", "Could not start"):
        assert message in output.getvalue()
    assert "2 step(s) failed" in output.getvalue()
    assert "2 non-read-only step(s) skipped after failures" in output.getvalue()
    assert "FastAPI API server: http://127.0.0.1:8000" in output.getvalue()
    assert "Vite UI server:    http://127.0.0.1:5173" in output.getvalue()
    print("PASS maintenance, UI lifecycle, verified suspended-owner recovery and shutdown")


if __name__ == "__main__":
    main()
