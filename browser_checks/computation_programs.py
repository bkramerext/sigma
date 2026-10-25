"""Evaluator-authored bounded programs, no precomputed answers or hidden oracle.

Returned as Investigator proposals; only SIGMA's real isolated runtime executes
these during the session. Separate evaluator oracles use different algorithms.
"""

SUBSET = """import json
states={(0,0):1}
values=[1]
for i in range(1,19):
    nxt={}
    for (r,last),count in states.items():
        nxt[(r,0)]=nxt.get((r,0),0)+count
        if not last:
            key=((r+i)%3,1)
            nxt[key]=nxt.get(key,0)+count
    states=nxt
    values.append(sum(c for (r,last),c in states.items() if r==0))
"""
SUBSET_FIRST = (
    SUBSET
    + """witness=None
for n in range(13):
    actual=values[n+6]
    predicted=4*values[n+3]+values[n]
    if actual!=predicted:
        witness={"n":n,"actual":actual,"predicted":predicted,"residual":actual-predicted}
        break
result={"test":"six_step_candidate","values":values,"witness":witness,"n_max":18,"scope":"finite exact counts; no global recurrence or limit proof"}
print(json.dumps(result,sort_keys=True))
open('/artifacts/observation.json','w').write(json.dumps(result,sort_keys=True))
"""
)
SUBSET_NEXT = (
    SUBSET
    + """residuals=[values[n+6]-4*values[n+3]-values[n] for n in range(13)]
result={"test":"residue_separated_residuals","residuals_by_n_mod_3":{str(r):residuals[r::3] for r in range(3)},"scope":"finite pattern only; derive an exact matrix identity and boundaries before extrapolating"}
print(json.dumps(result,sort_keys=True))
open('/artifacts/observation.json','w').write(json.dumps(result,sort_keys=True))
"""
)
GRAPH = """import json
from itertools import permutations
def acyclic(n,edges):
    incoming=[0]*n
    for u,v in edges:incoming[v]+=1
    ready=[u for u in range(n) if incoming[u]==0]
    seen=0
    while ready:
        u=ready.pop();seen+=1
        for x,v in edges:
            if x==u:
                incoming[v]-=1
                if incoming[v]==0:ready.append(v)
    return seen==n
def reaches(n,edges,start,target):
    seen={start};todo=[start]
    while todo:
        u=todo.pop()
        if u==target:return True
        for x,v in edges:
            if x==u and v not in seen:seen.add(v);todo.append(v)
    return False
"""
GRAPH_FIRST = (
    GRAPH
    + """n=3
possible=list(permutations(range(n),2))
witness=None;checks=0
for mask in range(1<<len(possible)):
    edges={edge for i,edge in enumerate(possible) if mask>>i&1}
    if not acyclic(n,edges):continue
    for u,v in possible:
        if (u,v) in edges:continue
        checks+=1
        candidate_accepts=(v,u) not in edges
        truth=acyclic(n,edges|{(u,v)})
        if candidate_accepts and not truth:
            witness={"edges_before":sorted(edges),"insert":[u,v],"candidate_accepts":candidate_accepts,"oracle_acyclic_after":truth}
            break
    if witness:break
result={"test":"reverse_edge_only_cycle_guard","n":n,"checks":checks,"witness":witness,"scope":"local insertion criterion only; no dynamic complexity result"}
print(json.dumps(result,sort_keys=True))
open('/artifacts/observation.json','w').write(json.dumps(result,sort_keys=True))
"""
)
GRAPH_NEXT = (
    GRAPH
    + """n=4
possible=list(permutations(range(n),2))
mismatch=None;checks=0
for mask in range(1<<len(possible)):
    edges={edge for i,edge in enumerate(possible) if mask>>i&1}
    if not acyclic(n,edges):continue
    for u,v in possible:
        if (u,v) in edges:continue
        checks+=1
        candidate_accepts=not reaches(n,edges,v,u)
        truth=acyclic(n,edges|{(u,v)})
        if candidate_accepts!=truth:mismatch={"edges_before":sorted(edges),"insert":[u,v]};break
    if mismatch:break
result={"test":"reachability_guard_finite_regression","n":n,"checks":checks,"mismatch":mismatch,"scope":"finite agreement is not a proof; update semantics, invariant and large-scale bounds remain open"}
print(json.dumps(result,sort_keys=True))
open('/artifacts/observation.json','w').write(json.dumps(result,sort_keys=True))
"""
)
SAGE = """import json
R.<z> = PolynomialRing(ZZ)
modulus=z^3-1
p0=R(1);p1=1+z
values=[int(p0[0]),int(p1[0])]
for n in range(2,19):
    pn=(p1+z^n*p0)%modulus
    values.append(int(pn[0]));p0,p1=p1,pn
witness=None
for n in range(13):
    actual=values[n+6];predicted=4*values[n+3]+values[n]
    if actual!=predicted:
        witness={"n":n,"actual":actual,"predicted":predicted,"residual":actual-predicted};break
result={"test":"sage_exact_weighted_polynomial_mod_z3_minus_1","values":values,"witness":witness,"scope":"independent finite exact method, not a general recurrence or limit proof"}
print(json.dumps(result,sort_keys=True,default=int))
open('/artifacts/observation.json','w').write(json.dumps(result,sort_keys=True,default=int))
"""
ERROR = 'raise RuntimeError("Deliberate evaluator failure before producing any observation")\n'
TIMEOUT = "while True:\n    pass\n"
RESTART = "import time\ntime.sleep(3)\n" + SUBSET_FIRST
for _source in [SUBSET_FIRST, SUBSET_NEXT, GRAPH_FIRST, GRAPH_NEXT, SAGE, ERROR, TIMEOUT, RESTART]:
    assert len(_source) < 4000
