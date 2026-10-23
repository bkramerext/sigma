"""Cloud research start, status and cross-owner API workflow with a fake provider."""

from __future__ import annotations

import os
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import AsyncMock, patch
from uuid import uuid4


def main() -> None:
    with TemporaryDirectory(prefix="sigma-cloud-api-", dir=Path.cwd().parent) as temporary:
        root = Path(temporary)
        root.chmod(0o700)
        for name in ("workspaces", "local-projects", "local-state"):
            (root / name).mkdir(mode=0o700)
        environment = {
            "SIGMA_CLOUD_AUTH_ENABLED": "true",
            "SIGMA_CLOUD_WORKSPACES_ROOT": str(root / "workspaces"),
            "SIGMA_PROJECTS_ROOT": str(root / "local-projects"),
            "SIGMA_STATE_DIR": str(root / "local-state"),
            "SIGMA_CLOUD_OPENAI_API_KEY": "fake-server-credential",
            "SIGMA_CLOUD_GLOBAL_SPEND_CEILING_USD": "1.00",
            "SIGMA_CLOUD_USER_SPEND_CEILING_USD": "0.25",
            "SIGMA_CLOUD_USER_MAX_CONCURRENT": "1",
            "SIGMA_CLOUD_GLOBAL_MAX_CONCURRENT": "2",
            "SIGMA_CLOUD_USER_MAX_QUEUED": "2",
            "SIGMA_CLOUD_GLOBAL_MAX_QUEUED": "4",
            "SIGMA_CLOUD_USER_TOKEN_BUDGET": "1000000",
        }
        with patch.dict(os.environ, environment, clear=False):
            # This isolated test app attaches deterministic verified principals
            # but otherwise uses the production FastAPI router and workspace scope.
            import cloud_workspace_test_app
            from fastapi.testclient import TestClient

            from sigma import cloud_research, research_sessions

            credential = {
                "mode": "api_key",
                "identity": "cloud_service_api_key",
                "token": "fake-server-credential",
                "status": "connected",
            }
            config = {
                "available": True,
                "model": "gpt-6.1-sol",
                "reasoning_effort": "high",
            }
            investigator = {
                "claim": "An induction suggests the recurrence bound.",
                "method": "Apply the recurrence once and check the base case.",
                "assumptions": ["The recurrence is valid at positive indices."],
                "evidence_status": "Unverified model derivation.",
                "open_obligations": ["Check the base case."],
                "python_code": None,
                "sage_code": None,
                "prior_session_failure_attempt_ids": [],
                "human_guidance_reviews": [],
                "computational_citations": [],
            }
            skeptic = {
                "assessment": "continue",
                "stop_reason": "recoverable_objection",
                "response": "The base case remains to be checked.",
                "objections": ["Verify the first value."],
                "remaining_obligations": ["Verify the first value."],
                "next_question": "Check the recurrence at its first index.",
                "objective_status": "partial",
                "solution_claim": "A partial bound is plausible.",
                "argument_summary": "The recurrence step is plausible but not a proof.",
                "assumptions_reviewed": ["The recurrence is valid at positive indices."],
                "proof_obligations": ["Verify the first value."],
                "unresolved_objections": ["Verify the first value."],
                "supporting_cycles": [1],
                "verification_status": "incomplete",
                "strategy_contribution": "productive",
                "contribution_rationale": "The remaining check is now explicit.",
                "cross_strategy_relations": [],
                "retracted_cross_strategy_source_artifact_ids": [],
                "peer_handoff_reviews": [],
                "human_guidance_reviews": [],
                "computational_citations": [],
            }
            usage = {
                "input_tokens": 90,
                "cached_input_tokens": 0,
                "output_tokens": 30,
            }

            async def fake_call(record, role, context, timeout_seconds=None):
                del record, context, timeout_seconds
                return (investigator if role == "investigator" else skeptic), usage

            settings = {
                "research_rounds": 5,
                "model_calls": 30,
                "session_duration_minutes": 60,
                "output_tokens_per_call": 256,
                "maximum_estimated_cost_usd": 1.0,
            }
            with (
                patch.object(
                    research_sessions, "auth_context", new=AsyncMock(return_value=credential)
                ),
                patch.object(
                    research_sessions, "configuration", new=AsyncMock(return_value=config)
                ),
                patch.object(research_sessions, "execution_capabilities", return_value=[]),
                patch.object(
                    research_sessions, "_call", new=AsyncMock(side_effect=fake_call)
                ) as calls,
                TestClient(cloud_workspace_test_app.app) as client,
            ):
                client.headers.update(
                    {"X-Test-Subject": "cloud-a", "X-Test-Email": "a@example.test"}
                )
                created = client.post(
                    "/api/projects/create",
                    json={"title": "Cloud research API", "problem": "A recurrence bound"},
                )
                assert created.status_code == 201, created.text
                path = created.json()["path"]
                project_id = created.json()["project"]["id"]
                strategy_response = client.post(
                    "/api/projects/strategies",
                    json={
                        "path": path,
                        "title": "Induction",
                        "approach": "Check recurrence bounds by induction.",
                    },
                )
                assert strategy_response.status_code == 201, strategy_response.text
                strategy = client.get("/api/projects/strategies", params={"path": path})
                strategy_id = strategy.json()["strategies"][0]["id"]
                limits = client.put(
                    "/api/projects/research-limits", json={"path": path, **settings}
                )
                assert limits.status_code == 200, limits.text
                assert limits.json()["model_calls"] == 6
                assert limits.json()["research_rounds"] == 3
                assert limits.json()["session_duration_minutes"] == 15
                assert limits.json()["maximum_estimated_cost_usd"] == 0.25
                key = str(uuid4())
                start_body = {
                    "path": path,
                    "strategy_id": strategy_id,
                    "idempotency_key": key,
                    "expected_project_id": project_id,
                    "expected_binding": credential["identity"],
                    "expected_limits": limits.json(),
                }
                started = client.post("/api/projects/research-sessions/start", json=start_body)
                assert started.status_code == 200, started.text
                session_id = started.json()["id"]

                # A new request context sees the saved authoritative status;
                # the provider task is no longer tied to the start request.
                for _ in range(500):
                    status = client.get(
                        f"/api/projects/research-sessions/{session_id}", params={"path": path}
                    )
                    assert status.status_code == 200, status.text
                    saved = status.json()
                    if saved["status"] in {"ended", "failed", "paused"}:
                        break
                    time.sleep(0.01)
                else:
                    raise AssertionError("HTTP-started cloud research did not reach a saved state")
                assert saved["status"] == "ended"
                assert len(saved["steps"]) == 6
                assert calls.await_count == 6
                duplicate = client.post("/api/projects/research-sessions/start", json=start_body)
                assert duplicate.status_code == 200, duplicate.text
                assert duplicate.json()["id"] == session_id
                assert calls.await_count == 6

                budget = client.get(
                    "/api/cloud-research/budget",
                    params={"workspace_id": "cloud-b", "owner": "cloud-b"},
                )
                assert budget.status_code == 200, budget.text
                assert budget.headers["cache-control"] == "no-store"
                assert budget.json()["allowance_usd"] == 0.25
                assert budget.json()["estimated_usage_usd"] > 0
                assert budget.json()["remaining_usd"] < 2.0
                # Simulate cumulative exhaustion; it must block inference only,
                # while saved research remains readable to its owner.
                db = cloud_research._connect()
                db.execute(
                    "UPDATE calls SET amount_usd=0.25 WHERE workspace_id=(SELECT workspace_id FROM jobs WHERE session_id=?)",
                    (session_id,),
                )
                db.close()
                exhausted = client.get("/api/cloud-research/budget")
                assert exhausted.status_code == 200
                assert exhausted.json()["remaining_usd"] == 0
                still_readable = client.get(
                    f"/api/projects/research-sessions/{session_id}", params={"path": path}
                )
                assert still_readable.status_code == 200, still_readable.text

                client.headers.update(
                    {"X-Test-Subject": "cloud-b", "X-Test-Email": "b@example.test"}
                )
                hidden_status = client.get(
                    f"/api/projects/research-sessions/{session_id}", params={"path": path}
                )
                hidden_control = client.post(
                    f"/api/projects/research-sessions/{session_id}/control",
                    json={"path": path, "action": "stop"},
                )
                assert hidden_status.status_code == 404, hidden_status.text
                assert hidden_control.status_code == 404, hidden_control.text
                owner_b_budget = client.get("/api/cloud-research/budget")
                assert owner_b_budget.status_code == 200
                assert owner_b_budget.json()["reserved_and_estimated_usd"] == 0

    print(
        "PASS authenticated HTTP research start/status/idempotency and cross-workspace status/control denial with deterministic provider"
    )


if __name__ == "__main__":
    main()
