"""Controlled HTTP transport fixtures exercise the real adapter; no paid calls."""

import asyncio
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient

from sigma import chatgpt_auth, proposals
from sigma.api import app
from sigma.investigations import (
    InvestigationError,
    create_strategy,
    initialize_investigation,
    inspect_investigation,
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
    except InvestigationError as exc:
        if contains is not None:
            assert contains in str(exc), str(exc)
        return
    raise AssertionError("Expected proposal rejection")


async def check(path):
    await chatgpt_auth.select("api_key")
    before = (path / "investigation.json").read_bytes()
    calls = []

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
        assert payload["max_output_tokens"] == 25000
        context = json.loads(payload["input"])
        assert context["research_problem"] == "A real mathematical question"
        assert context["research_mode"] == "mathematical"
        assert context["existing_strategies"][0]["approach"] == "Existing full content"
        assert len(context["starting_point"]) <= 4000
        calls.append(payload)
        return httpx.Response(200, json=response())

    def client(**kwargs):
        return REAL_CLIENT(transport=httpx.MockTransport(handler), **kwargs)

    with patch("sigma.proposals.httpx.AsyncClient", side_effect=client):
        first = await proposals.generate_proposal(str(path), consent=True)
        second = await proposals.generate_proposal(str(path), "Try a necessary condition", True)
        assert len(calls) == 2
        assert (path / "investigation.json").read_bytes() == before
        provenance = proposals.accepted_provenance(first["receipt"], str(path))
        assert provenance.model == "gpt-4.1-fixture"
        with TestClient(app) as api:
            accepted = api.post(
                "/api/investigations/strategies",
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
                accepted.json()["investigation"]["strategies"][-1]["provenance"]["provider"]
                == "openai"
            )
            assert (
                api.post(
                    "/api/investigations/strategies",
                    json={"path": str(path), "title": "X", "approach": "Y", "receipt": "forged"},
                ).status_code
                == 400
            )
        await rejects(
            proposals.generate_proposal(str(path), consent=True), "repeats"
        )  # Repeated approach.
    print(
        "PASS exact Responses request/strict schema/full context, empty/seed, nonmutation, human-edited acceptance and signed provenance"
    )
    for fixture in (
        httpx.Response(429),
        httpx.Response(200, json={"status": "incomplete"}),
        httpx.Response(200, text="not JSON"),
        httpx.Response(200, json=response({**DRAFT, "title": ""})),
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
            snapshot = (path / "investigation.json").read_bytes()
            await rejects(proposals.generate_proposal(str(path), consent=True))
            assert (path / "investigation.json").read_bytes() == snapshot

    async def slow(request):
        await asyncio.sleep(1)
        return httpx.Response(200, json=response())

    def slow_client(**kwargs):
        return REAL_CLIENT(transport=httpx.MockTransport(slow), **kwargs)

    with patch("sigma.proposals.httpx.AsyncClient", side_effect=slow_client):
        pending = asyncio.create_task(proposals.generate_proposal(str(path), consent=True))
        await asyncio.sleep(0.01)
        await rejects(proposals.generate_proposal(str(path), consent=True))
        pending.cancel()
        try:
            await pending
        except asyncio.CancelledError:
            pass
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
        "path": "/api/investigations/proposals",
        "raw_path": b"/api/investigations/proposals",
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
        initialize_investigation(
            path, "Proposal fixture", "A real mathematical question", "mathematical"
        )
        create_strategy(path, "Existing direction", "Existing full content")
        asyncio.run(check(path))
        assert inspect_investigation(path).investigation.strategies[0].provenance is None


if __name__ == "__main__":
    main()
