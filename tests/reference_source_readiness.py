"""Provider-free pilot admission checks for research-method source retrieval."""

from __future__ import annotations

import asyncio
import hashlib
import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import AsyncMock, patch
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parent))
import research_sessions as fixture

from sigma import research_sessions
from sigma.openai_connection import AuthContext
from sigma.projects import ProjectError

from sigma.research_method_sources import retrieval_readiness_errors


def source(title: str, *, status: str = "retrieved", reason: str | None = None) -> dict:
    excerpt = f"Verified methodological excerpt for {title}."
    retrieval = {
        "status": status,
        "url": "https://example.org/" + title,
        "content_sha256": hashlib.sha256(excerpt.encode()).hexdigest(),
        "excerpt_sha256": hashlib.sha256(excerpt.encode()).hexdigest(),
        "excerpt": excerpt,
        "reason": reason,
    }
    if status != "retrieved":
        retrieval.update(
            content_sha256=None,
            excerpt_sha256=None,
            excerpt=None,
        )
    return {"title": title, "url": retrieval["url"], "retrieval": retrieval}



async def verify_provider_free_admission() -> None:
    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "method-readiness.sigma"
        view, strategy, fixture_credential, config = await fixture.setup(path)
        credential = AuthContext(
            token=fixture_credential["token"],
            mode=fixture_credential["mode"],
            status=fixture_credential["status"],
            identity=fixture_credential["identity"],
        )
        limits = research_sessions.get_limits(str(path))
        configured = [
            source("UConn"),
            source("Brandeis-close-reading", status="unavailable", reason="http_403"),
            source("Brandeis-source-synthesis", status="unavailable", reason="http_403"),
        ]
        methods = {
            "version": "methodology-catalog-v2",
            "status": "selected",
            "mode": "literature",
            "branch": None,
            "sources": configured,
            "retrieval_summary": {"retrieved": 1, "unavailable": 2},
        }
        with (
            patch.dict(os.environ, {"SIGMA_REQUIRE_RETRIEVED_RESEARCH_METHODS": "true"}),
            patch.object(
                research_sessions, "auth_context", new=AsyncMock(return_value=credential)
            ),
            patch.object(
                research_sessions, "configuration", new=AsyncMock(return_value=config)
            ),
            patch.object(research_sessions, "select_method_sources", return_value=methods),
            patch.object(research_sessions, "_worker", new=AsyncMock()) as mock_worker,
        ):
            try:
                await research_sessions.start_session(
                    str(path), strategy.id, str(uuid4()), view.project.id,
                    credential["identity"], expected_limits=limits,
                    strategy_ids=[strategy.id],
                )
            except ProjectError as exc:
                message = str(exc)
                assert "before provider dispatch" in message, message
                assert "Brandeis-close-reading" in message, message
                assert "Brandeis-source-synthesis" in message, message
            else:
                raise AssertionError("Unretrieved methodology URLs were accepted")
            assert research_sessions._all(str(path)) == []
            mock_worker.assert_not_called()

            # A complete, hash-verified three-reference snapshot must pass
            # admission without requiring a model request.
            ready = {
                **methods,
                "sources": [source("UConn"), source("Brandeis-close-reading"),
                            source("Brandeis-source-synthesis")],
                "retrieval_summary": {"retrieved": 3, "unavailable": 0},
            }
            with patch.object(research_sessions, "select_method_sources", return_value=ready):
                started = await research_sessions.start_session(
                    str(path), strategy.id, str(uuid4()), view.project.id,
                    credential["identity"], expected_limits=limits,
                    strategy_ids=[strategy.id],
                )
            assert started["status"] == "queued"
            saved = research_sessions._read(str(path), started["id"])
            assert saved["research_method_sources"]["retrieval_summary"]["retrieved"] == 3
            assert saved["reference_compilation"]["status"] == "pending"
            assert saved["calls_used"] == 0
            assert saved["steps"] == []


def main() -> None:
    retrieved = [source("UConn"), source("Close-reading"), source("Source-synthesis")]
    assert retrieval_readiness_errors({"sources": retrieved}) == []

    # Exactly the Crucible failure pattern: 3 selected sources, only 1 inspected.
    unavailable = [
        retrieved[0],
        source("Close-reading", status="unavailable", reason="http_403"),
        source("Source-synthesis", status="unavailable", reason="http_403"),
    ]
    issues = retrieval_readiness_errors({"sources": unavailable})
    assert len(issues) == 2
    assert all("http_403" in item for item in issues)
    assert any("Close-reading" in item for item in issues)
    assert any("Source-synthesis" in item for item in issues)

    # A title, URL, or coordinator annotation never counts as source content.
    metadata_only = {"title": "Uninspected", "url": "https://example.org/uninspected"}
    assert len(retrieval_readiness_errors({"sources": [metadata_only]})) == 1

    # Tampered saved content cannot masquerade as a verified excerpt.
    modified = source("Tampered")
    modified["retrieval"]["excerpt"] = "Different text"
    assert "SHA-256" in retrieval_readiness_errors({"sources": [modified]})[0]
    missing_content_hash = source("No-content-hash")
    missing_content_hash["retrieval"]["content_sha256"] = None
    assert "source-content SHA-256" in retrieval_readiness_errors(
        {"sources": [missing_content_hash]}
    )[0]

    # An empty selection is not evidence that all configured methods were read.
    assert retrieval_readiness_errors({"sources": []})
    assert retrieval_readiness_errors({"sources": "invalid"})
    asyncio.run(verify_provider_free_admission())
    print("PASS: research-reference admission / all-3 retrievable / 403 / no provider dispatch")


if __name__ == "__main__":
    main()
