# Re-optimizing the four university routing architectures: a constrained LP result

**2026-10-31 · independent offline sensitivity study for #394 / support PR #396.** All workloads, prices except the explicitly cited public API price input, success probabilities, capacities and federation overhead are **synthetic assumptions** from the checked-in scenario. This is not observed university performance, a SIGMA Investigator/Skeptic run, or a deployment decision. The local solver was executed in Python 3.13 with SciPy 1.17.0; the subsequently committed script has not yet been separately executed in a checked-out repository. No AI-provider calls or paid usage.

## Why this analysis changes the interpretation

The earlier fixed-allocation comparison found that the frozen federation allocation costs more and yields fewer expected successful tasks than the frozen hybrid allocation. **That is not a fair claim of optimality**: either plan might improve by choosing a different allocation. The stronger question is: *after each architecture independently optimizes its own routing decisions, does federation buy any extra useful research completions, and at what cost?*

We solved a **continuous linear-programming relaxation** for each architecture under exactly the same 1,150 monthly task mix, per-task success probabilities, GPU-hour capacity, $0/$2,000/$4,000 frontier caps, and policy-approved destinations. Full coverage is required; restricted tasks can only run at their home campus. The decision variables are the numbers of tasks assigned to each allowed route. Constraints enforce each workload's demand, per-route capacity, and projected external charges. Objective A maximizes expected successful useful tasks; Objective B minimizes full cost given an expected-success floor. These are *separate* objectives: the max-success result is not necessarily a cost-minimal plan, and no single number is a universal preference ranking.

The linear program permits fractional task counts, so its values are **optimistic upper bounds** for indivisible work. It assumes independently additive success rates and costs, no queuing or latency interactions, and a forecast budget rather than a hard per-call reservation. It does not evaluate scientific validity of the assumed quality rates or enforce real data classification.

## Solved maximum-success frontier

| External provider cap/month | Campus only: expected successes / full cost | Campus + frontier: expected successes / full cost | Federation + frontier: expected successes / full cost |
|---|---|---|---|
| $0 | 787.00 / $15,898 | 787.00 / $16,798 | **828.57 / $21,578.57** |
| $2,000 | 787.00 / $15,898 | **936.63 / $18,721.34** | **968.77 / $23,558.49** |
| $4,000 | 787.00 / $15,898 | **994.00 / $20,262.40** | **994.00 / $22,862.40** |

The API-only architecture cannot serve the 250 restricted tasks, so it is infeasible for this full-coverage study. This is a policy exclusion, not a quality or pricing judgment. Every plan's fixed costs are included even when a route is unused, because an enabled, maintained federation control plane has an operating cost.

### Finding 1: federation buys an expensive quality increment when cloud spend is tightly capped

At a $2,000/month frontier cap, the optimized hybrid sends all 600 low-risk tasks and 166.575 complex tasks to the approved frontier API, with the other 133.425 complex and all 250 restricted tasks on campus. Its expected success count is **936.6273**.

Federation uses the same external allocation but transfers **128.5714 complex tasks** (450 partner GPU-hours at 3.5 GPU-hours/task) from home-campus inference to the partner, increasing expected success by **32.1429** to **968.7702**. This costs an additional **$4,837.14/month** fully loaded, or approximately **$150.49 per incremental expected successful task**. The increment comprises $2,600 federation governance overhead and $2,237.14 additional partner variable costs net of displaced campus work. A research university might pay for that increment if the tasks have sufficient measured value; the scenario does not establish that value.

The result also exposes a potential **research-governance tradeoff**: access to partner capacity can improve forecast quality without raising the *external provider* bill, but the partner is still costly and requires policy approvals, contracts, audit, cross-campus security and service-level evidence.

### Finding 2: at $4,000/month, federation offers no additional success in this model

The approved frontier can serve all 900 unrestricted tasks for **$3,554.40** in forecast provider charges. The restricted 250 remain local. Both optimized architectures reach the same modeled upper bound of **994 expected successful tasks**. Federation's $2,600/month additional fixed overhead yields no modeled quality benefit, and the optimizer leaves partner capacity unused. It is **strictly dominated in this cost/expected-success projection** by the simpler hybrid, although resilience, vendor dependence, fairness, locality, latency, and institutional sovereignty are not represented in this objective.

At a $0 external cap, federation instead increases expected successes from 787 to 828.57 by using the partner's 450 GPU-hours; that costs **$5,680.57/month** above campus-only, or **$136.65 per incremental expected success**. The hybrid cannot improve on campus-only with no external calls.

### Finding 3: a lower-cost target may dominate maximum-quality routing

At an **expected 900 successful tasks** target, the minimum-cost hybrid allocation has modeled full monthly cost **$17,737.52** and forecast frontier bill **$1,007.66**, regardless of whether the allowed cap is $2,000 or $4,000. The federation architecture can choose the same allocation, but costs **$20,337.52** because of its additional fixed overhead. This is why a cost/quality **frontier**, not a single optimized number, is necessary for a defensible architecture decision.

## Formulation and reproducibility

Let x(w,r) be the number of tasks of workload w sent to approved route r, d(w) demand, q(w,r) useful-completion probability, c(w,r) expected variable cost, g(w,r) capacity units, K(r) route capacity, and B external budget. For each architecture solve

    maximize sum_{w,r} q(w,r) * x(w,r)
    subject to:
      sum_r x(w,r) = d(w)                   for each workload w
      sum_w g(w,r) * x(w,r) <= K(r)          for each route r
      sum_{w,r in external} c(w,r)*x(w,r) <= B
      x(w,r) >= 0, with unapproved pairs absent

For a quality floor Q, instead minimize the sum of c(w,r)*x(w,r) subject to the same constraints and sum q(w,r)*x(w,r) >= Q, then add the architecture's fixed monthly costs.

The optional, research-only script is research/sovereign_lp_optimization.py. It reads the same checked-in JSON and requires SciPy separately from SIGMA's runtime dependencies:

    python research/sovereign_lp_optimization.py research/sovereign_scenario_hypothetical.json --budget 2000
    python research/sovereign_lp_optimization.py research/sovereign_scenario_hypothetical.json --budget 4000
    python research/sovereign_lp_optimization.py research/sovereign_scenario_hypothetical.json --budget 2000 --min-success 900

The committed script was executed on the committed JSON with a transient SciPy 1.17.0 environment (`uv run --locked --with scipy==1.17.0`). Runs at $0, $2,000 and $4,000 caps reproduced the table exactly; the $2,000 / 900-success-floor run reproduced $17,737.516279 hybrid cost, $20,337.516279 federation cost, and $1,007.655814 frontier bill. SciPy is not added to SIGMA's locked dependencies. This is a deterministic optimization on invented inputs, not independent model evaluation. To move beyond a conditional result, measure real paired task quality, campus and partner service-time distributions, cloud bills including retries/cache/tools, GPU depreciation/utilization, fairness, latency, policy controls, outages and opportunity cost. Validate integer-task allocations, uncertainty bounds and demand seasonality before operational recommendations.

**Conclusion:** The strongest conditional finding is not "federation always loses." Under the same synthetic assumptions, federation's *incremental scientific utility* is **zero** with an adequate $4,000 cloud cap but **positive and costly** with $0–$2,000 caps. A real decision depends on the measured value of that utility, institutionally approved data routes and the cost of managing the additional trust boundary.
