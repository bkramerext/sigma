# SIGMA coding guidance

Read `docs/PROJECT.md`, `docs/DECISIONS.md`, `docs/STATUS.md`, `docs/BRAINSTORM.md`, and the active specification before implementing.

## Working agreement
1. Implement only the active approved spec: `specs/project-lifecycle.md`.
2. Deliver a **browser-visible vertical slice** in tandem with the CLI and executable scenarios. The user must be able to self-host the page and open `projects/rh.sigma` as the first demonstration.
3. The React/TypeScript/Vite frontend, FastAPI backend, argparse CLI, and source-controlled scenario runner are peer adapters to the same Python application services. Do not route scenarios through CLI subprocesses.
4. Prefer readable scenarios with offline deterministic assertions; add focused Python tests for mechanics not naturally expressed by scenarios.
5. Do not expand scope to agents, rubrics, scheduling, or advanced visualizations.
6. If a contract is ambiguous, propose an explicit spec amendment rather than inventing architecture.
7. Run scenarios, CLI and API checks, frontend build/typecheck, lint, and type checks. Record **actual** commands/results in STATUS, then commit and push.

Use Python, uv, SQLite, FastAPI, argparse, React, TypeScript, Vite, Ruff and Pyright. Keep dependencies minimal. No secrets, force pushes, speculative features, or API charges. The repository is public; avoid private recruiting context and borrowed marketing vocabulary.
