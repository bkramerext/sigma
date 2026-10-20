"""Check maintenance failure handling without installing or changing dependencies."""

import subprocess
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from unittest.mock import patch

from sigma.projects import ROOT
from sigma.tooling import run_tooling


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


def main() -> None:
    output = StringIO()
    with redirect_stdout(output), redirect_stderr(output):
        check_failures()
    for message in ("Missing prerequisite", "exit 7", "Could not start"):
        assert message in output.getvalue()
    print("PASS missing prerequisites, failed process status, fail-fast and launch errors")


if __name__ == "__main__":
    main()
