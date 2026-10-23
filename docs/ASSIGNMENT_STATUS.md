# SIGMA Assignment Status

**Snapshot:** October 23, 2026 (Days 0–3)  
**Scope:** Cumulative assignment and minor-work tracker. A status of `Done` indicates reported/verified implementation, not proof of research effectiveness. `Proposed` does not mean a Codex worker has started.

## Foundation and generation

| Assignment | Description | Status | Codex |
|---|---|---|---|
| A1–A4 | Initial foundations, persistence, workspace | Done | — |
| A5 | Strategy Pool workspace | Done | — |
| A6 | Home controls and research modes | Done | — |
| A7 | Strategies and human-reviewed AI proposals | Done | — |
| A8 | Shared settings, curated models, API status | Done | — |
| A8.1 | Automatic local configuration | Done | — |
| A8.2 | ChatGPT connection and explicit billing modes | Done | — |
| A8.2.1 | Quiet current connection status | Done | — |
| A9 | Recents and sample exercise | Done | — |
| A10–A13 | Home artwork, sample catalog, project header | Done | — |
| A14 | Agentic Generate Strategy foundation | Done | — |
| A14.0 | Test baseline and stabilization | Done | — |
| A14.2 | Markdown conversion error recovery | Done | — |
| A15 | Generate Strategy and text representations | Done | — |
| A16 | Multi-agent Generate Strategy | Done | — |
| A16.1 | Durable agentic generation evidence | Done | — |

**A14.1** (Project → Investigation rename) was removed from the active tracker at the user's request. Its historical GitHub issue was not deleted.

## Research and outputs

| Assignment | Description | Status | Codex |
|---|---|---|---|
| A17 | Persistent research sessions | Engineering done | — |
| A17.1 | Consistent sections, tables, inline edits | Done | — |
| A17.2 | Workspace interaction and layering | Done | — |
| A17.3 | Research settings and reliability | Done | — |
| A17.4 | Session outcomes, disclosures, export | Done | — |
| A17.5 | Project export and stabilization | Done | — |
| A17.6 | Research outcomes and strategy attribution | Done | — |
| A17.7 | UI corrections and regression hardening | Done | — |
| A17.7.1 | Dialog, report, and UI refinements | Done | — |
| A17.8 | Live research-quality acceptance | Open; not accepted | — |
| A18 | Concurrent multi-strategy research and peer handoffs | Merged, engineering done | Blue |
| A19 | Isolated Python execution for Investigator → Skeptic | Merged, engineering done | Green |
| A20 | AI-authored research paper / LaTeX export option | Merged, engineering done | — |
| A21 | Final integration, demonstration and acceptance testing | Planned; standalone work not started | Unassigned |
| A22 | Cloud deployment | Planned / unverified | Unassigned |
| A23 | Project difficulty setting | Done | — |
| A23.1 | Interactive model and thinking controls | Review revisions implemented; PR open | Blue |
| A24 | Consolidated outcome metrics, operational and research quality | Ready to assign; not verified started | Green proposed |

### A23.1 scope

Place four distinct controls in an upper-right 2×2 header group: Model over Thinking at left; Google sign-in over the existing functional ChatGPT sign-in control at right. Preserve Difficulty in place. Cycle through supported model/effort options, visibly disclose a required effort adjustment before changing models, persist only project model settings for future requests, and never change billing mode. Google is a noninteractive not-implemented placeholder for T22. Reuse the existing ChatGPT connection UI and state/actions.

### A24 scope

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
| Live cross-strategy research validation | Open (A17.8) |
| Formal Lean proof verification | Future, not implemented |
| LaTeX button / Academic paper using LaTeX | **Done (A20; supporting A17.7.1)** |

## Reported gaps and follow-up ownership

| Gap / limitation | Reported by | Tracking |
|---|---|---|
| Provider timeouts, HTTP 400 rejections, plan-usage uncertainty | Blue and Green | A24 for metrics; A21 for integration/reliability |
| Token usage metadata absent | Blue and Green | A24; display unavailable rather than inferred |
| Real cross-strategy reasoning and handoff uptake not demonstrated | Blue | A17.8 |
| Multi-session improvement of research strategies not demonstrated | Blue | A17.8 |
| False transfer due to domain/assumption mismatch | Blue | A17.8 adversarial evaluation |
| User intervention during active multi-strategy session not implemented | Blue | New deferred assignment needed; assign target branch and record exact intervention provenance |
| Revised Python-guidance quality not live validated | Green | A17.8 |
| Cross-session computation synthesis not live validated | Green | A17.8 |
| Model cannot inspect complete captured binary/plot artifacts | Green | New follow-up needed for richer artifact inspection |
| Python Docker sandbox assumes trusted host kernel/daemon/image | Green | Documented prototype security boundary |
| No independent mathematical proof checker | Both | Future Lean/formal verification |
| Real-provider paper quality and provider compatibility not established | A20 | A21 integration / acceptance |

Do not equate successful deterministic tests with demonstrated research effectiveness. Failed strategy *runs* are not discarded strategies. Research sessions retain attempts and evidence so narrow strategies can be revised, rerun, and branched.

## Codex allocation at snapshot

| Codex | Last assignment | Current work |
|---|---|---|
| Blue | A18 merged | No active task verified |
| Green | A19 merged | A24 proposed next; not confirmed started |

**Terminology:** Ticket and assignment are interchangeable. **Color:** Blue and Green identify Codex workers, not status. There is no confirmed currently-running worker from the repository evidence in this snapshot.

**Delivery target:** October 26, 2026. Outstanding integration, cloud work, A23+ pills, A24 metrics and A17.8 acceptance should be tracked separately; completion of software work does not close the research-quality gate.
