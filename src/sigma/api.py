"""Local browser adapter. Launch on 127.0.0.1; never bind to a public interface."""

import asyncio
from dataclasses import asdict

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict
from starlette.middleware.trustedhost import TrustedHostMiddleware

from sigma.openai_connection import connection, models
from sigma.projects import (
    ProjectError,
    change_stage,
    close_project,
    create_project,
    create_strategy,
    edit_strategy,
    initialize_project,
    inspect_project,
    list_events,
    list_strategies,
    open_project,
    project_destination,
    remove_strategy,
    reorder_strategies,
    update_project,
)
from sigma.proposals import accepted_provenance, configuration, generate_proposal

app = FastAPI(title="SIGMA", docs_url=None, redoc_url=None)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "testserver"])


@app.middleware("http")
async def local_browser_only(request: Request, call_next):
    origin = request.headers.get("origin")
    if origin and origin not in {"http://127.0.0.1:5173", "http://localhost:5173"}:
        return JSONResponse({"error": "Untrusted browser origin"}, status_code=403)
    return await call_next(request)


@app.exception_handler(ProjectError)
async def project_error(request: Request, exc: ProjectError):
    return JSONResponse({"error": str(exc)}, status_code=400)


class OpenRequest(BaseModel):
    path: str


class InitRequest(OpenRequest):
    title: str
    problem: str
    research_mode: str = "default"
    ai_model: str | None = None
    reasoning_effort: str = "high"


@app.post("/api/projects/open")
def open_view(body: OpenRequest):
    return asdict(open_project(body.path))


@app.post("/api/projects/init", status_code=201)
def init_view(body: InitRequest):
    return asdict(
        initialize_project(
            body.path,
            body.title,
            body.problem,
            body.research_mode,
            body.ai_model,
            body.reasoning_effort,
        )
    )


@app.get("/api/projects/inspect")
def inspect_view(path: str):
    return asdict(inspect_project(path))


@app.get("/api/projects/events")
def events_view(path: str):
    return {"events": [asdict(e) for e in list_events(path)]}


@app.post("/api/projects/close")
def close_view():
    close_project()
    return {"closed": True}


class StrategyRequest(OpenRequest):
    title: str
    approach: str


@app.get("/api/projects/strategies")
def strategies_view(path: str):
    return {"strategies": [asdict(s) for s in list_strategies(path)]}


class CreateStrategyRequest(StrategyRequest):
    summary: str = ""
    receipt: str | None = None


@app.post("/api/projects/strategies", status_code=201)
def create_strategy_view(body: CreateStrategyRequest):
    provenance = accepted_provenance(body.receipt, body.path) if body.receipt else None
    return asdict(create_strategy(body.path, body.title, body.approach, body.summary, provenance))


class RemoveStrategyRequest(OpenRequest):
    strategy_id: str


@app.post("/api/projects/strategies/remove")
def remove_strategy_view(body: RemoveStrategyRequest):
    return asdict(remove_strategy(body.path, body.strategy_id))


class EditStrategyRequest(StrategyRequest):
    strategy_id: str


@app.post("/api/projects/strategies/edit")
def edit_strategy_view(body: EditStrategyRequest):
    return asdict(edit_strategy(body.path, body.strategy_id, body.title, body.approach))


class CreateProjectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str
    problem: str
    research_mode: str = "default"
    ai_model: str | None = None
    reasoning_effort: str = "high"


@app.get("/api/projects/destination")
def destination_view(title: str = ""):
    return asdict(project_destination(title))


@app.post("/api/projects/create", status_code=201)
def create_project_view(body: CreateProjectRequest):
    return asdict(
        create_project(
            body.title, body.problem, body.research_mode, body.ai_model, body.reasoning_effort
        )
    )


class StageRequest(RemoveStrategyRequest):
    stage: str


class ReorderRequest(OpenRequest):
    order: list[str]
    expected_order: list[str]


@app.post("/api/projects/strategies/stage")
def stage_view(body: StageRequest):
    return asdict(change_stage(body.path, body.strategy_id, body.stage))


@app.post("/api/projects/strategies/reorder")
def reorder_view(body: ReorderRequest):
    return asdict(reorder_strategies(body.path, body.order, body.expected_order))


class ProposalRequest(OpenRequest):
    seed: str = ""
    consent: bool = False


@app.get("/api/projects/proposals/config")
async def proposal_config(path: str | None = None):
    return await configuration(path)


@app.post("/api/projects/proposals")
async def proposal_view(body: ProposalRequest, request: Request):
    async def disconnected():
        # Await the ASGI event directly. is_disconnected() polling can miss events
        # behind BaseHTTPMiddleware's receive channel.
        while (await request.receive())["type"] != "http.disconnect":
            pass

    task = asyncio.create_task(generate_proposal(body.path, body.seed, body.consent))
    connection = asyncio.create_task(disconnected())
    try:
        done, _ = await asyncio.wait({task, connection}, return_when=asyncio.FIRST_COMPLETED)
        if connection in done:
            return JSONResponse(
                {"error": "Proposal request cancelled; nothing saved"}, status_code=499
            )
        return await task
    finally:
        for pending in (task, connection):
            if not pending.done():
                pending.cancel()
        await asyncio.gather(task, connection, return_exceptions=True)


class ProjectSettingsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str
    problem: str
    research_mode: str
    ai_model: str
    reasoning_effort: str


class UpdateProjectRequest(ProjectSettingsRequest):
    path: str
    expected: ProjectSettingsRequest


@app.post("/api/projects/update")
def update_project_view(body: UpdateProjectRequest):
    return asdict(
        update_project(
            body.path,
            body.title,
            body.problem,
            body.research_mode,
            body.ai_model,
            body.reasoning_effort,
            body.expected.model_dump(),
        )
    )


@app.get("/api/ai/connection")
async def connection_view(refresh: bool = False):
    return await connection(refresh)


@app.get("/api/ai/models")
async def models_view(refresh: bool = False):
    return await models(refresh)
