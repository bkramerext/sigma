"""Local browser adapter. Launch on 127.0.0.1; never bind to a public interface."""

import asyncio
import json
import os
from dataclasses import asdict
from uuid import UUID

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse, StreamingResponse
from pydantic import AliasChoices, BaseModel, ConfigDict, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

from sigma import chatgpt_auth
from sigma.agentic import agentic_events
from sigma.agentic_evidence import get_run, list_runs
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
from sigma.proposals import (
    accepted_provenance,
    cancel_request,
    configuration,
    generate_proposal,
    register_request,
    unregister_request,
)
from sigma.text_conversion import convert_text
from sigma.text_views import inspect_text, save_source

app = FastAPI(title="SIGMA", docs_url=None, redoc_url=None)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "testserver"])


@app.get("/api/ui-instance")
def ui_instance() -> dict[str, str | None]:
    """Readiness identity only; grants no control or access to configuration."""
    return {"instance": os.environ.get("SIGMA_UI_INSTANCE_ID")}


@app.middleware("http")
async def local_browser_only(request: Request, call_next):
    origin = request.headers.get("origin")
    if (
        request.url.path.startswith("/api/ai/")
        and request.method == "POST"
        and (
            origin not in {"http://127.0.0.1:5173", "http://localhost:5173"}
            or request.headers.get("content-type", "").split(";")[0] != "application/json"
        )
    ):
        return JSONResponse(
            {"error": "Account changes require the local SIGMA browser origin and JSON."},
            status_code=403,
        )
    if origin and origin not in {"http://127.0.0.1:5173", "http://localhost:5173"}:
        return JSONResponse({"error": "Untrusted browser origin"}, status_code=403)
    response = await call_next(request)
    if request.url.path.startswith("/api/ai/"):
        response.headers["Cache-Control"] = "no-store"
        response.headers["Referrer-Policy"] = "no-referrer"
    return response


@app.exception_handler(ProjectError)
async def project_error(request: Request, exc: ProjectError):
    return JSONResponse({"error": str(exc)}, status_code=400)


class OpenRequest(BaseModel):
    path: str


class InitRequest(OpenRequest):
    title: str
    problem: str
    investigation_type: str = Field(
        default="default", validation_alias=AliasChoices("investigation_type", "research_mode")
    )
    ai_model: str | None = None
    reasoning_effort: str = "high"


@app.post("/api/projects/open")
def open_view(body: OpenRequest):
    return asdict(open_project(body.path))


@app.post("/api/projects/init", status_code=201)
def init_view(body: InitRequest):
    view = initialize_project(
        body.path,
        body.title,
        body.problem,
        body.investigation_type,
        body.ai_model,
        body.reasoning_effort,
    )
    from sigma.recents import record_access

    record_access(view)
    return asdict(view)


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
    investigation_type: str = Field(
        default="default", validation_alias=AliasChoices("investigation_type", "research_mode")
    )
    ai_model: str | None = None
    reasoning_effort: str = "high"


@app.get("/api/projects/destination")
def destination_view(title: str = ""):
    return asdict(project_destination(title))


@app.post("/api/projects/create", status_code=201)
def create_project_view(body: CreateProjectRequest):
    return asdict(
        create_project(
            body.title, body.problem, body.investigation_type, body.ai_model, body.reasoning_effort
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
    expected_binding: str | None = None
    expected_project_id: str | None = None
    request_id: UUID | None = None


class ProposalCancelRequest(BaseModel):
    request_id: UUID


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

    task = asyncio.create_task(
        generate_proposal(
            body.path,
            body.seed,
            expected_binding=body.expected_binding,
            expected_project_id=body.expected_project_id,
        )
    )
    request_id = str(body.request_id) if body.request_id else None
    if request_id:
        try:
            register_request(request_id, task)
        except ProjectError:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            raise
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
        if request_id:
            unregister_request(request_id, task)


@app.post("/api/projects/proposals/cancel")
async def cancel_proposal(body: ProposalCancelRequest):
    await cancel_request(str(body.request_id))
    return {"cancelled": True}


@app.post("/api/projects/proposals/agentic")
async def agentic_proposal_view(body: ProposalRequest):
    async def stream():
        async for event in agentic_events(
            body.path, body.seed, body.expected_binding, body.expected_project_id
        ):
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )


@app.get("/api/projects/proposals/agentic/runs")
def agentic_runs_view(path: str, run_id: str | None = None):
    """List saved run metadata, or export one complete validated evidence record."""
    return get_run(path, run_id) if run_id else {"runs": list_runs(path)}


@app.get("/api/projects/text")
def text_view(path: str, scope: str, strategy_id: str | None = None):
    return inspect_text(path, scope, strategy_id)


class TextSourceRequest(OpenRequest):
    scope: str
    strategy_id: str | None = None
    body: str
    format: str
    expected_digest: str


@app.post("/api/projects/text/source")
def text_source_view(body: TextSourceRequest):
    return asdict(
        save_source(
            body.path, body.scope, body.body, body.format, body.expected_digest, body.strategy_id
        )
    )


class TextConversionRequest(OpenRequest):
    scope: str
    strategy_id: str | None = None
    target: str
    expected_digest: str
    expected_binding: str | None = None


@app.post("/api/projects/text/convert")
async def text_conversion_view(body: TextConversionRequest, request: Request):
    async def disconnected():
        while (await request.receive())["type"] != "http.disconnect":
            pass

    task = asyncio.create_task(
        convert_text(
            body.path,
            body.scope,
            body.target,
            body.strategy_id,
            body.expected_digest,
            body.expected_binding,
        )
    )
    connection = asyncio.create_task(disconnected())
    try:
        done, _ = await asyncio.wait({task, connection}, return_when=asyncio.FIRST_COMPLETED)
        if connection in done:
            return JSONResponse(
                {"error": "Conversion cancelled; source text was kept"}, status_code=499
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
    investigation_type: str = Field(
        validation_alias=AliasChoices("investigation_type", "research_mode")
    )
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
            body.investigation_type,
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


class AuthBeginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    account_id: str | None = None
    enable_plan: bool = False
    retry_attempt_id: str | None = None


class AuthModeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: str
    account_id: str | None = None


@app.post("/api/ai/auth/begin")
async def auth_begin(body: AuthBeginRequest):
    return await chatgpt_auth.begin(body.account_id, body.enable_plan, body.retry_attempt_id)


@app.get("/api/ai/auth/open/{identifier}")
async def auth_open(identifier: str):
    return RedirectResponse(
        chatgpt_auth.authorization_url(identifier),
        headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"},
    )


@app.get("/api/ai/auth/attempt/{identifier}")
async def auth_attempt(identifier: str):
    return chatgpt_auth.attempt_status(identifier)


@app.post("/api/ai/auth/cancel/{identifier}")
async def auth_cancel(identifier: str):
    chatgpt_auth.cancel(identifier)
    return {"cancelled": True}


@app.post("/api/ai/mode")
async def auth_mode(body: AuthModeRequest):
    await chatgpt_auth.select(body.mode, body.account_id)
    return await connection()


@app.post("/api/ai/disconnect")
async def auth_disconnect():
    return await chatgpt_auth.disconnect()


@app.post("/api/ai/welcome")
async def auth_welcome():
    await chatgpt_auth.welcome_seen()
    return {"dismissed": True}


@app.get("/api/projects/recent")
def recent_view():
    from sigma.recents import home_projects

    return home_projects()


@app.get("/api/projects/samples")
def samples_view():
    from sigma.samples import sample_projects

    return sample_projects()


class SampleOpenRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sample_id: str


@app.post("/api/projects/samples/open")
def sample_open_view(body: SampleOpenRequest):
    from sigma.samples import open_sample_project

    return asdict(open_sample_project(body.sample_id))


class ForgetRecentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_id: str


@app.post("/api/projects/recent/forget")
def forget_recent_view(body: ForgetRecentRequest):
    from sigma.recents import forget_recent

    forget_recent(body.project_id)
    return {"forgotten": True}
