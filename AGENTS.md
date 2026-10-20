# SIGMA coding guidance

Read `docs/PROJECT.md`, `docs/DECISIONS.md`, `docs/STATUS.md`, `docs/BRAINSTORM.md`, and the active specification before implementing.

## Working agreement
1. Implement only the active approved spec: currently `specs/project-lifecycle.md`.
2. Build the smallest working slice; do not turn brainstorming into features.
3. Prefer source-controlled, human-readable executable scenarios that exercise the shared application interface directly. Use focused Python unit tests only where they add value. Keep ordinary verification offline.
4. Keep the CLI, future web UI, and scenario runner as peer adapters over one typed application interface. Never route the scenario runner through CLI subprocesses.
5. If requirements conflict, amend the specification explicitly rather than silently inventing behavior.
6. Run the scenarios, CLI smoke checks, lint, and type checks. Record **actual** commands and results in STATUS. Commit and push coherent tested increments.

Use Python, uv, argparse, SQLite, Ruff and Pyright. Models belong under `models/`; keep dependencies and abstractions minimal. No secrets, force pushes, speculative features, or API charges. The repository is public: avoid personal recruiting context or private project history in public-facing prose.
