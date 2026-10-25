# Draft — Intelligent Cross-Strategy Research Coordination

**Status:** design proposal for review, **not yet an implementation assignment**. Reconcile with the final merged A18 and A19 code before assigning a developer.  
**Context reviewed:** A18 PR #8, branch `a18-blue` at `1114aba3`; A19 PR #9 at its initial checkpoint.  
**Scope:** research coordination inside SIGMA. This is not a development-agent orchestrator and does not require a new UI cockpit.  
**Working label:** Intelligent Research Coordinator (assignment number to be chosen after A18 is merged).

## 1. Product outcome

SIGMA should be capable of treating several research strategies as parts of **one developing investigation**. A result from strategy A should change work on strategy B *when, and only when*, there is a concrete intellectual relationship.

A useful coordinator:

1. Recognizes that a finding, contradiction, failed experiment, or newly exposed obligation changes the prospects of another approach.
2. Proposes a **specific, discriminating next action**, not a general exhortation to try harder.
3. Allocates a limited research budget to that action, with reasons and an explicit uncertainty level.
4. Preserves the link from the new decision back to the exact saved evidence that caused it.
5. Revisits the decision when subsequent results weaken or overturn its premises.
6. Sometimes correctly chooses **no intervention**. Avoiding contamination and waste is part of the capability.

The target is *causal coordination*: a cross-strategy discovery changes subsequent research behavior in a way an external reviewer can reconstruct and judge. Mere peer-artifact visibility, fair rotation, an LLM-generated summary, or a plausible explanation written after execution does **not** meet this bar.

### Illustrative case

Strategy A establishes a bounded numerical counterexample to an assumption used by B. The coordinator should identify the *specific shared assumption*, decide whether the counterexample actually lies within B's stated domain, and either direct B to test/revise that assumption or record why no transfer is warranted. It must not prematurely mark B refuted merely because a numerical example exists. Meanwhile, strategy C might use A's corrected bound; the coordinator can propose that connection as a testable hypothesis, not as an established theorem.

## 2. Current A18 foundation, and the precise gap

In PR #8, A18 already provides:

- Real bounded concurrency among multiple selected strategies, with a shared call budget and up to three simultaneous provider calls.
- Persistent per-strategy branch state, artifacts, cycle counts, stop/recovery, and strategy attribution.
- Investigator/Skeptic output and coordinator dispositions inside branches.
- A bounded context containing selected peer strategy artifacts, plus bounded prior-session findings.
- A fair portfolio allocator and a `portfolio_decision` record listing active/stopped strategies with artifact IDs.
- Existing Research Session UX and A17.6 outcome/assessment contracts.

These are important foundations. **Do not replace them unnecessarily.**

At the reviewed A18 head, `_portfolio_context` selects recent peer evidence, `_commit_portfolio_review` reduces a branch's Skeptic output to a disposition, and `_portfolio_worker` schedules primarily by fair rotation and budget. The portfolio-level `coordinator.portfolio_review` message records which branches are active/stopped; it does not evaluate *why a finding in A should redirect B*, and does not itself select, combine, or experimentally compare cross-strategy hypotheses.

**This spec starts at that missing decision layer.** Before implementation, re-read the merged code: Blue may already have added some of the behavior below. Preserve and adapt to any working equivalents. If A19 has connected Python experiments to session artifacts, reuse their genuine execution IDs/results as evidence, never copy output into a disconnected coordinator-only store.

## 3. Proposed research-decision loop

A planning pass occurs at **safe research boundaries**, after completed artifacts have been durably committed and before the next work wave is scheduled. Never mutate in-flight provider prompts. The plan is a durable proposal validated before it influences scheduling.

### Step A: Construct a bounded, evidence-grounded research state

Assemble a compact portfolio snapshot with:

- The exact project objective and current problem assumptions.
- Enabled strategy IDs, approach summaries, current status, budget already spent, unresolved questions and obligations.
- Newly committed artifact IDs and material changes since the prior planning pass.
- A bounded, deduplicated index of relevant earlier artifacts and negative results, including original source references, stated assumptions, verification status and limitations.
- Executed test results where available: test code identity, execution result ID, exit status, and the precise assertion supported, **not** “experiment proved X.”
- Previous accepted coordinator decisions and whether their predicted test outcomes were observed.

Make truncation explicit. Do not silently discard a decisive objection or present a summarized assertion as though it were the original evidence. A referenced full artifact must be retrievable by ID for inspection. The planner may request missing evidence instead of guessing. Preserve the deterministic A18 context and resource limits.

### Step B: Generate candidate *cross-strategy influences*

Use a bounded model reasoning step, or an existing role with an equivalent explicit contract, to propose zero or more influences. Each one must identify:

- **Source:** exact saved artifact ID(s) and source strategy.
- **Target:** a distinct strategy ID (or an explicit proposed composite/fork, subject to normal human acceptance).
- **Relation:** e.g. shared assumption, supporting lemma, contradiction, tighter bound, useful method transfer, incompatible premise, experimental result, or no material relation.
- **Mechanism:** the concrete logical or experimental link, with stated domain restrictions.
- **Evidence class:** established/independently checked, finite computation/observation, agent-reviewed but unverified, speculative.
- **What would change:** the exact target question, proposed test, obligation, or resource priority.
- **Discriminating prediction:** what result would support or invalidate the relationship.
- **Known objections:** why the transfer might fail, and whether new evidence is needed first.

A vague semantic resemblance is insufficient. A coordinator must be allowed to return **no actionable relationships**.

### Step C: Adversarial validity check

Before applying an influence, validate its references deterministically and critique its substance:

- Source and target strategies must exist and be eligible. Source artifact IDs must exist and belong to the claimed project/session.
- The stated relation must quote or paraphrase *actual recorded content*, not a manufactured premise.
- A counterexample only transfers if the compared hypotheses have matching assumptions and scope.
- A numerical observation must not be promoted into a theorem. Agent consensus is not independent verification.
- Contradictory or retracted evidence must be carried forward with its status and conflict; no silent erasure.
- A proposed composite cannot inherit proof status from constituent strategies without a separately justified argument.
- The critique must name a concrete flaw or state that no decisive flaw was found. A model “approve” alone never upgrades verification status.

Use a small bounded critique call when useful; preserve a cheaper deterministic no-op path when there are no plausible influences. If rejected, save the rejected proposal and reason rather than suppressing the trace.

### Step D: Select *one of a small set* of executable research actions

An accepted decision can:

- **Continue** a target strategy with a revised, attributed next question.
- **Test** a specific claim or assumption, including Python execution once A19 is integrated.
- **Challenge** a cross-strategy transfer before investing in it.
- **Compare** two competing mechanisms under the same discriminating check.
- **Reallocate** the next bounded work wave toward an evidence-backed opportunity.
- **Defer** or **pause** a branch whose next action has low expected value, without deleting it.
- **Propose a fork/composite** strategy for human review; do not silently persist a new user-visible strategy or rewrite a saved approach.
- **Stop** an exhausted/refuted path only with explicit cited grounds; preserve the ability to reopen it when those grounds change.
- **No-op** and retain ordinary A18 fair scheduling when no sound intervention is available.

An action must be runnable by the existing Investigator/Skeptic and research-session mechanisms, or explicitly recorded as pending human approval. If an action cannot be mapped to an executable next step, it is not a scheduling directive.

### Step E: Apply at a safe boundary and observe consequences

Use A18's existing shared budget, concurrency caps, provider gates, session state machine, recovery, and idempotency rules. A strategy-specific directive takes effect only at a documented next-call boundary. Save the decision *before* dispatching affected calls, and capture which ensuing steps consumed it.

After the corresponding artifacts arrive, evaluate whether the predicted discriminating result occurred, whether the relationship survived critique, and whether to retain, revise or retract the influence. The result closes a causal chain:

`source evidence → proposed relation → critique → accepted decision → dispatched step → observed result → revised decision`.

A failed/timeout provider or tool request is an **operational failure**, not evidence against a mathematical hypothesis.

## 4. Suggested data contract (conceptual, not a mandated schema)

Use versioned typed records, backed by existing artifact/event storage when possible. A single stable coordinator-decision ID should link plans to subsequent steps.

```json
{
  "decision_id": "uuid",
  "snapshot_id": "versioned-hash-or-id",
  "source_artifact_ids": ["artifact-id"],
  "source_strategy_ids": ["strategy-id"],
  "target_strategy_ids": ["strategy-id"],
  "relationship": "shared_assumption",
  "mechanism": "specific, bounded statement",
  "evidence_class": "agent_reviewed_unverified",
  "proposed_action": "test",
  "target_question": "a discriminating test or derivation",
  "prediction": "expected observation if the connection holds",
  "failure_criterion": "result that rejects or narrows it",
  "critique": {"status": "accepted_for_test", "objections": []},
  "decision": {"status": "scheduled", "reason": "source-cited rationale"},
  "execution_step_ids": [],
  "result_artifact_ids": [],
  "evaluation": "pending"
}
```

The example illustrates provenance, **not exact field names**. Reconcile with A18's `strategy_runs`, `steps`, `artifacts`, `portfolio_decision`, and A19 execution records. Maintain backward compatibility for legacy projects/sessions. Never rewrite an old source artifact simply because a later coordinator now doubts it. Reject invented references or stale snapshot applications.

Decision status should distinguish **proposed**, **rejected**, **accepted**, **scheduled**, **executed**, **blocked**, **superseded**, and **retracted**. Research outcome status remains separate. Save model/effort/usage metadata and note if review was heuristic rather than independently verified.

## 5. Budgeting, autonomy, and failure handling

The coordinator may consume more model calls; it must earn that cost.

- All planning and critique calls count against the **same existing session/provider budget**, not an implicit bonus budget. Never silently extend the session or switch billing modes.
- Use the user's connected **ChatGPT-plan pathway only** for authorized live evaluation. No API-key, metered fallback, or external billable provider. Stop/skip calls on plan throttling and continue with offline verification where possible.
- Hard bounds: model calls, wall time, persisted bytes, context size, concurrent calls, planning frequency, and per-target interventions. Choose values after measuring existing A18 limits. Planning cannot starve investigation/critique of the calls needed to complete a useful cycle.
- A plan that repeatedly proposes the same action without new evidence is suppressed or logged as a duplicate. A stopped strategy is revisited only when genuinely new evidence changes its decision basis.
- Distinguish exploration fairness from evidence-sensitive allocation: don't permanently starve a strategy because a model finds another approach rhetorically attractive. Maintain a bounded minimum opportunity for alternatives or a concrete recorded reason for pruning them.
- Provider failure, invalid JSON/schema, unsupported action, bad citation, timeout, cancellation, or stale snapshot must be a recoverable failure. Save honest state and fall back to A18 deterministic scheduling where safe; never pretend the planner accepted a decision it didn't validate.
- No autonomous runaway recursion between planning, forking, and replanning. Planning follows completed research artifacts, not an unbounded self-triggering chain.
- Include at least one explicit "stop planning; use normal scheduling" condition to avoid spending most of a session orchestrating itself.

## 6. UX integration

**Reuse Project → Research Sessions → Strategies.** Do not add a coordinator dashboard or expose an editor for every internal plan.

Within the existing Research Session pane, show only actionable concise decisions, such as:

> Redirected “Spectral Bound” to test assumption P using artifact A17 from “Dirichlet Approximation.” Result pending.

For each decision, the user can inspect the cited source artifacts, proposed action, critique, actual follow-up step, and observed outcome. Label **proposed** versus **executed** clearly. Existing stop, restart, session supervision, and report/paper export should continue to work and include decision lineage where relevant.

A human can override, reject, or redirect a pending decision through existing controls or the smallest justified extension. Human interventions are recorded with attribution and must not masquerade as agent discoveries. Do not add speculative advanced controls merely because the coordinator has an internal plan.

## 7. Evaluation: falsify intelligence, not just verify wiring

Predefine tasks and hold evaluator answers/rubrics separately from SIGMA inputs. Compare against the existing **A18 fair-rotation coordinator as baseline**, with the same model, budget, source material and task assumptions. A convincing written rationale is not a success metric.

### Deterministic fixtures (mandatory)

1. **True transfer:** A's saved artifact establishes a restricted lemma/bound needed by B. Confirm the coordinator directs B to the corresponding concrete check; the dispatched prompt names the source ID; the resulting artifact links to the coordinator decision.
2. **False transfer / domain mismatch:** A's counterexample violates an assumption of B. The coordinator must refuse to mark B disproven; if it proposes a test, it must identify the scope mismatch.
3. **Negative result with value:** A fails but eliminates one mechanism that B was going to repeat. Confirm B avoids redoing it or explicitly records a materially changed premise.
4. **Complementary partial findings:** A and B each address distinct obligations of a common problem. Confirm the coordinator proposes an explicit composition/check without claiming the whole objective is proved.
5. **No-op control:** Two strategies have similar vocabulary but no sound connection. Confirm no wasteful redirection or fictitious dependency.
6. **Reversal:** A later artifact retracts the source finding. Confirm subsequent plans mark the prior influence superseded/retracted, do not erase history, and revisit downstream assumptions.
7. **Out-of-order concurrency:** A new source artifact arrives while a target Investigator call is already running. Confirm the plan applies only to later dispatch and cannot rewrite the active call's prompt or result.
8. **Failure controls:** Bad references, malformed model output, exceeding context or budget, canceled planning, unavailable Python runtime, duplicate review, and reload all preserve an honest, recoverable state.
9. **Legacy compatibility:** Single-strategy sessions retain A18 behavior, including evidence and reporting, without unnecessary coordinator calls.

Use fixtures where a **bad coordination decision would produce a visible, testable wrong next action**. Do not merely assert that the planner returned well-formed JSON.

### Research-quality evaluation (separate gate)

Evaluate at least two distinct domains, with no answer leakage. Candidate suites:

- **Mathematics / algorithms:** a multi-lemma or multi-approach problem with external reference solutions, negative-control lemmas, and a point where one strategy's insight is genuinely useful to another. The shipped Maximum Regions sample is unsuitable for independent discovery because its strategy includes the answer; construct fresh answer-free inputs.
- **Experimental reasoning:** the Unexpected Oscillation scenario, with contradictory measurements and known confounders. Reward identifying a discriminating experiment and refusing unwarranted certainty, not an invented discovery.
- **Hard investigation:** a constrained RH-inspired or other unsolved-like exploration scored for real, checkable constraints and falsified mechanisms, *not* for claiming a solution.

Track **decision precision** (fraction of interventions grounded and useful), **cross-strategy transfer success**, **wasted/repeated steps avoided**, **new obligations closed**, **correct final results where an oracle exists**, **false transfer/false refutation rate**, **extra model calls**, **wall time**, **budget consumed**, and **effect of coordinator on result versus fair rotation**.

Precommit rubrics, task inputs, reference answers, max call counts, and stopping criteria before live tests. Provide full result tables, including failures; do not cherry-pick or relabel Easy/Medium failures. A finite suite cannot prove general intelligence.

### Acceptance thresholds (proposed; adjust against initial measured baseline)

- All mandatory safety/provenance fixtures pass with **zero fabricated or dangling evidence links**, zero unbounded planning loops, and zero stale-plan applications.
- Positive/negative/no-op fixture actions change **actual future execution**, not just displayed summaries.
- At least one cross-strategy combination leads to a measurable closed obligation or correct discriminating test in a controlled evaluation.
- On held-out evaluations, report whether coordination improves outcomes **net of extra call cost**; if it does not, mark research-quality acceptance **failed/inconclusive** and diagnose rather than declaring success.
- No live model trial is represented as a verified theorem absent independent verification.

## 8. Implementation sequence and boundaries

**Phase 0 — reconcile after A18 merges.** Inspect actual merged services, A18 statuses and PR changes since reviewed head, and A19's integration status. Map existing fields/functions to this spec. Remove any duplicate requirements and document the exact uncovered mechanisms. This draft is **not** permission to modify active Blue/Green branches.

**Phase 1 — causal trace without new model reasoning.** Persist decision-to-step linkage and write fixtures demonstrating which A18 scheduling decisions actually occur. Establish baseline fair-rotation results and context/budget measurements.

**Phase 2 — bounded influence proposals and validation.** Add a typed planner result, deterministic reference checks, targeted substantive critique, no-op, stale-snapshot rejection, and failure-safe baseline fallback.

**Phase 3 — controlled action execution.** Route accepted next questions/tests/priority changes into A18's scheduler at safe wave boundaries, capture consumed decision IDs, and evaluate results. Connect genuine A19 execution artifacts when available. Avoid adding a new orchestrator runtime if the existing worker can do the job.

**Phase 4 — evaluation and integration.** Run adversarial fixtures, existing A18/17/20 regression suites, real-browser supervision checks, and an authorized conservative ChatGPT-plan live comparison. Record actual runs, spend, failures, and limitations in `docs/STATUS.md`; prepare a reviewable PR. Do not self-merge.

## 9. Out of scope

- Replacing A18's bounded concurrent engine, inventing a new research-session UI or strategy identity model.
- Unbounded autonomous model calls, uncontrolled self-forking, speculative dashboards.
- Claiming that an LLM critique or Python numeric experiment formally verifies mathematics.
- Cloud deployment (A22), persistent distributed worker orchestration, or a general-purpose Codex development manager.
- Silent promotion of model-generated strategies into durable user-authored strategies.

## 10. Exit report

When implemented, report **engineering gate** and **research-effectiveness gate** separately:

1. What cross-strategy decisions can SIGMA actually make now that A18 could not?
2. Which exact saved artifacts caused each representative decision, and which later actions consumed it?
3. Which counterexamples or hold-out tasks defeated the coordinator? How were those failures handled?
4. Did outcome quality improve relative to A18 fair rotation under comparable budgets, or was the added model overhead unjustified?
5. What remains unknown, untested, or blocked?

**The definition of success is not “the coordinator sounds intelligent.” It is that a real result in one strategy changes another strategy's work for a sound, inspectable reason and yields measurably better research decisions.**
