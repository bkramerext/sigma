"""Evaluator-only exact checks. Never imported by transport or project context."""
import importlib.util
import json
from collections import Counter
from functools import lru_cache
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs/evaluations/increment_3'


def brute(n):
    polynomial=Counter()
    for mask in range(1<<n):
        if mask & (mask<<1): continue
        polynomial[sum(i+1 for i in range(n) if mask>>i&1)]+=1
    return polynomial

@lru_cache(None)
def gaussian(n,k):
    if k<0 or k>n:return Counter()
    if k==0:return Counter({0:1})
    # [n k]_q=[n-1 k]_q + q^(n-k)[n-1 k-1]_q.
    value=gaussian(n-1,k).copy()
    for exponent,count in gaussian(n-1,k-1).items():value[exponent+n-k]+=count
    return value

def main():
    counts=[]
    for n in range(19):
        poly=brute(n);counts.append(sum(v for exponent,v in poly.items() if exponent%3==0))
        formula=Counter()
        for k in range((n+1)//2+1):
            for exponent,count in gaussian(n-k+1,k).items():formula[exponent+k*k]+=count
        assert poly==formula,(n,poly,formula)
    assert counts[5]==5 and counts[4]+counts[2]==4 and counts[12]==128
    spec=importlib.util.spec_from_file_location('rh_exact',ROOT/'tests/rh_adversarial.py')
    rh=importlib.util.module_from_spec(spec);spec.loader.exec_module(rh);rh.main()
    result={'provenance':'Independent evaluator-only exact arithmetic; no provider or research-agent tool execution',
            'subset_counts_n_0_through_18':counts,'short_rule_counterexample':{'n':2,'a_n_plus_3':counts[5],'a_n_plus_2_plus_a_n':counts[4]+counts[2]},
            'a12':counts[12],'gaussian_q_k_squared':'Complete polynomial coefficients match explicit nonadjacent-subset enumeration for n=0..18. Gap removal shift k(k-1)/2 plus ordinary k-subset shift k(k+1)/2 totals k squared.',
            'global_recurrence':'Unproved by these checks','one_third_limit':'Unproved by these checks',
            'rh_oracle':'Existing tests/rh_adversarial.py exact rational polynomial F(s)=F(1-s), roots 1/2±i,1/4±1001i,3/4±1001i; all assertions and mutations pass. Symmetry of set does not force each element fixed; finite low-height checks insufficient.',
            'rh_scope':'The polynomial is NOT zeta and is NOT a counterexample to RH. It refutes the invalid logical deduction from listed premises alone.',
            'answer_key_boundary':'This script/output is evaluator-only, not included in initial RH Investigator context, strategy or project.'}
    (OUT/'independent-oracles.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
