# SIGMA architectural decisions
Date: 2026-10-20

1. **Project:** A `.sigma` directory. `projects/rh.sigma/` is a source-controlled seed. Codex designs internal files, data model, serialization, and initialization in SPEC-001.
2. **Common application interface:** CLI, web API, and executable scenarios are peers over typed Python services.
3. **UI stack:** React + TypeScript + Vite with FastAPI. Browser-visible interaction is required in the first increment.
4. **Research:** Strategies are evolving investigations with parent-linked forks and generations; evaluations assess their promise using qualitative rubrics and adversarial tests.
5. **Governance:** Independent evaluation, deterministic constrained scheduling, auditable human controls and priorities.
6. **Verification:** Human-readable executable scenarios test common application services, with UI and CLI developed in tandem.
7. **Scope:** SPEC-001 covers project lifecycle and local browser only. Agent execution and advanced features are deferred.
