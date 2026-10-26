"""Isolated SIWC/OIDC server fixture. Never imported by the normal launcher."""

import os
import sys
from pathlib import Path
from tempfile import mkdtemp

import httpx
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tests"))
from siwc_fixture import Fixture

from sigma import chatgpt_auth as auth
from sigma import openai_connection as connection
from sigma.ai_store import transaction
from sigma.api import app

__all__ = ["app"]
os.environ["SIGMA_AUTH_HOME"] = mkdtemp(prefix="sigma-siwc-browser-auth-")
os.environ["SIGMA_STATE_DIR"] = mkdtemp(prefix="sigma-browser-recents-")
os.environ["SIGMA_PROJECTS_ROOT"] = mkdtemp(prefix="sigma-siwc-browser-projects-")
os.environ["OPENAI_API_KEY"] = "explicit-api-key-fixture"
os.environ.pop("SIGMA_AI_ENABLED", None)
fixture = Fixture()
real_client = httpx.AsyncClient
forced_status = None
last_input = None


def handler(request):
    global last_input
    if request.url.path == "/v1/models" and forced_status:
        return httpx.Response(forced_status, json={"detail": "controlled fixture unavailable"})
    if request.url.path == "/v1/responses":
        import json

        payload = json.loads(request.content)
        last_input = payload["input"]
    return fixture.handler(request)


def client(**kwargs):
    return real_client(transport=httpx.MockTransport(handler), **kwargs)


httpx.AsyncClient = client


class Authorization(BaseModel):
    url: str
    declined: bool = False


@app.post("/__fixture__/authorize")
def authorize(body: Authorization):
    return {
        "callback": fixture.authorize(body.url, error="access_denied" if body.declined else None)
    }


@app.get("/__fixture__/stats")
def stats():
    return {
        "generated": fixture.generated,
        "refreshed": fixture.refreshed,
        "last_input": last_input,
    }


class Control(BaseModel):
    state: str
    subject: str | None = None
    email: str | None = None


@app.post("/__fixture__/state")
async def control(body: Control):
    global forced_status
    forced_status = {"offline": 503, "limited": 429}.get(body.state)
    if body.subject is not None:
        fixture.subject = body.subject
    if body.email is not None:
        fixture.email = body.email
    fixture.claims_override = (
        {"nonce": "invalid-fixture-nonce"} if body.state == "invalid_id" else {}
    )
    fixture.refresh_error = None
    async with transaction() as stored:
        account = stored["accounts"].get(stored["active"])
        if account:
            if body.state == "not_permitted":
                account["scopes"] = [
                    scope for scope in account["scopes"] if scope != "chatgpt.tokens.use.direct"
                ]
            elif body.state == "expired":
                account["expires_at"] = account["earliest_refresh_at"] = 0
                fixture.refresh_error = "invalid_grant"
            elif body.state == "connected":
                account["scopes"] = auth.SCOPES.split()
    connection._cached, connection._identity, connection._known = None, "", set()
    connection._pending = None
    return {"controlled": True}
