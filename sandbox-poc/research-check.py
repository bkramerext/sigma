"""Real scientific computations through scripted research cycles; no model calls.

The provider fixture checks actual tool evidence before proposing the next
experiment. It tests SIGMA's feedback plumbing, not live model judgment.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import httpx

from sigma import research_sessions
from sigma.projects import create_strategy, initialize_project
from sigma.python_sandbox import get_execution, get_execution_artifact

REAL_CLIENT = httpx.AsyncClient
CASES = {
    "cancellation-error": [
        (
            "completed",
            "Test whether the naive difference quotient is accurate near zero.",
            """import json
import numpy as np
x=1e-16
naive=float((np.sqrt(1+x)-1)/x)
stable=float(1/(np.sqrt(1+x)+1))
assert naive == 0 and abs(stable-0.5)<1e-15
print(json.dumps({'naive':naive,'stable':stable,'absolute_error':abs(naive-stable)}))
""",
        ),
        (
            "completed",
            "Rationalize the expression and compare floating point with an exact symbolic limit.",
            """import json
import numpy as np
import sympy as sp
x=sp.symbols('x', positive=True)
limit=sp.limit((sp.sqrt(1+x)-1)/x,x,0)
xs=np.logspace(-16,-2,15)
values=1/(np.sqrt(1+xs)+1)
assert limit == sp.Rational(1,2)
assert np.isfinite(values).all() and abs(values[0]-float(limit))<1e-15
print(json.dumps({'symbolic_limit':str(limit),'samples':len(xs),'near_zero':float(values[0]),'finite_evidence_only':True}))
""",
        ),
    ],
    "ill-conditioned-system": [
        (
            "completed",
            "Test whether a small residual guarantees an accurate solution.",
            """import json
import numpy as np
from scipy.linalg import hilbert
A=hilbert(10); truth=np.ones(10); b=A@truth
perturbed=b+(-1.)**np.arange(10)*1e-12
x=np.linalg.solve(A,perturbed)
residual=float(np.linalg.norm(A@x-perturbed)/np.linalg.norm(perturbed))
error=float(np.linalg.norm(x-truth)/np.linalg.norm(truth))
condition=float(np.linalg.cond(A))
assert condition>1e12 and residual<1e-12 and error>0.1
print(json.dumps({'condition':condition,'relative_residual':residual,'relative_solution_error':error}))
""",
        ),
    ],
    "singular-system-repair": [
        (
            "failed",
            "Attempt a direct solve and retain the exception as an operational failure.",
            """import numpy as np
A=np.array([[1.,1.],[2.,2.]])
print('Trying a direct solve for a rank-deficient system',flush=True)
print(np.linalg.solve(A,np.array([1.,2.])))
""",
        ),
        (
            "completed",
            "Use rank-revealing least squares; identify nonuniqueness rather than asserting no solution.",
            """import json
import numpy as np
A=np.array([[1.,1.],[2.,2.]])
b=np.array([1.,2.])
x,residuals,rank,s=np.linalg.lstsq(A,b,rcond=None)
assert rank==1 and np.linalg.norm(A@x-b)<1e-12
assert np.linalg.norm(A@np.array([1.,-1.]))==0
print(json.dumps({'rank':int(rank),'one_solution':x.tolist(),'null_vector':[1,-1],'unique':False}))
""",
        ),
    ],
    "false-prime-hypothesis": [
        (
            "completed",
            "Search a limited interval for a counterexample to universal primality.",
            """import json
import sympy as sp
checked=[n for n in range(40) if not sp.isprime(n*n+n+41)]
assert checked==[]
print(json.dumps({'checked_n':[0,39],'counterexamples':checked,'universal_claim_proved':False}))
""",
        ),
        (
            "completed",
            "Expand the interval after the limited search; factor the first counterexample exactly.",
            """import json
import sympy as sp
n=next(n for n in range(101) if not sp.isprime(n*n+n+41))
value=n*n+n+41
assert n==40 and value==41**2
print(json.dumps({'first_counterexample':n,'value':value,'factorization':str(sp.factorint(value)),'universal_claim_proved':False}))
""",
        ),
    ],
    "monte-carlo-repeats": [
        (
            "completed",
            "Repeat a seeded Monte Carlo integral across sample sizes and compare with independent quadrature.",
            """import json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.integrate import quad
reference,quadrature_error=quad(lambda x:np.exp(-x*x),0,1)
rows=[]
for size in [1000,10000,100000]:
    for seed in range(8):
        values=np.exp(-np.random.default_rng(seed).random(size)**2)
        estimate=float(values.mean()); se=float(values.std(ddof=1)/np.sqrt(size))
        rows.append({'n':size,'seed':seed,'estimate':estimate,'standard_error':se,'absolute_error':abs(estimate-reference)})
table=pd.DataFrame(rows)
assert len(table)==24 and table.groupby('n').standard_error.mean().iloc[-1]<table.groupby('n').standard_error.mean().iloc[0]/8
assert abs(reference-0.7468241328124271)<1e-12
summary=table.groupby('n').agg(mean_estimate=('estimate','mean'),mean_standard_error=('standard_error','mean'),max_absolute_error=('absolute_error','max'))
table.to_csv('/artifacts/trials.csv',index=False)
fig,ax=plt.subplots(); ax.errorbar(summary.index,summary.mean_estimate,yerr=2*summary.mean_standard_error,fmt='o'); ax.axhline(reference); ax.set_xscale('log'); fig.savefig('/artifacts/convergence.png')
print(json.dumps({'reference':reference,'quadrature_error_estimate':quadrature_error,'trials':len(table),'total_samples':int(table.n.sum()),'summary':json.loads(summary.to_json()),'confidence_intervals_are_not_proof':True}))
""",
        ),
    ],
    "timeout-then-bounded-check": [
        ("timeout", "An unbounded loop cannot establish a convergence claim.", "while True: pass"),
        (
            "completed",
            "Replace the unbounded loop with a finite geometric sum and an analytic remainder bound.",
            """import json
import numpy as np
n=40; ratio=0.5
partial=float(np.sum(ratio**np.arange(n)))
bound=ratio**n/(1-ratio)
assert abs(2-partial)<=bound and bound<2e-12
print(json.dumps({'terms':n,'partial_sum':partial,'remainder_bound':bound,'infinite_limit_requires_argument':True}))
""",
        ),
    ],
}


def review(cycle: int, method: str, status: str) -> dict:
    return {
        "assessment": "continue",
        "stop_reason": "recoverable_objection",
        "response": f"Observed execution status {status}. {method} This is finite evidence; neither a timeout nor a floating-point result proves or refutes a general mathematical claim.",
        "objections": [
            "Check numerical accuracy and assumptions against the source, not the exit code alone."
        ],
        "remaining_obligations": ["Establish the scope of the claim beyond the tested cases."],
        "next_question": method,
        "objective_status": "partial",
        "solution_claim": "A bounded experiment produced inspectable evidence.",
        "argument_summary": "The saved source, status, diagnostics and output delimit what was actually observed.",
        "assumptions_reviewed": [
            "Synthetic inputs and fixed seeds do not represent arbitrary populations."
        ],
        "proof_obligations": ["Separate finite evidence from general mathematical reasoning."],
        "unresolved_objections": [],
        "supporting_cycles": list(range(1, cycle + 1)),
        "verification_status": "incomplete",
        "strategy_contribution": "productive",
        "contribution_rationale": "The experiment or its diagnosed failure supplies a specific next step.",
        "cross_strategy_relations": [],
    }


async def run_case(root: Path, name: str, experiments: list) -> dict:
    path = root / f"{name}-{uuid4().hex[:8]}.sigma"
    view = initialize_project(
        path, name, "Investigate the computational claim and its limitations."
    )
    strategy = create_strategy(
        path, "Discriminating numerical experiments", experiments[0][1]
    ).project.strategies[0]
    limits = research_sessions.get_limits(str(path))
    limits.update(research_rounds=len(experiments), model_calls=2 * len(experiments))
    limits = research_sessions.save_limits(str(path), limits)
    credential = {
        "identity": "fixture-account",
        "mode": "api_key",
        "token": "fixture-only",
        "status": "connected",
    }
    config = {"available": True, "model": "gpt-6.1-sol", "reasoning_effort": "high"}
    inspected = []

    async def handler(request):
        payload = json.loads(request.content)
        context = json.loads(payload["input"])
        cycle = context["cycle"]
        status, method, code = experiments[cycle - 1]
        assert "/artifacts" in research_sessions.INVESTIGATOR_GUIDANCE
        if payload["text"]["format"]["name"] == "research_investigator":
            if cycle > 1:
                assert (
                    context["prior_artifacts"][-1]["investigator_output"]["python_execution"]
                    == inspected[-1]
                )
                assert context["question"] == experiments[cycle - 1][1]
            result = {
                "claim": "The experiment tests the current hypothesis.",
                "method": method,
                "assumptions": ["Inputs are finite and self-contained."],
                "evidence_status": "Proposed computation; await captured result.",
                "open_obligations": ["Interpret numerical and operational limitations."],
                "python_code": code,
            }
        else:
            output = context["investigator_output"]
            execution = output["python_execution"]
            assert output["python_code"] == code == execution["source"]
            assert execution["status"] == status, execution
            assert (
                execution["session_id"] == context_session[0]
                and execution["strategy_id"] == strategy.id
                and execution["cycle"] == cycle
            )
            assert get_execution(path, execution["id"]) == execution
            if status == "completed":
                assert execution["exit_code"] == 0
                json.loads(execution["stdout"])
            elif status == "failed":
                assert "Singular matrix" in execution["stderr"]
            inspected.append(execution)
            next_method = (
                experiments[cycle][1]
                if cycle < len(experiments)
                else "Explain which general claims still need an argument."
            )
            result = review(cycle, next_method, status)
        return httpx.Response(
            200,
            json={
                "status": "completed",
                "output": [
                    {
                        "type": "message",
                        "content": [{"type": "output_text", "text": json.dumps(result)}],
                    }
                ],
            },
        )

    context_session = []
    with (
        patch.object(research_sessions, "auth_context", new=AsyncMock(return_value=credential)),
        patch.object(research_sessions, "configuration", new=AsyncMock(return_value=config)),
        patch(
            "sigma.research_sessions.httpx.AsyncClient",
            side_effect=lambda **kwargs: REAL_CLIENT(
                transport=httpx.MockTransport(handler), **kwargs
            ),
        ),
    ):
        started = await research_sessions.start_session(
            str(path),
            strategy.id,
            str(uuid4()),
            view.project.id,
            credential["identity"],
            expected_limits=limits,
        )
        context_session.append(started["id"])
        for _ in range(6000):
            session = research_sessions.get_session(str(path), started["id"])
            if session["status"] in {"ended", "failed", "stopped", "paused", "completed"}:
                break
            await asyncio.sleep(0.01)
        else:
            raise AssertionError("Research workflow exceeded the evaluation deadline")
    assert session["status"] == "ended" and len(session["artifacts"]) == len(experiments), session
    for artifact, execution in zip(session["artifacts"], inspected, strict=True):
        assert artifact["investigator_output"]["python_execution"] == execution
        assert artifact["objective_review"]["verification_status"] == "incomplete"
        for metadata in execution["artifacts"]:
            content, _ = get_execution_artifact(path, execution["id"], metadata["filename"])
            assert hashlib.sha256(content).hexdigest() == metadata["sha256"]
    result = {
        "case": name,
        "session_id": session["id"],
        "statuses": [item["status"] for item in inspected],
        "executions": [
            {
                "id": item["id"],
                "duration_ms": item["duration_ms"],
                "stdout": item["stdout"],
                "artifacts": item["artifacts"],
            }
            for item in inspected
        ],
    }
    print(json.dumps(result), flush=True)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    with TemporaryDirectory(prefix="sigma-scientific-evaluation-") as temporary:
        root = args.output_dir or Path(temporary)
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        results = []
        for name, experiments in CASES.items():
            results.append(asyncio.run(run_case(root, name, experiments)))
        (root / f"summary-{uuid4().hex[:8]}.json").write_text(
            json.dumps(
                {"provider": "scripted fixture; no model calls", "results": results}, indent=2
            )
            + "\n"
        )
        print(f"PASS {len(results)} scientific workflows; evidence root: {root}")


if __name__ == "__main__":
    main()
