"""One decisive, provider-free paper regression gate.

Expected fault-injection logs are saved locally, not mistaken for test failures.
Exit 0 only if all test subprocesses complete successfully; otherwise exit 1.
This is the *offline* gate, not the live paper-generation acceptance test.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path
from time import monotonic

ROOT = Path(__file__).resolve().parents[1]
TESTS = ROOT / "tests"
SHARDS = (
    ("platform-memory", TESTS / "platform_memory.py"),
    ("paper run isolation", TESTS / "paper_run_isolation.py"),
    ("two-creator Paper acceptance", TESTS / "paper_collaboration_acceptance.py"),
    ("papers 1/2", TESTS / "papers_part1.py"),
    ("papers 2/2", TESTS / "papers_part2.py"),
)
SHARD_TIMEOUT_SECONDS = 600


def main() -> int:
    checks: list[tuple[str, bool, str]] = []
    started = monotonic()
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        prefix="sigma-paper-preflight-",
        suffix=".log",
        delete=False,
    ) as log:
        path = Path(log.name)
        for name, script in SHARDS:
            began = monotonic()
            try:
                completed = subprocess.run(
                    [sys.executable, str(script)],
                    cwd=ROOT,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    timeout=SHARD_TIMEOUT_SECONDS,
                    check=False,
                )
                success = completed.returncode == 0
                output = completed.stdout
                detail = f"exit={completed.returncode}"
            except subprocess.TimeoutExpired as exc:
                success = False
                raw = exc.stdout or b""
                output = raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else raw
                detail = f"timeout>{SHARD_TIMEOUT_SECONDS}s"

            elapsed = monotonic() - began
            log.write(f"=== {name} ({detail}, {elapsed:.1f}s) ===\n{output}\n")
            log.flush()
            checks.append((name, success, output))
            print(f"{'PASS' if success else 'FAIL'} {name} ({elapsed:.1f}s)", flush=True)
            if not success:
                print(f"--- {name}: failure output (last 50 lines) ---", flush=True)
                for line in output.splitlines()[-50:]:
                    print(line, flush=True)

    if sys.platform != "linux":
        print(f"SKIP Linux-only native /proc and cgroup integration ({sys.platform})")
    passed = all(ok for _, ok, _ in checks)
    verdict = "GO" if passed else "NO-GO"
    print(
        f"{verdict}: offline paper regression "
        f"({sum(ok for _, ok, _ in checks)}/{len(checks)} suites passed, "
        f"{monotonic() - started:.1f}s)."
    )
    print(f"Full diagnostic log: {path}")
    if passed:
        print("Live Maximum Regions paper E2E remains a separate release gate.")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
