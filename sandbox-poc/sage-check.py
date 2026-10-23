"""Explicit opt-in real Sage container checks; never called by ordinary sigma test."""

import asyncio
import json
import time
from pathlib import Path
from tempfile import TemporaryDirectory

from sigma import python_sandbox
from sigma.projects import initialize_project

SOURCE = """from pathlib import Path
import os, json, socket
from sage.version import version
assert version == '10.8', version
assert os.geteuid() == 65532
status = dict(line.split(':', 1) for line in Path('/proc/self/status').read_text().splitlines() if ':' in line)
assert status['CapEff'].strip() == '0000000000000000'
assert status['NoNewPrivs'].strip() == '1'
assert Path('/sys/fs/cgroup/memory.max').read_text().strip() == '1073741824'
assert Path('/sys/fs/cgroup/pids.max').read_text().strip() == '64'
assert Path('/sys/fs/cgroup/cpu.max').read_text().strip() == '100000 100000'
try:
    Path('/work/escape').write_text('bad')
except OSError:
    pass
else:
    raise AssertionError('root filesystem is writable')
assert not Path('/Users/admin').exists()
try:
    socket.create_connection(('1.1.1.1', 443), timeout=2)
except OSError:
    pass
else:
    raise AssertionError('network available')
R.<x> = PolynomialRing(QQ)
f = x^4 - 1
assert prod(factor(f)) == f
assert 1/3 == QQ(1)/QQ(3) and 2^3 == 8
assert factor(2026) == factor(2*1013)
assert (inverse_mod(37, 101)*37) % 101 == 1
E = EllipticCurve(GF(101), [2,3])
independent = 1 + sum(1 for a in range(101) for b in range(101) if (b*b-a*a*a-2*a-3) % 101 == 0)
assert E.cardinality() == independent
pseudoprimes = [int(n) for n in srange(3,1000,2) if not is_prime(n) and power_mod(2,n-1,n)==1]
assert 341 in pseudoprimes and factor(341) == factor(11*31)
t = var('t')
plot(t^2, (t,-1,1)).save('/artifacts/quadratic.png')
Path('/artifacts/results.json').write_text(json.dumps({'pseudoprimes': pseudoprimes, 'elliptic_curve_points': int(E.cardinality()), 'version': version}))
print('NATIVE_SAGE_OK; exact counterexample 341=11*31; Fermat base-2 is not a primality certificate')
print('ISOLATION_NETWORK_AND_FINITE_CHECKS_OK')
"""


def run(source, expected):
    started = time.monotonic()
    result = python_sandbox._execute(source, "sagemath")
    print(
        json.dumps(
            {
                "status": result.status,
                "expected": expected,
                "duration_ms": result.duration_ms,
                "elapsed": round(time.monotonic() - started, 2),
                "stderr": result.stderr[-300:],
            },
            ensure_ascii=False,
        ),
        flush=True,
    )
    assert result.status == expected, result
    return result


async def cancelled_run(path):
    task = asyncio.create_task(
        python_sandbox.execute_research_code(
            path, "print('BOUNDED_CANCELLATION_SAVED')", runtime_name="sagemath"
        )
    )
    for _ in range(100):
        if python_sandbox.list_executions(path):
            break
        await asyncio.sleep(0.02)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    else:
        raise AssertionError("Caller cancellation not preserved")
    saved = python_sandbox.list_executions(path)[0]
    assert saved["status"] == "completed" and "BOUNDED_CANCELLATION_SAVED" in saved["stdout"], saved
    assert not list((path / "research-executions").glob("*.active"))
    print(
        "PASS cancelled caller waited for bounded cleanup; exact completed evidence persisted",
        flush=True,
    )


def main():
    with TemporaryDirectory() as temporary:
        path = Path(temporary) / "sage-experiments.sigma"
        initialize_project(
            path,
            "Sage exact investigations",
            "Find exact counterexamples and inspect finite algebraic evidence",
        )
        saved = asyncio.run(
            python_sandbox.execute_research_code(path, SOURCE, runtime_name="sagemath")
        )
        assert saved["status"] == "completed", saved
        print(
            json.dumps(
                {
                    "experiment": "algebra/number theory/plot/isolation",
                    "duration_ms": saved["duration_ms"],
                    "image_id": saved["environment"]["image_id"],
                    "stdout": saved["stdout"],
                }
            ),
            flush=True,
        )
        files = {item["filename"]: item for item in saved["artifacts"]}
        assert set(files) == {"results.json", "quadratic.png"}
        content, _ = python_sandbox.get_execution_artifact(path, saved["id"], "results.json")
        assert 341 in json.loads(content)["pseudoprimes"]
        png, media = python_sandbox.get_execution_artifact(path, saved["id"], "quadratic.png")
        assert media == "image/png" and png.startswith(b"\x89PNG\r\n\x1a\n")
        assert python_sandbox.get_execution(path, saved["id"]) == saved
        cancel_path = Path(temporary) / "cancel.sigma"
        initialize_project(
            cancel_path, "Sage cancellation", "Retain exact status during cancellation"
        )
        asyncio.run(cancelled_run(cancel_path))
    run("raise ValueError('deliberate Sage failure')", "failed")
    unsafe = run("import os; os.symlink('/etc/passwd', '/artifacts/escape')", "failed")
    assert unsafe.artifact_error and not unsafe.artifacts
    overflow = run("print('x' * 1000000)", "output_limit")
    assert len(overflow.stdout.encode()) + len(overflow.stderr.encode()) <= 32000
    run("data = bytearray(2 * 1024 * 1024 * 1024); print(len(data))", "failed")
    run("while True: pass", "timeout")
    print(
        "PASS real Sage symbolic/number-theory/artifact/isolation/network/error/output/memory/timeout/cancellation checks",
        flush=True,
    )


if __name__ == "__main__":
    main()
