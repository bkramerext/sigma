"""Run the real Docker sandbox through a fixture-backed Investigator/Skeptic cycle."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import httpx

from sigma import research_sessions
from sigma.projects import create_strategy, initialize_project
from sigma.python_sandbox import get_execution_artifact

MODEL = "gpt-6.1-sol"
REAL_CLIENT = httpx.AsyncClient
CODE = """import matplotlib.pyplot as plt
print('ANSWER: 79 regions for 12 lines')
fig, ax = plt.subplots()
ax.plot([0, 1, 2], [1, 2, 4])
fig.savefig('/artifacts/line-count.png')
"""


def provider_response(value: dict) -> dict:
    return {
        "status": "completed",
        "usage": {"input_tokens": 100, "output_tokens": 80},
        "output": [
            {"type": "message", "content": [{"type": "output_text", "text": json.dumps(value)}]}
        ],
    }


def main() -> None:
    with TemporaryDirectory() as temporary:
        path = Path(temporary) / "agent-python.sigma"
        view = initialize_project(
            path,
            "Line arrangement sandbox workflow",
            "Compute the number of regions formed by 12 lines in general position.",
        )
        strategy = create_strategy(
            path,
            "Finite insertion check",
            "Count regions by inserting lines and check the recurrence.",
        ).project.strategies[0]
        limits = research_sessions.get_limits(str(path))
        limits["research_rounds"] = 1
        limits["model_calls"] = 2
        limits = research_sessions.save_limits(str(path), limits)
        credential = {
            "identity": "fixture-account",
            "mode": "api_key",
            "token": "fixture-token",
            "status": "connected",
        }
        config = {"available": True, "model": MODEL, "reasoning_effort": "high"}
        observed: dict = {}

        async def handler(request: httpx.Request) -> httpx.Response:
            payload = json.loads(request.content)
            role = payload["text"]["format"]["name"]
            context = json.loads(payload["input"])
            if role == "research_investigator":
                result = {
                    "claim": "The insertion recurrence gives 79 regions for 12 lines.",
                    "method": "Evaluate the finite recurrence and compare it with the formula.",
                    "assumptions": ["The 12 lines are in general position."],
                    "evidence_status": "Candidate finite computation; Skeptic review required.",
                    "open_obligations": ["Review the source and execution output."],
                    "python_code": CODE,
                }
            else:
                investigation = context["investigator_output"]
                execution = investigation["python_execution"]
                assert investigation["python_code"] == CODE
                assert execution["source"] == CODE
                assert execution["status"] == "completed", execution
                assert "ANSWER: 79 regions" in execution["stdout"]
                assert execution["artifacts"][0]["filename"] == "line-count.png"
                observed.update({"id": execution["id"], "artifact": execution["artifacts"][0]})
                result = {
                    "assessment": "stop",
                    "stop_reason": "productive_conclusion",
                    "response": "The finite run and source agree on the reported value; this does not prove the general formula.",
                    "objections": [
                        "This finite case does not establish the formula for all line counts."
                    ],
                    "remaining_obligations": ["Prove the insertion recurrence for arbitrary n."],
                    "next_question": "Prove the recurrence for arbitrary n.",
                    "objective_status": "partial",
                    "solution_claim": "The finite computation reports 79 regions for 12 lines.",
                    "argument_summary": "The computation checks this finite case only.",
                    "assumptions_reviewed": ["The 12 lines are in general position."],
                    "proof_obligations": ["Prove the recurrence for arbitrary n."],
                    "unresolved_objections": [],
                    "supporting_cycles": [1],
                    "verification_status": "incomplete",
                    "strategy_contribution": "productive",
                    "contribution_rationale": "The bounded computation checks the selected finite case.",
                }
            return httpx.Response(200, json=provider_response(result))

        async def run() -> dict:
            with (
                patch.object(
                    research_sessions,
                    "auth_context",
                    new=AsyncMock(return_value=credential),
                ),
                patch.object(
                    research_sessions,
                    "configuration",
                    new=AsyncMock(return_value=config),
                ),
                patch(
                    "sigma.research_sessions.httpx.AsyncClient",
                    side_effect=lambda **kwargs: REAL_CLIENT(
                        transport=httpx.MockTransport(handler), **kwargs
                    ),
                ),
            ):
                started = await research_sessions.start_session(
                    str(path),
                    strategy.id,
                    str(uuid4()),
                    view.project.id,
                    credential["identity"],
                    expected_limits=limits,
                )
                for _ in range(500):
                    session = research_sessions.get_session(str(path), started["id"])
                    if session["status"] in {"completed", "ended", "failed", "stopped", "paused"}:
                        return session
                    await asyncio.sleep(0.01)
            raise AssertionError("fixture-backed research session did not finish")

        finished = asyncio.run(run())
        assert finished["status"] == "ended", finished
        artifact = finished["artifacts"][0]["investigator_output"]["python_execution"]
        assert artifact["id"] == observed["id"]
        assert finished["steps"][0]["output"]["python_execution"]["status"] == "completed"
        content, media_type = get_execution_artifact(str(path), observed["id"], "line-count.png")
        assert media_type == "image/png" and content.startswith(b"\x89PNG\r\n\x1a\n")
        print(
            "PASS fixture-backed Investigator→Docker sandbox→Skeptic workflow "
            f"(execution {observed['id']}, captured {len(content)}-byte PNG)"
        )


if __name__ == "__main__":
    main()
