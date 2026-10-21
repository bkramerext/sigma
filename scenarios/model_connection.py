"""No-network fixtures: classified discovery, cache/coalescing, project model snapshots."""

import asyncio
import json
import os
from dataclasses import asdict
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import httpx

from sigma import openai_connection as connection
from sigma.model_catalog import CATALOG
from sigma.projects import (
    ProjectError,
    create_strategy,
    initialize_project,
    inspect_project,
    project_settings,
    update_project,
)
from sigma.proposals import accepted_provenance, configuration, generate_proposal

REAL_CLIENT = httpx.AsyncClient
KEY = "non-secret-discovery-fixture"
MODELS = {
    "object": "list",
    "data": [{"id": i} for i in [*CATALOG, "gpt-unreviewed", "text-embedding-3-small"]],
}
DRAFT = {
    "title": "Bounded kernel obstruction",
    "summary": "Compare a concrete kernel inequality with a necessary bound.",
    "approach": "Derive the kernel inequality on an explicitly bounded domain and test counterexamples before extending it.",
    "first_tests": "Check small exact examples against independent calculations.",
    "assumptions": "Justify each limit interchange and domain restriction.",
    "failure_modes": "The bound may be necessary but insufficient.",
}


def reset():
    connection._identity = ""
    connection._cached = None
    connection._known = set()
    connection._pending = None


def client_factory(handler):
    return lambda **kwargs: REAL_CLIENT(transport=httpx.MockTransport(handler), **kwargs)


async def checks():
    calls = []

    async def success(request):
        calls.append(request)
        assert str(request.url) == "https://api.openai.com/v1/models"
        await asyncio.sleep(0.02)
        return httpx.Response(200, json=MODELS)

    reset()
    with patch("sigma.openai_connection.httpx.AsyncClient", side_effect=client_factory(success)):
        results = await asyncio.gather(*(connection.models() for _ in range(8)))
        assert len(calls) == 1
        assert all(r["connection"]["status"] == "connected" for r in results)
        assert {m["id"] for m in results[0]["models"]} == set(CATALOG)
        assert all(m["efforts"] == ("low", "medium", "high", "xhigh") for m in results[0]["models"])
        assert results[0]["default_model"] == "gpt-6.1-sol" and results[0]["default_verified"]
        await connection.connection()
        await connection.connection(refresh=True)
        assert len(calls) == 1  # cooldown also bounds retry spam.
        connection._at -= connection.TTL + 1
        await connection.models()
        assert len(calls) == 2
        connection._at -= 4
        await connection.connection(refresh=True)
        assert len(calls) == 3
    print(
        "PASS bounded curated account intersection, coalesced initial requests, TTL, retry cooldown and refresh"
    )
    for code, status in [
        (401, "unauthorized"),
        (403, "forbidden"),
        (429, "limited"),
        (500, "unavailable"),
        (302, "unavailable"),
    ]:
        reset()
        with patch(
            "sigma.openai_connection.httpx.AsyncClient",
            side_effect=client_factory(lambda r, code=code: httpx.Response(code, text=KEY)),
        ):
            state = await connection.connection()
            assert state["status"] == status, state
            assert KEY not in json.dumps(state)
            assert state["checked_at"]
    for raw in (
        {"data": []},
        {"object": "list", "data": [{"id": None}]},
        [],
        {"object": "list", "data": None},
    ):
        reset()
        with patch(
            "sigma.openai_connection.httpx.AsyncClient",
            side_effect=client_factory(lambda r, raw=raw: httpx.Response(200, json=raw)),
        ):
            assert (await connection.connection())["status"] == "invalid_response"
    reset()
    with patch(
        "sigma.openai_connection.httpx.AsyncClient",
        side_effect=client_factory(
            lambda r: httpx.Response(200, content=b"x" * (connection.MAX_BYTES + 1))
        ),
    ):
        assert (await connection.connection())["status"] == "invalid_response"

    def disconnected(request):
        raise httpx.ConnectError(KEY)

    reset()
    with patch(
        "sigma.openai_connection.httpx.AsyncClient", side_effect=client_factory(disconnected)
    ):
        assert (await connection.connection())["status"] == "unavailable"

    async def slow(request):
        await asyncio.sleep(1)
        return httpx.Response(200, json=MODELS)

    reset()
    with (
        patch("sigma.openai_connection.TIMEOUT", 0.01),
        patch("sigma.openai_connection.httpx.AsyncClient", side_effect=client_factory(slow)),
    ):
        assert (await connection.connection())["status"] == "unavailable"
    reset()
    with (
        patch.dict(os.environ, {"SIGMA_AI_ENABLED": "0"}),
        patch(
            "sigma.openai_connection.httpx.AsyncClient", side_effect=AssertionError("must not send")
        ),
    ):
        assert (await connection.models())["connection"]["status"] == "unconfigured"
    reset()
    with patch(
        "sigma.openai_connection.httpx.AsyncClient",
        side_effect=client_factory(
            lambda r: httpx.Response(200, json={"object": "list", "data": []})
        ),
    ):
        assert not (await connection.models())["default_verified"]
    print(
        "PASS missing/auth/permission/rate/provider/network/timeout/redirect/bad/oversized responses; no raw secret/error exposure or invented readiness"
    )
    with TemporaryDirectory() as directory:
        path = Path(directory) / "settings.sigma"
        initialize_project(
            path, "Snapshot", "A mathematical question", "mathematical", "gpt-6-luna", "xhigh"
        )
        initial = inspect_project(path)
        request_started = asyncio.Event()
        release = asyncio.Event()

        async def generate(request):
            if request.method == "GET":
                return httpx.Response(200, json=MODELS)
            payload = json.loads(request.content)
            assert payload["model"] == "gpt-6-luna" and payload["reasoning"] == {"effort": "xhigh"}
            assert (
                payload["max_output_tokens"] == 25000
                and payload["text"]["format"]["strict"] is True
            )
            request_started.set()
            await release.wait()
            return httpx.Response(
                200,
                json={
                    "status": "completed",
                    "model": "gpt-6-luna-returned",
                    "output": [
                        {
                            "type": "message",
                            "content": [{"type": "output_text", "text": json.dumps(DRAFT)}],
                        }
                    ],
                },
            )

        reset()
        with patch("sigma.proposals.httpx.AsyncClient", side_effect=client_factory(generate)):
            pending = asyncio.create_task(
                generate_proposal(str(path), "A starting constraint", True)
            )
            await asyncio.wait_for(request_started.wait(), 2)
            prior = asdict(project_settings(initial.project))
            update_project(
                path,
                **{**prior, "ai_model": "gpt-6-astra", "reasoning_effort": "low"},
                expected=prior,
            )
            release.set()
            draft = await pending
            provenance = accepted_provenance(draft["receipt"], str(path))
            assert (
                provenance.model == "gpt-6-luna-returned" and provenance.reasoning_effort == "xhigh"
            )
            before = inspect_project(path)
            assert not before.project.strategies
            accepted = create_strategy(
                path, DRAFT["title"], DRAFT["approach"], DRAFT["summary"], provenance
            )
            assert accepted.project.ai_model == "gpt-6-astra"
            assert accepted.project.strategies[-1].provenance == provenance
            assert inspect_project(path) == accepted
        reset()
        with patch(
            "sigma.openai_connection.httpx.AsyncClient",
            side_effect=client_factory(
                lambda r: httpx.Response(
                    200, json={"object": "list", "data": [{"id": "gpt-6-luna"}]}
                )
            ),
        ):
            config = await configuration(str(path))
            assert not config["available"] and config["model"] == "gpt-6-astra"
            try:
                await generate_proposal(str(path), consent=True)
            except ProjectError as exc:
                assert "unavailable" in str(exc)
            else:
                raise AssertionError("No model fallback allowed")
        # Catalog removal never erases settings or forces metadata edits to make network calls.
        with patch.dict(CATALOG, {}, clear=True):
            prior = asdict(project_settings(inspect_project(path).project))
            edited = update_project(path, **{**prior, "title": "Still editable"}, expected=prior)
            assert edited.project.ai_model == "gpt-6-astra"
    print(
        "PASS per-project model/actual effort request, immutable concurrent generation metadata, signed acceptance, unavailable choice/no fallback and offline metadata edits"
    )


def main():
    with patch.dict(os.environ, {"SIGMA_AI_ENABLED": "1", "OPENAI_API_KEY": KEY}):
        asyncio.run(checks())


if __name__ == "__main__":
    main()
