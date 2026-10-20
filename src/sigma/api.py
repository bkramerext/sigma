"""Local browser adapter. Launch on 127.0.0.1; never bind to a public interface."""

from dataclasses import asdict

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.middleware.trustedhost import TrustedHostMiddleware

from sigma.projects import (
    ProjectError,
    close_project,
    create_strategy,
    edit_strategy,
    initialize_project,
    inspect_project,
    list_events,
    list_strategies,
    open_project,
    remove_strategy,
)

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


@app.post("/api/projects/open")
def open_view(body: OpenRequest):
    return asdict(open_project(body.path))


@app.post("/api/projects/init", status_code=201)
def init_view(body: InitRequest):
    return asdict(initialize_project(body.path, body.title, body.problem))


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


@app.post("/api/projects/strategies", status_code=201)
def create_strategy_view(body: StrategyRequest):
    return asdict(create_strategy(body.path, body.title, body.approach))


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
