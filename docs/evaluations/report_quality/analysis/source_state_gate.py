"""Extract a small, non-sensitive research-completeness ledger from SIGMA bundles.

Reads a frozen SIGMA project bundle; does not rewrite it, send provider calls,
or infer that an ended session is scientifically complete. The output is a
review aid and contains only status/ID metadata, not provider request payloads.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def extract(bundle: dict) -> dict:
    files = bundle.get("files", {})
    sessions = []
    for path, record in sorted(files.items()):
        if not (path.startswith("research-sessions/") and path.endswith(".json")):
            continue
        if path.rsplit("/", 1)[-1] in {"limits.json", "sequence.json", "obligation-ids.json"}:
            continue
        if not isinstance(record, dict) or "steps" not in record:
            continue
        steps = record.get("steps") or []
        artifacts = record.get("artifacts") or []
        failed = [
            {
                "call_number": step.get("call_number"),
                "id": step.get("id"),
                "role": step.get("role"),
                "status": step.get("status"),
                "failure_kind": step.get("failure_kind"),
                "request_status": (step.get("provider_input_audit") or {}).get("status"),
            }
            for step in steps
            if step.get("status") != "completed"
        ]
        sessions.append(
            {
                "file": path,
                "session_id": record.get("id"),
                "status": record.get("status"),
                "termination_reason_code": record.get("termination_reason_code"),
                "terminal_reason": record.get("terminal_reason"),
                "step_count": len(steps),
                "artifact_count": len(artifacts),
                "failed_or_incomplete_steps": failed,
                "artifact_verification": [
                    {
                        "artifact_id": a.get("id"),
                        "verification_status": (a.get("skeptic_output") or {}).get(
                            "verification_status"
                        ),
                        "objective_status": (a.get("skeptic_output") or {}).get("objective_status"),
                    }
                    for a in artifacts
                ],
            }
        )
    project = files.get("project.json", {})
    return {
        "project_id": project.get("id"),
        "project_title": project.get("title"),
        "sessions": sessions,
        "scope": "saved status metadata; not independent verification of research claims",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    args = parser.parse_args()
    data = json.loads(args.bundle.read_text(encoding="utf-8"))
    print(json.dumps(extract(data), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
