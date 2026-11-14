"""Prototype Personal ChatGPT companion API: no OpenAI token on the server."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from sigma import cloud_auth, personal_companion_bridge as bridge
from sigma.projects import ProjectError

router = APIRouter(prefix="/api/personal-companion")


class Redeem(BaseModel):
    code: str = Field(min_length=20, max_length=200)


class Heartbeat(BaseModel):
    ready: bool
    label: str = Field(max_length=200)


class TestPrompt(BaseModel):
    prompt: str = Field(min_length=1, max_length=4000)


class Complete(BaseModel):
    job_id: str = Field(min_length=1, max_length=200)
    result: str = Field(max_length=16000)
    model: str = Field(max_length=120)
    failed: bool = False


def _enabled() -> None:
    cfg = cloud_auth.config()
    if not bridge.enabled() or not cfg.enabled or cfg.error:
        raise HTTPException(404, "Personal companion prototype is disabled.")


def _owner(request: Request) -> str:
    _enabled()
    principal = getattr(request.state, "cloud_principal", None)
    if not isinstance(principal, cloud_auth.Principal) or principal.role == "guest":
        raise HTTPException(403, "Authorized SIGMA account required.")
    return principal.subject


def _personal(subject: str) -> None:
    try:
        if cloud_auth.model_access_for_subject(subject) != "personal":
            raise HTTPException(409, "Select Personal ChatGPT first.")
    except RuntimeError as exc:
        raise HTTPException(503, "Connection choice unavailable.") from exc


def _bearer(request: Request) -> str:
    _enabled()
    authorization = request.headers.get("authorization", "")
    if not authorization.startswith("Bearer ") or authorization.count(" ") != 1:
        raise HTTPException(401, "Companion pairing required.")
    return authorization[7:]


@router.post("/pair")
def pair(request: Request) -> dict[str, Any]:
    subject = _owner(request)
    _personal(subject)
    return bridge.start_pairing(subject)


@router.get("/status")
def status(request: Request) -> dict[str, Any]:
    subject = _owner(request)
    return {**bridge.status(subject),
            "selected_personal": cloud_auth.model_access_for_subject(subject) == "personal"}


@router.post("/test")
def test(request: Request, body: TestPrompt) -> dict[str, str]:
    subject = _owner(request)
    _personal(subject)
    try:
        return {"job_id": bridge.submit(subject, body.prompt)}
    except ProjectError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.get("/test/{job_id}")
def test_result(request: Request, job_id: str) -> dict[str, str]:
    subject = _owner(request)
    try:
        return bridge.result(subject, job_id)
    except ProjectError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.post("/worker/redeem")
def worker_redeem(body: Redeem) -> dict[str, str]:
    _enabled()
    try:
        return {"token": bridge.redeem(body.code)}
    except ProjectError as exc:
        raise HTTPException(403, str(exc)) from exc


@router.post("/worker/heartbeat")
def worker_heartbeat(request: Request, body: Heartbeat) -> dict[str, bool]:
    try:
        bridge.heartbeat(_bearer(request), ready=body.ready, label=body.label)
        return {"ok": True}
    except ProjectError as exc:
        raise HTTPException(403, str(exc)) from exc


@router.post("/worker/next")
def worker_next(request: Request) -> dict[str, Any]:
    try:
        return {"job": bridge.next_job(_bearer(request))}
    except ProjectError as exc:
        raise HTTPException(403, str(exc)) from exc


@router.post("/worker/complete")
def worker_complete(request: Request, body: Complete) -> dict[str, bool]:
    try:
        bridge.complete(_bearer(request), body.job_id, result=body.result,
                        model=body.model, failed=body.failed)
        return {"ok": True}
    except ProjectError as exc:
        raise HTTPException(403, str(exc)) from exc


@router.post("/worker/disconnect")
def worker_disconnect(request: Request) -> dict[str, bool]:
    try:
        bridge.disconnect(_bearer(request))
        return {"ok": True}
    except ProjectError as exc:
        raise HTTPException(403, str(exc)) from exc
