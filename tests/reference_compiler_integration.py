"""End-to-end, compiler-enabled research using a deterministic mock provider.

The normal legacy CI fixtures isolate research roles. This acceptance explicitly
enables the initial compilation step and verifies that a real session freezes
the source set, sends only the compact method guide to each role, and charges
the compiler without counting it as an Investigator/Skeptic turn.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent))
import research_sessions as fixture

from sigma import research_sessions


async def verify_compilation(path: Path) -> None:
    view, strategy, credential, config = await fixture.setup(path)
    limits = research_sessions.get_limits(str(path))
    limits.update(research_rounds=1, model_calls=2)
    research_sessions.save_limits(str(path), limits)
    # Explicit frozen references make this a deterministic compiler contract,
    # independent of the calling account's enabled Common guide preferences.
    source_catalog = {
        "version": "methodology-catalog-v2",
        "status": "selected",
        "mode": "mathematical",
        "branch": None,
        "selection_key": "fixture-mathematics-guides",
        "sources": [
            {
                "id": "proof",
                "tier": "discipline",
                "title": "Mathematics proof methods",
                "url": "https://example.org/proof",
                "notes": "Check induction, boundary cases, and counterexamples.",
                "project_type_id": "mathematical",
            },
            {
                "id": "irrelevant",
                "tier": "discipline",
                "title": "Unrelated writing style",
                "url": "https://example.org/irrelevant-writing",
                "notes": "Decorative text presentation without research methodology.",
                "project_type_id": "mathematical",
            },
        ],
    }
    calls: list[str] = []
    role_requests: list[str] = []
    selection: list[str] = []
    omitted_urls: list[str] = []

    async def provider(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        name = payload["text"]["format"]["name"]
        calls.append(name)
        if name == "research_reference_compilation":
            assert payload["store"] is False
            sources = json.loads(payload["input"])["uninspected_methodology_sources"]
            assert len(sources) >= 2
            selection[:] = [sources[0]["id"]]
            omitted_urls[:] = [source["url"] for source in sources[1:]]
            result = {
                "guidance": "Check the proposed recurrence against base cases and counterexamples.",
                "selected_source_ids": selection,
                "omitted_source_ids": [source["id"] for source in sources[1:]],
                "rationale": "Only the first methodological reference is relevant.",
            }
        elif name in {"research_investigator", "research_skeptic"}:
            body = json.dumps(payload)
            role_requests.append(body)
            result = (
                fixture.investigation(1)
                if name == "research_investigator"
                else fixture.skeptic(1, "stop", "no_progress")
            )
        else:
            raise AssertionError(f"Unexpected provider request: {name}")
        return httpx.Response(200, json=fixture.provider_response(result))

    with (
        patch.dict(os.environ, {"SIGMA_REFERENCE_COMPILATION_ENABLED": "true"}),
        patch.object(research_sessions, "auth_context", new=AsyncMock(return_value=credential)),
        patch.object(research_sessions, "configuration", new=AsyncMock(return_value=config)),
        patch.object(research_sessions, "select_method_sources", return_value=source_catalog),
        patch(
            "sigma.research_sessions.httpx.AsyncClient",
            side_effect=lambda **kwargs: fixture.REAL_CLIENT(
                transport=httpx.MockTransport(provider), **kwargs
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
        finished = await fixture.wait_for(path, started["id"])

    assert finished["status"] in {"ended", "completed"}, finished.get("message")
    assert calls == [
        "research_reference_compilation",
        "research_investigator",
        "research_skeptic",
    ], calls
    assert finished["calls_used"] == 2
    assert len(finished["steps"]) == 2
    assert [step["role"] for step in finished["steps"]] == ["investigator", "skeptic"]
    saved = research_sessions._read(str(path), started["id"])
    stage = saved["reference_compilation"]
    assert stage["status"] == "completed", stage
    assert stage["selected_source_ids"] == selection
    assert stage["omitted_source_ids"]
    assert stage["guidance_sha256"]
    assert stage["token_usage"]["input_tokens"] == 120
    assert stage["token_usage"]["output_tokens"] == 80
    assert saved["research_method_sources"]["sha256"] == stage["source_sha256"]
    assert len(saved["research_method_sources"]["sources"]) >= 2
    assert saved["outcome"]["source_material"]["compilation"]["guidance"] == stage["guidance"]
    assert len(role_requests) == 2
    for request in role_requests:
        assert stage["guidance"] in request
        assert all(url not in request for url in omitted_urls), omitted_urls
    assert (
        sum(1 for event in saved["events"] if event["kind"] == "references.compilation.completed")
        == 1
    )
    ledger = saved.get("hard_budget_ledger")
    if isinstance(ledger, dict):
        assert len(ledger["calls"]) == 3, ledger["calls"]
        assert all(item["status"] == "settled" for item in ledger["calls"])


async def main() -> None:
    with TemporaryDirectory() as temporary:
        await verify_compilation(Path(temporary) / "compiled.sigma")
    print("PASS: compiled reference guide persisted, metered and reused by both agents")


if __name__ == "__main__":
    asyncio.run(main())
