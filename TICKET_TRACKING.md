# SIGMA Ticket Tracking

**Snapshot:** October 23, 2026 (Days 0–3)  
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
| T17.8 | Live research-quality acceptance | Open; not accepted | — |
| T18 | Concurrent multi-strategy research and peer handoffs | Merged, engineering done | Blue |
| T19 | Isolated Python execution for Investigator → Skeptic | Merged, engineering done | Green |
| T20 | AI-authored research paper / LaTeX export option | Merged, engineering done | — |
| T21 | Final integration, demonstration and acceptance testing | Planned; standalone work not started | Unassigned |
| T22 | Cloud deployment | Planned / unverified | Unassigned |
| T23 | Project difficulty setting | Done | — |
| T23.1 | Clickable model and thinking-level pills under Difficulty; cost dollar signs; sign-in placeholder | Proposed | Unassigned |
| T24 | Consolidated outcome metrics, operational and research quality | Ready to assign; not verified started | Green proposed |

### T23.1 scope

Clicking model and thinking pills cycles through the **actually supported** selections. Show relative pricing as `$`, `$$`, etc. Reconcile incompatible reasoning levels, persist selection, and apply changes only to future requests. Preserve the selected billing mode; do not initiate paid-API fallback. The authentication pill remains a placeholder. Preserve SIGMA's existing UI styling.

### T24 scope

Display one compact outcome table combining existing metrics with distinct operational and research-quality measurements: participating agents, dispatched/completed/rejected/timed-out/cancelled model calls, input/output/cached/total tokens where supplied, wall-clock time and per-agent duration, research cycles, participating strategies, Python execution outcomes, artifact counts/sizes, operational errors, estimated dollar cost when grounded, verification status and open proof obligations. Do not double-count concurrent work or recovered/reused executions. Use `—` when data are unavailable rather than inventing zeros or usage estimates. Explicitly account for Green's HTTP 400 rejection, plan allowance uncertainty, and incomplete live guidance validation.

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
| Network-bound failure toast and safe recovery | Implemented in tested paths; broader error coverage remains to validate |
| Live cross-strategy research validation | Open (T17.8) |
| Formal Lean proof verification | Future, not implemented |
| LaTeX button / Academic paper using LaTeX | **Done (T20; supporting T17.7.1)** |

## Reported gaps and follow-up ownership

| Gap / limitation | Reported by | Tracking |
|---|---|---|
| Provider timeouts, HTTP 400 rejections, plan-usage uncertainty | Blue and Green | T24 for metrics; T21 for integration/reliability |
| Token usage metadata absent | Blue and Green | T24; display unavailable rather than inferred |
| Real cross-strategy reasoning and handoff uptake not demonstrated | Blue | T17.8 |
| Multi-session improvement of research strategies not demonstrated | Blue | T17.8 |
| False transfer due to domain/assumption mismatch | Blue | T17.8 adversarial evaluation |
| User intervention during active multi-strategy session not implemented | Blue | New deferred ticket needed; assign target branch and record exact intervention provenance |
| Revised Python-guidance quality not live validated | Green | T17.8 |
| Cross-session computation synthesis not live validated | Green | T17.8 |
| Model cannot inspect complete captured binary/plot artifacts | Green | New follow-up needed for richer artifact inspection |
| Python Docker sandbox assumes trusted host kernel/daemon/image | Green | Documented prototype security boundary |
| No independent mathematical proof checker | Both | Future Lean/formal verification |
| Real-provider paper quality and provider compatibility not established | T20 | T21 integration / acceptance |

Do not equate successful deterministic tests with demonstrated research effectiveness. Failed strategy *runs* are not discarded strategies. Research sessions retain attempts and evidence so narrow strategies can be revised, rerun, and branched.

## Codex allocation at snapshot

| Codex | Last ticket | Current work |
|---|---|---|
| Blue | T18 merged | No active task verified |
| Green | T19 merged | T24 proposed next; not confirmed started |

**Terminology:** Ticket and ticket are interchangeable. **Color:** Blue and Green identify Codex workers, not status. There is no confirmed currently-running worker from the repository evidence in this snapshot.

**Delivery target:** October 26, 2026. Outstanding integration, cloud work, T23.1 pills, T24 metrics and T17.8 acceptance should be tracked separately; completion of software work does not close the research-quality gate.

## Planned Codex workers

| Codex | Planned responsibility | Status |
|---|---|---|
| Red | Cloud support (T22) | Later; not started |
| Gray | UI improvements, live prompts, and tickets | Later; not started |

Ticket naming convention: `T1`, `T8.2`, `T17.7.1`; canonical ticket documents live at `tickets/t1.md`, `tickets/t8.2.md`, etc. Historical references remain valid until document migration is complete.
