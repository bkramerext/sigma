"""Provider-free pilot admission checks for research-method source retrieval."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import AsyncMock, patch
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parent))
import research_sessions as fixture

from sigma import research_reference_compiler, research_sessions
from sigma.openai_connection import AuthContext
from sigma.project_types import builtin_types, curated_common_references
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
    return {"id": title.lower(), "title": title, "url": retrieval["url"], "retrieval": retrieval}


def verify_compiler_receives_verified_excerpts() -> None:
    configured = [source("UConn"), source("Close-reading"), source("Source-synthesis")]
    snapshot = {
        "research_method_sources": {"sources": configured},
        "project_title": "Crucible",
        "problem": "Interpret a play using three research methods.",
        "investigation_type": "literature",
        "strategy_runs": [],
    }
    payload = json.loads(research_reference_compiler.compile_input(snapshot))
    supplied = payload["retrieved_methodology_excerpts"]
    assert len(supplied) == 3, supplied
    assert {row["id"] for row in supplied} == {"uconn", "close-reading", "source-synthesis"}
    assert all(
        row["excerpt_sha256"] == hashlib.sha256(row["excerpt"].encode("utf-8")).hexdigest()
        for row in supplied
    )
    configured[1]["retrieval"]["excerpt"] = "Tampered source text"
    altered = json.loads(research_reference_compiler.compile_input(snapshot))
    assert len(altered["retrieved_methodology_excerpts"]) == 2
    assert not any(
        row["excerpt"] == "Tampered source text"
        for row in altered["retrieved_methodology_excerpts"]
    )


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
            patch.dict(
                os.environ,
                {
                    "SIGMA_REQUIRE_RETRIEVED_RESEARCH_METHODS": "false",
                    "SIGMA_REFERENCE_COMPILATION_ENABLED": "true",
                },
            ),
            patch.object(research_sessions, "auth_context", new=AsyncMock(return_value=credential)),
            patch.object(research_sessions, "configuration", new=AsyncMock(return_value=config)),
            patch.object(research_sessions, "select_method_sources", return_value=methods),
            patch.object(research_sessions, "_worker", new=AsyncMock()) as mock_worker,
        ):
            # Unavailable references are retained as uninspected pointers.
            assert retrieval_readiness_errors(methods) == []
            assert research_sessions._all(str(path)) == []
            mock_worker.assert_not_called()

            # Retrieval status alone is not proof of inspected content. The
            # gate must reject absent excerpts, mismatched excerpt hashes, and
            # malformed full-source digests, without saving or dispatching.
            no_excerpt = source("Missing-excerpt")
            no_excerpt["retrieval"]["excerpt"] = None
            wrong_excerpt_hash = source("Invalid-excerpt-hash")
            wrong_excerpt_hash["retrieval"]["excerpt_sha256"] = "0" * 64
            wrong_content_hash = source("Invalid-content-hash")
            wrong_content_hash["retrieval"]["content_sha256"] = "not-a-sha256"
            for broken, expected in (
                (no_excerpt, "Missing-excerpt"),
                (wrong_excerpt_hash, "Invalid-excerpt-hash"),
                (wrong_content_hash, "Invalid-content-hash"),
            ):
                snapshot = {**methods, "sources": [source("Valid"), broken]}
                with patch.object(
                    research_sessions, "select_method_sources", return_value=snapshot
                ):
                    try:
                        await research_sessions.start_session(
                            str(path),
                            strategy.id,
                            str(uuid4()),
                            view.project.id,
                            credential["identity"],
                            expected_limits=limits,
                            strategy_ids=[strategy.id],
                        )
                    except ProjectError as exc:
                        message = str(exc)
                        assert expected in message and "SHA-256" in message, message
                        assert "before provider dispatch" in message, message
                    else:
                        raise AssertionError(f"Unverified method {expected} was accepted")
                assert research_sessions._all(str(path)) == []
                mock_worker.assert_not_called()

            # Compilation being disabled does not bypass the source gate.
            with (
                patch.dict(os.environ, {"SIGMA_REFERENCE_COMPILATION_ENABLED": "false"}),
                patch.object(
                    research_sessions,
                    "select_method_sources",
                    return_value={**methods, "sources": [no_excerpt]},
                ),
            ):
                try:
                    await research_sessions.start_session(
                        str(path),
                        strategy.id,
                        str(uuid4()),
                        view.project.id,
                        credential["identity"],
                        expected_limits=limits,
                        strategy_ids=[strategy.id],
                    )
                except ProjectError as exc:
                    assert "Missing-excerpt" in str(exc), str(exc)
                else:
                    raise AssertionError("Compiler opt-out bypassed retrieval readiness")
            assert research_sessions._all(str(path)) == []
            mock_worker.assert_not_called()

            # A complete, hash-verified three-reference snapshot must pass
            # admission without requiring a model request.
            ready = {
                **methods,
                "sources": [
                    source("UConn"),
                    source("Brandeis-close-reading"),
                    source("Brandeis-source-synthesis"),
                ],
                "retrieval_summary": {"retrieved": 3, "unavailable": 0},
            }
            ready_idempotency_key = str(uuid4())
            with patch.object(research_sessions, "select_method_sources", return_value=ready):
                started = await research_sessions.start_session(
                    str(path),
                    strategy.id,
                    ready_idempotency_key,
                    view.project.id,
                    credential["identity"],
                    expected_limits=limits,
                    strategy_ids=[strategy.id],
                )
            assert started["status"] == "queued"
            saved = research_sessions._read(str(path), started["id"])
            assert saved["research_method_sources"]["retrieval_summary"]["retrieved"] == 3
            assert saved["reference_compilation"]["status"] == "pending"
            assert saved["reference_compilation"]["required_for_acceptance"] is True
            assert saved["calls_used"] == 0
            assert saved["steps"] == []

            # Restarting the same request must reuse its frozen snapshot,
            # never re-fetch the URLs or rewrite the saved record.
            with patch.object(
                research_sessions,
                "select_method_sources",
                side_effect=AssertionError("saved session unexpectedly re-fetched methods"),
            ):
                replay = await research_sessions.start_session(
                    str(path),
                    strategy.id,
                    ready_idempotency_key,
                    view.project.id,
                    credential["identity"],
                    expected_limits=limits,
                    strategy_ids=[strategy.id],
                )
            assert replay["id"] == started["id"]
            assert research_sessions._read(str(path), started["id"]) == saved

            # Simulate all compiler retries exhausted. The saved strict-policy
            # checkpoint must prevent the worker from starting research.
            saved["reference_compilation"]["status"] = "fallback"
            saved["reference_compilation"]["reason"] = (
                "Known provider validation failures, three attempts exhausted."
            )
            research_sessions._save(str(path), saved)

        with patch.object(research_sessions, "_portfolio_worker", new=AsyncMock()) as portfolio:
            await research_sessions._worker(started["id"], str(path))
            portfolio.assert_not_awaited()
        blocked = research_sessions._read(str(path), started["id"])
        assert blocked["status"] == "paused"
        assert "required reference compilation" in blocked["message"]
        assert blocked["calls_used"] == 0 and blocked["steps"] == []
        assert blocked["outcome"]["source_material"]["compilation"]["status"] == "fallback"


async def verify_empty_and_single_reference_sessions() -> None:
    # Zero enabled sources is valid. One enabled source is also sufficient:
    # three is a recommendation, not an admission minimum.
    for selected, compiler_enabled, expected_status, required in (
        ([], "true", "not_needed", False),
        ([source("Only-selected")], "true", "pending", True),
        ([source("Only-selected")], "false", "disabled", False),
    ):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "optional-methods.sigma"
            view, strategy, fixture_credential, config = await fixture.setup(path)
            credential = AuthContext(
                token=fixture_credential["token"],
                mode=fixture_credential["mode"],
                status=fixture_credential["status"],
                identity=fixture_credential["identity"],
            )
            selection = {
                "version": "project-type-methods-v1",
                "status": "selected" if selected else "unavailable",
                "mode": "literature",
                "sources": selected,
                "retrieval_summary": {"retrieved": len(selected), "unavailable": 0},
            }
            with (
                patch.dict(
                    os.environ,
                    {
                        "SIGMA_REQUIRE_RETRIEVED_RESEARCH_METHODS": "true",
                        "SIGMA_REFERENCE_COMPILATION_ENABLED": compiler_enabled,
                    },
                ),
                patch.object(
                    research_sessions, "auth_context", new=AsyncMock(return_value=credential)
                ),
                patch.object(
                    research_sessions, "configuration", new=AsyncMock(return_value=config)
                ),
                patch.object(research_sessions, "select_method_sources", return_value=selection),
                patch.object(research_sessions, "_worker", new=AsyncMock()),
            ):
                started = await research_sessions.start_session(
                    str(path),
                    strategy.id,
                    str(uuid4()),
                    view.project.id,
                    credential["identity"],
                    expected_limits=research_sessions.get_limits(str(path)),
                    strategy_ids=[strategy.id],
                )
            assert started["status"] == "queued"
            saved = research_sessions._read(str(path), started["id"])
            assert len(saved["research_method_sources"]["sources"]) == len(selected)
            assert saved["reference_compilation"]["source_count"] == len(selected)
            assert saved["reference_compilation"]["status"] == expected_status
            assert saved["reference_compilation"]["required_for_acceptance"] is required
            assert saved["calls_used"] == 0 and saved["steps"] == []


async def verify_unavailable_reference_sessions() -> None:
    """Broken URLs cannot consume providers or block a valid new session."""
    cases = (
        (
            "mixed",
            [
                source("Trusted-method"),
                source("Forbidden", status="unavailable", reason="http_403"),
                source("Missing", status="unavailable", reason="http_404"),
                source("Oversized", status="unavailable", reason="response_too_large"),
                source("Timed-out", status="unavailable", reason="reference_deadline_exceeded"),
            ],
            "pending",
            ["trusted-method"],
        ),
        (
            "unavailable-only",
            [
                source("Forbidden", status="unavailable", reason="http_403"),
                source("Non-HTTPS", status="unavailable", reason="non_https_or_credential_url"),
            ],
            "not_needed",
            [],
        ),
    )
    for label, sources, expected_stage, expected_ids in cases:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / f"{label}.sigma"
            view, strategy, fixture_credential, config = await fixture.setup(path)
            credential = AuthContext(
                token=fixture_credential["token"],
                mode=fixture_credential["mode"],
                status=fixture_credential["status"],
                identity=fixture_credential["identity"],
            )
            selection = {
                "version": "project-type-methods-v1",
                "status": "selected",
                "mode": "literature",
                "sources": sources,
                "retrieval_summary": {
                    "retrieved": len(expected_ids),
                    "unavailable": len(sources) - len(expected_ids),
                },
            }
            with (
                patch.dict(os.environ, {"SIGMA_REFERENCE_COMPILATION_ENABLED": "true"}),
                patch.object(
                    research_sessions, "auth_context", new=AsyncMock(return_value=credential)
                ),
                patch.object(
                    research_sessions, "configuration", new=AsyncMock(return_value=config)
                ),
                patch.object(research_sessions, "select_method_sources", return_value=selection),
                patch.object(research_sessions, "_worker", new=AsyncMock()),
            ):
                started = await research_sessions.start_session(
                    str(path),
                    strategy.id,
                    str(uuid4()),
                    view.project.id,
                    credential["identity"],
                    expected_limits=research_sessions.get_limits(str(path)),
                    strategy_ids=[strategy.id],
                )
            assert started["status"] == "queued"
            saved = research_sessions._read(str(path), started["id"])
            assert len(saved["research_method_sources"]["sources"]) == len(sources)
            assert saved["reference_compilation"]["status"] == expected_stage
            assert saved["reference_compilation"]["verified_source_count"] == len(expected_ids)
            assert saved["reference_compilation"]["unavailable_source_count"] == (
                len(sources) - len(expected_ids)
            )
            assert saved["calls_used"] == 0 and saved["steps"] == []
            compiled = json.loads(research_reference_compiler.compile_input(saved))
            assert [item["id"] for item in compiled["retrieved_methodology_excerpts"]] == (
                expected_ids
            )
            assert [item["id"] for item in compiled["uninspected_methodology_sources"]] == (
                expected_ids
            )
            context = research_sessions._portfolio_context(
                saved, saved["strategy_runs"][0], "investigator", 1
            )
            assert [item["id"] for item in context["methodology_source_material"]] == (expected_ids)
            assert context["methodology_retrieval_summary"]["unavailable"] == (
                len(sources) - len(expected_ids)
            )


def verify_curated_method_reference_defaults() -> None:
    # The built-in methodology defaults must be consumable by SIGMA's
    # HTML/plain-text-only retriever. Publication references are separate.
    for project_type in builtin_types():
        for reference in project_type.research_standards_references:
            assert reference["url"].startswith("https://"), (project_type.id, reference)
            assert not reference["url"].split("?", 1)[0].casefold().endswith(".pdf"), (
                project_type.id,
                reference,
            )
    expected_html = {
        "biology": (
            "https://www.nimh.nih.gov/research/research-funded-by-nimh/policies/"
            "enhancing-the-reliability-of-nimh-supported-research-through-rigorous-study-design-and-reporting"
        ),
        "philosophy": "https://writingprogram.gwu.edu/guide-writing-philosophy-papers",
        "religion": "https://research.kent.ac.uk/religion-methods/topics/comparative-research/",
    }
    for project_type in builtin_types():
        if project_type.id in expected_html:
            assert [row["url"] for row in project_type.research_standards_references] == [
                expected_html[project_type.id]
            ], project_type.id

    common = curated_common_references()["research_standards_references"]
    literature = next(item for item in builtin_types() if item.id == "literature")
    urls = {item["url"] for item in common}
    urls.update(item["url"] for item in literature.research_standards_references)
    assert urls == {
        "https://guides.lib.uconn.edu/c.php?g=1067492&p=7986329",
        "https://owl.purdue.edu/owl/research_and_citation/conducting_research/writing_a_literature_review.html",
        "https://owl.purdue.edu/owl/subject_specific_writing/writing_in_literature/writing_about_fiction/index.html",
    }, urls


def main() -> None:
    retrieved = [source("UConn"), source("Close-reading"), source("Source-synthesis")]
    assert retrieval_readiness_errors({"sources": retrieved}) == []

    # Exactly the Crucible failure pattern: 3 selected sources, only 1 inspected.
    unavailable = [
        retrieved[0],
        source("Close-reading", status="unavailable", reason="http_403"),
        source("Source-synthesis", status="unavailable", reason="http_403"),
    ]
    assert retrieval_readiness_errors({"sources": unavailable}) == []
    assert [row["retrieval"]["reason"] for row in unavailable[1:]] == [
        "http_403",
        "http_403",
    ]

    # A title, URL, or coordinator annotation never counts as source content.
    metadata_only = {"title": "Uninspected", "url": "https://example.org/uninspected"}
    assert len(retrieval_readiness_errors({"sources": [metadata_only]})) == 1

    # Tampered saved content cannot masquerade as a verified excerpt.
    modified = source("Tampered")
    modified["retrieval"]["excerpt"] = "Different text"
    assert "SHA-256" in retrieval_readiness_errors({"sources": [modified]})[0]
    missing_content_hash = source("No-content-hash")
    missing_content_hash["retrieval"]["content_sha256"] = None
    assert (
        "source-content SHA-256"
        in retrieval_readiness_errors({"sources": [missing_content_hash]})[0]
    )

    # A legitimate empty selection is valid; malformed source lists fail closed.
    assert retrieval_readiness_errors({"sources": []}) == []
    assert retrieval_readiness_errors({"sources": "invalid"})
    malformed_content_hash = source("Not-a-SHA")
    malformed_content_hash["retrieval"]["content_sha256"] = "invalid"
    assert (
        "source-content SHA-256"
        in retrieval_readiness_errors({"sources": [malformed_content_hash]})[0]
    )
    verify_curated_method_reference_defaults()
    verify_compiler_receives_verified_excerpts()
    asyncio.run(verify_provider_free_admission())
    asyncio.run(verify_unavailable_reference_sessions())
    asyncio.run(verify_empty_and_single_reference_sessions())
    print(
        "PASS: advisory URL failures, strict hash integrity, 0-1-3 verified sources / saved replay"
    )


if __name__ == "__main__":
    main()
