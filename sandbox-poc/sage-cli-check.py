"""Opt-in actual Sage execution through SIGMA's public CLI."""

import json
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

from sigma.projects import ROOT, initialize_project

with TemporaryDirectory(prefix="sigma-sage-cli-") as temporary:
    path = Path(temporary) / "cli.sigma"
    initialize_project(path, "Sage CLI", "Inspect exact arithmetic through the public CLI")
    source = Path(temporary) / "experiment.sage"
    source.write_text("R.<x> = PolynomialRing(QQ)\nprint(factor(x^4 - 1))\nprint(2^3)\n")
    result = subprocess.run(
        [
            str(ROOT / "sigma"),
            "sandbox-execute",
            str(path),
            "--runtime",
            "sagemath",
            "--source-file",
            str(source),
        ],
        capture_output=True,
        text=True,
        timeout=75,
        cwd=ROOT,
    )
    assert result.returncode == 0, (result.stdout, result.stderr)
    record = json.loads(result.stdout)
    assert record["runtime"] == "sagemath" and record["runtime_version"] == "10.8"
    assert record["source"] == source.read_text() and record["agent"] is None
    assert record["stdout"] == "(x - 1) * (x + 1) * (x^2 + 1)\n8\n"
    print(
        json.dumps(
            {
                "result": "PASS real Sage CLI",
                "duration_ms": record["duration_ms"],
                "image_id": record["environment"]["image_id"],
            }
        ),
        flush=True,
    )
