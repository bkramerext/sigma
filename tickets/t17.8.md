# A17.8 — Agentic solution quality and final A17 verification

Status: **ready for implementation/verification after A17.7**. This assignment consolidates the two deferred quality items; it is not a new research-framework redesign.

Read `docs/HUMAN-AI-INTERACTION.md`, `docs/ASSIGNMENT-A17.6.md`, `docs/ASSIGNMENT-A17.7.md`, and `docs/STATUS.md`. The A17.6 implementation and its 2026-10-22 deterministic/browser/live results are already recorded. **Do not erase or discount those results, and do not claim this final verification has run until it actually has.**

## Quality item 1: Actual agentic solution quality on a solvable problem

Use **Maximum Regions Formed by Lines** as the primary real-provider sample, not only a canned fixture. Its mathematical answer is `R(n) = 1 + n(n+1)/2`, but the quality test concerns **whether SIGMA's agents independently produce, critique, and recognize a complete supported solution**.

- Start with a fresh working copy and the normal research flow. Record the exact project question, strategies, selected provider/model/effort, configured limits, session IDs, costs/calls where available, and actual artifacts.
- Assess substance, not merely a positive status: the argument must show why line `k` creates at most `k` new regions and why a general-position construction attains the bound at each step.
- Confirm Investigator/Skeptic objections and coordinator conclusions address the argument; unsupported assertions, circular proofs, or incomplete constructions must not be promoted to independently verified proof.
- A complete supported solution may end with **no next path** and still be recognized as **objective achieved**. An unverified solution candidate must remain explicitly marked unverified.
- Strategy Assessments must credit the strategy or strategies actually supported by saved artifacts, not all active strategies automatically.
- If the run stalls, misclassifies success, fails to identify a material flaw, or produces empty/repetitive research, capture the failure with precise artifact references, implement a bounded correction, and rerun an appropriate regression. Do not tune the fixture to hide a real-provider weakness.
- Record limitations honestly. A real model run is an empirical quality check, **not** a guarantee of solving other problems or independent mathematical proof verification. Avoid unbounded paid calls; obtain approval before any extra billable provider experiments outside the existing connected-plan workflow.

## Codex operating procedure: own the investigation, not just the checklist

**You (Codex) are the responsible engineer and critical reviewer.** The assignment names objectives and boundaries, not a predetermined implementation. Do not wait for ChatGPT to diagnose each failed run or prescribe each edit. Exercise independent judgment, challenge the existing architecture and test assumptions, and distinguish actual product improvement from test-specific accommodation. Escalate only scope, billing, destructive changes, or consequential product decisions that require human approval.

Work in this order, iterating where the evidence warrants:

1. **Reconstruct the real pipeline before testing.** Trace the current project/strategy input, Investigator and Skeptic prompts and structured outputs, coordinator decision, objective assessment, evidence/verification labels, persistence and UI/report projection. Identify exactly where mathematical content is produced, challenged, interpreted and potentially misclassified. Review the A17.6 implementation and known failures in STATUS; do not presume that passing fixtures imply sound agent behavior.
2. **Write down falsifiable expectations before running.** For Maximum Regions, independently work out the necessary upper bound and attainability argument, plus plausible incomplete or subtly flawed variants. Specify what evidence would count as a correct candidate, a real objection, unsupported success, premature stopping, and useful continuation. Do not show the model the reference answer as part of the research prompt unless it is already part of the shipped sample; use the answer as an external evaluation rubric.
3. **Collect a baseline using the actual product.** Run the existing deterministic/mock tests first, then one bounded fresh-project real-provider session through the normal SIGMA flow when authorized/available. Preserve the original user-facing problem and strategy inputs. Capture ordered prompts/responses or their safe reproducible summaries, artifact IDs, decisions, objective/outcome labels, objections, attribution, call/budget consumption and any errors. Do not rely on the final badge alone.
4. **Audit the reasoning, step by step.** Read the Investigator's mathematical claims as if reviewing a proof; test each substantive inference, distinguish a proof from numerical examples, and verify whether the Skeptic caught genuine gaps rather than issuing generic criticism. Inspect whether the coordinator made a justified decision from available evidence, and whether the UI/report faithfully communicated it. Ask: would the same logic incorrectly accept a plausible false proof? Would it incorrectly reject a complete proof? Is it recycling the same objection or failing to use prior artifacts?
5. **Localize the failure.** Classify each defect as (a) research generation, (b) critical review, (c) coordination/termination, (d) objective or strategy attribution, (e) persistence/representation, (f) provider/transport/budget, or (g) UI. Cite the exact artifact and code path. Compare at least one alternative explanation before changing code. A weak model answer is not automatically a software bug, and a correct mathematical answer with a wrong status is not a reasoning failure.
6. **Choose the smallest general correction.** Prefer a prompt-contract, evidence-contract, decision-rule or context-continuity fix that improves reasoning on a class of problems. Do **not** hard-code Maximum Regions, insert its solution into general prompts, force a positive outcome, weaken verification labels, or add superficial keyword heuristics. If a structural change belongs to A18 rather than A17.8, document it and defer it instead of expanding scope silently.
7. **Build adversarial tests from the diagnosed failure.** Include a genuine complete argument, a convincing but incomplete argument, a material mathematical objection, a superficially plausible false argument, and a successful conclusion with no next step. Test the relevant role and coordinator boundaries, persistence, and browser-visible claims. Ensure the tests would have failed before the fix; avoid tests that merely mirror new implementation details.
8. **Rerun and compare.** First demonstrate that the new deterministic regression fails on the old behavior and passes on the fix. Then rerun the normal product scenario within the approved provider budget. Compare actual mathematical substance, critique specificity, correct outcome, call consumption and user-facing honesty, not just a green badge. If a fresh provider run is unavailable, stop at deterministic evidence and label the empirical quality question open.
9. **Check generalization.** Apply the same reasoning rubric to at least one *different solvable sample* already shipped with SIGMA, preferably one requiring a different proof mechanism. Use deterministic adversarial fixtures without additional paid calls by default. Check that the fix does not bias all research toward claiming completion or over-crediting strategies.
10. **Report a decision, not just a test log.** In STATUS, provide a compact baseline → diagnosis → change → before/after evidence table, the remaining weaknesses and whether another iteration is warranted. Explicitly say when the agents gave a poor answer but SIGMA represented it correctly, when a software defect was fixed, and when the result is inconclusive. Make a recommendation to accept A17, perform one more bounded correction, or defer a structural improvement to A18.

**Stop conditions:** Do not chase nondeterministic model quality indefinitely or spend extra provider calls to manufacture a pass. One bounded baseline and one bounded post-fix real-provider run are the default quality-trial budget, subject to available authorization; if no fix is justified, do not manufacture one. If evidence remains mixed, preserve it and report the uncertainty. Never claim independent mathematical verification merely because multiple model roles agreed.

## Quality item 2: Final integrated A17.6 verification

After A17.7 is merged, verify the **integrated A17.6 + A17.7** application end to end:

1. Maximum Regions deterministic completed-proof case, no-next-path success, and genuine incomplete/unverified/counterexample cases.
2. Research **objective outcome**, session **lifecycle/execution status**, and **strategy contribution** remain independent. Positive research must not erase stopped/failed/budget-exhausted execution.
3. **Strategy Assessments** table: Contributed to solution, Productive, Unproductive, Not used, Disabled; correct evidence/rationale, all strategies in project order, and historical eligibility snapshots unchanged by later edits/toggles.
4. Persistence and fidelity: save/reload/restart, historical sessions, JSON audit, text/HTML/LaTeX Research Report, and consistent caveats/evidence references. Legacy missing attribution must stay unknown.
5. Stop/resume, provider interruption/timeouts, budget limits, partial/failed assessment generation, toast visibility, and safe recovery without loss of committed artifacts.
6. Browser behavior after A17.7: session lifecycle and outcome summary, action placement, dialogs, export, tooltips and scroll containment. Reuse A17.7's visual checks rather than duplicating implementation work.

## Explicit exit criteria (human acceptance gate)

**SIGMA demonstrates that it can independently solve a tractable research problem, critically assess its own work, and accurately communicate the result.** Passing deterministic tests alone is insufficient. Codex must provide evidence for each criterion, and the human makes the final acceptance decision.

1. **Solution quality:** In at least one genuine end-to-end real-provider run of Maximum Regions, the agents produce a mathematically complete argument, not just the correct formula. The upper bound and attaining construction must both be supported.
2. **Meaningful criticism:** The Skeptic identifies material gaps when present, recognizes adequately supported reasoning, and does not invent objections merely to prolong research. Show adversarial complete and flawed cases.
3. **Sound coordination:** SIGMA recognizes when the research objective is achieved and terminates appropriately even if no further path is proposed; it does not confuse absence of next steps with failure.
4. **Calibrated conclusions:** Complete, incomplete, incorrect, and unverified claims are distinguished in saved evidence, outcome and UI. Multiple agents agreeing does **not** establish independent verification.
5. **Evidence-based attribution:** Each Strategy Assessment is justified by saved strategy-linked artifacts; unused/disabled/noncontributing strategies are not credited as solution contributors.
6. **Generalization:** Apply the same mechanism to at least one different, comparably tractable solvable sample with a different reasoning mechanism. Do not insert problem-specific shortcuts or the reference solution into agent prompts. Show deterministic adversarial coverage for both classes; if a second live run is not authorized, clearly limit the empirical generalization claim.
7. **Operational reliability:** Session lifecycle, resume/stop, persistence, history, export, error recovery, budgets and UI consistently preserve and communicate what happened. No data loss or misleading success on provider failure.
8. **Reproducible evidence:** Codex provides actual session/artifact references, exact test commands and results, screenshots where relevant, baseline versus corrected behavior, and an independent critical assessment of successes, failures and uncertainties.

**Stochastic qualification:** Do not require every nondeterministic model run to succeed. However, acceptance **does** require at least one authentic end-to-end Maximum Regions solution, plus adversarial evidence that plausible-looking incomplete or incorrect work is not automatically accepted. A failed or unavailable real-provider run leaves that criterion open; deterministic green tests cannot waive it. Avoid unbounded reruns to manufacture a pass; obtain human authorization if the bounded provider budget is exhausted.

**Decision question:** Could a user give SIGMA a different problem of comparable difficulty and reasonably trust it to investigate, challenge and assess its findings without intervention? Trust here means **reliable calibration of claims and evidence**, not assuming every generated answer is correct.

Codex must explicitly mark each criterion **met / unmet / unverified**, cite supporting artifacts, recommend acceptance or further bounded work, and present that assessment for human sign-off. **Do not declare A17 complete without that sign-off.**

## Evidence and exit criteria

- Run `./sigma test`, focused API/unit checks and real Chrome Playwright checks using isolated mock providers; inspect screenshots and recorded data. Add tests for any uncovered regression.
- Run and assess the **actual connected-provider Maximum Regions quality trial** if authorized/available; document model, limits, exact behavior and whether it genuinely met the objective. If it cannot run, explicitly leave real-agent quality **unverified** rather than marking the whole quality item passed.
- Record exact commands, results, costs if available, artifact/session identifiers, screenshots, failures and remaining caveats in `docs/STATUS.md`.
- Human reviews the results and accepts or requests fixes. **A17 is not declared complete, and A18 (Agentic Quality), A19 (Python Sandbox), A22 (Cloud Deployment) do not launch in parallel, until this final A17.8 gate is addressed.**

Out of scope: expanding A18 agentic-research architecture, A19 sandbox execution, A22 cloud work, or treating a solved sample as evidence that RH is solved.
