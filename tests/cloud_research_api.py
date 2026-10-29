"""Cloud research start, status and cross-owner API workflow with a fake provider."""

from __future__ import annotations

import asyncio
import json
import os
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import AsyncMock, patch
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
            "SIGMA_CLOUD_ADMIN_CONTACT_EMAIL": "admin@example.test",
            "SIGMA_CLOUD_AUTH_HOME": str(root / "auth"),
            "SIGMA_CLOUD_WORKSPACES_ROOT": str(root / "workspaces"),
            "SIGMA_PROJECTS_ROOT": str(root / "local-projects"),
            "SIGMA_STATE_DIR": str(root / "local-state"),
            "SIGMA_CLOUD_OPENAI_API_KEY": "fake-server-credential",
            "SIGMA_CLOUD_INFERENCE_PROVIDER": "api_key",
            # A personal API key must never win over the sponsored server key.
            "OPENAI_API_KEY": "fake-personal-credential-must-not-be-used",
            "SIGMA_CLOUD_GLOBAL_SPEND_CEILING_USD": "1.00",
            "SIGMA_CLOUD_USER_SPEND_CEILING_USD": "1.00",
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

            from sigma import (
                agentic,
                cloud_auth,
                cloud_research,
                cloud_workspaces,
                openai_connection,
                papers,
                proposals,
                research_sessions,
                text_conversion,
            )

            principal = cloud_auth.Principal("cloud-a", "a@example.test", "member")
            cloud_auth._persist_user_state(cloud_auth.config(), principal)
            cloud_auth.set_model_access(principal.subject, "sponsored")
            workspace_token = cloud_workspaces.bind(principal)
            try:
                credential = asyncio.run(openai_connection.auth_context())
            finally:
                cloud_workspaces.reset(workspace_token)
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

            async def fake_call(record, role, context, timeout_seconds=None, step_id=None):
                del record, context, timeout_seconds
                assert isinstance(step_id, str)
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
                assert limits.json()["model_calls"] == 30
                assert limits.json()["research_rounds"] == 5
                assert limits.json()["session_duration_minutes"] == 60
                assert limits.json()["maximum_estimated_cost_usd"] == 1.0
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
                assert saved["status"] == "ended"
                assert len(saved["steps"]) == 10
                assert calls.await_count == 10
                trace = client.get(
                    f"/api/projects/research-sessions/{session_id}/log", params={"path": path}
                )
                assert trace.status_code == 200, trace.text
                assert trace.json()["short_name"] == "Cloud API"
                assert any(item["type"] == "session_event" for item in trace.json()["events"])
                no_new_events = client.get(
                    f"/api/projects/research-sessions/{session_id}/log",
                    params={"path": path, "after": trace.json()["cursor"]},
                )
                assert no_new_events.status_code == 200 and no_new_events.json()["events"] == []
                client.headers.update(
                    {"X-Test-Subject": "cloud-b", "X-Test-Email": "b@example.test"}
                )
                hidden_log = client.get(
                    f"/api/projects/research-sessions/{session_id}/log", params={"path": path}
                )
                assert hidden_log.status_code == 404, hidden_log.text
                client.headers.update(
                    {"X-Test-Subject": "cloud-a", "X-Test-Email": "a@example.test"}
                )

                # Standalone strategy generation uses the same sponsored
                # credential and durable ledger as research sessions.
                response_body = {
                    "status": "completed",
                    "model": "gpt-6.1-sol",
                    "usage": {
                        "input_tokens": 120,
                        "output_tokens": 40,
                        "input_tokens_details": {"cached_tokens": 0},
                    },
                    "output": [
                        {
                            "type": "message",
                            "content": [
                                {
                                    "type": "output_text",
                                    "text": json.dumps(
                                        {
                                            "title": "Recurrence boundary check",
                                            "summary": "Check the initial terms before using the inductive bound.",
                                            "approach": "Compute the first recurrence values exactly, then compare the boundary case with the proposed induction hypothesis.",
                                            "first_tests": "Evaluate the recurrence for its first three valid indices.",
                                            "assumptions": "The recurrence definition applies at each stated index.",
                                            "failure_modes": "A failed base case invalidates this induction direction.",
                                        }
                                    ),
                                }
                            ],
                        }
                    ],
                }
                real_async_client = httpx.AsyncClient
                provider_status = 200
                provider_interrupt = False
                paper_long_mode = False
                paper_long_evidence_ref = None
                provider_calls = 0
                response_dispatches = 0
                provider_malformed = False
                provider_cancel_mode = False
                provider_cancel_started = threading.Event()

                async def provider_fixture(request):
                    nonlocal paper_long_evidence_ref, provider_calls, response_dispatches
                    provider_calls += 1
                    if request.url.path == "/v1/responses":
                        response_dispatches += 1
                    assert request.headers["authorization"] == "Bearer fake-server-credential"
                    if request.url.path == "/v1/models":
                        return httpx.Response(
                            200,
                            json={"object": "list", "data": [{"id": "gpt-6.1-sol"}]},
                        )
                    if provider_interrupt:
                        raise httpx.ReadTimeout(
                            "deterministic interrupted provider", request=request
                        )
                    if provider_cancel_mode and request.url.path == "/v1/responses":
                        provider_cancel_started.set()
                        await asyncio.sleep(30)
                    if provider_malformed:
                        return httpx.Response(
                            200,
                            json={
                                "status": "completed",
                                "model": "gpt-6.1-sol",
                                "usage": {},
                                "output": [{"type": "message", "content": "malformed"}],
                            },
                        )
                    if provider_status != 200:
                        return httpx.Response(provider_status, json={"error": "fixture failure"})
                    if paper_long_mode:
                        payload = json.loads(request.content)
                        schema_name = payload["text"]["format"]["name"]
                        if schema_name == "sigma_paper_evidence_batch":
                            batch = json.loads(payload["input"])
                            fields = batch["fields"]
                            paper_long_evidence_ref = fields[0]["source_ref"]
                            output = {
                                "notes": [
                                    {
                                        "statement": "The saved project contains a recurrence question.",
                                        "kind": "context",
                                        "evidence_refs": [paper_long_evidence_ref],
                                    }
                                ],
                                "conflicts_or_gaps": [],
                                "covered_field_refs": [field["field_ref"] for field in fields],
                                "omitted_fields": [],
                            }
                        elif schema_name == "sigma_long_paper_plan":
                            output = {
                                "title": "A source-linked recurrence note",
                                "abstract": "This note describes the saved recurrence question and records the limits of the evidence available in the project snapshot. No result beyond that record is established.",
                                "abstract_claim_ids": ["C1"],
                                "problem_framing": ["The project asks about a recurrence."],
                                "problem_framing_claim_ids": ["C1"],
                                "methods": ["We reviewed the single saved project record."],
                                "methods_claim_ids": ["C1"],
                                "claims": [
                                    {
                                        "id": "C1",
                                        "statement": "The saved project records a recurrence question.",
                                        "status": "established",
                                        "evidence_refs": [paper_long_evidence_ref],
                                        "reasoning": "The question occurs directly in the saved source record.",
                                    }
                                ],
                                "sections": [
                                    {
                                        "heading": "Project question",
                                        "purpose": "Describe the source record and its question.",
                                        "evidence_refs": [paper_long_evidence_ref],
                                        "claim_ids": ["C1"],
                                    },
                                    {
                                        "heading": "Evidence limits",
                                        "purpose": "State what the single saved source does not establish.",
                                        "evidence_refs": [paper_long_evidence_ref],
                                        "claim_ids": ["C1"],
                                    },
                                ],
                                "limitations": ["No recurrence computation or proof was recorded."],
                                "open_obligations": [],
                                "conclusions": [
                                    "The saved project contains a recurrence question."
                                ],
                                "conclusion_claim_ids": ["C1"],
                                "validation_warnings": [],
                            }
                        elif schema_name == "sigma_long_paper_section":
                            output = {
                                "paragraphs": [
                                    "The saved project record identifies a recurrence question. This statement is limited to the source record and does not establish a recurrence formula."
                                ]
                            }
                        else:
                            raise AssertionError(f"Unexpected cloud paper stage: {schema_name}")
                        return httpx.Response(
                            200,
                            json={
                                "status": "completed",
                                "model": "gpt-6.1-sol",
                                "usage": {
                                    "input_tokens": 180,
                                    "output_tokens": 120,
                                    "input_tokens_details": {"cached_tokens": 0},
                                },
                                "output": [
                                    {
                                        "type": "message",
                                        "content": [
                                            {"type": "output_text", "text": json.dumps(output)}
                                        ],
                                    }
                                ],
                            },
                        )
                    return httpx.Response(200, json=response_body)

                with (
                    patch.object(
                        proposals.httpx,
                        "AsyncClient",
                        side_effect=lambda **kwargs: real_async_client(
                            transport=httpx.MockTransport(provider_fixture), **kwargs
                        ),
                    ),
                ):
                    generated = client.post(
                        "/api/projects/proposals",
                        json={
                            "path": path,
                            "expected_project_id": project_id,
                            "expected_binding": credential["identity"],
                        },
                    )
                assert generated.status_code == 200, generated.text
                db = cloud_research._connect()
                proposal_call = db.execute(
                    "SELECT c.status,j.project_id FROM calls c JOIN jobs j USING(session_id) WHERE j.project_id=? AND j.session_id!=? ORDER BY c.created_at DESC LIMIT 1",
                    (project_id, session_id),
                ).fetchone()
                db.close()
                assert proposal_call is not None
                assert proposal_call["status"] == "usage_estimated"
                assert proposal_call["project_id"] == project_id

                # Credentials are selected by the real cloud auth adapter.
                # A configured local/personal key cannot be used for hosted
                # inference, and absence of the sponsor key fails closed.
                proposal_configuration = client.get(
                    "/api/projects/proposals/config", params={"path": path}
                )
                assert proposal_configuration.status_code == 200
                assert proposal_configuration.json()["mode"] == "api_key"
                assert proposal_configuration.json()["binding"] == credential["identity"]
                dispatched_before_missing = provider_calls
                os.environ.pop("SIGMA_CLOUD_OPENAI_API_KEY")
                missing_credential = client.post(
                    "/api/projects/proposals",
                    json={"path": path, "expected_project_id": project_id},
                )
                assert missing_credential.status_code != 200, missing_credential.text
                assert provider_calls == dispatched_before_missing
                os.environ["SIGMA_CLOUD_OPENAI_API_KEY"] = "fake-server-credential"

                # Text conversion goes through the same sponsored reservation
                # path while preserving its source revision checks.
                source = client.get(
                    "/api/projects/text", params={"path": path, "scope": "project"}
                ).json()
                response_body = {
                    "status": "completed",
                    "model": "gpt-6.1-sol",
                    "usage": {
                        "input_tokens": 120,
                        "output_tokens": 40,
                        "input_tokens_details": {"cached_tokens": 0},
                    },
                    "output": [
                        {
                            "type": "message",
                            "content": [
                                {
                                    "type": "output_text",
                                    "text": json.dumps(
                                        {
                                            "body": "The recurrence starts from a saved mathematical problem.\n\nThe initial terms need explicit verification.",
                                            "warnings": [],
                                        }
                                    ),
                                }
                            ],
                        }
                    ],
                }
                with (
                    patch.object(
                        text_conversion.httpx,
                        "AsyncClient",
                        side_effect=lambda **kwargs: real_async_client(
                            transport=httpx.MockTransport(provider_fixture), **kwargs
                        ),
                    ),
                ):
                    converted = client.post(
                        "/api/projects/text/convert",
                        json={
                            "path": path,
                            "scope": "project",
                            "target": "markdown",
                            "expected_digest": source["source_digest"],
                            "expected_binding": credential["identity"],
                            "expected_project_id": project_id,
                        },
                    )
                assert converted.status_code == 200, converted.text
                assert converted.json()["markdown"]["current"] is True
                db = cloud_research._connect()
                conversion_audit = db.execute(
                    "SELECT COUNT(*) FROM calls c JOIN jobs j USING(session_id) WHERE j.project_id=? AND c.status='usage_estimated'",
                    (project_id,),
                ).fetchone()[0]
                db.close()
                assert conversion_audit == 12

                # Agentic exploration and independent review reserve each call
                # separately while keeping the resulting proposal unsaved.
                agentic_outputs = [
                    {
                        "title": "Check the recurrence boundary",
                        "summary": "Test the initial cases before extending the recurrence argument.",
                        "approach": "Evaluate the first valid terms independently, then compare the boundary case with the induction hypothesis before extending the recurrence argument.",
                        "first_tests": "Compute the first three defined terms exactly.",
                        "assumptions": "The recurrence applies at every stated index.",
                        "failure_modes": "A mismatch at the base case invalidates the approach.",
                        "mechanism": "An exact boundary check tests the base of a recurrence argument.",
                        "evidence_boundary": "Finite values are checks and do not prove the general recurrence.",
                        "prior_finding_ids": [],
                    },
                    {
                        "assessment": "distinct",
                        "public_summary": "The boundary check is a distinct and relevant direction; the induction still needs proof.",
                        "mechanism_comparison": "No current strategy checks the first values independently before using the induction hypothesis.",
                        "objections": ["The recurrence may not be defined at the initial index."],
                        "missing_obligations": "Verify the domain and first defined value.",
                        "revision_needed": False,
                    },
                ]
                provider_status = 200
                agentic_calls_before = provider_calls

                async def agentic_provider(request):
                    nonlocal provider_calls
                    provider_calls += 1
                    assert request.headers["authorization"] == "Bearer fake-server-credential"
                    output = agentic_outputs.pop(0)
                    return httpx.Response(
                        200,
                        json={
                            "status": "completed",
                            "model": "gpt-6.1-sol",
                            "usage": {
                                "input_tokens": 180,
                                "output_tokens": 120,
                                "input_tokens_details": {"cached_tokens": 0},
                            },
                            "output": [
                                {
                                    "type": "message",
                                    "content": [
                                        {"type": "output_text", "text": json.dumps(output)}
                                    ],
                                }
                            ],
                        },
                    )

                with (
                    patch.object(
                        agentic.httpx,
                        "AsyncClient",
                        side_effect=lambda **kwargs: real_async_client(
                            transport=httpx.MockTransport(agentic_provider), **kwargs
                        ),
                    ),
                ):
                    agentic_response = client.post(
                        "/api/projects/proposals/agentic",
                        json={
                            "path": path,
                            "expected_project_id": project_id,
                            "expected_binding": credential["identity"],
                        },
                    )
                assert agentic_response.status_code == 200, agentic_response.text
                assert '"type": "run.completed"' in agentic_response.text
                assert len(agentic_outputs) == 0
                assert provider_calls - agentic_calls_before == 2
                db = cloud_research._connect()
                agentic_audit = db.execute(
                    "SELECT COUNT(*) FROM calls c JOIN jobs j USING(session_id) WHERE j.project_id=? AND c.status='usage_estimated'",
                    (project_id,),
                ).fetchone()[0]
                db.close()
                assert agentic_audit == 14

                # A bounded one-shot paper goes through sponsored admission and
                # persists both TeX source and the resulting PDF artifact.
                paper_project = client.post(
                    "/api/projects/create",
                    json={"title": "Cloud paper fixture", "problem": "Check a recurrence."},
                )
                assert paper_project.status_code == 201, paper_project.text
                paper_path = paper_project.json()["path"]
                paper_project_id = paper_project.json()["project"]["id"]
                package, _ = papers._snapshot(paper_path)
                evidence_ref = package["sources"][0]["id"]
                paper_draft = {
                    "title": "A bounded exploratory note",
                    "abstract": "This note records one limited observation in the saved project and describes the unresolved checks that remain before any claim about a recurrence can be established.",
                    "abstract_claim_ids": ["C1"],
                    "problem_framing": ["The project asks about a recurrence."],
                    "problem_framing_claim_ids": ["C1"],
                    "methods": ["We inspected the saved project record."],
                    "methods_claim_ids": ["C1"],
                    "claims": [
                        {
                            "id": "C1",
                            "statement": "The project record contains a recurrence question.",
                            "status": "established",
                            "evidence_refs": [evidence_ref],
                            "reasoning": "The question appears in the saved project source.",
                        }
                    ],
                    "sections": [
                        {
                            "heading": "Saved evidence",
                            "paragraphs": ["The project record was retained."],
                            "claim_ids": ["C1"],
                        },
                        {
                            "heading": "Limitations",
                            "paragraphs": ["No recurrence evaluation was performed."],
                            "claim_ids": ["C1"],
                        },
                    ],
                    "limitations": ["This note is not a proof."],
                    "open_obligations": ["Check the initial values."],
                    "conclusions": ["Only the saved question is asserted."],
                    "conclusion_claim_ids": ["C1"],
                    "validation_warnings": [],
                }
                response_body = {
                    "status": "completed",
                    "model": "gpt-6.1-sol",
                    "usage": {
                        "input_tokens": 180,
                        "output_tokens": 120,
                        "input_tokens_details": {"cached_tokens": 0},
                    },
                    "output": [
                        {
                            "type": "message",
                            "content": [{"type": "output_text", "text": json.dumps(paper_draft)}],
                        }
                    ],
                }
                preflight = client.get(
                    "/api/projects/papers/preflight", params={"path": paper_path}
                ).json()
                with (
                    patch.object(papers, "_compile_pdf", return_value=b"%PDF-1.4\nfixture\n"),
                    patch.object(
                        papers.httpx,
                        "AsyncClient",
                        side_effect=lambda **kwargs: real_async_client(
                            transport=httpx.MockTransport(provider_fixture), **kwargs
                        ),
                    ),
                ):
                    paper_response = client.post(
                        "/api/projects/papers",
                        json={
                            "path": paper_path,
                            "expected_project_id": paper_project_id,
                            "expected_binding": credential["identity"],
                            "expected_snapshot_sha256": preflight["snapshot_sha256"],
                        },
                    )
                assert paper_response.status_code == 200, paper_response.text
                assert '"type": "complete"' in paper_response.text, paper_response.text
                saved_papers = client.get(
                    "/api/projects/papers", params={"path": paper_path}
                ).json()["papers"]
                assert len(saved_papers) == 1 and saved_papers[0]["pdf_available"]
                saved_paper = client.get(
                    f"/api/projects/papers/{saved_papers[0]['paper_id']}",
                    params={"path": paper_path},
                ).json()
                assert saved_paper["tex_source"].startswith("\\documentclass")
                db = cloud_research._connect()
                paper_audit = db.execute(
                    "SELECT COUNT(*) FROM calls c JOIN jobs j USING(session_id) WHERE j.project_id=? AND c.status='usage_estimated'",
                    (paper_project_id,),
                ).fetchone()[0]
                db.close()
                assert paper_audit == 1

                # Forced long-form generation meters every evidence, plan and
                # section call and preserves a resumable per-project workflow.
                paper_long_mode = True
                long_preflight = client.get(
                    "/api/projects/papers/preflight",
                    params={"path": paper_path, "long_form": "true"},
                ).json()
                long_calls_before = provider_calls
                with (
                    patch.object(papers, "_compile_pdf", return_value=b"%PDF-1.4\nlong fixture\n"),
                    patch.object(
                        papers.httpx,
                        "AsyncClient",
                        side_effect=lambda **kwargs: real_async_client(
                            transport=httpx.MockTransport(provider_fixture), **kwargs
                        ),
                    ),
                ):
                    long_response = client.post(
                        "/api/projects/papers",
                        json={
                            "path": paper_path,
                            "expected_project_id": paper_project_id,
                            "expected_binding": credential["identity"],
                            "expected_snapshot_sha256": long_preflight["snapshot_sha256"],
                            "long_form": True,
                        },
                    )
                paper_long_mode = False
                assert long_response.status_code == 200, long_response.text
                assert '"type": "complete"' in long_response.text, long_response.text
                assert provider_calls - long_calls_before == 4
                all_papers = client.get("/api/projects/papers", params={"path": paper_path}).json()[
                    "papers"
                ]
                assert len(all_papers) == 2 and all(item["pdf_available"] for item in all_papers)
                private_paper_path = Path(paper_path).resolve(strict=True)
                assert private_paper_path.is_relative_to((root / "workspaces").resolve())
                from sigma.projects import read_project_artifact

                for paper in all_papers:
                    pdf_bytes = read_project_artifact(
                        paper_path, f"artifacts/papers/{paper['paper_id']}.pdf"
                    )
                    assert pdf_bytes.startswith(b"%PDF-")
                db = cloud_research._connect()
                paper_audit = db.execute(
                    "SELECT COUNT(*) FROM calls c JOIN jobs j USING(session_id) WHERE j.project_id=? AND c.status='usage_estimated'",
                    (paper_project_id,),
                ).fetchone()[0]
                db.close()
                assert paper_audit == 5

                response_body = {
                    "status": "completed",
                    "model": "gpt-6.1-sol",
                    "usage": {
                        "input_tokens": 120,
                        "output_tokens": 40,
                        "input_tokens_details": {"cached_tokens": 0},
                    },
                    "output": [
                        {
                            "type": "message",
                            "content": [
                                {
                                    "type": "output_text",
                                    "text": json.dumps(
                                        {
                                            "title": "Recurrence boundary check",
                                            "summary": "Check the initial terms before using the inductive bound.",
                                            "approach": "Compute the first recurrence values exactly, then compare the boundary case with the proposed induction hypothesis.",
                                            "first_tests": "Evaluate the recurrence for its first three valid indices.",
                                            "assumptions": "The recurrence definition applies at each stated index.",
                                            "failure_modes": "A failed base case invalidates this induction direction.",
                                        }
                                    ),
                                }
                            ],
                        }
                    ],
                }

                # Provider errors remain auditable as uncertain charges.
                provider_status = 429
                with (
                    patch.object(
                        proposals.httpx,
                        "AsyncClient",
                        side_effect=lambda **kwargs: real_async_client(
                            transport=httpx.MockTransport(provider_fixture), **kwargs
                        ),
                    ),
                ):
                    failed_proposal = client.post(
                        "/api/projects/proposals",
                        json={
                            "path": path,
                            "expected_project_id": project_id,
                            "expected_binding": credential["identity"],
                        },
                    )
                assert failed_proposal.status_code == 400, failed_proposal.text
                db = cloud_research._connect()
                unknown_attempts = db.execute(
                    "SELECT COUNT(*) FROM calls WHERE status='unknown' AND workspace_id=(SELECT workspace_id FROM jobs WHERE session_id=?)",
                    (session_id,),
                ).fetchone()[0]
                db.close()
                assert unknown_attempts == 1, (
                    unknown_attempts,
                    failed_proposal.status_code,
                    failed_proposal.text,
                )

                # A transport interruption after dispatch keeps its
                # write-ahead reservation instead of releasing the charge.
                provider_status = 200
                provider_interrupt = True
                with (
                    patch.object(
                        proposals.httpx,
                        "AsyncClient",
                        side_effect=lambda **kwargs: real_async_client(
                            transport=httpx.MockTransport(provider_fixture), **kwargs
                        ),
                    ),
                ):
                    interrupted = client.post(
                        "/api/projects/proposals",
                        json={
                            "path": path,
                            "expected_project_id": project_id,
                            "expected_binding": credential["identity"],
                        },
                    )
                assert interrupted.status_code == 400 and "timed out" in interrupted.text
                provider_interrupt = False
                db = cloud_research._connect()
                unknown_attempts = db.execute(
                    "SELECT COUNT(*) FROM calls WHERE status='unknown' AND workspace_id=(SELECT workspace_id FROM jobs WHERE session_id=?)",
                    (session_id,),
                ).fetchone()[0]
                db.close()
                assert unknown_attempts == 2

                # A completed HTTP response with malformed structured content
                # has uncertain provider billing and keeps its reservation.
                provider_interrupt = False
                provider_malformed = True
                with patch.object(
                    proposals.httpx,
                    "AsyncClient",
                    side_effect=lambda **kwargs: real_async_client(
                        transport=httpx.MockTransport(provider_fixture), **kwargs
                    ),
                ):
                    malformed = client.post(
                        "/api/projects/proposals",
                        json={
                            "path": path,
                            "expected_project_id": project_id,
                            "expected_binding": credential["identity"],
                        },
                    )
                provider_malformed = False
                assert malformed.status_code == 400, malformed.text
                db = cloud_research._connect()
                unknown_attempts = db.execute(
                    "SELECT COUNT(*) FROM calls WHERE status='unknown' AND workspace_id=(SELECT workspace_id FROM jobs WHERE session_id=?)",
                    (session_id,),
                ).fetchone()[0]
                db.close()
                assert unknown_attempts == 3

                # Cancel after provider dispatch. The request is deliberately
                # left awaiting its simulated response while the authenticated
                # cancellation endpoint interrupts it. A second concurrent
                # proposal must be rejected before provider dispatch.
                contention_project = client.post(
                    "/api/projects/create",
                    json={"title": "Concurrent cloud request", "problem": "A second problem."},
                )
                assert contention_project.status_code == 201, contention_project.text
                contention_path = contention_project.json()["path"]
                contention_id = contention_project.json()["project"]["id"]
                provider_cancel_mode = True
                provider_cancel_started.clear()
                cancel_id = str(uuid4())
                from concurrent.futures import ThreadPoolExecutor

                with (
                    patch.object(
                        proposals.httpx,
                        "AsyncClient",
                        side_effect=lambda **kwargs: real_async_client(
                            transport=httpx.MockTransport(provider_fixture), **kwargs
                        ),
                    ),
                    ThreadPoolExecutor(max_workers=1) as pool,
                ):
                    pending = pool.submit(
                        client.post,
                        "/api/projects/proposals",
                        json={
                            "path": path,
                            "expected_project_id": project_id,
                            "expected_binding": credential["identity"],
                            "request_id": cancel_id,
                        },
                    )
                    assert provider_cancel_started.wait(5), "cancel fixture did not reach provider"
                    dispatched_while_running = response_dispatches
                    concurrent_rejection = client.post(
                        "/api/projects/proposals",
                        json={
                            "path": contention_path,
                            "expected_project_id": contention_id,
                            "expected_binding": credential["identity"],
                        },
                    )
                    assert concurrent_rejection.status_code == 400, concurrent_rejection.text
                    assert response_dispatches == dispatched_while_running
                    cancelled = client.post(
                        "/api/projects/proposals/cancel", json={"request_id": cancel_id}
                    )
                    assert cancelled.status_code == 200, cancelled.text
                    cancellation_response = pending.result(timeout=10)
                provider_cancel_mode = False
                assert cancellation_response.status_code == 499, cancellation_response.text
                db = cloud_research._connect()
                unknown_attempts = db.execute(
                    "SELECT COUNT(*) FROM calls WHERE status='unknown' AND workspace_id=(SELECT workspace_id FROM jobs WHERE session_id=?)",
                    (session_id,),
                ).fetchone()[0]
                db.close()
                assert unknown_attempts == 4

                # Leave only enough budget for the dynamic text reservation.
                # Instructions and the response schema push the complete
                # request above the available amount, before dispatch.
                db = cloud_research._connect()
                db.execute(
                    "UPDATE calls SET amount_usd=0 WHERE workspace_id=(SELECT workspace_id FROM jobs WHERE session_id=?)",
                    (session_id,),
                )
                db.execute(
                    "UPDATE calls SET amount_usd=0.90 WHERE call_id=(SELECT c.call_id FROM calls c JOIN jobs j USING(session_id) WHERE j.session_id=? LIMIT 1)",
                    (session_id,),
                )
                db.close()
                attempted_before_quota = provider_calls
                real_start_provider_attempt = cloud_research.start_provider_attempt
                overhead_was_budgeted = False

                def start_with_overhead_assertion(
                    attempt_project_id, attempt_path, model, payload, output_tokens
                ):
                    nonlocal overhead_was_budgeted
                    assert isinstance(payload["input"], str)
                    dynamic_bytes = len(payload["input"].encode("utf-8"))
                    complete_bytes = cloud_research.provider_request_input_bytes(payload)
                    overhead_was_budgeted = complete_bytes > dynamic_bytes
                    return real_start_provider_attempt(
                        attempt_project_id, attempt_path, model, payload, output_tokens
                    )

                with (
                    patch.object(
                        cloud_research,
                        "start_provider_attempt",
                        side_effect=start_with_overhead_assertion,
                    ),
                    patch.object(
                        proposals.httpx,
                        "AsyncClient",
                        side_effect=lambda **kwargs: real_async_client(
                            transport=httpx.MockTransport(provider_fixture), **kwargs
                        ),
                    ),
                ):
                    exhausted_proposal = client.post(
                        "/api/projects/proposals",
                        json={
                            "path": path,
                            "expected_project_id": project_id,
                            "expected_binding": credential["identity"],
                        },
                    )
                assert exhausted_proposal.status_code == 400, exhausted_proposal.text
                assert overhead_was_budgeted
                assert provider_calls == attempted_before_quota

                duplicate = client.post("/api/projects/research-sessions/start", json=start_body)
                assert duplicate.status_code == 200, duplicate.text
                assert duplicate.json()["id"] == session_id
                assert calls.await_count == 10

                budget = client.get(
                    "/api/cloud-research/budget",
                    params={"workspace_id": "cloud-b", "owner": "cloud-b"},
                )
                assert budget.status_code == 200, budget.text
                assert budget.headers["cache-control"] == "no-store"
                assert budget.json()["allowance_usd"] == 1.0
                assert budget.json()["estimated_usage_usd"] > 0
                assert budget.json()["remaining_usd"] < 2.0
                # Simulate cumulative exhaustion; it must block inference only,
                # while saved research remains readable to its owner.
                db = cloud_research._connect()
                db.execute(
                    "UPDATE calls SET amount_usd=0 WHERE workspace_id=(SELECT workspace_id FROM jobs WHERE session_id=?)",
                    (session_id,),
                )
                db.execute(
                    "UPDATE calls SET amount_usd=1.00 WHERE call_id=(SELECT c.call_id FROM calls c JOIN jobs j USING(session_id) WHERE j.session_id=? LIMIT 1)",
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

                # Reopen the durable ledger in a fresh Python backend process,
                # then continue through the authenticated API with the same
                # persisted workspaces and quota state.
                with socket.socket() as port_socket:
                    port_socket.bind(("127.0.0.1", 0))
                    restart_port = port_socket.getsockname()[1]
                restart_environment = os.environ.copy()
                restart_environment["PYTHONPATH"] = os.pathsep.join(
                    [
                        str(Path.cwd() / "tests"),
                        str(Path.cwd() / "src"),
                        restart_environment.get("PYTHONPATH", ""),
                    ]
                )
                restarted_backend = subprocess.Popen(
                    [
                        sys.executable,
                        "-m",
                        "uvicorn",
                        "cloud_workspace_test_app:app",
                        "--host",
                        "127.0.0.1",
                        "--port",
                        str(restart_port),
                        "--log-level",
                        "error",
                    ],
                    cwd=Path.cwd(),
                    env=restart_environment,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                try:
                    recovered_budget = None
                    for _ in range(100):
                        if restarted_backend.poll() is not None:
                            raise AssertionError("Restarted FastAPI backend exited during startup")
                        try:
                            recovered_budget = httpx.get(
                                f"http://127.0.0.1:{restart_port}/api/cloud-research/budget",
                                headers={
                                    "X-Test-Subject": "cloud-a",
                                    "X-Test-Email": "a@example.test",
                                },
                                timeout=0.2,
                            )
                            if recovered_budget.status_code == 200:
                                break
                        except httpx.HTTPError:
                            time.sleep(0.05)
                    assert recovered_budget is not None, "Restarted API did not respond"
                    assert recovered_budget.status_code == 200, recovered_budget.text
                    assert recovered_budget.json()["unknown_provider_attempts"] >= 4
                    assert recovered_budget.json()["remaining_usd"] == 0
                    other_user_budget = httpx.get(
                        f"http://127.0.0.1:{restart_port}/api/cloud-research/budget",
                        headers={
                            "X-Test-Subject": "cloud-b",
                            "X-Test-Email": "b@example.test",
                        },
                        timeout=2,
                    )
                    assert other_user_budget.status_code == 200, other_user_budget.text
                    assert other_user_budget.json()["unknown_provider_attempts"] == 0
                    assert other_user_budget.json()["remaining_usd"] == 1.0
                finally:
                    restarted_backend.terminate()
                    restarted_backend.wait(timeout=10)

                client.headers.update(
                    {"X-Test-Subject": "cloud-b", "X-Test-Email": "b@example.test"}
                )
                principal_b = cloud_auth.Principal("cloud-b", "b@example.test", "member")
                cloud_auth._persist_user_state(cloud_auth.config(), principal_b)
                cloud_auth.set_model_access(principal_b.subject, "sponsored")
                workspace_token = cloud_workspaces.bind(principal_b)
                try:
                    credential_b = asyncio.run(openai_connection.auth_context())
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
                hidden_proposal = client.post(
                    "/api/projects/proposals",
                    json={"path": path, "expected_project_id": project_id},
                )
                assert hidden_proposal.status_code == 404, hidden_proposal.text
                owner_b_budget = client.get("/api/cloud-research/budget")
                assert owner_b_budget.status_code == 200
                assert owner_b_budget.json()["reserved_and_estimated_usd"] == 0

                # A has used the full $1 global pool above, while B still has
                # an empty $1 per-user allowance: the global ceiling blocks B
                # before provider dispatch.
                user_b_project = client.post(
                    "/api/projects/create",
                    json={"title": "Budget isolation", "problem": "A private question."},
                )
                assert user_b_project.status_code == 201, user_b_project.text
                user_b_path = user_b_project.json()["path"]
                user_b_id = user_b_project.json()["project"]["id"]
                dispatched_before_global = response_dispatches
                with patch.object(
                    proposals.httpx,
                    "AsyncClient",
                    side_effect=lambda **kwargs: real_async_client(
                        transport=httpx.MockTransport(provider_fixture), **kwargs
                    ),
                ):
                    global_exhausted = client.post(
                        "/api/projects/proposals",
                        json={
                            "path": user_b_path,
                            "expected_project_id": user_b_id,
                            "expected_binding": credential_b["identity"],
                        },
                    )
                assert global_exhausted.status_code == 400, global_exhausted.text
                assert "global inference-spend ceiling" in global_exhausted.text
                assert response_dispatches == dispatched_before_global

                # Lift only the test's global ceiling and consume B's own
                # allowance. A later B request must then fail at the per-user
                # ceiling while the global account still has room.
                os.environ["SIGMA_CLOUD_GLOBAL_SPEND_CEILING_USD"] = "15.00"
                with patch.object(
                    proposals.httpx,
                    "AsyncClient",
                    side_effect=lambda **kwargs: real_async_client(
                        transport=httpx.MockTransport(provider_fixture), **kwargs
                    ),
                ):
                    first_b = client.post(
                        "/api/projects/proposals",
                        json={
                            "path": user_b_path,
                            "expected_project_id": user_b_id,
                            "expected_binding": credential_b["identity"],
                        },
                    )
                assert first_b.status_code == 200, first_b.text
                db = cloud_research._connect()
                user_b_workspace = db.execute(
                    "SELECT workspace_id FROM jobs WHERE project_id=?", (user_b_id,)
                ).fetchone()[0]
                db.execute(
                    "UPDATE calls SET amount_usd=1.00 WHERE workspace_id=?", (user_b_workspace,)
                )
                db.close()
                dispatched_before_user = response_dispatches
                with patch.object(
                    proposals.httpx,
                    "AsyncClient",
                    side_effect=lambda **kwargs: real_async_client(
                        transport=httpx.MockTransport(provider_fixture), **kwargs
                    ),
                ):
                    user_exhausted = client.post(
                        "/api/projects/proposals",
                        json={
                            "path": user_b_path,
                            "expected_project_id": user_b_id,
                            "expected_binding": credential_b["identity"],
                        },
                    )
                assert user_exhausted.status_code == 400, user_exhausted.text
                assert "cumulative cloud research allowance" in user_exhausted.text
                assert response_dispatches == dispatched_before_user

    print(
        "PASS authenticated cloud inference endpoints, sponsor selection, spend limits, concurrency, failure accounting, cancellation, restart recovery, workspace artifacts and cross-user isolation"
    )


if __name__ == "__main__":
    main()
