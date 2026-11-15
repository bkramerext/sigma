# Fairness is not sovereignty: source-backed research obligations and a counterexample

**2026-10-31. Independent research note for PR #396 / primary PR #395.** This is a literature synthesis and an analytical counterexample, **not** a performance measurement, federation deployment, completed SIGMA Investigator/Skeptic run, or evidence that one scheduler is best. No provider calls or charges.

## 1. What the sources actually establish

**Existing university deployment:** Lucas Sheneman, *MindRouter: Open-Source LLM Inference Gateway for Institutional AI Sovereignty*, PEARC 2026, DOI 10.1145/3785462.3815861, [author PDF](https://ai4ra.uidaho.edu/wp-content/uploads/2026/04/Sheneman_MindRouter_PEARC26_Short_Paper.pdf), §§3.3, 4. MindRouter implements on-campus weighted deficit round robin (WDRR) with weights, burst credits and a fairness window. Its reported University of Idaho deployment has 13 nodes, 40 GPUs, 64 models, protocol translation and campus-level RBAC/audit. The author's statement that fair sharing was maintained under contention is an operational observation, **not** a published worst-case token latency bound or a cross-campus federation experiment. The architecture must not be misrepresented as already federating institutions or commercial APIs.

**Service-based fairness:** Ying Sheng et al., *Fairness in Serving Large Language Models*, OSDI 2024, [paper](https://arxiv.org/abs/2401.00588). Their Virtual Token Counter (VTC) considers the input/output token cost of continuous-batched serving and provides a service-gap guarantee between continuously backlogged clients, rather than relying on raw request counts. Their guarantees do **not** imply that every well-behaved short request meets a latency SLO under all arrival patterns.

**Prefix-locality tradeoff:** Shiyi Cao et al., *Locality-aware Fair Scheduling in LLM Serving*, arXiv:2501.14312 (2025), [primary paper](https://arxiv.org/abs/2501.14312). DLPM and distributed D²LPM investigate prefix-cache locality versus fairness; the paper reports improved throughput and latency in its own experiments. Its distributed setting is **inference-server scheduling**, not independent universities with legal data-sharing constraints.

**Latency isolation:** Dev Bali et al., *Token Latency Fairness: Performance Isolation for Multi-Tenant LLM Serving*, arXiv:2609.18112 (September 2026), [primary paper](https://arxiv.org/abs/2609.18112). The authors distinguish throughput/service fairness from a stronger per-token latency-isolation property for well-behaved tenants. Their δ-token fairness notion bounds interference relative to isolated service under specified conditions. Do not transfer their guarantee to MindRouter WDRR or to federation without proving the assumptions.

These works concern *different layers*: campus gateway scheduling, engine-level continuous batching, distributed serving within one operator, and latency isolation. Federated university admission, cross-campus contracts and prompt/derivative policy are a separate governance layer. Equating the layers would be a category error.

## 2. An analytical counterexample (no simulation or invented measurement)

**Proposition:** A scheduler with equal long-run token-service allocation can still have arbitrarily poor time-to-first-token (TTFT) for a compliant short request if service is non-preemptible at sufficiently large request stages.

**Construction.** One shared inference resource, two equally weighted tenants A and B, with A beginning an uninterruptible prefill stage lasting T seconds at time 0. B submits a short interactive request at time ε, where 0 < ε < T. Even if B is first in every subsequent fair queue decision, its request cannot begin until time T. Thus **B's queueing delay is at least T − ε**. For any proposed universal latency bound L, choose T > L + ε. After A's stage, the scheduler may compensate B with enough future service to maintain its desired long-run share. Long-run service equality therefore **does not imply** a fixed worst-case TTFT bound. This is a conditional mathematical construction, not a claim that any named deployed system runs completely non-preemptible prefill.

**Research consequence:** A campus WDRR scheduler could meet aggregate service-share targets while a long prefill, cache thrashing or bursty agentic batch causes an unacceptable interactive wait. Conversely, always prioritizing interactive users could starve low-priority research jobs. Both failure modes must be tested; neither follows automatically from the MindRouter paper.

## 3. Pre-registered questions, comparisons and failure tests

The *primary* question is: **under actual university data restrictions, what added measurable value does cross-campus routing provide over an optimized single-campus hybrid, net of operational overhead?** A federation must win against a well-tuned baseline, not a straw-man campus-only scheduler.

**Four controls (pre-register configurations):** (A) campus-local with fair queueing; (B) commercial frontier for *only* approved tasks, recording restricted demand as unserved; (C) campus-local plus contractually approved frontier; (D) C plus an approved partner-campus inference pool and additional identity/policy/settlement overhead. Hold workload, versioned prompts, task-level rubrics and time windows comparable. Do not give D free donated GPU-hours while charging A depreciation.

**Workload design:** distinguish short interactive prompts, long-context research tasks, agentic multi-call workflows, restricted student/research datasets, and cache-sharing patterns. Use consenting, de-identified or synthetic test material where necessary; never copy protected source data to another campus or commercial service merely to conduct a test. Freeze allowed destinations *before* seeing performance outcomes. Track input, cached input, output, failed and retried tokens, wall-clock, GPU-hours, energy and human evaluation labor.

**Primary outcomes:** (i) completed useful research tasks per fully loaded dollar; (ii) fraction of tasks served **within their approved data boundary**; (iii) paired blinded quality with confidence intervals; (iv) p95/p99 TTFT and completion latency for short/long tasks; (v) worst-department starvation intervals and weighted service-share deviation. Report both mean and worst-tail results. Mark infeasible designs separately instead of assigning a misleading low cost per completion.

**Adversarial drills:** one tenant issues long-prefill bursts while another sends short interactive requests; one tenant reuses a hot prefix while another does not; partner WAN is partitioned; policy revokes partner approval mid-queue; a provider times out after potentially charging; a 4xx/5xx arrives; commercial budget is exhausted; one university withdraws its GPU capacity; a retry contains derived restricted data. In every case the route decision must fail closed rather than bypass authorization or silently overrun the budget. Rejected/queued tasks count toward unmet demand.

**90-day prospective pilot (proposed, not performed):** Days 1–30 gather authorized local-only baseline and workload distributions, validate task rubric and fully loaded accounting; days 31–60 conduct blinded paired offline quality/capacity evaluation, source-safe failure drills and policy review; days 61–90 run a capped, institutionally authorized pilot comparing C and D with random assignment/paired time windows, predefined stop conditions and a holdout. Use stratification by department and task class; publish raw aggregate denominators, confidence intervals, rejected tasks, exclusions, version/price changes, and implementation costs. Do not present the 90 days as already executed.

**Hypotheses to try to falsify:**
- H1: For unrestricted complex tasks, frontier augmentation improves *useful* completion probability enough to offset per-call amplification, compared with campus-only.
- H2: Under constrained commercial spending and spare **approved** partner capacity, federation improves coverage/SLO attainment relative to an **optimized** campus+frontier hybrid, after partner charges and operational overhead.
- H3: Under weak partner trust or high governance/egress costs, the simple hybrid Pareto-dominates federation.
- H4: WDRR service-share compliance alone is insufficient to protect p99 interactive latency under adversarial burst/cache conditions.

**Acceptance gate:** A scientific manuscript may present the published MindRouter measurements and our explicitly conditional derivations as *external evidence and analytical results*. It may not present synthetic scenario successes, queueing outcomes, security guarantees, or simulated fairness as campus observations. A genuine SIGMA Investigator/Skeptic record and paired frozen-evidence papers remain **UNMET** until separately verified. Real model calls remain **unauthorized**.
