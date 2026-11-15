"""Multi-round deterministic provider fixture for Maximum Regions browser acceptance."""

import json

import httpx

from browser_checks import provider_fixture as fixture
from tests.research_sessions import provider_response

original_handler = fixture.handler
calls = []

FIRST_ARGUMENT = [
    {
        "title": "Proposed increment",
        "argument": "Assume the kth line adds 2k regions, so the proposed answer is R(n)=n^2+1.",
        "epistemic_status": "deduction",
        "basis_artifact_ids": [],
    }
]
FINAL_ARGUMENT = [
    {
        "title": "Insertion bound",
        "argument": "The kth line has at most k−1 distinct intersections with earlier lines, so it has at most k pieces; each piece can split at most one old region.",
        "epistemic_status": "deduction",
        "basis_artifact_ids": [],
    },
    {
        "title": "Distinct old regions",
        "argument": "Old regions are convex intersections of open half-planes. Two pieces separated by an earlier-line crossing cannot lie in one old region, and openness makes each crossed region split into two.",
        "epistemic_status": "deduction",
        "basis_artifact_ids": [],
    },
    {
        "title": "Attainment construction",
        "argument": "For L_k:y=kx+k², intersections with L_i occur at x=−(i+k), distinct for each i<k. Thus every insertion has k pieces in distinct old regions.",
        "epistemic_status": "deduction",
        "basis_artifact_ids": [],
    },
    {
        "title": "Recurrence and base case",
        "argument": "The upper bound and attaining family give R(k)=R(k−1)+k. With no lines the plane is one region, so R(0)=1.",
        "epistemic_status": "deduction",
        "basis_artifact_ids": [],
    },
    {
        "title": "Closed form",
        "argument": "Induction on the recurrence yields R(n)=1+Σ(k=1…n)k=1+n(n+1)/2 for every n≥0.",
        "epistemic_status": "deduction",
        "basis_artifact_ids": [],
    },
]


def _maximum_regions(context: dict) -> bool:
    problem = str(context.get("problem") or "").casefold()
    title = str(context.get("project_title") or "").casefold()
    return "line" in problem and "region" in problem or "maximum regions" in title


def _investigator(cycle: int) -> dict:
    if cycle == 1:
        return {
            "claim": "The proposed maximum is R(n)=n^2+1.",
            "method": "Assume each new line adds 2k regions. The estimate has not been checked on small arrangements.",
            "reasoning_steps": FIRST_ARGUMENT,
            "claim_is_conditional": False,
            "assumptions": [],
            "evidence_status": "Unverified initial candidate with an unchecked increment estimate.",
            "open_obligations": [
                "Check the proposed increment against an arrangement of two lines."
            ],
            "python_code": None,
            "sage_code": None,
            "prior_session_failure_attempt_ids": [],
            "human_guidance_reviews": [],
            "computational_citations": [],
        }
    return {
        "claim": "R(n) = 1 + n(n+1)/2 is the maximum for every n >= 0.",
        "method": "The kth line contributes at most k regions. Convexity separates the pieces, and the family y=kx+k² attains every increment. The empty arrangement starts at one region; summing the recurrence proves the formula.",
        "reasoning_steps": FINAL_ARGUMENT,
        "claim_is_conditional": False,
        "assumptions": [],
        "evidence_status": "Revised unverified argument; no formal proof checker was run.",
        "open_obligations": [],
        "python_code": None,
        "sage_code": None,
        "prior_session_failure_attempt_ids": [],
        "human_guidance_reviews": [],
        "computational_citations": [],
    }


def _skeptic(cycle: int, context: dict) -> dict:
    if cycle == 1:
        return {
            "assessment": "revise",
            "stop_reason": "recoverable_objection",
            "response": "For n=2, the proposed expression gives five regions, but two lines give at most four. The 2k increment is unsupported; revise it before concluding.",
            "objections": [
                "The proposed increment predicts five regions for two lines, but the maximum is four."
            ],
            "remaining_obligations": [
                "Replace the increment estimate and prove a matching construction."
            ],
            "next_question": "Derive the per-line upper bound and test an attaining family.",
            "objective_status": "partial",
            "solution_claim": "The initial n^2+1 candidate is contradicted by the two-line case.",
            "argument_summary": "The two-line counterexample refutes the proposed increment; a corrected bound and attainment remain open.",
            "reasoning_assessments": [
                {
                    "step_number": 1,
                    "disposition": "challenged",
                    "rationale": "The estimate does not follow from any count of crossings on the inserted line.",
                    "objection": "At n=2 it predicts five regions, exceeding the four possible regions.",
                    "basis_artifact_ids": [],
                }
            ],
            "claim_is_conditional": False,
            "assumptions_reviewed": [],
            "proof_obligations": ["Establish the upper bound and give an attaining construction."],
            "unresolved_objections": ["The 2k increment is contradicted by the two-line case."],
            "supporting_cycles": [1],
            "verification_status": "incomplete",
            "strategy_contribution": "productive",
            "contribution_rationale": "The small-case test rejected the first increment estimate and identified the needed revision.",
            "cross_strategy_relations": [],
            "retracted_cross_strategy_source_artifact_ids": [],
            "peer_handoff_reviews": [],
            "human_guidance_reviews": [],
            "obligation_reviews": [],
            "computational_citations": [],
        }
    investigation = context["investigator_output"]
    return {
        "assessment": "stop",
        "stop_reason": "productive_conclusion",
        "response": "The revised insertion bound handles the two-line objection. Convexity places separated pieces in distinct old regions; y=kx+k² attains every increment. Summation and R(0)=1 give the stated candidate for all n.",
        "objections": [],
        "remaining_obligations": [],
        "next_question": "",
        "objective_status": "achieved",
        "solution_claim": investigation["claim"],
        "argument_summary": "The insertion bound, explicit attaining family, recurrence, and empty-arrangement base case establish the formula as an unverified candidate.",
        "reasoning_assessments": [
            {
                "step_number": index,
                "disposition": "accepted",
                "rationale": "This step follows from its stated intersection, convexity, or induction argument, with no unsupported inference in the recorded derivation.",
                "objection": "",
                "basis_artifact_ids": [],
            }
            for index in range(1, len(investigation["reasoning_steps"]) + 1)
        ],
        "claim_is_conditional": False,
        "assumptions_reviewed": [],
        "proof_obligations": [
            "The insertion bound proves the universal upper bound [round 2].",
            "The explicit family attains each increment [round 2].",
            "The empty arrangement gives R(0)=1 [round 2].",
        ],
        "unresolved_objections": [],
        "supporting_cycles": [1, 2],
        "verification_status": "convincing_unverified",
        "strategy_contribution": "solution",
        "contribution_rationale": "The revised argument addresses the counterexample and links the bound, attainment, recurrence, and base case.",
        "cross_strategy_relations": [],
        "retracted_cross_strategy_source_artifact_ids": [],
        "peer_handoff_reviews": [],
        "human_guidance_reviews": [],
        "obligation_reviews": [],
        "computational_citations": [],
    }


async def handler(request):
    if request.method == "GET":
        return await original_handler(request)
    body = json.loads(request.content)
    context = json.loads(body["input"])
    schema = body["text"]["format"]["name"]
    if schema not in {"research_investigator", "research_skeptic"} or not _maximum_regions(context):
        return await original_handler(request)

    cycle = int(context["cycle"])
    calls.append((schema, cycle))
    output = _investigator(cycle) if schema == "research_investigator" else _skeptic(cycle, context)
    result = provider_response(output)
    result["usage"] = {
        "input_tokens": 900,
        "input_tokens_details": {"cached_tokens": 100},
        "output_tokens": 1200,
    }
    return httpx.Response(200, json=result)


fixture.handler = handler
app = fixture.app
