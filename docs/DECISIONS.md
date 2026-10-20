# SIGMA architectural decisions
Date: 2026-10-20

1. **Project package:** Each project is a `.sigma/` directory with `config.json`, SQLite `state.db`, `artifacts/`, and `scenarios/`. Generated packages may be ignored with `*.sigma/`.
2. **Common application interface:** CLI, web UI, and executable scenario runner are peer adapters calling the same typed commands/queries.
3. **Research vocabulary:** A strategy is an evolving investigation seeded by an idea, not a single result. Strategies form a genealogy: generation-0 roots and parent-linked forks. Iterations are bounded runs; events are the audit trail.
4. **Rubrics:** Human-editable natural-language criteria evaluate whether strategies have promising paths. Some criteria direct bounded adversarial testing. Evidence, uncertainty, novelty, and strategic promise are distinct; no false calibrated probabilities.
5. **Governance:** Independent evaluators assess evidence. A deterministic scheduler enforces hard constraints and allocates effort. Human controls change priorities, constraints, and pause state without rewriting assessments. Version and audit consequential changes.
6. **Verification:** Human-readable source-controlled scenarios are the primary acceptance mechanism; they invoke the application interface, not CLI subprocesses. Focused unit tests remain optional.
7. **Engineering:** Python, uv, SQLite, argparse, Ruff, Pyright; FastAPI/HTMX/SSE and agent runtime later. Models under `models/`. Build one small specification at a time.
8. **Collaboration:** GitHub docs, specifications, code, and commits are the shared handoff between ChatGPT and Codex. Public repository; no secrets or recruiting narrative in project documentation.
9. **Scope:** SPEC-001 is project lifecycle only. Strategy generation, scoring, scheduling, UI, and advanced research features remain deferred.
