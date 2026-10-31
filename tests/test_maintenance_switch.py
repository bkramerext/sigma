"""Unit tests for host-side maintenance switch; no host services required."""
import importlib.util
import pathlib
import subprocess
import sys
from unittest.mock import patch

MODULE = pathlib.Path(__file__).resolve().parents[1] / "deploy/maintenance/switch.py"
spec = importlib.util.spec_from_file_location("maintenance_switch", MODULE)
switch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(switch)


def test_on_off_and_failed_reload_restore(tmp_path):
    directory = tmp_path / "snippets"
    directory.mkdir()
    config = tmp_path / "Caddyfile"
    config.write_text("host config")
    snippet = directory / "active.caddy"
    with (
        patch.object(switch, "DIRECTORY", directory),
        patch.object(switch, "SNIPPET", snippet),
        patch.object(switch, "CONFIG", config),
        patch.object(switch.os, "geteuid", return_value=0),
        patch.object(pathlib.Path, "is_file", return_value=True),
    ):
        with patch.object(sys, "argv", ["switch.py", "on"]), patch.object(switch, "run") as run:
            switch.main()
            assert snippet.read_text() == switch.CONTENT
            assert run.call_count == 2
        with patch.object(sys, "argv", ["switch.py", "off"]), patch.object(switch, "run"):
            switch.main()
            assert not snippet.exists()
        with patch.object(sys, "argv", ["switch.py", "on"]), patch.object(switch, "run") as run:
            run.side_effect = [subprocess.CalledProcessError(1, "caddy"), None, None]
            try:
                switch.main()
            except subprocess.CalledProcessError:
                pass
            else:
                raise AssertionError("failed validation must be reported")
            assert not snippet.exists()
            assert run.call_count == 3
