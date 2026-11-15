# SIGMA Research Quality Charter

**Status:** Governing quality and coordination charter, 2026-10-24. Human-approved direction. Read with [SOFTWARE_FACTORY.md](SOFTWARE_FACTORY.md), [OUTCOME_QUALITY.md](OUTCOME_QUALITY.md), [DRAFT_INTELLIGENT_RESEARCH_COORDINATION.md](DRAFT_INTELLIGENT_RESEARCH_COORDINATION.md), and [Blue's operating protocol](BLUE_OPERATING_PROTOCOL.md). This document governs the **quality of the research machine**, not just the appearance of its outputs.

## Mission and success criterion

Build SIGMA into a coherent, maintainable workbench that conducts **genuine, cumulative, evidence-grounded investigations** of hard questions. A strategy is a narrow, bounded research idea within a project's larger goal; a session is one attempt, with durable artifacts, provenance, objections, and results. A failed session must not erase a strategy or its useful negative evidence.

Success is **not** twelve completed increments, polished reports, a model agreeing with itself, or a scripted showcase. Success is demonstrably better research behavior under controlled conditions, with transparent limits, than a simpler assistant given comparable resources. Preserve independent judgment: the coordinator must challenge weak mechanisms and poor evidence even when they appear to advance the schedule.

## Non-negotiable research principles

1. **Real research, not theater.** Distinguish unscripted model decisions from scripted offline fixtures and evaluator-authored answers. Never call a staged next action an autonomous discovery.
2. **Evidence classes stay separate.** A calculation, reproducible experiment, agent-reviewed claim, conditional argument, independent verification, and mathematical proof are not interchangeable. Neither hashes nor Investigator/Skeptic agreement verify the mathematics.
3. **Cumulative intelligence.** Persist findings, failures, assumptions, retractions, and open obligations. Carry a result across strategies only when there is a concrete, domain-valid, cited mechanism. Preserve the chain: source evidence → proposed influence → critique → decision → actual follow-up → observed result.
4. **Adversarial discipline.** Require counterexample searches, explicit assumptions, discriminating tests, skepticism of transfers, and willingness to record no actionable next step. Do not overinterpret finite tests as universal proofs.
5. **Actual execution and provenance.** When using Python or SageMath, preserve exact code, execution environment/status, observed output, source artifact, proposing role/step, and limitations. Failed, timed-out, or interrupted execution is not a mathematical refutation.
6. **No fabricated compression.** Context selection, summaries, Outcomes, exports, and TeX/papers must not silently drop decisive objections or invent missing reasoning. Historical artifacts remain immutable; absent evidence stays absent.
7. **Economy and coherence.** Favor understandable mechanisms with measurable benefits over extra planners, agents, abstractions, interfaces, and prompt complexity. Do not add a dashboard or new UI to demonstrate internal sophistication.
8. **Protect the product.** Maintain Project → Strategy → Session → Evidence semantics, durable history, Green's Simple/Advanced Outcome behavior, existing controls, and polished copper/dark UX. Major architectural removals, redesigns, or scope deferrals require the human's approval.
9. **Truthful verification.** Report MET / UNMET / UNVERIFIED. Source review, mock tests, browser checks, actual sandbox execution, and unscripted provider research establish different things. A merged PR is not research validation.
10. **No unapproved spending or release.** No paid/live provider calls or cloud publication without the human's explicit authorization and applicable security gates.

## Twelve-iteration research program

**Twelve is an approximate planning horizon, not a completion quota or permission to chase subgoals.** The original per-increment scope and its evidence remain in the immutable Blue mailbox and evaluation directories. Do not retrospectively invent a fixed twelve-item specification. The program's goals, across the remaining iterations, are:

- Establish durable, recoverable current research state and evidence-linked continuation.
- Enable meaningful, justified cross-strategy transfer while excluding unrelated or unapproved history.
- Feed genuine Python/Sage results and failures back into the next research decision, with complete attribution.
- Make Investigator/Skeptic criticism substantive, preserve objections, and avoid false proof claims.
- Present faithful, inspectable conclusions, reasoning, caveats, and exports without overwhelming the default UI.
- Stress-test adversarial examples, negative results, context limits, interruptions, provenance, and restart behavior.
- Compare SIGMA against a **matched-budget single-role baseline** and evidence-withheld controls on answer-free, blinded tasks; pre-register scoring and contamination exclusions.
- Consolidate and simplify when mechanisms fail to add value. Reserve time for integration, regression, reproducibility, and honest assessment rather than expanding features to fill increments.

**Known checkpoint:** Blue Increment 5 was integrated in PR #77. Its nine sessions used scripted offline provider responses, although actual Python/Sage execution and persistence were exercised. This is engineering/provenance progress, **not** autonomous research validation. Increment 6 was assigned as a main-based verification and blind-evaluation-readiness gate in `messages/blue_out_7.md` on `blue_session`. The blind experiment has **not** been authorized or run. Check current GitHub before asserting any later status.

### Acceptance questions for each increment

What new *research capability* was added or tested? What actual saved artifacts prove the behavior? Which decisions were scripted, which were model-generated, and which were independently checked? What negative or adversarial case was tried? What regressed? Would a simpler single-role system have done as well? What was the time, complexity, and provider-cost tradeoff? What remains UNVERIFIED? **Would we continue using this machine for a real investigation? Why?**

A 45-minute iteration may legitimately deliver verification, a negative finding, a narrowly scoped correction, or removal of demonstrably harmful complexity. It need not add features.

## Direct Blue collaboration: explicit SOFTWARE_FACTORY exception

**The human is NOT the messenger for Blue.** The ChatGPT coordinator directly writes numbered instructions to the GitHub mailbox on branch `blue_session`; Blue fetches and reads them, performs the work, and writes numbered handoffs back. This supersedes the human-relay assumption in SOFTWARE_FACTORY Sections 2–4 and 5A **for Blue only**. All other review, scope, isolation, authorization, and merge requirements remain in force.

**Canonical direction for this collaboration:**
- `messages/blue_out_N.md`: **coordinator → Blue**, new instruction.
- `messages/blue_in_N.md`: **Blue → coordinator**, completion report.
- The sequences are **independent**. Never infer that an `in_N` answers `out_N` merely because their numbers match; each message must name its predecessor/assignment.
- Blue commits/pushes work, tests, project exports and the immutable inbound report, then **fetches and fast-forward-pulls every ~30 seconds** while waiting for the next coordinator instruction. Polling resumes after each completed iteration; it stops on receipt of the next assignment. No dirty-tree resets or force pushes. A running worker is required for actual polling.
- The coordinator inspects the actual GitHub diff, tests, saved project exports, research provenance, and message before issuing the next numbered instruction. Do not duplicate assignments.
- Target **~45 minutes of substantive work per increment**, leaving ~15 minutes in the hourly coordination cycle for review and dispatch. Blue reports start/end times, **actual elapsed minutes**, blockers, incomplete work, and next suggestions in each handoff. At the 45-minute boundary, checkpoint and report unfinished work rather than silently running on. Increase/decrease the next scope if the prior iteration finished substantially early/late.
- The scheduled coordinator checks **hourly**, not continuously. Do not imply instant response or autonomous work when a session/automation is not actually running.
- **No overnight merges into main.** Preserve reviewable checkpoints for the morning. Blue never self-merges. Integration should be frequent at approved checkpoints, with combined regressions and independent coordinator review.
- No direct worker-to-worker coordination, unauthorized paid calls, unrelated UX changes, or sweeping architectural edits.

**Existing-document discrepancy:** `BLUE_OPERATING_PROTOCOL.md` currently uses opposite directional labels in places; its older wording and examples are not authoritative over the explicit directions above. Reconcile that document in a separate scoped correction, preserving mailbox history rather than rewriting old messages. Also reconcile any duplicate/outdated coordinator automation before relying on unattended operation.

## Independent review and evidence gate

For every substantial Blue handoff, the coordinator must read the assigned scope and subsequent human decisions, inspect the exact changed head and actual implementation, check committed reproducible tests/exports and CI, classify requirements MET/UNMET/UNVERIFIED, and request corrections in the same work stream where appropriate. Claims in Blue's report are evidence to test, not approval. Preserve missing logs as missing; never reconstruct fictitious test runs. Distinguish real Chrome, real Python/Sage, offline scripted provider, and live unscripted provider work.

The **blind research-quality gate** must freeze answer-free tasks, hidden evaluator keys, matching model/budget/tools, evidence-present and evidence-withheld conditions, independent scoring, integrity no-go rules, and authorized maximum cost *before* any live run. A favorable report is not proof of multi-agent advantage. If the matched baseline performs as well, simplify or redirect the architecture rather than rationalize the overhead.

## Recovery after chat or browser restart

1. Read this charter and `docs/SOFTWARE_FACTORY.md`.
2. Fetch current `main`, `blue_session`, both mailbox sequences, the latest evaluation manifests/exports, open PRs, CI, and the relevant canonical tickets.
3. Reconcile the last **completed** Blue report, latest **assigned** instruction, branch heads, active/blocked status, unmerged changes, and spending authorization. Do not guess that an instruction was received or executed.
4. Review the current iteration against this charter, then either provide one specific corrective instruction or the next bounded assignment.
5. Record any lasting decisions and limitations in GitHub, not just conversation memory.

**Governing principle:** Do not sacrifice the quality of the finished research machine to achieve the next iteration's subgoal.
