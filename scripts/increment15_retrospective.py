"""Read-only retrospective checks of existing SIGMA evidence. No model calls."""

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "docs/evaluations"
LIVE = BASE / "fixtures/t17-8-answer-free/live-session-91e96112-27ce-412e-841f-5cbf67cbba75.json"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    record = json.loads(LIVE.read_text(encoding="utf-8"))
    sessions = record["research_sessions"]
    assert len(sessions) == 1
    session = sessions[0]
    steps = session["steps"]
    assert session["status"] == "ended"
    assert len(steps) == 4
    assert [step["role"].lower() for step in steps] == [
        "investigator",
        "skeptic",
        "investigator",
        "skeptic",
    ]
    assert len(session["artifacts"]) == 2
    assert session["calls_used"] == 4
    usage = [step.get("token_usage", {}) for step in steps]
    # Historical aggregate token count is known to be defective. Preserve
    # per-step evidence but never silently recast this as current accounting.
    assert session["tokens_used"] == 0
    on_off = json.loads((BASE / "increment_3/control-results.json").read_text())
    assert on_off["off_second_question"] != on_off["on_second_question"]
    assert on_off["stop_reloaded_same_packet"] is True
    assert on_off["original_ids_preserved"] is True
    computation = json.loads((BASE / "increment_4/independent-results.json").read_text())
    assert computation["new_six_step_candidate_counterexample"] == {
        "n": 0,
        "actual": 8,
        "predicted": 9,
        "residual": -1,
    }
    assert computation["matched_actual_calls"] == 28
    assert computation["graph_insertion_cases"] == 4500
    assert computation["all_original_session_objects_export_equal"] is True
    results = {
        "evidence_type": "archived_observational_and_scripted_controls",
        "actual_live_model_sessions_reviewed": 1,
        "archived_live_session_sha256": hashlib.sha256(LIVE.read_bytes()).hexdigest(),
        "live_session_role_sequence": [s["role"] for s in steps],
        "live_session_calls": session["calls_used"],
        "live_session_artifacts": len(session["artifacts"]),
        "historical_top_level_token_count": session["tokens_used"],
        "per_step_usage_records": len(usage),
        "historical_accounting_defect": True,
        "controlled_followup_question_changed": True,
        "computation_counterexample_independently_checked": True,
        "actual_computation_insertion_cases": 4500,
        "matched_budget_single_role_baseline_available": False,
        "comparative_research_advantage_measured": False,
        "new_model_calls": 0,
        "new_spending_usd": 0,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(results, indent=2, sort_keys=True) + "\n")
    print("PASS archived evidence inspected; comparison not established")


if __name__ == "__main__":
    main()
