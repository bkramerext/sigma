# SIGMA Ticket Tracking

## Current main assignment update (2026-10-26)

| Issue | Owner | Status | Branch / handoff |
|---|---|---|---|
| #286 — Maximum Concurrent Sessions | Blue | **R4R** · [PR #287](https://github.com/bkramerext/sigma/pull/287) | `blue/issue-286-concurrent-sessions` · [ticket](../tickets/t286.md) · [handoff](../messages/issue_286_blue_r4r.md) |

| T279 — Invite me from sign-in pill | Blue | Implemented; local verification passed; R4R · [PR #281](https://github.com/bkramerext/sigma/pull/281) open, not merged | [ticket](../tickets/t279.md) · [issue #279](https://github.com/bkramerext/sigma/issues/279) · [handoff](../messages/issue_279_blue_r4r.md) |
| T277 — Hosted TeX generation HTTP 400 | Red | **R4R — safe API error classification; production cause and hosted generation UNVERIFIED** | [ticket](../tickets/t277.md) · [issue #277](https://github.com/bkramerext/sigma/issues/277) · [handoff](../messages/t277_red_paper_api_400.txt) |
| T81 — Invitation Requests, Feedback, and Privacy | Green | Invitation PR #225 merged at `f45ada5`; feedback/privacy code R4R on `green/t81-feedback`, validated head `756ae45b866f353e307596f5770dcd37ad06aeaa`; PR creation pending refreshed GitHub auth | [ticket](../tickets/t81.md) · [handoff](../messages/t81_green_feedback_privacy.txt) · [proposed privacy notice v1](../docs/PRIVACY_NOTICE_DRAFT_v1.md) · issue #81 remains open |
| #209 — Current Understanding AI strategy suggestion, copy-only | Green | Implemented; R4R · [PR #213](https://github.com/bkramerext/sigma/pull/213) | `green/issue-209-current-understanding-strategy` · [ticket](../tickets/t209.md) · [handoff](../messages/issue_209_green.txt) |
| T192 — Per-User Project Isolation | Codex | Implemented; R4R · [PR #223](https://github.com/bkramerext/sigma/pull/223) | `t192-per-user-project-isolation` · [ticket](../tickets/t192.md) · [handoff](../messages/t192_codex_handoff.txt) |

**Snapshot:** October 23, 2026 (Days 0–3; updated during PR #11 integration review)
**Scope:** Cumulative ticket and minor-work tracker. A status of `Done` indicates reported/verified implementation, not proof of research effectiveness. `Proposed` does not mean a Codex worker has started.

## Foundation and generation

| Ticket | Description | Status | Codex |
|---|---|---|---|
| T1–T4 | Initial foundations, persistence, workspace | Done | — |
| T5 | Strategy Pool workspace | Done | — |
| T6 | Home controls and research modes | Done | — |
| T7 | Strategies and human-reviewed AI proposals | Done | — |
| T8 | Shared settings, curated models, API status | Done | — |
| T8.1 | Automatic local configuration | Done | — |
| T8.2 | ChatGPT connection and explicit billing modes | Done | — |
| T8.2.1 | Quiet current connection status | Done | — |
| T9 | Recents and sample exercise | Done | — |
| T10–T13 | Home artwork, sample catalog, project header | Done | — |
| T14 | Agentic Generate Strategy foundation | Done | — |
| T14.0 | Test baseline and stabilization | Done | — |
| T14.2 | Markdown conversion error recovery | Done | — |
| T15 | Generate Strategy and text representations | Done | — |
| T16 | Multi-agent Generate Strategy | Done | — |
| T16.1 | Durable agentic generation evidence | Done | — |

**T14.1** (Project → Investigation rename) was removed from the active tracker at the user's request. Its historical GitHub issue was not deleted.

## Research and outputs

| Ticket | Description | Status | Codex |
|---|---|---|---|
| T17 | Persistent research sessions | Engineering done | — |
| T17.1 | Consistent sections, tables, inline edits | Done | — |
| T17.2 | Workspace interaction and layering | Done | — |
| T17.3 | Research settings and reliability | Done | — |
| T17.4 | Session outcomes, disclosures, export | Done | — |
| T17.5 | Project export and stabilization | Done | — |
| T17.6 | Research outcomes and strategy attribution | Done | — |
| T17.7 | UI corrections and regression hardening | Done | — |
| T17.7.1 | Dialog, report, and UI refinements | Done | — |
| T17.8 | Agentic solution quality and final A17 verification | Open; deterministic acceptance evidence ready for human review; genuine real-provider solution quality remains unverified | ChatGPT review · [PR #4](https://github.com/bkramerext/sigma/pull/4) merged (engineering); [PR #41](https://github.com/bkramerext/sigma/pull/41) acceptance |
| T18 | Concurrent multi-strategy research and peer handoffs | Merged, engineering done | Blue · [PR #8](https://github.com/bkramerext/sigma/pull/8) |
| T19 | Isolated Python execution for Investigator → Skeptic | Merged, engineering done | Green · [PR #9](https://github.com/bkramerext/sigma/pull/9) |
| T20 | AI-authored research paper / LaTeX export option | Merged, engineering done | [PR #5](https://github.com/bkramerext/sigma/pull/5) |
| T21 | Final integration, demonstration and acceptance testing | Current-main UI/browser acceptance passed through T28; coordinator integration pass remains | Gray |
| T22 | Cloud deployment | Gates A/C merged; Gate B PR #49 refreshed against main `803e655` and R4R; deployment prep PR #52 open; T22.5 remains separate and unimplemented | Red |
| T171 | Pre-deployment host security and runtime readiness audit | R4R · [PR #175](https://github.com/bkramerext/sigma/pull/175) · Offline launch assessment BLOCKED · [ticket](../tickets/t171.md) · [assessment](T171_HOST_READINESS.md) | Red |
| T22.1 | Cloudflare runtime feasibility spike | Merged (PR #22) | Red |
| T100 | Local validation of production-compatible persistent storage and real-Chrome restart/restore acceptance | Implementing · [issue #100](https://github.com/bkramerext/sigma/issues/100) | Red |
| T89 | Ship-ready stock sample curation, increment 1 | R4R · [PR #120](https://github.com/bkramerext/sigma/pull/120) · [issue #89](https://github.com/bkramerext/sigma/issues/89) · [implementation](evaluations/t89-stock-sample-curation-increment1.md) · prior audit [PR #115](https://github.com/bkramerext/sigma/pull/115) | Gray |
| T117 | Release safety and test reliability follow-ups | Implemented; R4R · [issue #117](https://github.com/bkramerext/sigma/issues/117) · [ticket](../tickets/t117.md) | Gray |
| T91.2 | Packaged real-PDF and disaster-recovery acceptance | R4R · [PR #113](https://github.com/bkramerext/sigma/pull/113) · [ticket](../tickets/t91.2.md) · [evidence](evaluations/t91.2/README.md) | Gray |
| T99.1 | Pre-cloud sponsored inference API and spending acceptance | Implemented; R4R · [PR #110](https://github.com/bkramerext/sigma/pull/110) · [ticket](../tickets/t99.1.md) | Blue |
| T22.2 | Google authentication and invited access | Merged to main at `24ca812` ([PR #37](https://github.com/bkramerext/sigma/pull/37)) | Red |
| T88 | Google user sign-in with SIGMA-sponsored ChatGPT inference | Implemented; R4R · [PR #214](https://github.com/bkramerext/sigma/pull/214) · [ticket](../tickets/t88.md) · [handoff](../messages/t88_red_google_sponsored_auth.txt) | Red |
| T23 | Project difficulty setting | Done | [PR #6](https://github.com/bkramerext/sigma/pull/6) |
| T23.1 | Upper-right 2×2 model/Google sign-in and thinking/ChatGPT sign-in pills; cost signs | Original implementation merged in PR #12; local Google-pill acceptance follow-up in review | Blue |
| T24 | Outcome metrics and provenance *data* (no presentation table) | Merged, engineering done | Green · ChatGPT authored ticket · [PR #13](https://github.com/bkramerext/sigma/pull/13) |
| T25 | Outcome hierarchy and collapsible subsections | Implemented; open for review | Gray · ChatGPT authored ticket · [PR #19](https://github.com/bkramerext/sigma/pull/19) |
| T26 | SageMath agent-aware sandboxed execution, Python parity | Implemented and validated; review pending | Green · ChatGPT authored ticket · [PR #24](https://github.com/bkramerext/sigma/pull/24) |
| T27 | Research intelligence, cross-strategy learning and agent guidance | Merged, engineering done | Blue · [PR #18](https://github.com/bkramerext/sigma/pull/18) |
| T28 | Rich computational artifact inspection and cross-session evidence | Merged, engineering done | Green · ChatGPT authored ticket · [PR #36](https://github.com/bkramerext/sigma/pull/36) |
| T29 | Human intervention during active concurrent research | Implementation open for review | Blue · ChatGPT authored ticket · [PR #39](https://github.com/bkramerext/sigma/pull/39) |

| T30 | Create Samples entries from exported projects | Done; PR #40 and Gray follow-up PR #48 merged | Green core; Gray sample follow-up |
| T37 | Trustworthy research memory, evidence selection, and continuity | Engineering done; PR #45 merged, live-agent quality unverified | Blue · [ticket](tickets/t37.md) · [PR #45](https://github.com/bkramerext/sigma/pull/45) |
| T45 | **HIGH:** Long-form TeX paper generation under output/context limits | Implemented; PR #68 open for final review | [ticket](../tickets/t45.md) · [PR #68](https://github.com/bkramerext/sigma/pull/68) |
| T46 | Home and Project About dialog and product introduction | R4R · Green · [PR #73](https://github.com/bkramerext/sigma/pull/73) · [ticket](../tickets/t46.md) |
| T47 | First-class Markdown Conclusion in Research Session Outcome | Implemented; R4R | Gray · [ticket](tickets/t47.md) · [PR #72](https://github.com/bkramerext/sigma/pull/72) |
| T114 | Blind matched-budget comparison of cumulative research; bounded maintainability review | P0 preregistration / deterministic planner R4R; no cumulative blind run · [PR #216](https://github.com/bkramerext/sigma/pull/216) | Blue · [issue #114](https://github.com/bkramerext/sigma/issues/114) · [cumulative preregistration](evaluations/T114_CUMULATIVE_PREREGISTRATION.md) · [T146 single-case evidence](evaluations/increment_22/exports/trial_20261025/assessment.md) |

### T23.1 scope

Exactly four separate pills in the **upper-right**: top row **Model | Google sign-in**; bottom row **Thinking | ChatGPT sign-in**. Model and Thinking cycle actual supported selections, persist for future calls, and display relative model dollar-sign pricing. **Google sign-in is a clearly unavailable placeholder for T22 cloud work; ChatGPT sign-in reuses the existing implemented functional account control.** Preserve Difficulty where it is. No billing fallback. See [T23.1](tickets/t23.1.md).

### T24 scope

Provide persisted, structured outcome measurements for T25's collapsible **Metrics** subsection (do **not** build a table): participating agents, dispatched/completed/rejected/timed-out/cancelled model calls, input/output/cached/total tokens where supplied, wall-clock time and per-agent duration, research cycles, participating strategies, Python execution outcomes, artifact counts/sizes, operational errors, estimated dollar cost when grounded, verification status and open proof obligations. Do not double-count concurrent work or recovered/reused executions. Use `—` when data are unavailable rather than inventing zeros or usage estimates. Explicitly account for Green's HTTP 400 rejection, plan allowance uncertainty, and incomplete live guidance validation.

## Minor and unnumbered work

| Work | Status |
|---|---|
| Strategy Edit / Remove | Done |
| Command hierarchy and common button refinements | Done |
| Home artwork and header placement | Done |
| Project dialog terminology correction | Done |
| Samples terminology and source directory | Done |
| Markdown conversion tooltip | Done |
| Cancel generation and immediate retry | Done |
| Project / Strategies heading controls and collapses | Done |
| Project description edit actions | Done |
| Strategy preview and Home tab persistence | Done |
| Candidate-solution generation | Done |
| Session controls, elapsed time and reports | Done |
| T43 manual acceptance fixes | [PR #62](https://github.com/bkramerext/sigma/pull/62) R4R; deterministic real-Chrome acceptance passed; live Google/ChatGPT OAuth remains unverified |
| T43.1 third-pass operator acceptance fixes | [PR #63](https://github.com/bkramerext/sigma/pull/63) R4R; consolidated Google/ChatGPT pill polish and responsive Chrome checks passed; live operator OAuth round trip and third manual pass remain required |
| T43.2 / issue #66 multi-account sign-in acceptance | Deterministic integrated acceptance R4R in [PR #222](https://github.com/bkramerext/sigma/pull/222), head `3a42ae8413107b57604b0cc6cfe04a8bf18b5e2d`; T88 / [PR #214](https://github.com/bkramerext/sigma/pull/214) merged at `e821520`. Distinct live identities/hosted OAuth remain unverified; [ticket](../tickets/t43.2.md), [handoff](../messages/t43_2_gray_multi_account.txt) |
| T172 pre-deployment authentication and account-isolation gate | Assessment **BLOCKED for production launch**; fixture API/Chrome checks passed, hosted OAuth and two-identity acceptance remain unverified · [assessment](T172_AUTH_READINESS.md) |
| T129 | Release-image SHA correctness and reproducibility | Gray · R4R, offline implementation only · [PR #182](https://github.com/bkramerext/sigma/pull/182) · [handoff](../messages/t129_gray_release_sha.txt) | — |
| UI shutdown and orphan-process recovery | **Done (user confirmed)** |
| Network-bound failure toast and safe recovery | Implemented in tested paths ([PR #1](https://github.com/bkramerext/sigma/pull/1)); broader error coverage remains to validate |
| T215 | Request-toast 60-second expiry and downward exit | R4R · [PR #221 (T215)](https://github.com/bkramerext/sigma/pull/221) · [handoff](../messages/blue_t215_r4r.md) · automated fake-clock and Chrome checks passed · [issue #215](https://github.com/bkramerext/sigma/issues/215) |
| Live cross-strategy research validation | Open (T17.8) |
| Formal Lean proof verification | Future, not implemented |
| LaTeX paper export workflow | **Done** (T20; [PR #5](https://github.com/bkramerext/sigma/pull/5)) |
| Separate project-header LaTeX shortcut | **Reconciled; ready for review** ([PR #10](https://github.com/bkramerext/sigma/pull/10)); not yet merged |

## Reported gaps and follow-up ownership

| Gap / limitation | Reported by | Tracking |
|---|---|---|
| Provider timeouts, HTTP 400 rejections, plan-usage uncertainty | Blue and Green | T24 for metrics; T21 for integration/reliability |
| Token usage metadata absent | Blue and Green | T24; display unavailable rather than inferred |
| Real cross-strategy reasoning and handoff uptake not demonstrated | Blue | T27 implementation; T17.8 acceptance |
| Multi-session improvement of research strategies not demonstrated | Blue | T27 implementation; T17.8 acceptance |
| False transfer due to domain/assumption mismatch | Blue | T27 adversarial tests; T17.8 acceptance |
| User intervention during active multi-strategy session | Blue | Implemented and under review in T29 (PR #39); agent uptake remains self-reported |
| Revised Python-guidance quality not live validated | Green | T27 guidance; T28 follow-up; T17.8 acceptance |
| Cross-session computation synthesis not live validated | Green | T28; T17.8 acceptance |
| Model cannot inspect complete captured binary/plot artifacts | Green | T28 (Green; pending) |
| Python Docker sandbox assumes trusted host kernel/daemon/image | Green | Documented prototype security boundary |
| No independent mathematical proof checker | Both | Future Lean/formal verification |
| Real-provider paper quality and provider compatibility not established | T20 | T21 integration / acceptance |

Do not equate successful deterministic tests with demonstrated research effectiveness. Failed strategy *runs* are not discarded strategies. Research sessions retain attempts and evidence so narrow strategies can be revised, rerun, and branched.

## Codex allocation at snapshot

| Codex | Last ticket | Current work |
|---|---|---|
| Blue | T27 merged ([PR #18](https://github.com/bkramerext/sigma/pull/18)) | T29 implementation in [PR #39](https://github.com/bkramerext/sigma/pull/39); review pending |
| Green | T24 merged ([PR #13](https://github.com/bkramerext/sigma/pull/13)) | T26 [PR #24](https://github.com/bkramerext/sigma/pull/24) implemented and validated; awaiting review |

**Terminology:** Ticket and assignment are interchangeable. **Color:** Blue and Green identify Codex workers, not status. Activity is inferred from reported PR work; current Codex process status is not independently visible.

**Delivery target:** October 26, 2026. Outstanding integration, cloud work, T23.1 pills, T24 metrics and T17.8 acceptance should be tracked separately; completion of software work does not close the research-quality gate.

## Outcome hierarchy (T25)

**SESSIONS → OUTCOME → direct general details + collapsible Status, Strategy Assessments, Metrics, Provenance** (additional Evidence & Obligations section if warranted). T24 supplies metrics/provenance evidence; T25 implements the presentation, without tables or a two-column layout. Markdown icons/actions are attached to meaningful markdown-bearing sections, not decorative status fields. [Ticket T25](tickets/t25.md) is proposed and authored by **ChatGPT**.

## Planned Codex workers

| Codex | Planned responsibility | Status |
|---|---|---|
| Red | Cloud support (T22) | Later; not started |
| Gray | UI improvements, live prompts, and tickets; T25 proposed | Later; not started |

Ticket naming convention: `T1`, `T8.2`, `T17.7.1`; canonical ticket documents live at `tickets/t1.md`, `tickets/t8.2.md`, etc. Historical ticket documents are migrated into `tickets/` in this PR; supplementary historical design/security documents use `tN-design.md` or `tN-security.md`. T14.1 is retained as historical record but removed from the active tracker.

## PR and authorship conventions

Include a clickable GitHub PR link **only when a specific PR exists**; each ticket's own PR belongs in its tracker row once opened. The current ticket-file migration is [PR #11](https://github.com/bkramerext/sigma/pull/11), authored by **ChatGPT**. Credit ChatGPT for ticket drafting, integration planning, and review where performed, without implying that ChatGPT or a Codex worker implemented changes it did not.
