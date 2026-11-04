"""Run all papers scenario groups through the legacy entrypoint.

The SIGMA CI test plan invokes each part separately for parallel sharding.
"""

import subprocess
import sys
from pathlib import Path


if __name__ == "__main__":
    directory = Path(__file__).resolve().parent
    for part in range(1, 3):
        subprocess.run(
            [sys.executable, str(directory / f"papers_part{part}.py")],
            check=True,
        )
