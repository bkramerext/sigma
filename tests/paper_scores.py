"""Regression tests for SIGMA's versioned, research-aware paper scoring."""

from __future__ import annotations

import asyncio
import copy
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import AsyncMock, patch

from sigma import paper_scores, papers
from sigma.projects import initialize_project


def judgment() -> paper_scores.PaperJudgment:
    return paper_scores.PaperJudgment.model_validate(
        {
            "tex_correctness": {"earned": 80, "explanation": "Typesetting is mostly sound."},
            "readability": {"earned": 76, "explanation": "Some sections require rereading."},
            "sustained_answer": {"earned": 72, "explanation": "The conclusion is qualified."},
            "research_rigor": {
                "earned": 68,
                "explanation": "Some alternate explanations are unchecked.",
            },
            "evidence": {
                "earned": 82,
                "explanation": "Several material citations need verification.",
            },
            "visuals": {"earned": 90, "explanation": "One chart could be more clearly labelled."},
        }
    )


def test_scoring_weights_and_normalized_total() -> None:
    sha = "a" * 64
    score = paper_scores._make_score(judgment(), sha)
    assert paper_scores.RUBRIC_VERSION == 3
    assert sum(paper_scores.WEIGHTS.values()) == 100
    assert all(weight >= 10 for weight in paper_scores.WEIGHTS.values())
    assert [score["categories"][key]["weight"] for key in paper_scores.WEIGHTS] == [
        0.10,
        0.20,
        0.15,
        0.30,
        0.15,
        0.10,
    ]
    assert [
        f"{score['categories'][key]['earned']}/{score['categories'][key]['max']}"
        for key in paper_scores.WEIGHTS
    ] == [
        "80/100",
        "76/100",
        "72/100",
        "68/100",
        "82/100",
        "90/100",
    ]
    # 8 + 15.2 + 10.8 + 20.4 + 12.3 + 9 = 75.7, rounded half up.
    assert score["total"] == 76
    assert f"{score['total']}/100" == "76/100"
    assert paper_scores.validate_score(score, sha) == score
    assert paper_scores.validate_score(score, "b" * 64) is None
    assert paper_scores.cached_score({"pdf_sha256": sha, "score": score}) == score

    for key in paper_scores.WEIGHTS:
        invalid = copy.deepcopy(score)
        invalid["categories"][key]["earned"] = 101
        assert paper_scores.validate_score(invalid, sha) is None
        invalid = copy.deepcopy(score)
        invalid["categories"][key]["earned"] = 0
        assert paper_scores.validate_score(invalid, sha) is None
        invalid = copy.deepcopy(score)
        invalid["categories"][key]["earned"] = 1.5
        assert paper_scores.validate_score(invalid, sha) is None
        invalid = copy.deepcopy(score)
        invalid["categories"][key]["weight"] = 0.99
        assert paper_scores.validate_score(invalid, sha) is None
        invalid = copy.deepcopy(score)
        invalid["categories"][key]["max"] = 99
        assert paper_scores.validate_score(invalid, sha) is None

    invalid = copy.deepcopy(score)
    invalid["total"] = 77
    assert paper_scores.validate_score(invalid, sha) is None
    invalid = copy.deepcopy(score)
    invalid["rubric_version"] += 1
    assert paper_scores.validate_score(invalid, sha) is None
    invalid = copy.deepcopy(score)
    del invalid["categories"]["research_rigor"]
    assert paper_scores.validate_score(invalid, sha) is None
    invalid = copy.deepcopy(score)
    invalid["categories"]["extra"] = {
        "earned": 1,
        "max": 100,
        "weight": 0.10,
        "explanation": "Extra",
    }
    assert paper_scores.validate_score(invalid, sha) is None

    assert paper_scores.normalize_total(0, 100) == 0
    assert paper_scores.normalize_total(1, 200) == 1
    assert paper_scores.normalize_total(100, 100) == 100
    try:
        paper_scores.normalize_total(101, 100)
    except ValueError:
        pass
    else:
        raise AssertionError("Out-of-bounds normalized score accepted")


def test_score_bounds_and_best_known_only() -> None:
    sha = "f" * 64
    low = paper_scores._make_score(judgment(), sha)
    high = copy.deepcopy(low)
    high["categories"]["research_rigor"]["earned"] = 78
    high["total"] += 3
    assert paper_scores.best_score([]) is None
    assert (
        paper_scores.best_score([{"score": None, "pdf_available": True, "pdf_sha256": sha}]) is None
    )
    assert (
        paper_scores.best_score(
            [
                {"score": low, "pdf_available": True, "pdf_sha256": sha},
                {"score": high, "pdf_available": True, "pdf_sha256": sha},
                {"score": None, "pdf_available": True, "pdf_sha256": sha},
            ]
        )
        == 79
    )
    assert (
        paper_scores.best_score(
            [
                {"score": high, "pdf_available": False, "pdf_sha256": sha},
                {"score": low, "pdf_available": True, "pdf_sha256": sha},
            ]
        )
        == 76
    )
    assert (
        paper_scores.best_score(
            [
                {"score": high, "pdf_available": True, "pdf_sha256": "0" * 64},
            ]
        )
        is None
    )


def test_score_persists_per_version_and_deleted_highest_falls_back() -> None:
    with TemporaryDirectory() as temporary:
        path = Path(temporary) / "scores.sigma"
        view = initialize_project(path, "Paper Scoring", "Compare two papers.")
        ids = ("a" * 32, "b" * 32)
        for version, paper_id in enumerate(ids):
            papers._save(
                str(path),
                {
                    "schema_version": 1,
                    "paper_id": paper_id,
                    "project_id": view.project.id,
                    "created_at": f"2026-11-0{version + 1}T00:00:00+00:00",
                    "snapshot_sha256": "c" * 64,
                    "draft": {"title": "A saved paper"},
                    "generation": {},
                    "validation_warnings": [],
                },
                b"%PDF-fixture" + bytes([version]),
            )
        assert len(papers.list_papers(str(path))) == 2
        records = [papers.get_paper(str(path), paper_id) for paper_id in ids]
        for index, record in enumerate(records):
            score = paper_scores._make_score(judgment(), record["pdf_sha256"])
            if index:
                score["categories"]["research_rigor"]["earned"] += 10
                score["total"] += 3
            paper_scores._save_score(str(path), ids[index], score)
        list_after_reload = papers.list_papers(str(path))
        assert all(item["score"] is not None for item in list_after_reload)
        assert paper_scores.best_score(list_after_reload) == 79
        assert len(list_after_reload) == 2
        papers.delete_paper(str(path), ids[1])
        remaining = papers.list_papers(str(path))
        assert len(remaining) == 1
        assert paper_scores.best_score(remaining) == 76


def test_scoring_is_single_flight_and_cache_hit_avoids_provider() -> None:
    async def scenario() -> None:
        with TemporaryDirectory() as temporary:
            path = Path(temporary) / "score-once.sigma"
            view = initialize_project(path, "Scoring Test", "Evaluate a saved paper.")
            paper_id = "d" * 32
            papers._save(
                str(path),
                {
                    "schema_version": 1,
                    "paper_id": paper_id,
                    "project_id": view.project.id,
                    "created_at": "2026-11-01T00:00:00+00:00",
                    "snapshot_sha256": "c" * 64,
                    "draft": {"title": "Scored paper"},
                    "generation": {},
                    "validation_warnings": [],
                },
                b"%PDF-fixture",
            )
            auth = {"identity": "test-binding", "mode": "api_key", "token": "test-token"}
            calls = 0

            async def provider(*args: object, **kwargs: object):
                nonlocal calls
                calls += 1
                await asyncio.sleep(0.03)
                return judgment(), "mock"

            with (
                patch("sigma.openai_connection.auth_context", new=AsyncMock(return_value=auth)),
                patch(
                    "sigma.proposals.configuration",
                    new=AsyncMock(
                        return_value={
                            "available": True,
                            "model": "test",
                            "reasoning_effort": "medium",
                        }
                    ),
                ),
                patch.object(paper_scores, "_context", return_value={"pdf": "fixture"}),
                patch.object(papers, "_provider_structured", new=provider),
            ):
                first, second = await asyncio.gather(
                    paper_scores.score_paper(str(path), paper_id, "test-binding", view.project.id),
                    paper_scores.score_paper(str(path), paper_id, "test-binding", view.project.id),
                )
                assert first == second and calls == 1
                third = await paper_scores.score_paper(
                    str(path), paper_id, "test-binding", view.project.id
                )
                assert third == first and calls == 1
                assert papers.list_papers(str(path))[0]["score"] == first

    asyncio.run(scenario())


def test_rubric_omits_stale_scores() -> None:
    sha = hashlib.sha256(b"paper").hexdigest()
    score = paper_scores._make_score(judgment(), sha)
    obsolete = copy.deepcopy(score)
    obsolete["rubric_version"] = 2
    assert paper_scores.cached_score({"pdf_sha256": sha, "score": obsolete}) is None
    assert paper_scores.cached_score({"pdf_sha256": sha, "score": score}) == score


def test_score_write_preserves_archived_paper_snapshot() -> None:
    with TemporaryDirectory() as temp:
        path = Path(temp) / "score-archive.sigma"
        view = initialize_project(path, "Score archive", "Evaluate an archived paper.")
        paper_id = "f" * 32
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
                "draft": {"title": "Score archive"},
                "generation": {},
                "validation_warnings": [],
            },
            b"%PDF-score-archive",
        )
        original = papers.get_paper(str(path), paper_id)
        score = paper_scores._make_score(judgment(), original["pdf_sha256"])
        paper_scores._save_score(str(path), paper_id, score)
        saved = json.loads(
            (papers._paper_dir(str(path), create=False) / f"{paper_id}.json").read_text()
        )
        assert saved["snapshot_ref"] == digest and "snapshot" not in saved
        assert papers.get_paper(str(path), paper_id)["score"] == score
        assert papers.get_pdf(str(path), paper_id) == b"%PDF-score-archive"
def main() -> None:
    test_scoring_weights_and_normalized_total()
    test_score_bounds_and_best_known_only()
    test_score_persists_per_version_and_deleted_highest_falls_back()
    test_scoring_is_single_flight_and_cache_hit_avoids_provider()
    test_rubric_omits_stale_scores()
    test_score_write_preserves_archived_paper_snapshot()
    print("PASS paper scoring weights, cache, persistence, concurrent evaluation, and invalidation")


if __name__ == "__main__":
    main()
