# Research effectiveness: proposed Increments 13–17

**Status:** Proposed, not authorized to incur paid provider costs. Prepared after adversarial review of 8–12. These are decision gates, not a quota of features. Do not resume Blue or claim unscripted validation from offline fixtures.

## Success standard

The goal is to demonstrate **better research per unit cost and time** than a strong, simpler single-role assistant. Mechanisms and green regression tests are prerequisites, not outcomes. Each experiment must produce reproducible artifacts and a falsifiable decision. A tie or loss must lead to simplification or targeted diagnosis, not another automatic layer of orchestration.

### 13. Adversarial acceptance and reproducibility (engineering gate)
- Finish real Chrome checks for Simple and Advanced Outcome, desktop and narrow mobile, plus TXT/HTML/TeX ordering. Verify no visual regression, overflow or confusing evidence labels.
- Review history/retention, truncated source pointers, stale continuations, duplicate/conflicting execution statuses, and cross-strategy leakage. Fix high-severity cases and repeat full CI.
- **Exit:** accepted browser screenshots, exact-head green CI, defect log with severity and resolution. No paid calls.

### 14. Preregister blinded cross-domain comparison (design gate)
- Choose four to six bounded, answer-free tasks spanning experimental design, source criticism, constrained engineering/scenario reasoning, and formal/mathematical reasoning. Include both evidence-present and evidence-withheld variants where attribution matters.
- Freeze prompts, tools, budgets, reasoning effort, model, context, scoring rubrics, randomization, exclusion rules, independent keys and task hashes before any outputs are observed. Do not allow either arm access to answer keys.
- Compare SIGMA Investigator/Skeptic with a single-role self-review baseline on identical model and total input/output/model-call/time ceilings. Track actual cost and wall time.
- **Exit:** reproducible sealed protocol, precommitted pass/fail thresholds and estimated spend, explicit human approval of model/provider/account/cost cap before execution.

### 15. Small unscripted pilot (requires authorization)
- Run only the approved bounded pilot; preserve complete request/response, tool outputs, source provenance, usage, elapsed time, failures and anonymized results.
- Score blind for correctness, objection uptake, evidence integrity, calibration, useful next experiment, and cost. Count fabricated computations and concealed decisive objections as integrity failures.
- **Exit:** publish all outcomes, including losses and abstentions. Do not call a small positive pilot a proof of general advantage.

### 16. Causal ablations and repair (conditional)
- If pilot shows an advantage, disable exactly one mechanism at a time (Skeptic review, saved follow-up, source readiness, provenance display) under matched budgets and test whether benefit survives.
- If SIGMA ties or loses, isolate failure modes and simplify. No new mechanism without a demonstrated deficiency, explicit hypothesis and discriminating test.
- **Exit:** evidence-backed keep/change/remove decisions, not merely added features.

### 17. Replication and product decision (requires authorization)
- Replicate on unseen tasks and another domain mix with blinded scoring. Compare gains to added cost/latency and assess stability across task types.
- Include one genuinely extended, multi-session investigation with real unscripted model work and an independently reviewable record of what changed between sessions: useful new results, resolved objections, false leads not repeated, or measured failure to progress. This is an additional longitudinal gate, not a substitute for blinded short-task comparisons.
- **Exit:** decide whether to promote SIGMA multi-agent research as demonstrably beneficial, constrain claims to supported domains, or default to simpler architecture.

## Evidence hierarchy and stop rules

- **Engineering:** exact-code tests, persisted dispatch, CI and real Chrome establish behavior, not research quality.
- **Research:** only blinded, unscripted, matched-budget comparisons can support claims of advantage.
- Stop on contamination, exceeded approved cost, asymmetric tool access, incomplete provenance or irreproducible evaluation. Preserve negative results.
- Keep RH and familiar math/graph samples as supplementary controls, not the entire benchmark.
