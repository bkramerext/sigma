"""Verify encrypted Personal state survives shared-container process restarts.

Must run under the unprivileged worker UID in the same named Docker volume.
"""
from __future__ import annotations

import asyncio
import os
from pathlib import Path

from sigma import ai_store

A = "a" * 32
B = "b" * 32


async def verify() -> None:
    base = Path(os.environ["SIGMA_PERSONAL_SHARED_WORKSPACES"])
    for workspace, marker in ((A, "A-UNIQUE"), (B, "B-UNIQUE")):
        with ai_store.use_directory(base / workspace):
            async with ai_store.transaction() as state:
                if state["welcome_seen"] != marker:
                    raise AssertionError("Encrypted state was not preserved through restart")
    print("PASS two users' encrypted state survived the shared worker restart")


if __name__ == "__main__":
    assert os.geteuid() == 10001
    asyncio.run(verify())
