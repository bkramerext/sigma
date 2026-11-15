# Coordinator independent primary-source check — MindRouter, not part of frozen baseline

**Checked:** 2026-11-01 ~03:45 PST. **Purpose:** external verification challenge for the existing Sovereignty paper's C1 and comparison baseline. **Important:** The frozen iteration-1 generator explicitly did **not** retrieve these sources. This coordinator check is **independent, post hoc research** and must not be misrepresented as source material the generator had seen. No saved project or paper was modified.

## Primary sources directly inspected

1. [MindRouter official documentation](https://mindrouter.ai/documentation.html), inspected 2026-11-01. This describes an on-premise inference gateway, OpenAI/Ollama/Anthropic-compatible client endpoints, Ollama/vLLM backends, WDRR scheduling, user quotas, request audit logs, GPU telemetry and administrative dashboards. These are **maintainer-published capability descriptions**, not a third-party functional test.
2. [Lucas Sheneman, *MindRouter: Open-Source LLM Inference Gateway for Institutional AI Sovereignty*, PEARC 2026 short paper](https://ai4ra.uidaho.edu/wp-content/uploads/2026/04/Sheneman_MindRouter_PEARC26_Short_Paper.pdf), **six pages**, inspected 2026-11-01. Abstract/page 1 describes the gateway and its intended institutional sovereignty use; pp. 3–5 detail architecture, WDRR and security; pp. 5–6 report the University of Idaho deployment and an author-reported cost comparison. This is **published primary research/experience reporting**, not an independently reproduced benchmark.

## Claim-level reconciliation

| Frozen paper claim | What primary source now supports | What remains unsupported |
|---|---|---|
| **C1:** MindRouter has protocol translation, WDRR, quotas, audit and GPU telemetry | Both official documentation and PEARC paper explicitly describe those features. A future source-enriched paper can cite the exact pages and retrieval date. | Whether each capability works under all failure modes, whether source implementation matches docs, current deployment configuration and independently measured reliability. |
| **C2/C3:** campus gateway comparator and useful parent-task definition | The PEARC paper describes a **campus-operated gateway** and reports production use; it does **not** describe an inter-campus federation or validate SIGMA's parent-task success rubric. | Empirical comparison of gateway-plus-separately-approved-external-access versus proposed federation; task-level completion and policy eligibility. |
| **C4/C6:** hard authorization/budget semantics | The documentation describes API-key authentication, token quotas and request-per-minute limits. | Immediate revocation across partitions, end-to-end egress mediation, recipient retention compliance, crash-safe financial reservation and immutable liability accounting. **Quotas are not automatically financial guarantees.** |
| **C10:** WDRR does not guarantee deadlines | WDRR implementation is described, but the PEARC report's qualitative fair-share claims do not provide a controlled latency/starvation theorem or a multi-site deadline evaluation. | Tail latency, model-compatibility starvation, queue failure and multi-institution contention. |
| **C11/C12:** cost ratio and missing full cost ledger | The PEARC report provides author-reported deployment measurements and a commercial-API price comparison, giving useful inputs for a later external-source-enriched scenario. | Fully loaded costs, model-quality equivalence, depreciation, staffing, task-level outcomes, exact provider price assumptions and transferable savings for a federation. |

**Specific harder failure case:** The official documentation's quota section states that **request-per-minute enforcement fails open if Redis is unavailable**. A paper claiming that the gateway's ordinary quota controls themselves constitute an absolute safety or spending cap would be unsound. The frozen manuscript's proposed hard reservation invariant is appropriately **additional**, but it remains unimplemented. A source-enriched paper should distinguish rate-limit availability behavior from token budget semantics and true worst-case financial exposure.

**Quantitative caution:** The PEARC report says 40 GPUs across 13 nodes, more than 64 open-weight models, 3.7 billion tokens since early 2026, approximately 9.4 kW normal cluster operation, and a 17-day March window with 872,997,430 tokens. It estimates commercial API comparison costs of $4,027–$11,896 for that window. Those are **author-reported deployment and comparison figures**, not a complete financial accounting or an estimate of federation cost-per-useful-task. Their existence does not resolve the frozen paper's C12, and they must not be inserted into the controlled baseline.

## Follow-up experiment design

When iteration 1 completes, keep the editorial-only A/B on **identical frozen sources**. Only afterward run a **separate source-enrichment treatment** that adds the two retrieved primary sources, exact retrieval timestamps and claim-span mappings. Measure whether C1 becomes accurately attributable without introducing unsupported claims about compliance, hard budgets, deployment performance, cost savings or federation. Compare changes in major claims, bibliography quality and contradiction handling separately from TeX layout.

**Status:** Source retrieval and textual cross-check performed; no code or live provider calls. This audit does **not** establish actual operational performance or legal compliance.
