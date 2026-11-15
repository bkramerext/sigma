# Sovereign AI economics: independent, reproducible counterexamples

**Status (2026-10-31):** Scenario analysis, not an empirical university cost study, not a completed SIGMA Investigator/Skeptic run, and not a paper. All workload counts, success rates, hardware costs, staffing, GPU-hour estimates, partner economics and provider-call amplification are **invented** and must be validated. The calculations below are conditional results, not observations. No provider calls, usage charges or production deployment.

## Primary evidence and careful attribution

Lucas Sheneman, [*MindRouter: Open-Source LLM Inference Gateway for Institutional AI Sovereignty*](https://ai4ra.uidaho.edu/wp-content/uploads/2026/04/Sheneman_MindRouter_PEARC26_Short_Paper.pdf), PEARC '26, [DOI 10.1145/3785462.3815861](https://doi.org/10.1145/3785462.3815861), reports a campus-owned inference gateway with protocol translation, fair-share Weighted Deficit Round Robin scheduling, quota controls, RBAC, audit and GPU monitoring. The University of Idaho deployment is reported as 13 nodes, 40 GPUs and 64 models. The published 17-day March 2026 observation was 872,997,430 processed tokens and approximately 275 kWh/day including overhead, with $4,027–$11,896 estimated comparable commercial API charges.

This **does not demonstrate** that MindRouter implements multi-campus federation or automatic frontier-model routing. Those are **proposals** to evaluate. The published cloud equivalence is an *estimate based on token pricing*, not same-task quality equivalence or full TCO. In particular, 17 × 275 = **4,675 kWh**; at a purely illustrative $0.12/kWh this represents **$561 electricity**, excluding GPU purchase/depreciation, staff, connectivity, facilities, repair, queueing, replacement, security and institutional governance. One cannot infer full TCO savings or research effectiveness solely from the article's energy/API comparison.

The only external commercial *price input* in the scenario is the OpenAI [GPT-5.4 model card](https://developers.openai.com/api/docs/models/gpt-5.4), which listed **$2.50 per million uncached input tokens and $15 per million output tokens** on 2026-10-31. These rates do not confer permission to send university data, and ignore actual contract, residency premium, taxes, rate limits, cache, context-tier and tool fees. Success probabilities are invented, **not** measurements of GPT-5.4.

## Reproducible method

Run the standard-library script on the checked-in hypothetical case:

    python scripts/sovereign_cost_model.py research/sovereign_scenario_hypothetical.json

It evaluates *fixed, declared allocations*, not an optimal router. It enforces declared allowed destinations, GPU-hour capacity (campus and partner), task capacity (frontier), external budget *in expected forecast*, and at least 95% task coverage. It compares monthly fully loaded cost (including amortized capital and staff), incremental cost after separately marked sunk assets, external billed charges, successful useful tasks and effective cost per completion. The reported maximum-attempt charge is a **scenario bound**, not enforceable credit reservation. Destination permission, academic performance, tail latency and real-world queue behavior are external required evidence.

The scenario has 120 active researchers and 1,150 monthly tasks: 600 low-risk, 300 complex scientific, 250 restricted. The restricted tasks can only be processed at their home campus (including all associated derived content). The campus is assumed to already have 1,600 *effective* available GPU-hours per month and has **$15,783 fixed monthly fully loaded cost**, with $10,133 of that marked sunk. Provider cap is illustrative **$4,000/month**. Partner capacity 450 available GPU-hours/month at invented transfer price $5/GPU-hour, plus explicit inter-campus operational overhead.

### Calculated base case

| Plan | Baseline feasible? | Tasks served | Expected useful successes | Full monthly cost | Cost / useful success | Expected frontier bill |
|---|---|---:|---:|---:|---:|---:|
| Campus only | Yes | 1,150 | 787.00 | $15,898.00 | $20.20 | $0 |
| Frontier only | **No: 250 restricted tasks unserved** | 900 | 819.00 | $3,854.40 | $4.71* | $3,554.40 |
| Campus + approved frontier | Yes | 1,150 | 891.55 | $19,396.69 | $21.76 | $2,627.19 |
| Federation + frontier | Yes | 1,150 | 882.40 | $22,831.47 | $25.87 | $1,750.47 |

*Frontier-only's seemingly low unit cost is **not an implementable full-coverage answer**: 21.7% of the task mix cannot use it under the declared data policy. There is no policy-violating fallback.*

- **Conditional counterexample against federation-first:** At baseline federation costs **$3,434.78 more per month** and achieves **9.15 fewer expected successful tasks** than the simpler campus + frontier plan. This makes the specified federation allocation Pareto-dominated in cost and expected useful completions. It could still improve unmodeled outage or vendor-dependence risk; the scenario does not prove universal inferiority.
- **Quality can be worth money without lowering cost per success:** Hybrid versus campus-only yields **104.55 additional expected successes** for **$3,498.69** monthly premium, or **$33.46 per incremental expected success**. Whether that is worth paying requires *measured* scientific utility, time saved, reproducibility and error criticality.
- **Sunk versus full TCO matters:** Campus-only incremental $5,765/month; simple hybrid $9,263.69; federation $12,698.47. Those numbers deliberately remove only explicitly tagged sunk portions. In a new-build decision, those costs are real and must be restored.
- **Cheap cloud-only is not a sovereign solution:** It fails the predefined coverage target even before considering vendor retention, derivatives, contract review or policy changes.

### Price sensitivity: the result can reverse on feasibility

Hold task mix, success and allocations constant; multiply only frontier token rates (fixed per-task external overhead unchanged). Plans have a hard projected external cap, but **not an enforced runtime billing ceiling**.

| Frontier token price | External cap | Hybrid projected bill / feasible | Federation projected bill / feasible |
|---|---:|---|---|
| 0.5× | $2,000 | $1,320.72 / yes | $879.74 / yes |
| 1× | $2,000 | $2,627.19 / **no** | $1,750.47 / yes |
| 1× | $4,000 | $2,627.19 / yes | $1,750.47 / yes |
| 2× | $4,000 | $5,240.13 / **no** | $3,491.94 / yes |
| 2× | $8,000 | $5,240.13 / yes | $3,491.94 / yes |

Thus a federation could preserve *forecast* coverage under a fixed provider spending cap when a static hybrid cannot. That does not establish a win: reoptimizing the hybrid splits, delaying low-value tasks or using a different authorized model may also solve the constraint with less overhead. Under 2× price and $4,000 expected cap, federation's **maximum-attempt exposure exceeds that cap**, so a real hard-budget admission controller would still have to defer or reject some work under high retry conditions. With zero external budget, the frozen hybrid and federation plans are infeasible until reallocated; campus-only remains feasible.

## What must be measured before drawing real conclusions

1. **Policy-first routing and institution autonomy.** Classify prompt, output, logs, cache, embedding, tool calls, metadata and derivatives. A cloud failure, WAN partition, cost cap, revoked access or stale policy must *never* trigger an unapproved destination. Approval is per campus/contract/dataset, not determined by model quality.
2. **Paired task quality:** blind scoring on identical real, IRB-authorized representative workloads for local, partner and approved frontier systems; version pinning, sample sizes and uncertainty intervals, calibration across fields and modalities, reproducibility and serious-error rates.
3. **Whole-system cost:** per-GPU depreciation, actual power/PUE, memory residency and queueing, model size, campus staff, procurement, support, cold start, cross-campus egress, partner settlement, vendor charges for failed/retried/agentic calls, cache, tokens and tools, data-residency surcharge.
4. **Resource sharing and fairness:** per-project and per-department quotas; interactive vs batch SLO and starvation; weighted deficit scheduling under mixed token costs, cancellation, stolen capacity and campus-to-campus disputes.
5. **Runtime hard spending:** reserve a bounded maximum before *each* external call, reconcile ambiguous charged timeouts, enforce global and departmental caps atomically, and never automatically escalate spend on retry.
6. **Controlled experiment:** 30 days shadow traces and classification; 30 days blinded paired quality/capacity evaluation; 30 days explicitly authorized low-risk capped pilot with failure drills. Stop on data-policy escapes, unaccounted bills or unacceptable reliability/operating burden.

**Research implication:** The interesting hypothesis is not “federate everything.” It is: *under what measured capacity, scientific quality, trust and external-budget regime does the value of cross-campus access exceed its security, operations and governance burden?* This independent calculation supplies reproducible counterexamples and measurement targets, **not a conclusive answer**. The final SIGMA research paper must draw on genuinely saved Investigator/Skeptic evidence and clearly separate hypotheses from independently measured observations.

Run tests with:

    python -m unittest discover -s tests -p 'sovereign_cost_model.py' -v

The implementation has no external dependencies, provider calls, cloud operations, or personal data.
