"""Synthetic adversarial wording check; not an actual research session."""

import hashlib
import json
import os
from copy import deepcopy
from pathlib import Path

from sigma.project_reports import render_report
from sigma.research_feedback import ComputationFeedback, validate_feedback
from sigma.research_sessions import _outcome

root = Path(__file__).resolve().parents[1]
out = Path(os.environ.get("SIGMA_COMPUTATION_OUTPUT_DIR", root / "docs/evaluations/increment_5"))
diagnostics = out / "diagnostics"
diagnostics.mkdir(parents=True, exist_ok=True)

# The bytes are authentic to this synthetic test, but contain no derivation.
stdout = '{"theorem_proved": true, "proof": "trust me"}\n'
execution = {
    "id": "synthetic-execution",
    "status": "completed",
    "exit_code": 0,
    "stdout": stdout,
    "stderr": "",
}
citation = {
    "research_artifact_id": "synthetic-artifact",
    "execution_id": execution["id"],
    "evidence": "output",
    "filename": None,
    "use": "result",
}
feedback = ComputationFeedback(
    research_artifact_id="synthetic-artifact",
    execution_id=execution["id"],
    observed_status="completed",
    observed_field="stdout",
    observed_text_sha256=hashlib.sha256(stdout.encode()).hexdigest(),
    reported_effect="bounded_support",
    next_test="Supply a derivation and inspect each claimed inference independently.",
).model_dump()
validate_feedback(
    feedback,
    [citation],
    [{"research_artifact_id": "synthetic-artifact", "execution": execution}],
    next_question=feedback["next_test"],
    assessment="revise",
)

record = {
    "id": "synthetic-session",
    "session_number": 1,
    "status": "ended",
    "problem": "Prove a universal mathematical statement.",
    "strategy_id": "synthetic-strategy",
    "strategy_title": "Test a purported proof",
    "strategy_text": "Inspect whether a printed assertion supplies a derivation.",
    "artifacts": [
        {
            "id": "synthetic-artifact",
            "sequence": 1,
            "strategy_id": "synthetic-strategy",
            "claim_or_question": "A program printed a proof flag but no proof.",
            "method": "Print a JSON assertion.",
            "skeptic_response": "The output is an assertion. No universal proof follows.",
            "coordinator_decision": "revise",
            "evidence_status": "incomplete",
            "objections": ["The program did not derive the claim."],
            "open_obligations": ["Supply a derivation and inspect every inference."],
            "next_question": feedback["next_test"],
            "investigator_output": {"python_execution": execution},
            "skeptic_output": {
                "computation_feedback": feedback,
                "computational_citations": [citation],
            },
            "objective_review": {
                "status": "partial",
                "claim": "A program asserted theorem_proved=true; the universal claim remains open.",
                "argument_summary": "No derivation was supplied.",
                "argument_steps": [],
                "verification_status": "incomplete",
                "basis_artifact_ids": ["synthetic-artifact"],
                "open_obligations": ["Supply a derivation and inspect every inference."],
                "unresolved_objections": ["The program did not derive the claim."],
            },
        }
    ],
    "research_context_version": 2,
}
record["outcome"] = _outcome(record)
assert record["outcome"]["assessment"] != "positive"
assert "unverified" in record["outcome"]["caveats"][0].lower()
report, _ = render_report(
    {
        "project": {
            "title": "SYNTHETIC ADVERSARIAL TEST",
            "problem": record["problem"],
            "id": "synthetic",
            "investigation_type": "mathematical",
            "strategies": [],
        },
        "research_sessions": [record],
    },
    "txt",
)
assert isinstance(report, str)
assert "Verification: Incomplete" in report
assert "No derivation was supplied" in report
assert (
    "not independently verified" in report.lower()
    or "not independent verification" in report.lower()
)
(diagnostics / "SYNTHETIC_MISLEADING_OUTPUT.report.txt").write_text(
    "SYNTHETIC ADVERSARIAL TEST; NOT AN ACTUAL SIGMA RESEARCH SESSION\n\n" + report
)
(diagnostics / "SYNTHETIC_MISLEADING_OUTPUT.validation.json").write_text(
    json.dumps(
        {
            "scope": "synthetic in-memory guard, not provider research",
            "stdout": stdout,
            "sha256": feedback["observed_text_sha256"],
            "feedback_accepted_as_observation": True,
            "outcome_assessment": record["outcome"]["assessment"],
            "verification": record["outcome"]["verification_label"],
        },
        indent=2,
    )
)

# Adversarial role agreement can still create a positive *candidate* label.
# Preserve that boundary visibly rather than treating a hash as a proof check.
optimistic = deepcopy(record)
review = optimistic["artifacts"][0]["objective_review"]
review.update(
    status="achieved",
    claim="The printout proves the universal claim.",
    argument_summary="The program printed theorem_proved=true.",
    argument_steps=[
        {
            "number": 1,
            "title": "Printed assertion",
            "argument": "The JSON flag is true.",
            "epistemic_status": "computation",
            "basis_artifact_ids": ["synthetic-artifact"],
            "review": {"disposition": "accepted", "rationale": "The printout was observed."},
        }
    ],
    verification_status="convincing_unverified",
    unresolved_objections=[],
    open_obligations=[],
)
optimistic["outcome"] = _outcome(optimistic)
assert optimistic["outcome"]["assessment"] == "positive"
assert "unverified" in optimistic["outcome"]["label"].lower()
optimistic_report, _ = render_report(
    {
        "project": {
            "title": "SYNTHETIC MISLEADING ROLE AGREEMENT",
            "problem": optimistic["problem"],
            "id": "synthetic",
            "investigation_type": "mathematical",
            "strategies": [],
        },
        "research_sessions": [optimistic],
    },
    "txt",
)
assert isinstance(optimistic_report, str)
assert "not independently verified" in optimistic_report.lower()
assert "Convincing but unverified" in optimistic_report
(diagnostics / "SYNTHETIC_MISLEADING_OUTPUT.optimistic.report.txt").write_text(
    "SYNTHETIC ADVERSARIAL TEST; NOT AN ACTUAL SIGMA RESEARCH SESSION\n\n" + optimistic_report
)
print(
    "PASS correctly hashed misleading stdout is only an observation; conservative synthetic report remains incomplete, and optimistic role agreement stays an unverified candidate"
)
