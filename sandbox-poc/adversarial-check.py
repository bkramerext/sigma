"""Attack the real container boundary and crash/cancellation evidence contract.

Only the fixed SIGMA service runs on the host; all research snippets are sent
to Docker. No provider requests, network dependencies or host code fallback.
"""

from __future__ import annotations

import asyncio
import base64
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from sigma import python_sandbox as sandbox
from sigma import research_sessions
from sigma.projects import create_strategy, initialize_project


def containers() -> set[str]:
    result = subprocess.run(
        ["docker", "ps", "-aq", "--filter", f"ancestor={sandbox.IMAGE}"],
        capture_output=True,
        text=True,
        check=True,
        timeout=5,
    )
    return set(result.stdout.split())


async def run_checks(root: Path) -> None:
    path = root / "adversarial.sigma"
    initialize_project(
        path, "Adversarial sandbox evaluation", "Retain truthful computational evidence"
    )
    for name, expression in {
        "symlink": "Path('/artifacts/link').symlink_to('/etc/passwd')",
        "fifo": "os.mkfifo('/artifacts/fifo')",
        "nested": "Path('/artifacts/nested').mkdir(); Path('/artifacts/nested/data').write_text('x')",
        "oversize": "Path('/artifacts/large').write_bytes(b'x'*4_000_001)",
        "too-many": "[Path('/artifacts/'+str(i)).write_text('x') for i in range(9)]",
        "invalid-name": "open(b'/artifacts/\\xff','wb').write(b'x')",
    }.items():
        code = (
            "from pathlib import Path\nimport os,sys\nprint('MEASURED=42')\nprint('ORIGINAL_DIAGNOSTIC',file=sys.stderr)\n"
            + expression
        )
        record = await sandbox.execute_research_code(path, code)
        assert record["status"] == "failed" and record["artifact_error"], record
        assert "MEASURED=42" in record["stdout"] and "ORIGINAL_DIAGNOSTIC" in record["stderr"], (
            record
        )
        assert record["artifacts"] == [] and sandbox.get_execution(path, record["id"]) == record
        print("PASS artifact rejection preserves both program streams:", name, flush=True)
    for byte in ("00", "ff"):
        code = f"import os; os.write(1,bytes.fromhex('{byte}')*32000)"
        record = await sandbox.execute_research_code(path, code)
        assert record["status"] == "completed" and len(record["stdout"]) == 32000, record
        assert sandbox.get_execution(path, record["id"]) == record
        if byte == "ff":
            assert base64.b64decode(record["stdout_base64"]) == b"\xff" * 32000
        print("PASS JSON expansion / exact non-UTF-8 evidence:", byte, flush=True)
    privacy = await sandbox.execute_research_code(
        path,
        """from pathlib import Path
import os
assert 'SIGMA_SANDBOX_HOST_SENTINEL' not in os.environ
assert not Path('/var/run/docker.sock').exists()
assert not Path('/Users/admin/sigma_green').exists()
print('NO_HOST_FILES_OR_CREDENTIALS')
""",
    )
    assert privacy["status"] == "completed", privacy
    processes = await sandbox.execute_research_code(
        path,
        """import subprocess,sys,json
children=[]
try:
    try:
        for _ in range(128):
            children.append(subprocess.Popen([sys.executable,'-c','import time;time.sleep(20)']))
    except OSError as e:
        assert e.errno==11
    else:
        raise AssertionError('Process limit was not enforced')
    print(json.dumps({'children':len(children),'process_limit_enforced':True}))
finally:
    for child in children: child.kill()
    for child in children: child.wait()
""",
    )
    assert (
        processes["status"] == "completed" and json.loads(processes["stdout"])["children"] < 64
    ), processes
    print("PASS process exhaustion and cleanup:", processes["stdout"].strip(), flush=True)
    disk = await sandbox.execute_research_code(
        path,
        """import errno
try:
    with open('/tmp/fill','wb') as output:
        for _ in range(80): output.write(b'x'*1024*1024)
except OSError as e:
    assert e.errno==errno.ENOSPC
    print('TMPFS_LIMIT_ENFORCED')
else:
    raise AssertionError('tmpfs size bound was not enforced')
""",
    )
    assert disk["status"] == "completed" and "TMPFS_LIMIT_ENFORCED" in disk["stdout"], disk
    print("PASS tmpfs exhaustion without host disk access", flush=True)
    code = "import time; time.sleep(1); print('FIRST_COMPLETED')"
    first = asyncio.create_task(sandbox.execute_research_code(path, code))
    for _ in range(100):
        if any(item["status"] == "running" for item in sandbox.list_executions(path)):
            await asyncio.sleep(0.1)
            break
        await asyncio.sleep(0.01)
    busy = await sandbox.execute_research_code(path, "print('SECOND')")
    assert busy["status"] == "busy", busy
    assert (await first)["status"] == "completed"
    print("PASS concurrent admission captures busy status", flush=True)
    code = "import time; time.sleep(1); print('DURABLE_AFTER_CANCEL')"
    task = asyncio.create_task(sandbox.execute_research_code(path, code))
    await asyncio.sleep(0.2)
    task.cancel()
    await asyncio.sleep(0.05)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    else:
        raise AssertionError("Cancellation must propagate after persistence")
    record = next(item for item in sandbox.list_executions(path) if item["source"] == code)
    assert record["status"] == "completed" and "DURABLE_AFTER_CANCEL" in record["stdout"], record
    print("PASS repeated cancellation preserves a terminal record", flush=True)


def crash_check(root: Path) -> None:
    path = root / "backend-crash.sigma"
    view = initialize_project(
        path, "Backend crash evaluation", "Do not silently rerun uncertain experiments"
    )
    strategy = create_strategy(
        path, "Crash witness", "Retain the exact proposal and uncertain execution state."
    ).project.strategies[0]
    session_id = str(uuid4())
    research_sessions._save(
        str(path),
        {
            "id": session_id,
            "project_path": str(path.resolve()),
            "project_id": view.project.id,
            "status": "running",
            "strategy_runs": [{"strategy_id": strategy.id, "cycle": 1}],
            "steps": [],
            "events": [],
        },
    )
    code = "import subprocess,sys; subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)'],start_new_session=True)"
    wrapper = "import asyncio,sys;from sigma.python_sandbox import execute_research_code;asyncio.run(execute_research_code(sys.argv[1],sys.argv[2],session_id=sys.argv[3],strategy_id=sys.argv[4],cycle=1))"
    before = containers()
    child = subprocess.Popen(
        [sys.executable, "-c", wrapper, str(path), code, session_id, strategy.id],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        deadline = time.monotonic() + 10
        new = set()
        while time.monotonic() < deadline:
            new = containers() - before
            if new:
                break
            time.sleep(0.05)
        assert len(new) == 1, "The test container did not start"
        assert sandbox.list_executions(path)[0]["status"] == "running"
        os.kill(child.pid, signal.SIGKILL)
        child.wait(timeout=5)
        records = sandbox.list_executions(path)
        assert len(records) == 1 and records[0]["status"] == "interrupted", records
        saved = asyncio.run(
            sandbox.execute_research_code(
                path, code, session_id=session_id, strategy_id=strategy.id, cycle=1
            )
        )
        assert saved["id"] == records[0]["id"] and saved["status"] == "interrupted"
        deadline = time.monotonic() + 25
        while containers() & new and time.monotonic() < deadline:
            time.sleep(0.2)
        assert not containers() & new, (
            "Detached descendants or their container survived the watchdog"
        )
        print(
            "PASS SIGKILL backend, detached descendant watchdog, automatic container removal and no duplicate after restart",
            flush=True,
        )
    finally:
        if child.poll() is None:
            child.kill()
            child.wait()


def main() -> None:
    before = containers()
    os.environ["SIGMA_SANDBOX_HOST_SENTINEL"] = "must-not-enter-container"
    with TemporaryDirectory(prefix="sigma-adversarial-") as temporary:
        root = Path(temporary)
        asyncio.run(run_checks(root))
        crash_check(root)
    assert containers() == before, "Research containers leaked during adversarial tests"
    print("PASS actual Docker adversarial suite; no new running or stopped containers remain")


if __name__ == "__main__":
    main()
