"""Offline synthetic negative tests for blinded pair audit: no provider calls."""

# fmt: off
import importlib.util
from copy import deepcopy
from pathlib import Path

root = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("audit14", root / "scripts/increment14_audit.py")
assert spec and spec.loader
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)
blind_spec = importlib.util.spec_from_file_location("blind14", root / "scripts/increment14_blinding.py")
assert blind_spec and blind_spec.loader
blind = importlib.util.module_from_spec(blind_spec)
blind_spec.loader.exec_module(blind)
pair = {"task_id":"X", "variant":"evidence_present", "replicate":0, "packet_sha256":"hash",
        "execution_order":["A", "B"],
        "arm_assignment":{"A":"sigma", "B":"single_role"}}
manifest = {"status":"FROZEN","freeze_approved":True,"user_approved":True,"pairs":[pair],
            "model_provider":"test","model_exact_version":"test-1","per_arm_token_cap":100,
            "per_arm_input_token_cap":60,"per_arm_output_token_cap":40,
            "per_call_input_token_cap":30,"per_call_output_token_cap":20,
            "per_arm_model_call_cap":3,"per_arm_tool_call_cap":2,
            "per_arm_wall_seconds":60,"per_arm_usd_cap":1.0,"total_usd_cap":2.0}
def record(arm):
    return {"task_id":"X","variant":"evidence_present","replicate":0,"arm_code":arm,
            "schedule_position":0 if arm == "A" else 1,
            "executed_arm":pair["arm_assignment"][arm],
            "packet_sha256":"hash","model_provider":"test","model_exact_version":"test-1",
            "total_tokens":50,"input_tokens":30,"output_tokens":20,
            "call_usage":[{"input_tokens":15,"output_tokens":10},
                          {"input_tokens":15,"output_tokens":10}],
            "model_calls":2,"tool_calls":0,"elapsed_seconds":12,
            "cost_usd":0.25,"transcript_sha256":"transcript","tool_audit_sha256":"audit",
            "normalized_submission":blind.normalize_submission(
                {"conclusion":"Answer", "reasoning":"Reason", "challenge":"Challenge",
                 "evidence":"Evidence", "uncertainty":"Uncertain", "next_test":"Test"},
                arm="single_role"),
            "schema_truncation_fields":[], "schema_validation_errors":[],
            "scores":dict.fromkeys(audit.DIMENSIONS, 3),
            "scorer_reviews":[
                {"grader_id":"g1", "scores":dict.fromkeys(audit.DIMENSIONS, 3),
                 "task_key_pass":True, "arm_guess":"uncertain", "guess_confidence":0},
                {"grader_id":"g2", "scores":dict.fromkeys(audit.DIMENSIONS, 3),
                 "task_key_pass":True, "arm_guess":"sigma", "guess_confidence":1},
            ],
            "critical_integrity_failure":False}
def seal_submission(r):
    r["submission_sha256"] = blind.digest_submission(r["normalized_submission"])
records = [record("A"),record("B")]
for r in records:
    seal_submission(r)
assert audit.check_trial_records(manifest, records, allow_partial_fixture=True)["pairs"] == 1
assert audit.check_trial_records(manifest, records, allow_partial_fixture=True)["blinding_guess_accuracy"] == 0.5
try:
    audit.check_trial_records(manifest, records)
except ValueError:
    pass
else:
    raise AssertionError("Unversioned partial fixture accepted as a full study")
assert abs(audit.weighted_score(records[0]["scores"]) - 3) < 1e-9
def rejected(changer):
    m,rs = deepcopy(manifest),deepcopy(records)
    changer(m,rs)
    try:
        audit.check_trial_records(m,rs,allow_partial_fixture=True)
    except (ValueError,KeyError):
        return
    raise AssertionError("Unsafe trial incorrectly accepted")
rejected(lambda m,r: m.update(status="DRAFT_NOT_FROZEN"))
rejected(lambda m,r: m.update(user_approved=False))
rejected(lambda m,r: r.pop())
rejected(lambda m,r: r.append(deepcopy(r[0])))
rejected(lambda m,r: r[1].update(packet_sha256="foreign"))
rejected(lambda m,r: r[1].update(schedule_position=0))
rejected(lambda m,r: r[0].update(model_exact_version="other"))
rejected(lambda m,r: r[0].update(executed_arm="single_role"))
rejected(lambda m,r: r[0].update(total_tokens=101))
rejected(lambda m,r: r[0].update(input_tokens=30.5))
rejected(lambda m,r: r[0].update(output_tokens=True))
rejected(lambda m,r: r[0].update(cost_usd=float("nan")))
rejected(lambda m,r: r[0].update(input_tokens=61,total_tokens=81))
rejected(lambda m,r: r[0].update(output_tokens=41,total_tokens=71))
rejected(lambda m,r: r[0].update(call_usage=[{"input_tokens":31,"output_tokens":10},
                                              {"input_tokens":-1,"output_tokens":10}]))
rejected(lambda m,r: r[0].update(call_usage=[{"input_tokens":15,"output_tokens":21},
                                              {"input_tokens":15,"output_tokens":-1}]))
rejected(lambda m,r: r[0].update(call_usage=[{"input_tokens":15,"output_tokens":10}]))
rejected(lambda m,r: r[0].update(call_usage=[{"input_tokens":True,"output_tokens":10},
                                              {"input_tokens":15,"output_tokens":10}]))
rejected(lambda m,r: r[0].update(cost_usd=1.2))
rejected(lambda m,r: m.update(total_usd_cap=0.2))
rejected(lambda m,r: r[0].update(transcript_sha256=""))
rejected(lambda m,r: r[0].update(scores={"correctness":4}))
rejected(lambda m,r: r[0].update(scores=dict.fromkeys(audit.DIMENSIONS, 5)))
rejected(lambda m,r: r[0].update(scorer_saw_arm_identity=True))
rejected(lambda m,r: r[0].update(submission_sha256="wrong"))
rejected(lambda m,r: r[0]["normalized_submission"].update(reasoning="x" * 3001))
rejected(lambda m,r: r[0].update(schema_truncation_fields="method"))
rejected(lambda m,r: r[0].update(scorer_reviews=[r[0]["scorer_reviews"][0]]))
rejected(lambda m,r: r[0]["scorer_reviews"][1].update(arm_identity="SIGMA"))

# Both arms have precisely the same scorer-visible shape and identity-neutral wording.
sigma = blind.normalize_submission({
    "investigator_output":{"claim":"Result", "method":"Reasoning", "evidence_status":"Evidence", "open_obligations":["Uncertain"]},
    "skeptic_output":{"solution_claim":"Answer", "argument_summary":"Reason", "response":"Challenge", "remaining_obligations":["Uncertain"], "next_question":"Test"},
}, arm="sigma")
single_role = blind.normalize_submission({
    "conclusion":"Answer", "reasoning":"Reason", "challenge":"Challenge", "evidence":"Evidence", "uncertainty":"Uncertain", "next_test":"Test"
}, arm="single_role")
assert set(blind.scorer_packet("anon-1", sigma)["submission"]) == set(blind.scorer_packet("anon-2", single_role)["submission"])
assert "arm_assignment" not in blind.scorer_packet("anon-1", sigma)
visible_values = blind.scorer_packet("anon-1", sigma)["submission"]
assert not any("sigma" in str(v).lower() or "skeptic" in str(v).lower() for k, v in visible_values.items() if k != "schema")
anon_a, packet_a = blind.new_scorer_packet(sigma)
anon_b, packet_b = blind.new_scorer_packet(single_role)
assert anon_a != anon_b
assert set(packet_a["submission"]) == set(packet_b["submission"])
long = {"conclusion":"x" * 2100, "reasoning":"r", "challenge":"c", "evidence":"e", "uncertainty":"u", "next_test":"n"}
clipped = blind.normalize_submission(long, arm="single_role")
assert clipped["clipped_fields"] == ["conclusion"] and len(clipped["conclusion"]) == 2000
assert "shared field limit reached" in blind.scorer_packet("anon-3", clipped)["submission"]["conclusion"]
upstream_cut = blind.normalize_submission(
    {"investigator_output":{"claim":"answer"}, "skeptic_output":{"solution_claim":"answer"}},
    arm="sigma", upstream_truncation_fields=["skeptic_output.solution_claim"])
assert upstream_cut["clipped_fields"] == ["conclusion"]
assert "shared field limit reached" in blind.scorer_packet("anon-4", upstream_cut)["submission"]["conclusion"]
cluster_rows = [
    {"task_id": f"T{i}", "sigma_minus_single_role": (i - 2.5) / 10}
    for i in range(6)
    for _ in range(6)
]
cluster = audit.task_cluster_summary(cluster_rows)
assert cluster["independent_units"] == 6 and cluster["within_task_pair_count"] == 36
assert len(cluster["task_cluster_means"]) == 6
rejected_cluster = False
try:
    audit.task_cluster_summary(cluster_rows[:-6])
except ValueError:
    rejected_cluster = True
assert rejected_cluster
summary = audit.check_scorer_reviews(records[0]["scorer_reviews"])
assert summary["scorer_count"] == 2 and summary["arm_guesses"]["uncertain"] == 1
print("Increment 14 blind normalization and audit adversarial checks passed")
