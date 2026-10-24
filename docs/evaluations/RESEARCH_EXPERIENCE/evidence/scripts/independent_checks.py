"""Evaluator checks only. No SIGMA runtime or provider invoked."""
import json
from pathlib import Path
# Enumerate independently of saved DP implementations.
a=[]
for n in range(17):
 subsets=[tuple(i+1 for i in range(n) if mask&(1<<i)) for mask in range(1<<n)]
 a.append(sum(all(y-x>1 for x,y in zip(s,s[1:])) and sum(s)%3==0 for s in subsets))
# Exact arithmetic in Z[w]/(w^2+w+1), represented as integer pairs.
def add(x,y):return (x[0]+y[0],x[1]+y[1])
def neg(x):return (-x[0],-x[1])
def mul(x,y):return (x[0]*y[0]-x[1]*y[1],x[0]*y[1]+x[1]*y[0]-x[1]*y[1])
def mm(a,b):return [[add(mul(a[i][0],b[0][j]),mul(a[i][1],b[1][j])) for j in range(2)] for i in range(2)]
one=(1,0);zero=(0,0);w=(0,1);w2=(-1,-1)
phases=[[[one,q],[one,zero]] for q in [w,w2,one]]
products=[]
for offset in range(3):
 block=mm(phases[(offset+2)%3],mm(phases[(offset+1)%3],phases[offset]));tr=add(block[0][0],block[1][1]);det=add(mul(block[0][0],block[1][1]),neg(mul(block[0][1],block[1][0])));products.append({'phase':offset,'matrix':block,'trace':tr,'determinant':det});assert tr==one and det==(-1,0)
result={'provenance':'Independent evaluator Python check, not a SIGMA research session or proof checker.','enumeration_a_0_to_16':a,'a12':a[12],'false_short_rule_at_n2':{'lhs':a[5],'rhs':a[4]+a[2]},'candidate_recurrence_residuals':[a[n+12]-5*a[n+9]+2*a[n+6]+5*a[n+3]+a[n] for n in range(5)],'exact_phase_products':products,'gap_explanation':{'incorrect_total_at_k2':1+1,'required_k_squared_at_k2':4,'correct_offset_total_at_k2':1+3},'maximum_regions_intersections':[{'i':i,'k':k,'x':-(i+k),'y':-i*k} for k in range(2,5) for i in range(1,k)]}
assert a[12]==128
Path('docs/evaluations/RESEARCH_EXPERIENCE/evidence/independent-checks.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
