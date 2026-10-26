#!/usr/bin/env python3
"""PR #257 local verification. Executes offline checks and publishes only its JSON report."""
from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
REPORT = Path("docs/evaluations/t257/local-verification.json")
BRANCH = "feature/local-mock-auth-walkthrough"


def run(name, argv, *, timeout=240, env=None, cwd=ROOT):
    started = time.monotonic()
    try:
        p = subprocess.run(argv, cwd=cwd, capture_output=True, text=True,
                           timeout=timeout, env=env, check=False)
        return {"name": name, "status": "passed" if p.returncode == 0 else "failed",
                "exit_code": p.returncode, "stdout": p.stdout[-30000:],
                "stderr": p.stderr[-30000:], "traceback": None,
                "duration_seconds": round(time.monotonic()-started, 3),
                "command": argv}
    except Exception:
        return {"name": name, "status": "error", "exit_code": None,
                "stdout": "", "stderr": "", "traceback": traceback.format_exc(),
                "duration_seconds": round(time.monotonic()-started, 3),
                "command": argv}


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, text=True,
                          capture_output=True, check=False)


def python_for_tests():
    for candidate in (ROOT / ".venv" / "bin" / "python",
                      ROOT / "venv" / "bin" / "python"):
        if candidate.is_file():
            return str(candidate)
    return sys.executable


def main():
    sha = git("rev-parse", "HEAD").stdout.strip()
    branch = git("branch", "--show-current").stdout.strip()
    report = {"ticket": "T257", "branch": branch, "tested_commit_sha": sha,
              "started_at": dt.datetime.now(dt.timezone.utc).isoformat(),
              "checks": [], "publication": {}}
    if branch != BRANCH:
        report["checks"].append({"name": "branch guard", "status": "failed",
            "stderr": f"Expected {BRANCH}, found {branch}", "stdout": "",
            "traceback": None, "duration_seconds": 0})
    else:
        env = os.environ.copy()
        env.update({"PYTHONPATH": str(ROOT / "src"), "SIGMA_MOCK_AUTH": "0",
                    "SIGMA_CLOUD_AUTH_ENABLED": "false"})
        python = python_for_tests()
        report["python_executable"] = python
        report["checks"].append(run("Python syntax",
            [python, "-m", "compileall", "-q", "src/sigma", "tests/cloud_auth.py"],
            env=env))
        dependencies = run("Python dependencies", [python, "-c",
            "import httpx, fastapi, pydantic"], env=env)
        report["checks"].append(dependencies)
        if dependencies["status"] == "passed":
            report["checks"].append(run("Cloud authentication and mock integration",
            [python, "tests/cloud_auth.py"], timeout=420, env=env))
            report["checks"].append(run("Research session simulation",
            [python, "tests/research_sessions.py"], timeout=420, env=env))
        else:
            for name in ("Cloud authentication and mock integration", "Research session simulation"):
                report["checks"].append({"name": name, "status": "unavailable",
                    "stderr": "Missing Python dependencies in " + python,
                    "stdout": "", "traceback": None, "duration_seconds": 0})
        if (ROOT / "frontend" / "node_modules").is_dir():
            report["checks"].append(run("Frontend build", ["npm", "run", "build"],
                timeout=420, env=env | {"CI": "true"}, cwd=ROOT / "frontend"))
        else:
            report["checks"].append({"name": "Frontend build", "status": "unavailable",
                "stderr": "frontend/node_modules missing; install dependencies before retry",
                "stdout": "", "traceback": None, "duration_seconds": 0})
    report["finished_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
    report["summary"] = {k: sum(c["status"] == k for c in report["checks"])
                         for k in ("passed", "failed", "error", "unavailable")}
    dest = ROOT / REPORT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(report, indent=2) + "\n")
    # Stage only the harness-owned report. Never use git add -A or commit -a.
    add = git("add", "--", str(REPORT))
    if add.returncode != 0:
        print("Could not stage report:", add.stderr, file=sys.stderr)
        return 2
    staged = git("diff", "--cached", "--name-only").stdout.splitlines()
    if staged != [str(REPORT)]:
        # Do not unstage the user's pre-existing staged changes.
        print("Report saved but NOT committed: unrelated staged changes:", staged,
              file=sys.stderr)
        return 2
    commit = git("commit", "-m", f"test(t257): local verification report for {sha[:12]}", "--", str(REPORT))
    if commit.returncode != 0:
        print("Report saved; commit failed:", commit.stderr, file=sys.stderr)
        return 2
    push = git("push", "origin", f"HEAD:{BRANCH}")
    if push.returncode != 0:
        print("Report committed locally; push failed:", push.stderr, file=sys.stderr)
        return 2
    print(json.dumps({"tested_commit_sha": sha, "summary": report["summary"],
                      "report": str(REPORT), "pushed": True}, indent=2))
    return 1 if any(c["status"] != "passed" for c in report["checks"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
