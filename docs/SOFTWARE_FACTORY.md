# SIGMA Software Factory

This document is the operating protocol for developing SIGMA with a human engineering lead, ChatGPT coordinators, and parallel color-identified Codex workers. It describes **how we build SIGMA**, not SIGMA's own research-agent architecture. It is a working agreement, not a claim that agents execute autonomously.

## 1. Participants and authority

| Participant | Responsibility | Authority and limits |
|---|---|---|
| **Human engineering lead** | Product vision, architecture and UX decisions, priorities, constraints, budget authorization, worker dispatch, hands-on product evaluation, release signoff | Final authority. May override assignments, challenge coordination decisions, and stop or redirect work. Manually forwards instructions between otherwise disconnected sessions. |
| **ChatGPT coordinator** | Clarify intent, propose architecture, scope T-tickets, assign workers, sequence dependencies, inspect GitHub code and PRs, review evidence, request corrections, merge reviewed PRs under the human's standing authorization, maintain integration and release status | Coordinates work, but does **not** secretly operate local Codex windows or run continuously between chat messages. Repository inspection is not local execution. Escalates consequential product/UX changes and paid calls. |
| **Codex workers** | Implement assigned tickets, maintain code and tests, run focused/full checks, exercise browser/CLI when relevant, document findings, resolve their own PR conflicts, and submit reviewable PRs | Work only within assigned scope. Do not self-merge, reassign other workers, or communicate directly with other Codex workers. |
| **GitHub** | Durable shared memory and integration boundary | Tickets, code, tests, PRs, commit history, review handoffs, and tracking provide the record. Conversation memory alone is not authoritative. |

A second ChatGPT conversation may coordinate a distinct domain. For example, cloud deployment (Red) is coordinated separately from local alpha (Blue, Green, Gray). The boundary is explicit: one coordinator does not assume ownership of the other's work. The human mediates cross-domain priorities and decisions.

**Accountability:** The coordinator must distinguish *assigned*, *started*, *reported complete*, *reviewed*, *merged*, and *accepted*. Assigning work does not make it run. ChatGPT cannot claim background execution without an actual persistent worker or scheduled mechanism.

## 2. Color identity and ownership

Colors identify **persistent Codex sessions/terminal windows**, not PR status or severity. Color-coding was adopted because terminal titles were unreliable. Use the color in every assignment and handoff to avoid sending instructions to the wrong worker.

| Color | Typical focus | Current Day 3 example (2026-10-23) |
|---|---|---|
| **Blue** | Research orchestration, agent/session behavior, model controls | T29 human guidance/intervention |
| **Green** | Python/Sage execution, computational evidence, data and CLI tooling | T30 exported-project-to-sample conversion |
| **Gray** | UI, browser acceptance, integration validation | T21 browser acceptance completed; reassigned T17.8 research-quality acceptance |
| **Red** | Cloud deployment and access | Cloud tickets, coordinated in separate ChatGPT conversation |

These are **specializations, not permanent silos**. The coordinator can reassign workers as capacity and critical path change. Ticket ownership, rather than color, defines the current modification boundary. Workers should not touch another worker's active area without coordinator authorization.

The human keeps the color windows open and forwards instructions to the corresponding session. ChatGPT can advise dispatch, but cannot directly send to those local sessions through this conversation.

## 3. Ticket and assignment contract

Canonical implementation tickets live in `tickets/tN.md` (including dotted IDs such as `t17.8.md`); `TICKET_TRACKING.md` records owner, state, dependencies, and PR links. Keep existing tickets updated rather than creating duplicate tickets for small clarifications or review corrections.

A good ticket or dispatch states:

1. **Objective and scope:** desired user-visible or system behavior, what is explicitly out of scope, and the branch/base to use.
2. **Acceptance:** observable success criteria, adverse cases, persistence/recovery, and required tests.
3. **Constraints:** established UX/design, security/billing, model and thinking budget where applicable, compatibility, and no unrelated churn.
4. **Ownership:** one accountable worker, any known dependencies, and areas not to modify.
5. **Deliverables:** code, tests, docs/tracker updates as needed, a PR, and a coordinator handoff with evidence.
6. **Stop/escalation conditions:** blockers, unclear requirements, risky redesign, provider charges, or overlapping work.

Human-facing assignments must be supplied as **one copyable message block** addressed to the worker, not scattered across commentary. The human explicitly confirms dispatch when it matters. Do not assume a proposed message was forwarded. The coordinator is the sole channel for instructions and changes of ownership within its domain.

Example dispatch shape:

```text
GRAY: Take T17.8 on current main. Read tickets/t17.8.md.
Scope: deterministic/mock research-quality acceptance.
No paid provider calls. Do not coordinate with other Codex workers.
Run ./sigma test and focused acceptance checks.
Document MET/UNMET/UNVERIFIED with evidence.
Open a PR, mark R4R, and do not self-merge.
Write a message file for coordinator handoff.
```

## 4. Worker isolation and message protocol

**No worker-to-worker coordination.** Blue, Green, Gray, and Red do not send each other instructions, negotiate APIs directly, or silently modify each other's branches. Dependencies, collisions, or discoveries are reported to the responsible ChatGPT coordinator through the human. The coordinator decides sequencing, interface contracts, and reassignment. If an issue crosses the local/cloud boundary, the human routes it between coordinators.

**Outbound, coordinator → worker:**
- Use a copyable, self-contained assignment prefixed with the worker color and ticket.
- Reference the canonical ticket and expected base branch.
- Specify what changed since the last assignment, the exact ask, constraints, and whether the worker should wait.
- State explicitly when a message is a proposed draft rather than already dispatched.

**Inbound, worker → coordinator:**
- Worker reports **R4R** (ready for review) with PR number/link, ticket, branch, base, and any dependencies.
- Worker writes a **repository message file** under `messages/` (for example, `messages/t21_gray_alpha_acceptance.txt`) and links it from the PR description.
- The message file summarizes implemented behavior, tests actually executed and results, relevant screenshots/artifacts, conflicts/rebases, known limitations, and any unmet criteria. Include whether provider calls or costs occurred.
- The coordinator **reads the message file**, PR description, changed files, and test evidence before review. A terse “R4R” is not sufficient acceptance evidence.

No invented test results. Report skipped, unavailable, or inconclusive verification as such. Screenshots left only under a worker's `/tmp` may be inaccessible to the coordinator; preserve important evidence in an accessible artifact or provide a reproducible command. Distinguish code inspection, automated tests, real-browser exercise, real sandbox execution, and real-provider quality assessment.

## 5. Git and PR integration protocol

- Each worker uses an isolated checkout/worktree and a ticket-specific branch targeting `main`.
- Keep changes narrow and avoid unrelated formatting, UI redesign, or other workers' ownership areas.
- Worker runs focused tests and `./sigma test`, plus CLI, real-Chrome, Python/Sage, or export checks as appropriate. If a check cannot run, explain why.
- Worker opens a PR, includes a concise description and message-file link, marks **R4R**, and **does not self-merge**.
- ChatGPT coordinator checks ticket requirements, message file, actual diff, tests, regression risk, integration dependencies, and mergeability. It can request another iteration rather than merge.
- **The PR author owns conflict resolution.** Coordinator explains the conflict and intended behavior. Worker updates from current `main`, preserves both sides' functionality, reruns affected checks, and returns R4R. Never resolve by blindly choosing one side.
- Coordinator rechecks the revised head and mergeability, then merges in dependency order, using an expected head SHA when supported. Merge is not proof of final product acceptance.
- After multiple PRs land, perform **combined integration checks** on updated `main`. Isolated PR tests are necessary but insufficient.

Review must account for downstream behavior, not just diff size. A fixture mismatch may be a test update rather than a product defect, but must be demonstrated rather than assumed.

## 6. Verification and release gates

SIGMA is being delivered as a **local alpha**, not production-hardened software. Prioritize functioning core workflows, bounded execution, coherent UX, recoverable failures, evidence integrity, and truthful limitations. Defer unrelated enhancements.

Verification layers are distinct:

| Layer | What it can establish | What it cannot establish |
|---|---|---|
| Source/PR review | Scope, plausible correctness, obvious bugs, architectural consistency | That the application ran successfully |
| Deterministic and mock tests | Contract behavior, failure handling, reproducible regression cases | Actual LLM research quality |
| Real browser/CLI checks | Integrated UI flow, persistence, exports, responsiveness, usability symptoms | Mathematical validity of model reasoning |
| Real Python/Sage sandbox runs | Computational execution, output, provenance, artifacts | Independent proof of a research conclusion |
| Real provider runs and expert evaluation | Evidence of actual model behavior and substantive output | General correctness from a single successful case |

No paid provider calls without **explicit human authorization**. At the time of this protocol, **none are authorized for T17.8**. Its mock-based criteria can be MET, while live-model research quality must remain **UNVERIFIED**, not passed. No silent model/account/billing fallback. Network/provider failures should produce a clear recoverable UI state.

Acceptance reports use **MET / UNMET / UNVERIFIED** with evidence and open obligations. The human retains final product and release signoff.

## 7. Operating cadence and schedule discipline

The coordinator maintains a current view of workers, tickets, PRs, blockers, and the critical path. When a worker becomes free, propose useful independent work rather than leave capacity idle while deadlines slip. Do not assign overlapping ownership simply to keep every color busy. Reprioritize explicitly when integration or quality acceptance becomes critical.

The human may challenge any staffing or priority decision. A recent example: the human challenged leaving Gray idle after PR #35; Gray was reassigned to T21 browser acceptance. The human also clarified that Gray must not coordinate directly with Blue. After PR #38 was reviewed and merged, Gray was reassigned T17.8, while Green stayed on T30. These are human-directed course corrections, not autonomous worker orchestration.

**Coordinator capacity is not background compute.** A ChatGPT coordinator that promises to “own” a ticket must either execute it during active tool-supported work, dispatch it to a persistent worker, or explicitly mark it unstarted. T17.8 exposed this failure mode: assigning it to ChatGPT did not make it progress between conversations. The correction was to give implementation/verification to Gray and retain ChatGPT review ownership.

## 8. Evidence from actual integration

The process has been exercised, not merely designed:

- PR #11 migrated work to durable T-tickets; PRs #12 and #13 underwent independent review, revision, and ordered integration.
- Gray's PR #35 fixed session-limit behavior and UI regressions. Green's T28 PR #36 rebased on that work, reran tests, and merged after review.
- Gray's T21 PR #38 documented real Chrome and Python/Sage acceptance. Its provider fixture was updated to include the new `computational_citations` schema field; the PR was reviewed and merged. The handoff was recorded at `messages/t21_gray_alpha_acceptance.txt`.
- T29, T30, and T17.8 remain subject to their own PR review and final integration. Do not treat assignment as completion.

See `WOLF.md` for the narrative, `WOLF_IDEAS.md` for writing ideas, `WOLF_TODO.md` for retrospective evidence gaps, and `docs/STATUS.md` for implementation and test observations.

## 9. Failure modes to watch

**Lost or ambiguous dispatch:** A message prepared by ChatGPT is not necessarily sent. Confirm handoff; keep tickets durable.

**Context fragmentation:** Separate conversations and Codex windows do not share live state. GitHub documents and PRs are the contract; coordinator must re-read current state.

**Worker collision:** Parallel branches can change the same schemas or UI. Respect ownership, rebase deliberately, and retest combined behavior.

**Overclaiming:** “Tests passed,” “PR merged,” “alpha accepted,” and “research works” are different claims. Preserve provenance and unresolved evidence gaps.

**Human overload:** The human forwards messages and exercises the UI, but should not become the default tester for every minor change. Assign browser and regression acceptance to workers; reserve human attention for product judgment.

**Visual and semantic drift:** A structurally functional UI may still be poorly polished or misunderstand strategy/session semantics. Preserve the established dark/copper visual system and require review before large UX changes.

**Unbounded scope:** Do not let new ideas, documentation, or cloud unknowns obscure the local alpha's critical path. Track follow-ups separately.

This protocol should evolve when the team changes its actual practices. Amend it based on observed behavior, not an idealized account of autonomous development.
