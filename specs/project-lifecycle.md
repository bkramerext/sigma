# SPEC-001: Browser-first project lifecycle

Status: Approved for implementation

## First user experience
Run a local React/TypeScript/Vite UI with a FastAPI backend. Open the source-controlled seed directory `projects/rh.sigma/` and inspect the RH project's title, problem, identity, and event history. Deliver CLI and executable scenarios in tandem.

## Coding exercise: project representation
The project is a directory ending in `.sigma`. Its initial source-controlled contents are only `.gitkeep`. **Codex must design its data model, serialization, directory layout, persistence and safe initialization workflow.** No `config.json`, `state.db`, or specific storage layout is mandated. Explain the choice and tradeoffs. Ensure the RH seed can be initialized reproducibly, then reopened without losing its identity or history. Source-control stable inputs as appropriate, but exclude generated state and secrets.

## Application interface
Provide typed shared Python commands/queries for creating/initializing, opening, inspecting and closing a project, and listing its events. CLI, FastAPI and scenario runner are peer adapters; never call each other as subprocesses. Preserve identity and history on reopen; validate incompatible or corrupt projects; avoid partial initialization and accidental overwrites.

## UI, CLI, and tests
Browser: project path selection, Open action, project metadata/history view, clear error display, and close/switch action. Localhost only; no authentication required in this slice.
CLI: argparse commands to initialize/open/inspect projects and list events, with documented machine-readable output.
Scenarios: readable source-controlled executable examples calling shared services directly. Verify seed initialization, persistence, repeat reads, invalid inputs, safe failure and event ordering. Use focused Python/API tests where appropriate. Run frontend build/typecheck, scenarios, API/CLI smoke checks, Ruff and Pyright.

## Scope
Keep dependencies and abstractions minimal. No agents, scheduler, rubrics, advanced visualization, paid APIs or cloud features. Record actual verification commands and results in `docs/STATUS.md`, then commit and push.
