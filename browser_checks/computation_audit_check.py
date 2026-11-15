"""Actual exports → execution → observed feedback → next actual call + exact oracle.
No program from the provider is evaluated on the host. Oracles are independent.
"""

import hashlib
import json
import os
from collections import Counter
from copy import deepcopy
from itertools import combinations, permutations
from pathlib import Path

from sigma.continuations import compact_dispatch_packet, expand_dispatch_packet
from sigma.research_sessions import _outcome_conclusion

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(os.environ.get("SIGMA_COMPUTATION_OUTPUT_DIR", ROOT / "docs/evaluations/increment_4"))
EXP = OUT / "exports"
m = json.loads((EXP / "MANIFEST.json").read_text())
captures = [
    json.loads(line) for line in (OUT / "transport-captures.jsonl").read_text().splitlines()
]
executions = {
    r["id"]: r
    for file in EXP.glob("execution.*.json")
    if "observation" not in file.name
    for r in [json.loads(file.read_text())]
}

# Independent subset oracle enumerates masks; session program uses residue/last-bit DP.
counts = []
for n in range(19):
    count = 0
    for mask in range(1 << n):
        if mask & (mask << 1):
            continue
        if sum(i + 1 for i in range(n) if mask >> i & 1) % 3 == 0:
            count += 1
    counts.append(count)
assert counts[12] == 128
first = next(
    {
        "n": n,
        "actual": counts[n + 6],
        "predicted": 4 * counts[n + 3] + counts[n],
        "residual": counts[n + 6] - 4 * counts[n + 3] - counts[n],
    }
    for n in range(13)
    if counts[n + 6] != 4 * counts[n + 3] + counts[n]
)


# Independent graph oracle enumerates topological orders, not Kahn/DFS.
def topological_orders(n, edges):
    return [
        order
        for order in permutations(range(n))
        if all(order.index(u) < order.index(v) for u, v in edges)
    ]


dags = set()
for order in permutations(range(4)):
    forward = list(combinations(order, 2))
    for mask in range(1 << len(forward)):
        dags.add(frozenset(edge for i, edge in enumerate(forward) if mask >> i & 1))
possible = list(permutations(range(4), 2))
oracle_checks = 0
for edges in dags:
    orders = topological_orders(4, edges)
    for u, v in possible:
        if (u, v) in edges:
            continue
        oracle_checks += 1
        direct = topological_orders(4, set(edges) | {(u, v)})
        # v precedes u in every valid topological order iff adding u->v creates
        # a cycle. This independent ordering characterization checks the scope.
        assert bool(direct) == any(order.index(u) < order.index(v) for order in orders)

rows = []
profiles = []
matched = 0
full_steps = 0
for project in m["projects"]:
    prefix = "subset" if project["slug"] == "nonconsecutive-subset-sums" else "algorithm"
    before = json.loads((EXP / f"{prefix}.before.audit.json").read_text())
    after = json.loads((EXP / f"{prefix}.after.audit.json").read_text())
    assert all(
        next(s for s in after["research_sessions"] if s["id"] == old["id"]) == old
        for old in before["research_sessions"]
    )
    for run in [r for r in m["runs"] if r["project_id"] == project["project_id"]]:
        session = next(s for s in after["research_sessions"] if s["id"] == run["session_id"])
        calls = [
            r
            for r in captures
            if json.loads(r["request_body"]["input"])["strategy"]["id"] == run["strategy_id"]
        ]
        saved = [r for r in executions.values() if r["session_id"] == run["session_id"]]
        if run["mode"] == "withheld":
            assert saved == [] and all(r["observed_execution_id"] is None for r in calls)
        for execution in saved:
            if OUT.name == "increment_5":
                origin = execution.get("agent")
                assert origin and origin["role"] == "investigator", execution
                assert origin["model"] == session["model"]
                assert any(
                    step["id"] == origin["step_id"]
                    and step["role"] == "investigator"
                    and step["strategy_id"] == run["strategy_id"]
                    for step in session["steps"]
                ), execution
            assert (
                hashlib.sha256(execution["source"].encode()).hexdigest()
                == execution["source_sha256"]
            )
            assert (
                execution["environment"]["network"] == "none"
                and execution["environment"]["cpu_limit"] == 1
            )
            if execution["status"] == "completed":
                assert execution["exit_code"] == 0
                observed = json.loads(execution["stdout"])
                if "values" in observed:
                    assert observed["values"] == counts and observed["witness"] == first
                if observed["test"] == "residue_separated_residuals":
                    assert observed["residuals_by_n_mod_3"] == {
                        str(r): [
                            counts[n + 6] - 4 * counts[n + 3] - counts[n] for n in range(r, 13, 3)
                        ]
                        for r in range(3)
                    }
                if observed["test"] == "reverse_edge_only_cycle_guard":
                    w = observed["witness"]
                    edges = set(map(tuple, w["edges_before"]))
                    edge = tuple(w["insert"])
                    assert (
                        topological_orders(3, edges)
                        and (edge[1], edge[0]) not in edges
                        and not topological_orders(3, edges | {edge})
                    )
                if observed["test"] == "reachability_guard_finite_regression":
                    assert observed["checks"] == oracle_checks and observed["mismatch"] is None
            for artifact in execution.get("artifacts", []):
                raw = (EXP / f"execution.{execution['id']}.{artifact['filename']}").read_bytes()
                assert hashlib.sha256(raw).hexdigest() == artifact["sha256"]
                assert json.loads(raw) == json.loads(execution["stdout"])
        statuses = Counter(e["status"] for e in saved)
        expected = {
            "actual": {"completed": 2},
            "withheld": {},
            "error": {"failed": 1},
            "timeout": {"timeout": 1},
            "sage": {"completed": 1},
            "invalid_feedback": {"completed": 1},
            "restart": {"interrupted": 1, "completed": 1},
        }[run["mode"]]
        assert statuses == Counter(expected), (run, statuses)
        if run["mode"] == "invalid_feedback":
            assert session["status"] == "failed" and not session["artifacts"] and len(calls) == 2
        chain = []
        for step in session["steps"]:
            full_steps += 1
            body = step["provider_input_audit"]["request_body"]
            wire = [r for r in calls if r["request_body"] == body]
            assert (
                wire
                and hashlib.sha256(
                    json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode()
                ).hexdigest()
                == step["provider_input_audit"]["request_body_sha256"]
            )
            matched += 1
            context = json.loads(body["input"])
            packet = context.get("approved_continuation")
            if packet:
                expanded = expand_dispatch_packet(packet)
                assert expanded == session["approved_continuations"][step["strategy_id"]]
                baseline = deepcopy(context)
                if OUT.name == "increment_5":
                    assert packet == expanded and "dispatch_text_pool" not in packet
                    baseline["approved_continuation"] = compact_dispatch_packet(packet)
                else:
                    baseline["approved_continuation"] = expanded
                profiles.append(
                    {
                        "session_id": session["id"],
                        "step_id": step["id"],
                        "actual_dispatch_bytes": len(body["input"].encode()),
                        "paired_alternative_encoding_bytes": len(
                            json.dumps(baseline, ensure_ascii=False).encode()
                        ),
                        "selected_source_ids": [s["artifact_id"] for s in packet["sources"]],
                        "full_source_coverage": True,
                        "measurement": "Actual dispatched encoding vs deterministic opposite encoding of same context; alternative is NOT a separate provider call.",
                    }
                )
            feedback = (step.get("output") or {}).get("computation_feedback")
            if feedback:
                execution = executions[feedback["execution_id"]]
                assert (
                    feedback["observed_text_sha256"]
                    == hashlib.sha256(execution[feedback["observed_field"]].encode()).hexdigest()
                )
                assert feedback["observed_status"] == execution["status"]
                if execution["status"] != "completed":
                    assert feedback["reported_effect"] == "inconclusive"
                chain.append(
                    {
                        "skeptic_step_id": step["id"],
                        "execution_id": execution["id"],
                        "reported_effect": feedback["reported_effect"],
                        "observation": execution.get("stdout") or execution.get("stderr"),
                        "next_test": feedback["next_test"],
                    }
                )
                next_call = next(
                    (
                        x
                        for x in session["steps"]
                        if x["role"] == "investigator" and x["cycle"] == step["cycle"] + 1
                    ),
                    None,
                )
                if next_call:
                    following = json.loads(
                        next_call["provider_input_audit"]["request_body"]["input"]
                    )
                    assert following["question"] == feedback["next_test"]
                    assert execution["id"] in json.dumps(following) and execution[
                        "source_sha256"
                    ] in json.dumps(following)
                    chain[-1]["next_investigator_step_id"] = next_call["id"]
        raw_record = json.loads(
            (Path(project["path"]) / "research-sessions" / f"{session['id']}.json").read_text()
        )
        legacy = deepcopy(raw_record)
        legacy["research_context_version"] = 1
        legacy_summary = _outcome_conclusion(legacy, session["outcome"])
        rows.append(
            {
                **run,
                "status": session["status"],
                "execution_ids": [e["id"] for e in saved],
                "execution_statuses": dict(statuses),
                "chain": chain,
                "actual_conclusion_characters": len(session["outcome"]["conclusion"]),
                "legacy_render_baseline_characters": len(legacy_summary),
                "summary_baseline_scope": "Deterministic legacy renderer on same saved data, not a historical rewrite or extra research run.",
            }
        )
        if run["mode"] in {"actual", "withheld"}:
            second = next(x for x in calls if x["role"] == "investigator" and x["cycle"] == 2)
            if run["mode"] == "actual":
                assert (
                    second["observed_execution_id"] is not None
                    and "Observed counterexample"
                    in json.loads(second["request_body"]["input"])["question"]
                )
            else:
                assert second["observed_execution_id"] is None and all(
                    not x["response"]["computational_citations"] for x in calls
                )
assert matched == len(captures) == 28
result = {
    "scope": "Independent finite enumeration/logical oracle; not an autonomous reasoning or general theorem claim",
    "subset_counts_n_0_to_18": counts,
    "new_six_step_candidate_counterexample": first,
    "graph_four_vertex_DAGs": len(dags),
    "graph_insertion_cases": oracle_checks,
    "all_original_session_objects_export_equal": True,
    "matched_actual_calls": matched,
    "executions": len(executions),
    "statuses": dict(Counter(e["status"] for e in executions.values())),
    "rows": rows,
}
(OUT / "independent-results.json").write_text(json.dumps(result, indent=2))
(OUT / "context-budget.json").write_text(
    json.dumps(
        {
            "scope": "Paired deterministic encoding/render baseline; actual dispatched calls and actual new Conclusions on the other side. Increment 5 dispatches full literal text; compact pooling is an untested hypothetical alternative. Exact reconstruction and all selected sources verified. No semantic source selection or truncation.",
            "contexts": profiles,
            "summaries": [
                {
                    "session_id": r["session_id"],
                    "actual": r["actual_conclusion_characters"],
                    "legacy_baseline": r["legacy_render_baseline_characters"],
                }
                for r in rows
            ],
        },
        indent=2,
    )
)
print(
    f"PASS {matched} actual call bodies/hashes, {len(executions)} actual execution records, exact subset/Sage outputs, {len(dags)} four-vertex DAGs/{oracle_checks} insertion cases, no-computation/error/timeout/invalid-hash/restart controls, lossless source coverage"
)
