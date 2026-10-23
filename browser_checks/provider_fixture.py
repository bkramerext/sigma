"""Isolated browser-test provider fixture; no network or real credentials."""

import asyncio
import json
import os
from contextlib import asynccontextmanager
from tempfile import mkdtemp

import httpx

os.environ["SIGMA_STATE_DIR"] = mkdtemp(prefix="sigma-browser-recents-")
os.environ["SIGMA_PROJECTS_ROOT"] = mkdtemp(prefix="sigma-browser-managed-")
os.environ["SIGMA_AUTH_HOME"] = mkdtemp(prefix="sigma-browser-api-auth-")
os.environ["OPENAI_API_KEY"] = "explicit-browser-test-fixture"
os.environ["SIGMA_AI_MODEL"] = "gpt-4.1"

from sigma import proposals
from sigma.api import app

__all__ = ["app"]
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
    if body["text"]["format"]["name"] in {"research_investigator", "research_skeptic"}:
        strategy_title = context.get("strategy", {}).get("title")
        if strategy_title == "Failure fixture strategy":
            return httpx.Response(500)
        if strategy_title == "Pause and stop fixture strategy":
            await asyncio.sleep(2)
        cycle = context["cycle"]
        maximum_regions = "maximum number of regions" in context.get("problem", "").lower()
        if body["text"]["format"]["name"] == "research_investigator":
            result = (
                {
                    "claim": "The maximum is R(n) = 1 + n(n+1)/2 for every n >= 0.",
                    "method": "Each region is a nonempty intersection of open half-planes with one chosen side of each line, hence convex and connected; different pieces of an inserted line lie in different old regions. Insert lines one at a time. The kth line has at most k-1 distinct intersections and is split into at most k pieces, each increasing the region count by at most one. The lines y=kx+k^2 have pairwise distinct intersections along each newly added line, so each of its k pieces lies in a distinct convex prior region and attains the bound. For n=0 there is one region.",
                    "assumptions": ["Lines are distinct straight lines in the Euclidean plane."],
                    "evidence_status": "Complete unverified mathematical argument; no proof checker was run.",
                    "open_obligations": [],
                }
                if maximum_regions
                else {
                    "claim": f"Fixture claim {cycle}: a candidate consequence follows from the saved strategy.",
                    "method": f"Use the stated mechanism to derive consequence {cycle}.",
                    "assumptions": [f"Fixture assumption {cycle}"],
                    "evidence_status": "Unverified model derivation; no tool was run.",
                    "open_obligations": [f"Check obligation {cycle}"],
                }
            )
        else:
            result = (
                {
                    "assessment": "stop",
                    "stop_reason": "productive_conclusion",
                    "response": "The upper bound and explicit general-position construction establish the objective for all n, including n=0. In particular, $R(n)=1+n(n+1)/2$ and $$R(0)=1$$. The candidate argument is complete but remains unverified.",
                    "objections": [],
                    "remaining_obligations": [],
                    "next_question": "",
                    "objective_status": "achieved",
                    "solution_claim": "$R(n) = 1 + n(n+1)/2$ for all $n \\ge 0$.",
                    "argument_summary": "The kth line adds at most k regions; y=kx+k^2 attains k at every step; sum from k=1 to n and include the empty arrangement.",
                    "assumptions_reviewed": ["The lines are distinct straight Euclidean lines."],
                    "proof_obligations": [
                        "Prove the per-line upper bound.",
                        "Show one arrangement attains every increment.",
                        "Handle n=0.",
                    ],
                    "unresolved_objections": [],
                    "supporting_cycles": [1],
                    "verification_status": "convincing_unverified",
                    "strategy_contribution": "solution",
                    "contribution_rationale": "This strategy supplies both the upper-bound induction and an explicit arrangement attaining equality.",
                }
                if maximum_regions
                else {
                    "assessment": "revise" if cycle == 1 else "continue",
                    "stop_reason": "recoverable_objection",
                    "response": f"Independent fixture review for cycle {cycle}.",
                    "objections": [f"Check boundary case {cycle}"],
                    "remaining_obligations": [f"Resolve obligation {cycle}"],
                    "next_question": f"Study the distinct consequence for cycle {cycle + 1}.",
                    "objective_status": "partial",
                    "solution_claim": "A partial consequence follows from the saved work.",
                    "argument_summary": "The result uses the stated mechanism but does not settle the objective.",
                    "assumptions_reviewed": [f"Fixture assumption {cycle}"],
                    "proof_obligations": [f"Resolve obligation {cycle}"],
                    "unresolved_objections": [],
                    "supporting_cycles": list(range(1, cycle + 1)),
                    "verification_status": "convincing_unverified",
                    "strategy_contribution": "productive",
                    "contribution_rationale": "The saved derivation advances the objective.",
                }
            )
        return httpx.Response(
            200,
            json={
                "status": "completed",
                "model": body["model"],
                "output": [
                    {
                        "type": "message",
                        "content": [{"type": "output_text", "text": json.dumps(result)}],
                    }
                ],
            },
        )
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
    seed = (context["project"] if agentic else context)["starting_point"]
    if seed == "timeout-fixture":
        await asyncio.sleep(2)
    if agentic and seed == "delay-fixture":
        await asyncio.sleep(3)
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
    project_context = context.get("project", context)
    counting = project_context["research_problem"].startswith("For each integer n >= 0")
    regions = "maximum number of regions into which" in project_context["research_problem"]
    previous = project_context["existing_strategies"] if counting else []
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
    if regions:
        draft = {
            "title": "Planar graph Euler count",
            "summary": "Count arrangement regions from vertices and edges of a planar graph.",
            "approach": "Choose a disk containing every line intersection and truncate each line at its boundary. In a maximizing arrangement every pair intersects at a distinct vertex and no three lines concur. Count the connected planar graph's vertices and edges, including the disk boundary, then apply Euler's formula to obtain the number of interior faces. For arbitrary placements, repeated or missing pairwise intersections reduce the vertex contribution and cannot increase the face count.",
            "first_tests": "Check n=0,1,2,3 against 1,2,4,7; these cases are checks, not a general proof.",
            "assumptions": "The disk boundary meets each line in two points and contains all pairwise intersections; general position means no parallel pair and no triple intersection.",
            "failure_modes": "Miscounting boundary edges or confusing the exterior face with a region changes the Euler calculation.",
        }
    if agentic and body["text"]["format"]["name"] == "strategy_challenge":
        if regions:
            draft = {
                "assessment": "distinct",
                "public_summary": "The Euler count offers a distinct route; its graph counts and upper-bound argument need a careful derivation.",
                "mechanism_comparison": "The saved baseline adds lines and counts new segments; this candidate encodes the arrangement as a planar graph and counts faces with Euler's formula.",
                "objections": [
                    "State precisely why each non-general-position coincidence cannot increase the face count."
                ],
                "missing_obligations": "Derive the vertex and edge counts, account for the exterior face, and justify the upper bound for arbitrary arrangements.",
                "revision_needed": False,
            }
        else:
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
            "mechanism": "Euler's formula turns the line arrangement into a planar face count."
            if regions
            else "A position-shift bijection converts the spacing condition into an ordinary subset count."
            if counting and previous
            else "A disjoint terminal-symbol partition maps both classes to shorter valid strings."
            if counting
            else "A parameterized moment matrix yields necessary positivity constraints that might expose an obstruction.",
            "evidence_boundary": "A proof of the bijection or recurrence remains necessary; finite counts are only checks."
            if counting
            else "Finite minor computations are checks only; the general inequality remains unproved.",
        }
    if counting and not agentic:
        draft = {
            "title": "Terminal-symbol recurrence",
            "summary": "Partition valid strings by their final symbol to derive a recurrence.",
            "approach": "Separate length-n valid strings ending in 0 from those ending in 1. An ending 1 forces a preceding 0, relating the two disjoint classes to shorter strings.",
            "first_tests": "Enumerate n=0,1,2,5,10 and compare to 1,2,3,13,144; finite agreement is not a proof.",
            "assumptions": "The empty string counts and n below two needs explicit initial conditions.",
            "failure_modes": "Missing the forced predecessor or mishandling n=0 invalidates the recurrence.",
        }
        if previous:
            draft.update(
                title="Position-shift subset count",
                summary="Count strings by a bijection from nonadjacent one positions to subsets.",
                approach="Fix k ones at increasing positions i_1,...,i_k. Shift position i_j to i_j-(j-1), yielding a k-subset of {1,...,n-k+1}; sum the resulting binomial counts over k.",
                first_tests="Enumerate n=0,1,2,5,10 and compare to 1,2,3,13,144; finite agreement is not a proof.",
                assumptions="Positions are one-indexed and k ranges from zero through the largest feasible count.",
                failure_modes="An incorrect inverse or boundary range would overcount strings.",
            )
    return httpx.Response(
        200,
        json={
            "status": "completed",
            "model": body["model"],
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
