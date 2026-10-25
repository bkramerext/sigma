"""Current understanding: real saved archives and explicit synthetic schema cases.

Synthetic records test disposition semantics only; they are not research results.
"""

import json
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient

from sigma.api import app
from sigma.projects import initialize_project
from sigma.research_sessions import _obligation_identity, _save
from sigma.research_state import build_current_understanding, current_understanding

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = (
    ROOT
    / "docs/evaluations/fixtures/t17-8-answer-free/live-session-91e96112-27ce-412e-841f-5cbf67cbba75.json"
)


def synthetic_artifact(
    identifier, sequence, *, strategy="strategy", text="Synthetic local finding", obligations=None
):
    return {
        "id": identifier,
        "project_id": "project",
        "session_id": "session",
        "strategy_id": strategy,
        "strategy_title": "Synthetic schema fixture",
        "sequence": sequence,
        "claim_or_question": text,
        "method": "Synthetic representation only",
        "assumptions": [],
        "evidence_status": "SYNTHETIC schema test; no live research",
        "objective_review": {
            "status": "partial",
            "claim": text,
            "verification_status": "incomplete",
            "assumptions": [],
        },
        "open_obligations": obligations or [],
        "skeptic_output": {},
    }


def synthetic_session(artifacts):
    return {
        "id": "session",
        "project_id": "project",
        "strategy_id": "strategy",
        "session_number": 1,
        "status": "ended",
        "artifacts": artifacts,
    }


def test_historical_archives():
    raw = ARCHIVE.read_bytes()
    data = json.loads(raw)
    before = deepcopy(data)
    result = build_current_understanding(data["project"]["id"], data["research_sessions"])
    assert len(result["findings"]) == 2
    assert len(result["current_finding_ids"]) == 1
    final = next(f for f in result["findings"] if f["id"] == result["current_finding_ids"][0])
    assert "1+n(n+1)/2" in final["text"] and "y=kx+k²" in final["text"]
    assert final["verification"] == "Convincing but unverified"
    assert result["project_status"] == "not_determined"
    # The original archive actually contains source-linked obligation reviews.
    # Report those as model-reported resolutions, never independent proof.
    assert result["obligations"] and not result["next_investigations"]
    assert all(not item["actionable"] for item in result["obligations"])
    resolved = [item for item in result["obligations"] if item["status"] == "resolved_reported"]
    assert len(resolved) == 4
    assert all(item["dispositions"][-1]["valid"] for item in resolved)
    assert any(
        item["status"] == "historical_unreconciled" and "Finish and state" in item["text"]
        for item in result["obligations"]
    )
    # Synthetic schema-absence variant tests narrative-only claims of resolution;
    # it must not be confused with the unaltered provider archive above.
    narrative_only = deepcopy(data["research_sessions"])
    narrative_only[0]["artifacts"][-1]["skeptic_output"]["obligation_reviews"] = []
    narrative = build_current_understanding(data["project"]["id"], narrative_only)
    noticed = [item for item in narrative["obligations"] if item["narrative_resolution_sources"]]
    assert noticed and all(
        item["status"] == "historical_unreconciled" and not item["actionable"] for item in noticed
    )
    assert data == before and ARCHIVE.read_bytes() == raw

    source = ROOT / "samples/nonconsecutive-subset-sums/sample-evidence.json"
    fixture_raw = source.read_bytes()
    fixture = json.loads(fixture_raw)
    # The canonical evidence uses a substitution token for the owning sample ID.
    records = json.loads(
        json.dumps(fixture["research_sessions"]).replace(
            "$SIGMA_SAMPLE_PROJECT_ID", "subset-project"
        )
    )
    result = build_current_understanding("subset-project", records)
    assert len(result["findings"]) == 5
    refutation = next(
        item for item in result["changes"] if item["kind"] == "local_refutation_reported"
    )
    assert "original problem remains open" in refutation["text"]
    assert "local claim only" in refutation["caution"]
    # The correction is a later saved finding, not an inferred retraction of the
    # earlier (correct-formula/wrong-explanation) artifact.
    correction = next(item for item in result["findings"] if "exponent explanation" in item["text"])
    assert correction["status"] == "partial_reported"
    assert any("gap-removal" in f["investigated_claim"] for f in result["findings"])
    assert not any(item["kind"] in {"supersedes", "refutes"} for item in result["changes"])
    assert result["next_investigations"]
    assert any(
        "asymptotic" in item["question"] or "limiting" in item["question"]
        for item in result["next_investigations"]
    )
    assert all("fixture" in f["evidence_kind"].casefold() for f in result["findings"])
    assert source.read_bytes() == fixture_raw
    assert result == build_current_understanding("subset-project", list(reversed(records)))


def test_explicit_dispositions_and_no_semantic_matching():
    text = "Prove the boundary case."
    first = synthetic_artifact("first", 1, obligations=[text])
    second = synthetic_artifact("second", 2, text="A later exact calculation is saved.")
    obligation_id = _obligation_identity(
        text, project_id="project", strategy_id="strategy", assumptions=[]
    )
    second["skeptic_output"]["obligation_reviews"] = [
        {
            "obligation_id": obligation_id,
            "status": "addressed",
            "basis_artifact_ids": ["second"],
            "rationale": "Synthetic explicit source-linked disposition.",
        }
    ]
    record = synthetic_session([first, second])
    before = deepcopy(record)
    result = build_current_understanding("project", [record])
    item = result["obligations"][0]
    assert item["id"] == obligation_id and item["status"] == "resolved_reported"
    assert (
        item["dispositions"][0]["valid"]
        and item["dispositions"][0]["basis"][0]["artifact_id"] == "second"
    )
    assert record == before
    third = synthetic_artifact("third", 3, obligations=[text])
    reopened = build_current_understanding("project", [synthetic_session([first, second, third])])
    assert reopened["obligations"][0]["status"] == "open_reported"
    assert reopened["obligations"][0]["actionable"]
    assert not reopened["obligations"][0]["dispositions"][0]["applied"]
    # Similar wording without an exact ID cannot close the original obligation.
    invalid = deepcopy(second)
    invalid["skeptic_output"]["obligation_reviews"][0]["obligation_id"] = "unrelated-id"
    assert (
        build_current_understanding("project", [synthetic_session([first, invalid])])[
            "obligations"
        ][0]["status"]
        == "historical_unreconciled"
    )
    for broken_basis in (["foreign-artifact"], [], ["future-artifact"]):
        invalid = deepcopy(second)
        invalid["skeptic_output"]["obligation_reviews"][0]["basis_artifact_ids"] = broken_basis
        candidate = build_current_understanding(
            "project",
            [synthetic_session([first, invalid, synthetic_artifact("future-artifact", 3)])],
        )
        assert candidate["obligations"][0]["status"] != "resolved_reported"
        assert not candidate["obligations"][0]["dispositions"][0]["valid"]
    # Exact same note under a different branch must retain its distinct scope.
    other = synthetic_artifact("other", 3, strategy="other-strategy", obligations=[text])
    scoped = build_current_understanding("project", [synthetic_session([first, second, other])])
    assert len(scoped["obligations"]) == 2 and len({o["id"] for o in scoped["obligations"]}) == 2
    assert (
        next(o for o in scoped["obligations"] if o["strategy_id"] == "other-strategy")["status"]
        == "open_reported"
    )


def test_relations_are_explicit_and_bounded_to_sources():
    first = synthetic_artifact("upper", 1, strategy="bound", text="An upper bound is 1+n(n+1)/2.")
    second = synthetic_artifact(
        "construction",
        2,
        strategy="construction",
        text="The parabolic line family attains the bound.",
    )
    unrelated = synthetic_artifact(
        "other", 3, strategy="unrelated", text="A finite sequence has five terms."
    )
    record = synthetic_session([first, second, unrelated])
    result = build_current_understanding("project", [record])
    assert len(result["current_finding_ids"]) == 3
    assert not result["changes"]
    assert all(not f["related_by"] for f in result["findings"])
    assert all(f["status"] == "partial_reported" for f in result["findings"])
    # A deliberately stored synthetic assessment, not a prose-inequality heuristic.
    unrelated["finding_relations"] = [
        {
            "source_session_id": "session",
            "source_artifact_id": "upper",
            "relation": "refutes",
            "basis_artifact_ids": ["other"],
            "rationale": "Synthetic relation test only, not a mathematical assertion.",
        }
    ]
    explicit = build_current_understanding("project", [record])
    assert explicit["findings"][0]["status"] == "refuted_reported"
    assert explicit["changes"][0]["kind"] == "refutes"
    assert explicit["changes"][0]["earlier"]["artifact_id"] == "upper"
    assert "not independent verification" in explicit["changes"][0]["caution"]
    unrelated["finding_relations"][0]["source_session_id"] = "foreign-session"
    assert (
        build_current_understanding("project", [record])["findings"][0]["status"]
        == "partial_reported"
    )
    # Peer-handoff retraction must not be interpreted as retracting a whole finding.
    unrelated.pop("finding_relations")
    unrelated["skeptic_output"]["retracted_cross_strategy_source_artifact_ids"] = ["upper"]
    assert (
        build_current_understanding("project", [record])["findings"][0]["status"]
        == "partial_reported"
    )


def test_read_only_path_isolation_and_empty_failed():
    with TemporaryDirectory() as temporary:
        root = Path(temporary)
        view = initialize_project(root / "empty.sigma", "Empty", "A bounded question")
        before_files = sorted(str(p.relative_to(root)) for p in root.rglob("*"))
        state = current_understanding(view.path)
        assert not state["findings"] and not state["next_investigations"]
        assert sorted(str(p.relative_to(root)) for p in root.rglob("*")) == before_files
        session_id = str(uuid4())
        record = {
            "id": session_id,
            "project_id": view.project.id,
            "project_path": view.path,
            "status": "running",
            "session_number": 1,
            "artifacts": [],
        }
        _save(view.path, record)
        foreign_id = str(uuid4())
        _save(
            view.path,
            {
                **record,
                "id": foreign_id,
                "project_id": "foreign",
                "project_path": "/unrelated/project",
            },
        )
        before = {p: p.read_bytes() for p in Path(view.path).rglob("*") if p.is_file()}
        with (
            patch(
                "sigma.research_sessions._recover",
                side_effect=AssertionError("Recovery is not a read"),
            ),
            patch("httpx.AsyncClient.send", side_effect=AssertionError("No external requests")),
        ):
            state = current_understanding(view.path)
            with TestClient(app) as client:
                response = client.get(
                    "/api/projects/current-understanding", params={"path": view.path}
                )
                assert response.status_code == 200
                assert response.json() == state
        assert state["session_count"] == 1 and state["failures"][0]["status"] == "running"
        assert any("excluded" in note for note in state["limitations"])
        assert not state["findings"]
        assert all(p.read_bytes() == content for p, content in before.items())
        assert (
            json.loads((Path(view.path) / "research-sessions" / f"{session_id}.json").read_text())[
                "status"
            ]
            == "running"
        )
        failed = build_current_understanding(
            "project",
            [{"id": "failed", "project_id": "project", "status": "failed", "artifacts": []}],
        )
        assert not failed["findings"] and failed["failures"][0]["status"] == "failed"
        assert (
            build_current_understanding(
                "project", [{"id": "foreign", "project_id": "elsewhere", "artifacts": []}]
            )["session_count"]
            == 0
        )


def main():
    test_historical_archives()
    test_explicit_dispositions_and_no_semantic_matching()
    test_relations_are_explicit_and_bounded_to_sources()
    test_read_only_path_isolation_and_empty_failed()
    print(
        "PASS read-only current understanding: original archives, explicit dispositions/relations, no semantic matching, stable ordering/IDs, path isolation, missing/failed history, no provider work"
    )


if __name__ == "__main__":
    main()
