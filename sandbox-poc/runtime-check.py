"""Exercise the built image through SIGMA's production adapter."""

import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory

from sigma.projects import initialize_project
from sigma.python_sandbox import (
    _execute,
    execute_research_code,
    get_execution,
    get_execution_artifact,
)


def main() -> None:
    boundary = _execute(
        """from pathlib import Path
import os
assert os.geteuid() == 65532
status = dict(line.split(':', 1) for line in Path('/proc/self/status').read_text().splitlines() if ':' in line)
assert status['CapEff'].strip() == '0000000000000000'
assert status['NoNewPrivs'].strip() == '1'
assert Path('/sys/fs/cgroup/memory.max').read_text().strip() == '536870912'
assert Path('/sys/fs/cgroup/pids.max').read_text().strip() == '64'
assert Path('/sys/fs/cgroup/cpu.max').read_text().strip() == '100000 100000'
try:
    Path('/work/not-writable').write_text('x')
except OSError:
    print('ROOT_READ_ONLY')
else:
    raise SystemExit('ROOT_WRITABLE')
print('ISOLATION_BOUNDARY_OK')
"""
    )
    assert boundary.status == "completed", boundary
    assert "ISOLATION_BOUNDARY_OK" in boundary.stdout
    research_source = """import numpy as np
import pandas as pd
import sympy as sp
import matplotlib.pyplot as plt
from scipy.integrate import quad
from scipy.optimize import brentq

# A small concrete research task: find the region count from 12 lines in
# general position, and check the insertion argument on an explicit family.
counts = [1]
for n in range(1, 13):
    xs = [-(n + j) for j in range(n - 1)]
    assert len(set(xs)) == n - 1, 'new line has a repeated intersection'
    counts.append(counts[-1] + n)
assert counts[-1] == 79

# Exact symbolic and numerical checks used by a researcher.
n = sp.symbols('n', integer=True, nonnegative=True)
assert sp.simplify(1 + sp.summation(sp.Symbol('k'), (sp.Symbol('k'), 1, n)) - (1 + n*(n+1)/2)) == 0
assert abs(quad(lambda x: x*x, 0, 1)[0] - 1/3) < 1e-12
assert abs(brentq(lambda x: x*x - 2, 1, 2) - 2**0.5) < 1e-10
matrix = np.array([[3.0, 1.0], [1.0, 2.0]])
solution = np.linalg.solve(matrix, np.array([9.0, 8.0]))
assert np.linalg.norm(matrix @ solution - [9.0, 8.0]) < 1e-12
table = pd.DataFrame({'n': range(13), 'observed': counts})
table['formula'] = 1 + table.n * (table.n + 1) // 2
assert (table.observed == table.formula).all()
fig, ax = plt.subplots()
ax.plot(table.n, table.observed, 'o-', label='enumerated insertion counts')
ax.plot(table.n, table.formula, '--', label='1 + n(n+1)/2')
ax.set(xlabel='number of lines', ylabel='regions', title='Finite check of the line insertion formula')
ax.legend()
fig.savefig('/artifacts/regions-check.png')
print('ANSWER: 79 regions for 12 lines in general position')
print('FINITE_CASES:', table.to_json(orient='records'))
print('NUMPY_SCIPY_PANDAS_SYMPY_MATPLOTLIB_OK')
"""
    scientific = _execute(research_source)
    assert scientific.status == "completed", scientific
    assert "ANSWER: 79 regions" in scientific.stdout
    assert "NUMPY_SCIPY_PANDAS_SYMPY_MATPLOTLIB_OK" in scientific.stdout
    assert [item[0] for item in scientific.artifacts] == ["regions-check.png"], scientific
    assert scientific.artifacts[0][1] == "image/png"
    assert scientific.artifacts[0][2].startswith(b"\x89PNG\r\n\x1a\n")
    no_network = _execute(
        """import socket
try:
    socket.create_connection(('1.1.1.1', 443), timeout=2)
except OSError:
    print('NETWORK_BLOCKED')
else:
    raise SystemExit('NETWORK_AVAILABLE')
"""
    )
    assert no_network.status == "completed", no_network
    assert "NETWORK_BLOCKED" in no_network.stdout
    over_output = _execute("print('x' * 1000000)")
    assert over_output.status == "output_limit", over_output.status
    assert len(over_output.stdout.encode()) + len(over_output.stderr.encode()) <= 32_000
    memory = _execute("data = bytearray(768 * 1024 * 1024)\nprint(len(data))")
    assert memory.status == "failed", memory
    timeout = _execute("while True: pass")
    assert timeout.status == "timeout", timeout.status
    assert timeout.duration_ms < 25_000, timeout.duration_ms
    with TemporaryDirectory() as temporary:
        project = Path(temporary) / "line-count-research.sigma"
        initialize_project(
            project,
            "Regions formed by lines: finite checks",
            "Compute regions added by inserting lines in general position and inspect cases through n=12.",
        )
        saved = asyncio.run(
            execute_research_code(
                str(project),
                research_source,
                session_id="f7b95c68-af09-49d6-9b6f-3454bdfd1d93",
                strategy_id="977c41d9-208f-4657-a2af-4fc5a32042b0",
                cycle=1,
            )
        )
        assert saved["status"] == "completed", saved
        assert "ANSWER: 79 regions" in saved["stdout"] and saved["environment"]["image_id"]
        assert saved["artifacts"][0]["filename"] == "regions-check.png"
        assert get_execution(str(project), saved["id"]) == saved
        png, media_type = get_execution_artifact(str(project), saved["id"], "regions-check.png")
        assert media_type == "image/png" and png.startswith(b"\x89PNG\r\n\x1a\n")
    print(
        "PASS actual Docker imports the scientific stack, denies network, enforces memory/output/time limits, and persists execution artifacts"
    )


if __name__ == "__main__":
    main()
