"""Controlled HTTP transport fixtures exercise the real adapter; no paid calls."""

import asyncio
import concurrent.futures
import json
import os
import subprocess
import sys
import threading
from dataclasses import asdict
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
from fastapi.testclient import TestClient

from sigma import chatgpt_auth, openai_connection, proposals, research_sessions
from sigma.api import app
from sigma.projects import (
    ProjectError,
    create_strategy,
    initialize_project,
    inspect_project,
    project_settings,
    set_strategy_enabled,
    update_project,
)

DRAFT = {
    "title": "Moment positivity obstruction",
    "summary": "Test finite moment matrices for a discriminating obstruction.",
    "approach": "Construct a parameterized moment matrix and test necessary positivity inequalities, without assuming sufficiency.",
    "first_tests": "Compute small minors on independently verified inputs and test sensitivity.",
    "assumptions": "Check convergence and interchange of limits rather than assuming them.",
    "failure_modes": "The inequalities may be necessary but too weak to distinguish a counterexample.",
}
REAL_CLIENT = httpx.AsyncClient


def response(draft=None):
    return {
        "status": "completed",
        "model": "gpt-4.1-fixture",
        "output": [
            {
                "type": "message",
                "content": [
                    {"type": "output_text", "text": json.dumps(DRAFT if draft is None else draft)}
                ],
            }
        ],
    }


async def rejects(awaitable, contains=None):
    try:
        await awaitable
    except ProjectError as exc:
        if contains is not None:
            assert contains in str(exc), str(exc)
        return
    raise AssertionError("Expected proposal rejection")


async def check(path):
    await chatgpt_auth.select("api_key")
    project_id = inspect_project(str(path)).project.id
    research_sessions._save(
        str(path),
        {
            "id": "00000000-0000-4000-8000-000000000001",
            "project_id": project_id,
            "session_number": 1,
            "project_path": str(path.resolve()),
            "status": "completed",
            "created_at": "2026-01-01T00:00:00+00:00",
            "strategy_title": "Moment positivity",
            "artifacts": [
                {
                    "id": "finding-moment",
                    "sequence": 1,
                    "strategy_id": "strategy-moment",
                    "claim_or_question": "A real mathematical question about moment positivity.",
                    "method": "Test a finite moment matrix condition.",
                    "evidence_status": "Partial necessary condition found; sufficiency remains open.",
                    "objections": ["The condition may be too weak."],
                    "open_obligations": ["Test the boundary parameter range."],
                    "coordinator_decision": "continue",
                    "next_question": "Does positivity persist at the boundary?",
                }
            ],
        },
    )
    research_sessions._save(
        str(path),
        {
            "id": "00000000-0000-4000-8000-000000000002",
            "project_id": project_id,
            "project_path": str(path.resolve()),
            "session_number": 2,
            "status": "completed",
            "created_at": "2026-01-02T00:00:00+00:00",
            "strategy_title": "Independent boundary check",
            "artifacts": [
                {
                    "id": "finding-boundary",
                    "sequence": 1,
                    "claim_or_question": "A real mathematical question about the boundary case.",
                    "method": "Check the boundary of the moment positivity condition.",
                    "evidence_status": "The boundary remains unresolved.",
                    "open_obligations": ["Test the limiting boundary value."],
                }
            ],
        },
    )
    before = (path / "project.json").read_bytes()
    calls = []
    inference_calls = []
    inference_hook = None
    suggestion_output: dict[str, str | None] = {
        "markdown": "## Independent boundary test\n\nCompare the boundary case with the saved moment positivity approach.\n\n**Rationale:** Session evidence leaves the boundary obligation open."
    }
    inference_output = {
        "title": "Boundary compactness transfer",
        "summary": "Test whether a compactness argument controls the unresolved boundary case.",
        "approach": "Formalize a compactness hypothesis from the unresolved boundary findings and test it on the extremal parameter family. Treat any successful computation as evidence, not proof.",
    }

    async def handler(request):
        if request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "object": "list",
                    "data": [{"id": "gpt-6.1-sol"}, {"id": "gpt-6-luna"}, {"id": "gpt-6-astra"}],
                },
            )
        assert str(request.url) == "https://api.openai.com/v1/responses"
        payload = json.loads(request.content)
        assert payload["store"] is False and payload["text"]["format"]["strict"] is True
        assert payload["reasoning"] == {"effort": "high"}
        assert payload["model"] == "gpt-6.1-sol"
        assert payload["max_output_tokens"] == 8000
        if "Infer exactly one useful" in payload["instructions"]:
            context = json.loads(payload["input"])
            assert context["current_understanding"]["session_count"] == 2
            assert len(context["existing_strategies_including_disabled"]) >= 1
            calls.append(payload)
            inference_calls.append(payload)
            if inference_hook is not None:
                response_override = await inference_hook()
                if response_override is not None:
                    return response_override
            return httpx.Response(200, json=response(inference_output))
        if "ready-to-copy strategy description in Markdown" in payload["instructions"]:
            context = json.loads(payload["input"])
            assert context["project_question"] == "A real mathematical question"
            assert "current_understanding" in context
            assert context["current_understanding"]["session_count"] == 2
            assert isinstance(context["current_understanding"]["unavailable_session_records"], int)
            assert context["selected_session_evidence"]
            assert {row["id"] for row in context["selected_session_evidence"]} >= {
                "finding-moment",
                "finding-boundary",
            }
            assert context["existing_strategies_including_disabled"]
            assert context["existing_strategies_including_disabled"][0]["enabled"] is False
            calls.append(payload)
            return httpx.Response(
                200,
                json=response(suggestion_output),
            )
        # Generation must propose a candidate answer, leaving viability assessment for later.
        instructions = payload["instructions"]
        assert "bounded STRATEGY" in instructions
        assert "concise, specific title of 2–12 words" in instructions
        assert "not a complete solution" in instructions
        assert "first discriminating" in instructions
        assert "other required JSON fields concise" in instructions
        context = json.loads(payload["input"])
        assert context["research_problem"] == "A real mathematical question"
        assert context["research_mode"] == "mathematical"
        assert context["existing_strategies"][0]["approach"] == "Existing full content"
        assert len(context["starting_point"]) <= 4000
        assert {row["id"] for row in context["prior_research_findings"]} >= {
            "finding-moment",
            "finding-boundary",
        }
        calls.append(payload)
        return httpx.Response(200, json=response())

    def client(**kwargs):
        return REAL_CLIENT(transport=httpx.MockTransport(handler), **kwargs)

    with patch("sigma.proposals.httpx.AsyncClient", side_effect=client):
        first = await proposals.generate_proposal(str(path), consent=True)
        second = await proposals.generate_proposal(str(path), "Try a necessary condition", True)
        assert (path / "project.json").read_bytes() == before
        provenance = proposals.accepted_provenance(first["receipt"], str(path))
        assert provenance.model == "gpt-4.1-fixture"
        with TestClient(app) as api:

            def inference_request(request_id, *, binding=None, mode="api_key"):
                current_binding = api.get(
                    "/api/projects/proposals/config", params={"path": str(path)}
                ).json()["binding"]
                return {
                    "path": str(path),
                    "expected_project_id": inspect_project(path).project.id,
                    "expected_binding": binding or current_binding,
                    "expected_mode": mode,
                    "request_id": request_id,
                }

            generated = api.post(
                "/api/projects/proposals",
                json={
                    "path": str(path),
                    "seed": "",
                    "expected_project_id": inspect_project(path).project.id,
                },
            )
            assert generated.status_code == 200, generated.text
            assert generated.json()["draft"]["title"] == DRAFT["title"]
            assert generated.json()["provenance"]["model"] == "gpt-4.1-fixture"
            before_suggestion = (path / "project.json").read_bytes()
            suggestion = api.post(
                "/api/projects/strategy-suggestions",
                json={"path": str(path), "expected_project_id": inspect_project(path).project.id},
            )
            assert suggestion.status_code == 200, suggestion.text
            assert suggestion.json()["markdown"].startswith("## Independent boundary test")
            assert (path / "project.json").read_bytes() == before_suggestion
            suggestion_output["markdown"] = None
            no_suggestion = api.post(
                "/api/projects/strategy-suggestions",
                json={"path": str(path), "expected_project_id": inspect_project(path).project.id},
            )
            assert no_suggestion.status_code == 200 and no_suggestion.json()["markdown"] is None
            assert (path / "project.json").read_bytes() == before_suggestion
            suggestion_output["markdown"] = (
                "## Existing direction\n\nRepeat the already saved strategy."
            )
            duplicate = api.post(
                "/api/projects/strategy-suggestions",
                json={"path": str(path), "expected_project_id": inspect_project(path).project.id},
            )
            assert duplicate.status_code == 200 and duplicate.json()["markdown"] is None
            assert (path / "project.json").read_bytes() == before_suggestion
            assert (
                api.get(
                    "/api/projects/continuations/proposal",
                    params={"path": str(path), "parent_strategy_id": "unused"},
                ).status_code
                == 404
            )
            accepted = api.post(
                "/api/projects/strategies",
                json={
                    "path": str(path),
                    "title": "Human edited proposal",
                    "approach": DRAFT["approach"],
                    "summary": DRAFT["summary"],
                    "receipt": second["receipt"],
                },
            )
            assert accepted.status_code == 201, accepted.text
            assert (
                accepted.json()["project"]["strategies"][-1]["provenance"]["provider"] == "openai"
            )
            inferred = api.post(
                "/api/projects/strategy-inference",
                json={
                    "path": str(path),
                    "expected_project_id": inspect_project(path).project.id,
                    "expected_binding": api.get(
                        "/api/projects/proposals/config", params={"path": str(path)}
                    ).json()["binding"],
                    "expected_mode": "api_key",
                    "request_id": "00000000-0000-4000-8000-000000000332",
                },
            )
            assert inferred.status_code == 200, inferred.text
            inferred_data = inferred.json()
            assert inferred_data["strategy"]["title"] == inference_output["title"]
            assert inferred_data["strategy"]["provenance"]["provider"] == "openai"
            assert (
                len(inferred_data["project"]["project"]["strategies"])
                == len(accepted.json()["project"]["strategies"]) + 1
            )
            replay = api.post(
                "/api/projects/strategy-inference",
                json={
                    "path": str(path),
                    "expected_project_id": inspect_project(path).project.id,
                    "expected_binding": api.get(
                        "/api/projects/proposals/config", params={"path": str(path)}
                    ).json()["binding"],
                    "expected_mode": "api_key",
                    "request_id": "00000000-0000-4000-8000-000000000332",
                },
            )
            assert replay.status_code == 200, replay.text()
            assert replay.json() == inferred_data, (inferred_data, replay.json())
            inference_count = len(inference_calls)
            removed = api.post(
                "/api/projects/strategies/remove",
                json={"path": str(path), "strategy_id": inferred_data["strategy"]["id"]},
            )
            assert removed.status_code == 200
            assert any(
                row["id"] == inferred_data["strategy"]["id"] and row["removed_at"]
                for row in removed.json()["project"]["strategies"]
            )
            restarted = await asyncio.to_thread(
                subprocess.run,
                [
                    sys.executable,
                    "-c",
                    "import json,sys; from sigma.proposals import inference_status; print(json.dumps(inference_status(sys.argv[1], sys.argv[2], sys.argv[3])))",
                    str(path),
                    inspect_project(path).project.id,
                    "00000000-0000-4000-8000-000000000332",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            restart_state = json.loads(restarted.stdout)
            assert restart_state["status"] == "completed"
            assert restart_state["strategy"]["removed_at"]
            replay_after_remove = api.post(
                "/api/projects/strategy-inference",
                json={
                    "path": str(path),
                    "expected_project_id": inspect_project(path).project.id,
                    "expected_binding": api.get(
                        "/api/projects/proposals/config", params={"path": str(path)}
                    ).json()["binding"],
                    "expected_mode": "api_key",
                    "request_id": "00000000-0000-4000-8000-000000000332",
                },
            )
            assert replay_after_remove.status_code == 200
            assert replay_after_remove.json()["strategy"]["removed_at"]
            assert (
                replay_after_remove.json()["project"]["project"]["strategies"]
                == removed.json()["project"]["strategies"]
            )
            assert len(inference_calls) == inference_count
            completed_cancel = api.post(
                "/api/projects/proposals/cancel",
                json=inference_request("00000000-0000-4000-8000-000000000332"),
            )
            assert completed_cancel.status_code == 200
            assert completed_cancel.json()["status"] == "completed"
            assert completed_cancel.json()["strategy"]["removed_at"]

            reserved_id = "00000000-0000-4000-8000-000000000336"
            reserved_action, _ = proposals.begin_inference(
                str(path),
                inspect_project(path).project.id,
                reserved_id,
                inference_request(reserved_id)["expected_binding"],
                "api_key",
            )
            assert reserved_action == "run"
            cancelled_before_send = api.post(
                "/api/projects/proposals/cancel", json=inference_request(reserved_id)
            )
            assert cancelled_before_send.status_code == 200
            assert cancelled_before_send.json()["status"] == "cancelled"

            count_before_account_rejection = len(inference_calls)
            account_rejected = api.post(
                "/api/projects/strategy-inference",
                json=inference_request(
                    "00000000-0000-4000-8000-000000000337", binding="different-account"
                ),
            )
            assert account_rejected.status_code == 400
            assert len(inference_calls) == count_before_account_rejection

            async def provider_failure_hook():
                return httpx.Response(503, json={"error": {"message": "fixture provider failure"}})

            inference_hook = provider_failure_hook
            provider_failure_id = "00000000-0000-4000-8000-000000000338"
            before_provider_failure = len(inference_calls)
            provider_failure = api.post(
                "/api/projects/strategy-inference", json=inference_request(provider_failure_id)
            )
            assert provider_failure.status_code >= 400
            provider_failure_retry = api.post(
                "/api/projects/strategy-inference", json=inference_request(provider_failure_id)
            )
            assert provider_failure_retry.status_code >= 400
            assert len(inference_calls) == before_provider_failure + 1

            async def timeout_provider_hook():
                raise httpx.ReadTimeout("fixture response lost after dispatch")

            inference_hook = timeout_provider_hook
            timeout_id = "00000000-0000-4000-8000-000000000339"
            before_timeout = len(inference_calls)
            timed_out = api.post(
                "/api/projects/strategy-inference", json=inference_request(timeout_id)
            )
            assert timed_out.status_code >= 400
            timeout_retry = api.post(
                "/api/projects/strategy-inference", json=inference_request(timeout_id)
            )
            assert timeout_retry.status_code >= 400
            assert len(inference_calls) == before_timeout + 1

            async def mutate_history_during_provider():
                create_strategy(
                    path,
                    "Concurrent human direction",
                    "A direction saved while inference was in flight.",
                )

            inference_hook = mutate_history_during_provider
            changed_history_id = "00000000-0000-4000-8000-000000000340"
            before_history_change = len(inference_calls)
            history_changed = api.post(
                "/api/projects/strategy-inference", json=inference_request(changed_history_id)
            )
            assert history_changed.status_code >= 400
            assert not any(
                row.provenance and row.provenance.inference_request_id == changed_history_id
                for row in inspect_project(path).project.strategies
            )
            history_retry = api.post(
                "/api/projects/strategy-inference", json=inference_request(changed_history_id)
            )
            assert history_retry.status_code >= 400
            assert len(inference_calls) == before_history_change + 1

            async def mutate_settings_during_provider():
                current = inspect_project(path).project
                settings = project_settings(current)
                update_project(
                    path,
                    "Edited project title during inference",
                    settings.problem,
                    settings.investigation_type.value,
                    settings.ai_model,
                    settings.reasoning_effort,
                    asdict(settings),
                    difficulty=settings.difficulty.value if settings.difficulty else None,
                    show_advanced_outcome_details=settings.show_advanced_outcome_details,
                )

            inference_hook = mutate_settings_during_provider
            changed_settings_id = "00000000-0000-4000-8000-000000000344"
            before_settings_change = len(inference_calls)
            settings_changed = api.post(
                "/api/projects/strategy-inference", json=inference_request(changed_settings_id)
            )
            assert settings_changed.status_code >= 400
            assert not any(
                row.provenance and row.provenance.inference_request_id == changed_settings_id
                for row in inspect_project(path).project.strategies
            )
            settings_retry = api.post(
                "/api/projects/strategy-inference", json=inference_request(changed_settings_id)
            )
            assert settings_retry.status_code >= 400
            assert len(inference_calls) == before_settings_change + 1
            replay_after_edit = api.post(
                "/api/projects/strategy-inference",
                json=inference_request("00000000-0000-4000-8000-000000000332"),
            )
            assert replay_after_edit.status_code == 200
            assert (
                replay_after_edit.json()["project"]["project"]["title"]
                == "Edited project title during inference"
            )
            assert replay_after_edit.json()["strategy"]["removed_at"]
            assert len(inference_calls) == before_settings_change + 1

            account_changed = False
            original_auth_context = proposals.auth_context

            async def changing_auth_context(*args, **kwargs):
                result = await original_auth_context(*args, **kwargs)
                return {**result, "identity": "changed-account"} if account_changed else result

            async def switch_account_during_provider():
                nonlocal account_changed
                account_changed = True

            inference_hook = switch_account_during_provider
            changed_account_id = "00000000-0000-4000-8000-000000000341"
            before_account_change = len(inference_calls)
            with patch("sigma.proposals.auth_context", side_effect=changing_auth_context):
                account_changed_response = api.post(
                    "/api/projects/strategy-inference", json=inference_request(changed_account_id)
                )
            account_changed = False
            assert account_changed_response.status_code >= 400
            assert not any(
                row.provenance and row.provenance.inference_request_id == changed_account_id
                for row in inspect_project(path).project.strategies
            )
            account_retry = api.post(
                "/api/projects/strategy-inference", json=inference_request(changed_account_id)
            )
            assert account_retry.status_code >= 400
            assert len(inference_calls) == before_account_change + 1

            inference_hook = None
            inference_output.update(
                title="Boundary spectral stability",
                summary="Test spectral stability at the unresolved boundary.",
                approach="Derive a spectral stability criterion for the boundary family and evaluate its limits on small parameter cases, treating computations as exploratory evidence.",
            )
            write_failure_id = "00000000-0000-4000-8000-000000000342"
            before_write_failure = len(inference_calls)
            with patch(
                "sigma.projects.create_strategy",
                side_effect=ProjectError("fixture disk failure"),
            ):
                write_failed = api.post(
                    "/api/projects/strategy-inference", json=inference_request(write_failure_id)
                )
            assert write_failed.status_code >= 400
            recovered_write = api.post(
                "/api/projects/strategy-inference", json=inference_request(write_failure_id)
            )
            assert recovered_write.status_code == 200, recovered_write.text()
            assert recovered_write.json()["strategy"]["title"] == inference_output["title"]
            assert len(inference_calls) == before_write_failure + 1

            # Sponsored inference begins one durable spending attempt. A replay
            # returns its persisted result without reserving or settling again.
            class BillingAttempt:
                dispatched = False
                settled = False
                job_id = "fixture-job"

            spending_attempts = []
            settled_attempts = []
            billing_identity = {
                "identity": "fixture-sponsored-user",
                "mode": "api_key",
                "token": "fixture",
                "status": "connected",
            }
            inference_output.update(
                title="Weighted boundary concentration",
                summary="Test a weighted concentration estimate near the boundary.",
                approach="Derive a weighted concentration bound for the boundary family and compare it against independently enumerated small cases, treating computation as evidence rather than proof.",
            )
            billing_id = "00000000-0000-4000-8000-000000000343"
            _, billing_record = proposals.begin_inference(
                str(path),
                inspect_project(path).project.id,
                billing_id,
                billing_identity["identity"],
                billing_identity["mode"],
            )
            with (
                patch(
                    "sigma.proposals.cloud_workspaces",
                    SimpleNamespace(enabled=lambda: True, current=lambda: None),
                ),
                patch("sigma.proposals.auth_context", new=AsyncMock(return_value=billing_identity)),
                patch("sigma.proposals.cloud_credential", return_value=True),
                patch(
                    "sigma.proposals.cloud_research.start_provider_attempt",
                    side_effect=lambda *_args: (
                        spending_attempts.append(BillingAttempt()) or spending_attempts[-1]
                    ),
                ),
                patch(
                    "sigma.proposals.cloud_research.settle_provider_attempt",
                    side_effect=lambda attempt, _raw: settled_attempts.append(attempt),
                ),
                patch("sigma.proposals.cloud_research.finish_provider_attempt"),
            ):
                result = await proposals.generate_proposal(
                    str(path),
                    expected_binding=billing_identity["identity"],
                    expected_mode=billing_identity["mode"],
                    expected_project_id=inspect_project(path).project.id,
                    infer_strategy=True,
                    request_id=billing_id,
                    inference_owner=billing_record["owner"],
                )
                assert result["strategy"] is not None
                replay_action, replay_record = proposals.begin_inference(
                    str(path),
                    inspect_project(path).project.id,
                    billing_id,
                    billing_identity["identity"],
                    billing_identity["mode"],
                )
                assert replay_action == "return"
                proposals.inference_result(str(path), billing_id, replay_record)
            assert len(spending_attempts) == 1
            assert len(settled_attempts) == 1

            async def delayed_configuration(*args, **kwargs):
                config_entered.set()
                await asyncio.to_thread(config_release.wait, 8)
                return await original_configuration(*args, **kwargs)

            config_entered = threading.Event()
            config_release = threading.Event()
            original_configuration = proposals.configuration
            config_cancel_id = "00000000-0000-4000-8000-000000000345"
            config_cancel_body = inference_request(config_cancel_id)
            before_config_cancel = len(inference_calls)
            with (
                patch("sigma.proposals.configuration", side_effect=delayed_configuration),
                concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor,
            ):
                config_request = executor.submit(
                    api.post, "/api/projects/strategy-inference", json=config_cancel_body
                )
                assert config_entered.wait(5)
                config_cancel = api.post("/api/projects/proposals/cancel", json=config_cancel_body)
                assert config_cancel.status_code == 200
                assert config_cancel.json()["status"] == "cancelled"
                config_release.set()
                assert config_request.result(timeout=8).status_code >= 400
            assert len(inference_calls) == before_config_cancel

            provider_entered = threading.Event()
            provider_release = threading.Event()

            async def delayed_provider():
                provider_entered.set()
                await asyncio.to_thread(provider_release.wait, 8)

            inference_hook = delayed_provider
            provider_cancel_id = "00000000-0000-4000-8000-000000000346"
            provider_cancel_body = inference_request(provider_cancel_id)
            before_provider_cancel = len(inference_calls)
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                provider_request = executor.submit(
                    api.post, "/api/projects/strategy-inference", json=provider_cancel_body
                )
                assert provider_entered.wait(5)
                duplicate_inflight = api.post(
                    "/api/projects/strategy-inference", json=provider_cancel_body
                )
                assert duplicate_inflight.status_code >= 400
                assert len(inference_calls) == before_provider_cancel + 1
                provider_cancel = api.post(
                    "/api/projects/proposals/cancel", json=provider_cancel_body
                )
                assert provider_cancel.status_code == 200
                assert provider_cancel.json()["status"] == "uncertain"
                provider_release.set()
                assert provider_request.result(timeout=8).status_code >= 400
            inference_hook = None
            assert len(inference_calls) == before_provider_cancel + 1
            cancel_retry = api.post("/api/projects/strategy-inference", json=provider_cancel_body)
            assert cancel_retry.status_code >= 400
            assert len(inference_calls) == before_provider_cancel + 1

            failed_cancel_id = "00000000-0000-4000-8000-000000000347"
            failed_cancel_body = inference_request(failed_cancel_id)
            _, failed_cancel_record = proposals.begin_inference(
                str(path),
                inspect_project(path).project.id,
                failed_cancel_id,
                failed_cancel_body["expected_binding"],
                "api_key",
            )
            with patch(
                "sigma.proposals.cancel_inference",
                side_effect=ProjectError("fixture cancellation channel failed"),
            ):
                failed_cancel = api.post("/api/projects/proposals/cancel", json=failed_cancel_body)
            assert failed_cancel.status_code == 400
            assert failed_cancel_record["status"] == "reserved"
            before_failed_cancel_retry = len(inference_calls)
            retried_after_failed_cancel = api.post(
                "/api/projects/strategy-inference", json=failed_cancel_body
            )
            assert retried_after_failed_cancel.status_code == 200
            assert len(inference_calls) == before_failed_cancel_retry + 1

            inference_output.update(
                title="Boundary remainder compactness",
                summary="Test whether compactness controls the boundary remainder.",
                approach="Formulate a compactness estimate for the boundary remainder and test its hypotheses on small parameter cases, treating computation as exploratory evidence.",
            )
            commit_race_id = "00000000-0000-4000-8000-000000000348"
            writer_started = threading.Event()
            writer_finished = threading.Event()
            real_snapshot_guard = proposals._assert_inference_snapshot

            def write_during_commit():
                writer_started.set()
                session_record = research_sessions._read(
                    str(path), "00000000-0000-4000-8000-000000000002"
                )
                session_record["artifacts"][0]["evidence_status"] = (
                    "Updated after inference commit."
                )
                research_sessions._save(str(path), session_record)
                current = inspect_project(path).project
                settings = project_settings(current)
                update_project(
                    path,
                    "Settings writer after inference commit",
                    settings.problem,
                    settings.investigation_type.value,
                    settings.ai_model,
                    settings.reasoning_effort,
                    asdict(settings),
                    difficulty=settings.difficulty.value if settings.difficulty else None,
                    show_advanced_outcome_details=settings.show_advanced_outcome_details,
                )
                writer_finished.set()

            def guarded_snapshot(path_value, request_id, record, project):
                real_snapshot_guard(path_value, request_id, record, project)
                if request_id == commit_race_id:
                    threading.Thread(target=write_during_commit, daemon=True).start()
                    assert writer_started.wait(2)
                    assert not writer_finished.wait(0.1), (
                        "evidence/settings writer crossed inference commit lock"
                    )

            before_commit_race = len(inference_calls)
            with patch("sigma.proposals._assert_inference_snapshot", side_effect=guarded_snapshot):
                commit_race = api.post(
                    "/api/projects/strategy-inference", json=inference_request(commit_race_id)
                )
            assert commit_race.status_code == 200, commit_race.text()
            assert commit_race.json()["strategy"]["title"] == inference_output["title"]
            assert writer_finished.wait(3)
            assert len(inference_calls) == before_commit_race + 1
            unchanged_after_remove = (path / "project.json").read_bytes()
            no_novel = api.post(
                "/api/projects/strategy-inference",
                json={
                    "path": str(path),
                    "expected_project_id": inspect_project(path).project.id,
                    "expected_binding": api.get(
                        "/api/projects/proposals/config", params={"path": str(path)}
                    ).json()["binding"],
                    "expected_mode": "api_key",
                    "request_id": "00000000-0000-4000-8000-000000000333",
                },
            )
            assert no_novel.status_code == 200 and no_novel.json()["strategy"] is None
            assert (path / "project.json").read_bytes() == unchanged_after_remove
            inference_output.clear()
            inference_output["title"] = "Incomplete structured output"
            invalid = api.post(
                "/api/projects/strategy-inference",
                json={
                    "path": str(path),
                    "expected_project_id": inspect_project(path).project.id,
                    "expected_binding": api.get(
                        "/api/projects/proposals/config", params={"path": str(path)}
                    ).json()["binding"],
                    "expected_mode": "api_key",
                    "request_id": "00000000-0000-4000-8000-000000000334",
                },
            )
            assert invalid.status_code != 200, invalid.text
            assert (path / "project.json").read_bytes() == unchanged_after_remove
            stale_mode = api.post(
                "/api/projects/strategy-inference",
                json={
                    "path": str(path),
                    "expected_project_id": inspect_project(path).project.id,
                    "expected_binding": api.get(
                        "/api/projects/proposals/config", params={"path": str(path)}
                    ).json()["binding"],
                    "expected_mode": "chatgpt",
                    "request_id": "00000000-0000-4000-8000-000000000335",
                },
            )
            assert stale_mode.status_code == 400
            assert (path / "project.json").read_bytes() == unchanged_after_remove
            stale = api.post(
                "/api/projects/strategies",
                json={
                    "path": str(path),
                    "title": "Stale generated draft",
                    "approach": DRAFT["approach"],
                    "receipt": second["receipt"],
                },
            )
            assert stale.status_code == 400 and "inputs changed" in stale.json()["error"]
            assert (
                api.post(
                    "/api/projects/strategies",
                    json={"path": str(path), "title": "X", "approach": "Y", "receipt": "forged"},
                ).status_code
                == 400
            )
        assert len(inference_calls) == 13
        unchanged = (path / "project.json").read_bytes()
        original_binding = {
            "identity": "proposal-account",
            "mode": "api_key",
            "token": "fixture",
            "status": "connected",
        }
        switched_binding = {
            "identity": "other-account",
            "mode": "api_key",
            "token": "fixture",
            "status": "connected",
        }
        with (
            patch(
                "sigma.proposals.auth_context",
                new=AsyncMock(side_effect=[original_binding, original_binding, switched_binding]),
            ),
            patch("sigma.proposals.httpx.AsyncClient", side_effect=client),
        ):
            await rejects(
                proposals.generate_proposal(
                    str(path),
                    expected_binding="proposal-account",
                    expected_project_id=inspect_project(path).project.id,
                ),
                "changed during generation",
            )
        assert (path / "project.json").read_bytes() == unchanged
        await rejects(
            proposals.generate_proposal(str(path), consent=True), "repeats"
        )  # Repeated approach.

    source = {
        "project_id": project_id,
        "session_id": "suggestion-context-session",
        "session_number": 4,
        "strategy_id": "suggestion-context-strategy",
        "artifact_id": "suggestion-context-artifact",
    }
    large_understanding = {
        "scope_note": "All findings remain unverified.",
        "session_count": 4,
        "findings": [
            {
                "id": "current-finding",
                "text": "Saved finding. " * 90,
                "investigated_claim": "Conditional claim. " * 90,
                "source": source,
                "review_ref": "artifacts/suggestion-context-artifact/objective_review",
                "review_status": "partial",
                "status": "unassessed",
                "verification": "Incomplete",
                "local_scope": "Local strategy finding only.",
                "strategy_title": "Existing direction",
                "strategy_text": "Existing full content",
                "assumptions": ["Assumption. " * 30 for _ in range(6)],
                "objections": ["Unresolved objection. " * 30 for _ in range(6)],
                "evidence_kind": "Unverified source-backed evidence.",
                "related_by": [],
            }
        ],
        "current_finding_ids": ["current-finding"],
        "changes": [
            {
                "kind": "supersedes",
                "text": "Changed claim. " * 60,
                "caution": "Unverified.",
                "source": source,
                "earlier": None,
            }
            for _ in range(28)
        ],
        "obligations": [
            {
                "id": f"obligation-{number:03d}",
                "text": f"Open question {number}. " + "Investigate the boundary. " * 18,
                "kind": "obligation",
                "strategy_id": "suggestion-context-strategy",
                "status": "historical_unreconciled",
                "actionable": number % 2 == 0,
                "sources": [source],
                "note": "Historical and not reconciled.",
            }
            for number in range(80)
        ],
        "failures": [
            {
                "session_id": f"failure-{number}",
                "session_number": number,
                "status": "failed",
                "note": "Preserved." * 30,
            }
            for number in range(20)
        ],
        "limitations": [f"Limitation {number}. " * 40 for number in range(16)],
        "next_investigations": [],
    }
    with (
        patch("sigma.research_state.build_current_understanding", return_value=large_understanding),
        patch(
            "sigma.research_sessions.strategy_generation_findings",
            return_value=[
                {"id": "bounded-source", "claim_or_question": "A relevant saved result."}
            ],
        ),
    ):
        bounded_project_id, bounded_context = proposals.suggestion_context_for(str(path))
    bounded = json.loads(bounded_context)
    omitted = bounded["context_selection"]["omitted"]
    assert bounded_project_id == project_id and len(bounded_context) <= proposals.MAX_CONTEXT
    assert bounded["project_question"] == inspect_project(path).project.problem
    assert (
        bounded["existing_strategies_including_disabled"][0]["approach"] == "Existing full content"
    )
    assert len(bounded["current_understanding"]["open_questions"]) == 12
    assert omitted["open_questions"] == 68
    assert len(omitted["open_question_ids"]) == 32
    assert omitted["additional_open_question_ids_omitted"] == 36
    assert omitted["changes"] == 20 and omitted["execution_states"] == 12
    print(
        "PASS exact Responses request/strict schema, nonmutating strategy suggestions, bounded Current Understanding with omission accounting, human-edited acceptance and signed provenance"
    )
    for fixture in (
        httpx.Response(429),
        httpx.Response(200, json={"status": "incomplete"}),
        httpx.Response(200, text="not JSON"),
        httpx.Response(200, json=response({**DRAFT, "title": ""})),
        httpx.Response(200, json=response({**DRAFT, "title": "one\ntwo"})),
        httpx.Response(
            200,
            json=response(
                {
                    **DRAFT,
                    "title": "one two three four five six seven eight nine ten eleven twelve thirteen",
                }
            ),
        ),
        httpx.Response(200, json=response({**DRAFT, "summary": "two\nlines"})),
        httpx.Response(
            200,
            json={
                "status": "completed",
                "output": [{"type": "message", "content": [{"type": "refusal"}]}],
            },
        ),
    ):

        def failed_client(fixture=fixture, **kwargs):
            return REAL_CLIENT(transport=httpx.MockTransport(lambda request: fixture), **kwargs)

        with patch("sigma.proposals.httpx.AsyncClient", side_effect=failed_client):
            snapshot = (path / "project.json").read_bytes()
            await rejects(proposals.generate_proposal(str(path), consent=True))
            assert (path / "project.json").read_bytes() == snapshot

    synthetic_credential = "synthetic-provider-credential-do-not-log"

    async def credential_echo(request):
        if request.method == "GET":
            return httpx.Response(
                200,
                json={"object": "list", "data": [{"id": "gpt-6.1-sol"}]},
            )
        assert request.headers["authorization"] == f"Bearer {synthetic_credential}"
        return httpx.Response(
            401,
            json={"error": {"code": "unauthorized", "message": synthetic_credential}},
        )

    def credential_echo_client(**kwargs):
        return REAL_CLIENT(transport=httpx.MockTransport(credential_echo), **kwargs)

    with (
        patch.dict(os.environ, {"OPENAI_API_KEY": synthetic_credential}),
        patch("sigma.proposals.httpx.AsyncClient", side_effect=credential_echo_client),
    ):
        try:
            await proposals.generate_proposal(str(path), consent=True)
        except ProjectError as exc:
            assert synthetic_credential not in str(exc)
        else:
            raise AssertionError("Expected synthetic provider credential rejection")
        openai_connection.clear_cache_for_tests()
    with patch("sigma.proposals.httpx.AsyncClient", side_effect=client):
        await proposals.configuration(str(path))

    request_started = asyncio.Event()

    async def slow(request):
        request_started.set()
        await asyncio.sleep(30)
        return httpx.Response(200, json=response())

    def slow_client(**kwargs):
        return REAL_CLIENT(transport=httpx.MockTransport(slow), **kwargs)

    with patch("sigma.proposals.httpx.AsyncClient", side_effect=slow_client):
        pending = asyncio.create_task(proposals.generate_proposal(str(path), consent=True))
        await asyncio.wait_for(request_started.wait(), timeout=2)
        await rejects(proposals.generate_proposal(str(path), consent=True))
        request_id = "test-cancel-request"
        proposals.register_request(request_id, pending)
        assert await proposals.cancel_request(request_id)
        proposals.unregister_request(request_id, pending)
        assert not proposals._gate.locked()
        with patch("sigma.proposals.TIMEOUT_SECONDS", 0.01):
            await rejects(proposals.generate_proposal(str(path), consent=True))
        assert not proposals._gate.locked()
    # Exercise actual ASGI middleware/endpoint disconnection, not just the service.
    started = asyncio.Event()

    async def pending_provider(request):
        started.set()
        await asyncio.sleep(20)
        return httpx.Response(200, json=response())

    def disconnect_client(**kwargs):
        return REAL_CLIENT(transport=httpx.MockTransport(pending_provider), **kwargs)

    queue = asyncio.Queue()
    await queue.put(
        {
            "type": "http.request",
            "body": json.dumps({"path": str(path), "consent": True}).encode(),
            "more_body": False,
        }
    )
    sent = []

    async def send(message):
        sent.append(message)

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/api/projects/proposals",
        "raw_path": b"/api/projects/proposals",
        "query_string": b"",
        "root_path": "",
        "headers": [(b"host", b"testserver"), (b"content-type", b"application/json")],
        "server": ("testserver", 80),
        "client": ("127.0.0.1", 1234),
    }
    with patch("sigma.proposals.httpx.AsyncClient", side_effect=disconnect_client):
        serving = asyncio.create_task(app(scope, queue.get, send))
        await asyncio.wait_for(started.wait(), timeout=2)
        await queue.put({"type": "http.disconnect"})
        await asyncio.wait_for(serving, timeout=2)
        assert not proposals._gate.locked()
    print(
        "PASS ASGI endpoint disconnection through middleware cancels transport and releases request slot"
    )
    for i in range(6):
        create_strategy(path, str(i), "X" * 10000)
    with patch("sigma.proposals.httpx.AsyncClient", side_effect=AssertionError("must not send")):
        await rejects(proposals.generate_proposal(str(path), consent=True))
    with patch.dict(os.environ, {"OPENAI_API_KEY": ""}):
        await rejects(proposals.generate_proposal(str(path), consent=True))
    with patch.dict(os.environ, {"SIGMA_AI_MODEL": "bad model"}):
        from sigma.model_catalog import legacy_model

        assert legacy_model() == "gpt-6.1-sol"
    print(
        "PASS unavailable/invalid configuration, malformed/refused/incomplete/rate errors, duplicate, hard timeout, cancellation, concurrency and oversized-context nonmutation"
    )


def main():
    with (
        TemporaryDirectory() as directory,
        patch.dict(
            os.environ,
            {
                "SIGMA_AUTH_HOME": str(Path(directory) / "auth"),
                "OPENAI_API_KEY": "explicit-test-fixture-not-a-secret",
                "SIGMA_AI_MODEL": "gpt-4.1",
            },
        ),
    ):
        path = Path(directory) / "proposal.sigma"
        initialize_project(path, "Proposal fixture", "A real mathematical question", "mathematical")
        create_strategy(path, "Existing direction", "Existing full content")
        set_strategy_enabled(path, inspect_project(path).project.strategies[0].id, False)
        asyncio.run(check(path))
        assert inspect_project(path).project.strategies[0].provenance is None


if __name__ == "__main__":
    main()
