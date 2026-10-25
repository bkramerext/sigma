"""Offline adversarial regression for Increment 14 protocol and answer-key integrity."""

# fmt: off
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("protocol14", ROOT / "scripts/increment14_protocol.py")
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

data = module.validate()
assert len(data["tasks"]) == 6
manifest1 = module.manifest(140017, 1)
manifest2 = module.manifest(140017, 1)
assert manifest1 == manifest2
assert manifest1["paired_runs"] == 12 and manifest1["total_arm_runs"] == 24
assert not manifest1["user_approved"] and not manifest1["freeze_approved"]
assert manifest1["per_arm_input_token_cap"] == 48000
assert manifest1["per_arm_output_token_cap"] == 16000
assert manifest1["per_call_output_token_cap"] == 4000
assert manifest1["per_arm_model_call_cap"] == 4
assert manifest1["per_arm_usd_cap"] == 0.55 and abs(manifest1["total_usd_cap"] - 13.20) < 1e-9
assert len({(x["task_id"], x["variant"], x["replicate"]) for x in manifest1["pairs"]}) == 12
assert len({x["packet_sha256"] for x in manifest1["pairs"]}) == 12
assert module.manifest(140018, 1)["pairs"] != manifest1["pairs"]
repeated = module.manifest(140017, 3)
assert repeated["paired_runs"] == 36 and repeated["total_arm_runs"] == 72
assert abs(repeated["total_usd_cap"] - 39.60) < 1e-9
assert repeated["independent_task_count"] == 6 and repeated["analysis_unit"] == "task_cluster"
for entry in manifest1["pairs"]:
    assert sorted(entry["execution_order"]) == ["A", "B"]
    assert set(entry["arm_assignment"]) == {"A", "B"}
    assert set(entry["arm_assignment"].values()) == {"sigma", "single_role"}
assert "evaluator" not in json.dumps(data).lower()

# Independently verify the graph fixture: all degrees 3, no 3- or 4-cycles.
nodes = [("a", i) for i in range(5)] + [("b", i) for i in range(5)]
adj = {n: set() for n in nodes}
def edge(u, v):
    adj[u].add(v)
    adj[v].add(u)
for i in range(5):
    edge(("a", i), ("a", (i+1)%5))
    edge(("a", i), ("b", i))
    edge(("b", i), ("b", (i+2)%5))
assert all(len(adj[n]) == 3 for n in nodes)
for a in nodes:
    for b in adj[a]:
        for c in adj[b] - {a}:
            assert a not in adj[c]
            for d in adj[c] - {a,b}:
                assert a not in adj[d]

# Independently verify the deficient matching subset.
compat = {"T1":{"A","B"}, "T2":{"A","B"}, "T3":{"A","B"},
          "T4":{"C","D","E"}, "T5":{"C","D","E"}}
assert len(set.union(*(compat[k] for k in ("T1","T2","T3")))) == 2
assert sum([60,50]) == 110
assert max(60,50) < 110

packet_spec = importlib.util.spec_from_file_location("packet14", ROOT / "scripts/increment14_agent_packet.py")
assert packet_spec and packet_spec.loader
packet_module = importlib.util.module_from_spec(packet_spec)
packet_spec.loader.exec_module(packet_module)
for task in data["tasks"]:
    for variant in ("evidence_present", "evidence_withheld"):
        packet = packet_module.agent_packet(task["id"], variant)
        assert set(packet) == {"instruction", "question", "evidence"}
        assert "scoring_dimensions" not in json.dumps(packet)
        assert module.sha256(module.canonical_bytes(packet)) in {p["packet_sha256"] for p in manifest1["pairs"]}
try:
    packet_module.agent_packet("INVALID", "evidence_present")
except ValueError:
    pass
else:
    raise AssertionError("Invalid task accepted")
try:
    packet_module.agent_packet("M1", "../evaluator_only.md")
except ValueError:
    pass
else:
    raise AssertionError("Invalid variant accepted")
print("Increment 14 adversarial offline checks passed")
