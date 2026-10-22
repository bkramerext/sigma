# Operation Narrow Passage

**Fictional sample investigation | Maritime humanitarian crisis | Baseline T+0**

This sample examines a difficult military-supported humanitarian mission in a contemporary-style South China Sea crisis. It is **fictional**, does not describe an actual operation, and is not an operational plan. Its objective is to test SIGMA's ability to compare competing strategies, scrutinize assumptions, and maintain a reasoned research record under uncertainty.

The application's current project format stores the **T+0 scenario** in `project.json`. The later time-stepped developments below are **scenario fixtures for a future feature**, not events that today's SIGMA runtime automatically applies.

## Initial situation

A Philippine outpost on an **invented** disputed maritime feature is isolated after weeks of maritime access restrictions. Its personnel lack adequate medical supplies, and a critically injured person needs advanced care. Coast guard vessels from another claimant state enforce a contested access zone. Authorities disagree about jurisdiction and lawful passage. The Philippines seeks assistance from regional partners, including the United States. Neither government intends to start a war, but a collision, confusing message, or public misstatement could cause escalation.

The scenario deliberately abstracts tactical movements, precise locations, force capabilities, and weapon systems. The central problem is **humanitarian mission success under diplomatic, legal, resource, and escalation constraints**.

## Mission

Deliver essential supplies, evacuate those needing urgent care, and secure a repeatable humanitarian access process without causing an armed confrontation.

Distinct research strategies may include negotiated medical evacuation, a third-party humanitarian mechanism, a monitored multinational relief effort, temporary stand-down arrangements, or other defensible nonviolent combinations. A strategy must explain which actors can authorize it, what cooperation it assumes, and what observations would cause SIGMA to abandon or revise it.

## Assessment criteria

The investigation should retain **separate evidence and judgments** for:

1. Patient survival and personnel protection.
2. Emergency delivery and evacuation completion.
3. Time to relief, including uncertainty in medical deadlines.
4. Legal authority and sovereignty constraints.
5. Diplomatic feasibility and commitments needed.
6. Resource requirements and continuity of assistance.
7. Reversibility and robustness when communication fails.
8. Escalation risk, including low-likelihood high-severity consequences.
9. Information quality: source confidence, conflicting reports, and missing facts.

A weighted ranking can inform prioritization, but no weighted total should conceal a failed hard constraint. Unverified likelihood estimates are expert or agent judgments, **not measured probabilities**.

## Proposed feature: scenario evolution (T+n)

**Not implemented in the current SIGMA sample runtime.** A future scenario-evolution capability would introduce authoritative, versioned **event injects** into an ongoing investigation and require previously assessed strategies to be reconsidered.

Illustrative injects, all synthetic:

| Simulated phase | Inject | Required reevaluation |
| --- | --- | --- |
| T+0 | Initial isolation, uncertain medical urgency, contested access | Produce baseline options, assumptions, and tests |
| T+1 | An updated clinical assessment shortens the evacuation window | Recheck time feasibility and triage priorities |
| T+2 | A regional government offers medical support but only if specific authorization conditions are met | Reevaluate permissions, diplomatic dependencies, and alternative arrangements |
| T+3 | Reports of a vessel collision arrive from conflicting sources | Distinguish verified from unverified facts; reassess escalation and pause inappropriate actions |
| T+4 | A credible offer of humanitarian access emerges, contingent on a temporary agreement | Recompare negotiated and independent options, including reversibility |

These are **simulation inputs** intended to stress SIGMA's research process, not a prediction of real events.

### Requirements for a future T+n capability

- **Explicit scenario state:** Every inject has an ID, effective simulation time, source/authority, payload, and relation to earlier state. Live facts, fictional scenario facts, unverified reports, and agent speculation must be distinguishable.
- **Immutable history and versioned assumptions:** Preserve the T+0 problem, each inject, the resulting state snapshot, and the exact strategy and rubric revisions. Do not rewrite the past to match current information.
- **Triggered fitness reevaluation:** Identify which strategies, proof obligations, feasibility tests, and assumptions depend on the changed information. Recheck them against the updated state rather than merely asking for a fresh narrative.
- **Explain decisions:** Record what changed, the evidence used, which tests were rerun, how each strategy's status changed, and why an agent or user continued, revised, paused, or rejected it.
- **Replay and comparison:** Given fixed injects and deterministic mock agents/tools, reconstruct the run and compare results across different strategies, rubrics, models, or human interventions. Preserve branched alternate futures when supported.
- **Bounded operation and safety:** Respect execution budgets; keep failures, cancellations, and uncertain updates visible. The feature should support other dynamic research domains beyond military scenarios.

### Discriminating tests

1. **No-op inject:** A duplicate fact does not change strategy fitness or emit an invented reevaluation.
2. **Dependency impact:** A changed medical deadline invalidates a plan with a previously acceptable but now-too-slow response, while leaving unrelated reasoning intact.
3. **Conflicting intelligence:** An unverified collision report is not promoted to established fact; the system identifies a conservative conditional response and what evidence it needs.
4. **Hard constraint:** An otherwise attractive proposal is disqualified when legal authorization is absent.
5. **Lineage:** A user can trace a final recommendation back to the initial state, inject IDs, revised assumptions, actual test artifacts, critiques, and human overrides.
6. **Recovery:** Interrupted reevaluation resumes or terminates without erasing prior results or presenting partially completed assessments as verified.

## What counts as success

A credible demonstration would show several distinct options, independent critiques, meaningful updates after changed evidence, and a reconstructable decision history. It must be possible to observe SIGMA rejecting a previously favored option for a concrete reason. It should **not** be judged by whether a model invents a persuasive-sounding military plan.

The baseline investigation can be opened today as a regular SIGMA sample. The T+n evolution and replay behavior must be implemented and tested separately before any UI can claim to perform them.
