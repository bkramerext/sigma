#!/usr/bin/env python3
"""Read-only Increment 17 longitudinal research integrity gate, no inference."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "docs/evaluations/increment_7/exports"

def load(name):
    return json.loads((ROOT / name).read_text())["research_sessions"]

def evaluate():
    withheld = load("graph-withheld.audit.json")
    present = load("graph-present.audit.json")
    assert len(withheld) == 1 and len(present) == 3
    w = withheld[0]
    p = present
    metrics = w["outcome"]["metrics"]["operational"]
    execution = next(item["value"] for item in metrics if item["label"] == "Python runs by status")
    assert execution == "0 executions"
    summary = w["outcome"]["summary"]
    assert "computational observation" in summary.lower()
    assert w["outcome"]["verification_label"] == "Incomplete"
    assert summary in w["outcome"]["conclusion"]
    assert p[0]["outcome"]["verification_label"] == "Incomplete"
    next_questions = [s["current_question"] for s in p]
    generic_reset = "Advance this strategy with one specific claim" in next_questions[1]
    assert generic_reset
    assert "three-vertex negative witness" in next_questions[2]
    assert "arbitrary-size proof open" in next_questions[2]
    assert len({s["id"] for s in p}) == 3
    return {
        "archived_graph_sessions": len(p),
        "withheld_control_sessions": len(withheld),
        "unsupported_computation_claim_at_summary_lead": True,
        "withheld_control_actual_executions": 0,
        "typed_verification_blocks_false_proof": True,
        "generic_followup_reset_detected": generic_reset,
        "approved_continuation_preserves_negative_witness": True,
        "general_proof_remains_open": True,
        "unscripted_longitudinal_quality_demonstrated": False,
        "matched_budget_single_role_comparison": False,
        "new_paid_calls": 0,
        "disposition": "RESEARCH_QUALITY_GATE_NOT_MET",
    }

def main():
    result = evaluate()
    print(json.dumps(result, indent=2, sort_keys=True))

if __name__ == "__main__":
    main()
