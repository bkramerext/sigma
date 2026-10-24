"""Cloud research start, status and cross-owner API workflow with a fake provider."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from uuid import uuid4

import httpx


def main() -> None:
    with TemporaryDirectory(prefix="sigma-cloud-api-", dir=Path.cwd().parent) as temporary:
        root = Path(temporary)
        root.chmod(0o700)
        for name in ("workspaces", "local-projects", "local-state"):
            (root / name).mkdir(mode=0o700)
        environment = {
            "SIGMA_CLOUD_AUTH_ENABLED": "true",
            "GOOGLE_OIDC_CLIENT_ID": "fixture.apps.googleusercontent.com",
            "GOOGLE_OIDC_CLIENT_SECRET": "fixture-secret",
            "SIGMA_CLOUD_PUBLIC_ORIGIN": "https://sigma.test",
            "SIGMA_CLOUD_BOOTSTRAP_ADMIN_EMAIL": "admin@example.test",
            "SIGMA_CLOUD_ADMIN_CONTACT_EMAIL": "admin@example.test",
            "SIGMA_CLOUD_AUTH_HOME": str(root / "auth"),
            "SIGMA_CLOUD_WORKSPACES_ROOT": str(root / "workspaces"),
            "SIGMA_PROJECTS_ROOT": str(root / "local-projects"),
            "SIGMA_STATE_DIR": str(root / "local-state"),
            "SIGMA_CLOUD_OPENAI_API_KEY": "fake-server-credential",
            "OPENAI_API_KEY": "local-key-must-not-be-used",
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

            from sigma import cloud_research

            # Exercise the real server credential lookup, model discovery,
            # Responses request construction, usage parsing, and cloud ledger.
            # The fixture is deterministic and never makes an external request.
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
                "obligation_reviews": [],
                "computational_citations": [],
            }
            provider_calls: list[str] = []
            fail_next_inference = False
            timeout_next_inference = False

            def provider_response(value):
                return {
                    "status": "completed",
                    "usage": {
                        "input_tokens": 90,
                        "input_tokens_details": {"cached_tokens": 0},
                        "output_tokens": 30,
                    },
                    "output": [
                        {
                            "type": "message",
                            "content": [{"type": "output_text", "text": json.dumps(value)}],
                        }
                    ],
                }

            def provider_handler(request):
                nonlocal fail_next_inference, timeout_next_inference
                assert request.headers["authorization"] == "Bearer fake-server-credential"
                if request.url.path == "/v1/models":
                    return httpx.Response(
                        200,
                        json={"object": "list", "data": [{"id": "gpt-6.1-sol"}]},
                    )
                assert request.url.path == "/v1/responses"
                payload = json.loads(request.content)
                role = payload["text"]["format"]["name"]
                assert role in {"research_investigator", "research_skeptic"}
                assert payload["store"] is False
                provider_calls.append(role)
                if timeout_next_inference:
                    timeout_next_inference = False
                    raise httpx.ReadTimeout("deterministic fake provider timeout", request=request)
                if fail_next_inference:
                    fail_next_inference = False
                    return httpx.Response(
                        500,
                        json={"error": {"code": "fixture_server_error", "message": "fixture"}},
                    )
                output = investigator if role == "research_investigator" else skeptic
                return httpx.Response(200, json=provider_response(output))

            real_client = httpx.AsyncClient

            def fake_provider_client(**kwargs):
                return real_client(transport=httpx.MockTransport(provider_handler), **kwargs)

            settings = {
                "research_rounds": 5,
                "model_calls": 30,
                "session_duration_minutes": 60,
                "output_tokens_per_call": 256,
                "maximum_estimated_cost_usd": 1.0,
            }
            with (
                patch(
                    "sigma.openai_connection.httpx.AsyncClient", side_effect=fake_provider_client
                ),
                patch(
                    "sigma.research_sessions.httpx.AsyncClient", side_effect=fake_provider_client
                ),
                patch("sigma.research_sessions.execution_capabilities", return_value=[]),
                TestClient(cloud_workspace_test_app.app) as client,
            ):
                # Missing identity and revoked identity are rejected at the
                # production workspace boundary. Missing sponsor credentials
                # produce an explicit unconfigured status and no provider I/O.
                assert client.get("/api/ai/models").status_code == 401
                client.headers.update(
                    {"X-Test-Subject": "cloud-a", "X-Test-Email": "a@example.test"}
                )
                client.headers["X-Test-Revoked"] = "true"
                assert client.get("/api/ai/models").status_code == 401
                del client.headers["X-Test-Revoked"]
                with patch.dict(os.environ, {"SIGMA_CLOUD_OPENAI_API_KEY": ""}):
                    unconfigured = client.get("/api/ai/models")
                assert unconfigured.status_code == 200
                assert unconfigured.json()["connection"]["status"] == "unconfigured"
                assert provider_calls == []
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
                    "expected_binding": "cloud_service_api_key",
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
                assert saved["status"] == "ended", saved
                assert len(saved["steps"]) == 6
                assert len(provider_calls) == 6
                assert provider_calls == [
                    "research_investigator",
                    "research_skeptic",
                    "research_investigator",
                    "research_skeptic",
                    "research_investigator",
                    "research_skeptic",
                ]
                duplicate = client.post("/api/projects/research-sessions/start", json=start_body)
                assert duplicate.status_code == 200, duplicate.text
                assert duplicate.json()["id"] == session_id
                assert len(provider_calls) == 6

                budget = client.get(
                    "/api/cloud-research/budget",
                    params={"workspace_id": "cloud-b", "owner": "cloud-b"},
                )
                assert budget.status_code == 200, budget.text
                assert budget.headers["cache-control"] == "no-store"
                assert budget.json()["allowance_usd"] == 0.25
                assert budget.json()["estimated_usage_usd"] > 0
                assert budget.json()["remaining_usd"] < 2.0
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

                # A provider-side failure after dispatch is uncertain billing:
                # the reservation is retained and the attempt is never retried.
                second_project = client.post(
                    "/api/projects/create",
                    json={"title": "Cloud failure case", "problem": "A bounded question"},
                )
                assert second_project.status_code == 201, second_project.text
                second_path = second_project.json()["path"]
                second_id = second_project.json()["project"]["id"]
                second_strategy_response = client.post(
                    "/api/projects/strategies",
                    json={
                        "path": second_path,
                        "title": "Test approach",
                        "approach": "Check a bounded claim.",
                    },
                )
                assert second_strategy_response.status_code == 201
                second_strategy = client.get(
                    "/api/projects/strategies", params={"path": second_path}
                ).json()["strategies"][0]
                second_limits = client.put(
                    "/api/projects/research-limits", json={"path": second_path, **settings}
                )
                assert second_limits.status_code == 200
                fail_next_inference = True
                failed_start = client.post(
                    "/api/projects/research-sessions/start",
                    json={
                        "path": second_path,
                        "strategy_id": second_strategy["id"],
                        "idempotency_key": str(uuid4()),
                        "expected_project_id": second_id,
                        "expected_binding": "cloud_service_api_key",
                        "expected_limits": second_limits.json(),
                    },
                )
                assert failed_start.status_code == 200, failed_start.text
                failed_session_id = failed_start.json()["id"]
                for _ in range(500):
                    failed_status = client.get(
                        f"/api/projects/research-sessions/{failed_session_id}",
                        params={"path": second_path},
                    )
                    if failed_status.json()["status"] in {"ended", "failed", "paused"}:
                        break
                    time.sleep(0.01)
                else:
                    raise AssertionError("fake-provider failure did not reach a terminal session")
                assert failed_status.json()["status"] == "failed", failed_status.json()
                assert failed_status.json()["steps"][0]["attempt_status"] == "unknown"
                assert len(provider_calls) == 7

                # Timeouts after transport dispatch are also unknown charges;
                # the in-flight reservation is held without replay.
                timeout_next_inference = True
                timeout_start = client.post(
                    "/api/projects/research-sessions/start",
                    json={
                        "path": second_path,
                        "strategy_id": second_strategy["id"],
                        "idempotency_key": str(uuid4()),
                        "expected_project_id": second_id,
                        "expected_binding": "cloud_service_api_key",
                        "expected_limits": second_limits.json(),
                    },
                )
                assert timeout_start.status_code == 200, timeout_start.text
                timeout_session_id = timeout_start.json()["id"]
                for _ in range(500):
                    timeout_status = client.get(
                        f"/api/projects/research-sessions/{timeout_session_id}",
                        params={"path": second_path},
                    )
                    if timeout_status.json()["status"] in {"ended", "failed", "paused"}:
                        break
                    time.sleep(0.01)
                else:
                    raise AssertionError("fake-provider timeout did not reach a terminal session")
                assert timeout_status.json()["status"] == "failed"
                assert timeout_status.json()["steps"][0]["attempt_status"] == "unknown"
                assert len(provider_calls) == 8
                unknown_budget = client.get("/api/cloud-research/budget").json()
                assert unknown_budget["unknown_provider_attempts"] == 2
                assert unknown_budget["reserved_and_estimated_usd"] > 0

                # Exhaust the first owner's persisted allowance. A later
                # session must be denied before provider dispatch, while the
                # completed evidence remains readable.
                client.headers.update(
                    {"X-Test-Subject": "cloud-a", "X-Test-Email": "a@example.test"}
                )
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
                exhausted_start = client.post(
                    "/api/projects/research-sessions/start",
                    json={**start_body, "idempotency_key": str(uuid4())},
                )
                assert exhausted_start.status_code == 200, exhausted_start.text
                exhausted_id = exhausted_start.json()["id"]
                for _ in range(500):
                    exhausted_status = client.get(
                        f"/api/projects/research-sessions/{exhausted_id}",
                        params={"path": path},
                    )
                    if exhausted_status.json()["status"] in {"ended", "failed", "paused"}:
                        break
                    time.sleep(0.01)
                else:
                    raise AssertionError(
                        "exhausted sponsored session did not reach a terminal state"
                    )
                assert len(provider_calls) == 8
                assert exhausted_status.json()["steps"][0]["attempt_status"] == "not_dispatched"

    print(
        "PASS authenticated HTTP sponsored inference through a deterministic fake OpenAI provider, including no personal account, budget exhaustion, uncertain failure holds, idempotency, and cross-workspace isolation"
    )


if __name__ == "__main__":
    main()
