# Phase 2 research quality: evidence, adversarial follow-through and corrected conclusions

**Status:** evaluation and improvement criterion for the cumulative [PR #433](https://github.com/bkramerext/sigma/pull/433); prompted by the qubit project [#442](https://github.com/bkramerext/sigma/issues/442). **Scope:** intellectual quality of research, across every discipline. No change to the Investigator/Skeptic loop, strategy scheduler, rounds, provider billing, UI or manuscript generation.

## Fundamental distinction

A model's fluent explanation is **not** a verified finding. Ask whether SIGMA acquired appropriate evidence, checked what it really establishes, responded to substantive objections with work, and revised the conclusion. A final paper is a communication artifact, not scientific certification.

Trace the *same claim* through the durable record:

**Claim → actual evidence and provenance → material Skeptic objection → specific follow-up question/action → observed derivation, computation, source inspection, discriminating test or documented inability → result → retained, narrowed, retracted or still-unresolved conclusion.**

This is a reconstruction from actual saved artifacts and turn/role IDs, not a requirement that an agent fill out a new form or invent a chain. Multiple related branches may appear, and an honest failure may end with an open obligation. Correctly identifying that no available evidence can discriminate rival explanations is a valuable result.

## Audit each consequential claim

For each project, choose **one to three pivotal claims**, not the easiest examples. Inspect the saved full source, exact Investigator/Skeptic outputs, context manifest, execution logs, peer handoffs and durable obligations. Record:

| Audit field | What must be established |
|---|---|
| Claim and scope | Exact words, conditions, quantifiers, units, definitions, domain, research artifact and turn IDs |
| Evidence kind | **Executed numerical/symbolic result** with program/parameters/output/status; **complete formal deduction** with checkable steps; **observed empirical data** with origin, design and uncertainties; **actually inspected primary literature** with specific content; **model assumption**; **agent assertion**; **unperformed proposal**. Categories can coexist; never merge them into a generic "supported" label |
| Provenance and verification | Exact source/step/execution/artifact IDs, usable source body vs pointer, code/output and file inspection, validation limits, independence of checks, whether source was actually reachable and read. A saved method-note URL is not scientific literature retrieval |
| Skeptic action | Concrete high-impact objection tied to the claim: erroneous inference, invalid model, counterexample, confound, observational equivalence, bias, prior art, failed execution or unavailable input. Distinguish substantive criticism from stylistic commentary |
| Follow-up | Did the actual next Investigator turn or cross-strategy handoff **attempt the proposed discriminating action**, not merely rephrase the objection or promise future work? Preserve next-question/cycle/obligation IDs |
| Result and revision | Concrete computation, derivation, evidence examination, falsifier, failed attempt or explicit access blocker; whether the later claim was strengthened, narrowed, rejected or left open. Exact artifact/step and revised conclusion IDs |
| Alternative explanations | Strongest live competing explanation and a test/observation that truly discriminates it, or demonstration of non-identifiability; no assertion that alternatives were ruled out without work |
| Prior art and novelty | What primary sources were inspected, scope of coverage and publication details; if no live retrieval, **novelty NOT ASSESSED**, not an invented reference or declaration of novelty |
| Epistemic status | Independently verified (state by whom and how), completed but bounded computation, conditional deduction, empirical association, unverified model reasoning, unknown or contradicted. Missing final Skeptic review remains explicit |
| Value | Did this chain materially improve correctness, useful negative knowledge, uncertainty calibration, reproducibility or a genuine novel result? Count a valuable falsification as progress |

**Distinguish three very different events:** (a) the model proposes a Python/SageMath calculation; (b) SIGMA actually executes it and saves exact code, parameters, status and outputs; (c) an independent check validates the computation's relevance and scientific interpretation. A successful run proves neither (b)→(c) automatically nor a universal theorem. Similarly, a source citation does not prove the source was retrieved or read. Do not claim external literature search without a real retrieval capability or saved inspected documents.

## Generalize by inference standard, not by a universal physics checklist

| Domain/example | A plausible but unjustified conclusion | Decisive follow-up evidence or negative result |
|---|---|---|
| Quantum physics / #442 | "A fitted non-exponential curve proves non-Markovian memory" | Specify Markovianity definition and dynamical assumptions; derive valid model, compare non-memory and static-disorder alternatives, execute model-discrimination simulation with real saved outputs and noise controls, inspect relevant original literature. Report indistinguishable fits if that is the finding |
| Other physics / Warp | "Our tensor calculation proves a physically realizable drive" | Verify math, energy conditions, units, limiting cases, convergence; separate metric-internal consistency from measured physical realizability; identify untested matter assumptions |
| Biology / Xenopus | "These stage-average observations establish an individual-animal mechanism" | Check actual cohort/data access, experimental unit, paired trajectories and temporal controls; construct observationally equivalent mechanisms; if unpaired marginals cannot identify mechanism, preserve the negative identifiability result |
| Mathematical / Nonconsecutive Subset Sums | "Numerical agreement establishes the recurrence/theorem" | Formal proof with explicit quantifiers, base cases and missing lemmas, independent symbolic/finite counterexample checks; failed counterexample search is not proof |
| Computer systems / Agent Reliability | "Our evaluation establishes exactly-once external effects" | Distinguish claim/commit/acknowledgment observations, construct indistinguishable crash histories, run fault injection with an actual external-effect oracle or state the untested guarantee |
| Engineering / Sovereign AI | "Reservation protocol guarantees practical benefit/fairness" | Prove conditional invariants, compare matching cost denominators and failure regimes, test omitted subgroup/delayed-send counterexamples and real measurement evidence; preserve conditional-only benefit |
| Clinical/economic/legal inquiries | "A plausible mechanism, regression or legal interpretation establishes causality or legality" | Check genuine study design/confounding or controlling authority/adverse precedent and dates, relevant jurisdiction, actual records, sensitivity and contradictory results. No fabricated retrieved sources |

These are **examples**, not mandatory techniques across domains. Choose the strongest test suited to the exact claim. One correct decisive derivation may outweigh many shallow simulations.

## Evaluation protocol on actual unscripted sessions

1. **Freeze the source.** Identify branch commit, project ID and bundle SHA. Do not alter saved role outputs. Review all strategies, not just the preferred narrative.
2. **Find the hinge claims.** Select 1–3 claims whose failure changes the scientific conclusion. Reconstruct actual evidence and classify source/execution/inspection status, including what's missing.
3. **Trace real challenges.** Identify material Skeptic objections or cross-strategy counterexamples with exact IDs. For each, follow the recorded next_question and subsequent Investigator/peer turns. A planned calculation, fabricated execution, unchanged retry or prose-only acknowledgement is **not** follow-through.
4. **Recheck independently.** Where feasible, redo a concise derivation, rerun a code fragment in isolation, compare an alternative model or read the relevant primary source (coordinator review). State when independent verification was impossible.
5. **Inspect the final change.** Compare pre-objection and post-objection claims. Record correction, non-identifiability, retraction, evidence-backed retention, or unresolved uncertainty. A stop with unsupported "achieved" is a failure, even if well written.
6. **Check novelty separately.** For material novelty claims, actually inspect primary prior art when accessible. Without retrieval, mark coverage limited/not assessed, and do not transform a literature suggestion into a checked citation.
7. **Compare prior research.** Compare I1, I2 and previous strongest source *per subject*, not only call counts or length. Use the best evidence for paper writing, with missing Skeptic checks disclosed.
8. **Repair observed failure mechanisms.** Prefer narrow versioned prompt/context and validation changes with deterministic tests, then measure behavior on subsequent genuine unscripted research. Do not alter the loop/scheduler/UI or force an extra round as a surrogate for evidence.

### Reporting matrix (one row per pivotal claim)

| Project / source SHA | Claim / artifact | Evidence classification & independent check | Skeptic objection / ID | Follow-up action / ID | Actual outcome / ID | Revised epistemic conclusion | PASS / PARTIAL / FAIL / UNVERIFIED |
|---|---|---|---|---|---|---|---|

**PASS**: a material objection generated genuinely new or re-evaluated evidence appropriate to the claim, with resulting calibrated conclusion and traceable links (possibly a justified negative result). **PARTIAL**: some evidence or response exists but the decisive test is incomplete or conditional. **FAIL**: unsupported asserted success, invented evidence, a prose-only response to a testable material objection, or hidden decisive counterevidence. **UNVERIFIED**: records, tools or primary sources needed to assess the chain are unavailable. Do not assign PASS from model agreement alone.

### Portfolio synthesis

Report separately: (1) pivotal claims audited; (2) proportion with genuinely executed evidence, formal proof checks, inspected literature or real observations; (3) material objections identified and proportion that led to concrete subsequent work; (4) material corrections/retractions, valid negative findings and unresolved alternatives; (5) unchecked/unsupported novelty statements; (6) qualitative changes relative to the strongest earlier research. Give numerators/denominators and explain missing opportunities (e.g., a final Skeptic objection with no following turn), not an aggregate quality score.

A particular run may have no available follow-up turn or no network-accessible literature tool. **Do not penalize absence as an imaginary executed failure:** classify as unmet opportunity or explicitly unverifiable, preserve the question, and use independent coordinator review where available. Do not require a simulation when the right evidence is a proof, controlled observation, decisive countermodel or adverse authority.

## Engineering boundary

SIGMA currently provides optional bounded Python/SageMath evidence execution and persisted execution artifacts, but **its research agents do not have a live external literature-retrieval tool**. Evaluate such claims accordingly; do not write prompts instructing them to claim to have retrieved sources. The existing role schema, obligation ledger, cross-strategy handoffs, saved execution status, and next_question are the links used for this audit. New UI, extra roles, scheduler changes, automatic provider spending and paper-generator changes are out of scope.

Green supplies real traces, working code/test evidence and honest blockers. Phase 2 scientific coordinator independently validates crucial scientific claims, prioritizes improvements and chooses the best per-project source for Phase 1. The current archived I2 40/60 partial snapshot is not retroactively certified by adoption of this rubric.
