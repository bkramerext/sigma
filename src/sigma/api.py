"""Local browser adapter. Launch on 127.0.0.1; never bind to a public interface."""

import asyncio
import json
import logging
import os
import re
import secrets
import sqlite3
from collections.abc import AsyncIterator
from contextlib import nullcontext
from dataclasses import asdict, replace
from time import perf_counter
from typing import Any, Literal
from urllib.parse import quote, urlencode
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import (
    HTMLResponse,
    JSONResponse,
    RedirectResponse,
    Response,
    StreamingResponse,
)
from pydantic import AliasChoices, BaseModel, ConfigDict, Field, SecretStr, model_validator
from starlette.concurrency import run_in_threadpool
from starlette.middleware.trustedhost import TrustedHostMiddleware

from sigma import (
    chatgpt_auth,
    cloud_auth,
    cloud_demo,
    cloud_research,
    cloud_workspaces,
    memory_guard,
    paper_scores,
    papers,
    project_collaboration,
    project_diagnostics,
    project_types,
    proposals,
    python_sandbox,
    research_qa,
    research_sessions,
    section_layout_preferences,
    session_log,
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
    save_project_as,
    set_strategy_enabled,
    update_project,
)
from sigma.proposals import (
    accepted_provenance,
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
        not cloud_workspaces.account_scoping_enabled()
        or request.url.path == "/api/ui-instance"
        or (
            request.url.path == "/api/local-runtime/build"
            and request.method == "GET"
            and cloud_auth.config().local
        )
        or request.url.path == "/api/projects/samples"
        or cloud_auth.public_sample_paper_path(request.method, request.url.path)
        or request.url.path.startswith("/api/cloud-auth/")
        or request.url.path.startswith("/api/ai/auth/callback/")
    ):
        yield
        return
    principal = getattr(request.state, "cloud_principal", None)
    if (
        request.url.path == "/api/project-types"
        and request.method == "GET"
        and (not isinstance(principal, cloud_auth.Principal) or principal.role == "guest")
    ):
        yield
        return
    if not isinstance(principal, cloud_auth.Principal):
        raise HTTPException(status_code=401, detail="Authentication required.")
    if cloud_auth.config().local and principal.subject.startswith("local-admin:"):
        # Preserve the old unpartitioned developer shortcut. A real OAuth
        # session is bound below to its own workspace, even on this server.
        yield
        return
    try:
        workspace = await run_in_threadpool(
            cloud_workspaces.workspace_for_subject, principal.subject
        )
        workspace = replace(workspace, email=principal.email, verified_subject=principal.subject)
        token = cloud_workspaces.bind_workspace(workspace)
    except cloud_workspaces.WorkspaceUnavailable as exc:
        raise HTTPException(status_code=503, detail="Private workspace is unavailable.") from exc
    try:
        yield
    finally:
        cloud_workspaces.reset(token)


app = FastAPI(title="SIGMA", docs_url=None, redoc_url=None)


@app.on_event("startup")
async def start_memory_protection() -> None:
    from sigma.memory_guard import attach_loop

    attach_loop(asyncio.get_running_loop())
    from sigma import progress_notifications

    progress_notifications.start_outbox()


@app.on_event("shutdown")
async def stop_memory_protection() -> None:
    from sigma.memory_guard import detach_loop

    detach_loop()
    from sigma import progress_notifications

    progress_notifications.stop_outbox()


_research_qa_tasks: dict[
    tuple[str, str], tuple[tuple[str, str, str, str], asyncio.Task[dict[str, Any]]]
] = {}


def _cleanup_research_qa_task(key: tuple[str, str], task: asyncio.Task[dict[str, Any]]) -> None:
    entry = _research_qa_tasks.get(key)
    if entry is not None and entry[1] is task:
        _research_qa_tasks.pop(key, None)
    if not task.cancelled():
        task.exception()


# Installed before routes, so FastAPI applies this dependency after the auth
# middleware has attached its verified principal. Cloud-auth's own public and
# admin endpoints do not access workspace data.
app.router.dependencies.append(Depends(cloud_workspace_scope))


class ProjectTypeBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str | None = Field(default=None, max_length=100)
    name: str = Field(min_length=1, max_length=80)
    scope: str = Field(min_length=1, max_length=500)
    # Accept historical clients but do not persist the retired description field.
    description: str = Field(default="", max_length=2000, exclude=True)
    based_on: str | None = Field(default=None, max_length=100)
    user_defined: bool = True
    icon: dict[str, Any]
    research_standards_references: list[str | dict[str, str]] = Field(
        default_factory=list, max_length=100
    )
    publication_standards_references: list[str | dict[str, str]] = Field(
        default_factory=list, max_length=100
    )
    origin: str | None = None
    behavior: dict[str, bool] = Field(default_factory=dict)


class ProjectTypeCatalogBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_types: list[ProjectTypeBody] = Field(max_length=500)
    expected_revision: str = Field(min_length=64, max_length=64)
    confirmed_removals: dict[str, int] = Field(default_factory=dict)
    # Optional for older clients: absence preserves existing enable/disable choices.
    reference_preferences: dict[str, dict[str, list[str]]] | None = None
    # Private additions to common reference guides, preserving immutable defaults.
    common_custom_references: dict[str, list[dict[str, str]]] | None = None
    # Private additions to built-in project types (curated definitions remain immutable).
    builtin_custom_references: dict[str, dict[str, list[dict[str, str]]]] | None = None


class ProjectTypeDeleteBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    confirm: bool
    expected_project_count: int = Field(ge=0)
    expected_revision: str = Field(min_length=64, max_length=64)


@app.get("/api/project-types")
def list_project_types_view(request: Request):
    principal = getattr(request.state, "cloud_principal", None)
    if cloud_auth.config().enabled and (principal is None or principal.role == "guest"):
        # Public guests can render sample/type metadata without enumerating a
        # member's private custom catalog. Writes remain authenticated.
        builtins = [item.record() for item in project_types.builtin_types()]
        import hashlib

        revision = hashlib.sha256(
            json.dumps(builtins, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()
        return {
            "project_types": builtins,
            "common_references": project_types.curated_common_references(),
            "common_custom_references": {},
            "builtin_custom_references": {},
            "reference_preferences": {},
            "icons": {"placeholder": project_types.placeholder_icon()},
            "revision": revision,
        }
    return {
        "project_types": [
            *[item.record() for item in project_types.builtin_types()],
            *[item.record() for item in project_types.all_types() if item.user_defined],
        ],
        "common_references": project_types.curated_common_references(),
        "common_custom_references": project_types.common_custom_references(),
        "builtin_custom_references": project_types.builtin_custom_references(),
        "reference_preferences": project_types.reference_preferences(),
        "icons": {"placeholder": project_types.placeholder_icon()},
        "revision": project_types.catalog_revision(),
    }


@app.get("/api/reference-title")
def reference_title_view(url: str):
    """Optional presentation metadata; never required for editing or saving."""
    from sigma.reference_titles import domain_status, resolve_title

    status = domain_status(url)
    return {
        "title": resolve_title(url) if status == "valid" else None,
        "domain_status": status,
    }


@app.put("/api/project-types")
def replace_project_types_view(body: ProjectTypeCatalogBody):
    saved = project_types.replace_custom_types(
        [item.model_dump() for item in body.project_types],
        expected_revision=body.expected_revision,
        confirmed_removals=body.confirmed_removals,
        reference_preferences_update=body.reference_preferences,
        common_custom_references_update=body.common_custom_references,
        builtin_custom_references_update=body.builtin_custom_references,
    )
    return {
        "project_types": [item.record() for item in saved],
        "revision": project_types.catalog_revision(),
    }


@app.get("/api/project-types/{identifier}/usage")
def project_type_usage_view(identifier: str):
    if project_types.get_type(identifier) is None:
        return {"project_count": project_types.project_usage(identifier)}
    return {"project_count": project_types.project_usage(identifier)}


@app.delete("/api/project-types/{identifier}")
def remove_project_type_view(identifier: str, body: ProjectTypeDeleteBody):
    if not body.confirm:
        raise ProjectError("Confirm removal to continue")
    count = project_types.project_usage(identifier)
    if count != body.expected_project_count:
        raise ProjectError("Project references changed; review the removal warning again")
    project_types.remove_type(identifier, expected_revision=body.expected_revision)
    return {"deleted": True, "project_count": count}


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
) -> tuple[Any, Any] | None:
    """Require explicit project/account intent before admitting sponsored inference."""
    memory_guard.require_capacity()
    # Local inference uses the user's personal ChatGPT connection even when
    # Google authentication supplies per-user collaboration workspaces.
    if not cloud_workspaces.enabled() or cloud_auth.config().local:
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
    # Admission callers may reuse this authorized project and connection.
    # Avoid re-reading a large bundle and re-resolving the provider binding.
    return view, credential


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


@app.get("/api/local-runtime/build")
def local_runtime_build(request: Request):
    """Loopback-only, build-identity diagnostic; grants no account or workspace access."""
    from sigma.build_info import build_commit, checkout_commit

    cfg = cloud_auth.config()
    client = request.client.host if request.client is not None else None
    if (
        not cfg.local
        or not os.environ.get("SIGMA_UI_INSTANCE_ID")
        or client not in {"127.0.0.1", "::1", "localhost"}
        or request.url.hostname not in {"127.0.0.1", "localhost"}
    ):
        raise HTTPException(404, "Not found")
    running = build_commit()
    checkout = checkout_commit()
    matched = (
        len(running) == 40 and checkout is not None and len(checkout) == 40 and running == checkout
    )
    return JSONResponse(
        {
            "backend_build_commit": running,
            "backend_checkout_commit": checkout,
            "backend_update_required": not matched,
            "build_verified": matched,
        },
        headers={
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "no-referrer",
        },
    )


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


@app.get("/api/cloud-research/readiness")
async def cloud_research_readiness(request: Request):
    """Sanitized, admin-only checks for customer sponsored research readiness.

    This probes model-catalog authorization but never dispatches inference
    or discloses provider secrets, account identities, or another user's usage.
    A green preflight is not a substitute for a successful real Play test.
    """
    principal = getattr(request.state, "cloud_principal", None)
    if (
        not cloud_workspaces.enabled()
        or not isinstance(principal, cloud_auth.Principal)
        or principal.role != "admin"
    ):
        raise HTTPException(403, "Administrator access required.")
    from sigma.build_info import build_commit, checkout_commit, local_build_mismatch
    from sigma.cloud_sponsor import inference_provider

    provider = inference_provider()
    enabled = cloud_auth.sponsored_access_enabled()
    budget: dict[str, Any] = {}
    try:
        budget = cloud_research.snapshot()
    except (cloud_research.CloudResearchUnavailable, sqlite3.Error, OSError, RuntimeError):
        # A misconfigured or unavailable spend ledger is itself a readiness
        # blocker. Operators still need this endpoint most when it fails.
        pass
    # A catalog check does not incur an inference call or reserve any funds.
    provider_status = "unconfigured"
    provider_token_present = False
    try:
        credential = await sponsored_auth_context()
        provider_token_present = bool(credential.get("token"))
        if provider_token_present and credential.get("status") == "connected":
            state = await connection(refresh=True, context=credential)
            provider_status = str(state.get("status", "unavailable"))
    except (ProjectError, OSError, RuntimeError, ValueError):
        provider_status = "unavailable"
    blockers: list[str] = []
    stale_backend = local_build_mismatch()
    if stale_backend is not None:
        blockers.append("stale_backend_checkout_mismatch")
    if not enabled:
        blockers.append("sponsorship_disabled")
    if provider not in {"chatgpt", "api_key"}:
        blockers.append("sponsored_provider_invalid")
    if not provider_token_present:
        blockers.append("sponsored_provider_credential_missing")
    elif provider_status != "connected":
        blockers.append("provider_connection_unavailable")
    if not budget:
        blockers.append("shared_spending_policy_unavailable")
    elif float(budget.get("global_remaining_usd", 0)) <= 0:
        blockers.append("shared_inference_budget_exhausted")
    return JSONResponse(
        {
            "preflight_ready": not blockers,
            "live_inference_verified": False,
            "provider": provider,
            "provider_status": provider_status,
            "sponsorship_enabled": enabled,
            "global_ceiling_usd": budget.get("global_ceiling_usd"),
            "global_remaining_usd": budget.get("global_remaining_usd"),
            "global_spend_period": budget.get("global_spend_period"),
            "global_reset_at": budget.get("global_reset_at"),
            "blockers": blockers,
            "backend_build_commit": build_commit(),
            "backend_checkout_commit": checkout_commit(),
            "backend_update_required": stale_backend is not None,
        },
        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
    )


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
    from sigma.cloud_sponsor import inference_provider

    try:
        if cloud_auth.model_access_for_subject(principal.subject) == "sponsored":
            cloud_auth.persist_model_connection_status(principal.subject, str(state.get("status")))
    except (sqlite3.Error, OSError, RuntimeError) as exc:
        raise HTTPException(503, "Account connection state could not be saved.") from exc
    return JSONResponse(
        {
            "mode": "sponsored",
            "provider": inference_provider(),
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
    principal = cloud_auth.current_principal()
    subject = principal.subject if principal is not None and principal.role != "guest" else None
    target = cloud_workspaces.guest_workspace(guest_token, create=True, subject=subject)
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
    continue_using_saved_type_settings: bool = False
    browser_presence_required: bool = Field(default=False, strict=True)


class ResearchControlRequest(OpenRequest):
    action: str = Field(min_length=4, max_length=6)
    additional_calls: int = Field(default=0, ge=0, le=12)
    browser_presence_required: bool = Field(default=False, strict=True)
    request_only: bool = Field(default=False, strict=True)


class ResearchInterventionRequest(OpenRequest):
    model_config = ConfigDict(extra="forbid", strict=True)
    kind: Literal["objection", "evidence", "priority"]
    text: str = Field(min_length=1, max_length=20000)
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
    research_rounds: int = Field(ge=1, le=60)
    turns_per_round: int | None = Field(default=None, ge=1, le=20)
    scheduler_version: Literal[2] | None = None
    model_calls: int = Field(ge=2, le=2400)
    session_duration_minutes: int | None = Field(
        ge=1, le=research_sessions.MAX_SESSION_DURATION_MINUTES
    )
    output_tokens_per_call: int = Field(ge=256, le=20000)
    maximum_estimated_cost_usd: float | None = Field(default=None, ge=0.01, le=100)
    maximum_input_tokens_per_session: int | None = Field(default=None, ge=4096, le=1_000_000)
    max_concurrent_sessions: int | str = "1"

    @model_validator(mode="after")
    def validate_legacy_call_ceiling(self) -> "ResearchLimitsRequest":
        # Explicit legacy callers retain their historical 120-call API bound.
        # Version-2 budgets are derived from rounds and paired turns instead.
        if self.scheduler_version is None and self.model_calls > 120:
            raise ValueError("Legacy model call maximum must be 120 or fewer")
        return self


class PaperGenerateRequest(OpenRequest):
    run_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{32}$")
    browser_presence_required: bool = False
    expected_project_id: str = Field(min_length=1, max_length=100)
    expected_binding: str = Field(min_length=1, max_length=512)
    expected_snapshot_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    long_form: bool = False
    include_research_details: bool = False
    include_claim_details: bool = False
    include_validation_notes: bool = False
    include_research_excerpts: bool = False
    include_sigma_issues: bool = False
    # Keep the request name for compatibility; this selects both visual types.
    include_diagrams: bool = True
    # Only an affirmative, section-specific user action may replay a paid
    # request that was dispatched but not saved. This is never a default.
    authorized_recovery_section: int | None = Field(default=None, ge=1, le=48)
    # Explicit Play authorizes redoing the exact unsaved section set checked
    # against persisted dispatch receipts; no additional dialog is needed.
    authorized_recovery_sections: list[int] | None = Field(default=None, max_length=48)
    # This may change the model or billing account of unfinished paid work.
    # Only an explicit, informed user authorization may set it to True.
    authorized_provider_change: bool = False


class PaperCancelRequest(OpenRequest):
    run_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{32}$")
    expected_project_id: str = Field(min_length=1, max_length=100)
    expected_binding: str = Field(min_length=1, max_length=512)
    request_only: bool = False


class PaperDiscardRequest(PaperCancelRequest):
    confirm_discard: Literal[True]


class PaperRestartRequest(OpenRequest):
    run_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{32}$")
    expected_project_id: str = Field(min_length=1, max_length=100)
    expected_binding: str = Field(min_length=1, max_length=512)
    expected_snapshot_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    confirm_restart: Literal[True]
    long_form: bool = False


class PaperUnfinishedRewindRequest(OpenRequest):
    run_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    request_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    expected_project_id: str = Field(min_length=1, max_length=100)
    expected_snapshot_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    stage: Literal[
        "started",
        "review",
        "evidence",
        "planning",
        "writing",
        "validation",
        "typesetting",
        "pdf",
    ]
    confirm_restart: Literal[True]


class PaperRewindRequest(OpenRequest):
    expected_project_id: str = Field(min_length=1, max_length=100)
    expected_binding: str = Field(min_length=1, max_length=512)
    source_pdf_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    expected_snapshot_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    stage: Literal["started", "writing", "validation", "typesetting"]
    confirm_restart: Literal[True]
    run_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{32}$")


class ResearchQARequest(OpenRequest):
    expected_project_id: str = Field(min_length=1, max_length=100)
    expected_binding: str = Field(min_length=1, max_length=512)
    request_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    question: str = Field(min_length=1, max_length=4000)


@app.get("/api/projects/evidence")
def project_evidence_list(path: str):
    from sigma import project_evidence

    principal = cloud_auth.current_principal()
    # Guest reads are safe because the request is already bound to the unique
    # cookie's temporary workspace. Guest writes/uploads remain forbidden.
    files = project_evidence.list_evidence(path)
    # Once project access has been checked, every authorized collaborator can
    # remove Source Material, including attachments uploaded by another member.
    return {
        "files": [
            {
                **entry,
                "enabled": entry.get("enabled", True),
                "can_remove": principal is None or principal.role != "guest",
            }
            for entry in files
        ]
    }


class EvidenceLinkRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: str
    url: str


@app.post("/api/projects/evidence/link")
def project_evidence_add_link(body: EvidenceLinkRequest):
    from sigma import project_evidence

    return project_evidence.add_link(body.path, body.url)


class EvidenceLinkEditRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: str
    url: str
    expected_url: str | None = None


@app.put("/api/projects/evidence/{evidence_id}/link")
def project_evidence_edit_link(evidence_id: str, body: EvidenceLinkEditRequest):
    from sigma import project_evidence

    return project_evidence.edit_link(
        body.path, evidence_id, body.url, expected_url=body.expected_url
    )


class EvidenceEnabledRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: str
    enabled: bool


@app.patch("/api/projects/evidence/{evidence_id}/enabled")
def project_evidence_set_enabled(evidence_id: str, body: EvidenceEnabledRequest):
    from sigma import project_evidence

    return project_evidence.set_enabled(body.path, evidence_id, body.enabled)


@app.post("/api/projects/evidence")
async def project_evidence_upload(request: Request, path: str, filename: str):
    from sigma import project_evidence

    project_evidence.list_evidence(path)  # Reject inaccessible projects before reading bytes.
    data = bytearray()
    async for chunk in request.stream():
        data.extend(chunk)
        if len(data) > project_evidence.MAX_PDF_BYTES:
            raise HTTPException(413, "PDF evidence exceeds 12 MiB.")
    return project_evidence.add_evidence(path, filename, bytes(data))


@app.get("/api/projects/evidence/{evidence_id}/pdf")
def project_evidence_pdf(evidence_id: str, path: str):
    from sigma import project_evidence

    entry, pdf = project_evidence.get_pdf(path, evidence_id)
    return Response(
        pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": "inline; filename*=UTF-8''" + quote(entry["filename"], safe=""),
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@app.delete("/api/projects/evidence/{evidence_id}")
def project_evidence_remove(evidence_id: str, path: str):
    from sigma import project_evidence

    project_evidence.remove_evidence(path, evidence_id)
    return {"deleted": evidence_id}


@app.get("/api/projects/activity-runs")
def project_activity_runs_view(path: str):
    """Run-level activity for the project title and collaborator views."""
    from sigma.recents import project_activity_runs

    return {"runs": project_activity_runs(path)}


@app.get("/api/projects/research-qa/activity")
def research_qa_activity(path: str):
    return {"active": research_qa.list_pending_answers(path)}


@app.get("/api/projects/research-qa")
def research_qa_list(path: str):
    return {
        "answers": research_qa.list_answers(path),
        "archive_available": research_qa.archive_available(path),
    }


@app.post("/api/projects/research-qa")
async def research_qa_answer(body: ResearchQARequest):
    await require_cloud_inference_binding(
        body.expected_binding, body.expected_project_id, body.path
    )
    key = (os.path.realpath(body.path), body.request_id)
    # A collaborator must never attach to another creator's paid task by
    # replaying its request ID, even if both share the sponsored provider.
    creator = project_collaboration.collaborator_identity(body.path) or ""
    fingerprint = (body.expected_project_id, body.expected_binding, body.question, creator)
    entry = _research_qa_tasks.get(key)
    if entry is not None and entry[0] != fingerprint:
        raise ProjectError("Q/A request identifier is in use with different request parameters")
    task = entry[1] if entry is not None else None
    if task is None:
        task = asyncio.create_task(
            research_qa.answer(
                body.path,
                body.question,
                body.expected_project_id,
                body.expected_binding,
                body.request_id,
            )
        )
        memory_guard.track_task(task)
        _research_qa_tasks[key] = (fingerprint, task)
        task.add_done_callback(
            lambda completed, task_key=key: _cleanup_research_qa_task(task_key, completed)
        )
    try:
        return await asyncio.shield(task)
    except asyncio.CancelledError:
        if memory_guard.is_critical():
            return JSONResponse({"error": memory_guard.MESSAGE}, status_code=503)
        raise
    finally:
        if task.done():
            _cleanup_research_qa_task(key, task)


@app.get("/api/projects/research-qa/{qa_id}")
def research_qa_get(qa_id: str, path: str):
    return research_qa.get_answer(path, qa_id)


@app.delete("/api/projects/research-qa/{qa_id}")
def research_qa_delete(qa_id: str, path: str):
    project_collaboration.require_artifact_manager(path, "answer", qa_id)
    research_qa.delete_answer(path, qa_id)
    return {"deleted": qa_id}


@app.get("/api/projects/research-qa/{qa_id}/browser")
def research_qa_browser(qa_id: str, path: str):
    research_qa.get_answer(path, qa_id)
    return RedirectResponse(
        f"/project?{urlencode({'path': path, 'qa_browser': qa_id})}",
        status_code=303,
        headers={"Cache-Control": "no-store"},
    )


@app.get("/api/projects/research-qa/{qa_id}/markdown")
def research_qa_markdown(qa_id: str, path: str):
    record = research_qa.get_answer(path, qa_id)
    return Response(
        research_qa.markdown_document(record),
        media_type="text/markdown; charset=utf-8",
        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
    )


@app.get("/api/projects/papers")
def papers_view(path: str, include_runs: bool = True):
    # A metadata-only list must never wait for unfinished run recovery or
    # checkpoint inspection. Run activity is fetched via /papers/progress.
    saved = papers.list_papers(path)
    available = [paper for paper in saved if paper.get("pdf_available")]
    return {
        "papers": saved,
        "next_paper_number": papers.next_paper_number_for_activity(
            path, include_reserved=include_runs
        ),
        "paper_count": len(available),
        "best_paper_score": paper_scores.best_score(available),
        "runs": papers.run_progress_list(path) if include_runs else [],
    }


@app.get("/api/projects/papers/preflight")
def papers_preflight_view(
    path: str,
    long_form: bool = False,
    expected_project_id: str | None = None,
    expected_binding: str | None = None,
    mode: str | None = None,
    model: str | None = None,
    reasoning_effort: str | None = None,
    run_id: str | None = None,
):
    if run_id is not None:
        project_collaboration.execution_run(path, "paper", run_id, missing_ok=True)
    with papers.paper_run_scope(run_id) if run_id is not None else nullcontext():
        return papers.preflight(
            path,
            force_long_form=long_form,
            expected_project_id=expected_project_id,
            expected_binding=expected_binding,
            mode=mode,
            model=model,
            reasoning_effort=reasoning_effort,
        )


@app.get("/api/projects/papers/progress")
def papers_progress_view(path: str, run_id: str | None = None):
    # Local generation is project-scoped even if an older UI submitted a
    # transient client run ID. Only shared-workspace runs have scoped workers.
    scoped_run_id = run_id if cloud_workspaces.current() is not None else None
    if scoped_run_id is not None:
        project_collaboration.execution_run(path, "paper", scoped_run_id)
    with papers.paper_run_scope(scoped_run_id) if scoped_run_id is not None else nullcontext():
        progress = papers.progress_status(path)
        preflight = papers.needs_preflight_on_open(path)
        stop_pending = papers.stop_request_pending(path)
    return {
        "progress": progress,
        "stop_pending": stop_pending,
        "preflight_needed": preflight,
        "runs": papers.run_progress_list(path),
    }


@app.post("/api/projects/papers/cancel")
async def paper_cancel_view(body: PaperCancelRequest):
    control_started = perf_counter()
    # Stop is a safety/control operation, not a new inference admission.
    # Do not wait for (or require) the current AI connection: a provider outage,
    # account switch, or memory-pressure preflight must never prevent Stop.
    # Project identity and creator authorization remain mandatory.
    view = await run_in_threadpool(inspect_project, body.path)
    if view.project.id != body.expected_project_id:
        raise HTTPException(404, "Project not found or access denied.")
    # The generation endpoint ignores client run IDs in local mode and uses
    # the project task key. Stop must target that SAME worker, not the
    # optimistic client ID (otherwise it acknowledges a nonexistent task).
    scoped_run_id = body.run_id if cloud_workspaces.current() is not None else None
    if scoped_run_id is None:
        await run_in_threadpool(
            project_collaboration.require_paper_draft_operator,
            body.path,
            body.expected_project_id,
            controlling_active=True,
        )
    else:
        await run_in_threadpool(
            project_collaboration.execution_run,
            body.path,
            "paper",
            scoped_run_id,
            operator=True,
        )
    with papers.paper_run_scope(scoped_run_id) if scoped_run_id is not None else nullcontext():
        if body.request_only:
            # Stop is accepted and cancellation scheduled; cleanup may still
            # be running. Never return "cancelled" before it is durable.
            requested = papers.request_cancel_generation(body.path)
            logging.getLogger("sigma.responsiveness").info(
                "paper.stop_ack duration_ms=%.1f request_only=true",
                (perf_counter() - control_started) * 1000,
            )
            return {"stop_requested": requested}
        cancelled = await papers.cancel_generation(body.path)
        logging.getLogger("sigma.responsiveness").info(
            "paper.stop_ack duration_ms=%.1f request_only=false",
            (perf_counter() - control_started) * 1000,
        )
        return {"cancelled": cancelled}


@app.post("/api/projects/papers/discard")
async def papers_discard_view(body: PaperDiscardRequest):
    # Removing unpublished work is a provider-free recovery operation.
    # A disconnected AI provider must not strand a checkpoint or queue receipt,
    # but guest and unauthenticated cloud users cannot mutate another's work.
    workspace = cloud_workspaces.current()
    if (workspace is not None and workspace.guest) or (
        cloud_workspaces.enabled() and cloud_auth.current_principal() is None
    ):
        raise HTTPException(403, "Member access is required to remove Paper work.")
    view = await run_in_threadpool(inspect_project, body.path)
    if view.project.id != body.expected_project_id:
        raise HTTPException(404, "Project not found or access denied.")
    if body.run_id is None:
        await run_in_threadpool(
            project_collaboration.require_paper_draft_operator, body.path, body.expected_project_id
        )
    else:
        await run_in_threadpool(
            project_collaboration.execution_run, body.path, "paper", body.run_id
        )
    owner_terminal = False
    with papers.paper_run_scope(body.run_id) if body.run_id is not None else nullcontext():
        if body.run_id is not None:
            progress = await run_in_threadpool(papers.progress_status, body.path)
            owner_terminal = (
                progress is not None
                and progress.get("status") in {"cancelled", "failed", "interrupted", "stopped"}
                and await run_in_threadpool(project_collaboration.is_project_owner, body.path)
            )
            # Terminal work may be removed by its original author or owner;
            # while running, only the current executor may control it.
            if progress is not None and progress.get("status") in {"active", "queued"}:
                await run_in_threadpool(
                    project_collaboration.execution_run,
                    body.path,
                    "paper",
                    body.run_id,
                    operator=True,
                )
        result = await papers.discard_work(body.path, body.expected_project_id)
    if body.run_id is not None:
        await run_in_threadpool(
            project_collaboration.discard_execution_run,
            body.path,
            "paper",
            body.run_id,
            owner_terminal=owner_terminal,
        )
    return result


@app.post("/api/projects/papers/restart")
async def papers_restart_view(body: PaperRestartRequest):
    if body.run_id is None:
        project_collaboration.require_paper_draft_operator(body.path, body.expected_project_id)
    else:
        # Restart is permitted for any member when the run is stopped.
        # restart_work itself verifies a stopped checkpoint.
        project_collaboration.execution_run(body.path, "paper", body.run_id)
    with papers.paper_run_scope(body.run_id) if body.run_id is not None else nullcontext():
        return await papers.restart_work(
            body.path,
            body.expected_project_id,
            body.expected_binding,
            body.expected_snapshot_sha256,
            body.confirm_restart,
            body.long_form,
        )


@app.get("/api/projects/papers/unfinished-checkpoints")
def paper_unfinished_checkpoints(path: str, run_id: str, allow_active: bool = False):
    project_collaboration.execution_run(path, "paper", run_id, operator=allow_active)
    with papers.paper_run_scope(run_id):
        return papers.unfinished_restart_options(path, allow_active=allow_active)


@app.post("/api/projects/papers/unfinished-checkpoints")
async def paper_unfinished_rewind(body: PaperUnfinishedRewindRequest):
    # Restarting a stopped checkpoint is provider-free and available to
    # collaborators. The actual Play still claims the execution controller.
    project_collaboration.execution_run(body.path, "paper", body.run_id)
    with papers.paper_run_scope(body.run_id):
        return await papers.restart_unfinished_step(
            body.path,
            body.expected_project_id,
            body.expected_snapshot_sha256,
            body.stage,
            request_id=body.request_id,
        )


@app.get("/api/projects/papers/{paper_id}/rewind")
def paper_rewind_options(paper_id: str, path: str):
    from sigma import paper_rewind

    # The source publication is immutable; creating a new run does not
    # require permission to remove another collaborator's saved Paper.
    return paper_rewind.describe(path, paper_id, inspect_project(path).project.id)


@app.post("/api/projects/papers/{paper_id}/rewind")
async def paper_rewind_view(paper_id: str, body: PaperRewindRequest):
    from sigma import paper_rewind

    await require_cloud_inference_binding(
        body.expected_binding, body.expected_project_id, body.path
    )
    # An authorized member may start a NEW run from a published Paper,
    # without changing the original publication.
    # Validate the immutable source before allocating a new collaborator run.
    source = paper_rewind.describe(body.path, paper_id, body.expected_project_id)
    if (
        source["source_pdf_sha256"] != body.source_pdf_sha256
        or source["snapshot_sha256"] != body.expected_snapshot_sha256
    ):
        raise ProjectError("Published Paper changed; reopen before restarting.")
    account = await auth_context()
    config = await papers.configuration(view=inspect_project(body.path), context=account)
    if not config["available"]:
        raise ProjectError(config["message"])
    shared = cloud_workspaces.current() is not None
    reservation = None
    run_id = body.run_id or (uuid4().hex if shared else None)
    if shared:
        assert run_id is not None
        project_collaboration.register_owner(inspect_project(body.path))
        reservation = project_collaboration.reserve_execution_run(
            body.path,
            "paper",
            run_id,
            papers.next_paper_number_for_activity(body.path, include_reserved=False) - 1,
            model=config["model"],
            thinking=config["reasoning_effort"],
        )
        if reservation is None:
            raise ProjectError("Paper run reservation is unavailable.")
    else:
        project_collaboration.reserve_paper_draft(
            body.path, body.expected_project_id, resuming=False
        )
    scope = (
        papers.paper_run_scope(run_id, number=reservation["number"])
        if reservation is not None and run_id is not None
        else nullcontext()
    )
    with scope:
        try:
            result = await paper_rewind.create(
                body.path,
                paper_id,
                body.expected_project_id,
                body.source_pdf_sha256,
                body.stage,
                expected_snapshot_sha256=body.expected_snapshot_sha256,
                auth=account,
                config=config,
            )
        except Exception:
            # Failed rewind admissions must not leave a phantom interrupted
            # collaborator run. Never tombstone a successfully saved checkpoint.
            if (
                reservation is not None
                and run_id is not None
                and papers._load_work(body.path) is None
            ):
                project_collaboration.discard_execution_run(body.path, "paper", run_id)
            raise
    return {
        **result,
        "run_id": run_id,
        "number": reservation["number"] if reservation is not None else None,
    }


@app.get("/api/projects/papers/{paper_id}")
def paper_view(paper_id: str, path: str):
    # The TeX download has its own endpoint; do not hydrate large TeX text
    # into the interactive paper metadata response.
    return papers.get_paper(path, paper_id, include_tex=False)


class PaperScoreRequest(OpenRequest):
    expected_project_id: str = Field(min_length=1, max_length=100)
    expected_binding: str = Field(min_length=1, max_length=512)
    force: bool = False


@app.post("/api/projects/papers/{paper_id}/score")
async def paper_score_view(paper_id: str, body: PaperScoreRequest):
    await require_cloud_inference_binding(
        body.expected_binding, body.expected_project_id, body.path
    )
    try:
        score = await paper_scores.score_paper(
            body.path,
            paper_id,
            body.expected_binding,
            body.expected_project_id,
            force=body.force,
        )
        papers.mark_scored_progress(body.path, paper_id)
        project_collaboration.note_artifact_author(body.path, "paper", paper_id)
        return {"score": score}
    except asyncio.CancelledError:
        if memory_guard.is_critical():
            return JSONResponse({"error": memory_guard.MESSAGE}, status_code=503)
        raise


@app.post("/api/projects/papers/{paper_id}/eli5")
async def paper_eli5_view(paper_id: str, body: PaperScoreRequest):
    from sigma.paper_eli5 import explain

    await require_cloud_inference_binding(
        body.expected_binding, body.expected_project_id, body.path
    )
    try:
        markdown = await explain(
            body.path, paper_id, body.expected_binding, body.expected_project_id
        )
    except asyncio.CancelledError:
        if memory_guard.is_critical():
            return JSONResponse({"error": memory_guard.MESSAGE}, status_code=503)
        raise
    except ProjectError:
        raise
    except Exception:
        logging.getLogger(__name__).exception("Unexpected ELI5 explanation failure")
        return JSONResponse(
            {
                "error": "The explanation failed unexpectedly. Please retry or inspect the server logs."
            },
            status_code=500,
        )
    return {"markdown": markdown}


@app.get("/api/projects/papers/{paper_id}/pdf")
def paper_pdf_view(paper_id: str, path: str, open_in_browser: bool = False):
    disposition = "inline" if open_in_browser else "attachment"
    filename = f"{papers.paper_download_basename(path, paper_id)}.pdf"
    fallback = filename.encode("ascii", "ignore").decode("ascii") or "sigma-paper.pdf"
    return Response(
        papers.get_pdf(path, paper_id),
        media_type="application/pdf",
        headers={
            "Cache-Control": "no-store",
            "Content-Disposition": (
                f"{disposition}; filename=\"{fallback}\"; filename*=UTF-8''{quote(filename, safe='')}"
            ),
        },
    )


@app.get("/api/projects/papers/{paper_id}/txt")
def paper_txt_view(paper_id: str, path: str):
    filename = f"{papers.paper_download_basename(path, paper_id)}.txt"
    fallback = filename.encode("ascii", "ignore").decode("ascii") or "sigma-paper.txt"
    return Response(
        papers.paper_text(path, paper_id),
        media_type="text/plain; charset=utf-8",
        headers={
            "Cache-Control": "no-store",
            "Content-Disposition": (
                f"attachment; filename=\"{fallback}\"; filename*=UTF-8''{quote(filename, safe='')}"
            ),
        },
    )


@app.get("/api/projects/papers/{paper_id}/tex")
def paper_tex_view(paper_id: str, path: str):
    filename = f"{papers.paper_download_basename(path, paper_id)}.tex"
    fallback = filename.encode("ascii", "ignore").decode("ascii") or "sigma-paper.tex"
    return Response(
        papers.paper_tex(path, paper_id),
        media_type="application/x-tex; charset=utf-8",
        headers={
            "Cache-Control": "no-store",
            "Content-Disposition": (
                f"attachment; filename=\"{fallback}\"; filename*=UTF-8''{quote(filename, safe='')}"
            ),
        },
    )


@app.delete("/api/projects/papers/{paper_id}")
def paper_delete_view(paper_id: str, path: str):
    project_collaboration.require_artifact_manager(path, "paper", paper_id)
    papers.delete_paper(path, paper_id)
    return {"deleted": paper_id}


@app.post("/api/projects/papers")
async def paper_generate_view(body: PaperGenerateRequest, request: Request):
    admission_started = perf_counter()
    verified_view = await require_cloud_inference_binding(
        body.expected_binding, body.expected_project_id, body.path
    )

    # This task belongs to the project, not the SSE subscriber. Sleeping
    # laptops and mobile browsers routinely drop streams; that must not turn
    # into a provider cancellation or lost paper.
    updates: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=64)
    viewer_connected = True

    async def progress(event: papers.PaperProgressEvent) -> None:
        if not viewer_connected:
            return
        if updates.full():
            updates.get_nowait()
        updates.put_nowait(dict(event))

    presence_kwargs: dict[str, Any] = (
        {"browser_presence_required": True} if body.browser_presence_required else {}
    )
    from sigma import project_collaboration

    # Reserve a distinct Paper and number *before* scheduling provider work.
    # Local single-user projects keep their existing checkpoint selection.
    shared = cloud_workspaces.current() is not None
    reservation: dict[str, Any] | None = None
    run_id: str | None = None
    if shared:
        admission_view = (
            verified_view[0]
            if verified_view
            else await run_in_threadpool(inspect_project, body.path)
        )
        await run_in_threadpool(project_collaboration.register_owner, admission_view)
        run_id = body.run_id or uuid4().hex
        account = verified_view[1] if verified_view else await auth_context()
        config = await papers.configuration(view=admission_view, context=account)
        if not config["available"]:
            raise ProjectError(config["message"])
        # Disk-backed sequence and SQLite admission are synchronous. Run them
        # off the API event loop so another user's Stop remains responsive.
        saved_max = (
            await run_in_threadpool(
                papers.next_paper_number_for_activity, body.path, include_reserved=False
            )
            - 1
        )
        # Determine restart eligibility from the durable run's own sidecar.
        # It is never inferred from a different paper's global busy state.
        with papers.paper_run_scope(run_id):
            previous = await run_in_threadpool(papers.progress_status, body.path)
        resume_stopped = bool(
            previous and previous.get("status") in {"cancelled", "failed", "interrupted", "stopped"}
        )
        reservation = await run_in_threadpool(
            project_collaboration.reserve_execution_run,
            body.path,
            "paper",
            run_id,
            saved_max,
            model=config["model"],
            thinking=config["reasoning_effort"],
            resume_stopped_paper=resume_stopped,
        )
        if reservation is None:
            raise ProjectError("Paper reservation is unavailable.")
        # The atomic reservation already verified permanent creator ownership,
        # discarded state and published artifacts. Avoid a separate SQLite ACL
        # read before it; a published run still cannot be dispatched twice.
        if reservation.get("artifact_id"):
            raise ProjectError("This Paper run is already published; open the PDF.")
    else:
        project_collaboration.reserve_paper_draft(
            body.path,
            body.expected_project_id,
            resuming=papers._load_work(body.path) is not None,
        )
    scope = (
        papers.paper_run_scope(run_id, number=reservation["number"])
        if run_id is not None and reservation is not None
        else nullcontext()
    )
    with scope:
        task = asyncio.create_task(
            papers.generate(
                body.path,
                body.expected_binding,
                body.expected_project_id,
                progress=progress,
                force_long_form=body.long_form,
                expected_snapshot_sha256=body.expected_snapshot_sha256,
                include_research_details=body.include_research_details,
                include_claim_details=body.include_claim_details,
                include_validation_notes=body.include_validation_notes,
                include_research_excerpts=body.include_research_excerpts,
                include_sigma_issues=body.include_sigma_issues,
                include_diagrams=body.include_diagrams,
                authorized_recovery_section=body.authorized_recovery_section,
                **(
                    {"authorized_recovery_sections": body.authorized_recovery_sections}
                    if body.authorized_recovery_sections is not None
                    else {}
                ),
                **({"authorized_provider_change": True} if body.authorized_provider_change else {}),
                **presence_kwargs,
            )
        )
        try:
            # Synchronous, durable receipt: an immediate Stop sees the task.
            papers.register_submission(body.path, task)
        except BaseException:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            raise

    def observe_detached_result(completed: asyncio.Task[dict[str, Any]]) -> None:
        if completed.cancelled():
            return
        error = completed.exception()
        if error is None:
            paper_id = completed.result().get("paper_id")
            if isinstance(paper_id, str):
                try:
                    if run_id is not None:
                        project_collaboration.note_execution_artifact_author(
                            body.path, "paper", run_id, paper_id
                        )
                    else:
                        project_collaboration.note_artifact_author(
                            body.path, "paper", paper_id, created_only=True
                        )
                except (OSError, sqlite3.Error, ValueError):
                    logging.getLogger(__name__).warning(
                        "Paper author attribution unavailable for %s", paper_id
                    )
        elif not isinstance(error, ProjectError):
            logging.getLogger(__name__).error(
                "Detached paper generation failed: %s", type(error).__name__
            )

    task.add_done_callback(observe_detached_result)

    async def stream():
        nonlocal viewer_connected
        try:
            while not task.done() or not updates.empty():
                try:
                    update = await asyncio.wait_for(updates.get(), timeout=1)
                except TimeoutError:
                    with papers.paper_run_scope(run_id) if run_id is not None else nullcontext():
                        current = papers.progress_status(body.path)
                    if current is None:
                        yield ": paper generation is active\n\n"
                    else:
                        yield (
                            "data: "
                            + json.dumps(
                                {"type": "heartbeat", "progress": current}, separators=(",", ":")
                            )
                            + "\n\n"
                        )
                    continue
                yield "data: " + json.dumps(update, separators=(",", ":")) + "\n\n"
            result = await task
            yield "data: " + json.dumps({"type": "complete", "result": result}) + "\n\n"
        except asyncio.CancelledError:
            # Differentiate cancellation of the job itself from teardown of
            # this SSE viewer. Disconnects never cancel the backend paper.
            if not task.cancelled():
                raise
            reason = (
                memory_guard.MESSAGE
                if memory_guard.is_critical()
                else "Paper generation cancelled; completed work remains available."
            )
            yield "data: " + json.dumps({"type": "error", "error": reason}) + "\n\n"
        except ProjectError as exc:
            event: dict[str, str | int] = {"type": "error", "error": str(exc)}
            provider_calls_attempted = getattr(exc, "provider_calls_attempted", None)
            if type(provider_calls_attempted) is int:
                event["provider_calls_attempted"] = provider_calls_attempted
            yield "data: " + json.dumps(event) + "\n\n"
        except Exception as exc:  # noqa: BLE001 - SSE must emit an error after HTTP 200
            # StreamingResponse already sent HTTP 200. Log only safe stack
            # locations and exception class: exception text may contain
            # private project or provider content on the persistent log disk.
            from sigma.production_observability import safe_exception_trace

            logging.getLogger(__name__).error(
                "Unexpected paper-generation failure type=%s frames=%s",
                type(exc).__name__,
                safe_exception_trace(exc),
            )
            yield (
                "data: "
                + json.dumps(
                    {
                        "type": "error",
                        "error": (
                            "An unexpected paper-generation error occurred. "
                            "No version was published. Check server logs; "
                            "work may be resumable."
                        ),
                    }
                )
                + "\n\n"
            )
        finally:
            # Stream teardown only disconnects the viewer. The independent
            # generation task retains its own checkpoints and lifecycle.
            viewer_connected = False

    logging.getLogger("sigma.responsiveness").info(
        "paper.start_ack duration_ms=%.1f", (perf_counter() - admission_started) * 1000
    )
    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-store",
            "X-Accel-Buffering": "no",
            **({"X-Sigma-Paper-Run": run_id} if run_id is not None else {}),
        },
    )


class GlobalResearchSettingsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    limits: dict[str, Any] | None = None
    ai_model: str | None = Field(default=None, min_length=1, max_length=128)
    reasoning_effort: str | None = Field(default=None, min_length=1, max_length=40)
    show_advanced_outcome_details: bool | None = None


@app.get("/api/user-preferences/research-settings")
def global_research_settings_view():
    from sigma import global_research_settings

    principal = cloud_auth.current_principal()
    if principal is not None and principal.role == "guest":
        raise HTTPException(403, "Sign in to view research settings.")
    return global_research_settings.load_config()


@app.put("/api/user-preferences/research-settings")
def global_research_settings_update(body: GlobalResearchSettingsRequest):
    from sigma import global_research_settings

    principal = cloud_auth.current_principal()
    if principal is not None and principal.role == "guest":
        raise HTTPException(403, "Sign in to change research settings.")
    changes = body.model_dump(exclude_none=True)
    # Explicit null limits are not meaningful; omit unchanged fields.
    return global_research_settings.save_config(changes)


class ResearchEthosPreference(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    markdown: str | None


@app.get("/api/user-preferences/research-ethos")
def research_ethos_preference():
    from sigma import research_ethos

    principal = cloud_auth.current_principal()
    if principal is not None and principal.role == "guest":
        raise HTTPException(403, "Sign in to view Research Ethos.")
    return research_ethos.current()


@app.put("/api/user-preferences/research-ethos")
def update_research_ethos_preference(body: ResearchEthosPreference):
    from sigma import research_ethos

    principal = cloud_auth.current_principal()
    if principal is not None and principal.role == "guest":
        raise HTTPException(403, "Sign in to change Research Ethos.")
    return research_ethos.save_override(body.markdown)


@app.post("/api/user-preferences/research-ethos/recover")
def recover_invalid_research_ethos():
    """Requires explicit UI confirmation; preserve malformed data in a backup."""
    from sigma import research_ethos

    principal = cloud_auth.current_principal()
    if principal is not None and principal.role == "guest":
        raise HTTPException(403, "Sign in to recover Research Ethos.")
    return research_ethos.quarantine_invalid_override()


@app.get("/api/projects/research-limits")
def research_limits_view(path: str):
    inspect_project(path)
    limits = research_sessions._new_session_limits(research_sessions.get_limits(path))
    return {**limits, "max_concurrent_sessions": str(limits["max_concurrent_sessions"])}


@app.put("/api/projects/research-limits")
def research_limits_update(body: ResearchLimitsRequest):
    inspect_project(body.path)
    if (body.scheduler_version is None) != (body.turns_per_round is None):
        raise ProjectError("Scheduler version and turns per round must be saved together")
    limits = research_sessions.save_limits(
        body.path,
        {
            "research_rounds": body.research_rounds,
            **(
                {
                    "scheduler_version": body.scheduler_version,
                    "turns_per_round": body.turns_per_round,
                }
                if body.scheduler_version is not None
                else {}
            ),
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


class WorkspacePresenceRequest(BaseModel):
    viewer_id: str = Field(min_length=36, max_length=36)


@app.post("/api/projects/research-presence/workspace")
def research_workspace_presence_view(body: WorkspacePresenceRequest):
    """Renew the authenticated workspace lease without a blocking SSE stream."""
    from sigma import research_presence

    principal = cloud_auth.current_principal()
    if principal and principal.role == "guest":
        raise HTTPException(403, "Guests cannot keep paid research active")
    research_presence.refresh_workspace_viewer(body.viewer_id)
    return {"connected": True}


@app.post("/api/projects/research-presence/auth-handoff")
def research_presence_auth_handoff():
    """Only explicit authenticated sign-out may start a bounded handoff."""
    from sigma import research_presence

    principal = cloud_auth.current_principal()
    if principal and principal.role == "guest":
        raise HTTPException(403, "Guests cannot preserve paid work")
    research_presence.begin_auth_handoff()
    return {"ready": True}


@app.get("/api/projects/research-presence")
async def research_presence_view(path: str):
    """Project-scoped browser lease, independent of AI-account binding."""
    from sigma import research_presence

    principal = cloud_auth.current_principal()
    if principal and principal.role == "guest":
        raise HTTPException(403, "Guests cannot keep paid research active")
    marker = research_presence.open_viewer(path)

    async def heartbeat():
        try:
            while True:
                research_presence.touch_viewer(marker)
                yield ": SIGMA browser viewer connected\n\n"
                await asyncio.sleep(8)
        finally:
            research_presence.close_viewer(marker)

    return StreamingResponse(
        heartbeat(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache, no-store", "X-Accel-Buffering": "no"},
    )


class ProgressEmailPreference(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    enabled: bool


@app.get("/api/user-preferences/progress-email")
def progress_email_preference():
    from sigma import progress_notifications

    return progress_notifications.preference(cloud_auth.current_principal())


@app.put("/api/user-preferences/progress-email")
def set_progress_email_preference(body: ProgressEmailPreference):
    from sigma import progress_notifications

    principal = cloud_auth.current_principal()
    if principal is None or principal.role == "guest":
        raise HTTPException(403, "Sign in with Google to change progress email notifications.")
    try:
        return progress_notifications.update_preference(principal, body.enabled)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.get("/api/user-preferences/unattended-execution")
def unattended_execution_preference():
    from sigma import research_preferences

    principal = cloud_auth.current_principal()
    if principal and principal.role == "guest":
        raise HTTPException(403, "Guests cannot change unattended execution preferences")
    return {
        "allow_unattended_background_execution": research_preferences.allow_unattended_background_execution()
    }


class UnattendedExecutionPreference(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    allow_unattended_background_execution: bool


@app.put("/api/user-preferences/unattended-execution")
def set_unattended_execution_preference(body: UnattendedExecutionPreference):
    from sigma import research_preferences

    principal = cloud_auth.current_principal()
    if principal and principal.role == "guest":
        raise HTTPException(403, "Guests cannot change unattended execution preferences")
    return {
        "allow_unattended_background_execution": research_preferences.update_unattended_background_execution(
            body.allow_unattended_background_execution
        )
    }


class SectionLayoutPreference(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    expand_one_project_section_at_a_time: bool


@app.get("/api/user-preferences/section-layout")
def section_layout_preference():
    principal = cloud_auth.current_principal()
    if principal and principal.role == "guest":
        raise HTTPException(403, "Guests cannot change section layout preferences")
    return {
        "expand_one_project_section_at_a_time": section_layout_preferences.expand_one_project_section_at_a_time()
    }


@app.put("/api/user-preferences/section-layout")
def set_section_layout_preference(body: SectionLayoutPreference):
    principal = cloud_auth.current_principal()
    if principal and principal.role == "guest":
        raise HTTPException(403, "Guests cannot change section layout preferences")
    return {
        "expand_one_project_section_at_a_time": section_layout_preferences.update_expand_one_project_section_at_a_time(
            body.expand_one_project_section_at_a_time
        )
    }


@app.get("/api/projects/research-sessions")
async def research_sessions_view(path: str):
    principal = cloud_auth.current_principal()
    if not (principal and principal.role == "guest"):
        await research_sessions.ensure_queued_workers(path)
    from sigma.research_state import build_current_understanding

    sessions = research_sessions.list_sessions(path)
    project = inspect_project(path).project
    return {
        "sessions": sessions,
        "max_concurrent_sessions": research_sessions.get_limits(path)["max_concurrent_sessions"],
        "current_understanding": build_current_understanding(project.id, sessions),
    }


@app.get("/api/projects/research-sessions/{session_id}")
async def research_session_view(session_id: str, path: str):
    principal = cloud_auth.current_principal()
    if not (principal and principal.role == "guest"):
        await research_sessions.ensure_queued_workers(path)
    return research_sessions.get_session(path, session_id)


class ClientDiagnosticRequest(OpenRequest):
    stage: str = Field(min_length=1, max_length=40)
    code: str = Field(min_length=1, max_length=64)
    message: str = Field(min_length=1, max_length=1600)
    correlation_id: str | None = Field(default=None, max_length=80)
    # Browser-authored errors are project-scoped, never authoritative
    # evidence of membership in a research session.
    session_id: str | None = Field(default=None, max_length=80)


@app.post("/api/projects/diagnostics")
def record_project_diagnostic(body: ClientDiagnosticRequest):
    try:
        diagnostic = project_diagnostics.append(
            body.path,
            stage=body.stage,
            code=body.code,
            message=body.message,
            session_id=None,  # Untrusted browser claims cannot enter session exports.
            correlation_id=body.correlation_id,
        )
    except (ProjectError, OSError, ValueError):
        return JSONResponse(
            {
                "recorded": False,
                "error": "Diagnostic not recorded (storage unavailable or full). The displayed error remains available to copy.",
            },
            status_code=503,
        )
    return {"recorded": True, "diagnostic": diagnostic}


@app.get("/api/projects/diagnostics")
def project_diagnostics_view(path: str):
    return {"diagnostics": project_diagnostics.read(path)}


@app.get("/api/projects/diagnostics/download")
def project_diagnostics_download(path: str):
    return Response(
        project_diagnostics.export(path),
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=project-diagnostics.log"},
    )


@app.get("/api/projects/research-sessions/{session_id}/log")
def research_session_log_view(session_id: str, path: str, after: int = 0):
    try:
        return session_log.read(path, session_id, max(0, after))
    except (ProjectError, ValueError, OSError) as exc:
        raise HTTPException(404, "Session log not found or access denied.") from exc


@app.get("/api/projects/research-sessions/{session_id}/log/download")
def research_session_log_download_view(session_id: str, path: str):
    try:
        result = session_log.read(path, session_id, 0)  # Reuse project/session ownership checks.
        body = session_log.markdown_export(
            result["events"],
            result["session"],
            result["project_title"],
            result["reference_preparation"],
        )
        # Same sanitized project diagnostic records appear in readable session
        # exports when explicitly correlated to this session. Do not import
        # pre-session errors into unrelated historical session logs.
        try:
            related = [
                item
                for item in project_diagnostics.read(path)
                if item.get("session_id") == session_id
            ]
        except (ProjectError, OSError, ValueError):
            # Diagnostic storage failure must never make the session log unavailable.
            related = []
        if related:
            body += "\n## Exportable UI diagnostics\n\n"
            for item in related:
                body += (
                    f"- {item['timestamp']} · {item['code']} · {item['id']}: {item['message']}\n"
                )
        filename = session_log.export_filename(
            result["saved_short_name"], result["project_title"], result["session"]["number"]
        )
        # RFC 5987 preserves readable Unicode while the ASCII fallback keeps
        # Content-Disposition safe for Latin-1 HTTP headers and older browsers.
        ascii_name = filename.encode("ascii", "ignore").decode("ascii") or "project.log"
        return Response(
            body,
            media_type="text/markdown; charset=utf-8",
            headers={
                "Content-Disposition": f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(filename)}"
            },
        )
    except (ProjectError, ValueError, OSError) as exc:
        raise HTTPException(404, "Session log not found or access denied.") from exc


class MockResearchStartRequest(OpenRequest):
    strategy_id: str
    idempotency_key: str
    expected_project_id: str
    continue_using_saved_type_settings: bool = False


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
    result = research_sessions.mock_session(
        body.path,
        body.strategy_id,
        body.idempotency_key,
        scenario,
        body.continue_using_saved_type_settings,
    )
    project_collaboration.note_artifact_author(
        body.path, "session", result["id"], created_only=True
    )
    return result


@app.post("/api/projects/research-sessions/start")
async def research_start_view(body: ResearchStartRequest):
    """Independent Session admission; per-session state already has durable IDs."""
    admission_started = perf_counter()
    try:
        result = await research_sessions.start_session(
            body.path,
            body.strategy_id,
            body.idempotency_key,
            body.expected_project_id,
            body.expected_binding,
            body.expected_limits,
            body.strategy_ids,
            body.continue_using_saved_type_settings,
            body.browser_presence_required,
        )
    except ProjectError as exc:
        safe_message = project_diagnostics.sanitize(str(exc))
        try:
            diagnostic = project_diagnostics.append(
                body.path,
                stage="admission",
                code="research_admission_failed",
                message=safe_message,
                correlation_id=str(body.idempotency_key),
                http_status=400,
            )
        except (ProjectError, OSError, ValueError):
            return JSONResponse(
                {"error": safe_message, "diagnostic_recorded": False},
                status_code=400,
            )
        return JSONResponse(
            {
                "error": diagnostic["message"],
                "diagnostic_recorded": True,
                "diagnostic": diagnostic,
            },
            status_code=400,
        )
    if isinstance(result.get("id"), str):
        await run_in_threadpool(
            project_collaboration.note_artifact_author,
            body.path,
            "session",
            result["id"],
            created_only=True,
        )
    logging.getLogger("sigma.responsiveness").info(
        "session.start_ack duration_ms=%.1f", (perf_counter() - admission_started) * 1000
    )
    return result


@app.post("/api/projects/research-sessions/{session_id}/control")
async def research_control_view(session_id: str, body: ResearchControlRequest, request: Request):
    control_started = perf_counter()
    await run_in_threadpool(
        project_collaboration.require_execution_operator,
        body.path,
        "session",
        session_id,
        "Research session",
    )
    cfg = cloud_auth.config()
    principal = getattr(request.state, "cloud_principal", None)
    if (
        cloud_auth._mock_enabled(cfg)
        and isinstance(principal, cloud_auth.Principal)
        and principal.subject.startswith("mock:")
    ):
        if body.additional_calls:
            raise HTTPException(400, "Mock research cannot extend provider-call limits.")
        simulated = await run_in_threadpool(
            research_sessions.control_mock_session, body.path, session_id, body.action
        )
        if simulated is None:
            raise HTTPException(404, "Not found")
        await run_in_threadpool(
            project_collaboration.note_artifact_author, body.path, "session", session_id
        )
        return simulated

    result = await research_sessions.control_session(
        body.path,
        session_id,
        body.action,
        additional_calls=body.additional_calls,
        browser_presence_required=body.browser_presence_required,
        acknowledge_only=body.request_only,
    )
    await run_in_threadpool(
        project_collaboration.note_artifact_author,
        body.path,
        "session",
        session_id,
        created_only=True,
    )
    logging.getLogger("sigma.responsiveness").info(
        "session.control_ack action=%s duration_ms=%.1f request_only=%s",
        body.action,
        (perf_counter() - control_started) * 1000,
        body.request_only,
    )
    return result


@app.post("/api/projects/research-sessions/{session_id}/interventions")
async def research_intervention_view(session_id: str, body: ResearchInterventionRequest):
    project_collaboration.require_execution_operator(
        body.path, "session", session_id, "Research session"
    )
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
async def research_session_remove_view(session_id: str, body: ResearchSessionRemoveRequest):
    session = research_sessions.get_session(body.path, session_id)
    project_collaboration.require_artifact_manager(
        body.path,
        "session",
        session_id,
        owner_terminal=session["status"] in {"completed", "ended"},
    )
    return await research_sessions.remove_session(body.path, session_id, body.expected_updated_at)


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


class ProjectOpenRequest(OpenRequest):
    # The interactive project page never renders its historical event log.
    # Keep the full API response as the default for exports and external clients.
    compact: bool = False


@app.post("/api/projects/open")
def open_view(body: ProjectOpenRequest):
    from sigma import project_collaboration

    view = open_project(body.path)
    project_collaboration.register_owner(view)
    if body.compact:
        view = replace(view, project=replace(view.project, events=()))
    return asdict(view)


@app.post("/api/projects/init", status_code=201)
def init_view(body: InitRequest):
    if (
        body.investigation_type != "default"
        and project_types.get_type(body.investigation_type) is None
    ):
        raise ProjectError("Choose a currently available project type")
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
    from sigma import project_collaboration

    view = inspect_project(path)
    project_collaboration.register_owner(view)
    return asdict(view)


@app.get("/api/projects/collaboration")
def project_collaboration_view(
    path: str, verify_revision: bool = False, include_authors: bool = True
):
    from sigma import project_collaboration

    view = inspect_project(path)
    project_collaboration.register_owner(view)
    return project_collaboration.summary(
        view.path, verify_revision=verify_revision, include_authors=include_authors
    )


class RetryCollaborationNoticesRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: str = Field(min_length=1, max_length=4096)


@app.post("/api/projects/collaboration/notifications/retry")
def retry_collaboration_notices_view(body: RetryCollaborationNoticesRequest):
    from sigma import project_collaboration

    view = inspect_project(body.path)
    count = project_collaboration.retry_failed_notifications(view.path)
    return {"requeued": count}


class LeaveCollaborationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: str = Field(min_length=1, max_length=4096)
    project_id: str = Field(min_length=1, max_length=128)


@app.post("/api/projects/collaboration/leave")
def leave_collaboration_view(body: LeaveCollaborationRequest):
    """A verified collaborator may revoke only their own membership."""
    from sigma import project_collaboration

    project_collaboration.leave_project(body.path, body.project_id)
    return {"left": True}


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
    from sigma.project_transfer import export_project
    from sigma.projects import project_path

    authorized = project_path(path)
    inspect_project(authorized)
    content = export_project(authorized)
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
    from sigma.project_bundle import BundleError
    from sigma.project_transfer import VERSION, bundle_document, import_project
    from sigma.projects import (
        _occupied_titles,
        _project_name,
        _title_key,
        _title_registry_lock,
        projects_root,
    )

    try:
        # Legacy single-file projects remain readable internally, but external
        # uploads must use v4. Accepting v1-v3 here would silently drop the
        # separate artifact archive that v4 requires.
        if type(body.bundle.get("version")) is not int or body.bundle["version"] != VERSION:
            raise BundleError("Only version 4 project exports can be imported")
        document = bundle_document(body.bundle)
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
                    suffix = f" v{number - 1}"
                    candidate = title[: 200 - len(suffix)].rstrip() + suffix
                _, name = _project_name(candidate)
                destination = root / name
                if (
                    _title_key(candidate) in occupied_titles
                    or os.path.lexists(destination)
                    or os.path.lexists(root / name)
                ):
                    continue
                imported = import_project(
                    body.bundle,
                    destination,
                    title_override=candidate if candidate != title else None,
                )
                break
            if imported is None:
                raise ProjectError("A unique name for the imported project is unavailable.")
        view = inspect_project(imported)
        from sigma.recents import record_access

        record_access(view)
        return asdict(view)
    except (KeyError, TypeError, ValueError, UnicodeDecodeError, BundleError) as exc:
        raise ProjectError(f"Cannot import project bundle: {exc}") from exc


class EmailProjectRequest(OpenRequest):
    request_id: UUID
    recipients: str = Field(min_length=3, max_length=2000)
    body: str = Field(default="", max_length=10_000)
    mode: Literal["project", "pdf", "pdf_tex"] = "project"
    paper_id: str | None = Field(default=None, max_length=100)


@app.post("/api/projects/email")
def email_project_view(body: EmailProjectRequest, request: Request):
    """Mail an importable project and optional paper via the shared mail transport."""
    cfg = cloud_auth.config()
    allowed = {"http://127.0.0.1:5173", "http://localhost:5173"}
    if cfg.origin:
        allowed.add(cfg.origin)
    if (
        request.headers.get("origin") not in allowed
        or request.headers.get("content-type", "").split(";")[0] != "application/json"
    ):
        raise HTTPException(403, "Project email requires the SIGMA browser origin and JSON.")
    principal = cloud_auth.current_principal()
    if cfg.enabled and (principal is None or principal.role == "guest"):
        raise HTTPException(403, "Member access is required to email a project.")
    from sigma.project_email import (
        MailDeliveryNotSent,
        MailDispatchConflict,
        MailRateLimit,
        send_project_email,
    )

    try:
        count = send_project_email(
            body.path, body.recipients, body.body, body.mode, body.paper_id, str(body.request_id)
        )
    except MailRateLimit as exc:
        raise HTTPException(429, str(exc)) from exc
    except MailDispatchConflict as exc:
        raise HTTPException(409, str(exc)) from exc
    except MailDeliveryNotSent as exc:
        raise HTTPException(503, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(
            503, "Project email could not be delivered. Check email configuration or retry."
        ) from exc
    return {"sent": count}


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
    view = create_strategy(body.path, body.title, body.approach, body.summary, provenance)
    project_collaboration.note_artifact_author(
        body.path, "strategy", view.project.strategies[-1].id
    )
    return asdict(view)


class RemoveStrategyRequest(OpenRequest):
    strategy_id: str


@app.post("/api/projects/strategies/remove")
def remove_strategy_view(body: RemoveStrategyRequest):
    view = remove_strategy(body.path, body.strategy_id)
    project_collaboration.note_artifact_author(body.path, "strategy", body.strategy_id)
    return asdict(view)


class EditStrategyRequest(StrategyRequest):
    strategy_id: str


@app.post("/api/projects/strategies/edit")
def edit_strategy_view(body: EditStrategyRequest):
    view = edit_strategy(body.path, body.strategy_id, body.title, body.approach)
    project_collaboration.note_artifact_author(body.path, "strategy", body.strategy_id)
    return asdict(view)


class StrategyEnabledRequest(OpenRequest):
    model_config = ConfigDict(extra="forbid", strict=True)
    strategy_id: str
    enabled: bool


@app.post("/api/projects/strategies/enabled")
def strategy_enabled_view(body: StrategyEnabledRequest):
    view = set_strategy_enabled(body.path, body.strategy_id, body.enabled)
    project_collaboration.note_artifact_author(body.path, "strategy", body.strategy_id)
    return asdict(view)


class CreateProjectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str
    problem: str
    desired_outcomes: str = ""
    paper_requirements: str = ""
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


def _limit_anonymous_demo_projects() -> None:
    """Bound anonymous server-side storage before allocating another copy.

    This does not grant an identity, sharing, execution or provider entitlement.
    Guests can export their private temporary work before expiry.
    """
    workspace = cloud_workspaces.current()
    if workspace is None or not workspace.guest:
        return

    # Only server-managed temporary roots can be used here; reject forged
    # project names or attempts to select an external destination.
    root = workspace.path
    count = sum(
        1
        for item in root.iterdir()
        if not item.is_symlink()
        and (
            (item.is_dir() and item.suffix == ".sigma")
            or (item.is_file() and item.suffix == ".json" and not item.name.startswith("."))
        )
    )
    if count >= 12:
        raise HTTPException(
            429,
            "Guest preview limit: 12 projects. Export or remove one to continue.",
        )


@app.post("/api/projects/create", status_code=201)
def create_project_view(body: CreateProjectRequest):
    _limit_anonymous_demo_projects()
    if (
        body.investigation_type != "default"
        and project_types.get_type(body.investigation_type) is None
    ):
        raise ProjectError("Choose a currently available project type")
    # Only type and difficulty are project configuration. Legacy model/Outcome
    # columns remain for schema compatibility but are never taken from imports
    # or from the previous project's settings when creating new projects.
    from sigma import global_research_settings, project_collaboration

    user = global_research_settings.load_config()
    view = create_project(
        body.title,
        body.problem,
        body.investigation_type,
        user["ai_model"],
        user["reasoning_effort"],
        body.difficulty,
        user["show_advanced_outcome_details"],
        body.desired_outcomes,
        body.paper_requirements,
    )
    project_collaboration.register_owner(view)
    return asdict(view)


class SaveProjectAsRequest(OpenRequest):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=200)


@app.post("/api/projects/save-as", status_code=201)
def save_project_as_view(body: SaveProjectAsRequest):
    _limit_anonymous_demo_projects()
    return asdict(save_project_as(body.path, body.title))


class StageRequest(RemoveStrategyRequest):
    stage: str


class ReorderRequest(OpenRequest):
    order: list[str]
    expected_order: list[str]


@app.post("/api/projects/strategies/stage")
def stage_view(body: StageRequest):
    view = change_stage(body.path, body.strategy_id, body.stage)
    project_collaboration.note_artifact_author(body.path, "strategy", body.strategy_id)
    return asdict(view)


@app.post("/api/projects/strategies/reorder")
def reorder_view(body: ReorderRequest):
    view = reorder_strategies(body.path, body.order, body.expected_order)
    previous_positions = {
        strategy_id: index for index, strategy_id in enumerate(body.expected_order)
    }
    for index, strategy_id in enumerate(body.order):
        if previous_positions.get(strategy_id) != index:
            project_collaboration.note_artifact_author(body.path, "strategy", strategy_id)
    return asdict(view)


class ProposalRequest(OpenRequest):
    seed: str = ""
    expected_binding: str | None = None
    expected_mode: str | None = None
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


@app.post("/api/projects/strategy-inference")
async def strategy_inference_view(body: ProposalRequest):
    if not body.expected_binding or not body.expected_mode or not body.expected_project_id:
        raise ProjectError(
            "Inference requires the current AI account and project identity; reopen the project and retry."
        )
    await require_cloud_inference_binding(
        body.expected_binding, body.expected_project_id, body.path
    )
    credential = await auth_context()
    if body.expected_binding != credential["identity"] or body.expected_mode != credential["mode"]:
        raise ProjectError(
            "AI account or billing mode changed. Review the current connection and retry; no request was sent."
        )
    if body.request_id is None:
        raise ProjectError("Inference request identifier is required; no request was sent.")
    request_id = str(body.request_id)
    action, record = proposals.begin_inference(
        body.path,
        body.expected_project_id,
        request_id,
        body.expected_binding,
        body.expected_mode,
    )
    if action == "return":
        current = proposals.inference_status(body.path, body.expected_project_id, request_id)
        return {**current, "inference_status": current["status"]}
    if action == "uncertain":
        raise ProjectError(
            "This inference request may already have reached the provider. It will not be sent again; refresh the project to check persisted strategies."
        )
    if action == "in_progress":
        raise ProjectError(
            "This inference request is already being processed; it was not sent again."
        )
    if action == "commit":
        return proposals.commit_inference_candidate(body.path, request_id, record)
    task = asyncio.create_task(
        generate_proposal(
            body.path,
            expected_binding=body.expected_binding,
            expected_mode=body.expected_mode,
            expected_project_id=body.expected_project_id,
            infer_strategy=True,
            request_id=request_id,
            inference_owner=record["owner"],
        )
    )
    memory_guard.track_task(task)
    try:
        register_request(request_id, task)
    except ProjectError:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        raise
    try:
        try:
            await task
            current = proposals.inference_status(body.path, body.expected_project_id, request_id)
            if current.get("status") in {"completed", "no_strategy"}:
                return {**current, "inference_status": current["status"]}
            return current
        except asyncio.CancelledError:
            proposals.fail_inference(body.path, request_id, record["owner"], uncertain=True)
            pressure = memory_guard.is_critical()
            return JSONResponse(
                {
                    "error": memory_guard.MESSAGE
                    if pressure
                    else "Cancellation was requested. The provider outcome may be uncertain; this request will not be repeated.",
                    "inference_status": proposals.inference_status(
                        body.path, body.expected_project_id, request_id
                    )["status"],
                },
                status_code=503 if pressure else 409,
            )
        except Exception:
            proposals.fail_inference(body.path, request_id, record["owner"], uncertain=True)
            raise
    finally:
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        unregister_request(request_id, task)


class ProposalCancelRequest(BaseModel):
    request_id: UUID
    path: str
    expected_project_id: str
    expected_binding: str


@app.get("/api/projects/proposals/config")
async def proposal_config(path: str | None = None, purpose: str | None = None):
    principal = cloud_auth.current_principal()
    if principal is not None and principal.role == "guest":
        view = inspect_project(path) if path else None
        return {
            "provider": "unavailable",
            "mode": "guest",
            "binding": "guest",
            "project_id": view.project.id if view else None,
            "model": view.project.ai_model if view else None,
            "reasoning_effort": view.project.reasoning_effort if view else None,
            "available": False,
            "message": "Sign in as a member to use AI features.",
            "connection": {"status": "unavailable", "guidance": "Member access is required."},
        }
    if purpose is not None and purpose != "markdown":
        raise ProjectError("Unknown proposal configuration purpose")
    if purpose == "markdown":
        from sigma.text_conversion import FORMAT_EFFORT, FORMAT_MODEL

        return await configuration(path, frozen_model=FORMAT_MODEL, frozen_effort=FORMAT_EFFORT)
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
    memory_guard.track_task(task)
    connection = asyncio.create_task(disconnected())
    try:
        done, _ = await asyncio.wait({task, connection}, return_when=asyncio.FIRST_COMPLETED)
        if connection in done:
            return JSONResponse(
                {"error": "Proposal request cancelled; no proposal was added"}, status_code=499
            )
        try:
            return await task
        except asyncio.CancelledError:
            if memory_guard.is_critical():
                return JSONResponse({"error": memory_guard.MESSAGE}, status_code=503)
            return JSONResponse(
                {"error": "Proposal request cancelled; no proposal was added"}, status_code=499
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
    await require_cloud_inference_binding(
        body.expected_binding, body.expected_project_id, body.path
    )
    credential = await auth_context()
    if credential["identity"] != body.expected_binding:
        raise ProjectError(
            "AI account changed; reopen the connection before checking cancellation status."
        )
    return await proposals.cancel_inference(
        body.path, body.expected_project_id, str(body.request_id)
    )


@app.get("/api/projects/strategy-inference/status")
async def strategy_inference_status(
    path: str, expected_project_id: str, expected_binding: str, request_id: UUID
):
    await require_cloud_inference_binding(expected_binding, expected_project_id, path)
    credential = await auth_context()
    if credential["identity"] != expected_binding:
        raise ProjectError(
            "AI account changed; reopen the connection before checking inference status."
        )
    return proposals.inference_status(path, expected_project_id, str(request_id))


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
    qa_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{32}$")
    strategy_id: str | None = None
    session_id: str | None = Field(default=None, max_length=36)
    field_path: str | None = Field(default=None, max_length=160)
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
            body.field_path,
            body.qa_id,
        )
    )
    memory_guard.track_task(task)
    connection = asyncio.create_task(disconnected())
    try:
        done, _ = await asyncio.wait({task, connection}, return_when=asyncio.FIRST_COMPLETED)
        if connection in done:
            return JSONResponse(
                {"error": "Conversion cancelled; source text was kept"}, status_code=499
            )
        try:
            return await task
        except asyncio.CancelledError:
            if memory_guard.is_critical():
                return JSONResponse({"error": memory_guard.MESSAGE}, status_code=503)
            raise
    finally:
        for pending in (task, connection):
            if not pending.done():
                pending.cancel()
        await asyncio.gather(task, connection, return_exceptions=True)


class ProjectSettingsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str
    problem: str
    desired_outcomes: str | None = None
    paper_requirements: str | None = None
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
    expected_revision: int | None = Field(default=None, ge=0)
    collaborators: list[str] | None = None


class DeleteProjectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: str = Field(min_length=1, max_length=4096)
    expected_project_id: str = Field(min_length=1, max_length=100)


async def _delete_project_unleased(body: DeleteProjectRequest):
    """Stop project executions before removing the saved project data."""
    import shutil

    from sigma import project_collaboration
    from sigma.projects import project_path, projects_root

    authorized = project_path(body.path)
    root = projects_root().resolve(strict=True)
    try:
        if authorized == root or not authorized.is_relative_to(root):
            raise ProjectError("Project is outside the permitted projects directory")
        view = inspect_project(str(authorized))
        if view.project.id != body.expected_project_id:
            raise ProjectError("Project changed; refresh before deleting it")
        # Admission holds the same manager lock until its worker is published.
        # Keep it across deletion; prove every saved session's original worker
        # has exited before removing its project, including foreign-process
        # workers whose local task is invisible in this process.
        from contextlib import ExitStack

        with research_sessions._project_manager_lock(str(authorized)):
            view = inspect_project(str(authorized))
            if view.project.id != body.expected_project_id:
                raise ProjectError("Project changed; refresh before deleting it")
            await research_sessions.stop_project_sessions(str(authorized))
            with ExitStack() as worker_fences:
                for session in research_sessions._all(str(authorized)):
                    worker_fences.enter_context(
                        research_sessions._idle_worker_lock(str(authorized), session["id"])
                    )
                await asyncio.to_thread(
                    session_log.delete_project, body.expected_project_id, authorized
                )
                with project_collaboration.finalize_deletion(str(authorized), view.project.title):
                    if authorized.suffix == ".json":
                        authorized.unlink()
                    elif authorized.suffix == ".sigma" and authorized.is_dir():
                        shutil.rmtree(authorized)
                    else:
                        raise ProjectError("Unsupported project storage format")
        from sigma.recents import forget_recent

        forget_recent(body.expected_project_id, str(authorized))
        return {"deleted": True, "project_id": body.expected_project_id}
    except ProjectError:
        # Preserve actionable concurrency refusal rather than masking it as
        # an unexplained project deletion error.
        raise
    except (OSError, RuntimeError, ValueError) as exc:
        raise ProjectError("Project could not be deleted safely") from exc


@app.delete("/api/projects")
async def delete_project_view(body: DeleteProjectRequest):
    """Fence owner deletion against all research and paper execution."""
    from sigma import project_collaboration
    from sigma.projects import project_path, projects_root

    authorized = project_path(body.path)
    root = projects_root().resolve(strict=True)
    if authorized == root or not authorized.is_relative_to(root):
        raise ProjectError("Project is outside the permitted projects directory")
    lease = project_collaboration.acquire_lease(str(authorized), "Project deletion")
    try:
        with (
            project_collaboration.bind_lease(str(authorized), lease),
            project_collaboration.keep_lease(str(authorized), lease),
        ):
            return await _delete_project_unleased(body)
    finally:
        project_collaboration.release_lease(str(authorized), lease)


@app.post("/api/projects/description")
def update_project_description_view(body: UpdateProjectRequest):
    """Edit authored project text independently of long-running frozen research.

    The supplied prior project settings are checked atomically against the
    document under its short file mutex. Operational revision changes alone
    cannot cancel or reject a human's text edit.
    """
    from sigma import project_collaboration

    current_view = inspect_project(body.path)
    project_collaboration.register_owner(current_view)
    current = current_view.project
    if (
        body.investigation_type != current.investigation_type
        or body.difficulty != current.difficulty
    ):
        raise ProjectError("This editor changes only project title and research text.")
    view = update_project(
        body.path,
        body.title,
        body.problem,
        body.investigation_type,
        body.ai_model,
        body.reasoning_effort,
        body.expected.model_dump(exclude_none=True),
        difficulty=body.difficulty,
        desired_outcomes=body.desired_outcomes,
        paper_requirements=body.paper_requirements,
        semantic_update=True,
    )
    return asdict(view)


@app.post("/api/projects/update")
def update_project_view(body: UpdateProjectRequest):
    from sigma import project_collaboration

    workspace = cloud_workspaces.current()
    if (
        workspace is not None
        and workspace.guest
        and (body.collaborators is not None or body.expected_revision is not None)
    ):
        raise HTTPException(
            403, "Temporary guest projects cannot be shared or invite collaborators."
        )

    current_view = inspect_project(body.path)
    project_collaboration.register_owner(current_view)
    current = current_view.project
    if (
        body.investigation_type != current.investigation_type
        and body.investigation_type != "default"
        and project_types.get_type(body.investigation_type) is None
    ):
        raise ProjectError("Choose a currently available project type")
    view = update_project(
        body.path,
        body.title,
        body.problem,
        body.investigation_type,
        body.ai_model,
        body.reasoning_effort,
        body.expected.model_dump(exclude_none=True),
        difficulty=body.difficulty,
        show_advanced_outcome_details=body.show_advanced_outcome_details,
        desired_outcomes=body.desired_outcomes,
        paper_requirements=body.paper_requirements,
        expected_revision=body.expected_revision,
        collaborators=body.collaborators,
    )
    # Collaboration notices were committed to the durable outbox by Save.
    # The mail worker sends them without blocking or invalidating this response.
    return asdict(view)


def connection_view_state(state: dict[str, Any], request: Request) -> dict[str, Any]:
    principal = getattr(request.state, "cloud_principal", None)
    if isinstance(principal, cloud_auth.Principal) and principal.role != "admin":
        try:
            sponsored_selected = (
                cloud_auth.model_access_for_subject(principal.subject) == "sponsored"
            )
        except (OSError, RuntimeError, sqlite3.Error):
            sponsored_selected = True  # Fail closed for sponsor identity disclosure.
        if sponsored_selected:
            state = {key: value for key, value in state.items() if key != "account_label"}
    return state


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
    return connection_view_state(state, request)


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
    # This route always operates on the authenticated user's personal store.
    # Sponsor maintenance has its own admin-only endpoint; email equality does
    # not change credential ownership or OAuth intent.
    return await chatgpt_auth.begin(body.account_id, body.enable_plan, body.retry_attempt_id)


@app.get("/api/ai/auth/callback/{identifier}")
async def hosted_chatgpt_callback(identifier: str, request: Request):
    """Public OAuth return; validation and credential exchange stay server-side."""
    if cloud_auth.config().local or not cloud_workspaces.enabled():
        raise HTTPException(404, "Hosted callback unavailable.")
    try:
        await chatgpt_auth.hosted_callback(identifier, request.url.query)
    except (ProjectError, OSError, TimeoutError):
        raise HTTPException(400, "ChatGPT sign-in attempt expired or failed.") from None
    return Response(
        "Return to SIGMA to continue. You can close this sign-in tab.",
        media_type="text/plain",
        headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"},
    )


@app.post("/api/ai/sponsor-auth/begin")
async def sponsor_auth_begin(request: Request):
    """Allow only a verified Google administrator to renew sponsor credentials."""
    principal = getattr(request.state, "cloud_principal", None)
    if not isinstance(principal, cloud_auth.Principal) or principal.subject.startswith("mock:"):
        raise HTTPException(403, "Authenticated sponsor administrator required.")
    if principal.role != "admin":
        raise HTTPException(403, "Designated sponsor administrator required.")
    from sigma.cloud_sponsor import expected_email, sponsor_account_id

    try:
        expected_email()
    except ProjectError as exc:
        raise HTTPException(503, str(exc)) from exc
    try:
        account_id = await sponsor_account_id()
    except ProjectError:
        account_id = None
    try:
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
    try:
        target = chatgpt_auth.authorization_url(identifier)
    except ProjectError:
        # A browser navigation must not expose a raw JSON API error. This can
        # happen when a sign-in tab is reused, the Google session expires, or
        # an OAuth attempt has already been consumed. No provider URL is issued.
        return HTMLResponse(
            """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ChatGPT connection could not start · SIGMA</title>
<style>
body{font:16px system-ui,sans-serif;line-height:1.6;max-width:38rem;margin:12vh auto;
padding:0 1.5rem;color:#ddd;background:#171b20}
h1{font-size:1.5rem;font-weight:600}p{color:#bdc5ce}
</style></head><body><main><h1>ChatGPT sign-in needs to be restarted</h1>
<p>This authorization link is no longer active for this SIGMA window.
Close this tab and start a new connection from the original SIGMA window.
Your saved research is unchanged.</p></main></body></html>""",
            status_code=400,
            headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"},
        )
    return RedirectResponse(
        target,
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
        if body.mode == "sponsored" and not cloud_auth.sponsored_access_enabled():
            raise HTTPException(403, "Sponsored access is disabled.")
        try:
            cloud_auth.set_model_access(principal.subject, body.mode)
        except PermissionError as exc:
            raise HTTPException(403, "This account cannot select sponsored access.") from exc
        except (OSError, RuntimeError, ValueError) as exc:
            raise HTTPException(503, "Connection choice could not be saved.") from exc
        return connection_view_state(await connection(refresh=True), request)
    if cfg.enabled and not cfg.local:
        if not isinstance(principal, cloud_auth.Principal):
            raise HTTPException(401, "Authentication required.")
        if body.mode not in {"personal", "sponsored"} or body.account_id is not None:
            raise HTTPException(422, "Choose personal or sponsored access.")
        if body.mode == "sponsored" and not cloud_auth.sponsored_access_enabled():
            raise HTTPException(403, "Sponsored access is disabled.")
        try:
            cloud_auth.set_model_access(principal.subject, body.mode)
        except PermissionError as exc:
            raise HTTPException(403, "This account cannot select sponsored access.") from exc
        except (OSError, RuntimeError, ValueError) as exc:
            raise HTTPException(503, "Connection choice could not be saved.") from exc
        return connection_view_state(await connection(refresh=True), request)
    await chatgpt_auth.select(body.mode, body.account_id)
    return connection_view_state(await connection(), request)


@app.post("/api/ai/disconnect")
async def auth_disconnect():
    if cloud_auth.config().local and cloud_auth.current_principal() is None:
        from sigma.ai_store import sponsor_transaction
        from sigma.cloud_sponsor import expected_email

        try:
            designated_sponsor_email = expected_email()
        except ProjectError:
            designated_sponsor_email = None
        if designated_sponsor_email:
            async with sponsor_transaction() as state:
                active = state["accounts"].get(state.get("active")) or {}
                if active.get("email", "").casefold() == designated_sponsor_email:
                    raise HTTPException(403, "The sponsor account cannot be disconnected here.")
    return await chatgpt_auth.disconnect()


@app.post("/api/ai/welcome")
async def auth_welcome():
    await chatgpt_auth.welcome_seen()
    return {"dismissed": True}


@app.get("/api/projects/recent")
def recent_view(response: Response, lightweight: bool = False):
    from sigma.recents import home_projects

    started = perf_counter()
    result = home_projects(lightweight=lightweight)
    # Chrome DevTools can now distinguish backend listing time from browser
    # rendering/network delay without logging sensitive project information.
    response.headers["Server-Timing"] = (
        f"saved-projects;dur={(perf_counter() - started) * 1000:.1f}"
    )
    return result


@app.get("/api/projects/recent/activity")
def recent_activity_view():
    """Activity is fetched after Home renders; never scan paper records."""
    from sigma.recents import recent_activity

    return recent_activity()


@app.get("/api/projects/pinned")
def pinned_paper_projects_view():
    """Per-workspace preferred projects for manual paper-generation testing."""
    from sigma.recents import pinned_projects

    return pinned_projects()


class ProjectPinRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_id: str
    path: str
    pinned: bool


@app.post("/api/projects/pin")
def pin_project_view(body: ProjectPinRequest):
    from sigma.recents import set_project_pin

    set_project_pin(body.project_id, body.path, body.pinned)
    return {"project_id": body.project_id, "pinned": body.pinned}


@app.post("/api/projects/recent/pin")
def pin_recent_project_view(body: ProjectPinRequest):
    """Compatibility route for the in-category Saved Projects pin UI."""
    return pin_project_view(body)


@app.get("/api/projects/samples/{sample_id}/top-paper/pdf")
def sample_top_paper_pdf_view(sample_id: str):
    from sigma.samples import top_sample_pdf

    return Response(
        top_sample_pdf(sample_id),
        media_type="application/pdf",
        headers={
            "Cache-Control": "no-store",
            "Content-Disposition": 'inline; filename="sigma-sample-paper.pdf"',
        },
    )


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

    _limit_anonymous_demo_projects()
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
