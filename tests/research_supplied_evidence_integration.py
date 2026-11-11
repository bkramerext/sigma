"""Mocked session barrier for unavailable authoritative Source Material."""

from __future__ import annotations

import asyncio
import hashlib
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


async def check_edited_source_selection_resume(*, remove: bool) -> None:
    """An oversized PDF/link portfolio must recover without a new session."""
    with TemporaryDirectory() as temporary:
        path = Path(temporary) / "oversized.sigma"
        view, strategy, credential, config = await setup(path)
        attachment = project_evidence.add_evidence(
            str(path),
            "test-resume.pdf",
            (
                Path(__file__).resolve().parent / "fixtures/sigma-valid-sample-paper.pdf"
            ).read_bytes(),
        )
        link = project_evidence.add_link(str(path), "https://example.org/oversize.txt")
        oversized_text = "A" * 80_000
        real_compile = research_supplied_evidence.compile_entry
        compiled_ids: list[str] = []

        def compile_frozen_source(p: str, source: dict, session_id: str) -> dict:
            compiled_ids.append(source["id"])
            if source["id"] == f"uploaded-link:{link['id']}":
                return {
                    **source,
                    "status": "retrieved",
                    "excerpt": oversized_text,
                    "excerpt_sha256": hashlib.sha256(oversized_text.encode()).hexdigest(),
                    "incomplete_extract": False,
                }
            return real_compile(p, source, session_id)

        ready = asyncio.Event()

        async def portfolio(_session_id: str, _path: str) -> None:
            ready.set()

        with (
            patch.object(research_sessions, "auth_context", new=AsyncMock(return_value=credential)),
            patch.object(research_sessions, "configuration", new=AsyncMock(return_value=config)),
            patch.object(
                research_sessions,
                "_ensure_reference_compilation",
                new=AsyncMock(return_value=True),
            ) as compiler,
            patch.object(research_sessions, "_portfolio_worker", new=portfolio),
            patch.object(
                research_supplied_evidence, "compile_entry", side_effect=compile_frozen_source
            ) as compile_call,
        ):
            started = await research_sessions.start_session(
                str(path), strategy.id, str(uuid4()), view.project.id, credential["identity"]
            )
            paused = await wait_for(path, started["id"])
            assert paused["status"] == "paused"
            assert paused["supplied_evidence_compilation"]["status"] == "blocked"
            assert "Source Material contains" in paused["message"]
            assert "80,000" in paused["message"]
            assert paused["calls_used"] == 0
            compiler.assert_not_awaited()
            assert compile_call.call_count == 2

        # These operations are project edits, not session changes. Re-enable
        # no historical inputs and never throw away completed source receipts.
        if remove:
            project_evidence.remove_evidence(str(path), link["id"])
        else:
            project_evidence.set_enabled(str(path), link["id"], False)
        assert [
            row["id"]
            for row in project_evidence.list_evidence(str(path))
            if row.get("enabled", True)
        ] == [attachment["id"]]

        with (
            patch.object(research_sessions, "auth_context", new=AsyncMock(return_value=credential)),
            patch.object(research_sessions, "configuration", new=AsyncMock(return_value=config)),
            patch.object(
                research_sessions,
                "_ensure_reference_compilation",
                new=AsyncMock(return_value=True),
            ) as compiler,
            patch.object(research_sessions, "_portfolio_worker", new=portfolio),
            patch.object(
                research_supplied_evidence,
                "compile_entry",
                side_effect=AssertionError("Unchanged PDF must not be extracted again"),
            ),
        ):
            await research_sessions.control_session(str(path), started["id"], "resume")
            await asyncio.wait_for(ready.wait(), 15)
            compiler.assert_awaited_once()

        resumed = research_sessions._read(str(path), started["id"])
        assert resumed["supplied_evidence_compilation"]["status"] == "completed"
        assert resumed["supplied_evidence_compilation"]["total"] == 1
        assert len(resumed["uploaded_project_evidence"]) == 1
        assert resumed["uploaded_project_evidence"][0]["id"] == f"uploaded-pdf:{attachment['id']}"
        assert "80,000" not in resumed["uploaded_project_evidence"][0]["excerpt"]
        assert resumed["calls_used"] == 0
        assert len(compiled_ids) == 2
        history = resumed["source_material_selection_history"]
        assert history[-1]["reason"] == "user_resume_before_research_dispatch"
        assert history[-1]["reused_verified_extracts"] == 1
        assert any(
            event["kind"] == "source_material.selection_refreshed" for event in resumed["events"]
        )


async def check_remove_last_source_resume() -> None:
    """Removing every formerly oversized source must clear the frozen input."""
    with TemporaryDirectory() as temporary:
        path = Path(temporary) / "removed.sigma"
        view, strategy, credential, config = await setup(path)
        link = project_evidence.add_link(str(path), "https://example.org/giant.txt")
        huge = "X" * 75_000
        done = asyncio.Event()

        async def portfolio(_session_id: str, _path: str) -> None:
            done.set()

        with (
            patch.object(research_sessions, "auth_context", new=AsyncMock(return_value=credential)),
            patch.object(research_sessions, "configuration", new=AsyncMock(return_value=config)),
            patch.object(
                research_sessions,
                "_ensure_reference_compilation",
                new=AsyncMock(return_value=True),
            ),
            patch.object(research_sessions, "_portfolio_worker", new=portfolio),
            patch.object(
                research_supplied_evidence,
                "compile_entry",
                return_value={
                    "id": f"uploaded-link:{link['id']}",
                    "url": link["url"],
                    "status": "retrieved",
                    "excerpt": huge,
                    "excerpt_sha256": hashlib.sha256(huge.encode()).hexdigest(),
                    "incomplete_extract": False,
                },
            ),
        ):
            started = await research_sessions.start_session(
                str(path), strategy.id, str(uuid4()), view.project.id, credential["identity"]
            )
            paused = await wait_for(path, started["id"])
            assert paused["supplied_evidence_compilation"]["status"] == "blocked"

        project_evidence.remove_evidence(str(path), link["id"])
        with (
            patch.object(research_sessions, "auth_context", new=AsyncMock(return_value=credential)),
            patch.object(research_sessions, "configuration", new=AsyncMock(return_value=config)),
            patch.object(
                research_sessions,
                "_ensure_reference_compilation",
                new=AsyncMock(return_value=True),
            ),
            patch.object(research_sessions, "_portfolio_worker", new=portfolio),
            patch.object(
                research_supplied_evidence,
                "compile_entry",
                side_effect=AssertionError("Deleted Source Material must not be fetched"),
            ),
        ):
            await research_sessions.control_session(str(path), started["id"], "resume")
            await asyncio.wait_for(done.wait(), 15)

        resumed = research_sessions._read(str(path), started["id"])
        assert resumed["uploaded_project_evidence"] == []
        assert resumed["supplied_evidence_compilation"]["total"] == 0
        assert resumed["calls_used"] == 0


async def check_role_dispatch_freezes_sources() -> None:
    """A session with role attempts must not silently rewrite past premises."""
    with TemporaryDirectory() as temporary:
        path = Path(temporary) / "past-research.sigma"
        await setup(path)
        link = project_evidence.add_link(str(path), "https://example.org/old.txt")
        old = [{"id": f"uploaded-link:{link['id']}", "url": link["url"]}]
        record = {
            "uploaded_project_evidence": old,
            "calls_used": 1,
            "artifacts": [],
            "steps": [{"role": "investigator", "status": "interrupted"}],
            "strategy_runs": [],
        }
        project_evidence.remove_evidence(str(path), link["id"])
        assert research_sessions._refresh_supplied_evidence_on_resume(str(path), record) is False
        assert record["uploaded_project_evidence"] == old
        assert "source_material_selection_history" not in record


if __name__ == "__main__":
    asyncio.run(check_barrier())
    asyncio.run(check_partial_resume())
    asyncio.run(check_edited_source_selection_resume(remove=False))
    asyncio.run(check_edited_source_selection_resume(remove=True))
    asyncio.run(check_remove_last_source_resume())
    asyncio.run(check_role_dispatch_freezes_sources())
    print(
        "PASS Source Material barrier, corrected-selection Resume, and immutable dispatched premises"
    )
