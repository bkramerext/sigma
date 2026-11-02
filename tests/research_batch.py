"""Regression checks for safe multi-session research continuation."""

from __future__ import annotations

import asyncio
from unittest.mock import patch

from sigma import research_batch


async def test_supervisor_waits_after_targeted_continuation() -> None:
    state = {
        "name": "Xenopus",
        "project_path": "/tmp/xenopus.sigma",
        "project_id": "project-id",
        "session_id": "session-id",
        "status": "ended",
        "accepted_turns": 8,
        "target_turns": 12,
        "percent_complete": 67,
        "round": 3,
        "round_limit": 3,
        "calls_used": 14,
        "call_limit": 17,
        "additional_calls": 0,
        "current_action": "Ended · research incomplete",
        "provider_usage_limited": False,
        "in_flight": [],
        "_record": {},
    }
    entry = {
        "name": state["name"],
        "project_path": state["project_path"],
        "project_id": state["project_id"],
        "session_id": state["session_id"],
        "additional_calls": 0,
    }
    control_calls: list[int] = []

    async def control_session(*_args, additional_calls: int = 0, **_kwargs):
        control_calls.append(additional_calls)
        if len(control_calls) == 1:
            # Initial resume quickly reaches a recoverable terminal state.
            return {"status": "ended", "message": "Known invalid response."}
        assert additional_calls == 1
        state["status"] = "queued"
        state["call_limit"] = 18
        return {"status": "queued", "message": "Targeted continuation queued."}

    async def sleep_then_complete(_seconds: float) -> None:
        state["status"] = "ended"
        state["accepted_turns"] = 12
        state["percent_complete"] = 100
        state["calls_used"] = 18
        state["current_action"] = "Ended · protocol complete"

    with (
        patch.object(research_batch, "_snapshot", side_effect=lambda _entry: dict(state)),
        patch.object(research_batch, "_validate_resume"),
        patch.object(
            research_batch,
            "_protocol_completion_recovery_plan",
            return_value=({"required_calls": 4}, None),
        ),
        patch.object(research_batch, "control_session", new=control_session),
        patch("sigma.research_batch.asyncio.sleep", new=sleep_then_complete),
    ):
        result = await research_batch._watch([entry], poll_seconds=0.5, max_recovery_resumes=12)

    assert result == 0
    assert control_calls == [0, 1]
    assert state["accepted_turns"] == 12


def main() -> None:
    asyncio.run(test_supervisor_waits_after_targeted_continuation())
    print("Research batch targeted-continuation lifecycle passed.")


if __name__ == "__main__":
    main()
