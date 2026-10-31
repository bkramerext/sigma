"""Isolated browser-test provider fixture; no network or real credentials."""

import asyncio
import json
import os
from contextlib import asynccontextmanager
from pathlib import Path
from tempfile import mkdtemp

import httpx

os.environ["SIGMA_STATE_DIR"] = mkdtemp(prefix="sigma-browser-recents-")
os.environ["SIGMA_PROJECTS_ROOT"] = mkdtemp(prefix="sigma-browser-managed-")
os.environ["SIGMA_AUTH_HOME"] = mkdtemp(prefix="sigma-browser-api-auth-")
os.environ["OPENAI_API_KEY"] = "explicit-browser-test-fixture"
os.environ["SIGMA_AI_MODEL"] = "gpt-4.1"

from sigma import papers, proposals, samples
from sigma.api import app

# The fixture's project workspace is temporary and private, while sample
# projects are immutable repository source data that the UI must still list.
samples.SAMPLES = Path(__file__).resolve().parents[1] / "samples"

# Mutable controls are exposed only by this isolated deterministic fixture.
# They let browser acceptance exercise recovery states without contacting a
# provider endpoint or spending an account allowance.
_paper_failures: dict[str, dict[str, int]] = {}
_qa_control = {"delay_seconds": 0.0, "fail_next": 0, "started": 0, "completed": 0}
_real_provider_structured = papers._provider_structured


@app.post("/api/__fixture/paper-failure")
def set_paper_failure(body: dict[str, object]):
    schema_name = body.get("schema_name")
    mode = body.get("mode")
    count = body.get("count")
    if (
        not isinstance(schema_name, str)
        or schema_name not in {"sigma_long_paper_plan", "sigma_long_paper_section"}
        or mode not in {"pre_dispatch", "provider_error"}
        or type(count) is not int
        or not 0 <= count <= 3
    ):
        return {"error": "Invalid deterministic paper-fixture control"}, 400
    _paper_failures[schema_name] = {"mode": str(mode), "count": count}
    return {"configured": True}


@app.post("/api/__fixture/qa-control")
def set_qa_control(body: dict[str, object]):
    delay = body.get("delay_seconds", 0)
    failures = body.get("fail_next", 0)
    if (
        type(delay) not in {int, float}
        or not 0 <= delay <= 5
        or type(failures) is not int
        or not 0 <= failures <= 2
    ):
        return {"error": "Invalid deterministic Q/A fixture control"}, 400
    _qa_control["delay_seconds"] = float(delay)
    _qa_control["fail_next"] = failures
    return {"configured": True}


@app.get("/api/__fixture/qa-state")
def qa_fixture_state():
    return dict(_qa_control)


async def fixture_provider_structured(input_value, *args, schema_name: str, **kwargs):
    control = _paper_failures.get(schema_name)
    if control and control["count"]:
        control["count"] -= 1
        if control["mode"] == "pre_dispatch":
            raise papers.PaperConnectionFailure(
                "Deterministic fixture connection failure before provider dispatch"
            )
        raise papers.ProjectError("Deterministic fixture provider returned HTTP 500")
    return await _real_provider_structured(input_value, *args, schema_name=schema_name, **kwargs)


papers._provider_structured = fixture_provider_structured

# Optional test-only origin normalization lets real-browser acceptance use a
# separate Vite port while preserving the local API's production origin guard.
fixture_origin = os.environ.get("SIGMA_PAPER_PROGRESS_FIXTURE_ORIGIN", "").strip()
if fixture_origin:

    @app.middleware("http")
    async def normalize_fixture_origin(request, call_next):
        headers = [
            (key, b"http://127.0.0.1:5173" if key == b"origin" else value)
            for key, value in request.scope["headers"]
        ]
        request.scope["headers"] = headers
        return await call_next(request)


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
    schema_name = body["text"]["format"]["name"]
    progress_delay = float(os.environ.get("SIGMA_PAPER_PROGRESS_FIXTURE_DELAY", "0"))
    if progress_delay > 0 and schema_name in {
        "sigma_paper_evidence_batch",
        "sigma_paper_evidence_reduction",
        "sigma_long_paper_plan",
        "sigma_long_paper_section",
        "sigma_research_paper",
        "sigma_research_qa",
    }:
        await asyncio.sleep(min(progress_delay, 5))
    if schema_name in {
        "sigma_paper_evidence_batch",
        "sigma_paper_evidence_reduction",
        "sigma_long_paper_plan",
        "sigma_long_paper_section",
    }:
        if schema_name in {"sigma_paper_evidence_batch", "sigma_paper_evidence_reduction"}:
            if schema_name == "sigma_paper_evidence_batch":
                refs = list(dict.fromkeys(field["source_ref"] for field in context["fields"]))[:3]
            else:
                refs = list(
                    dict.fromkeys(ref for note in context for ref in note["evidence_refs"])
                )[:3]
            output = {
                "notes": [
                    {
                        "statement": "The frozen record contains a saved research objective and source-linked study context.",
                        "kind": "context",
                        "evidence_refs": [reference],
                    }
                    for reference in refs
                ],
                "conflicts_or_gaps": [],
                "covered_field_refs": (
                    [field["field_ref"] for field in context["fields"]]
                    if schema_name == "sigma_paper_evidence_batch"
                    else []
                ),
                "omitted_fields": [],
            }
        elif schema_name == "sigma_long_paper_plan":
            reference = context["evidence_index"][0]["evidence_refs"][0]
            output = {
                "title": "A Long-Form Experimental Research Synthesis",
                "abstract": "This paper organizes the saved experimental question, its evidence base, and the limitations recorded in the frozen research snapshot. The manuscript distinguishes observations from hypotheses and proposed future tests.",
                "abstract_claim_ids": ["C1"],
                "problem_framing": [
                    "The saved project defines an experimentally anchored question whose interpretation depends on the available records."
                ],
                "problem_framing_claim_ids": ["C1"],
                "methods": [
                    "We organized the frozen source record into bounded evidence batches and retained each source reference."
                ],
                "methods_claim_ids": ["C1"],
                "claims": [
                    {
                        "id": "C1",
                        "statement": "The frozen project records an experimental research objective.",
                        "status": "established",
                        "evidence_refs": [reference],
                        "reasoning": "The objective appears in the saved project source in the complete snapshot.",
                    }
                ],
                "sections": [
                    {
                        "heading": "Experimental question and prior context",
                        "purpose": "Describe the saved question and distinguish established context from open hypotheses.",
                        "evidence_refs": [reference],
                        "claim_ids": ["C1"],
                    },
                    {
                        "heading": "Evidence, limitations, and next tests",
                        "purpose": "Explain the available records, gaps, and discriminating experimental work.",
                        "evidence_refs": [reference],
                        "claim_ids": ["C1"],
                    },
                ],
                "limitations": [
                    "This deterministic browser fixture is not biological evidence or an independent review."
                ],
                "open_obligations": [
                    "Review the underlying biological sources and validate the proposed experiments."
                ],
                "conclusions": [
                    "The saved evidence supports an exploratory synthesis, not a validated biological mechanism."
                ],
                "conclusion_claim_ids": ["C1"],
                "validation_warnings": [],
            }
        else:
            output = {
                "paragraphs": [
                    "The saved material is described with explicit source references and with its uncertainty intact. The research question is treated as an experimental problem; hypotheses and future interventions are not presented as observations.",
                    "The appropriate interpretation is limited by the records currently preserved. Independent samples, suitable controls, and a falsifiable perturbation would be needed before claiming a new mechanism.",
                ]
            }
        return httpx.Response(
            200,
            json={
                "status": "completed",
                "model": body["model"],
                "output": [
                    {
                        "type": "message",
                        "content": [{"type": "output_text", "text": json.dumps(output)}],
                    }
                ],
            },
        )
    if schema_name == "sigma_research_qa":
        _qa_control["started"] = int(_qa_control["started"]) + 1
        if _qa_control["fail_next"]:
            _qa_control["fail_next"] = int(_qa_control["fail_next"]) - 1
            _qa_control["completed"] = int(_qa_control["completed"]) + 1
            return httpx.Response(500, json={"error": {"message": "Deterministic Q/A failure"}})
        delay = float(_qa_control["delay_seconds"])
        if delay:
            await asyncio.sleep(delay)
        question = context.get("question", "")
        sources = context.get("sources", [])
        refs = []
        for kind in ("session", "artifact", "current_understanding"):
            source = next((item for item in sources if item.get("kind") == kind), None)
            if source:
                refs.append(source["id"])
        output = {
            "answer": f"The saved research answers: {question}. The record is provisional and should be reviewed with its supporting evidence.",
            "source_refs": refs,
        }
        _qa_control["completed"] = int(_qa_control["completed"]) + 1
        return httpx.Response(
            200,
            json={
                "status": "completed",
                "model": body["model"],
                "output": [
                    {
                        "type": "message",
                        "content": [{"type": "output_text", "text": json.dumps(output)}],
                    }
                ],
            },
        )
    if schema_name == "sigma_research_paper":
        sources = context["sources"]
        project_source = next(item for item in sources if item["kind"] == "project")
        project_data = project_source["data"]
        title = project_data["title"]
        problem = project_data["problem"]
        if project_data.get("investigation_type") == "mathematical":
            assert "organization and precision of a" in body["instructions"]
            assert "separately prove the upper bound" in body["instructions"]
        max_regions = (
            "maximum regions" in title.casefold()
            or "maximum number of regions" in problem.casefold()
        )
        artifact_refs = [item["id"] for item in sources if item["kind"] == "artifact"]
        if max_regions:
            evidence = artifact_refs[:4] or [project_source["id"]]
            paper = {
                "title": "The Maximum Number of Regions Formed by Lines",
                "abstract": r"We study the maximum number $R(n)$ of regions cut out in the plane by $n$ distinct lines. Inserting lines one at a time gives an upper bound of $k$ new regions at step $k$. The family $L_j:y=jx+j^2$ attains this bound at every step, since the intersections on each new line are distinct. Together with the empty arrangement, this yields the candidate formula $R(n)=1+n(n+1)/2$. The complete argument is present in the saved research record, but has not been independently verified.",
                "abstract_claim_ids": ["C1", "C2", "C3"],
                "problem_framing": [
                    "An arrangement partitions the plane into connected components of its complement; these components are the regions being counted. We seek the largest possible count among arrangements of n distinct lines.",
                    "There are two tasks: prove that no insertion can add more than k regions at step k, and construct arrangements in which every insertion adds exactly k.",
                ],
                "problem_framing_claim_ids": ["C1", "C2"],
                "methods": [
                    "We organize the saved argument as induction on the number of inserted lines. The research artifacts supply the upper-bound argument, an explicit attaining family, and the caveat that no independent proof checker was run."
                ],
                "methods_claim_ids": ["C1", "C2", "C3"],
                "claims": [
                    {
                        "id": "C1",
                        "statement": "Adding a kth line to an arrangement of k−1 lines creates at most k new regions.",
                        "status": "conjecture",
                        "evidence_refs": evidence,
                        "reasoning": "The cited argument bounds the intersection points on the new line and uses convexity of old regions to show its pieces enter distinct regions.",
                    },
                    {
                        "id": "C2",
                        "statement": "The family L_j:y=jx+j² attains k new regions at every insertion step k.",
                        "status": "conjecture",
                        "evidence_refs": evidence,
                        "reasoning": "For fixed k, intersections with earlier lines have distinct x-coordinates −(k+j), giving k pieces; the saved cell argument shows they split k distinct old regions.",
                    },
                    {
                        "id": "C3",
                        "statement": "The saved argument derives R(n)=1+n(n+1)/2 for every integer n≥0.",
                        "status": "conjecture",
                        "evidence_refs": evidence,
                        "reasoning": "The recurrence starts at one region for n=0 and adds exactly k at step k, while the source record labels the argument unverified.",
                    },
                ],
                "sections": [
                    {
                        "heading": "Notation and a cell lemma",
                        "paragraphs": [
                            r"Let $R(\mathcal{A})$ be the number of regions determined by a finite line arrangement $\mathcal{A}$. Choose one of the two open sides of each line and intersect the chosen half-planes. Every nonempty intersection is convex, hence connected, and is one region.",
                            r"If a new line meets an old region, it splits that region into two nonempty pieces: a point on the line lies inside the open region, so a small disk around it contains points on both sides. Further, two separated pieces of the new line cannot lie in the same old region. Convexity would force the segment between them to stay in that region, including an intervening point on an earlier line, which no old region contains.",
                        ],
                        "claim_ids": ["C1", "C2"],
                    },
                    {
                        "heading": "Main result (unverified proof candidate)",
                        "paragraphs": [
                            r"For every integer $n\geq0$, the maximum number of regions determined by $n$ lines is $R(n)=1+n(n+1)/2$. We give the saved argument for this statement below; the project record classifies it as an unverified candidate."
                        ],
                        "claim_ids": ["C3"],
                    },
                    {
                        "heading": "The upper bound",
                        "paragraphs": [
                            r"Insert the lines in order. At step $k$, the new line intersects each of the $k−1$ earlier lines in at most one point. These points divide it into at most $k$ connected pieces, including the two unbounded pieces. Each piece lies in an old region, and the cell lemma puts different pieces in different old regions. Each crossed region is split into two, so at most $k$ new regions are created.",
                            r"Writing $R_k$ for the largest count after $k$ insertions gives $R_k\leq R_{k−1}+k$. Since the empty arrangement has one region, induction yields $R_n\leq 1+\sum_{k=1}^{n}k$.",
                        ],
                        "claim_ids": ["C1"],
                    },
                    {
                        "heading": "Proof of attainability",
                        "paragraphs": [
                            r"For each positive integer $j$, take $L_j:y=jx+j^2$. The slopes are distinct. Fix $k$ and intersect $L_k$ with an earlier line $L_j$, where $1\le j<k$. Solving $kx+k^2=jx+j^2$ gives $x=−(k+j)$. These coordinates are distinct as $j$ varies, so the $k−1$ crossings on $L_k$ are distinct and divide it into exactly $k$ pieces.",
                            r"By the cell lemma, these pieces lie in distinct old regions, and each crossed region is split into two. Thus $L_k$ adds exactly $k$ regions. The construction attains every insertion bound, not just the final sum.",
                        ],
                        "claim_ids": ["C2"],
                    },
                    {
                        "heading": "The formula and its status",
                        "paragraphs": [
                            r"The upper bound and construction match, so $R_k=R_{k−1}+k$ with $R_0=1$. Summing gives $R_n=1+\sum_{k=1}^{n}k=1+n(n+1)/2$. The boundary case $n=0$ is included: with no lines, the plane has one region.",
                            "The saved artifacts contain this full candidate argument, including the convexity step and explicit construction. They label it unverified, and no independent proof checker was run; we therefore present a saved proof candidate, not a formally certified theorem.",
                        ],
                        "claim_ids": ["C1", "C2", "C3"],
                    },
                ],
                "limitations": [
                    "The argument is recorded as an unverified model-generated candidate; no independent proof checker was run."
                ],
                "open_obligations": [],
                "conclusions": [
                    r"The saved proof candidate explains both why no arrangement can exceed $1+n(n+1)/2$ and how the displayed family attains that count. It remains unverified by an independent checker."
                ],
                "conclusion_claim_ids": ["C1", "C2", "C3"],
                "validation_warnings": ["The proof has not been independently verified."],
            }
        else:
            paper = {
                "title": "An Exploratory Record with Open Questions",
                "abstract": "This paper reports an exploratory research state. The saved project provides an objective but no completed research session, so the available evidence does not support a theorem-proof conclusion. The discussion is limited to the recorded scope and makes its missing evidence explicit.",
                "abstract_claim_ids": ["C1"],
                "problem_framing": [f"The saved objective is: {problem}"],
                "problem_framing_claim_ids": ["C1"],
                "methods": [
                    "We inspected the current saved project snapshot; no research session or experiment was recorded."
                ],
                "methods_claim_ids": ["C1"],
                "claims": [
                    {
                        "id": "C1",
                        "statement": "The project snapshot records the stated research objective.",
                        "status": "established",
                        "evidence_refs": [project_source["id"]],
                        "reasoning": "This is directly present in the saved project record.",
                    }
                ],
                "sections": [
                    {
                        "heading": "Available evidence",
                        "paragraphs": [
                            "The snapshot contains the project objective but no durable research findings."
                        ],
                        "claim_ids": ["C1"],
                    },
                    {
                        "heading": "Exploratory status",
                        "paragraphs": [
                            "No substantive conclusion is justified by this record; the project remains open for investigation."
                        ],
                        "claim_ids": [],
                    },
                ],
                "limitations": [
                    "There are no saved research sessions or findings in this snapshot."
                ],
                "open_obligations": [
                    "Conduct and preserve research before drawing a substantive conclusion."
                ],
                "conclusions": ["This is an exploratory account, not a theorem-proof paper."],
                "conclusion_claim_ids": ["C1"],
                "validation_warnings": [],
            }
        return httpx.Response(
            200,
            json={
                "status": "completed",
                "model": body["model"],
                "output": [
                    {
                        "type": "message",
                        "content": [{"type": "output_text", "text": json.dumps(paper)}],
                    }
                ],
            },
        )
    if body["text"]["format"]["name"] in {"research_investigator", "research_skeptic"}:
        strategy_title = context.get("strategy", {}).get("title")
        if strategy_title == "Failure fixture strategy":
            return httpx.Response(500)
        if strategy_title == "Pause and stop fixture strategy":
            await asyncio.sleep(2)
        cycle = context["cycle"]
        problem_text = context.get("problem", "").lower()
        maximum_regions = "line" in problem_text and "region" in problem_text
        if body["text"]["format"]["name"] == "research_investigator":
            result = (
                {
                    "claim": "The maximum is R(n) = 1 + n(n+1)/2 for every n >= 0.",
                    "method": "Each region is a nonempty intersection of open half-planes with one chosen side of each line, hence convex and connected; different pieces of an inserted line lie in different old regions. Insert lines one at a time. The kth line has at most k-1 distinct intersections and is split into at most k pieces, each increasing the region count by at most one. The lines y=kx+k^2 have pairwise distinct intersections along each newly added line, so each of its k pieces lies in a distinct convex prior region and attains the bound. For n=0 there is one region.",
                    "assumptions": ["Lines are distinct straight lines in the Euclidean plane."],
                    "claim_is_conditional": True,
                    "evidence_status": "Complete unverified mathematical argument; no proof checker was run.",
                    "open_obligations": [],
                    "python_code": None,
                    "sage_code": None,
                    "prior_session_failure_attempt_ids": [],
                    "human_guidance_reviews": [],
                    "computational_citations": [],
                }
                if maximum_regions
                else {
                    "claim": f"Fixture claim {cycle}: a candidate consequence follows from the saved strategy.",
                    "method": f"Use the stated mechanism to derive consequence {cycle}.",
                    "assumptions": [f"Fixture assumption {cycle}"],
                    "claim_is_conditional": False,
                    "evidence_status": "Unverified model derivation; no tool was run.",
                    "open_obligations": [f"Check obligation {cycle}"],
                    "python_code": None,
                    "sage_code": None,
                    "prior_session_failure_attempt_ids": [],
                    "human_guidance_reviews": [],
                    "computational_citations": [],
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
                    "assumptions_reviewed": [
                        "Lines are distinct straight lines in the Euclidean plane."
                    ],
                    "proof_obligations": [
                        "Prove the per-line upper bound.",
                        "Show one arrangement attains every increment.",
                        "Handle n=0.",
                        "Define regions as connected components of the complement.",
                        "Prove every cell is convex.",
                        "Prove each crossed cell splits into two cells.",
                        "Prove separated line pieces cannot lie in one old cell.",
                        "Bound the number of distinct intersections on the inserted line.",
                        "Count the unbounded pieces at each insertion step.",
                        "Verify the attaining lines have distinct slopes.",
                        "Compute the intersection coordinates explicitly.",
                        "Derive the recurrence from the insertion bound.",
                    ],
                    "unresolved_objections": [],
                    "supporting_cycles": [1],
                    "verification_status": "convincing_unverified",
                    "strategy_contribution": "solution",
                    "contribution_rationale": "This strategy supplies both the upper-bound induction and an explicit arrangement attaining equality.",
                    "cross_strategy_relations": [],
                    "retracted_cross_strategy_source_artifact_ids": [],
                    "peer_handoff_reviews": [],
                    "human_guidance_reviews": [],
                    "obligation_reviews": [],
                    "claim_is_conditional": True,
                    "computational_citations": [],
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
                    "cross_strategy_relations": [],
                    "retracted_cross_strategy_source_artifact_ids": [],
                    "peer_handoff_reviews": [],
                    "human_guidance_reviews": [],
                    "obligation_reviews": [],
                    "claim_is_conditional": False,
                    "computational_citations": [],
                }
            )
        if body["text"]["format"]["name"] == "research_investigator":
            result["reasoning_steps"] = (
                [
                    {
                        "title": "Assumptions and domain",
                        "argument": "Lines are distinct straight lines in the Euclidean plane.",
                        "epistemic_status": "assumption",
                        "basis_artifact_ids": [],
                    },
                    {
                        "title": "Insertion upper bound",
                        "argument": "The kth line has at most k−1 distinct intersections with earlier lines, giving at most k pieces; each piece can split at most one old region, so at most k new regions are added.",
                        "epistemic_status": "deduction",
                        "basis_artifact_ids": [],
                    },
                    {
                        "title": "Distinct regions are split",
                        "argument": "Old regions are convex intersections of open half-planes. Two pieces separated by an earlier-line crossing cannot lie in one old region, and openness gives points on both sides of each crossing, so each met region splits.",
                        "epistemic_status": "deduction",
                        "basis_artifact_ids": [],
                    },
                    {
                        "title": "Attainment construction",
                        "argument": "For L_k:y=kx+k², intersections with L_i occur at x=−(i+k), distinct for each i<k. There are no triple intersections, so insertion k creates k pieces in k distinct old regions.",
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
                        "argument": "Induction on the recurrence yields R(n)=1+Σ(k=1…n)k=1+n(n+1)/2.",
                        "epistemic_status": "deduction",
                        "basis_artifact_ids": [],
                    },
                ]
                if maximum_regions
                else [
                    {
                        "title": "Bounded fixture finding",
                        "argument": "This fixture makes a local consequence under its stated premise; it does not establish the project's full objective.",
                        "epistemic_status": "deduction",
                        "basis_artifact_ids": [],
                    }
                ]
            )
        else:
            result["reasoning_assessments"] = [
                {
                    "step_number": index,
                    "disposition": "accepted",
                    "rationale": (
                        "The stated geometric step follows from the explicit intersections and convexity argument."
                        if maximum_regions
                        else "The limited consequence follows from its recorded premise; it does not resolve the full objective."
                    ),
                    "objection": "",
                    "basis_artifact_ids": [],
                }
                for index, _ in enumerate(
                    context.get("investigator_output", {}).get("reasoning_steps", []), 1
                )
            ]
            result["assumptions_reviewed"] = context.get("investigator_output", {}).get(
                "assumptions", []
            )
        result["human_guidance_reviews"] = [
            {
                "intervention_id": item["intervention_id"],
                "uptake": "considered",
                "rationale": "I considered this guidance while preparing the next bounded step.",
            }
            for item in context.get("human_guidance", [])
        ]
        result.setdefault("computational_citations", [])
        return httpx.Response(
            200,
            json={
                "status": "completed",
                "model": body["model"],
                **(
                    {
                        "usage": {
                            "input_tokens": 900,
                            "input_tokens_details": {"cached_tokens": 100},
                            "output_tokens": 1200,
                        }
                    }
                    if maximum_regions
                    else {}
                ),
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
    if agentic and seed == "long-fixture":
        details = "\n".join(
            f"Review item {index}: record the controlling assumption, confirming evidence, decision owner, deadline, alternate path, and consequence if unconfirmed."
            for index in range(1, 100)
        )
        draft = {
            **draft,
            "title": "Long strategy field regression",
            "approach": f"{draft['approach']}\n\n{details}",
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
            "prior_finding_ids": [],
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
