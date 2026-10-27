"""T249 reproducible verification: run locally, commit and push a diagnostic report.

Run from the SIGMA checkout on fix/t249-single-file-projects:
    python3 scripts/t249_verify.py
Only docs/evaluations/t249/local-verification.json is staged by this script.
"""
from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path
import subprocess
import sys
import time

BRANCH = "fix/t249-single-file-projects"
REPORT = Path("docs/evaluations/t249/local-verification.json")


def command(argv: list[str], *, timeout: int = 180, env: dict[str, str] | None = None) -> dict:
    print(f"RUN {' '.join(argv)} (timeout {timeout}s)", flush=True)
    started = time.monotonic()
    try:
        result = subprocess.run(argv, capture_output=True, text=True, errors="replace",
                                timeout=timeout, env=env, check=False)
        print(f"DONE exit={result.returncode} elapsed={time.monotonic() - started:.1f}s", flush=True)
        return {"command": argv, "exit_code": result.returncode,
                "seconds": round(time.monotonic() - started, 2),
                "stdout": result.stdout[-24000:], "stderr": result.stderr[-24000:]}
    except subprocess.TimeoutExpired as exc:
        print(f"TIMEOUT after {timeout}s: {' '.join(argv)}", flush=True)
        return {"command": argv, "exit_code": None, "timed_out": True,
                "seconds": round(time.monotonic() - started, 2),
                "stdout": str(exc.stdout or "")[-24000:],
                "stderr": str(exc.stderr or "")[-24000:]}
    except OSError as exc:
        print(f"ERROR: {exc}", flush=True)
        return {"command": argv, "exit_code": None, "error": str(exc),
                "seconds": round(time.monotonic() - started, 2)}


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    os.chdir(root)
    branch = command(["git", "branch", "--show-current"])
    if branch["exit_code"] != 0 or branch["stdout"].strip() != BRANCH:
        print(f"Switch to {BRANCH} first. Current: {branch.get('stdout', '').strip()}", file=sys.stderr)
        return 2
    head = command(["git", "rev-parse", "HEAD"])
    status = command(["git", "status", "--porcelain"])
    env = os.environ.copy()
    env["PYTHONPATH"] = str(root / "src") + os.pathsep + env.get("PYTHONPATH", "")
    python = root / ".venv" / "bin" / "python"
    interpreter = str(python) if python.is_file() else sys.executable
    checks = {
        "compile": command([interpreter, "-m", "compileall", "-q", "src/sigma", "tests/project_bundle.py"], env=env),
        "bundle_simulation": command([interpreter, "tests/project_bundle.py"], timeout=300, env=env),
        "docker_info": command(["docker", "info", "--format", "{{json .ServerVersion}}"], timeout=20),
        "docker_images": command(["docker", "images", "--format", "{{.Repository}}:{{.Tag}}"], timeout=20),
    }
    checks["docker_lifecycle"] = command(
        [interpreter, "tests/t249_docker_lifecycle.py"], timeout=180, env=env
    )
    # Human-readable simulations are standalone Python programs. Select only
    # related suites, so unrelated provider/network tests do not obscure T249.
    candidates = sorted((root / "tests").glob("*.py"))
    names = ("project", "research_session", "python_sandbox", "execution", "bundle")
    for path in candidates:
        if path.name == "project_bundle.py" or not any(x in path.stem for x in names):
            continue
        checks["simulation:" + path.name] = command(
            [interpreter, str(path.relative_to(root))], timeout=240, env=env
        )
    report = {
        "ticket": "T249", "branch": BRANCH, "tested_head": head["stdout"].strip(),
        "utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "python": interpreter, "initial_git_status": status["stdout"],
        "checks": checks,
        "passing": [key for key, value in checks.items() if value.get("exit_code") == 0],
        "failing_or_unavailable": [key for key, value in checks.items() if value.get("exit_code") != 0],
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("Report:", REPORT)
    for key, result in checks.items():
        print(f"{key}: exit={result.get('exit_code')} duration={result.get('seconds')}s")
    # Stage only our own report; never stage or commit the user's other work.
    stage = command(["git", "add", "--", str(REPORT)])
    if stage["exit_code"] != 0:
        print("Could not stage report:", stage["stderr"], file=sys.stderr)
        return 3
    staged = command(["git", "diff", "--cached", "--name-only"])
    if staged["exit_code"] != 0 or any(
        name != str(REPORT) for name in staged["stdout"].splitlines()
    ):
        command(["git", "reset", "-q", "--", str(REPORT)])
        print("Other staged changes detected; report saved but not committed.", file=sys.stderr)
        return 4
    if staged["stdout"].strip():
        commit = command(["git", "commit", "-m", "test(t249): capture local verification results"])
        if commit["exit_code"] != 0:
            print("Report saved; commit failed:", commit["stderr"], file=sys.stderr)
            return 5
    push = command(["git", "push", "origin", f"HEAD:{BRANCH}"], timeout=90)
    if push["exit_code"] != 0:
        print("Report committed locally; push failed:", push["stderr"], file=sys.stderr)
        return 6
    print("Verification report pushed to", BRANCH)
    return 0 if not report["failing_or_unavailable"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
