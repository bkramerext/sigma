"""Offline cross-process test of the hosted backend-wide provider slot bound."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from sigma import research_sessions


def main() -> None:
    child = """
import os, sys
from pathlib import Path
from unittest.mock import patch
from sigma import research_sessions
with patch.object(research_sessions.cloud_workspaces, 'storage_root', return_value=Path(sys.argv[1])):
    fd = research_sessions._shared_provider_slot()
    print('admitted' if fd is not None else 'blocked', flush=True)
    if fd is not None:
        research_sessions.fcntl.flock(fd, research_sessions.fcntl.LOCK_UN)
        os.close(fd)
"""

    with TemporaryDirectory(prefix="sigma-capacity-") as directory:
        root = Path(directory)
        # Only private storage may be used for quota locks.
        os.chmod(root, 0o700)
        with (
            patch.object(research_sessions.cloud_workspaces, "storage_root", return_value=root),
            patch.dict(os.environ, {"SIGMA_RESEARCH_GLOBAL_INFLIGHT": "32"}),
        ):
            held: list[int] = []
            try:
                for _ in range(32):
                    fd = research_sessions._shared_provider_slot()
                    assert fd is not None, "Provider cap rejected a funded slot too early."
                    held.append(fd)
                assert research_sessions._shared_provider_slot() is None

                def run_child() -> str:
                    result = subprocess.run(
                        [sys.executable, "-c", child, str(root)],
                        check=True, capture_output=True, text=True, timeout=8,
                    )
                    return result.stdout.strip()

                assert run_child() == "blocked", "Another backend process bypassed the 32-slot cap."
                research_sessions.fcntl.flock(held[-1], research_sessions.fcntl.LOCK_UN)
                os.close(held.pop())
                assert run_child() == "admitted", "Capacity was not returned after release."
            finally:
                for fd in held:
                    research_sessions.fcntl.flock(fd, research_sessions.fcntl.LOCK_UN)
                    os.close(fd)

    print("PASS: 32 slots shared across two independent backend processes.")


if __name__ == "__main__":
    main()
