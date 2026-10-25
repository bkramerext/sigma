#!/usr/bin/env python3
"""Increment 16: evaluate archived causal mechanisms without provider inference.

Outputs independently checkable observations, not a research-quality win.
"""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "docs/evaluations"


def examine():
    control = json.loads((ROOT / "increment_3/control-results.json").read_text())
    oracle = json.loads((ROOT / "increment_4/independent-results.json").read_text())
    off = control["off_second_question"]
    on = control["on_second_question"]
    assert off != on and control["stop_reloaded_same_packet"]
    assert control["original_ids_preserved"]
    # The ON question is not automatically 'better': both are mathematical
    # proposals and both require boundary checks and independent verification.
    assert "n=0,1,2" in off and "n=0,1,2" in on
    counts = oracle["subset_counts_n_0_to_18"]
    assert len(counts) == 19
    witness = oracle["new_six_step_candidate_counterexample"]
    n = witness["n"]
    predicted = 4 * counts[n + 3] + counts[n]
    actual = counts[n + 6]
    assert (actual, predicted, actual - predicted) == (
        witness["actual"], witness["predicted"], witness["residual"]
    )
    assert oracle["graph_insertion_cases"] == 4500
    assert oracle["all_original_session_objects_export_equal"]
    actual_rows = [row for row in oracle["rows"] if row.get("mode") == "actual"]
    grounded_followups = []
    for row in actual_rows:
        for link in row.get("chain", []):
            if link.get("reported_effect") != "counterexample":
                continue
            observation = json.loads(link["observation"])
            next_test = link.get("next_test", "")
            grounded_followups.append({
                "scenario": row.get("scenario"),
                "has_execution_provenance": bool(link.get("execution_id")),
                "identifies_observed_counterexample": (
                    "counterexample" in next_test.lower()
                    and all(
                        json.dumps(value) in next_test
                        for value in observation.get("witness", {}).values()
                        if isinstance(value, bool)
                    )
                    and (
                        "residual" not in observation.get("witness", {})
                        or str(observation["witness"]["residual"]) in next_test
                    )
                ),
                "requests_bounded_next_step": bool(link.get("next_investigator_step_id")),
            })
    # Independent structural oracle for the graph witness, not role prose.
    graph_rows = [r for r in actual_rows if r.get("scenario") == "graph"]
    assert len(graph_rows) == 1
    graph_links = [c for c in graph_rows[0]["chain"] if c.get("reported_effect") == "counterexample"]
    assert len(graph_links) == 1
    graph_observation = json.loads(graph_links[0]["observation"])
    graph_witness = graph_observation["witness"]
    edges = [tuple(e) for e in graph_witness["edges_before"]]
    proposed_edge = tuple(graph_witness["insert"])
    assert proposed_edge[::-1] not in edges  # naive reverse-edge rule accepts it
    adjacency = {i: [] for i in range(graph_observation["n"])}
    for a, b in edges:
        adjacency[a].append(b)
    def reachable(start, target):
        seen, pending = set(), [start]
        while pending:
            node = pending.pop()
            if node == target:
                return True
            if node in seen:
                continue
            seen.add(node)
            pending.extend(adjacency[node])
        return False
    assert reachable(proposed_edge[1], proposed_edge[0])  # forms a cycle
    assert graph_witness["candidate_accepts"] is True
    assert graph_witness["oracle_acyclic_after"] is False
    graph_followup = graph_links[0]["next_test"].lower()
    assert "reachability" in graph_followup
    assert "recomputation" in graph_followup
    subset_links = [
        c for r in actual_rows if r.get("scenario") == "subset"
        for c in r.get("chain", []) if c.get("reported_effect") == "counterexample"
    ]
    assert subset_links
    for link in subset_links:
        question = link["next_test"].lower()
        assert "residual" in question and "phase" in question
        assert "do not infer" in question  # retains global proof boundary
    assert grounded_followups
    assert all(
        row["has_execution_provenance"] and row["identifies_observed_counterexample"]
        and row["requests_bounded_next_step"] for row in grounded_followups
    )
    return {
        "evidence_transfer_changes_dispatched_question": True,
        "evidence_transfer_improves_research_quality": "UNDETERMINED",
        "both_arms_ask_for_boundary_validation": True,
        "counterexample_independently_recomputed": {
            "n": n, "actual": actual, "predicted": predicted, "residual": actual - predicted
        },
        "grounded_counterexample_followups": grounded_followups,
        "independent_graph_witness": {"reverse_edge_absent": True, "cycle_formed": True},
        "followup_quality_boundaries": {"graph_requests_reachability": True, "subset_retains_global_proof_obligation": True},
        "autonomous_unscripted_tool_choice_verified": False,
        "matched_budget_single_role_quality_comparison": False,
        "new_model_calls": 0,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    data = examine()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
    print("PASS archived causal observations; comparative quality remains undetermined")


if __name__ == "__main__":
    main()
