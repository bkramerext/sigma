"""Actual backend SIGKILL and replacement process for two independent Papers.

Exercises the production scoped FIFO gate and durable section/queue sidecars,
without invoking a paid provider or TeX. Real dual-PDF HTTP publication is
covered independently by the Track B acceptance suite.
"""

from __future__ import annotations

import asyncio
import json
import os
import select
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from uuid import uuid4

from sigma import papers

ROOT = Path(__file__).resolve().parents[1]


def _checkpoint(path: str, *, model: str, partial: bool) -> None:
    work = papers._new_work("a" * 64, "test-project", "b" * 64, model, "high")
    if partial:
        work["section_drafts"]["1"] = {
            "tables": [],
            "examples": [],
            "paragraphs": ["Section one was completely saved before the backend died."],
        }
        work["section_dispatches"]["1"] = [1]
        work["provider_calls"] = 1
        work["provider_calls_total"] = 1
    papers._save_work(path, work)
    assert papers._load_work(path) is not None


def _child(stage: str) -> None:
    root = Path(os.environ["SIGMA_PAPER_RESTART_ROOT"])
    ids = json.loads(os.environ["SIGMA_PAPER_RESTART_IDS"])
    project = str(root / "research.sigma")
    if stage == "worker":
        Path(project).mkdir(mode=0o700)

        async def work() -> None:
            first_entered = asyncio.Event()

            async def first() -> None:
                with papers.paper_run_scope(ids["first"]):
                    async with papers._paper_operation(project, generating=True):
                        _checkpoint(project, model="N", partial=True)
                        receipt = root / "provider-attempts"
                        with receipt.open("w") as stream:
                            stream.write("section-one\n")
                            stream.flush()
                            os.fsync(stream.fileno())
                        first_entered.set()
                        await asyncio.Event().wait()

            async def second() -> None:
                with papers.paper_run_scope(ids["second"]):
                    _checkpoint(project, model="Z", partial=False)
                    async with papers._paper_operation(project, generating=True):
                        (root / "second-admitted").write_text("unexpected early admission\n")

            with patch("sigma.memory_guard.require_capacity"):
                primary = asyncio.create_task(first())
                await asyncio.wait_for(first_entered.wait(), timeout=5)
                queued = asyncio.create_task(second())
                for _ in range(500):
                    with papers.paper_run_scope(ids["second"]):
                        receipt = papers._read_queue_status(project)
                        if receipt is not None and receipt["status"] == "queued":
                            break
                    await asyncio.sleep(0.01)
                else:
                    raise AssertionError("second Paper never entered the durable queue")
                assert not queued.done()
                assert not (root / "second-admitted").exists()
                print("READY", flush=True)
                await asyncio.gather(primary, queued)

        asyncio.run(work())
        return

    if stage != "recover":
        raise AssertionError(f"Unexpected test stage: {stage}")

    with papers.paper_run_scope(ids["first"]):
        first = papers._load_work(project)
        assert first is not None
        assert first["model"] == "N"
        assert first["provider_calls_total"] == 1
        assert first["section_dispatches"] == {"1": [1]}
        assert first["section_drafts"]["1"]["paragraphs"] == [
            "Section one was completely saved before the backend died."
        ]
        assert papers._read_queue_status(project) is None
        assert papers.activity_status(project) != "active"

    with papers.paper_run_scope(ids["second"]):
        second = papers._load_work(project)
        assert second is not None and second["model"] == "Z"
        original = papers._read_queue_status(project)
        assert original is not None and original["status"] == "queued"
        assert papers.activity_status(project) == "interrupted"

    async def explicitly_reopen() -> None:
        with patch("sigma.memory_guard.require_capacity"):
            # A fresh backend cannot silently dispatch anything: these are
            # deliberately explicit, provider-free operations under the same
            # saved run IDs. They demonstrate both queue slots are reclaimable.
            for run_id, expected_model in (
                (ids["second"], "Z"),
                (ids["first"], "N"),
            ):
                with papers.paper_run_scope(run_id):
                    async with papers._paper_operation(project, generating=True):
                        recovered = papers._load_work(project)
                        assert recovered is not None and recovered["model"] == expected_model
                        assert papers._read_queue_status(project) is None

    asyncio.run(explicitly_reopen())
    assert not (root / "second-admitted").exists()
    assert (root / "provider-attempts").read_text().splitlines() == ["section-one"]
    with papers.paper_run_scope(ids["first"]):
        first_reopened = papers._load_work(project)
        assert first_reopened is not None
        assert first_reopened["section_drafts"]["1"]["paragraphs"]
    with papers.paper_run_scope(ids["second"]):
        second_reopened = papers._load_work(project)
        assert second_reopened is not None
        assert second_reopened["model"] == "Z"
    print(json.dumps({"provider_attempts": 1, "replays": 0, "runs": 2}), flush=True)


def test_real_paper_process_crash() -> None:
    """Kill both a running and a queued Paper, then verify fresh-process recovery."""
    with TemporaryDirectory(prefix="sigma-paper-kill-", dir=ROOT.parent) as directory:
        root = Path(directory)
        ids = {"first": uuid4().hex, "second": uuid4().hex}
        environment = {
            **os.environ,
            "SIGMA_PAPER_RESTART_ROOT": str(root),
            "SIGMA_PAPER_RESTART_IDS": json.dumps(ids),
            "PYTHONPATH": str(ROOT / "src") + os.pathsep + os.environ.get("PYTHONPATH", ""),
        }
        worker = subprocess.Popen(
            [sys.executable, str(Path(__file__)), "worker"],
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            assert worker.stdout is not None
            readable, _, _ = select.select([worker.stdout], [], [], 10)
            if not readable:
                raise AssertionError("Paper worker never accepted both tasks")
            ready = worker.stdout.readline().strip()
            assert ready == "READY", f"Paper worker failed before kill: {ready!r}"
            assert worker.poll() is None
            worker.kill()
            worker.wait(timeout=3)
            assert worker.returncode != 0
            replacement = subprocess.run(
                [sys.executable, str(Path(__file__)), "recover"],
                env=environment,
                capture_output=True,
                text=True,
                timeout=12,
                check=False,
            )
            assert replacement.returncode == 0, replacement.stdout + replacement.stderr
            report = json.loads(replacement.stdout.strip().splitlines()[-1])
            assert report == {"provider_attempts": 1, "replays": 0, "runs": 2}
        finally:
            if worker.poll() is None:
                worker.kill()
            worker.communicate(timeout=3)


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in {"worker", "recover"}:
        raise SystemExit("This is a subprocess acceptance helper")
    _child(sys.argv[1])
