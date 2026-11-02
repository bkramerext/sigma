# SIGMA report-generation quality: current Chat–Blue protocol

**Effective 2026-11-01.** **Scheduling clarification (latest human instruction):** scheduled coordinator wakes are fixed at **02:45 PST on 2026-11-01, then 03:45, 04:45, etc., at :45 hourly**; the corresponding Blue report targets are **:40**, five minutes before the *next* wake. No special 02:15 delay remains. This supersedes the earlier :00 example below and the obsolete hold mentioned in the immutable first checkpoint. Use explicit `-08:00` offsets after the DST transition. A checkpoint with unfinished papers is not a completed iteration, even when `message_in_N.md` exists; await the matching immutable completion addendum before publishing `message_out_(N+1).md`. Do not rewrite historical numbered messages.

 This is the active, independent **three-project report-quality** study. The Sovereign AI Federation/diagram study retained below is historical; its two-hour cadence, branch, mailbox, and single-sample goals are not instructions for this experiment.

**Workspace:** one draft PR against `main` using branch `report-quality-coordination`. Chat publishes immutable `messages/message_out_N.md` and Blue replies in immutable `messages/message_in_N.md`. Numbering starts at **1**. The human bootstraps Blue with a pointer to `message_out_1.md`; after that, GitHub messages form the durable handoff. Keep unrelated earlier mailbox names and experiments unchanged.

## Objectives and roles

Improve the **complete, substantive research paper**, rather than celebrating isolated features, diagrams, snippets, or successful compilation. Every substantive iteration generates, inspects, and compares complete TXT/TeX/PDF reports for **all three**:
1. **AI Agent Reliability and Evaluation**: long multi-session engineering evidence, failures, architecture, contradictions, and cross-session synthesis.
2. **AI Sovereignty**: architecture, governance/policy, cost-quality trade-offs, and competing system proposals.
3. **Xenopus Tadpoles**: scientific hypotheses, evidence versus conjecture, methodology, alternative explanations, and uncertainty.

Use the *actual* named saved research projects and frozen sources. Do not substitute the previous Sovereign AI Federation diagram experiment or simplified toy projects. If a project or source bundle cannot be found, say exactly what is missing, preserve what can be tested, and do not present an invented or synthetic paper as a real baseline.

**Chat:** research director, architecture, hypotheses, challenge design, independent evaluation, comparative scorecards, acceptance/rejection, next experiment and time allocation. **Blue:** implement bounded changes, run controlled experiments, produce *full* artifacts, assess quality and regressions critically, report source identities, timings, costs and failure evidence. Blue must actively challenge ineffective direction; Chat must not accept Blue's self-evaluation without inspecting the artifacts.

## Schedule and measured effort

- Chat's fixed scheduled review cadence is **2026-11-01 02:45 PST (UTC-08:00)** and hourly thereafter at **:45**; the next submission target is always **:40**. The initial immutable message used an earlier schedule and remains as a historical record, not an instruction to shift future wakes. Daylight saving time ends on this date: specify **offset-aware timestamps** to disambiguate the repeated 01:00 hour. Review is a scheduled opportunity, not proof of continuous operation.
- Every coordinator `message_out_N.md` must name the **next scheduled wake time**, the submission target **five minutes earlier**, and the actual handoff publication time. The *real* Blue work window starts when Blue receives and begins that message, not when Chat wakes. Adjust the scope to the remaining interval, allowing sufficient time for all three complete reports.
- **Troubleshooting is productive engineering time, not a protocol violation.** Blue may need to diagnose, implement fixes, rebuild and retest before any paper can be generated. Timebox fruitless loops, preserve durable checkpoints, and choose the simplest safe fix. In its outgoing report, distinguish root cause confirmed versus suspected; record errors/reproduction, fix SHA, affected projects, retries, test evidence, troubleshooting minutes, incomplete results, revised completion estimate and explicit asks. If blocked at the deadline, publish a safe, truthful status checkpoint if feasible, then continue the assigned work rather than manufacturing a complete three-paper result. Chat must factor troubleshooting delays and the real start time into the next assignment; no punitive attempt to compress unfinished work into a later deadline.
- Blue aims to push the code, **all three** full evaluated reports, tests and matching `message_in_N.md` **at least five minutes before Chat's next wake**. Blue logs actual work-start and push times. Do not abort unsafe in-flight operations, discard saved progress, rush partial reports into an accepted state or fake results to hit the clock. If late, checkpoint safely, explain precisely what completed and why, and finish the honest response; Chat must not advance to iteration N+1 before reviewing a matching response.
- Blue polls the **same branch** every ~30 seconds **only after** its matching `message_in_N.md` is committed and pushed and its tree is clean. Polling stops **immediately upon receipt** of `message_out_(N+1).md`; it does not run during active implementation or after receiving an assignment. Poll with safe fast-forward-only synchronization; no force push/reset. Never claim persistent polling exists after the process terminates.
- Each handoff records: `wake_at`, `out_pushed_at`, `blue_started_at`, `target_at`, `in_pushed_at`, `early_or_late_minutes`, blue active minutes, coordinator review minutes, scope carried forward and reasons for delays. Blue includes its own measured execution breakdown. Chat uses the gaps to give Blue more challenging work if consistently early, or reduce/chunk work and coordinator overhead if consistently late. **No iteration quota**: converge early when quality plateaus; continue if meaningful improvements continue.

## Evaluation, escalation and acceptance

- Establish a reproducible **three-project baseline** first. Freeze source evidence for before/after comparisons. For each candidate, evaluate complete manuscript extent, argument development, key claim support and source links, contradiction handling, unresolved obligations, discipline-specific rigor, technical accuracy, concision, TeX/PDF fidelity, reliability, latency and cost. Compare against the **best accepted baseline**, not merely the prior output.
- Increase challenge methodically: richer evidence, conflicting or negative findings, cross-session dependencies, deeper technical analysis, scientific alternatives, and edge cases. Form hypotheses, change controlled variables when possible, document what was actually learned. Do not spend all night on an easy example; do not treat a good diagram in a two-paragraph paper as success.
- A correct rendering or passing CI is **engineering success**, not experimental proof or research-paper acceptance. Read complete artifacts for **all three**. Reject regressions in the paper's substance even when a feature improved. Preserve original model outputs and provenance; do not make unsupported claims sound verified.
- Blue's reply must include branch/implementation SHA, summary of changes, frozen project/source identities, full TXT/TeX/PDF artifact paths and hashes, actual measurements and comparisons, criticisms, regressions, incomplete work, costs, MET/UNMET/UNVERIFIED and its recommendation. Chat reviews these independently and writes the next experiment. Never fabricate evidence, imply simulations are live results, authorize merge/deployment, or pay for unapproved API calls. Use only separately authorized provider mode/funding; distinguish ChatGPT-plan usage from metered API costs.
- No cross-worker coordination. Do not coordinate or communicate directly with other Codex workers. Report dependencies, conflicts, and requests for other workers to your ChatGPT coordinator through the human.

---

## Archived prior experiment (not active for current study)

# Sovereign AI Federation — autonomous experiment

Issues: [#394 Sovereign AI Federation](https://github.com/bkramerext/sigma/issues/394), [#393 opt-in TeX diagrams](https://github.com/bkramerext/sigma/issues/393).

This branch `blue/sovereign-ai-federation` and its single draft PR are the canonical implementation and coordination workspace. Created from `main` at `2d0a564c731655d4ba7264fab826f96b12c63b96`. Keep all changes, tests, deliverables and mailbox messages here (or references to committed artifacts here). Do not touch the working tree containing 37 pre-existing untracked files; create a distinct worktree for this branch.

## Independent numbered mailbox, restarted at 1

- Coordinator writes immutable `messages/out_message_N.md`; Blue responds with immutable `messages/in_message_N.md`.
- Round **1** starts with `messages/out_message_1.md`, and Blue responds to `messages/in_message_1.md`.
- After posting inbound, Blue polls for the next outbound (2, 3, etc.) while preserving its work. The coordinator is scheduled approximately every **two hours**, but never advances the sequence without reading the matching inbound. This is a *minimum coordination opportunity*, not a work deadline or a mandate to interrupt active research.
- The older `blue_session` branch and its numbered messages are a historical experiment; do not reuse their numbering or files, and do not modify them.
- Nobody needs the human to relay ordinary messages. Material security or paid-cost approvals remain hard gates, not implied permissions.
- Record every handoff's branch HEAD SHA, implementation changes, tests actually run, evidence/research/paper artifact locations and hashes, costs, and MET/UNMET/UNVERIFIED.
- Keep worktree and mailbox append-only where possible. Never force-push or overwrite either party's numbered messages.
- Do not merge or deploy. Full CI is for final readiness after local checks, not a debugging loop.

## End state

1. A high-quality Hard / Computer Science SIGMA sample, **Sovereign AI Federation**, rooted in MindRouter's published goals and practical university sovereignty, cost, fairness and research-utility constraints.
2. Substantive Investigator/Skeptic research actually saved in SIGMA (not scripted responses represented as science), with traceable reasoning, counterarguments and unresolved questions.
3. A credible, typeset conventional TeX/PDF paper and a **second paper from the same frozen evidence** with diagrams enabled. Meaningful architecture and decision diagrams; honest attribution, realistic university cost and quality analysis, and safe compilation.
4. An independently reviewed and locally validated implementation, with a single PR and final CI when truly ready.
