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

**Mandatory instruction in every worker-facing message:** Include the exact rule **“Do not coordinate or communicate directly with other Codex workers. Report dependencies, conflicts, and requests for other workers to your ChatGPT coordinator through the human.”** This requirement applies to initial ticket assignments, follow-up tasks, correction requests, rebase requests, and handoffs. Do not assume a worker remembers the rule from an earlier message. Workers may read shared repository artifacts and integrated code, but may not directly instruct, message, or negotiate with other workers. The human and ChatGPT coordinator remain the only authorized coordination path.

**No worker-to-worker coordination.** Blue, Green, Gray, and Red do not send each other instructions, negotiate APIs directly, or silently modify each other's branches. Dependencies, collisions, or discoveries are reported to the responsible ChatGPT coordinator through the human. The coordinator decides sequencing, interface contracts, and reassignment. If an issue crosses the local/cloud boundary, the human routes it between coordinators.

**Mandatory human dispatch presentation:** Whenever ChatGPT wants the human to communicate anything to a Codex worker, it must **first name the intended color explicitly outside the message block** (for example, **Send to Blue (T29)**), then provide **one complete, copyable block of the exact text to forward**. This applies to initial assignments, corrections, rebases, merge notifications, dependency updates, stop/wait instructions, and requests for evidence. Do not replace the block with paraphrased advice, mix multiple worker instructions into one block, or assume that writing the block delivers it. If more than one color needs instructions, provide a separate labeled copyable block for each. Never instruct one color to contact another directly. When no communication is needed, do not manufacture a forwarding message.

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

## 5A. Explicit review, merge, and message-passing state machine

The normal work cycle is **ASSIGNED → IMPLEMENTING → R4R → REVIEW → (CHANGES REQUESTED → IMPLEMENTING → R4R)* → APPROVED → MERGED → INTEGRATION VERIFIED**. A PR can be merged without overall product acceptance; release signoff is a separate human decision.

| Event | Who initiates | Required response | Who owns next action |
|---|---|---|---|
| Assignment ready | ChatGPT coordinator | Send one copyable message to the human; human forwards it to the named color and confirms when necessary | Human dispatch, then Codex |
| Worker blocked or dependency found | Codex | Write a concise handoff; do not contact another worker or alter another branch | ChatGPT decides resolution; human forwards any new instruction |
| PR ready for review (R4R) | Codex | Provide PR URL/number and repository message-file path; report executed tests and remaining gaps | ChatGPT |
| Review finds defects or missing evidence | ChatGPT | Send a single actionable, copyable correction request tied to the existing ticket/PR; do not create a new ticket for routine fixes | Human forwards; same Codex worker corrects |
| Review approves | ChatGPT | Verify current head SHA, mergeability, intended scope, and evidence; record outstanding integration obligations | ChatGPT merges under standing human authorization |
| Branch conflict or stale base | ChatGPT or GitHub | Explain exact conflict and expected combined behavior | PR-author Codex rebases/resolves, retests, resubmits R4R; ChatGPT re-reviews |
| PR merged | ChatGPT | Tell human PR number, merge SHA, what is complete, and what remains unverified | Coordinator schedules combined tests; human may redirect priorities |
| Integrated product ready | ChatGPT and workers | Exercise relevant workflows on updated main and report MET/UNMET/UNVERIFIED | Human decides alpha acceptance |

**Merge authority is deliberately asymmetric.** Codex workers must never merge their own PRs. ChatGPT coordinators conduct the independent review and may execute the merge within their assigned domain under the human's standing authorization. The human can pause, veto, or require explicit approval for any merge. A coordinator does not merge another coordinator's domain without an agreed handoff. Review and merge should not be delegated back to the PR author merely because that author reports tests passing.

**Review means more than reading the PR description.** The coordinator reads the worker's `messages/` handoff file, examines changed code and tests, compares against the ticket, checks merge state and relevant dependencies, and evaluates whether the claimed checks actually support the acceptance criteria. A green test report from the author is evidence, not independent verification. If review is incomplete, report it as pending rather than silently merging.

### Requirement Traceability and Review Completeness

**Requirement completeness is a merge gate.** Before approving a substantive PR, the ChatGPT coordinator must reconcile the delivered implementation against:

1. The canonical ticket and its acceptance criteria.
2. Subsequent human-approved clarifications and decisions.
3. Corrections requested during earlier review rounds.
4. Applicable integration, security, compatibility, and UX requirements.

For **each substantive requirement**, record its disposition and supporting evidence in the PR review or a durable, linked review handoff:

- **MET:** The implementation and relevant verification evidence demonstrate the requirement.
- **UNMET:** The implementation is missing, incorrect, or violates the requirement.
- **UNVERIFIED:** The implementation may exist, but sufficient evidence is unavailable.

Worker-reported test results are **evidence, not independent verification**. The reviewer inspects the actual code and tests, challenges test coverage, and explicitly distinguishes what was established by source inspection, what the worker reports executing, and what the coordinator independently executed or observed. A green suite does not excuse missing acceptance coverage. Review the **current PR head**, not an earlier revision.

**Do not approve or merge a PR with UNMET mandatory requirements.** UNVERIFIED requirements must receive sufficient additional verification before approval or be explicitly documented as outstanding, with the human's informed acceptance. Any change or deferral of mandatory ticket scope requires **explicit human authorization**, recorded with the affected requirement and rationale; a coordinator cannot unilaterally drop it. Preserve subsequent clarifications and authorized deferrals in the ticket or a durable linked handoff so they are not lost in later iterations. An accepted PR-level limitation is not automatically a release acceptance or authorization to bypass separate security/deployment gates.

**Corrections stay in the same PR.** The coordinator sends one consolidated correction message to the original color; the worker updates the branch, executes appropriate regressions, updates its message file, and announces **R4R again**. ChatGPT re-reads the changed head and message file before approving. Do not merge on the basis of an earlier review after the branch changes.

**Message-passing path:** `Codex → repository message file + R4R notice → human → ChatGPT coordinator → copyable response → human → same Codex`. ChatGPT may inspect GitHub directly, but does not thereby gain access to a worker's local terminal. The human is the transport between disconnected conversations; GitHub is the durable record. Messages should be addressed to a color and ticket, state the requested action, and distinguish decisions from suggestions. The coordinator must never assert that a message was delivered merely because it generated one.

**Post-merge discipline:** Notify the human of the merge result and immediately update the dependency picture. If another worker's branch is affected, send that worker a targeted update through the human. Run or assign cross-PR regression checks; do not mistake per-PR test success for a tested combined system. The final acceptance report names outstanding risks and explicitly identifies any unverified live-model behavior.

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

**Separate cloud security and deployment gate.** T22 cloud functionality needs explicit, independent acceptance of tenant/workspace isolation, authentication and session revocation, durable execution and recovery, enforced cost/call limits, and guest/denied-account restrictions. Include adverse-case and cross-tenant tests, threat/security review, deployment configuration, and documented operational rollback as applicable. **Passing local alpha checks does not authorize public deployment.** Cloud publication requires the human's explicit signoff on this separate gate; incomplete or unverified security requirements block public release unless the human explicitly resolves their disposition without misrepresenting the risk.

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

## 10. Cold-start recovery: resume the factory without conversation history

A new human, ChatGPT coordinator, or replacement Codex session must be able to resume from GitHub alone. **Do not rely on memory of a previous chat or on an old worker terminal.** The first action is to reconstruct the actual state, not issue new assignments.

1. Read this protocol, `docs/HUMAN-AI-INTERACTION.md`, `README.md`, `docs/STATUS.md`, and `TICKET_TRACKING.md`. Read relevant `tickets/t*.md` in full.
2. Inspect **current GitHub state**, not just tracker prose: default branch HEAD, open PRs and their bases/heads, mergeability, latest commits, review comments, and `messages/` handoffs. Tracking files are snapshots and can lag reality.
3. Reconstruct a worker ledger: color, coordinator domain, assigned ticket, branch/PR, status, last confirmed human dispatch, blocker, next action, and whether tests were reported or independently reproduced.
4. Reconcile discrepancies with the human. Ask which worker windows are still active, which instructions were actually forwarded, and whether a worker has unpushed changes. Never infer live activity from an open PR.
5. Confirm **current authorization**: who may merge, whether provider calls are permitted, spending limits, release target, UX constraints, and any paused work. Prior approvals do not imply approval for a new paid action.
6. Check integration order and outstanding release gates; identify one critical path and independent secondary work. Only then dispatch or review.
7. Record the reconciled snapshot in the appropriate tracker/handoff so the next coordinator can repeat this procedure.

A useful restart summary is:

```text
Repository/main HEAD:
Coordinator domains and responsible human:
Release goal / target / blockers:
Color | ticket | branch/PR | last confirmed dispatch | state | next owner/action
Open PR review queue and merge order:
Outstanding integration/acceptance criteria:
Paid-provider authorization:
Known local-only/unpushed work (human-confirmed):
Last reconciled date and evidence links:
```

**Source-of-truth precedence:** actual GitHub commit/PR state for repository facts; canonical ticket for scope; most recent explicitly confirmed human decision for authority and product intent; worker message files for *reported* execution; independent reproduction for *verified* runtime behavior. If these conflict, surface the conflict rather than silently selecting the most convenient account.

## 11. Replacing or recovering a worker

A color identifies a logical work slot, not a guaranteed persistent model identity. If a Codex window crashes, loses context, or must be replaced:

1. Freeze new assignments to that color and ask the human whether there are uncommitted or unpushed changes in its checkout.
2. Preserve the branch, PR, ticket, handoff, and any reproducible logs; do not discard local-only work without human approval.
3. Start the replacement in an isolated checkout on the **existing branch** where appropriate. Read this protocol, ticket, PR discussion, message file, current main, and changed files before coding.
4. Have the replacement state its understanding of scope, branch, blockers, and tests to rerun. Do not treat a previous worker's test claims as newly executed.
5. Continue the existing PR when possible, rather than creating duplicate tickets or competing PRs. Mark the handoff explicitly.

For a ChatGPT coordinator replacement, use Section 10. A coordinator conversation is not a running daemon; no work should be assumed to have progressed during the gap.

## 12. Operational conventions and tooling

**Repository:** `bkramerext/sigma`, default integration branch `main`. Tickets: `tickets/t<id>.md`; tracker: `TICKET_TRACKING.md`; worker-to-coordinator handoffs: `messages/`; implementation/test observations: `docs/STATUS.md`. The exact current filenames and commands should be verified in the checkout before execution.

**Local setup and checks:** The documented starting point is `./sigma setup`, `./sigma start`, and `./sigma test`. Run focused tests for the affected subsystem, plus browser checks under `browser_checks/` where relevant. Python/Sage sandbox tests may require Docker and prepared images. Distinguish a test that was *reported* from one the reviewer actually ran. Never claim that GitHub PR review itself ran local Chrome, Docker, or provider calls.

**Branch hygiene:** Base new work on current `main`; keep one primary ticket per branch/PR; avoid force pushes over other people's work; do not commit secrets, personal datasets, generated credentials, or bulky transient artifacts. If a branch has changed after review, review its new head. Use an expected head SHA at merge to prevent merging an unseen revision.

**Evidence retention:** A message file must contain enough to reproduce meaningful tests: commands, relevant environment prerequisites, base/head revisions, outcomes, and artifact locations. Temporary `/tmp` screenshots are not durable evidence. When a screenshot or log is essential to acceptance, attach it to an accessible PR artifact or commit a small appropriate test fixture, subject to repository policy. Redact tokens, email addresses, private paths, and user data.

**Change control:** Human discussion does not automatically authorize repository edits. Obtain explicit authorization for changes when required by `docs/HUMAN-AI-INTERACTION.md`; standing permission to review and merge assigned PRs is not blanket permission for unrelated direct edits. For consequential architecture, security, billing, UX redesign, or release-scope changes, return to the human for a decision.

## 13. Exceptions, escalation, and rollback

**Stop and escalate** when a worker encounters an undocumented paid call, credential exposure, destructive migration, unexpected data loss, scope collision, unresolved security boundary, or a change that materially alters approved UX. Do not work around the constraint by switching accounts, providers, or billing modes. Report what happened, affected state, and the safest next action.

**Urgent defect discovered after merge:** record the symptom and reproducer, identify the introducing commit/PR, decide with the human whether to revert or issue a narrow fix, and assign an owner. A revert is not automatically safe if later PRs depend on the change; inspect dependencies and retest. Keep the original ticket/PR history intact and document the corrective commit.

**Blocked worker:** report the precise dependency and whether independent work can continue. The coordinator can park the ticket, move the worker to another bounded task, or request a small interface agreement through the human. Do not let blocked workers silently idle or invent interfaces.

**Unavailable reviewer/coordinator:** leave the PR unmerged. R4R is not self-approval. The human can explicitly reassign independent review to another coordinator.

**Unclear human dispatch:** treat the message as *not yet sent* until confirmed or evidenced. Avoid issuing conflicting follow-ups to an unconfirmed worker.

## 14. Decision and status hygiene

For every significant decision, record **what changed, why, who authorized it, which ticket/PR it affects, and what remains to verify**. Prefer updating the canonical ticket or a short linked handoff over scattering decisions across chat. Do not rewrite history to imply that a changed plan was always intended.

Keep these statuses distinct: `PROPOSED`, `ASSIGNED (dispatch unconfirmed)`, `DISPATCHED`, `IN PROGRESS (worker reported)`, `BLOCKED`, `R4R`, `CHANGES REQUESTED`, `APPROVED`, `MERGED`, `INTEGRATION VERIFIED`, and `ACCEPTED`. A ticket may be merged but have an explicitly **UNVERIFIED** quality criterion.

At the end of an integration cycle, the coordinator should provide a concise ledger of completed merges, PRs still in review, worker availability, blockers, critical path, and what the human must do next. **Never promise work is happening in the background unless a real persistent executor has been dispatched.**

## 15. Maintenance of this protocol

This file is the stable operating contract; `TICKET_TRACKING.md` and current PRs hold volatile assignment state. Avoid turning this protocol into a daily status log. When practice changes, update the affected rule here, explain the rationale in the commit, and ensure worker assignments refer to the current protocol. Periodically check for contradictions with `docs/HUMAN-AI-INTERACTION.md`, ticket instructions, and actual observed behavior.

A future team should be able to answer without the original chat: **Who decides? Who sends? Who codes? Who reviews? Who merges? Who tests the integrated result? What is actually running? What is still unverified? What happens if a participant disappears?**

This protocol should evolve when the team changes its actual practices. Amend it based on observed behavior, not an idealized account of autonomous development.
