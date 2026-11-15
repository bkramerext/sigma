"""Mock provider roles with real isolated Sage execution; no live model calls."""

import json

import httpx
import provider_fixture

app = provider_fixture.app
original = provider_fixture.handler
SOURCE = """from pathlib import Path
import json
witnesses = [int(n) for n in srange(3,1000,2) if not is_prime(n) and power_mod(2,n-1,n)==1]
assert 341 in witnesses and 341 == 11*31
Path('/artifacts/witnesses.json').write_text(json.dumps(witnesses))
print('COUNTEREXAMPLE: 341 = 11 * 31; Fermat base-2 does not certify primality')
"""


async def handler(request):
    response = await original(request)
    if request.method != "POST":
        return response
    body = json.loads(request.content)
    context = json.loads(body["input"])
    name = body["text"]["format"]["name"]
    if "Sage fixture" not in context.get("problem", "") or name not in {
        "research_investigator",
        "research_skeptic",
    }:
        return response
    assert "SageMath is available" in body["instructions"]
    assert any(
        tool["runtime"] == "sagemath" and tool["available"] for tool in context["execution_tools"]
    )
    payload = response.json()
    result = json.loads(payload["output"][0]["content"][0]["text"])
    if name == "research_investigator":
        result.update(
            claim="Test the proposed base-2 Fermat primality certificate.",
            method="Search finite odd composites below 1000 for a passing Fermat test; a composite witness contradicts the certificate.",
            assumptions=["Integer candidates 3 through 999"],
            evidence_status="Proposal; inspect the subsequent Sage execution.",
            python_code=None,
            sage_code=SOURCE,
        )
    else:
        execution = context["investigator_output"]["sage_execution"]
        assert (
            execution["status"] == "completed" and "COUNTEREXAMPLE: 341" in execution["stdout"]
        ), execution
        assert execution["source"] == SOURCE and execution["agent"]["step_id"]
        result.update(
            assessment="stop",
            stop_reason="productive_conclusion",
            response="The saved Sage source finds the exact composite witness 341=11*31. Its passing base-2 Fermat test contradicts the proposed certificate. This is computational evidence; no formal proof checker was run.",
            objections=[],
            remaining_obligations=[],
            next_question="",
            objective_status="achieved",
            solution_claim="341=11*31 is a composite passing the base-2 Fermat test.",
            argument_summary="Use the original saved Sage source, stdout and witness file. The experiment contradicts the original hypothesis; a zero exit alone would not establish that.",
            assumptions_reviewed=["Integer arithmetic; fixed finite search"],
            proof_obligations=[],
            unresolved_objections=[],
            supporting_cycles=[1],
            verification_status="convincing_unverified",
            strategy_contribution="solution",
            contribution_rationale="Exact finite counterexample recorded in the execution evidence.",
        )
    payload["output"][0]["content"][0]["text"] = json.dumps(result)
    return httpx.Response(200, json=payload)


provider_fixture.handler = handler
