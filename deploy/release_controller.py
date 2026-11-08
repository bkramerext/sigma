#!/usr/bin/env python3
"""Crash-safe checkpoint runner for SIGMA's unattended release operations.

This module does not decide whether a safety assertion is true. Each concrete
stage must verify its own postcondition; a process restart must *reconcile* an
interrupted stage before it can proceed. State contains no credentials or data.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import re
import stat
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

SHA = re.compile(r"[0-9a-f]{40}")
Reconcile = Literal["done", "retry", "blocked"]


class ReleaseBlocked(RuntimeError):
    """A failed safety gate or an operation requiring explicit reconciliation."""


@dataclass(frozen=True)
class Stage:
    name: str
    execute: Callable[[], dict]
    reconcile: Callable[[], Reconcile]


class CheckpointedRelease:
    def __init__(self, state_dir: Path, sha: str, stages: list[Stage]) -> None:
        if not SHA.fullmatch(sha):
            raise ValueError("release requires an exact 40-character lowercase SHA")
        if not stages or len({stage.name for stage in stages}) != len(stages):
            raise ValueError("release stages must be nonempty and uniquely named")
        self.sha = sha
        self.stages = stages
        self.state_dir = state_dir
        self.path = state_dir / (sha + ".json")

    def _prepare_dir(self) -> None:
        if self.state_dir.is_symlink():
            raise ReleaseBlocked("state directory may not be a symlink")
        self.state_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        mode = self.state_dir.stat().st_mode
        if not stat.S_ISDIR(mode) or stat.S_IMODE(mode) & 0o077:
            raise ReleaseBlocked("release state directory must be private (mode 0700)")

    def _load(self) -> dict:
        if not self.path.exists():
            return {
                "schema": 1,
                "sha": self.sha,
                "stages": [stage.name for stage in self.stages],
                "completed": {},
                "active": None,
                "blocked": None,
            }
        if self.path.is_symlink():
            raise ReleaseBlocked("release checkpoint must not be a symlink")
        try:
            state = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ReleaseBlocked("release checkpoint is unreadable or corrupt") from exc
        if (
            not isinstance(state, dict)
            or state.get("schema") != 1
            or state.get("sha") != self.sha
            or state.get("stages") != [stage.name for stage in self.stages]
            or not isinstance(state.get("completed"), dict)
        ):
            raise ReleaseBlocked("checkpoint identity or step plan has changed")
        if set(state["completed"]) - {stage.name for stage in self.stages}:
            raise ReleaseBlocked("checkpoint contains an unknown completed stage")
        return state

    def _save(self, state: dict) -> None:
        encoded = (json.dumps(state, sort_keys=True, indent=2) + "\n").encode()
        fd, temporary = tempfile.mkstemp(prefix=".release-", dir=self.state_dir)
        try:
            with os.fdopen(fd, "wb") as stream:
                os.fchmod(stream.fileno(), 0o600)
                stream.write(encoded)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
            directory = os.open(self.state_dir, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    @staticmethod
    def _time() -> str:
        return datetime.now(UTC).isoformat()

    def run(self) -> dict:
        self._prepare_dir()
        with (self.state_dir / ".release.lock").open("a+") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise ReleaseBlocked("another release controller is already active") from exc
            state = self._load()
            # A blocked or interrupted stage is never implicitly assumed safe
            # to repeat. Reconciliation must inspect its actual postcondition.
            for stage in self.stages:
                if stage.name in state["completed"]:
                    continue
                interrupted = state.get("active") == stage.name
                if interrupted:
                    disposition = stage.reconcile()
                    if disposition == "blocked":
                        state["blocked"] = {
                            "stage": stage.name,
                            "reason": "interrupted operation requires safe reconciliation",
                            "time": self._time(),
                        }
                        self._save(state)
                        raise ReleaseBlocked(f"{stage.name}: interrupted operation not reconciled")
                    if disposition == "done":
                        state["completed"][stage.name] = {
                            "time": self._time(),
                            "reconciled": True,
                        }
                        state["active"] = None
                        state["blocked"] = None
                        self._save(state)
                        print(f"PASS {stage.name}: reconciled completed operation", flush=True)
                        continue
                state["active"] = stage.name
                state["blocked"] = None
                self._save(state)
                try:
                    evidence = stage.execute()
                    if not isinstance(evidence, dict):
                        raise ReleaseBlocked("stage returned no structured evidence")
                except Exception as exc:
                    # Do not persist command output, secrets or user records.
                    state["blocked"] = {
                        "stage": stage.name,
                        "reason": type(exc).__name__,
                        "time": self._time(),
                    }
                    self._save(state)
                    raise ReleaseBlocked(f"BLOCKED at {stage.name}: {type(exc).__name__}") from exc
                state["completed"][stage.name] = {
                    "time": self._time(),
                    "evidence": evidence,
                }
                state["active"] = None
                state["blocked"] = None
                self._save(state)
                print(f"PASS {stage.name}", flush=True)
            print(f"PASS release controller complete for {self.sha}", flush=True)
            return state


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("release_sha")
    parser.add_argument("--state-dir", type=Path, default=Path("/var/lib/sigma-release"))
    args = parser.parse_args()
    parser.error(
        "This library provides the durable checkpoint runner; use "
        "routine-gce-release.py for the actual release, not this module."
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
