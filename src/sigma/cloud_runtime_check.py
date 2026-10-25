"""Opt-in Python/Sage, isolation, TeX, and artifact-integrity smoke check.

Run on a host that can access the dedicated rootless Docker socket. The
--allow-nonrootless-dev option is for local Docker Desktop/Colima validation;
GCE acceptance must omit it.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path
from uuid import uuid4

from sigma import papers, python_sandbox
from sigma.projects import initialize_project


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--allow-nonrootless-dev",
        action="store_true",
        help="Permit local Docker Desktop/Colima; this does not verify the GCE daemon boundary.",
    )
    args = parser.parse_args()
    info = subprocess.run(
        ["docker", "info", "--format", "{{json .SecurityOptions}}"],
        check=True,
        capture_output=True,
        text=True,
        timeout=15,
        env=python_sandbox._runtime_environment(),
    )
    security_options = json.loads(info.stdout)
    rootless = any("rootless" in item.casefold() for item in security_options)
    if not rootless and not args.allow_nonrootless_dev:
        raise SystemExit(
            "FAIL: selected Docker daemon does not report rootless mode; use the dedicated "
            "sigma-sandbox socket (local desktop validation requires --allow-nonrootless-dev)."
        )

    with tempfile.TemporaryDirectory(prefix="sigma-cloud-runtime-") as temporary:
        root = Path(temporary)
        project = root / "runtime.sigma"
        secret = root / "host-secret.txt"
        secret.write_text("host-only sentinel; never expose to a sandbox\n", encoding="utf-8")
        project_view = initialize_project(
            project, "Runtime acceptance", "Verify Python, SageMath and PDF artifacts"
        )

        probe = f"""import json, os, pathlib, socket
checks = {{"uid": os.getuid()}}
try:
    pathlib.Path({str(secret)!r}).read_text()
    checks["host_secret"] = "readable"
except (OSError, PermissionError):
    checks["host_secret"] = "blocked"
try:
    socket.create_connection(("1.1.1.1", 53), timeout=1).close()
    checks["network"] = "reachable"
except OSError:
    checks["network"] = "blocked"
pathlib.Path("/artifacts/runtime-evidence.json").write_text(json.dumps(checks, sort_keys=True))
print(json.dumps(checks, sort_keys=True))
"""
        results = {}
        for runtime in ("python", "sagemath"):
            record = asyncio.run(
                python_sandbox.execute_research_code(
                    project,
                    probe,
                    runtime_name=runtime,
                )
            )
            if record["status"] != "completed" or record["exit_code"] != 0:
                raise AssertionError(f"{runtime} did not complete: {record}")
            observations = json.loads(record["stdout"])
            if observations != {"uid": 65532, "host_secret": "blocked", "network": "blocked"}:
                raise AssertionError(f"{runtime} isolation probe failed: {observations}")
            evidence, _mime = python_sandbox.get_execution_artifact(
                project, record["id"], "runtime-evidence.json"
            )
            if json.loads(evidence) != observations:
                raise AssertionError(f"{runtime} evidence artifact did not round-trip")
            saved = python_sandbox.get_execution(project, record["id"])
            if saved["source"] != probe or saved["status"] != "completed":
                raise AssertionError(f"{runtime} execution provenance was not preserved")
            results[runtime] = {
                "execution_id": record["id"],
                "image_id": record["environment"]["image_id"],
                "isolation": observations,
                "captured_artifact": "runtime-evidence.json",
            }

        tex = r"""\documentclass{article}
\usepackage[T1]{fontenc}
\begin{document}
SIGMA cloud runtime acceptance. Exact arithmetic: $1+2+3=6$.
\end{document}
"""
        pdf = papers._compile_pdf(tex, timeout_seconds=90)
        if not pdf.startswith(b"%PDF-"):
            raise AssertionError("Tectonic did not produce a PDF")
        snapshot, snapshot_sha256 = papers._snapshot(str(project))
        identifier = uuid4().hex
        record = {
            "schema_version": 1,
            "paper_id": identifier,
            "project_id": project_view.project.id,
            "created_at": "2026-10-25T00:00:00+00:00",
            "snapshot_sha256": snapshot_sha256,
            "snapshot": snapshot,
            "draft": {"title": "Runtime acceptance"},
            "tex_source": tex,
            "validation_warnings": [],
            "obligation_reconciliation": [],
            "author_review_warnings": [],
            "generation": {"provider_calls_attempted": 0, "long_form": False},
        }
        papers._save(str(project), record, pdf)
        saved_paper = papers.get_paper(str(project), identifier)
        saved_pdf = papers.get_pdf(str(project), identifier)
        saved_snapshot_sha256 = hashlib.sha256(papers._json(saved_paper["snapshot"])).hexdigest()
        if (
            saved_paper["tex_source"] != tex
            or saved_paper["snapshot"] != snapshot
            or saved_paper["snapshot_sha256"] != snapshot_sha256
            or saved_snapshot_sha256 != saved_paper["snapshot_sha256"]
            or saved_pdf != pdf
            or not saved_paper["pdf_available"]
        ):
            raise AssertionError("TeX, evidence snapshot, or PDF did not persist intact")
        results["paper"] = {
            "paper_id": identifier,
            "snapshot_sha256": saved_snapshot_sha256,
            "snapshot_integrity_verified": True,
            "tex_bytes": len(tex.encode()),
            "pdf_bytes": len(pdf),
            "pdf_sha256": hashlib.sha256(pdf).hexdigest(),
            "persisted": True,
        }
        print(json.dumps({"result": "PASS", "daemon_rootless": rootless, **results}, indent=2))


if __name__ == "__main__":
    main()
