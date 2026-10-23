"""Explicit, bounded research evaluation using the already selected ChatGPT plan.

Never selects a billing mode or falls back to API-key billing. Not run by the
test suite. Invoke with --run only when real plan-backed work is authorized.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from sigma import research_sessions
from sigma.openai_connection import auth_context
from sigma.projects import ProjectError, create_strategy, initialize_project, inspect_project
from sigma.proposals import configuration


async def plan_only():
    context = await auth_context()
    if context.get("mode") != "chatgpt" or context.get("status") != "connected":
        raise ProjectError(
            "Evaluation requires the already selected connected ChatGPT plan; no call or billing switch is permitted"
        )
    return context


async def run(
    path: Path, effort: str, output_tokens: int, rounds: int, continue_project: bool
) -> None:
    credential = await plan_only()
    if continue_project:
        view = inspect_project(path)
        if view.project.ai_model != "gpt-6.1-sol" or view.project.reasoning_effort != effort:
            raise ProjectError(
                "Existing project configuration differs; the evaluation will not rewrite it"
            )
        strategy = next(
            item for item in view.project.strategies if item.enabled and item.removed_at is None
        )
    else:
        view = initialize_project(
            path,
            "Small-argument square-root response",
            "Assess whether direct double-precision evaluation of f(x)=(sqrt(1+x)-1)/x is reliable for positive x from 1e-18 through 1e-2. Give a concrete recommendation with reproducible evidence and state the limitations of observations and of any general claim.",
            ai_model="gpt-6.1-sol",
            reasoning_effort=effort,
        )
        strategy = create_strategy(
            path,
            "Numerical reliability investigation",
            "Investigate numerical reliability, challenge candidate explanations with measurable tests, and follow the evidence.",
        ).project.strategies[0]
    config = await configuration(view=view, context=credential)
    if not config["available"]:
        raise ProjectError(
            "The selected model is unavailable; no alternative or billing fallback was attempted"
        )
    limits = research_sessions.get_limits(str(path))
    limits.update(
        research_rounds=rounds,
        model_calls=2 * rounds,
        session_duration_minutes=5,
        output_tokens_per_call=output_tokens,
    )
    limits = research_sessions.save_limits(str(path), limits)
    print(
        json.dumps(
            {
                "path": str(path),
                "mode": "chatgpt",
                "model": config["model"],
                "call_cap": limits["model_calls"],
            }
        ),
        flush=True,
    )
    started_at = time.monotonic()
    with patch.object(research_sessions, "auth_context", new=plan_only):
        started = await research_sessions.start_session(
            str(path),
            strategy.id,
            str(uuid4()),
            view.project.id,
            credential["identity"],
            expected_limits=limits,
        )
        count = 0
        while True:
            session = research_sessions.get_session(str(path), started["id"])
            for event in session["events"][count:]:
                print(
                    json.dumps(
                        {
                            "elapsed_seconds": round(time.monotonic() - started_at, 1),
                            "kind": event["kind"],
                            "message": event["message"],
                        }
                    ),
                    flush=True,
                )
            count = len(session["events"])
            if session["status"] in {"ended", "completed", "failed", "stopped", "paused"}:
                break
            if time.monotonic() - started_at > 300:
                await research_sessions.control_session(str(path), started["id"], "stop")
                continue
            await asyncio.sleep(0.5)
    summary = {
        "mode": session["mode"],
        "status": session["status"],
        "session_id": session["id"],
        "calls_used": session["calls_used"],
        "elapsed_seconds": round(time.monotonic() - started_at, 1),
        "artifacts": len(session["artifacts"]),
        "executions": [
            step["output"]["python_execution"]
            for step in session["steps"]
            if isinstance(step.get("output"), dict) and step["output"].get("python_execution")
        ],
    }
    (path / f"evaluation-summary-{session['id']}.json").write_text(
        json.dumps(summary, indent=2) + "\n"
    )
    if not (path / "evaluation-summary.json").exists():
        (path / "evaluation-summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(
        json.dumps(
            {
                "status": summary["status"],
                "calls_used": summary["calls_used"],
                "artifacts": summary["artifacts"],
                "executions": len(summary["executions"]),
                "elapsed_seconds": summary["elapsed_seconds"],
                "session_id": summary["session_id"],
            }
        ),
        flush=True,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--run", action="store_true", help="Explicitly run a real ChatGPT-plan evaluation"
    )
    parser.add_argument("--project", type=Path)
    parser.add_argument("--reasoning-effort", choices=("medium", "high"), default="high")
    parser.add_argument("--output-tokens", type=int, choices=(2048, 4096), default=4096)
    parser.add_argument("--rounds", type=int, choices=(1, 2), default=2)
    parser.add_argument(
        "--continue-project",
        action="store_true",
        help="Start a new bounded session in the existing evaluation project, preserving prior evidence",
    )
    args = parser.parse_args()
    if not args.run:
        parser.error("--run is required; this evaluation uses real plan allowance")
    path = args.project or Path("projects") / f"a19-plan-stability-{uuid4().hex[:8]}.sigma"
    asyncio.run(
        run(
            path.resolve(),
            args.reasoning_effort,
            args.output_tokens,
            args.rounds,
            args.continue_project,
        )
    )


if __name__ == "__main__":
    main()
