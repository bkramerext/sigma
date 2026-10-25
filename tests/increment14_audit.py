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
pair = {"task_id":"X", "variant":"evidence_present", "replicate":0, "packet_sha256":"hash"}
manifest = {"status":"FROZEN","freeze_approved":True,"user_approved":True,"pairs":[pair],
            "model_provider":"test","model_exact_version":"test-1","per_arm_token_cap":100,
            "per_arm_input_token_cap":60,"per_arm_output_token_cap":40,
            "per_call_input_token_cap":30,"per_call_output_token_cap":20,
            "per_arm_model_call_cap":3,"per_arm_tool_call_cap":2,
            "per_arm_wall_seconds":60,"per_arm_usd_cap":1.0,"total_usd_cap":2.0}
def record(arm):
    return {"task_id":"X","variant":"evidence_present","replicate":0,"arm_code":arm,
            "packet_sha256":"hash","model_provider":"test","model_exact_version":"test-1",
            "total_tokens":50,"input_tokens":30,"output_tokens":20,
            "call_usage":[{"input_tokens":15,"output_tokens":10},
                          {"input_tokens":15,"output_tokens":10}],
            "model_calls":2,"tool_calls":0,"elapsed_seconds":12,
            "cost_usd":0.25,"transcript_sha256":"transcript","tool_audit_sha256":"audit",
            "scores":dict.fromkeys(audit.DIMENSIONS, 3),"critical_integrity_failure":False}
records = [record("A"),record("B")]
assert audit.check_trial_records(manifest, records)["pairs"] == 1
assert abs(audit.weighted_score(records[0]["scores"]) - 3) < 1e-9
def rejected(changer):
    m,rs = deepcopy(manifest),deepcopy(records)
    changer(m,rs)
    try:
        audit.check_trial_records(m,rs)
    except (ValueError,KeyError):
        return
    raise AssertionError("Unsafe trial incorrectly accepted")
rejected(lambda m,r: m.update(status="DRAFT_NOT_FROZEN"))
rejected(lambda m,r: m.update(user_approved=False))
rejected(lambda m,r: r.pop())
rejected(lambda m,r: r.append(deepcopy(r[0])))
rejected(lambda m,r: r[1].update(packet_sha256="foreign"))
rejected(lambda m,r: r[0].update(model_exact_version="other"))
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
print("Increment 14 blinded audit rejects 13 negative conditions")
