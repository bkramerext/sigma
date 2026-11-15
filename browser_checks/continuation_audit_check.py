"""Independently compare actual exported call audits with captured HTTP bodies."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/evaluations/increment_3"
manifest = json.loads((OUT / "exports/MANIFEST.json").read_text())
captures = [
    json.loads(line) for line in (OUT / "transport-captures.jsonl").read_text().splitlines()
]
rows = []
matches = 0
for project in manifest["projects"]:
    after = json.loads(
        (
            OUT
            / "exports"
            / (
                "subset.after.audit.json"
                if project["slug"] == "nonconsecutive-subset-sums"
                else "rh.after.audit.json"
            )
        ).read_text()
    )
    before = json.loads(
        (
            OUT
            / "exports"
            / (
                "subset.before.audit.json"
                if project["slug"] == "nonconsecutive-subset-sums"
                else "rh.before.audit.json"
            )
        ).read_text()
    )
    for prior in before["research_sessions"]:
        assert next(s for s in after["research_sessions"] if s["id"] == prior["id"]) == prior
    assert len({case["id"] for case in project["new_sessions"]}) == len(project["new_sessions"])
    for case in project["new_sessions"]:
        session = next(s for s in after["research_sessions"] if s["id"] == case["id"])
        for step in session["steps"]:
            audit = step["provider_input_audit"]
            body = audit["request_body"]
            encoded = json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode()
            assert hashlib.sha256(encoded).hexdigest() == audit["request_body_sha256"]
            wire = [row for row in captures if row["request_body"] == body]
            # An interrupted call can have crossed HTTP dispatch or been stopped
            # after audit preparation but before transport receipt. Don't infer it.
            if step["status"] == "completed":
                assert wire
            if wire:
                matches += 1
        packets = session.get("approved_continuations", {})
        for packet in packets.values():
            accepted = {s["artifact_id"] for s in packet["sources"]}
            for step in session["steps"]:
                body = step["provider_input_audit"]["request_body"]
                context = json.loads(body["input"])
                assert context["approved_continuation"] == packet
                assert accepted <= set(context["prior_session_artifact_ids"])
                if step["status"] == "completed":
                    assert {
                        r["artifact_id"] for r in step["output"]["continuation_reviews"]
                    } == accepted
        selected_call = next(
            (
                s
                for s in session["steps"]
                if s["role"] == "investigator" and s["cycle"] == 2 and s["status"] == "completed"
            ),
            session["steps"][-1],
        )
        selected_artifact = session["artifacts"][-1]
        rows.append(
            {
                "project": project["slug"],
                "case": case["case"],
                "session_id": session["id"],
                "approved_strategy_id": session["strategy_id"],
                "prior_artifact_ids": [
                    r["artifact_id"] for p in packets.values() for r in p["sources"]
                ],
                "selected_call_step_id": selected_call["id"],
                "request_body_sha256": selected_call["provider_input_audit"]["request_body_sha256"],
                "dispatched_question": json.loads(
                    selected_call["provider_input_audit"]["request_body"]["input"]
                )["question"],
                "new_artifact_id": selected_artifact["id"],
                "calls_used": session["calls_used"],
                "status": session["status"],
                "remaining_obligations": selected_artifact.get("open_obligations", []),
            }
        )
(OUT / "evidence-table.json").write_text(
    json.dumps(
        {
            "completed_or_interrupted_steps_matched_to_transport": matches,
            "all_five_original_sessions_export_equal": True,
            "rows": rows,
        },
        indent=2,
    )
)
lines = [
    "# Increment 3 evidence path",
    "",
    "Derived from actual SIGMA API exports and captured offline HTTP request bodies. This is an evaluator index, not a substitute export or a proof of research quality. Every completed role input matches a transport body and its saved SHA-256. Original five subset sessions compare equal before/after.",
    "",
    "| Case | Prior findings → approved strategy | Actual dispatched call → new artifact | What changed / remains open |",
    "|---|---|---|---|",
]
for row in rows:
    prior = (
        ", ".join(f"`{s}`" for s in row["prior_artifact_ids"])
        or "Evaluator-authored injection; no prior evidence"
    )
    scope = "Scripted choice only; no recurrence, density limit or RH proof."
    lines.append(
        f"| {row['project']} / {row['case']} | {prior} → `{row['approved_strategy_id']}` | Session `{row['session_id']}`, step `{row['selected_call_step_id']}` → artifact `{row['new_artifact_id']}` | {row['dispatched_question']} {scope} |"
    )
(OUT / "EVIDENCE_TABLE.md").write_text("\n".join(lines) + "\n")
print(
    f"PASS exact exported call SHA-256 and HTTP body matching ({matches} steps); all completed source acknowledgments exact; five original subset exports unchanged"
)
