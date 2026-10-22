"""Exercise the real CLI process and its JSON/exit-status contract in temporary storage."""

import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from sigma.agentic_evidence import save as save_agentic_evidence


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
        result = cli(
            "edit-strategy", path, strategy["id"], "--title", "Renamed", "--approach", "Updated"
        )
        assert result.returncode == 0, result.stderr
        assert json.loads(result.stdout)["project"]["strategies"][0]["title"] == "Renamed"
        result = cli("remove-strategy", path, strategy["id"])
        assert result.returncode == 0, result.stderr
        assert json.loads(cli("strategies", path).stdout) == {"strategies": []}
        reopened = json.loads(cli("open", path).stdout)["project"]
        assert reopened["strategies"][0]["title"] == "Renamed"
        assert reopened["events"][-1]["kind"] == "strategy.removed"
        assert cli("remove-strategy", path, strategy["id"]).returncode == 2
        run_id = "a" * 32
        save_agentic_evidence(
            path,
            {
                "schema_version": 1,
                "run_id": run_id,
                "started_at": datetime.now(UTC).isoformat(),
                "finished_at": datetime.now(UTC).isoformat(),
                "project_id": identity,
                "steps": [],
                "history": [],
                "timeline": [],
                "terminal": {"status": "stopped", "summary": "Fixture"},
            },
        )
        listed_runs = cli("agentic-runs", path)
        assert listed_runs.returncode == 0, listed_runs.stderr
        assert json.loads(listed_runs.stdout)["runs"][0]["run_id"] == run_id
        exported_run = cli("agentic-runs", path, run_id)
        assert exported_run.returncode == 0, exported_run.stderr
        assert json.loads(exported_run.stdout)["terminal"]["summary"] == "Fixture"
        result = cli("close")
        assert result.returncode == 0 and json.loads(result.stdout) == {"closed": True}
    print(
        "PASS CLI lifecycle, strategy create/edit/remove/list/reopen, agentic evidence list/export and safe failure"
    )


if __name__ == "__main__":
    main()
