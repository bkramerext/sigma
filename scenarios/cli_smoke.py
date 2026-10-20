"""Exercise the real CLI process and its JSON/exit-status contract in temporary storage."""

import json
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory


def cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "sigma.cli", *args], capture_output=True, text=True, check=False
    )


def main() -> None:
    with TemporaryDirectory() as directory:
        path = str(Path(directory) / "cli.sigma")
        result = cli("init", path, "--title", "CLI question", "--problem", "Investigate")
        assert result.returncode == 0, result.stderr
        identity = json.loads(result.stdout)["project"]["id"]
        before = (Path(path) / "project.json").read_bytes()
        for command in ("open", "inspect"):
            result = cli(command, path)
            assert result.returncode == 0, result.stderr
            assert json.loads(result.stdout)["project"]["id"] == identity
        result = cli("events", path)
        assert result.returncode == 0, result.stderr
        assert json.loads(result.stdout)["events"][0]["sequence"] == 1
        for args in (
            ("init", path, "--title", "Overwrite", "--problem", "No"),
            ("open", str(Path(directory) / "missing.sigma")),
        ):
            result = cli(*args)
            assert result.returncode == 2 and not result.stdout
            assert "error" in json.loads(result.stderr)
        assert (Path(path) / "project.json").read_bytes() == before
        result = cli("new-strategy", path, "--title", "Manual idea", "--approach", "Investigate it")
        assert result.returncode == 0, result.stderr
        strategy = json.loads(result.stdout)["project"]["strategies"][0]
        result = cli("strategies", path)
        assert result.returncode == 0 and json.loads(result.stdout)["strategies"] == [strategy]
        result = cli("open", path)
        assert json.loads(result.stdout)["project"]["strategies"][0]["id"] == strategy["id"]
        snapshot = (Path(path) / "project.json").read_bytes()
        result = cli("new-strategy", path, "--title", " ", "--approach", "Invalid")
        assert result.returncode == 2 and "error" in json.loads(result.stderr)
        assert (Path(path) / "project.json").read_bytes() == snapshot
        result = cli("close")
        assert result.returncode == 0 and json.loads(result.stdout) == {"closed": True}
    print("PASS CLI lifecycle, strategy create/list/reopen, JSON output and safe failure")


if __name__ == "__main__":
    main()
