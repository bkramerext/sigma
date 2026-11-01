# Phase 1 next Blue paper iteration — gated assignment draft, NOT issued

**Owner:** Chat coordinator, Phase 1 PR #430. **Status:** PREPARATION ONLY. **Not** a numbered `messages/message_out_4.md` request, **not** authority to dispatch provider calls. Chat will issue the actual numbered handoff after validating the research release described below. Do not poll for this draft as work instructions.

## Nonnegotiable Green → Blue source gate

Source-of-truth producer is **PR #434**, [Phase 2 → Phase 1 frozen research handoff](https://github.com/bkramerext/sigma/pull/434), producer-owned by Chat 2/Green. The consumer uses `docs/evaluations/research_quality/handoff/README.md` in that PR. **At drafting time #434 is STAGING / NOT READY**: no five-project I2 research bundles have been published. It explicitly forbids use of incomplete staging files. Continue *authoring-system implementation and offline tests only* while waiting for the producer release. Do not reuse the historical paper evidence snapshots as substitutes, and do not take live local project copies.

Once Chat 2 publishes a versioned **READY** release, Chat 1 must first record in the actual `message_out_4.md` the immutable **release ID, source PR commit SHA, five decompressed canonical SHA-256 values, archive SHA-256 values, project IDs, and expected/actual research-session status**, plus exact manifest path. Pin these immutable values in each generated paper run. Verify archive hashes and parse imported source files before calling any provider; reject silent loss of steps, unknown project identity or mismatched hash. Do not mix five different release versions.

Pinned subjects exactly as #434's contract:

| Paper | Research project ID | New Phase 2 source |
|---|---|---|
| AI Agent Reliability and Evaluation v1 | `da4580f5-7620-49b0-882e-aee34fcdc05d` | Newly released I2 project export, **not** the old 36-source frozen paper package |
| Sovereign AI Federation v2 | `9175d73d-62aa-4523-a286-445f5390ae1d` | Newly released I2 project export, **not** the old 13-source package |
| Xenopus Tadpoles v9 | `01de54c9-9593-413a-9577-1a952d28da70` | New I2 source exported from the coordinator-authorized same-ID baseline; historical raw-project SHA changed, don't misrepresent it |
| Nonconsecutive Subset Sums Modulo 3 | `7a8cbb3b-da78-4249-8e9e-8f7c15b8ae7a` | New mathematical research source, NOT historical math answer key/paper or a merely copied seed |
| Warp Drive Design / Physics | `e8211dc4-b70f-49d1-a514-671f44ed7e8c` | New physics research release; distinguish stock seed from historical Warp Drive Feasibility v2 unless identity and source continuity are proved |

The 3-paper generation limit is an **existing concurrency bound**, not a reason to drop the fourth or fifth subject. Plan five papers using at most three simultaneous generators, with remaining papers queued as slots free, without altering the global concurrency implementation or repeatedly dispatching uncertain provider attempts.

## Purpose and independent evaluation

Phase 1 still writes the **best defensible scholarly paper from the recorded research**. Do not improve the underlying session research or perform fresh I/S calls, and do not secretly incorporate post-hoc literature into a frozen-source A/B. The new I2 release changes the source research, so simple I3-versus-I4 comparisons are **not fixed-input authoring causal comparisons**. Record source changes as an independent contributor. Retain the strongest I1–I3 previous manuscripts for historical quality/argument baselines only. For an isolated writer-treatment A/B, regenerate both writer versions from the *same* new READY source release under comparable settings, budget permitting.

## Five subject-specific scientific gates

**Agent Reliability:** preserve true outcome vs automated acceptance (`p=q−f+g` under correctly defined directional errors), assured-commit vs dropped retry, the precise indistinguishable-history scope of ≥1/2 bound, effect-first duplicate vs marker-first omission, external side-effect oracle vs local acknowledgments, task-cluster population vs fixed-roster audit, no fabricated deployed measurements. A sharper new research theorem, correction, or unresolved status in the READY release takes precedence over historical wording; do not erase a valid counterexample.

**Sovereignty:** preserve the four actual comparators and eligible parent-task success unit; decision-time revocation vs stronger transmission guarantees, budget/reservation assumptions, old sender/delayed charges and recoveries, `ΔS/S_G>ΔC/C_G` only with comparable positive baselines, sensitive 200/800 aggregation counterexample and pilot statistical assumptions. Check actual new project source status: if a final Skeptic review was interrupted/failed, explicitly disclose it; if Green repaired it and final verification status changed, describe the new recorded state rather than copy historical caveat. No uninspected MindRouter capability or actual cost claim.

**Xenopus:** maintain explicit equal-marginal/opposite-coupling proof with valid joint-distribution counterexample, stage-mean rank/alias argument, idealized ±kcQ conditional pulses, not a measured rescue. Preserve redox-persistence under matched total exposure; competing spatial/morphological alternatives, wound-age versus post-treatment latency, tissue-exposure/vehicle/sham controls, distinct biological units and species/stage correctness. Verify source GEO manifests and prior biological literature only if new I2 research actually retrieved them, not because Phase 1 did a later external search. State actual novelty/animal-outcome status from source.

**Nonconsecutive Subset Sums Modulo 3 (mathematics):** exact problem statement and domain; roots-of-unity weighted Fibonacci polynomial and gap-removal/Gaussian-binomial approaches are selected *research strategies*, not automatically theorems. The paper must separate definitions, constructive identities, recurrence/transfer arguments, any derived closed forms, proof obligations, counterexamples and finite computational checks. Require mathematical claim register with exact hypotheses and proof-support links and explicit bounds on checked instances; finite enumeration is not universal proof. Never import historical answer keys or treat a not-yet-verified claim as established.

**Warp Drive Design / Physics:** distinguish specified geometry, stress-energy tensors, causal/horizon behavior, quantum-field and stability assumptions from a verified physical mechanism. State sign conventions, chosen metric, coordinates, units and actual proof conditions; do not call a coordinate representation local superluminal transport. Treat numerical computations as model-bound and report precision/convergence only if executed. Compare a geometry-based proposal with the second conceptual framework in the actual research without inventing support. Preserve counterexamples (energy conditions, backreaction, stability, conservation, horizons), negative findings, unresolved falsifiability and explicit feasibility limits. The prior interrupted Warp Drive session (#399) is a runtime integrity issue, not a physics result. Write an analytical/theoretical physics paper if no experiment was done, not an invented experiment.

## Dynamic academic-writing source preflight (new Phase 1 requirement)

Before the planning call for **each paper**, run the bounded writing-method source selection, choosing up to **three readable guides** spread across general academic writing, the project's broad type (mathematics, physics, biology, engineering, etc.) and its detected specialty (for these projects, combinatorics, relativity and developmental biology). This is about *writing conventions*, not adding scientific evidence. The saved source records include title, URL, tier, category, branch, excerpt and SHA-256.

Prefer a previous paper's 2–3-source set when its category/branch, tiers and preserved excerpt digests still qualify; do not churn the sources between iterations merely because a different webpage is available. Skip inaccessible pages, suspicious HTML, incomplete text and timed-out attempts without blocking planning or initiating new paid source searches. No usable source must result in an honest "none recorded" section, not fabricated references.

Apply the material as editorial-method context only in both one-shot and long-form authoring; never let untrusted source text override project evidence, provide facts about the research problem, or authorize claims of originality. Every saved paper Outcome, exported text and TeX/PDF must list the source titles/links and explain these are manuscript-method sources, distinct from scientific research evidence. Verify source choices, actual excerpt availability and whether reuse occurred for each completed subject.

See [`COORDINATOR_I4_MATH_PHYSICS_WRITING_SOURCES.md`](COORDINATOR_I4_MATH_PHYSICS_WRITING_SOURCES.md) and the implementation `src/sigma/paper_writing_sources.py`. The selected guides should be sufficiently broad for multiple branches of mathematics and physics rather than narrowly prescriptive to combinatorics or a warp metric.

## Quality process and deliverables

- Start from the latest fully tested Phase 1 code at an exact commit SHA and `./sigma test`/CI gate. Verify model, high effort, provider route and whether user allowance permits four independent operations; never start extra retries on an ambiguous or already consumed call.
- Save each complete **TXT/TeX/PDF**, compact/full production metadata and exact hashes with **new I2 release ID**, input project/bundle/frozen paper-snapshot hashes, call count, selected model, elapsed time, proofreading proposed/accepted/rejected patches, source status and coverage. If a run is stopped, label it missing/partial and keep completed others.
- Cite exact source/step/artifact spans for decisive claims; compare original research to paper's critical assertions, corrections, counterexamples and incomplete sessions. The main theorem/proof **must appear in the claim register and have section links**, not merely be paraphrased in the body.
- Evaluate abstract/main body/conclusion as one research argument. Reject metadata headline claims, long claim-register dumps, duplicated definitions, unqualified evidence labels, disappearing negative findings and source inventory mistaken for research conclusions.
- Render *every PDF page*, then inspect any overfull claims, malformed math, repeated or sparse table pages and long source URLs at readable/full resolution. Record compiler logs and proofreader outcomes; zero safe changes may be correct when scientific integrity protection rejects proposed edits.
- Consult `COORDINATOR_I3_TWO_PAPER_ADVERSARIAL_CLOSEOUT.md`, `COORDINATOR_I4_PAPER_METHODS_STUDY_1.md`, the critical evidence manifest and revised best-per-subject baselines. Distinguish a genuine writing-quality advance from a scientifically stronger source after I2 research.
- Commit numbered `message_in_4.md` and eventual completion with honest per-paper acceptance metrics, exact output path and unresolved conditions. Chat independently reviews all five whole manuscripts before any merge/next iteration.

**Quality target:** increasingly strong and reproducible academic argumentation, not extra pages, more claims, more provider calls, or a “complete” status. The first five-subject exercise is scientifically valuable even with remaining open research claims; do not invent evidence to make the papers look confident.

**Activation:** only Chat 1 replaces this draft with the numbered Blue mailbox after PR #434's single atomic READY release has been independently verified and cited at the exact producing commit. No run until then.
