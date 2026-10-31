# Source-derived MindRouter break-even envelope (not an experiment on federation)

**2026-10-31 · Independent ChatGPT research note for PR #395, support PR #396**

This is a reproducible *derived finding* using quantities reported in a real campus deployment, not invented workload data. It is **not** a measurement of scientific-task quality, a matched comparison with commercial LLMs, a university total-cost study, or a SIGMA Investigator/Skeptic run. It does not establish whether cross-campus federation is worthwhile.

**Primary source:** Lucas Sheneman, *MindRouter: Open-Source LLM Inference Gateway for Institutional AI Sovereignty*, PEARC'26, [author-hosted paper](https://ai4ra.uidaho.edu/wp-content/uploads/2026/04/Sheneman_MindRouter_PEARC26_Short_Paper.pdf), DOI [10.1145/3785462.3815861](https://doi.org/10.1145/3785462.3815861). In §4, the author reports **872,997,430 tokens** over a **17-day period in March 2026**, about **275 kWh/day including facility overhead under normal operation**, and **$4,027–$11,896** of estimated API-equivalent spend for that token mix. The normal daily energy estimate is not separately demonstrated to be a meter reading *for those exact 17 days*; it is an approximate normalization. The API dollar range is a price-based proxy, **not an invoice or same-task quality result**.

## Calculation and conditional result

- At the paper's approximate normal daily energy, **17 × 275 = 4,675 kWh**. The 17-day token volume corresponds to approximately **186,737 tokens/kWh**, or **5.355 Wh per 1,000 processed tokens**. This is *system-level, workload-mix-dependent* energy normalization, not a per-model efficiency estimate.
- At an **illustrative** electricity tariff of **$0.12/kWh** (not claimed as Idaho's actual tariff), electricity is **$561** for the period, or **$0.643 per million tokens**. The paper's price-based API equivalents correspond to **$4.61–$13.63 per million tokens**. Neither side accounts for task-quality differences; the local number omits all non-electric costs.
- Let `r = P(local useful success) / P(API useful success)` for the **same representative tasks**. Let `H` be all *non-electric* local cost during the period. Local cost per useful success is no higher than API cost per useful success only if **`H <= r × API_proxy_cost - $561`**. This formula assumes matched task demand and that the paper's token mix can be priced equivalently.
- With **hypothetical r=1.00** (equal quality), the break-even *allowable non-electric cost* is **$3,466–$11,335 over 17 days** (**$203.88–$666.76/day**, or roughly **$6,201–$20,281 per 365/12-day month**). With **r=0.75**, it falls to **$2,459.25–$8,361**; with **r=0.50**, to **$1,452.50–$5,387**. These are thresholds, not estimates of actual hardware/staff spending.
- Under the low API-price endpoint, if `r < $561/$4,027 ≈ 0.1393`, the electricity alone would exceed the quality-adjusted proxy, even before capital or labor. At the high endpoint the analogous threshold is **0.0472**. These are algebraic thresholds, **not measured success rates**.
- A defensible *conditional* conclusion is therefore: published energy and throughput figures do **not** establish the claimed cost advantage after fully loaded TCO and usefulness adjustments. They instead constrain how large non-electric operating costs could be at each hypothesized quality ratio.

### Why the result is not yet a scientific comparative outcome

The MindRouter paper establishes an actual *on-campus gateway deployment*, not an implemented federation. Its deployed WDRR scheduling, RBAC, local GPU observability and protocol translation are baseline mechanisms. Neither the paper nor this note measures comparable task completion rates between local models and paid frontier APIs, p95 latency, failed attempts, burst congestion, capital purchase price, utilization-based amortization, staff burden, per-dataset governance costs, cross-campus legal agreements or federation availability. The estimated API range uses model and provider assumptions; the exact price/mix is not a quality-matched control.

The scientific question for a future 90-day pilot is whether a **policy-constrained hybrid/federation** increases *measured useful completions per dollar* and preserves data sovereignty/fairness under failures, **relative to an optimized local-only and optimized single-campus hybrid**. The 17-day observation supplies an external energy/token normalization and a falsifiable break-even target, not an answer to that question.

### Reproduction

```sh
python scripts/mindrouter_empirical_envelope.py
python scripts/mindrouter_empirical_envelope.py --tariff 0.20 --success-ratio 0.75
python -m unittest discover -s tests -p 'mindrouter_empirical_envelope.py' -v
```

All calculations are offline standard-library Python. No provider calls, real user data, paid services or production actions. **Provenance:** reported quantities = token count, period, approximate daily energy, estimated API-equivalent price range; derived quantities = energy normalization and break-even algebra; illustrative parameters = electricity tariff and useful-success ratio.
