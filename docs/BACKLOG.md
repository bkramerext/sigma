# SIGMA backlog

Open ideas and possible follow-up work, not implementation commitments. Completed work and historical decisions belong in [DECISIONS](DECISIONS.md), [STATUS](STATUS.md), and the ticket tracker.

**Times:** Approximate local times reconstructed from discussions. Preserve timestamps for retained ideas.

## Core research model

- **2026-10-20 9:00 AM** — A strategy is an evolving investigation, not a solution; it retains evidence and revisions.
- **2026-10-20 9:30 AM** — Strategy pool: independent roots (generation 0) and parent-linked forks with separate histories.
- **2026-10-20 9:30 AM** — Forks have one parent initially; consider synthesis later.
- **2026-10-20 9:30 AM** — Generation indicates ancestry, not merit.
- **2026-10-20 10:00 AM** — Bound fork growth by difference, overlap, depth, active branches, and cost.

## Rubrics, adversarial evaluation, and scheduling

- **2026-10-20 9:30 AM** — Editable rubrics assess a strategy's promise, not its probability of solving RH.
- **2026-10-20 9:30 AM** — Distinguish established knowledge and significance from novelty.
- **2026-10-20 9:30 AM** — Adversarially test claims; passing finite tests is not proof.
- **2026-10-20 10:00 AM** — Separate research agents, independent evaluators, and deterministic scheduling.
- **2026-10-20 10:00 AM** — Bound evaluation work; retain evidence, uncertainty, and rubric versions.
- **2026-10-20 10:00 AM** — SIGMA autonomously prioritizes and schedules strategies by promise, uncertainty, information value, cost, and hard limits, while preserving human overrides and auditable decisions.

## Human control and interfaces

- **2026-10-20 10:00 AM** — Human controls: edit rubric/limits, prioritize, pause/resume, request investigation.
- **2026-10-20 10:00 AM** — Keep human priorities distinct from evaluator judgments; audit changes.
- **2026-10-20 9:00 AM** — Web, CLI, and scenarios share one typed application interface.
- **2026-10-20 10:30 AM** — Show strategy lineage, evidence, priorities, and uncertainty clearly.

## Agent runtime and public presentation

- **2026-10-20 10:00 AM** — Agent runtime needs model, role, retry, timeout, concurrency, and cost controls.
- **2026-10-20 10:00 AM** — Public docs should reflect actual architecture, not promotional claims.
- **2026-10-20 10:00 AM** — SIGMA orchestrates research, not a general software factory.

## Configuration, spending, and progress notifications

Some base settings and limits now exist. The entries below concern additional strategy-level controls, spending presentation, and notifications. **Notifications remain deferred.**

- **2026-10-20 1:00 PM** — Project settings: model, budget, agent limits, reporting, rubric, notifications.
- **2026-10-20 1:00 PM** — Strategy settings: priority, scheduling state, spending ceiling; inherit project defaults.
- **2026-10-20 1:15 PM** — Show actual spend against limit as subtle strategy subtext.
- **2026-10-20 1:15 PM** — Periodic progress reports, distinct from execution deadlines.
- **2026-10-20 1:30 PM** — Notify on candidate solutions; distinguish claims from independent verification.
- **2026-10-20 1:30 PM** — Defer notification channels and detailed overrides.

## Research communication artifacts

- **2026-10-20 2:00 PM** — **Show Me:** Agent-produced, illustrated narrative of actual research findings, inspired by accessible mathematical journalism. Scope (one strategy versus cross-session project narrative) remains a future design decision.
- **2026-10-20 2:00 PM** — Explain accomplishments and failures equally well; never invent evidence, discoveries, or certainty.
- **2026-10-20 2:00 PM** — Original illustrations clarify ideas; claims trace to research artifacts. Show Me communicates, not verifies.
- **2026-10-24** — **Riemann Hypothesis example:** An accessible illustrated article could introduce a spectral strategy, explain what operator or condition SIGMA investigated, show an annotated eigenvalue plot generated from reproducible numerical results, and visualize a counterexample or the precise point where an attempted argument fails. Distinguish data-derived plots from conceptual artwork; never invent eigenvalues, proofs, or discoveries.
- **2026-10-20 2:00 PM** — Place Show Me under a strategy's Report artifact actions, alongside Audit.

## Network failure UX and state consistency (deferred)

- **2026-10-21** — Treat every network-bound operation as fallible (provider inference, conversions, API requests, saves, status/discovery). On failure, show an accessible, non-disruptive toast with an actionable, accurate explanation; never silently fail or falsely indicate success. Pair the toast with the appropriate UI state transition: retain the last valid persisted content and prior view, preserve unsaved edits where applicable, clear loading states, and do **not** switch into Markdown/Rendered when Markdown generation fails. On successful conversion, transition only after durable save is confirmed. Test HTTP failures, timeouts, disconnects, cancellation, and stale responses without unintended view changes or duplicate requests.


## Context management and retrieval

- **2026-10-22** — Build a deterministic Context Manager to seed each Investigator/Skeptic call, including resumed sessions, from durable strategy, session, artifact, objection, and Coordinator-decision records. Assemble role-specific, token-budgeted context with provenance; never silently omit unresolved critical objections. Resume must not depend on an earlier model conversation or process.
- **2026-10-22** — **Potential future vector retrieval:** Embedding-based semantic search across past strategies, sessions, arguments, experiments, and objections could discover related research despite differing terminology and reduce repeated dead ends. Treat similarity as a discovery signal, never mathematical equivalence or proof; preserve structured retrieval of critical obligations as mandatory. Start with explicit relationships and possibly full-text search, not a vector database. Design the retrieval interface to accommodate an optional local SQLite vector index later, when research volume warrants its cost and complexity. Preserve export/deletion consistency and retrieval provenance.
