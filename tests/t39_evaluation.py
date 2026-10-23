"""Offline T39 challenge and scoring contract, without paid provider calls."""

import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from sigma.t39_evaluation import (
    CASES,
    SCORE_AXES,
    blank_review,
    challenge_manifest,
    validate_review,
)


def must_reject(review: dict, reason: str) -> None:
    try:
        validate_review(review)
    except ValueError:
        return
    raise AssertionError(f"Incorrectly accepted {reason}")


def main() -> None:
    manifest = challenge_manifest()
    assert len(manifest["cases"]) == 4
    assert set(CASES) == {case["case_id"] for case in manifest["cases"]}
    assert all(case["provenance"] == "injected_evaluator_challenge" for case in manifest["cases"])
    manifest_text = json.dumps(manifest)
    assert "Reject set symmetry" not in manifest_text
    assert "Credit the exact finite identity" not in manifest_text

    with TemporaryDirectory() as directory:
        transcript = Path(directory) / "transcript.json"
        transcript.write_text(
            json.dumps({"session_id": "real-session-placeholder", "messages": []}),
            encoding="utf-8",
        )
        review = blank_review("RH-SYM", str(transcript))
        review["transcript_sha256"] = hashlib.sha256(transcript.read_bytes()).hexdigest()
        assert validate_review(review)["status"] == "UNVERIFIED"
        assert set(review["scores"]) == set(SCORE_AXES)

        scored = {
            **review,
            "status": "MET",
            "scores": dict.fromkeys(SCORE_AXES, 2),
            "reviewer": "Independent evaluator",
            "observed_objection": "Symmetric set does not imply fixed points.",
            "observed_next_step": "Find a property excluding symmetric off-line pairs.",
            "notes": "Human-scored fixture only; not evidence of a live SIGMA trial.",
            "session_id": "session-fixture",
            "artifact_ids": ["artifact-fixture"],
        }
        assert validate_review(scored)["status"] == "MET"
        must_reject({**scored, "transcript_sha256": "bad"}, "transcript tampering")
        must_reject({**scored, "artifact_ids": []}, "missing artifact provenance")
        must_reject({**scored, "session_id": None}, "missing session provenance")
        must_reject({**scored, "reviewer": None}, "anonymous grading")
        must_reject({**scored, "scores": {**scored["scores"], "mathematical_judgment": 1}}, "incorrect math pass")
        must_reject({**scored, "scores": {**scored["scores"], "mathematical_judgment": True}}, "boolean as numeric score")
        must_reject({**scored, "injection_provenance": "agent_discovery"}, "false discovery provenance")
        must_reject({**review, "scores": dict.fromkeys(SCORE_AXES, 2)}, "unverified numeric scoring")
        transcript.write_text("tampered", encoding="utf-8")
        must_reject(scored, "post-review transcript mutation")

    print("PASS T39 manifest redaction, review provenance, score validation and transcript integrity")


if __name__ == "__main__":
    main()
