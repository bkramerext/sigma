# SIGMA Ticket Tracking

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
| T17.8 | Live research-quality acceptance | Open; not accepted | ChatGPT review · [PR #4](https://github.com/bkramerext/sigma/pull/4) merged (engineering) |
| T18 | Concurrent multi-strategy research and peer handoffs | Merged, engineering done | Blue · [PR #8](https://github.com/bkramerext/sigma/pull/8) |
| T19 | Isolated Python execution for Investigator → Skeptic | Merged, engineering done | Green · [PR #9](https://github.com/bkramerext/sigma/pull/9) |
| T20 | AI-authored research paper / LaTeX export option | Merged, engineering done | [PR #5](https://github.com/bkramerext/sigma/pull/5) |
| T21 | Final integration, demonstration and acceptance testing | Planned; standalone work not started | Unassigned |
| T22 | Cloud deployment | T22.1 local feasibility checked; remote/security gates open | Red · ChatGPT authored ticket |
| T22.1 | Cloudflare runtime, scientific isolation and durable storage spike | Local checks pass; remote deployment and model access unverified | Red · [requirements PR #21](https://github.com/bkramerext/sigma/pull/21) |
| T23 | Project difficulty setting | Done | [PR #6](https://github.com/bkramerext/sigma/pull/6) |
| T23.1 | Upper-right 2×2 model/Google sign-in and thinking/ChatGPT sign-in pills; cost signs | [PR #12](https://github.com/bkramerext/sigma/pull/12) reviewed; open | Blue |
| T24 | Outcome metrics and provenance *data* (no presentation table) | Merged, engineering done | Green · ChatGPT authored ticket · [PR #13](https://github.com/bkramerext/sigma/pull/13) |
| T25 | Outcome hierarchy and collapsible subsections | Implemented; open for review | Gray · ChatGPT authored ticket · [PR #19](https://github.com/bkramerext/sigma/pull/19) |
| T26 | SageMath agent-aware sandboxed execution, Python parity | Assigned; implementation pending | Green · ChatGPT authored ticket · PR #15 |
| T27 | Research intelligence, cross-strategy learning and agent guidance | Assigned; immediate | Blue · ChatGPT authored ticket |
| T28 | Rich computational artifact inspection and cross-session evidence | Pending; Green unavailable | Green · ChatGPT authored ticket |
| T29 | Human intervention during active concurrent research | Pending after T27 | Blue · ChatGPT authored ticket |

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
| UI shutdown and orphan-process recovery | **Done (user confirmed)** |
| Network-bound failure toast and safe recovery | Implemented in tested paths ([PR #1](https://github.com/bkramerext/sigma/pull/1)); broader error coverage remains to validate |
| Live cross-strategy research validation | Open (T17.8) |
| Formal Lean proof verification | Future, not implemented |
| LaTeX paper export workflow | **Done** (T20; [PR #5](https://github.com/bkramerext/sigma/pull/5)) |
| Separate project-header LaTeX shortcut | **Open PR** ([PR #10](https://github.com/bkramerext/sigma/pull/10)); not yet merged |

## Reported gaps and follow-up ownership

| Gap / limitation | Reported by | Tracking |
|---|---|---|
| Provider timeouts, HTTP 400 rejections, plan-usage uncertainty | Blue and Green | T24 for metrics; T21 for integration/reliability |
| Token usage metadata absent | Blue and Green | T24; display unavailable rather than inferred |
| Real cross-strategy reasoning and handoff uptake not demonstrated | Blue | T27 implementation; T17.8 acceptance |
| Multi-session improvement of research strategies not demonstrated | Blue | T27 implementation; T17.8 acceptance |
| False transfer due to domain/assumption mismatch | Blue | T27 adversarial tests; T17.8 acceptance |
| User intervention during active multi-strategy session not implemented | Blue | T29 (Blue; pending) |
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
| Blue | T18 merged ([PR #8](https://github.com/bkramerext/sigma/pull/8)) | T23.1 implementation in [PR #12](https://github.com/bkramerext/sigma/pull/12); reviewed, awaiting integration |
| Green | T19 merged ([PR #9](https://github.com/bkramerext/sigma/pull/9)) | T24 [PR #13](https://github.com/bkramerext/sigma/pull/13) reconciled with migrated main; checks passed; awaiting final merge approval |

**Terminology:** Ticket and assignment are interchangeable. **Color:** Blue and Green identify Codex workers, not status. Activity is inferred from reported PR work; current Codex process status is not independently visible.

**Delivery target:** October 26, 2026. Outstanding integration, cloud work, T23.1 pills, T24 metrics and T17.8 acceptance should be tracked separately; completion of software work does not close the research-quality gate.

## Outcome hierarchy (T25)

**SESSIONS → OUTCOME → direct general details + collapsible Status, Strategy Assessments, Metrics, Provenance** (additional Evidence & Obligations section if warranted). T24 supplies metrics/provenance evidence; T25 implements the presentation, without tables or a two-column layout. Markdown icons/actions are attached to meaningful markdown-bearing sections, not decorative status fields. [Ticket T25](tickets/t25.md) is proposed and authored by **ChatGPT**.

## Planned Codex workers

| Codex | Planned responsibility | Status |
|---|---|---|
| Red | Cloud support (T22) | T22.1 spike in progress; local evidence recorded, remote gates open |
| Gray | UI improvements, live prompts, and tickets; T25 proposed | Later; not started |

Ticket naming convention: `T1`, `T8.2`, `T17.7.1`; canonical ticket documents live at `tickets/t1.md`, `tickets/t8.2.md`, etc. Historical ticket documents are migrated into `tickets/` in this PR; supplementary historical design/security documents use `tN-design.md` or `tN-security.md`. T14.1 is retained as historical record but removed from the active tracker.

## PR and authorship conventions

Include a clickable GitHub PR link **only when a specific PR exists**; each ticket's own PR belongs in its tracker row once opened. The current ticket-file migration is [PR #11](https://github.com/bkramerext/sigma/pull/11), authored by **ChatGPT**. Credit ChatGPT for ticket drafting, integration planning, and review where performed, without implying that ChatGPT or a Codex worker implemented changes it did not.
