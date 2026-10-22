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

os.environ["SIGMA_STATE_DIR"] = mkdtemp(prefix="sigma-browser-recents-")
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
    if body["text"]["format"]["name"] == "text_conversion":
        await asyncio.sleep(0.25)
        source = context["text"]
        if context["target_format"] == "markdown":
            converted = (
                source.replace("a_n/F_{n+2}", "@@RATIO@@")
                .replace("n >= 0", r"$n \ge 0$")
                .replace("a_12", "$a_{12}$")
                .replace("a_n", "$a_n$")
                .replace("F_0", "$F_0$")
                .replace("F_1", "$F_1$")
                .replace("@@RATIO@@", r"$\frac{a_n}{F_{n+2}}$")
            )
        else:
            converted = source.replace(r"$\frac{a_n}{F_{n+2}}$", "a_n/F_{n+2}")
            converted = converted.replace(r"$n \ge 0$", "n >= 0").replace("$a_n$", "a_n")
            converted = (
                converted.replace("$a_{12}$", "a_12")
                .replace("$F_0$", "F_0")
                .replace("$F_1$", "F_1")
            )
        return httpx.Response(
            200,
            json={
                "status": "completed",
                "model": body["model"],
                "output": [
                    {
                        "type": "message",
                        "content": [
                            {
                                "type": "output_text",
                                "text": json.dumps({"body": converted, "warnings": []}),
                            }
                        ],
                    }
                ],
            },
        )
    agentic = (
        body["text"]["format"]["name"].startswith("strategy_")
        and body["text"]["format"]["name"] != "strategy_proposal"
    )
    seed = (context["investigation"] if agentic else context)["starting_point"]
    if seed == "timeout-fixture":
        await asyncio.sleep(2)
    if seed == "error-fixture":
        return httpx.Response(500)
    if agentic:
        await asyncio.sleep(0.15)
    draft = {
        "title": "Moment matrix obstruction",
        "summary": "Check finite moment matrices for a necessary positivity obstruction.",
        "approach": "Construct a parameterized moment matrix without assuming positivity is sufficient. Check domain and convergence before interchanging integrals.",
        "first_tests": "Compute small principal minors on independently verified samples.",
        "assumptions": "Justify convergence and distinguish finite checks from a universal bound.",
        "failure_modes": "Necessary inequalities may be too weak; sampled positivity does not prove the conjecture.",
    }
    counting = agentic and context["investigation"]["research_problem"].startswith(
        "For each integer n >= 0"
    )
    previous = context["investigation"]["existing_strategies"] if counting else []
    if counting:
        if previous:
            draft = {
                "title": "Position-shift subset count",
                "summary": "Count strings by a bijection from nonadjacent one positions to subsets.",
                "approach": "Fix k ones at increasing positions i_1,...,i_k. Shift position i_j to i_j-(j-1), yielding a k-subset of {1,...,n-k+1}; sum the resulting binomial counts over k.",
                "first_tests": "Enumerate n=0,1,2,5,10 and compare to 1,2,3,13,144; finite agreement is not a proof.",
                "assumptions": "Positions are one-indexed and k ranges from zero through the largest feasible count.",
                "failure_modes": "An incorrect inverse or boundary range would overcount strings.",
            }
        else:
            draft = {
                "title": "Terminal-symbol recurrence",
                "summary": "Partition valid strings by their final symbol to derive a recurrence.",
                "approach": "Separate length-n valid strings ending in 0 from those ending in 1. An ending 1 forces a preceding 0, relating the two disjoint classes to shorter strings.",
                "first_tests": "Enumerate n=0,1,2,5,10 and compare to 1,2,3,13,144; finite agreement is not a proof.",
                "assumptions": "The empty string counts and n below two needs explicit initial conditions.",
                "failure_modes": "Missing the forced predecessor or mishandling n=0 invalidates the recurrence.",
            }
    if agentic and body["text"]["format"]["name"] == "strategy_challenge":
        draft = {
            "assessment": "distinct",
            "public_summary": "The proposed mechanism is distinct; its proof obligations remain open.",
            "mechanism_comparison": "The candidate uses a different counting mechanism from prior strategies."
            if counting and previous
            else "No earlier strategy uses this mechanism."
            if counting
            else "The candidate uses moment constraints rather than an existing strategy mechanism.",
            "objections": [
                "Prove the mapping and all boundary cases."
                if counting
                else "Finite positivity is necessary, not a proof of the full claim."
            ],
            "missing_obligations": "Prove the partition or bijection is reversible and exhaustive."
            if counting
            else "Justify convergence and show exactly what the necessary inequalities imply.",
            "revision_needed": False,
        }
    elif agentic:
        draft = {
            **draft,
            "mechanism": "A position-shift bijection converts the spacing condition into an ordinary subset count."
            if counting and previous
            else "A disjoint terminal-symbol partition maps both classes to shorter valid strings."
            if counting
            else "A parameterized moment matrix yields necessary positivity constraints that might expose an obstruction.",
            "evidence_boundary": "A proof of the bijection or recurrence remains necessary; finite counts are only checks."
            if counting
            else "Finite minor computations are checks only; the general inequality remains unproved.",
        }
    return httpx.Response(
        200,
        json={
            "status": "completed",
            "model": body["model"] if agentic else "gpt-4.1-TEST-FIXTURE",
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
