"""Provider-free two-account fixture for real collaboration HTTP/browser acceptance.

Only the test server imports this module. Production API endpoints, authorization,
project storage and worker ownership remain unmodified.
"""

from __future__ import annotations

import asyncio
import os
from uuid import uuid4

from fastapi import HTTPException

from sigma import papers, project_collaboration, research_qa, research_sessions
from sigma.api import app, research_qa_answer, research_qa_delete
from sigma.projects import inspect_project

if os.environ.get("SIGMA_MOCK_AUTH") != "1":
    raise RuntimeError("Collaboration fixture cannot run outside local mock authentication")

_started: list[str] = []
_release = asyncio.Event()


# In production, a real Session remains active while its process owns an OS
# worker lock. Mock Sessions have no worker; the original single-browser tests
# progress them on every read. Freeze only after admission so a two-browser
# acceptance can observe the same overlapping running/queued state.
_real_has_active_session = research_sessions.has_active_session
_real_advance_mock = research_sessions._advance_mock


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


# The Paper fixture uses the real serialized Paper gate and durable run ledger.
# It never invokes model inference, scoring, publication, or PDF generation;
# full two-PDF verification belongs to #769.
_paper_holds: dict[str, tuple[str, asyncio.Event, asyncio.Task[None]]] = {}


async def held_paper(path: str, run_id: str, number: int, release: asyncio.Event) -> None:
    with papers.paper_run_scope(run_id, number=number):
        async with papers._paper_operation(path, generating=True):
            key = papers._paper_state_key(path)
            now = papers._now()
            papers._active_progress[key] = {
                "run_id": uuid4().hex,
                "status": "running",
                "stage": "writing",
                "current": 0,
                "total": 1,
                "started_at": now,
                "updated_at": now,
                "elapsed_seconds": 0,
                "model": "fixture-model",
                "reasoning_effort": "medium",
            }
            try:
                await release.wait()
            finally:
                papers._active_progress.pop(key, None)


@app.post("/api/__fixture/collaboration-paper-start")
async def start_held_paper(body: dict[str, str]):
    path = body.get("path", "")
    if not isinstance(path, str) or not path:
        raise HTTPException(400, "Missing project path")
    view = inspect_project(path)
    project_collaboration.register_owner(view)
    run_id = uuid4().hex
    receipt = project_collaboration.reserve_execution_run(
        path,
        "paper",
        run_id,
        papers.next_paper_number_for_activity(path) - 1,
        model="fixture-model",
        thinking="medium",
    )
    if receipt is None:
        raise HTTPException(409, "Paper admission unavailable")
    release = asyncio.Event()
    task = asyncio.create_task(held_paper(path, run_id, receipt["number"], release))
    _paper_holds[run_id] = (path, release, task)
    return {"run_id": run_id, "number": receipt["number"]}


@app.post("/api/__fixture/collaboration-paper-release")
async def release_held_paper(body: dict[str, str]):
    run_id = body.get("run_id", "")
    path = body.get("path", "")
    if not isinstance(run_id, str) or run_id not in _paper_holds:
        raise HTTPException(404, "Fixture Paper run unavailable")
    saved_path, release, task = _paper_holds[run_id]
    if path != saved_path:
        raise HTTPException(403, "Incorrect shared project")
    project_collaboration.execution_run(path, "paper", run_id, operator=True)
    release.set()
    await asyncio.wait_for(task, timeout=5)
    project_collaboration.discard_execution_run(path, "paper", run_id)
    _paper_holds.pop(run_id, None)
    return {"released": run_id}


@app.post("/api/__fixture/collaboration-unfreeze-sessions")
def unfreeze_mock_sessions():
    research_sessions._advance_mock = _real_advance_mock
    research_sessions.has_active_session = _real_has_active_session
    return {"frozen": False}


# Production mock auth deliberately denies inference endpoints. Test the real
# Q/A handler, including task idempotency and creator-scoped authorization,
# behind a fixture-only alias. This module cannot load outside mock auth, and
# its provider is replaced with deterministic, no-network inference.
app.add_api_route("/api/__fixture/collaboration-qa-ask", research_qa_answer, methods=["POST"])
app.add_api_route("/api/__fixture/collaboration-qa/{qa_id}", research_qa_delete, methods=["DELETE"])


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
