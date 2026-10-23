"""Offline T39 challenge manifest and human-scored transcript audit.

No provider dispatch, hidden grading heuristics, or inference of mathematical
correctness from fluent text. Actual model transcripts must be supplied as files.
"""

import hashlib
import json
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



def capture_session(
    case_id: str, session: dict[str, Any]
) -> dict[str, Any]:
    """Extract actual saved role evidence only after challenge delivery is proven.

    This never generates a model response and never treats authored fixtures
    as independently discovered research. The caller supplies an authentic
    SIGMA session returned by research_sessions.get_session().
    """
    if case_id not in CASES:
        raise ValueError("Unknown challenge")
    if not isinstance(session, dict) or not isinstance(session.get("id"), str):
        raise ValueError("Missing SIGMA session ID")
    claim = CASES[case_id][0]
    interventions = [
        item for item in session.get("interventions", [])
        if isinstance(item, dict)
        and isinstance(item.get("text"), str)
        and claim in item["text"]
    ]
    if len(interventions) != 1:
        raise ValueError("Exactly one matching evaluator challenge intervention is required")
    intervention = interventions[0]
    deliveries = [
        item for item in intervention.get("deliveries", [])
        if isinstance(item, dict)
        and item.get("role") == "skeptic"
        and item.get("status") == "acknowledged"
    ]
    if len(deliveries) != 1:
        raise ValueError("A single acknowledged Skeptic delivery is required")
    delivery = deliveries[0]
    attempts = [
        attempt for attempt in delivery.get("attempts", [])
        if isinstance(attempt, dict) and attempt.get("status") == "acknowledged"
    ]
    if len(attempts) != 1 or not isinstance(attempts[0].get("step_id"), str):
        raise ValueError("Acknowledged delivery must identify exactly one saved step")
    step_id = attempts[0]["step_id"]
    steps = [
        step for step in session.get("steps", [])
        if isinstance(step, dict) and step.get("id") == step_id
        and step.get("role") == "skeptic" and step.get("status") == "completed"
    ]
    if len(steps) != 1 or not isinstance(steps[0].get("output"), dict):
        raise ValueError("The challenge response must be a completed saved Skeptic output")
    step = steps[0]
    reviews = step["output"].get("human_guidance_reviews", [])
    if not isinstance(reviews, list) or not any(
        isinstance(item, dict) and item.get("intervention_id") == intervention.get("id")
        for item in reviews
    ):
        raise ValueError("Skeptic output lacks acknowledgment of the matching challenge")
    artifacts = [
        artifact for artifact in session.get("artifacts", [])
        if isinstance(artifact, dict)
        and artifact.get("strategy_id") == step.get("strategy_id")
        and artifact.get("strategy_cycle") == step.get("cycle")
        and isinstance(artifact.get("id"), str)
    ]
    if len(artifacts) != 1:
        raise ValueError("Expected exactly one saved artifact from the challenged cycle")
    artifact = artifacts[0]
    return {
        "schema_version": 1,
        "case_id": case_id,
        "provenance": "evaluator-authored human intervention, acknowledged by Skeptic",
        "session_id": session["id"],
        "session_number": session.get("session_number"),
        "session_status": session.get("status"),
        "mode": session.get("mode"),
        "model": session.get("model"),
        "reasoning_effort": session.get("reasoning_effort"),
        "intervention_id": intervention["id"],
        "challenge_claim": claim,
        "skeptic_step_id": step_id,
        "strategy_id": step.get("strategy_id"),
        "strategy_cycle": step.get("cycle"),
        "skeptic_output": step["output"],
        "artifact_id": artifact["id"],
        "artifact_claim": artifact.get("claim_or_question"),
        "outcome": {
            "assessment": session.get("outcome", {}).get("assessment"),
            "label": session.get("outcome", {}).get("label"),
        },
        "scope": "Saved content only; no assertion of mathematical correctness",
    }


def captured_review(case_id: str, transcript_path: str) -> dict[str, Any]:
    """Generate an unscored review anchored to a captured transcript file."""
    path = Path(transcript_path)
    capture = json.loads(path.read_text(encoding="utf-8"))
    if capture.get("case_id") != case_id or capture.get("schema_version") != 1:
        raise ValueError("Captured transcript case or schema mismatch")
    if capture.get("provenance") != "evaluator-authored human intervention, acknowledged by Skeptic":
        raise ValueError("Unverified challenge delivery")
    result = blank_review(case_id, transcript_path)
    result.update({
        "transcript_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "provider": capture.get("mode"),
        "session_id": capture["session_id"],
        "artifact_ids": [capture["artifact_id"]],
    })
    return result


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", action="store_true", help="Print challenge inputs without answers")
    parser.add_argument("--review-template", choices=CASES, help="Print a blank review for a case")
    parser.add_argument("--transcript", help="Transcript path for a blank review template")
    parser.add_argument("--score", type=Path, help="Validate a completed review JSON and print result")
    parser.add_argument("--capture", choices=CASES, help="Capture an acknowledged Skeptic challenge from saved session")
    parser.add_argument("--project-path", help="Working SIGMA project path, not sample template")
    parser.add_argument("--session-id", help="Saved research session UUID")
    parser.add_argument("--output", type=Path, help="Write captured transcript JSON to this new file")
    parser.add_argument("--captured-review", type=Path, help="Create blank review from a captured transcript")
    args = parser.parse_args()
    if args.manifest:
        result = challenge_manifest()
    elif args.review_template:
        if not args.transcript:
            parser.error("--review-template requires --transcript")
        result = blank_review(args.review_template, args.transcript)
    elif args.score:
        result = validate_review(json.loads(args.score.read_text(encoding="utf-8")))
    elif args.capture:
        if not args.project_path or not args.session_id or not args.output:
            parser.error("--capture requires --project-path, --session-id and --output")
        from sigma.research_sessions import get_session

        result = capture_session(args.capture, get_session(args.project_path, args.session_id))
        with args.output.open("x", encoding="utf-8") as handle:
            json.dump(result, handle, indent=2, ensure_ascii=False)
            handle.write("\\n")
    elif args.captured_review:
        record = json.loads(args.captured_review.read_text(encoding="utf-8"))
        result = captured_review(record["case_id"], str(args.captured_review))
    else:
        parser.error("Choose --manifest, --review-template, or --score")
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
