"""Isolated browser-test provider fixture; no network or real credentials."""

import asyncio
import json
import os
from contextlib import asynccontextmanager
from tempfile import mkdtemp

import httpx

from sigma import proposals
from sigma.api import app

__all__ = ["app"]

os.environ["SIGMA_PROJECTS_ROOT"] = mkdtemp(prefix="sigma-browser-managed-")
os.environ["SIGMA_AUTH_HOME"] = mkdtemp(prefix="sigma-browser-api-auth-")
os.environ["OPENAI_API_KEY"] = "explicit-browser-test-fixture"
os.environ["SIGMA_AI_MODEL"] = "gpt-4.1"
real_client = httpx.AsyncClient


async def handler(request):
    if request.method == "GET":
        return httpx.Response(
            200,
            json={
                "object": "list",
                "data": [
                    {"id": "gpt-6.1-sol"},
                    {"id": "gpt-6-luna"},
                    {"id": "gpt-6-astra"},
                    {"id": "unreviewed-embedding-model"},
                ],
            },
        )
    body = json.loads(request.content)
    context = json.loads(body["input"])
    seed = context["starting_point"]
    if seed == "timeout-fixture":
        await asyncio.sleep(20)
    if seed == "error-fixture":
        return httpx.Response(500)
    draft = {
        "title": "Moment matrix obstruction",
        "summary": "Check finite moment matrices for a necessary positivity obstruction.",
        "approach": "Construct a parameterized moment matrix without assuming positivity is sufficient. Check domain and convergence before interchanging integrals.",
        "first_tests": "Compute small principal minors on independently verified samples.",
        "assumptions": "Justify convergence and distinguish finite checks from a universal bound.",
        "failure_modes": "Necessary inequalities may be too weak; sampled positivity does not prove the conjecture.",
    }
    return httpx.Response(
        200,
        json={
            "status": "completed",
            "model": "gpt-4.1-TEST-FIXTURE",
            "output": [
                {"type": "message", "content": [{"type": "output_text", "text": json.dumps(draft)}]}
            ],
        },
    )


def client(**kwargs):
    return real_client(transport=httpx.MockTransport(handler), **kwargs)


proposals.httpx.AsyncClient = client


@asynccontextmanager
async def select_fixture_billing(app):
    from sigma.chatgpt_auth import select

    await select("api_key")
    yield


app.router.lifespan_context = select_fixture_billing
