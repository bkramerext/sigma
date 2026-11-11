"""Provider-free two-account fixture for real collaboration HTTP/browser acceptance.

Only the test server imports this module. Production API endpoints, authorization,
project storage and worker ownership remain unmodified.
"""

from __future__ import annotations

import asyncio

from fastapi import HTTPException

from sigma import papers, research_qa
from sigma.api import app

_started: list[str] = []
_release = asyncio.Event()


@app.get("/api/__fixture/collaboration-qa-state")
async def qa_state():
    return {"started": len(_started), "questions": list(_started), "released": _release.is_set()}


@app.post("/api/__fixture/collaboration-qa-release")
async def qa_release():
    _release.set()
    return {"released": True}


async def fixture_auth_context():
    return {
        "identity": "fixture:collaboration-qa",
        "mode": "api_key",
        "token": "non-networking-test-fixture",
        "status": "connected",
    }


async def fixture_configuration(**_kwargs):
    return {
        "available": True,
        "model": "gpt-6.1-sol",
        "reasoning_effort": "medium",
        "binding": "fixture:collaboration-qa",
    }


async def fixture_provider(input_value, _binding, config, *, schema_name, **_kwargs):
    if schema_name != "sigma_research_qa":
        raise HTTPException(500, "Unexpected provider invocation in collaboration fixture")
    question = input_value["question"]
    _started.append(question)
    # Both calls must overlap at a real provider boundary before the browser
    # releases them. No sleep, network request or paid inference is involved.
    await _release.wait()
    sources = input_value["sources"]
    refs = [source["id"] for source in sources if source.get("kind") in {"session", "artifact"}][:2]
    return research_qa.AnswerDraft(
        answer=f"Fixture answer for: {question}. Saved evidence remains provisional.",
        source_refs=refs,
    ), config["model"]


# Patch only the Q/A inference adapter, not the actual API/ACL/persistence code.
research_qa.auth_context = fixture_auth_context
research_qa.configuration = fixture_configuration
papers._provider_structured = fixture_provider
