"""Exercise the built image through SIGMA's production adapter."""

import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory

from sigma.projects import initialize_project
from sigma.python_sandbox import _execute, execute_research_code, get_execution


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
    scientific = _execute(
        """import numpy, scipy, pandas, sympy, matplotlib
import matplotlib.pyplot as plt
from scipy.integrate import quad
import pandas as pd
import sympy as sp
assert round(quad(lambda x: x, 0, 2)[0], 8) == 2
assert float(sp.integrate(sp.Symbol('x'), (sp.Symbol('x'), 0, 2))) == 2
assert pd.DataFrame({'x': [1, 2]}).x.sum() == 3
plt.plot([0, 1], [0, 1])
print('NUMERICAL_STACK_OK')
"""
    )
    assert scientific.status == "completed", scientific
    assert "NUMERICAL_STACK_OK" in scientific.stdout
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
        project = Path(temporary) / "sandbox.sigma"
        initialize_project(project, "Sandbox runtime", "Capture one finite result")
        saved = asyncio.run(execute_research_code(str(project), "print('CAPTURED')", cycle=1))
        assert saved["status"] == "completed", saved
        assert "CAPTURED" in saved["stdout"] and saved["environment"]["image_id"]
        assert get_execution(str(project), saved["id"]) == saved
    print(
        "PASS actual Docker imports the scientific stack, denies network, enforces memory/output/time limits, and persists execution artifacts"
    )


if __name__ == "__main__":
    main()
