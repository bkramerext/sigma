# SIGMA brainstorm and roadmap

Dated ideas for future SIGMA work, not implementation commitments.

**Times:** Approximate local times reconstructed from discussions. Add new dated entries; preserve earlier ideas.

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
- **2026-10-20 10:00 AM** — Schedule by promise, uncertainty, information value, cost, and hard limits.

## Human control and interfaces

- **2026-10-20 10:00 AM** — Human controls: edit rubric/limits, prioritize, pause/resume, request investigation.
- **2026-10-20 10:00 AM** — Keep human priorities distinct from evaluator judgments; audit changes.
- **2026-10-20 9:00 AM** — Web, CLI, and scenarios share one typed application interface.
- **2026-10-20 10:30 AM** — Show strategy lineage, evidence, priorities, and uncertainty clearly.

## Projects and persistence

- **2026-10-20 9:00 AM** — Projects live in portable `.sigma/` directories.
- **2026-10-20 9:00 AM** — Potential layout: config, SQLite state, artifacts, scenarios; not mandated.
- **2026-10-20 9:00 AM** — Keep credentials outside project data.

## Verification and implementation approach

- **2026-10-20 9:00 AM** — Prefer readable executable scenarios over extensive brittle tests.
- **2026-10-20 9:00 AM** — Use deterministic fake agents, clocks, and budgets for offline scenarios.
- **2026-10-20 9:30 AM** — Test false confidence, contradictions, trivialities, budget exhaustion, and invalid forks.
- **2026-10-20 9:30 AM** — Specs define contracts and acceptance; implementation follows bounded slices.
- **2026-10-20 10:00 AM** — Keep scenario runner minimal; defer elaborate orchestration.

## Agent runtime and public presentation

- **2026-10-20 10:00 AM** — Agent runtime needs model, role, retry, timeout, concurrency, and cost controls.
- **2026-10-20 10:00 AM** — Public docs should reflect actual architecture, not promotional claims.
- **2026-10-20 10:00 AM** — SIGMA orchestrates research, not a general software factory.

## Configuration, spending, and progress notifications

Deferred until agent execution work.

- **2026-10-20 1:00 PM** — Project settings: model, budget, agent limits, reporting, rubric, notifications.
- **2026-10-20 1:00 PM** — Strategy settings: priority, scheduling state, spending ceiling; inherit project defaults.
- **2026-10-20 1:15 PM** — Show actual spend against limit as subtle strategy subtext.
- **2026-10-20 1:15 PM** — Periodic progress reports, distinct from execution deadlines.
- **2026-10-20 1:30 PM** — Notify on candidate solutions; distinguish claims from independent verification.
- **2026-10-20 1:30 PM** — Defer notification channels and detailed overrides.

## Research communication artifacts

- **2026-10-20 2:00 PM** — **Show Me:** Agent-produced, illustrated narrative of a strategy's actual findings, inspired by accessible mathematical journalism.
- **2026-10-20 2:00 PM** — Explain accomplishments and failures equally well; never invent evidence, discoveries, or certainty.
- **2026-10-20 2:00 PM** — Original illustrations clarify ideas; claims trace to research artifacts. Show Me communicates, not verifies.
- **2026-10-20 2:00 PM** — Place Show Me under a strategy's Report artifact actions, alongside Audit.

## Documentation reconciliation

Implemented storage uses versioned JSON; SQLite remains a future option. See [DECISIONS](DECISIONS.md).
