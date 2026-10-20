# SIGMA coding guidance

Read `docs/PROJECT.md`, `docs/DECISIONS.md`, `docs/STATUS.md`, `docs/BRAINSTORM.md`, and the active `specs/project-lifecycle.md`.

Implement SPEC-001 as a browser-first vertical slice: React/TypeScript/Vite UI, FastAPI API, argparse CLI, and source-controlled executable scenarios, all calling common typed Python application services.

**Project data model, serialization, internal directory structure and initialization are your coding exercise.** The source-controlled `projects/rh.sigma/` contains only a placeholder. Choose a simple approach, explain tradeoffs, protect existing research from overwrite, and make the seed openable from the browser.

Run scenarios, frontend build/typecheck, API/CLI checks, Ruff and Pyright. Record actual results in STATUS; commit and push. No speculative agent features, paid API calls, secrets, force pushes, or private recruiting context.
