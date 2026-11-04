"""Run all research_sessions scenario groups through the legacy entrypoint.

The SIGMA CI test plan invokes each part separately for parallel sharding.
"""

# The scheduler parity workflow imports these historical fixture helpers from
# this module. Preserve that import contract after splitting the test suite.
from research_sessions_part1 import (  # noqa: F401
    REAL_CLIENT,
    investigation,
    provider_response,
    setup,
    skeptic,
    wait_for,
)

import subprocess
import sys
from pathlib import Path


if __name__ == "__main__":
    directory = Path(__file__).resolve().parent
    for part in range(1, 5):
        subprocess.run(
            [sys.executable, str(directory / f"research_sessions_part{part}.py")],
            check=True,
        )
