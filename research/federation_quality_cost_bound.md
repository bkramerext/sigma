# A bound on federation's quality-adjusted cost advantage (frozen scenario)

**2026-10-31 · Analytical result from a fully synthetic scenario; not an empirical finding.** This note is independent support for [PR #395](https://github.com/bkramerext/sigma/pull/395) via [PR #396](https://github.com/bkramerext/sigma/pull/396). The inputs are in research/sovereign_scenario_hypothetical.json and the deterministic accounting rules are in scripts/sovereign_cost_model.py. Nothing here is a measured university success rate or proof about real-world federation. No provider calls.

## Question

For the **frozen allocations** in the synthetic case, could the federation plan outperform the simpler campus-plus-approved-frontier hybrid in **fully loaded dollars per useful completed task** merely by obtaining free partner GPU-hours and raising both partner model success probabilities all the way to 100%?

## Bound

Let C_H = $19,396.69, S_H = 891.55 expected useful completions per month for the simple hybrid. Let C_F(5) = $22,831.47, S_F = 882.40 for the federation with partner transfer price p=$5/GPU-hour, success q_low=0.85 on 150 partner low-risk tasks and q_complex=0.65 on 90 partner complex tasks.

The partner consumes 150×0.2 + 90×3.5 = 345 GPU-hours/month. Holding all other quantities fixed, with partner price p≥0 and success probabilities q_low,q_complex∈[0,1]:

    C_F(p) = 22,831.47 + 345(p - 5)
           ≥ 21,106.47.

    S_F(q_low,q_complex)
       = 882.40 + 150(q_low - 0.85) + 90(q_complex - 0.65)
       ≤ 936.40.

For every admissible p,q_low,q_complex in this restricted family, since all costs and completions are nonnegative,

    C_F(p) / S_F(q_low,q_complex)
       ≥ 21,106.47 / 936.40
       = $22.5400 per expected useful completion.

Yet the fixed hybrid costs 19,396.69 / 891.55 = $21.7561 per expected useful completion. Thus **even a free, perfectly successful partner does not make the frozen federation allocation more cost-effective than this fixed hybrid**, given the assumed extra $2,600/month federation-operations overhead and all other frozen parameters.

The result is *not* a claim that a federation is never economically optimal. It only proves an impossibility **within the declared, frozen allocation and accounting assumptions**. Changing the federation's governance cost, task allocation, task mix, latency value, outage losses, external budget, or actual model quality can change the comparison. The bound says nothing about sovereignty gains, resilience, vendor independence or fairness, which need separate metrics and institutional authorization.

## Necessary change in the frozen scenario

At p=0 and both partner success probabilities 1.0, federation cost would be $21,106.47, and useful successes 936.40. To equal the hybrid's fully loaded cost per success at that extreme requires total federation cost at most:

    936.40 × (19,396.69 / 891.55) = $20,372.45.

That is a **further $734.02/month** reduction in fixed federation overhead (or an equivalent cost reduction elsewhere), beyond giving away the partner compute. At the *baseline* p=$5/GPU-hour, even perfect partner task success would require **$2,459.02/month** overhead reduction, leaving at most **$140.98/month** of the assumed $2,600 federation-specific overhead. These are necessary thresholds for this exact allocation, not operational forecasts.

## Why this is a useful research result

It prevents a weak argument that "if partner models are good enough or spare GPU-hours are donated, federation must win." Under a fully loaded accounting and an explicit fixed control plane, those two improvements alone are insufficient in the example. A serious experiment must measure the additional federation overhead, re-optimize **both** candidate plans under identical policy and budget constraints, and separately value any sovereignty/resilience benefits. The fact that the **simple hybrid itself has not been optimized** makes the federation's burden of proof stronger, not weaker.

## Independent reproduction

The baseline numbers can be reproduced without paid inference:

    python scripts/sovereign_cost_model.py research/sovereign_scenario_hypothetical.json

The inequalities use only the partner fractions, GPU-hour coefficients, and unit-success upper bounds from that checked-in JSON. A small independent arithmetic check of the extremal values was performed by the coordinator with Python 3.13 on 2026-10-31; the **committed test suites remain unexecuted** in the current environment. This is an *analytical sensitivity result* on invented inputs, not a genuine saved SIGMA Investigator/Skeptic run, and must not be presented as one.
