"""Provider-free two-account fixture for real collaboration HTTP/browser acceptance.

Only the test server imports this module. Production API endpoints, authorization,
project storage and worker ownership remain unmodified.
"""

from __future__ import annotations

import asyncio

from fastapi import HTTPException

from sigma import papers, research_qa, research_sessions
from sigma.api import app

_started: list[str] = []
_release = asyncio.Event()


# In production, a real Session remains active while its process owns an OS
# worker lock. Mock Sessions have no worker; the original single-browser tests
# progress them on every read. Freeze only after admission so a two-browser
# acceptance can observe the same overlapping running/queued state.
_real_has_active_session = research_sessions.has_active_session


@app.post("/api/__fixture/collaboration-freeze-sessions")
def freeze_mock_sessions(body: dict[str, str]):
    path = body.get("path", "")
    if not isinstance(path, str) or not path:
        raise HTTPException(400, "Missing project path")
    records = research_sessions._all(path)
    if not any(row.get("simulated") and row.get("status") == "running" for row in records):
        raise HTTPException(409, "No simulated running Session to freeze")

    research_sessions._advance_mock = lambda record: record

    def simulated_liveness(candidate: str, *, project_id: str | None = None) -> bool:
        if candidate == path:
            return any(
                row.get("simulated") and row.get("status") in {"queued", "running"}
                for row in research_sessions._all(candidate)
            )
        return _real_has_active_session(candidate, project_id=project_id)

    research_sessions.has_active_session = simulated_liveness
    return {"frozen": True}


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
