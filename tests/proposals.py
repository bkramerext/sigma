"""Controlled HTTP transport fixtures exercise the real adapter; no paid calls."""

import asyncio
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
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
    set_strategy_enabled,
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
    suggestion_output: dict[str, str | None] = {
        "markdown": "## Independent boundary test\n\nCompare the boundary case with the saved moment positivity approach.\n\n**Rationale:** Session evidence leaves the boundary obligation open."
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
        assert len(calls) == 6
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
    openai_connection._identity = ""
    openai_connection._cached = None
    openai_connection._known = set()
    openai_connection._pending = None
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
