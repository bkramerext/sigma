"""Regression coverage for paper-specific, versioned ELI5 explanations."""

from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from sigma import paper_eli5, papers
from sigma.projects import ProjectError, initialize_project


def explanation() -> str:
    return "## The question\nWhat happened?\n\n" + ("We tested an idea. " * 10)


def test_eli5_cache_requires_matching_pdf_sha_and_prompt_version() -> None:
    record = {
        "pdf_sha256": "a" * 64,
        "eli5": {
            "version": paper_eli5.ELI5_VERSION,
            "source_sha256": "a" * 64,
            "markdown": explanation(),
        },
    }
    assert paper_eli5.cached(record) == record["eli5"]["markdown"]
    assert paper_eli5.cached({**record, "pdf_sha256": "b" * 64}) is None
    assert paper_eli5.cached({**record, "eli5": {**record["eli5"], "version": 1}}) is None


def test_eli5_cache_rejects_invalid_content() -> None:
    invalid = {"version": paper_eli5.ELI5_VERSION, "source_sha256": "abc"}
    invalid_short = {"pdf_sha256": "abc", "eli5": {**invalid, "markdown": "short"}}
    assert paper_eli5.cached(invalid_short) is None
    assert paper_eli5.cached({"pdf_sha256": "abc", "eli5": {**invalid, "markdown": 123}}) is None
    assert paper_eli5.cached({"pdf_sha256": "abc"}) is None


def test_eli5_input_bounded_and_preserves_question_and_conclusion() -> None:
    record = {
        "title": "A research question",
        "draft": {
            "abstract": "This is the question and answer.",
            "problem_framing": ["Why does this happen?"],
            "methods": ["We compared two explanations."],
            "sections": [{"heading": "Details", "paragraphs": ["a" * 130000, "b" * 130000]}],
            "conclusions": ["The hypothesis remains unresolved."],
            "limitations": ["More evidence is needed."],
            "open_obligations": ["The follow-up test is missing."],
        },
    }
    payload = paper_eli5.paper_context(record)
    assert payload["abstract"] == record["draft"]["abstract"]
    assert payload["conclusions"] == record["draft"]["conclusions"]
    assert payload["source_excerpts_truncated"]
    assert len(str(payload)) < 70000
    assert "## What's cool about it" in paper_eli5.INSTRUCTIONS


def test_eli5_persists_in_paper_record_and_reuses_cache() -> None:
    with TemporaryDirectory() as temp:
        path = Path(temp) / "eli5.sigma"
        view = initialize_project(path, "ELI5 test", "Explain a saved paper.")
        paper_id = "a" * 32
        papers._save(
            str(path),
            {
                "schema_version": 1,
                "paper_id": paper_id,
                "project_id": view.project.id,
                "created_at": "2026-11-02T00:00:00+00:00",
                "snapshot_sha256": "b" * 64,
                "draft": {"title": "Saved research"},
                "generation": {},
                "validation_warnings": [],
            },
            b"%PDF-test-fixture",
        )
        record = papers._read_one(str(path), paper_id)
        saved = paper_eli5._save(str(path), paper_id, record["pdf_sha256"], explanation())
        assert saved == explanation()
        updated = papers._read_one(str(path), paper_id)
        assert paper_eli5.cached(updated) == explanation()
        with patch("sigma.papers.get_paper", return_value=updated):
            result = asyncio.run(
                paper_eli5.explain(str(path), paper_id, "not-needed", view.project.id)
            )
            assert result == explanation()


def test_eli5_structured_schema_uses_provider_supported_keywords() -> None:
    schema = paper_eli5.Explanation.model_json_schema()
    markdown_schema = schema["properties"]["markdown"]
    assert "minLength" not in markdown_schema and "maxLength" not in markdown_schema
    try:
        paper_eli5.Explanation(markdown="too short")
    except ValueError:
        pass
    else:
        raise AssertionError("Runtime validation must still reject short explanations")


def test_archived_paper_eli5_roundtrip_and_legacy_duplicate_recovery() -> None:
    """A fresh ELI5 generation must not make its own paper PDF unreadable."""
    with TemporaryDirectory() as temp:
        path = Path(temp) / "archived.sigma"
        view = initialize_project(path, "Archived ELI5", "Explain archived evidence.")
        paper_id = "e" * 32
        snapshot = {
            "schema": "sigma-paper-evidence-v2",
            "project_id": view.project.id,
            "sources": [
                {"id": "project:" + view.project.id, "kind": "project", "data": {"title": "Test"}}
            ],
        }
        digest = hashlib.sha256(papers._json(snapshot)).hexdigest()
        papers._save(
            str(path),
            {
                "schema_version": 1,
                "paper_id": paper_id,
                "project_id": view.project.id,
                "created_at": "2026-11-04T00:00:00+00:00",
                "snapshot_sha256": digest,
                "snapshot": snapshot,
                "draft": {"title": "Archived test", "abstract": "Test"},
                "generation": {},
                "validation_warnings": [],
            },
            b"%PDF-archived-fixture",
        )
        filename = papers._paper_dir(str(path), create=False) / f"{paper_id}.json"
        raw = json.loads(filename.read_text())
        assert raw["snapshot_ref"] == digest and "snapshot" not in raw

        # Recreate the production corruption caused by the former ELI5 writer.
        raw["snapshot"] = snapshot
        filename.write_text(json.dumps(raw))
        assert papers.get_paper(str(path), paper_id)["snapshot"] == snapshot
        assert papers.get_pdf(str(path), paper_id) == b"%PDF-archived-fixture"
        paper_eli5._save(str(path), paper_id, raw["pdf_sha256"], explanation())
        repaired = json.loads(filename.read_text())
        assert repaired["snapshot_ref"] == digest and "snapshot" not in repaired
        assert paper_eli5.cached(papers.get_paper(str(path), paper_id)) == explanation()
        assert papers.get_pdf(str(path), paper_id) == b"%PDF-archived-fixture"

        # A genuinely divergent duplicate is still rejected as tampering.
        repaired["snapshot"] = {**snapshot, "sources": []}
        filename.write_text(json.dumps(repaired))
        try:
            papers.get_paper(str(path), paper_id)
        except ProjectError as exc:
            assert "conflicts" in str(exc)
        else:
            raise AssertionError("Mismatched archived evidence must be rejected")
if __name__ == "__main__":
    test_eli5_cache_requires_matching_pdf_sha_and_prompt_version()
    test_eli5_cache_rejects_invalid_content()
    test_eli5_input_bounded_and_preserves_question_and_conclusion()
    test_eli5_persists_in_paper_record_and_reuses_cache()
    test_eli5_structured_schema_uses_provider_supported_keywords()
    test_archived_paper_eli5_roundtrip_and_legacy_duplicate_recovery()
    print("PASS ELI5 cache identity, simple explanation prompt, bounded context and persistence")
