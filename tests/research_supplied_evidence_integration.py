"""Mocked session barrier for unavailable authoritative Source Material."""

from __future__ import annotations

import asyncio
import hashlib
import sys
from datetime import UTC, datetime, timedelta
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
        assert paused["stopped_at"] is not None
        assert "example.org/unavailable.txt" in paused["message"]
        assert "source_unavailable" in paused["message"]
        warnings = [
            event for event in paused["events"] if event["kind"] == "source_material.source_failed"
        ]
        assert len(warnings) == 1
        assert "example.org/unavailable.txt" in warnings[0]["message"]
        assert "source_unavailable" in warnings[0]["message"]
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
            warnings = [
                event
                for event in paused["events"]
                if event["kind"] == "source_material.source_failed"
            ]
            assert len(warnings) == 1
            assert second["url"] in warnings[0]["message"]

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


async def check_previously_blocked_192k_source_resumes() -> None:
    """An old 60k-cap stop resumes using saved complete extracts, no refetch or paid call."""
    with TemporaryDirectory() as temporary:
        path = Path(temporary) / "large-literature.sigma"
        view, strategy, credential, config = await setup(path)
        link = project_evidence.add_link(str(path), "https://example.org/large-paper.pdf")
        full_text = "Source text: " + ("A" * (192_711 - len("Source text: ")))
        excerpt_sha = hashlib.sha256(full_text.encode("utf-8")).hexdigest()
        reached_portfolio = asyncio.Event()

        def compile_large_source(_path: str, source: dict, _session_id: str) -> dict:
            assert source["id"] == f"uploaded-link:{link['id']}"
            return {
                **source,
                "status": "retrieved",
                "excerpt": full_text,
                "excerpt_sha256": excerpt_sha,
                "incomplete_extract": False,
            }

        async def portfolio(session_id: str, project_path: str) -> None:
            record = research_sessions._read(project_path, session_id)
            branch = record["strategy_runs"][0]
            context = research_sessions._portfolio_context(record, branch, "investigator", 1)
            assert context["uploaded_project_evidence"][0]["excerpt"] == full_text
            # The source may exceed the normal 256 kB compaction target on
            # other documents, but it must pass the reviewed Astra byte guard.
            source_context_bytes = research_sessions._json_bytes(context)
            dispatch_guard_bytes = research_sessions._agent_dispatch_guard_bytes(record)
            assert source_context_bytes < dispatch_guard_bytes
            reached_portfolio.set()

        # Recreate the persisted Source Material failure of an already-started
        # session using the historical cap, not a newly started session.
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
                research_supplied_evidence, "compile_entry", side_effect=compile_large_source
            ) as compiled,
            patch.object(
                research_sessions,
                "_bounded_supplied_evidence",
                side_effect=ValueError(
                    "Source Material contains 192,711 extracted characters; "
                    "the session supports at most 60,000."
                ),
            ),
        ):
            started = await research_sessions.start_session(
                str(path), strategy.id, str(uuid4()), view.project.id, credential["identity"]
            )
            paused = await wait_for(path, started["id"])
            assert paused["status"] == "paused"
            assert paused["supplied_evidence_compilation"]["status"] == "blocked"
            assert paused["calls_used"] == 0
            compiled.assert_called_once()

        # With the raised limit, Resume MUST reuse the saved extract and reach
        # the dispatch preflight without refetching or replacing any source.
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
                side_effect=AssertionError("Saved full source must not be fetched again"),
            ),
        ):
            await research_sessions.control_session(str(path), started["id"], "resume")
            await asyncio.wait_for(reached_portfolio.wait(), 15)

        resumed = research_sessions._read(str(path), started["id"])
        assert resumed["supplied_evidence_compilation"]["status"] == "completed"
        assert resumed["uploaded_project_evidence"][0]["excerpt_sha256"] == excerpt_sha
        assert resumed["calls_used"] == 0


def check_increased_complete_source_limit() -> None:
    """Allow complete literature up to the new ceiling and reject oversized inputs."""
    limit = research_sessions.MAX_SUPPLIED_EVIDENCE_CHARACTERS
    assert limit == 400_000
    source = {"excerpt": "X" * limit}
    assert research_sessions._bounded_supplied_evidence([source]) == [source]
    try:
        research_sessions._bounded_supplied_evidence([{"excerpt": "X" * (limit + 1)}])
    except ValueError as exc:
        assert "400,001" in str(exc)
        assert "400,000" in str(exc)
    else:
        raise AssertionError("Oversized input was silently truncated or accepted")


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
        oversized_text = "A" * (research_sessions.MAX_SUPPLIED_EVIDENCE_CHARACTERS + 1)
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
            assert "extracted characters" in paused["message"]
            assert "at most 400,000" in paused["message"]
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

        if remove:
            # Simulate the real historical Session 5 record: blocked before any
            # research call, with a missing pause checkpoint and expired clock.
            # This state must be recoverable without giving away active time.
            old = research_sessions._read(str(path), started["id"])
            pause_at = datetime.now(UTC) - timedelta(minutes=85)
            old["stopped_at"] = None
            old["started_at"] = (pause_at - timedelta(seconds=8)).isoformat()
            old["updated_at"] = pause_at.isoformat()
            old["deadline_at"] = (pause_at + timedelta(minutes=60)).isoformat()
            for event in old["events"]:
                if event.get("kind") == "source_material.compilation.blocked":
                    event["timestamp"] = pause_at.isoformat()
            research_sessions._save(str(path), old)

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
        assert "400,001" not in resumed["uploaded_project_evidence"][0]["excerpt"]
        assert resumed["calls_used"] == 0
        if remove:
            assert float(resumed["stopped_duration_seconds"]) > 80 * 60
            assert datetime.fromisoformat(resumed["deadline_at"]) > datetime.now(UTC)
            assert any(
                event["kind"] == "source_material.pause_clock_recovered"
                for event in resumed["events"]
            )
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
        huge = "X" * (research_sessions.MAX_SUPPLIED_EVIDENCE_CHARACTERS + 1)
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


def check_robust_link_retrieval() -> None:
    """Binary PDF hosts, permanent failures and transient retries, without real HTTP."""
    url = "http://example.org/reconstruction.pdf"
    pdf = (Path(__file__).parent / "fixtures/sigma-valid-sample-paper.pdf").read_bytes()

    class FakeSocket:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def settimeout(self, _timeout):
            pass

        def connect(self, _address):
            pass

        def sendall(self, _request):
            pass

    class FakeResponse:
        status = 200

        def __init__(self, content_type: str, payload: bytes) -> None:
            self.content_type = content_type
            self.payload = payload

        def begin(self):
            pass

        def getheader(self, name: str, default=None):
            return {
                "Content-Type": self.content_type,
                "Content-Length": str(len(self.payload)),
            }.get(name, default)

        def read1(self, limit):
            chunk, self.payload = self.payload[:limit], self.payload[limit:]
            return chunk

    def fake_http(content_type: str, payload: bytes):
        endpoint = (
            "example.org",
            "example.org",
            80,
            "/reconstruction.pdf",
            (
                research_supplied_evidence.socket.AF_INET,
                research_supplied_evidence.socket.SOCK_STREAM,
                0,
                "",
                ("93.184.216.34", 80),
            ),
        )
        with (
            patch.object(
                research_supplied_evidence.research_reference_content,
                "_public_endpoint",
                return_value=endpoint,
            ),
            patch.object(research_supplied_evidence.socket, "socket", return_value=FakeSocket()),
            patch.object(
                research_supplied_evidence.http.client,
                "HTTPResponse",
                return_value=FakeResponse(content_type, payload),
            ),
        ):
            return research_supplied_evidence._fetch_url_once(url)

    binary, media_type, resolved = fake_http("application/octet-stream", pdf)
    assert binary == pdf and media_type == "application/pdf" and resolved == url
    extracted = research_supplied_evidence.read_link(url, (binary, media_type, resolved))
    assert extracted["status"] == "retrieved"
    assert extracted["pages"] >= 1 and extracted["excerpt_sha256"]

    try:
        fake_http("application/octet-stream", b"<html>not a PDF</html>")
    except ValueError as exc:
        assert str(exc) == "binary_response_is_not_pdf"
    else:
        raise AssertionError("Non-PDF binary payload was accepted")

    with (
        patch.object(
            research_supplied_evidence,
            "_fetch_url_once",
            side_effect=[ValueError("http_503"), (pdf, "application/pdf", url)],
        ) as fetch,
        patch.object(research_supplied_evidence.time, "sleep") as sleep,
    ):
        assert research_supplied_evidence._fetch_url(url)[0] == pdf
        assert fetch.call_count == 2
        sleep.assert_called_once()

    with (
        patch.object(
            research_supplied_evidence, "_fetch_url_once", side_effect=ValueError("http_404")
        ) as fetch,
        patch.object(research_supplied_evidence.time, "sleep") as sleep,
    ):
        try:
            research_supplied_evidence._fetch_url(url)
        except ValueError as exc:
            assert str(exc) == "http_404"
        else:
            raise AssertionError("Permanent 404 was retried or hidden")
        fetch.assert_called_once()
        sleep.assert_not_called()

    with (
        patch.object(
            research_supplied_evidence, "_fetch_url_once", side_effect=TimeoutError("timed_out")
        ) as fetch,
        patch.object(research_supplied_evidence.time, "sleep") as sleep,
    ):
        try:
            research_supplied_evidence._fetch_url(url)
        except TimeoutError as exc:
            assert str(exc) == "timed_out"
        else:
            raise AssertionError("Exhausted transient source failures were ignored")
        assert fetch.call_count == 3
        assert sleep.call_count == 2

    with patch.object(
        research_supplied_evidence.project_evidence,
        "_extract",
        side_effect=project_evidence.ProjectError("PDF cannot be inspected."),
    ):
        failed = research_supplied_evidence.read_link(url, (pdf, "application/pdf", url))
    assert failed["status"] == "unavailable"
    assert failed["reason"] == "PDF cannot be inspected."


if __name__ == "__main__":
    check_robust_link_retrieval()
    check_increased_complete_source_limit()
    asyncio.run(check_barrier())
    asyncio.run(check_previously_blocked_192k_source_resumes())
    asyncio.run(check_partial_resume())
    asyncio.run(check_edited_source_selection_resume(remove=False))
    asyncio.run(check_edited_source_selection_resume(remove=True))
    asyncio.run(check_remove_last_source_resume())
    asyncio.run(check_role_dispatch_freezes_sources())
    print(
        "PASS Source Material barrier, corrected-selection Resume, and immutable dispatched premises"
    )
