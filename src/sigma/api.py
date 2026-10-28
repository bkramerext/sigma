"""Local browser adapter. Launch on 127.0.0.1; never bind to a public interface."""

import asyncio
import json
import os
import re
import secrets
import sqlite3
from collections.abc import AsyncIterator
from dataclasses import asdict
from typing import Any, Literal
from urllib.parse import quote
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response, StreamingResponse
from pydantic import AliasChoices, BaseModel, ConfigDict, Field, SecretStr
from starlette.concurrency import run_in_threadpool
from starlette.middleware.trustedhost import TrustedHostMiddleware

from sigma import (
    chatgpt_auth,
    cloud_auth,
    cloud_demo,
    cloud_research,
    cloud_workspaces,
    papers,
    python_sandbox,
    research_sessions,
)
from sigma.agentic import agentic_events
from sigma.agentic_evidence import get_run, list_runs
from sigma.continuations import approved_packets
from sigma.openai_connection import auth_context, connection, models, sponsored_auth_context
from sigma.projects import (
    ProjectError,
    WorkspaceAccessError,
    _document,
    change_stage,
    close_project,
    copy_project_between_workspaces,
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
    set_strategy_enabled,
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
from sigma.research_tools import execution_capabilities
from sigma.text_conversion import convert_text
from sigma.text_views import inspect_text, save_source


async def cloud_workspace_scope(request: Request) -> AsyncIterator[None]:
    """Bind each protected cloud request to its verified subject's durable root."""
    guest_workspace = getattr(request.state, "cloud_guest_workspace", None)
    if isinstance(guest_workspace, cloud_workspaces.Workspace):
        token = cloud_workspaces.bind_workspace(guest_workspace)
        try:
            yield
        finally:
            cloud_workspaces.reset(token)
        return
    if (
        not cloud_workspaces.enabled()
        or request.url.path == "/api/ui-instance"
        or request.url.path == "/api/projects/samples"
        or request.url.path.startswith("/api/cloud-auth/")
    ):
        yield
        return
    principal = getattr(request.state, "cloud_principal", None)
    if not isinstance(principal, cloud_auth.Principal):
        raise HTTPException(status_code=401, detail="Authentication required.")
    try:
        token = cloud_workspaces.bind(principal)
    except cloud_workspaces.WorkspaceUnavailable as exc:
        raise HTTPException(status_code=503, detail="Private workspace is unavailable.") from exc
    try:
        yield
    finally:
        cloud_workspaces.reset(token)


app = FastAPI(title="SIGMA", docs_url=None, redoc_url=None)
# Installed before routes, so FastAPI applies this dependency after the auth
# middleware has attached its verified principal. Cloud-auth's own public and
# admin endpoints do not access workspace data.
app.router.dependencies.append(Depends(cloud_workspace_scope))
_cloud_config = cloud_auth.config()
_trusted_hosts = ["127.0.0.1", "localhost", "testserver"]
if _cloud_config.origin:
    from urllib.parse import urlsplit

    _trusted_hosts.append(urlsplit(_cloud_config.origin).hostname or "")
app.add_middleware(TrustedHostMiddleware, allowed_hosts=_trusted_hosts)

# Keep public Demo endpoints outside the app-wide private-workspace dependency.
# The parent app's cloud-auth middleware still gates this mount to these two
# exact GET routes; the mounted app has no write operations or caller paths.
demo_app = FastAPI(title="SIGMA public Demo", docs_url=None, redoc_url=None)
app.mount("/api/cloud-demo", demo_app)


async def require_cloud_inference_binding(
    expected_binding: str | None,
    expected_project_id: str | None,
    path: str,
    *,
    require_project: bool = True,
) -> None:
    """Require explicit project/account intent before admitting sponsored inference."""
    if not cloud_workspaces.enabled():
        return
    view = inspect_project(path)
    if expected_project_id is not None and expected_project_id != view.project.id:
        raise HTTPException(404, "Project not found or access denied.")
    credential = await auth_context()
    if expected_binding != credential["identity"] or (require_project and not expected_project_id):
        raise HTTPException(
            403, "Cloud inference requires the current sponsored account and project binding."
        )
    from sigma.openai_connection import cloud_credential

    if not cloud_credential(credential):
        raise HTTPException(503, "Sponsored cloud inference is not configured.")


@demo_app.get("/")
def cloud_demo_view():
    """Return the one server-configured public audit snapshot, never a caller path."""
    if not cloud_auth.config().enabled:
        raise HTTPException(404, "Hosted Demo is unavailable.")
    try:
        return JSONResponse(
            cloud_demo.audit(),
            headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
        )
    except ProjectError as exc:
        raise HTTPException(503, "Hosted Demo is not available.") from exc


@demo_app.get("/report")
def cloud_demo_report_view(format: str = "txt"):
    if not cloud_auth.config().enabled:
        raise HTTPException(404, "Hosted Demo is unavailable.")
    try:
        body, media_type = cloud_demo.report(format)
    except ProjectError as exc:
        raise HTTPException(503, "Hosted Demo is not available.") from exc
    return Response(body, media_type=media_type, headers={"Cache-Control": "no-store"})


@app.get("/api/ui-instance")
def ui_instance() -> dict[str, str | None]:
    """Readiness identity only; grants no control or access to configuration."""
    return {"instance": os.environ.get("SIGMA_UI_INSTANCE_ID")}


@app.get("/api/cloud-research/budget")
def cloud_research_budget():
    """Return only the authenticated workspace's persisted inference budget."""
    if not cloud_research.billing_enabled():
        raise HTTPException(404, "Cloud research budget is unavailable.")
    try:
        return JSONResponse(
            cloud_research.snapshot(),
            headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
        )
    except cloud_research.CloudResearchUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc


@app.get("/api/cloud-research/connection")
async def cloud_sponsored_connection(request: Request):
    """Check only the server-held sponsored credential's model-catalog access."""
    if not cloud_workspaces.enabled() or not cloud_auth.sponsored_access_enabled():
        raise HTTPException(404, "Sponsored cloud connection is unavailable.")
    principal = getattr(request.state, "cloud_principal", None)
    if not isinstance(principal, cloud_auth.Principal):
        raise HTTPException(401, "Authentication required.")
    sponsor_context = await sponsored_auth_context()
    state = await connection(refresh=True, context=sponsor_context)
    try:
        if cloud_auth.model_access_for_subject(principal.subject) == "sponsored":
            cloud_auth.persist_model_connection_status(principal.subject, str(state.get("status")))
    except (sqlite3.Error, OSError, RuntimeError) as exc:
        raise HTTPException(503, "Account connection state could not be saved.") from exc
    return JSONResponse(
        {
            "mode": "sponsored",
            "status": state.get("status", "unavailable"),
            "label": state.get("label", "Sponsored model access unavailable"),
            "guidance": state.get("guidance", "Retry the connection check."),
            "checked_at": state.get("checked_at"),
        },
        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
    )


@app.middleware("http")
async def local_browser_only(request: Request, call_next):
    origin = request.headers.get("origin")
    allowed_origins = {"http://127.0.0.1:5173", "http://localhost:5173"}
    cfg = cloud_auth.config()
    if cfg.origin:
        allowed_origins.add(cfg.origin)
    if (
        request.url.path.startswith("/api/ai/")
        and request.method == "POST"
        and (
            origin not in allowed_origins
            or request.headers.get("content-type", "").split(";")[0] != "application/json"
        )
    ):
        return JSONResponse(
            {"error": "Account changes require the local SIGMA browser origin and JSON."},
            status_code=403,
        )
    if origin and origin not in allowed_origins:
        return JSONResponse({"error": "Untrusted browser origin"}, status_code=403)
    response = await cloud_auth.middleware(request, call_next)
    sponsored_start = request.url.path == "/api/projects/research-sessions/start"
    if (
        cfg.local
        and request.url.path.startswith("/api/projects/")
        and (response.status_code >= 400 or sponsored_start)
    ):
        principal = getattr(request.state, "cloud_principal", None)
        if isinstance(principal, cloud_auth.Principal):
            try:
                if cloud_auth.model_access_for_subject(principal.subject) == "sponsored":
                    from sigma.sponsor_diagnostics import record

                    content_length = response.headers.get("content-length", "")
                    large_body = content_length.isdigit() and int(content_length) > 600
                    if sponsored_start:
                        route = "sponsor_play"
                    elif request.url.path.startswith("/api/projects/research-sessions"):
                        route = "sponsor_sessions_api"
                    elif request.url.path.endswith("/api/projects/proposals/config"):
                        route = "sponsor_config_api"
                    elif request.url.path.endswith("/api/projects/research-limits"):
                        route = "sponsor_limits_api"
                    else:
                        route = "sponsor_project_api"
                    outcome = (
                        "accepted"
                        if sponsored_start and response.status_code < 400
                        else f"{request.method.lower()}_{response.status_code}"
                    )
                    if large_body and response.status_code >= 400:
                        outcome += "_large"
                    record(route, outcome)
            except (OSError, RuntimeError, sqlite3.Error, ValueError, ImportError):
                # Diagnostics never alter or delay the API response.
                pass
    if request.url.path.startswith("/api/ai/"):
        response.headers["Cache-Control"] = "no-store"
        response.headers["Referrer-Policy"] = "no-referrer"
    return response


@app.exception_handler(ProjectError)
async def project_error(request: Request, exc: ProjectError):
    return JSONResponse({"error": str(exc)}, status_code=400)


@app.exception_handler(WorkspaceAccessError)
async def workspace_access_error(request: Request, exc: WorkspaceAccessError):
    return JSONResponse({"error": "Project not found or access denied."}, status_code=404)


class OpenRequest(BaseModel):
    path: str


class GuestProjectCopyRequest(BaseModel):
    path: str = Field(min_length=1, max_length=4096)


@app.post("/api/projects/guest-copy", status_code=201)
def copy_project_to_guest_workspace(body: GuestProjectCopyRequest):
    """Copy the current project into a private, temporary guest workspace."""
    source = cloud_workspaces.current()
    cfg = cloud_auth.config()
    if (source is None and not cfg.local) or (source is not None and source.guest):
        raise HTTPException(401, "Sign in to copy this project to a guest workspace.")
    guest_token = secrets.token_hex(32)
    target = cloud_workspaces.guest_workspace(guest_token, create=True)
    if target is None:
        raise HTTPException(503, "A temporary guest workspace is unavailable.")
    try:
        copied_path = copy_project_between_workspaces(body.path, source, target)
    except ProjectError as exc:
        raise HTTPException(400, str(exc)) from exc
    response = JSONResponse({"path": copied_path}, status_code=201)
    response.set_cookie(
        cloud_auth._cookie_name(cloud_auth.GUEST_COOKIE, cfg),
        guest_token,
        **cloud_auth._cookie_options(
            cfg, cloud_auth.GUEST_COOKIE, max_age=cloud_auth.SESSION_SECONDS
        ),
    )
    return response


class ResearchStartRequest(OpenRequest):
    strategy_id: str = Field(min_length=1, max_length=100)
    strategy_ids: list[str] | None = Field(default=None, min_length=1, max_length=12)
    idempotency_key: str = Field(min_length=36, max_length=36)
    expected_project_id: str = Field(min_length=1, max_length=100)
    expected_binding: str = Field(min_length=1, max_length=512)
    expected_limits: dict[str, Any] | None = None


class ResearchControlRequest(OpenRequest):
    action: str = Field(min_length=4, max_length=6)


class ResearchInterventionRequest(OpenRequest):
    model_config = ConfigDict(extra="forbid", strict=True)
    kind: Literal["objection", "evidence", "priority"]
    text: str = Field(min_length=1, max_length=1200)
    strategy_ids: list[str] | None = Field(default=None, min_length=1, max_length=12)
    agent_roles: list[Literal["investigator", "skeptic"]] = Field(
        default_factory=lambda: ["investigator", "skeptic"], min_length=1, max_length=2
    )
    supersedes_intervention_id: str | None = Field(default=None, max_length=36)


class ResearchSessionRemoveRequest(OpenRequest):
    expected_updated_at: str = Field(min_length=1, max_length=64)


class ResearchExecutionRequest(OpenRequest):
    runtime: Literal["python", "sagemath"] = "python"
    step_id: str | None = Field(default=None, max_length=36)
    model_config = ConfigDict(extra="forbid", strict=True)
    source: str = Field(min_length=1, max_length=16_000)
    session_id: str | None = Field(default=None, max_length=36)
    strategy_id: str | None = Field(default=None, max_length=36)
    cycle: int | None = Field(default=None, ge=1)


class ResearchLimitsRequest(OpenRequest):
    model_config = ConfigDict(extra="forbid", strict=True)
    research_rounds: int = Field(ge=1, le=5)
    model_calls: int = Field(ge=2, le=120)
    session_duration_minutes: int = Field(ge=1, le=research_sessions.MAX_SESSION_DURATION_MINUTES)
    output_tokens_per_call: int = Field(ge=256, le=20000)
    maximum_estimated_cost_usd: float | None = Field(default=None, ge=0.01, le=100)
    maximum_input_tokens_per_session: int | None = Field(default=None, ge=4096, le=1_000_000)
    max_concurrent_sessions: int | str = "1"


class PaperGenerateRequest(OpenRequest):
    expected_project_id: str = Field(min_length=1, max_length=100)
    expected_binding: str = Field(min_length=1, max_length=512)
    expected_snapshot_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    long_form: bool = False


class PaperRestartRequest(OpenRequest):
    expected_project_id: str = Field(min_length=1, max_length=100)
    expected_binding: str = Field(min_length=1, max_length=512)
    expected_snapshot_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    confirm_restart: Literal[True]
    long_form: bool = False


@app.get("/api/projects/papers")
def papers_view(path: str):
    return {"papers": papers.list_papers(path)}


@app.get("/api/projects/papers/preflight")
def papers_preflight_view(
    path: str,
    long_form: bool = False,
    expected_project_id: str | None = None,
    expected_binding: str | None = None,
    mode: str | None = None,
    model: str | None = None,
    reasoning_effort: str | None = None,
):
    return papers.preflight(
        path,
        force_long_form=long_form,
        expected_project_id=expected_project_id,
        expected_binding=expected_binding,
        mode=mode,
        model=model,
        reasoning_effort=reasoning_effort,
    )


@app.post("/api/projects/papers/restart")
async def papers_restart_view(body: PaperRestartRequest):
    return await papers.restart_work(
        body.path,
        body.expected_project_id,
        body.expected_binding,
        body.expected_snapshot_sha256,
        body.confirm_restart,
        body.long_form,
    )


@app.get("/api/projects/papers/{paper_id}")
def paper_view(paper_id: str, path: str):
    return papers.get_paper(path, paper_id)


@app.get("/api/projects/papers/{paper_id}/pdf")
def paper_pdf_view(paper_id: str, path: str, open_in_browser: bool = False):
    disposition = "inline" if open_in_browser else "attachment"
    return Response(
        papers.get_pdf(path, paper_id),
        media_type="application/pdf",
        headers={
            "Cache-Control": "no-store",
            "Content-Disposition": f'{disposition}; filename="sigma-ai-paper-{paper_id}.pdf"',
        },
    )


@app.get("/api/projects/papers/{paper_id}/txt")
def paper_txt_view(paper_id: str, path: str):
    return Response(
        papers.paper_text(path, paper_id),
        media_type="text/plain; charset=utf-8",
        headers={
            "Cache-Control": "no-store",
            "Content-Disposition": f'attachment; filename="sigma-ai-paper-{paper_id}.txt"',
        },
    )


@app.get("/api/projects/papers/{paper_id}/tex")
def paper_tex_view(paper_id: str, path: str):
    return Response(
        papers.paper_tex(path, paper_id),
        media_type="application/x-tex; charset=utf-8",
        headers={
            "Cache-Control": "no-store",
            "Content-Disposition": f'attachment; filename="sigma-ai-paper-{paper_id}.tex"',
        },
    )


@app.delete("/api/projects/papers/{paper_id}")
def paper_delete_view(paper_id: str, path: str):
    papers.delete_paper(path, paper_id)
    return {"deleted": paper_id}


@app.post("/api/projects/papers")
async def paper_generate_view(body: PaperGenerateRequest, request: Request):
    await require_cloud_inference_binding(
        body.expected_binding, body.expected_project_id, body.path
    )

    async def stream():
        updates: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

        async def progress(stage: str, completed: int, total: int) -> None:
            await updates.put(
                {"type": "progress", "stage": stage, "completed": completed, "total": total}
            )

        task = asyncio.create_task(
            papers.generate(
                body.path,
                body.expected_binding,
                body.expected_project_id,
                progress=progress,
                force_long_form=body.long_form,
                expected_snapshot_sha256=body.expected_snapshot_sha256,
            )
        )
        try:
            while not task.done():
                try:
                    update = await asyncio.wait_for(updates.get(), timeout=1)
                except TimeoutError:
                    yield ": paper generation is active\n\n"
                    continue
                yield "data: " + json.dumps(update, separators=(",", ":")) + "\n\n"
            result = await task
            yield "data: " + json.dumps({"type": "complete", "result": result}) + "\n\n"
        except ProjectError as exc:
            event: dict[str, str | int] = {"type": "error", "error": str(exc)}
            provider_calls_attempted = getattr(exc, "provider_calls_attempted", None)
            if type(provider_calls_attempted) is int:
                event["provider_calls_attempted"] = provider_calls_attempted
            yield "data: " + json.dumps(event) + "\n\n"
        finally:
            if not task.done():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )


@app.get("/api/projects/research-limits")
def research_limits_view(path: str):
    limits = research_sessions.get_limits(path)
    return {**limits, "max_concurrent_sessions": str(limits["max_concurrent_sessions"])}


@app.put("/api/projects/research-limits")
def research_limits_update(body: ResearchLimitsRequest):
    limits = research_sessions.save_limits(
        body.path,
        {
            "research_rounds": body.research_rounds,
            "model_calls": body.model_calls,
            "session_duration_minutes": body.session_duration_minutes,
            "output_tokens_per_call": body.output_tokens_per_call,
            "maximum_estimated_cost_usd": body.maximum_estimated_cost_usd,
            "maximum_input_tokens_per_session": body.maximum_input_tokens_per_session,
            "max_concurrent_sessions": body.max_concurrent_sessions,
        },
    )
    return {**limits, "max_concurrent_sessions": str(limits["max_concurrent_sessions"])}


@app.get("/api/projects/current-understanding")
def current_understanding_view(path: str):
    from sigma.research_state import current_understanding

    return current_understanding(path)


@app.get("/api/projects/research-sessions")
async def research_sessions_view(path: str):
    await research_sessions.ensure_queued_workers(path)
    from sigma.research_state import build_current_understanding

    sessions = research_sessions.list_sessions(path)
    project = inspect_project(path).project
    return {
        "sessions": sessions,
        "current_understanding": build_current_understanding(project.id, sessions),
    }


@app.get("/api/projects/research-sessions/{session_id}")
async def research_session_view(session_id: str, path: str):
    await research_sessions.ensure_queued_workers(path)
    return research_sessions.get_session(path, session_id)


class MockResearchStartRequest(OpenRequest):
    strategy_id: str
    idempotency_key: str
    expected_project_id: str


@app.post("/api/projects/research-sessions/mock")
def mock_research_start_view(
    body: MockResearchStartRequest, request: Request, scenario: str = "completed"
):
    cfg = cloud_auth.config()
    principal = getattr(request.state, "cloud_principal", None)
    if (
        not cloud_auth._mock_enabled(cfg)
        or not isinstance(principal, cloud_auth.Principal)
        or not principal.subject.startswith("mock:")
    ):
        raise HTTPException(404, "Not found")
    account = cloud_auth._persist_user_state(cfg, principal)
    allowance = cloud_auth._mock_allowance(cfg, principal.subject)
    provider = cloud_auth._mock_provider(cfg, principal.subject)
    if account["model_access"]["mode"] == "sponsored" and allowance["scenario"] == "exhausted":
        scenario = "exhausted"
    elif provider in {"unavailable", "error"}:
        scenario = "provider-error"
    if inspect_project(body.path).project.id != body.expected_project_id:
        raise HTTPException(409, "Project changed; reopen it before starting research")
    return research_sessions.mock_session(
        body.path, body.strategy_id, body.idempotency_key, scenario
    )


@app.post("/api/projects/research-sessions/start")
async def research_start_view(body: ResearchStartRequest):
    return await research_sessions.start_session(
        body.path,
        body.strategy_id,
        body.idempotency_key,
        body.expected_project_id,
        body.expected_binding,
        body.expected_limits,
        body.strategy_ids,
    )


@app.post("/api/projects/research-sessions/{session_id}/control")
async def research_control_view(session_id: str, body: ResearchControlRequest, request: Request):
    cfg = cloud_auth.config()
    principal = getattr(request.state, "cloud_principal", None)
    if (
        cloud_auth._mock_enabled(cfg)
        and isinstance(principal, cloud_auth.Principal)
        and principal.subject.startswith("mock:")
    ):
        simulated = await run_in_threadpool(
            research_sessions.control_mock_session, body.path, session_id, body.action
        )
        if simulated is None:
            raise HTTPException(404, "Not found")
        return simulated
    return await research_sessions.control_session(body.path, session_id, body.action)


@app.post("/api/projects/research-sessions/{session_id}/interventions")
async def research_intervention_view(session_id: str, body: ResearchInterventionRequest):
    return await research_sessions.submit_intervention(
        body.path,
        session_id,
        body.kind,
        body.text,
        body.strategy_ids,
        body.agent_roles,
        body.supersedes_intervention_id,
    )


@app.delete("/api/projects/research-sessions/{session_id}")
def research_session_remove_view(session_id: str, body: ResearchSessionRemoveRequest):
    return research_sessions.remove_session(body.path, session_id, body.expected_updated_at)


@app.get("/api/research-tools")
async def research_tools_view():
    import asyncio

    return {"execution_tools": await asyncio.to_thread(execution_capabilities)}


@app.get("/api/projects/research-executions")
def research_executions_view(path: str):
    return {"executions": python_sandbox.list_executions(path)}


@app.get("/api/projects/research-executions/{execution_id}")
def research_execution_view(execution_id: str, path: str):
    return python_sandbox.get_execution(path, execution_id)


@app.get("/api/projects/research-executions/{execution_id}/artifacts/{filename}")
def research_execution_artifact_view(execution_id: str, filename: str, path: str):
    content, media_type = python_sandbox.get_execution_artifact(path, execution_id, filename)
    return Response(
        content,
        media_type=media_type,
        headers={
            "Cache-Control": "no-store",
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename, safe='')}",
            "X-Content-Type-Options": "nosniff",
        },
    )


@app.post("/api/projects/research-executions", status_code=201)
async def research_execution_start_view(body: ResearchExecutionRequest):
    return await python_sandbox.execute_research_code(
        body.path,
        body.source,
        session_id=body.session_id,
        strategy_id=body.strategy_id,
        cycle=body.cycle,
        runtime_name=body.runtime,
        step_id=body.step_id,
    )


class InitRequest(OpenRequest):
    title: str
    problem: str
    investigation_type: str = Field(
        default="default", validation_alias=AliasChoices("investigation_type", "research_mode")
    )
    ai_model: str | None = None
    reasoning_effort: str = "high"
    difficulty: str = "medium"


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
        body.difficulty,
    )
    from sigma.recents import record_access

    record_access(view)
    return asdict(view)


@app.get("/api/projects/inspect")
def inspect_view(path: str):
    return asdict(inspect_project(path))


@app.get("/api/projects/audit")
def export_project_view(path: str):
    """Return the structured audit view used by reports and review tooling."""
    project = json.loads(_document(inspect_project(path).project))
    runs = [get_run(path, item["run_id"]) for item in reversed(list_runs(path))]
    sessions = list(reversed(research_sessions.list_sessions(path)))
    continuations = list(approved_packets(path, validate_dispatch=False).values())
    return {
        "export_version": 2,
        "project": project,
        "agentic_runs": runs,
        "research_sessions": sessions,
        **({"continuations": continuations} if continuations else {}),
    }


@app.get("/api/projects/export")
@app.get("/api/projects/download")
def download_project_bundle(path: str):
    """Export every project file as one complete, importable JSON bundle."""
    from sigma.project_bundle import download_bytes, encode
    from sigma.projects import project_path

    authorized = project_path(path)
    inspect_project(authorized)
    # Legacy directory projects remain exportable without modifying live storage.
    # A lossless bundle snapshot has the same importable format as a JSON project.
    if authorized.suffix == ".json":
        content = download_bytes(authorized)
    elif authorized.suffix == ".sigma" and authorized.is_dir():
        content = encode(authorized)
    else:
        raise ProjectError("Unsupported project storage format")
    return Response(
        content=content,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{authorized.name}"'},
    )


class ImportBundleRequest(BaseModel):
    bundle: dict[str, Any]


@app.post("/api/projects/import", status_code=201)
def import_project_bundle(body: ImportBundleRequest):
    """Import into the authenticated workspace without replacing existing work."""
    from sigma.project_bundle import (
        BundleError,
        bundle_project_document,
        import_bundle,
        rename_bundle_project,
    )
    from sigma.projects import (
        _occupied_titles,
        _project_name,
        _title_key,
        _title_registry_lock,
        projects_root,
    )

    try:
        document = bundle_project_document(body.bundle)
        title = document["title"]
        if not isinstance(document.get("id"), str):
            raise ProjectError("Imported project identity is invalid")
        root = projects_root()
        with _title_registry_lock(root):
            occupied_titles = _occupied_titles(root)
            imported = None
            version_match = re.search(r"(?i)\bv(\d+)$", title)
            for number in range(1, 1001):
                if number == 1:
                    candidate = title
                elif version_match:
                    version_number = int(version_match.group(1)) + number - 1
                    candidate = title[: version_match.start()] + f"v{version_number}"
                else:
                    suffix = " (imported)" if number == 2 else f" (imported {number - 1})"
                    candidate = title[: 200 - len(suffix)].rstrip() + suffix
                _, name = _project_name(candidate)
                destination = (root / name).with_suffix(".json")
                if (
                    _title_key(candidate) in occupied_titles
                    or os.path.lexists(destination)
                    or os.path.lexists(root / name)
                ):
                    continue
                payload = (
                    body.bundle
                    if candidate == title
                    else rename_bundle_project(body.bundle, candidate)
                )
                imported = import_bundle(payload, destination)
                break
            if imported is None:
                raise ProjectError("A unique name for the imported project is unavailable.")
        view = inspect_project(imported)
        from sigma.recents import record_access

        record_access(view)
        return asdict(view)
    except (KeyError, TypeError, ValueError, UnicodeDecodeError, BundleError) as exc:
        raise ProjectError(f"Cannot import project bundle: {exc}") from exc


@app.get("/api/projects/export/report")
def export_project_report_view(path: str, format: str = "txt"):
    """Create a deterministic, escaped report from the same evidence as the JSON audit."""
    from sigma.project_reports import render_report

    data = export_project_view(path)
    try:
        body, media_type = render_report(data, format)
    except ValueError as exc:
        raise ProjectError(str(exc)) from exc
    except RuntimeError as exc:
        raise ProjectError(str(exc)) from exc
    return Response(body, media_type=media_type, headers={"Cache-Control": "no-store"})


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


class StrategyEnabledRequest(OpenRequest):
    model_config = ConfigDict(extra="forbid", strict=True)
    strategy_id: str
    enabled: bool


@app.post("/api/projects/strategies/enabled")
def strategy_enabled_view(body: StrategyEnabledRequest):
    return asdict(set_strategy_enabled(body.path, body.strategy_id, body.enabled))


class CreateProjectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str
    problem: str
    investigation_type: str = Field(
        default="default", validation_alias=AliasChoices("investigation_type", "research_mode")
    )
    ai_model: str | None = None
    reasoning_effort: str = "high"
    difficulty: str = "medium"
    show_advanced_outcome_details: bool = False


@app.get("/api/projects/destination")
def destination_view(title: str = ""):
    return asdict(project_destination(title))


@app.post("/api/projects/create", status_code=201)
def create_project_view(body: CreateProjectRequest):
    return asdict(
        create_project(
            body.title,
            body.problem,
            body.investigation_type,
            body.ai_model,
            body.reasoning_effort,
            body.difficulty,
            body.show_advanced_outcome_details,
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


@app.post("/api/projects/strategy-suggestions")
async def strategy_suggestion_view(body: ProposalRequest):
    await require_cloud_inference_binding(
        body.expected_binding, body.expected_project_id, body.path
    )
    return await generate_proposal(
        body.path,
        expected_binding=body.expected_binding,
        expected_project_id=body.expected_project_id,
        suggestion_only=True,
    )


class ProposalCancelRequest(BaseModel):
    request_id: UUID


@app.get("/api/projects/proposals/config")
async def proposal_config(path: str | None = None):
    return await configuration(path)


@app.post("/api/projects/proposals")
async def proposal_view(body: ProposalRequest, request: Request):
    await require_cloud_inference_binding(
        body.expected_binding, body.expected_project_id, body.path
    )

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
        try:
            return await task
        except asyncio.CancelledError:
            return JSONResponse(
                {"error": "Proposal request cancelled; nothing saved"}, status_code=499
            )
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
    await require_cloud_inference_binding(
        body.expected_binding, body.expected_project_id, body.path
    )

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
    session_id: str | None = Field(default=None, max_length=36)
    target: str
    expected_digest: str
    expected_binding: str | None = None
    expected_project_id: str | None = None


@app.post("/api/projects/text/convert")
async def text_conversion_view(body: TextConversionRequest, request: Request):
    await require_cloud_inference_binding(
        body.expected_binding, body.expected_project_id, body.path, require_project=False
    )

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
            body.expected_project_id,
            body.session_id,
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
    difficulty: str | None
    show_advanced_outcome_details: bool | None = None


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
            body.expected.model_dump(exclude_none=True),
            difficulty=body.difficulty,
            show_advanced_outcome_details=body.show_advanced_outcome_details,
        )
    )


@app.get("/api/ai/connection")
async def connection_view(request: Request, refresh: bool = False):
    state = await connection(refresh)
    cfg = cloud_auth.config()
    principal = getattr(request.state, "cloud_principal", None)
    if cfg.enabled and cfg.local and isinstance(principal, cloud_auth.Principal):
        try:
            cloud_auth.persist_model_connection_status(principal.subject, str(state.get("status")))
        except (sqlite3.Error, OSError, RuntimeError) as exc:
            raise HTTPException(503, "Account connection state could not be saved.") from exc
    return state


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


class ApiKeyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    api_key: SecretStr


@app.post("/api/ai/auth/begin")
async def auth_begin(body: AuthBeginRequest):
    if cloud_auth.config().local and body.account_id is not None:
        from sigma.ai_store import sponsor_transaction
        from sigma.cloud_sponsor import expected_email

        async with sponsor_transaction() as state:
            account = state["accounts"].get(body.account_id) or {}
            if account.get("email", "").casefold() == expected_email():
                raise HTTPException(403, "Use Admin Settings to renew the sponsor account.")
    return await chatgpt_auth.begin(body.account_id, body.enable_plan, body.retry_attempt_id)


@app.post("/api/ai/sponsor-auth/begin")
async def sponsor_auth_begin(request: Request):
    """Let admins or eligible local members renew only the designated sponsor."""
    cfg = cloud_auth.config()
    principal = getattr(request.state, "cloud_principal", None)
    if (
        not cfg.local
        or not isinstance(principal, cloud_auth.Principal)
        or principal.subject.startswith("mock:")
    ):
        raise HTTPException(403, "An authenticated local account is required to renew sponsorship.")
    if principal.role != "admin":
        try:
            account = cloud_auth._persist_user_state(cfg, principal)
        except (OSError, RuntimeError, sqlite3.Error):
            raise HTTPException(
                503, "Sponsored account eligibility could not be checked."
            ) from None
        if (
            principal.role != "member"
            or not cloud_auth.sponsored_access_enabled()
            or not account["sponsorship"]["eligible"]
        ):
            raise HTTPException(403, "Eligible sponsored access is required to renew sponsorship.")
    from sigma.cloud_sponsor import sponsor_account_id

    try:
        account_id = await sponsor_account_id()
        return await chatgpt_auth.begin(account_id=account_id, sponsor=True)
    except ProjectError as exc:
        from sigma.sponsor_diagnostics import record

        record("sponsor_oauth", "begin_failed")
        raise HTTPException(503, str(exc)) from exc


@app.post("/api/ai/api-key")
async def auth_api_key(body: ApiKeyRequest):
    cfg = cloud_auth.config()
    if cfg.enabled and not cfg.local:
        raise HTTPException(403, "Personal API-key configuration is unavailable in hosted SIGMA.")
    try:
        await chatgpt_auth.save_api_key(body.api_key.get_secret_value())
    except ProjectError as exc:
        raise HTTPException(422, str(exc)) from exc
    return JSONResponse({"saved": True}, headers={"Cache-Control": "no-store"})


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
async def auth_mode(body: AuthModeRequest, request: Request):
    cfg = cloud_auth.config()
    principal = getattr(request.state, "cloud_principal", None)
    if cfg.local and isinstance(principal, cloud_auth.Principal):
        if body.mode not in {"personal", "sponsored"} or body.account_id is not None:
            raise HTTPException(422, "Choose personal or sponsored access.")
        if body.mode == "sponsored":
            if not cloud_auth.sponsored_access_enabled():
                raise HTTPException(403, "Sponsored access is disabled.")
            try:
                allowance = cloud_research.snapshot()
            except cloud_research.CloudResearchUnavailable as exc:
                raise HTTPException(503, "Sponsored allowance is unavailable.") from exc
            if float(allowance.get("remaining_usd", 0)) <= 0:
                raise HTTPException(409, "No sponsored allowance remains.")
        try:
            cloud_auth.set_model_access(principal.subject, body.mode)
        except PermissionError as exc:
            raise HTTPException(403, "This account cannot select sponsored access.") from exc
        except (OSError, RuntimeError, ValueError) as exc:
            raise HTTPException(503, "Connection choice could not be saved.") from exc
        return await connection(refresh=True)
    if cfg.enabled and not cfg.local:
        if not isinstance(principal, cloud_auth.Principal):
            raise HTTPException(401, "Authentication required.")
        if body.mode not in {"personal", "sponsored"} or body.account_id is not None:
            raise HTTPException(422, "Choose personal or sponsored access.")
        if body.mode == "sponsored":
            if not cloud_auth.sponsored_access_enabled():
                raise HTTPException(403, "Sponsored access is disabled.")
            try:
                allowance = cloud_research.snapshot()
            except cloud_research.CloudResearchUnavailable as exc:
                raise HTTPException(503, "Sponsored allowance is unavailable.") from exc
            if float(allowance.get("remaining_usd", 0)) <= 0:
                raise HTTPException(409, "No sponsored allowance remains.")
        try:
            cloud_auth.set_model_access(principal.subject, body.mode)
        except PermissionError as exc:
            raise HTTPException(403, "This account cannot select sponsored access.") from exc
        except (OSError, RuntimeError, ValueError) as exc:
            raise HTTPException(503, "Connection choice could not be saved.") from exc
        return await connection(refresh=True)
    await chatgpt_auth.select(body.mode, body.account_id)
    return await connection()


@app.post("/api/ai/disconnect")
async def auth_disconnect():
    if cloud_auth.config().local:
        from sigma.ai_store import sponsor_transaction
        from sigma.cloud_sponsor import expected_email

        async with sponsor_transaction() as state:
            active = state["accounts"].get(state.get("active")) or {}
            if active.get("email", "").casefold() == expected_email():
                raise HTTPException(403, "The sponsor account cannot be disconnected here.")
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
def forget_recent_view(body: ForgetRecentRequest, path: str | None = None):
    from sigma.recents import forget_recent

    forget_recent(body.project_id, path)
    return {"forgotten": True}


app.include_router(cloud_auth.router)
