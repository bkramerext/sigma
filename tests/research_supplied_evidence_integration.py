"""Mocked session barrier for unavailable authoritative Source Material."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import AsyncMock, patch
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parent))
from research_sessions_part1 import setup, wait_for

from sigma import project_evidence, research_sessions, research_supplied_evidence


async def check_barrier() -> None:
    with TemporaryDirectory() as temporary:
        path = Path(temporary) / "source-barrier.sigma"
        view, strategy, credential, config = await setup(path)
        project_evidence.add_link(str(path), "https://example.org/unavailable.txt")
        portfolio = AsyncMock()
        reference_compiler = AsyncMock(return_value=True)
        with (
            patch.object(research_sessions, "auth_context", new=AsyncMock(return_value=credential)),
            patch.object(research_sessions, "configuration", new=AsyncMock(return_value=config)),
            patch.object(
                research_sessions, "_ensure_reference_compilation", new=reference_compiler
            ),
            patch.object(research_sessions, "_portfolio_worker", new=portfolio),
            patch.object(
                research_supplied_evidence,
                "_fetch_url",
                side_effect=OSError("source_unavailable"),
            ),
        ):
            started = await research_sessions.start_session(
                str(path), strategy.id, str(uuid4()), view.project.id, credential["identity"]
            )
            paused = await wait_for(path, started["id"])
        assert paused["status"] == "paused"
        assert paused["supplied_evidence_compilation"]["status"] == "blocked"
        assert "example.org/unavailable.txt" in paused["message"]
        portfolio.assert_not_called()
        reference_compiler.assert_not_awaited()  # Never spend on a blocked source


async def check_partial_resume() -> None:
    with TemporaryDirectory() as temporary:
        path = Path(temporary) / "partial.sigma"
        view, strategy, credential, config = await setup(path)
        first = project_evidence.add_link(str(path), "https://example.org/first.txt")
        second = project_evidence.add_link(str(path), "https://example.org/second.txt")
        completed = asyncio.Event()

        async def portfolio(_session_id: str, _path: str) -> None:
            completed.set()

        def fetch(url: str):
            if url == first["url"]:
                return b"Frozen first premise", "text/plain", url
            raise OSError("second_source_unavailable")

        with (
            patch.object(research_sessions, "auth_context", new=AsyncMock(return_value=credential)),
            patch.object(research_sessions, "configuration", new=AsyncMock(return_value=config)),
            patch.object(
                research_sessions, "_ensure_reference_compilation", new=AsyncMock(return_value=True)
            ),
            patch.object(research_sessions, "_portfolio_worker", new=portfolio),
            patch.object(research_supplied_evidence, "_fetch_url", side_effect=fetch),
        ):
            started = await research_sessions.start_session(
                str(path), strategy.id, str(uuid4()), view.project.id, credential["identity"]
            )
            paused = await wait_for(path, started["id"])
            assert paused["supplied_evidence_compilation"]["status"] == "blocked"
            saved = paused["supplied_evidence_compilation"]["sources"]
            assert saved[0]["status"] == "retrieved" and saved[1]["status"] == "unavailable"

        with (
            patch.object(research_sessions, "auth_context", new=AsyncMock(return_value=credential)),
            patch.object(research_sessions, "configuration", new=AsyncMock(return_value=config)),
            patch.object(
                research_sessions, "_ensure_reference_compilation", new=AsyncMock(return_value=True)
            ),
            patch.object(research_sessions, "_portfolio_worker", new=portfolio),
            patch.object(
                research_supplied_evidence,
                "_fetch_url",
                return_value=(b"Recovered second premise", "text/plain", second["url"]),
            ) as refetch,
        ):
            await research_sessions.control_session(str(path), started["id"], "resume")
            await asyncio.wait_for(completed.wait(), 15)
        refetch.assert_called_once_with(second["url"])
        restored = research_sessions.get_session(str(path), started["id"])
        assert restored["supplied_evidence_compilation"]["status"] == "completed"
        assert len(restored["uploaded_project_evidence"]) == 2
        saved_record = research_sessions._read(str(path), started["id"])
        branch = saved_record["strategy_runs"][0]
        for role in ("investigator", "skeptic"):
            context = research_sessions._portfolio_context(saved_record, branch, role, 1)
            delivered = context["uploaded_project_evidence"]
            assert "Frozen first premise" in delivered[0]["excerpt"]
            assert "Recovered second premise" in delivered[1]["excerpt"]
            assert "authoritative premises" in context["supplied_evidence_policy"]


if __name__ == "__main__":
    asyncio.run(check_barrier())
    asyncio.run(check_partial_resume())
    print("PASS Source Material barrier and partial resume without refetching completed sources")
