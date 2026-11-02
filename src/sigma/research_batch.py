"""Keep concurrently resumed persistent research sessions alive and observable."""

from __future__ import annotations

import argparse
import asyncio
import json
import signal
import sys
from pathlib import Path
from typing import Any

from sigma.local_config import load_local_config
from sigma.projects import ProjectError
from sigma.research_sessions import (
    _protocol_completion_recovery_plan,
    _read,
    control_session,
)

TERMINAL = {"completed", "ended", "failed", "paused", "stopped"}


def _parse_spec(path: Path) -> list[dict[str, Any]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ProjectError(f"Could not read JSON research spec: {exc}") from exc
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise ProjectError("Research spec must be a JSON object with schema_version 1.")
    projects = payload.get("projects")
    if not isinstance(projects, list) or not projects:
        raise ProjectError("Research spec must contain a nonempty projects array.")
    normalized: list[dict[str, Any]] = []
    seen_sessions: set[tuple[str, str]] = set()
    for index, raw in enumerate(projects):
        if not isinstance(raw, dict):
            raise ProjectError(f"Project entry {index + 1} must be an object.")
        name, project_path, project_id, session_id = (
            raw.get("name"),
            raw.get("project_path"),
            raw.get("project_id"),
            raw.get("session_id"),
        )
        additional_calls = raw.get("additional_calls", 0)
        if not isinstance(name, str) or not name.strip():
            raise ProjectError(f"Project entry {index + 1} needs a name and project_path.")
        if not isinstance(project_path, str) or not project_path.strip():
            raise ProjectError(f"Project entry {index + 1} needs a name and project_path.")
        if not isinstance(project_id, str) or not project_id.strip():
            raise ProjectError(f"Project entry {index + 1} needs project_id and session_id.")
        if not isinstance(session_id, str) or not session_id.strip():
            raise ProjectError(f"Project entry {index + 1} needs project_id and session_id.")
        if type(additional_calls) is not int or not 0 <= additional_calls <= 12:
            raise ProjectError(f"Project entry {index + 1} additional_calls must be 0..12.")
        identity = (str(Path(project_path).resolve()), session_id)
        if identity in seen_sessions:
            raise ProjectError(f"Duplicate session in research spec: {session_id}.")
        seen_sessions.add(identity)
        normalized.append(
            {
                "name": name.strip(),
                "project_path": str(Path(project_path).expanduser().resolve()),
                "project_id": project_id,
                "session_id": session_id,
                "additional_calls": additional_calls,
            }
        )
    return normalized


def _snapshot(entry: dict[str, Any]) -> dict[str, Any]:
    record = _read(entry["project_path"], entry["session_id"])
    if record.get("project_id") != entry["project_id"]:
        raise ProjectError(
            f"{entry['name']}: saved project ID does not match the JSON spec; refusing to resume."
        )
    completed = {
        (step.get("strategy_id"), step.get("role"), step.get("cycle"))
        for step in record.get("steps", [])
        if step.get("status") == "completed" and step.get("role") in {"investigator", "skeptic"}
    }
    strategy_rounds = [
        int(branch.get("cycle", 0))
        for branch in record.get("strategy_runs", [])
        if isinstance(branch.get("cycle"), int)
    ]
    step_rounds = [
        int(step.get("cycle", 0))
        for step in record.get("steps", [])
        if isinstance(step.get("cycle"), int) and step.get("role") in {"investigator", "skeptic"}
    ]
    round_number = min(
        max(1, int(record.get("cycle_limit", 1))),
        max(strategy_rounds + step_rounds + [1]),
    )
    return {
        "name": entry["name"],
        "project_path": entry["project_path"],
        "project_id": entry["project_id"],
        "session_id": entry["session_id"],
        "status": record.get("status"),
        "accepted_turns": len(completed),
        "target_turns": 12,
        "percent_complete": round(min(12, len(completed)) * 100 / 12),
        "round": round_number,
        "round_limit": int(record.get("cycle_limit", 3)),
        "calls_used": int(record.get("calls_used", 0)),
        "call_limit": int(record.get("call_limit", 0)),
        "additional_calls": entry["additional_calls"],
        "current_action": record.get("current_action"),
        "provider_usage_limited": record.get("provider_usage_limited") is True,
        "in_flight": [
            {
                "strategy": step.get("strategy_title"),
                "role": step.get("role"),
                "round": step.get("cycle"),
            }
            for step in record.get("steps", [])
            if step.get("status") == "running"
        ],
        "_record": record,
    }


def _report(snapshot: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in snapshot.items() if key != "_record"}


def _validate_resume(snapshot: dict[str, Any]) -> None:
    record = snapshot["_record"]
    if snapshot["accepted_turns"] >= 12:
        return
    if record.get("status") in {"queued", "running"}:
        if snapshot["additional_calls"]:
            raise ProjectError(
                f"{snapshot['name']}: active sessions cannot receive an attempt-limit extension."
            )
        return
    if record.get("status") == "completed":
        if snapshot["accepted_turns"] != 12:
            raise ProjectError(
                f"{snapshot['name']}: session is marked completed but has fewer than 12 accepted turns."
            )
        return
    plan, error = _protocol_completion_recovery_plan(record)
    if plan is None:
        raise ProjectError(f"{snapshot['name']}: {error or 'no safe continuation plan.'}")
    available = max(0, snapshot["call_limit"] - snapshot["calls_used"])
    exact_extension = max(0, int(plan["required_calls"]) - available)
    if snapshot["additional_calls"] != exact_extension:
        raise ProjectError(
            f"{snapshot['name']}: spec requests +{snapshot['additional_calls']} attempts, "
            f"but exact protocol shortfall is +{exact_extension}; no session was resumed."
        )


async def _watch(
    entries: list[dict[str, Any]], poll_seconds: float, max_recovery_resumes: int
) -> int:
    snapshots = [_snapshot(entry) for entry in entries]
    for snapshot in snapshots:
        _validate_resume(snapshot)
    print(
        json.dumps({"event": "preflight", "projects": [_report(item) for item in snapshots]}),
        flush=True,
    )

    stop_requested = asyncio.Event()
    loop = asyncio.get_running_loop()
    installed_signals: list[signal.Signals] = []
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop_requested.set)
            installed_signals.append(sig)
        except (NotImplementedError, RuntimeError):
            continue

    async def resume_one(snapshot: dict[str, Any]) -> tuple[str, str, str | None]:
        if snapshot["accepted_turns"] >= 12 or snapshot["status"] in {
            "queued",
            "running",
            "completed",
        }:
            return snapshot["name"], "already_active", None
        try:
            result = await control_session(
                snapshot["project_path"],
                snapshot["session_id"],
                "resume",
                additional_calls=snapshot["additional_calls"],
            )
            return snapshot["name"], str(result.get("status")), result.get("message")
        except (ProjectError, OSError, ValueError) as exc:  # keep independent sessions moving
            return snapshot["name"], "resume_error", str(exc)[:500]

    launched = await asyncio.gather(*(resume_one(item) for item in snapshots))
    for name, status, message in launched:
        print(
            json.dumps({"event": "resume", "project": name, "status": status, "message": message}),
            flush=True,
        )

    previous: dict[str, tuple[Any, ...]] = {}
    recovery_resumes = {item["session_id"]: 0 for item in entries}
    interrupted = False
    while True:
        current = [_snapshot(entry) for entry in entries]
        continuation_queued = False
        for item in current:
            if (
                item["status"] not in {"ended", "failed", "paused"}
                or item["accepted_turns"] >= 12
                or item["provider_usage_limited"]
                or recovery_resumes[item["session_id"]] >= max_recovery_resumes
            ):
                continue
            plan, error = _protocol_completion_recovery_plan(item["_record"])
            if plan is None:
                print(
                    json.dumps(
                        {
                            "event": "recovery_blocked",
                            "project": item["name"],
                            "reason": error or "No safe protocol continuation is available.",
                        }
                    ),
                    flush=True,
                )
                recovery_resumes[item["session_id"]] = max_recovery_resumes
                continue
            available = max(0, item["call_limit"] - item["calls_used"])
            additional_calls = max(0, int(plan["required_calls"]) - available)
            try:
                result = await control_session(
                    item["project_path"],
                    item["session_id"],
                    "resume",
                    additional_calls=additional_calls,
                )
                continuation_queued = True
                recovery_resumes[item["session_id"]] += 1
                print(
                    json.dumps(
                        {
                            "event": "protocol_continuation",
                            "project": item["name"],
                            "accepted_turns": item["accepted_turns"],
                            "missing_role_turns": plan["required_calls"],
                            "additional_calls": additional_calls,
                            "status": result.get("status"),
                        }
                    ),
                    flush=True,
                )
            except (ProjectError, OSError, ValueError) as exc:
                recovery_resumes[item["session_id"]] = max_recovery_resumes
                print(
                    json.dumps(
                        {
                            "event": "recovery_blocked",
                            "project": item["name"],
                            "reason": str(exc)[:500],
                        }
                    ),
                    flush=True,
                )
        for item in current:
            state = (
                item["status"],
                item["accepted_turns"],
                item["calls_used"],
                item["round"],
                item["current_action"],
                tuple((call["role"], call["round"]) for call in item["in_flight"]),
            )
            if previous.get(item["session_id"]) != state:
                print(json.dumps({"event": "progress", **_report(item)}), flush=True)
                previous[item["session_id"]] = state
        if stop_requested.is_set():
            interrupted = True
            active = [item for item in current if item["status"] in {"queued", "running"}]
            await asyncio.gather(
                *(
                    control_session(item["project_path"], item["session_id"], "pause")
                    for item in active
                ),
                return_exceptions=True,
            )
            break
        # A targeted continuation may have just moved a terminal snapshot to
        # queued. Do not exit on the stale snapshot from the top of this loop.
        if not continuation_queued and all(item["status"] in TERMINAL for item in current):
            break
        await asyncio.sleep(poll_seconds)

    final = [_snapshot(entry) for entry in entries]
    for item in final:
        print(json.dumps({"event": "final", **_report(item)}), flush=True)
    successful = all(item["accepted_turns"] == 12 for item in final)
    return 130 if interrupted else (0 if successful else 1)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Resume and supervise multiple saved SIGMA research sessions in parallel."
    )
    parser.add_argument("--spec", required=True, help="JSON project/session specification")
    parser.add_argument("--poll-seconds", type=float, default=10.0)
    parser.add_argument(
        "--max-recovery-resumes",
        type=int,
        default=12,
        help="Bound targeted continuations after recoverable incomplete stops",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Validate and print without dispatch"
    )
    return parser


def run(
    spec_path: str,
    *,
    poll_seconds: float = 10.0,
    max_recovery_resumes: int = 12,
    dry_run: bool = False,
) -> int:
    if not 0.5 <= poll_seconds <= 60:
        print("--poll-seconds must be between 0.5 and 60.", file=sys.stderr)
        return 2
    if not 0 <= max_recovery_resumes <= 12:
        print("--max-recovery-resumes must be between 0 and 12.", file=sys.stderr)
        return 2
    try:
        load_local_config()
        entries = _parse_spec(Path(spec_path).expanduser().resolve())
        snapshots = [_snapshot(entry) for entry in entries]
        for item in snapshots:
            _validate_resume(item)
        if dry_run:
            print(
                json.dumps(
                    {"event": "dry_run", "projects": [_report(item) for item in snapshots]},
                    indent=2,
                )
            )
            return 0
        return asyncio.run(_watch(entries, poll_seconds, max_recovery_resumes))
    except (ProjectError, OSError, ValueError) as exc:
        print(f"Research batch refused: {exc}", file=sys.stderr)
        return 2


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    sys.exit(
        run(
            args.spec,
            poll_seconds=args.poll_seconds,
            max_recovery_resumes=args.max_recovery_resumes,
            dry_run=args.dry_run,
        )
    )
