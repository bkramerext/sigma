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

from sigma.cli import main as cli_main
from sigma.projects import ROOT
from sigma.tooling import _safe_independent_test_step, _zstd_setup_steps, run_tooling
from sigma.ui import local_google_configuration_warning, run_shutdown, run_ui, stop_servers
from sigma.ui_instance import Instance


def check_zstd_setup() -> None:
    """Local setup installs zstd through the platform package manager."""
    with (
        patch("sigma.tooling.sys.platform", "darwin"),
        patch(
            "sigma.tooling.shutil.which",
            side_effect=lambda tool: "/brew" if tool == "brew" else None,
        ),
    ):
        assert _zstd_setup_steps() == [["brew", "install", "zstd"]]
    with (
        patch("sigma.tooling.sys.platform", "linux"),
        patch("sigma.tooling.os.geteuid", return_value=500),
        patch(
            "sigma.tooling.shutil.which",
            side_effect=lambda tool: "/usr/bin/tool" if tool in {"apt-get", "sudo"} else None,
        ),
    ):
        assert _zstd_setup_steps() == [
            ["sudo", "apt-get", "update", "-qq"],
            ["sudo", "apt-get", "install", "-y", "zstd"],
        ]
    with patch("sigma.tooling.shutil.which", return_value="/usr/bin/zstd"):
        assert _zstd_setup_steps() == []


def check_failures() -> None:
    check_zstd_setup()
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
        assert any("tests/host_monitor.py" in command for command in completed)
        format_command = next(
            command for command in completed if "format" in command and "--check" in command
        )
        assert "browser_checks" in format_command
        assert "docs/evaluations" in format_command
        assert any(command[-2:] == ["run", "typecheck"] for command in completed)
        assert not any("increment15_offline_pairs.py" in command for command in completed)
        assert not any(command[-2:] == ["run", "build"] for command in completed)
        assert run.call_args.kwargs["cwd"] == ROOT
    # CI keeps a separate Ruff job, but local SIGMA verification still lints.
    with (
        patch.dict(os.environ, {"SIGMA_CI_SEPARATE_RUFF": "1"}),
        patch("sigma.tooling.shutil.which", return_value="tool"),
        patch(
            "sigma.tooling.subprocess.run", return_value=subprocess.CompletedProcess([], 0)
        ) as run,
    ):
        assert run_tooling("test") == 0
        commands = [item.args[0] for item in run.call_args_list]
        assert not any("ruff" in command for command in commands)
        assert any("pyright" in command for command in commands)
        assert any("tests/lifecycle.py" in command for command in commands)

    # CI may skip npm installation on shards that run no frontend build/typecheck.
    with (
        patch.dict(os.environ, {"SIGMA_SETUP_SKIP_NPM": "1"}),
        patch("sigma.tooling.shutil.which", return_value="tool"),
        patch(
            "sigma.tooling.subprocess.run",
            return_value=subprocess.CompletedProcess([], 0),
        ) as run,
    ):
        assert run_tooling("setup") == 0
        setup_commands = [item.args[0] for item in run.call_args_list]
        assert ["uv", "sync", "--locked", "--group", "dev"] in setup_commands
        assert not any(command[0] == "npm" for command in setup_commands)

    # A successful shard emits actual per-check and shard timings as machine-readable JSON.
    with (
        TemporaryDirectory() as directory,
        patch.dict(
            os.environ,
            {
                "SIGMA_CI_TEST_SHARD": "1",
                "SIGMA_CI_SEPARATE_RUFF": "1",
                "SIGMA_CI_TIMINGS_FILE": str(Path(directory) / "timing.json"),
            },
        ),
        patch("sigma.tooling.shutil.which", return_value="tool"),
        patch(
            "sigma.tooling.subprocess.run",
            return_value=subprocess.CompletedProcess([], 0),
        ) as run,
    ):
        assert run_tooling("test") == 0
        report = json.loads((Path(directory) / "timing.json").read_text(encoding="utf-8"))
        assert report["shard"] == "1"
        assert report["schema_version"] == 1
        assert report["failures"] == 0
        assert len(report["steps"]) == run.call_count
        assert report["duration_seconds"] >= 0
        assert all(step["duration_seconds"] >= 0 for step in report["steps"])
        assert all("SIGMA_CI_TIMINGS_FILE" not in c.kwargs["env"] for c in run.call_args_list)

    # All eight CI shards must be exhaustive together, disjoint, and independent.
    plans: dict[str, list[list[str]]] = {}
    shard_names = tuple(str(index) for index in range(1, 9))
    for shard in ("", *shard_names):
        with (
            patch.dict(
                os.environ,
                {"SIGMA_CI_TEST_SHARD": shard, "SIGMA_CI_SEPARATE_RUFF": "1"},
            ),
            patch("sigma.tooling.shutil.which", return_value="tool"),
            patch(
                "sigma.tooling.subprocess.run",
                return_value=subprocess.CompletedProcess([], 0),
            ) as run,
        ):
            assert run_tooling("test") == 0
            plans[shard] = [item.args[0] for item in run.call_args_list]
            assert all(
                "SIGMA_CI_TEST_SHARD" not in item.kwargs["env"] for item in run.call_args_list
            )
    whole = plans[""]
    combined = [step for shard in shard_names for step in plans[shard]]
    assert all(len(plans[shard]) >= 5 for shard in shard_names)
    assert sum(len(plans[shard]) for shard in shard_names) == len(whole)
    assert len({tuple(step) for step in combined}) == len(whole)
    assert {tuple(step) for step in combined} == {tuple(step) for step in whole}
    regular_index = 0
    for step in whole:
        extra_half_b = "tests/research_sessions_part3b.py" in step
        extra_half_c = "tests/research_sessions_part3c.py" in step
        extra_half = extra_half_b or extra_half_c
        if step == ["npm", "--prefix", "frontend", "run", "typecheck"]:
            owner = "1"
        elif step == ["npm", "--prefix", "frontend", "run", "build"]:
            owner = "7"
        elif "tests/crucible_scheduler_evidence.py" in step:
            owner = "1"
        elif "tests/papers_part2.py" in step:
            owner = "3"
        elif "tests/research_sessions_part2.py" in step:
            owner = "5"
        elif "tests/sage_execution.py" in step:
            owner = "1"
        elif "tests/storage.py" in step:
            owner = "2"
        elif "pyright" in step:
            owner = "4"
        elif extra_half:
            owner = "8" if extra_half_b else "6"
        else:
            owner = shard_names[regular_index % 8]
        assert step in plans[owner]
        if not extra_half:
            regular_index += 1
    assert not any("ruff" in step for step in combined)
    # Split suites must each appear once; legacy aggregate drivers are not
    # scheduled in addition to their independently runnable pieces.
    for suite, parts in (("research_sessions", 4), ("papers", 2), ("cloud_auth", 2)):
        for part in range(1, parts + 1):
            name = f"tests/{suite}_part{part}.py"
            assert sum(name in step for step in combined) == 1, name
        assert not any(f"tests/{suite}.py" in step for step in combined)

    assert sum("tests/research_sessions_part3b.py" in step for step in combined) == 1
    assert sum("tests/research_sessions_part3c.py" in step for step in combined) == 1
    assert any("scripts/increment15_offline_pairs.py" in step for step in combined)
    assert any(step[-2:] == ["run", "build"] for step in combined)
    # Runtime-based moves must remain disjoint, exhaustive and intentional.
    for shard, filename in (
        ("1", "tests/crucible_scheduler_evidence.py"),
        ("3", "tests/papers_part2.py"),
        ("5", "tests/research_sessions_part2.py"),
        ("1", "tests/sage_execution.py"),
        ("2", "tests/storage.py"),
        ("4", "pyright"),
    ):
        assert sum(filename in step for step in combined) == 1
        assert any(filename in step for step in plans[shard])
    # If frontend commands move shards, the workflow's npm-skip configuration
    # must be updated rather than silently running without dependencies.
    assert all(
        not any(command[:4] == ["npm", "--prefix", "frontend", "run"] for command in plans[shard])
        for shard in shard_names
        if shard not in {"1", "7"}
    )
    with (
        patch.dict(os.environ, {"SIGMA_CI_TEST_SHARD": "invalid"}),
        patch("sigma.tooling.shutil.which", return_value="tool"),
        patch("sigma.tooling.subprocess.run") as run,
    ):
        assert run_tooling("test") == 2
        run.assert_not_called()

    with (
        patch("sigma.tooling.shutil.which", return_value="tool"),
        patch("sigma.tooling.subprocess.run", side_effect=OSError("cannot launch")),
    ):
        assert run_tooling("setup") == 2


def check_start_cli() -> None:
    for flags, mock_auth in ((["--sponsored"], False), (["--sponsored", "--mock-auth"], True)):
        with (
            patch("sys.argv", ["sigma", "start", *flags]),
            patch("sigma.cli.run_ui", return_value=0) as launch,
        ):
            try:
                cli_main()
            except SystemExit as exc:
                assert exc.code == 0
            else:
                raise AssertionError("start did not exit")
        launch.assert_called_once_with(
            navigate=False, signin=False, mock_auth=mock_auth, sponsored=True, prod=False
        )
    # --prod is forwarded to the local UI launcher, not a production backend.
    with (
        patch("sys.argv", ["sigma", "start", "--prod"]),
        patch("sigma.cli.run_ui", return_value=0) as launch,
    ):
        try:
            cli_main()
        except SystemExit as exc:
            assert exc.code == 0
        else:
            raise AssertionError("start --prod did not exit")
    launch.assert_called_once_with(
        navigate=False, signin=False, mock_auth=False, sponsored=False, prod=True
    )
    for flags, prod in (
        (["--brainstorm"], False),
        (["--brainstorm", "--navigate"], False),
        (["--brainstorm", "--prod"], True),
    ):
        with (
            patch("sys.argv", ["sigma", "start", *flags]),
            patch("sigma.cli.run_ui", return_value=0) as launch,
        ):
            try:
                cli_main()
            except SystemExit as exc:
                assert exc.code == 0
            else:
                raise AssertionError("start --brainstorm did not exit")
        launch.assert_called_once_with(
            navigate=True,
            navigate_path="/brainstorm",
            signin=False,
            mock_auth=False,
            sponsored=False,
            prod=prod,
        )
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
    assert "--brainstorm" in help_text
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
    with patch("sys.argv", ["sigma", "start", "--help"]), redirect_stdout(output):
        try:
            cli_main()
        except SystemExit as exc:
            assert exc.code == 0
        else:
            raise AssertionError("start --help did not exit")
    assert "--sponsored" in output.getvalue()

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
            "SIGMA_CLOUD_ADMIN_CONTACT_EMAIL": "",
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
                "SIGMA_CLOUD_ADMIN_CONTACT_EMAIL": "owner@gmail.com",
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
        assert run_ui(navigate=True, signin=True) == 0
    backend_env = launch.call_args_list[0].kwargs["env"]
    frontend_env = launch.call_args_list[1].kwargs["env"]
    for key, value in {
        "SIGMA_CLOUD_AUTH_ENABLED": "true",
        "SIGMA_CLOUD_AUTH_LOCAL": "true",
        "SIGMA_CLOUD_PUBLIC_ORIGIN": "http://127.0.0.1:5173",
        "SIGMA_CLOUD_ADMIN_CONTACT_EMAIL": "owner@gmail.com",
    }.items():
        assert backend_env[key] == value
    assert backend_env["GOOGLE_OIDC_CLIENT_SECRET"] == "server-secret"
    assert backend_env["SIGMA_LOCAL_AUTO_ADMIN"] == "true"
    assert "GOOGLE_OIDC_CLIENT_SECRET" not in frontend_env
    assert "SIGMA_CLOUD_ADMIN_CONTACT_EMAIL" not in frontend_env
    assert frontend_env["SIGMA_CLOUD_AUTH_LOCAL"] == "true"


def check_sponsored_local_startup() -> None:
    backend, frontend = Mock(), Mock()
    backend.poll.return_value = frontend.poll.return_value = None
    owner = MagicMock()
    owner.__enter__.return_value.replacement_request.return_value = None
    with (
        patch.dict(
            "os.environ",
            {
                "SIGMA_CLOUD_INFERENCE_PROVIDER": "api_key",
                "SIGMA_CLOUD_OPENAI_API_KEY_FILE": "/private/fixture-key",
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
    ):
        assert run_ui(sponsored=True) == 0
    backend_env = launch.call_args_list[0].kwargs["env"]
    assert backend_env["SIGMA_MOCK_AUTH"] == "0"
    assert backend_env["SIGMA_LOCAL_SPONSORED_TEST_MODE"] == "1"
    assert backend_env["SIGMA_CLOUD_AUTH_LOCAL"] == "true"
    assert backend_env["SIGMA_LOCAL_AUTO_ADMIN"] == "false"
    assert backend_env["SIGMA_CLOUD_INFERENCE_PROVIDER"] == "api_key"
    assert backend_env["SIGMA_CLOUD_OPENAI_API_KEY_FILE"] == "/private/fixture-key"
    frontend_env = launch.call_args_list[1].kwargs["env"]
    assert "SIGMA_CLOUD_OPENAI_API_KEY" not in frontend_env
    assert "SIGMA_CLOUD_OPENAI_API_KEY_FILE" not in frontend_env


def check_local_google_setup_warning() -> None:
    with patch.dict("os.environ", {}, clear=True):
        warning = local_google_configuration_warning()
    assert warning is not None
    assert "GOOGLE_OIDC_CLIENT_ID" in warning
    assert "GOOGLE_OIDC_CLIENT_SECRET" in warning
    with patch.dict(
        "os.environ",
        {
            "GOOGLE_OIDC_CLIENT_ID": "client-id",
            "GOOGLE_OIDC_CLIENT_SECRET": "server-secret",
            "SIGMA_CLOUD_ADMIN_CONTACT_EMAIL": "",
        },
        clear=True,
    ):
        warning = local_google_configuration_warning()
    assert warning is not None
    assert "SIGMA_CLOUD_ADMIN_CONTACT_EMAIL" in warning
    assert "administrator access is unavailable" in warning
    assert "server-secret" not in warning
    with patch.dict(
        "os.environ",
        {
            "GOOGLE_OIDC_CLIENT_ID": "client-id",
            "GOOGLE_OIDC_CLIENT_SECRET": "server-secret",
            "SIGMA_CLOUD_ADMIN_CONTACT_EMAIL": "owner@gmail.com",
        },
        clear=True,
    ):
        assert local_google_configuration_warning() is None


def check_partial_google_startup_remains_guest_without_admin() -> None:
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
                "SIGMA_CLOUD_ADMIN_CONTACT_EMAIL": "",
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
    assert "SIGMA_CLOUD_ADMIN_CONTACT_EMAIL" in warning_output.getvalue()
    assert "administrator access is unavailable" in warning_output.getvalue()
    backend_env = launch.call_args_list[0].kwargs["env"]
    assert backend_env["SIGMA_CLOUD_AUTH_ENABLED"] == "true"
    assert backend_env["SIGMA_CLOUD_AUTH_LOCAL"] == "true"
    assert backend_env["SIGMA_LOCAL_AUTO_ADMIN"] == "false"
    assert backend_env["SIGMA_CLOUD_ADMIN_CONTACT_EMAIL"] == ""
    assert backend_env["GOOGLE_OIDC_CLIENT_SECRET"] == "server-secret"
    frontend_env = launch.call_args_list[1].kwargs["env"]
    assert "GOOGLE_OIDC_CLIENT_SECRET" not in frontend_env


def check_signin_without_admin_contact_fails_before_launch() -> None:
    error_output = StringIO()
    with (
        patch.dict("os.environ", {}, clear=True),
        patch("sigma.ui.load_local_config"),
        patch("pathlib.Path.is_dir", return_value=True),
        patch("sigma.ui.shutil.which", return_value="npm"),
        patch("sigma.ui.Instance") as instance,
        patch("sigma.ui.subprocess.Popen") as launch,
        redirect_stderr(error_output),
    ):
        assert run_ui(signin=True) == 2
    assert "Cannot start SIGMA with --signin." in error_output.getvalue()
    assert "SIGMA_CLOUD_ADMIN_CONTACT_EMAIL is not configured." in error_output.getvalue()
    instance.assert_not_called()
    launch.assert_not_called()


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


def check_browser_pdf_ci_distribution() -> None:
    """Keep every browser suite and the mandatory real-PDF gate during rebalancing."""
    browser_workflow = (ROOT / ".github/workflows/browser-verification.yml").read_text(
        encoding="utf-8"
    )
    assert "group: ['1', '2', '3']" in browser_workflow
    assert "Browser acceptance (${{ matrix.group }}/3)" in browser_workflow
    assert "Require all three browser groups to pass" in browser_workflow
    assert "needs: browser" in browser_workflow
    assert "matrix.group == '3'" in browser_workflow
    scripts = (
        "issue525_project_diagnostics.py",
        "guest_samples.py",
        "t47_conclusion.py",
        "project_types_436.py",
        "project_email.py",
        "collaboration_settings.py",
        "collaboration_local_accounts.py",
        "research_qa.py",
        "model_availability.py",
        "t201_overflow.py",
        "t81_public_legal_pages.py",
        "t92_recent_running.py",
        "save_as_contract.py",
    )
    for filename in scripts:
        assert browser_workflow.count(f"python browser_checks/{filename}") == 1, filename
    # Both evidence uploads must include third-group collaboration output.
    assert browser_workflow.count("            /tmp/collaboration-local-accounts.log") == 2
    assert "pipefail" in browser_workflow

    pdf_workflow = (ROOT / ".github/workflows/verify.yml").read_text(encoding="utf-8")
    assert "Two-creator real PDF acceptance" in pdf_workflow
    assert 'SIGMA_REQUIRE_REAL_PAPER_PDF: "1"' in pdf_workflow
    assert "SIGMA_SETUP_SKIP_NPM=1 ./sigma setup" in pdf_workflow
    assert (
        "uv run --locked --no-sync python tests/paper_collaboration_acceptance.py" in pdf_workflow
    )
    assert "sha256sum --check --strict" in pdf_workflow


def main() -> None:
    output = StringIO()
    with redirect_stdout(output), redirect_stderr(output):
        check_failures()
        check_browser_pdf_ci_distribution()
        check_start_cli()
        check_command_help()
        check_ui()
        check_local_google_startup()
        check_sponsored_local_startup()
        check_local_google_setup_warning()
        check_partial_google_startup_remains_guest_without_admin()
        check_signin_without_admin_contact_fails_before_launch()
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
