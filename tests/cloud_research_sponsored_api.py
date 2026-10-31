"""Cloud research start, status and cross-owner API workflow with a fake provider."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import httpx


def main(mode: str = "api_key") -> None:
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
            "SIGMA_CLOUD_ADMIN_CONTACT_EMAIL": "admin@example.test",
            "SIGMA_CLOUD_AUTH_HOME": str(root / "auth"),
            "SIGMA_CLOUD_WORKSPACES_ROOT": str(root / "workspaces"),
            "SIGMA_PROJECTS_ROOT": str(root / "local-projects"),
            "SIGMA_STATE_DIR": str(root / "local-state"),
            "SIGMA_CLOUD_OPENAI_API_KEY": "fake-server-credential",
            "SIGMA_CLOUD_INFERENCE_PROVIDER": mode,
            "SIGMA_CLOUD_SPONSOR_EMAIL": "sponsor@example.test",
            "SIGMA_CLOUD_CHATGPT_AUTH_HOME": str(root / "sponsor"),
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

            from sigma import ai_store, cloud_auth, cloud_research, openai_connection

            binding = ""
            if mode == "chatgpt":
                import asyncio

                async def provision_fixture():
                    async with ai_store.transaction() as state:
                        state["active"] = "fixture"
                        state["accounts"] = {
                            "fixture": {
                                "email": "sponsor@example.test",
                                "client_id": "oaiapp_fixture",
                                "subject": "fixture-subject",
                                "access_token": "fake-plan-credential",
                                "expires_at": time.time() + 3600,
                                "scopes": ["resource.invoke", "chatgpt.tokens.use.direct"],
                            }
                        }

                asyncio.run(provision_fixture())

            # Exercise the real server credential lookup, model discovery,
            # Responses request construction, usage parsing, and cloud ledger.
            # The fixture is deterministic and never makes an external request.
            investigator = {
                "claim": "An induction suggests the recurrence bound.",
                "method": "Apply the recurrence once and check the base case.",
                "reasoning_steps": [
                    {
                        "title": "Recurrence consequence",
                        "argument": "The recurrence supports the stated local consequence under the supplied assumption.",
                        "epistemic_status": "deduction",
                        "basis_artifact_ids": [],
                    }
                ],
                "claim_is_conditional": False,
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
                "reasoning_assessments": [
                    {
                        "step_number": 1,
                        "disposition": "accepted",
                        "rationale": "The stated local consequence follows from its supplied premise.",
                        "objection": "",
                        "basis_artifact_ids": [],
                    }
                ],
                "claim_is_conditional": False,
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
                assert request.headers["authorization"] == (
                    "Bearer fake-plan-credential"
                    if mode == "chatgpt"
                    else "Bearer fake-server-credential"
                )
                if request.url.path == "/v1/models":
                    return httpx.Response(
                        200,
                        json=(
                            {
                                "models": [
                                    {
                                        "slug": "gpt-6.1-sol",
                                        "display_name": "Sol",
                                        "visibility": "list",
                                    }
                                ]
                            }
                            if mode == "chatgpt"
                            else {"object": "list", "data": [{"id": "gpt-6.1-sol"}]}
                        ),
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
                if mode == "chatgpt":
                    assert payload["stream"] is True and "max_output_tokens" not in payload
                    value = provider_response(output) | {"id": "resp_fixture"}
                    event = {"type": "response.completed", "sequence_number": 1, "response": value}
                    created = {
                        "type": "response.created",
                        "sequence_number": 0,
                        "response": {"id": "resp_fixture"},
                    }
                    return httpx.Response(
                        200,
                        headers={"content-type": "text/event-stream"},
                        content="data: "
                        + json.dumps(created)
                        + "\n\ndata: "
                        + json.dumps(event)
                        + "\n\n",
                    )
                return httpx.Response(200, json=provider_response(output))

            real_client = httpx.AsyncClient

            def fake_provider_client(**kwargs):
                return real_client(transport=httpx.MockTransport(provider_handler), **kwargs)

            settings = {
                "research_rounds": 5,
                "model_calls": 30,
                "session_duration_minutes": 60,
                "output_tokens_per_call": 256,
                "maximum_estimated_cost_usd": None,
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
                cloud_auth._persist_user_state(
                    cloud_auth.config(),
                    cloud_auth.Principal("cloud-a", "a@example.test", "member"),
                )
                cloud_auth.set_model_access("cloud-a", "sponsored")
                from sigma import cloud_workspaces

                principal = cloud_auth.Principal("cloud-a", "a@example.test", "member")
                workspace_token = cloud_workspaces.bind(principal)
                try:
                    import asyncio

                    binding = asyncio.run(openai_connection.auth_context())["identity"]
                finally:
                    cloud_workspaces.reset(workspace_token)
                client.headers["X-Test-Revoked"] = "true"
                assert client.get("/api/ai/models").status_code == 401
                del client.headers["X-Test-Revoked"]
                sponsor_status = client.get("/api/cloud-research/connection")
                assert sponsor_status.status_code == 200, sponsor_status.text
                assert sponsor_status.json()["mode"] == "sponsored"
                assert sponsor_status.json()["status"] == "connected"
                assert "authorization" not in sponsor_status.json()
                # Readiness discloses aggregate funding only to verified admins,
                # and must never trigger an inference call or expose credentials.
                assert client.get("/api/cloud-research/readiness").status_code == 403
                # Administrators receive the same per-identity sponsored
                # allowance; role grants administration authority, not an
                # inference-budget exemption.
                client.headers.update(
                    {
                        "X-Test-Subject": "cloud-admin",
                        "X-Test-Email": "admin@example.test",
                        "X-Test-Role": "admin",
                    }
                )
                cloud_auth._persist_user_state(
                    cloud_auth.config(),
                    cloud_auth.Principal("cloud-admin", "admin@example.test", "admin"),
                )
                admin_budget = client.get("/api/cloud-research/budget")
                assert admin_budget.status_code == 200, admin_budget.text
                assert admin_budget.json()["allowance_usd"] == float(
                    cloud_research._spend_ceiling_decimal()
                )
                assert admin_budget.json()["remaining_usd"] == float(
                    cloud_research._spend_ceiling_decimal()
                )
                with patch(
                    "sigma.api.connection",
                    new=AsyncMock(return_value={"status": "connected"}),
                ) as catalog_check:
                    readiness = client.get("/api/cloud-research/readiness")
                assert readiness.status_code == 200, readiness.text
                data = readiness.json()
                assert catalog_check.await_count == 1
                assert data["provider"] == mode
                assert data["provider_status"] == "connected"
                assert data["global_remaining_usd"] == float(
                    cloud_research._spend_ceiling_decimal()
                )
                assert data["live_inference_verified"] is False
                assert data["preflight_ready"] is True
                assert "sponsored_provider_invalid" not in data["blockers"]
                assert "fake-server-credential" not in readiness.text
                assert "fake-plan-credential" not in readiness.text
                assert "admin@example.test" not in readiness.text
                assert readiness.headers["cache-control"] == "no-store"
                # The diagnostic must remain readable when production's
                # deployment provider or spending cap is broken; neither
                # failure may leak provider exceptions or credentials.
                from sigma.projects import ProjectError

                with patch(
                    "sigma.api.sponsored_auth_context",
                    new=AsyncMock(side_effect=ProjectError("private auth failure")),
                ):
                    no_provider = client.get("/api/cloud-research/readiness")
                assert no_provider.status_code == 200
                assert "sponsored_provider_credential_missing" in no_provider.json()["blockers"]
                assert "private auth failure" not in no_provider.text
                with patch(
                    "sigma.api.cloud_research.snapshot",
                    side_effect=cloud_research.CloudResearchUnavailable("private ledger failure"),
                ):
                    no_budget = client.get("/api/cloud-research/readiness")
                assert no_budget.status_code == 200
                assert no_budget.json()["global_remaining_usd"] is None
                assert "shared_spending_policy_unavailable" in no_budget.json()["blockers"]
                assert "private ledger failure" not in no_budget.text
                client.headers.pop("X-Test-Role")
                client.headers.update(
                    {"X-Test-Subject": "cloud-a", "X-Test-Email": "a@example.test"}
                )
                import sqlite3

                with sqlite3.connect(root / "auth" / "access.sqlite3") as db:
                    assert db.execute(
                        "SELECT model_connection_status FROM user_state WHERE subject=?",
                        ("cloud-a",),
                    ).fetchone() == ("connected",)
                with patch.dict(
                    os.environ,
                    {
                        "SIGMA_CLOUD_OPENAI_API_KEY": "",
                        **(
                            {"SIGMA_CLOUD_SPONSOR_EMAIL": "absent@example.test"}
                            if mode == "chatgpt"
                            else {}
                        ),
                    },
                ):
                    unconfigured = client.get("/api/ai/models")
                    sponsor_unconfigured = client.get("/api/cloud-research/connection")
                assert unconfigured.status_code == 200
                assert unconfigured.json()["connection"]["status"] == (
                    "disconnected" if mode == "chatgpt" else "unconfigured"
                )
                assert sponsor_unconfigured.status_code == 200
                assert sponsor_unconfigured.json()["status"] == (
                    "disconnected" if mode == "chatgpt" else "unconfigured"
                )
                with sqlite3.connect(root / "auth" / "access.sqlite3") as db:
                    assert db.execute(
                        "SELECT model_connection_status FROM user_state WHERE subject=?",
                        ("cloud-a",),
                    ).fetchone() == (("disconnected" if mode == "chatgpt" else "unconfigured"),)
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
                fresh_limits = client.get("/api/projects/research-limits", params={"path": path})
                assert fresh_limits.status_code == 200, fresh_limits.text
                assert fresh_limits.json()["maximum_estimated_cost_usd"] is None
                limits = client.put(
                    "/api/projects/research-limits", json={"path": path, **settings}
                )
                assert limits.status_code == 200, limits.text
                assert limits.json()["model_calls"] == 30
                assert limits.json()["research_rounds"] == 5
                assert limits.json()["session_duration_minutes"] == 60
                assert limits.json()["maximum_estimated_cost_usd"] is None
                key = str(uuid4())
                start_body = {
                    "path": path,
                    "strategy_id": strategy_id,
                    "idempotency_key": key,
                    "expected_project_id": project_id,
                    "expected_binding": binding,
                    "expected_limits": limits.json(),
                }
                started = client.post("/api/projects/research-sessions/start", json=start_body)
                assert started.status_code == 200, started.text
                assert started.json()["duration_limit_minutes"] == 15
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
                assert len(saved["steps"]) == 10
                assert len(provider_calls) == 10
                assert provider_calls == [
                    role for _ in range(5) for role in ("research_investigator", "research_skeptic")
                ]
                duplicate = client.post("/api/projects/research-sessions/start", json=start_body)
                assert duplicate.status_code == 200, duplicate.text
                assert duplicate.json()["id"] == session_id
                assert len(provider_calls) == 10

                # Verify the actual owner-facing export boundary after research,
                # not only the session status endpoint. Then read it again from
                # a fresh application process to cover hosted workspace restart.
                exported = client.get("/api/projects/audit", params={"path": path})
                assert exported.status_code == 200, exported.text
                export_data = exported.json()
                assert export_data["project"]["id"] == project_id
                assert len(export_data["research_sessions"]) == 1
                exported_session = export_data["research_sessions"][0]
                assert exported_session["id"] == session_id
                assert exported_session["status"] == "ended"
                assert exported_session["outcome"]["assessment"]
                assert exported_session["outcome"]["verification_label"] in {
                    "Incomplete",
                    "Unknown",
                }
                report = client.get(
                    "/api/projects/export/report", params={"path": path, "format": "txt"}
                )
                assert report.status_code == 200, report.text
                assert report.headers["content-type"].startswith("text/plain")
                assert "Outcome" in report.text and "Verification" in report.text

                export_directory = os.environ.get("SIGMA_INCREMENT18_EXPORT_DIR")
                if export_directory:
                    retained = Path(export_directory)
                    retained.mkdir(parents=True, exist_ok=True)
                    (retained / "cloud-research-project.json").write_bytes(exported.content)
                    (retained / "cloud-research-report.txt").write_bytes(report.content)
                    capture_commit = subprocess.run(
                        ["git", "rev-parse", "HEAD"],
                        cwd=Path(__file__).resolve().parents[1],
                        check=True,
                        capture_output=True,
                        text=True,
                    ).stdout.strip()
                    manifest = {
                        "source_project_id": project_id,
                        "source_session_ids": [session_id],
                        "captured_at_utc": datetime.now(UTC).isoformat(),
                        "capture_app_commit": capture_commit,
                        "capture_method": (
                            "Production FastAPI project/export and report routes in the "
                            "deterministic authenticated cloud sponsored-session scenario."
                        ),
                        "activity": [
                            "Created a private project and saved strategy through authenticated routes.",
                            "Completed three Investigator/Skeptic rounds using the no-network fake Responses transport.",
                            "Retrieved the owner-facing project JSON and text report, then re-read both from a fresh FastAPI process.",
                        ],
                        "files": [
                            {
                                "path": "cloud-research-project.json",
                                "source": "exact HTTP response bytes from /api/projects/audit",
                                "content_type": exported.headers.get("content-type"),
                            },
                            {
                                "path": "cloud-research-report.txt",
                                "source": "exact HTTP response bytes from /api/projects/export/report?format=txt",
                                "content_type": report.headers.get("content-type"),
                            },
                        ],
                        "omissions": [
                            "No real Google OAuth exchange or production host was used.",
                            "No live inference, paid provider call, Python/Sage execution, PDF, or Markdown export was exercised.",
                        ],
                    }
                    (retained / "manifest.json").write_text(
                        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8",
                    )

                restart_environment = os.environ.copy()
                restart_environment["PYTHONPATH"] = os.pathsep.join(
                    (
                        str(Path(__file__).resolve().parent),
                        restart_environment.get("PYTHONPATH", ""),
                    )
                ).rstrip(os.pathsep)
                restarted_read = subprocess.run(
                    [
                        sys.executable,
                        "-c",
                        """
import sys
from fastapi.testclient import TestClient
import cloud_workspace_test_app
with TestClient(cloud_workspace_test_app.app) as reopened:
    reopened.headers.update({"X-Test-Subject": "cloud-a", "X-Test-Email": "a@example.test"})
    path, expected_session_id, expected_project_id = sys.argv[1:]
    session = reopened.get("/api/projects/research-sessions/" + expected_session_id, params={"path": path})
    assert session.status_code == 200, session.text
    value = session.json()
    assert value["status"] == "ended" and value["outcome"]["assessment"]
    exported = reopened.get("/api/projects/audit", params={"path": path})
    assert exported.status_code == 200, exported.text
    data = exported.json()
    assert data["project"]["id"] == expected_project_id
    assert len(data["research_sessions"]) == 1
    assert data["research_sessions"][0]["id"] == expected_session_id
    report = reopened.get("/api/projects/export/report", params={"path": path, "format": "txt"})
    assert report.status_code == 200, report.text
    assert "Outcome" in report.text and "Verification" in report.text
print("PASS fresh-process research, Outcome and report recovery")
""",
                        path,
                        session_id,
                        project_id,
                    ],
                    check=False,
                    capture_output=True,
                    text=True,
                    env=restart_environment,
                )
                assert restarted_read.returncode == 0, restarted_read.stderr
                assert "PASS fresh-process research, Outcome and report recovery" in (
                    restarted_read.stdout
                )

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
                cloud_auth._persist_user_state(
                    cloud_auth.config(),
                    cloud_auth.Principal("cloud-b", "b@example.test", "member"),
                )
                cloud_auth.set_model_access("cloud-b", "sponsored")
                from sigma import cloud_workspaces

                workspace_token = cloud_workspaces.bind(
                    cloud_auth.Principal("cloud-b", "b@example.test", "member")
                )
                try:
                    binding_b = asyncio.run(openai_connection.auth_context())["identity"]
                finally:
                    cloud_workspaces.reset(workspace_token)
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
                        "expected_binding": binding_b,
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
                assert failed_status.json()["status"] == "ended", failed_status.json()
                assert failed_status.json()["steps"][0]["failure_kind"] == "provider_temporary"
                assert failed_status.json()["steps"][1]["status"] == "completed"
                assert failed_status.json()["artifacts"]
                provider_calls_after_failure = len(provider_calls)
                assert provider_calls_after_failure == 10 + failed_status.json()["calls_used"]

                # A bounded timeout retry is a new charged attempt. The first
                # attempt stays unknown and reserved; completed turns persist.
                timeout_next_inference = True
                provider_calls_before_timeout = len(provider_calls)
                timeout_start = client.post(
                    "/api/projects/research-sessions/start",
                    json={
                        "path": second_path,
                        "strategy_id": second_strategy["id"],
                        "idempotency_key": str(uuid4()),
                        "expected_project_id": second_id,
                        "expected_binding": binding_b,
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
                assert timeout_status.json()["status"] in {"ended", "paused"}, timeout_status.json()
                assert timeout_status.json()["steps"][0]["attempt_status"] == "unknown"
                assert timeout_status.json()["calls_used"] >= 1
                if len(timeout_status.json()["steps"]) > 1:
                    retry_step = timeout_status.json()["steps"][1]
                    assert (
                        retry_step["status"] == "completed"
                        or retry_step.get("attempt_status") == "not_dispatched"
                    )
                provider_calls_after_timeout = len(provider_calls)
                assert provider_calls_after_timeout == (
                    provider_calls_before_timeout + timeout_status.json()["calls_used"]
                )
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
                existing_session_ids = {
                    session["id"]
                    for session in client.get(
                        "/api/projects/research-sessions", params={"path": path}
                    ).json()["sessions"]
                }
                exhausted_start = client.post(
                    "/api/projects/research-sessions/start",
                    json={**start_body, "idempotency_key": str(uuid4())},
                )
                assert exhausted_start.status_code == 400, exhausted_start.text
                assert "global inference-spend ceiling" in exhausted_start.json()["error"]
                assert len(provider_calls) == provider_calls_after_timeout
                # Reject a hopeless start before creating any session record.
                assert {
                    session["id"]
                    for session in client.get(
                        "/api/projects/research-sessions", params={"path": path}
                    ).json()["sessions"]
                } == existing_session_ids

    print(
        "PASS authenticated HTTP sponsored inference through a deterministic fake OpenAI provider, including no personal account, budget exhaustion, uncertain failure holds, idempotency, and cross-workspace isolation"
    )


if __name__ == "__main__":
    main()
    main("chatgpt")
