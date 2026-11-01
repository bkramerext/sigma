"""Offline cross-process test of the hosted backend-wide provider slot bound."""

from __future__ import annotations

import asyncio
import os
import sqlite3
import subprocess
import sys
from contextlib import AsyncExitStack
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from sigma import cloud_research, research_sessions


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
                        check=True,
                        capture_output=True,
                        text=True,
                        timeout=8,
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


async def test_real_local_admission_gate() -> None:
    """Verify the public admission context, not just its lock-file helper."""
    child = """
import asyncio, sys
from pathlib import Path
from unittest.mock import patch
from sigma import research_sessions
async def main():
    with (
        patch('sigma.projects.local_projects_root', return_value=Path(sys.argv[1])),
        patch.object(research_sessions.cloud_workspaces, 'enabled', return_value=False),
    ):
        try:
            async with asyncio.timeout(0.25):
                async with research_sessions._portfolio_global_gate('other-process'):
                    print('admitted', flush=True)
        except TimeoutError:
            print('blocked', flush=True)
asyncio.run(main())
"""
    with TemporaryDirectory(prefix="sigma-local-gate-") as directory:
        root = Path(directory)
        os.chmod(root, 0o700)
        with (
            patch("sigma.projects.local_projects_root", return_value=root),
            patch.object(research_sessions.cloud_workspaces, "enabled", return_value=False),
            patch.dict(os.environ, {"SIGMA_RESEARCH_GLOBAL_INFLIGHT": "32"}),
        ):
            # The caller's bound guest/member workspace must NOT select a
            # private per-user provider capacity directory.
            private_workspace = root / "guest-workspace"
            private_workspace.mkdir(mode=0o700)
            guest = research_sessions.cloud_workspaces.Workspace(
                "a" * 32, "guest", private_workspace, guest=True
            )
            binding = research_sessions.cloud_workspaces._CURRENT.set(guest)
            try:
                async with AsyncExitStack() as held:
                    for index in range(32):
                        await held.enter_async_context(
                            research_sessions._portfolio_global_gate(f"owner-{index}")
                        )
                    blocked = await asyncio.to_thread(
                        subprocess.run,
                        [sys.executable, "-c", child, str(root)],
                        check=True,
                        capture_output=True,
                        text=True,
                        timeout=8,
                    )
                    assert blocked.stdout.strip() == "blocked", blocked.stdout
            finally:
                research_sessions.cloud_workspaces._CURRENT.reset(binding)
            admitted = await asyncio.to_thread(
                subprocess.run,
                [sys.executable, "-c", child, str(root)],
                check=True,
                capture_output=True,
                text=True,
                timeout=8,
            )
            assert admitted.stdout.strip() == "admitted", admitted.stdout
    print("PASS: local real gate never exceeds 32 across backend processes.")


def test_global_spend_holds_full_provider_exposure() -> None:
    """The global cap must not mistake a soft user estimate for worst-case usage."""
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.execute(
        "CREATE TABLE calls (amount_usd REAL, maximum_liability_usd REAL, "
        "status TEXT, created_at TEXT)"
    )
    db.execute("INSERT INTO calls VALUES (0.04, 1.28, 'reserved', '2026-01-01')")
    with patch.object(cloud_research, "_global_window_start", return_value=None):
        assert cloud_research._global_call_amount_units(db) == 1_280_000_000
        assert cloud_research._call_amount_units(db, "") == 40_000_000
        db.execute("UPDATE calls SET amount_usd=0.08, status='usage_estimated'")
        assert cloud_research._global_call_amount_units(db) == 80_000_000
    db.close()


if __name__ == "__main__":
    main()
    asyncio.run(test_real_local_admission_gate())
    test_global_spend_holds_full_provider_exposure()
