# SIGMA architectural decisions
Date: 2026-10-20

1. **Project package:** Each project is a `.sigma/` directory with declarative `config.json`, generated SQLite `state.db`, `artifacts/`, and `scenarios/`. The source-controlled `projects/rh.sigma/` starter has no database until first open. Ignore generated state, not the whole starter directory.
2. **Common application interface:** CLI, web UI, and executable scenario runner are peer adapters calling the same typed Python commands/queries.
3. **UI stack:** React + TypeScript + Vite frontend, FastAPI backend; no Django or HTMX in the initial implementation. Local self-hosted browser interaction is required from the first slice.
4. **Research vocabulary:** A strategy is an evolving investigation seeded by an idea, not a single result. Strategies form a genealogy: generation-0 roots and parent-linked forks. Iterations are bounded runs; events are the audit trail.
5. **Rubrics:** Human-editable natural-language criteria evaluate whether strategies have promising paths. Some criteria direct bounded adversarial testing. Evidence, uncertainty, novelty, and strategic promise are distinct.
6. **Governance:** Independent evaluators assess evidence. A deterministic scheduler enforces hard constraints and allocates effort. Human controls change priorities, constraints, and pause state without rewriting assessments.
7. **Verification:** Source-controlled scenarios are primary acceptance tests; they invoke application services, not CLI subprocesses. API and UI smoke checks accompany every browser-visible slice.
8. **Engineering:** Python, uv, SQLite, argparse, FastAPI, React, TypeScript, Vite, Ruff, Pyright. Build one small specification at a time.
9. **Scope:** SPEC-001 includes the local browser, CLI, and scenarios together. Research and agent features remain deferred.
