"""Offline T39 challenge manifest and human-scored transcript audit.

No provider dispatch, hidden grading heuristics, or inference of mathematical
correctness from fluent text. Actual model transcripts must be supplied as files.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SCORE_AXES = ("mathematical_judgment", "discriminating_next_step", "evidence_labels", "continuity")
SCORE_VALUES = (0, 1, 2)
CASES: dict[str, tuple[str, str, str]] = {
    "RH-SYM": (
        "The functional equation pairs each nontrivial zero with its reflection; therefore each zero is fixed by reflection and lies on Re(s)=1/2.",
        "Reject set symmetry implying pointwise fixedness; a symmetric pair may be distinct.",
        "invalid_inference",
    ),
    "RH-FIN": (
        "All checked zeros below a finite height lie on Re(s)=1/2, so RH is proved.",
        "Reject finite-to-universal extrapolation; require control at unbounded heights.",
        "invalid_inference",
    ),
    "RH-REGION": (
        "There are no zeros with Re(s)>7/8, and symmetry excludes Re(s)<1/8, so all zeros lie on Re(s)=1/2.",
        "Reject interior-to-line collapse: 1/8 <= Re(s) <= 7/8 is not just the line.",
        "invalid_inference",
    ),
    "RH-ETA-PARTIAL": (
        "For every complex s and positive integer m, splitting even and odd indices gives sum_{n=1}^{2m}(-1)^(n-1)n^(-s) = sum_{n=1}^{2m}n^(-s) - 2^(1-s)sum_{n=1}^m n^(-s).",
        "Credit the exact finite identity; require separate convergence and continuation arguments for infinite-series claims.",
        "valid_partial_result",
    ),
}


def challenge_manifest() -> dict[str, Any]:
    """Public challenge inputs. Expected judgments are deliberately omitted."""
    return {
        "schema_version": 1,
        "purpose": "Evaluator-authored RH challenges, not independently generated agent discoveries",
        "cases": [
            {"case_id": key, "kind": kind, "claim": claim, "provenance": "injected_evaluator_challenge"}
            for key, (claim, _, kind) in CASES.items()
        ],
    }


def blank_review(case_id: str, transcript_path: str) -> dict[str, Any]:
    if case_id not in CASES:
        raise ValueError(f"Unknown challenge: {case_id}")
    return {
        "schema_version": 1,
        "case_id": case_id,
        "transcript_path": transcript_path,
        "transcript_sha256": None,
        "provider": None,
        "session_id": None,
        "artifact_ids": [],
        "injection_provenance": "evaluator-authored",
        "reviewer": None,
        "observed_objection": None,
        "observed_next_step": None,
        "scores": {axis: None for axis in SCORE_AXES},
        "status": "UNVERIFIED",
        "notes": None,
    }


def validate_review(review: dict[str, Any]) -> dict[str, Any]:
    """Fail closed: no scored outcome without source bytes and reviewer evidence."""
    import hashlib

    case_id = review.get("case_id")
    if case_id not in CASES:
        raise ValueError("Unknown case_id")
    if review.get("schema_version") != 1:
        raise ValueError("Unsupported review schema")
    if review.get("injection_provenance") != "evaluator-authored":
        raise ValueError("Challenge provenance must remain explicit")
    path = Path(str(review.get("transcript_path", "")))
    if not path.is_file():
        raise ValueError("Missing transcript file")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if review.get("transcript_sha256") != digest:
        raise ValueError("Transcript digest missing or mismatched")
    scores = review.get("scores")
    if not isinstance(scores, dict) or set(scores) != set(SCORE_AXES):
        raise ValueError("All four scoring axes are required")
    status = review.get("status")
    if status not in ("UNVERIFIED", "MET", "UNMET"):
        raise ValueError("Invalid status")
    if status == "UNVERIFIED":
        if any(value is not None for value in scores.values()):
            raise ValueError("Unverified review cannot have numeric scores")
    else:
        if any(type(value) is not int or value not in SCORE_VALUES for value in scores.values()):
            raise ValueError("Scored review requires four integer scores from 0 to 2")
        if not all(isinstance(review.get(key), str) and review[key].strip() for key in ("reviewer", "observed_objection", "observed_next_step", "notes")):
            raise ValueError("Scored review requires human reviewer and specific evidence")
        if not review.get("artifact_ids") or not review.get("session_id"):
            raise ValueError("Scored review requires session and artifact provenance")
        if status == "MET" and scores["mathematical_judgment"] != 2:
            raise ValueError("Cannot pass a case without fully correct mathematical judgment")
    return {
        "case_id": case_id,
        "status": status,
        "scores": scores,
        "transcript_sha256": digest,
        "answer_key": CASES[case_id][1],
    }


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", action="store_true", help="Print challenge inputs without answers")
    parser.add_argument("--review-template", choices=CASES, help="Print a blank review for a case")
    parser.add_argument("--transcript", help="Transcript path for a blank review template")
    parser.add_argument("--score", type=Path, help="Validate a completed review JSON and print result")
    args = parser.parse_args()
    if args.manifest:
        result = challenge_manifest()
    elif args.review_template:
        if not args.transcript:
            parser.error("--review-template requires --transcript")
        result = blank_review(args.review_template, args.transcript)
    elif args.score:
        result = validate_review(json.loads(args.score.read_text(encoding="utf-8")))
    else:
        parser.error("Choose --manifest, --review-template, or --score")
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
