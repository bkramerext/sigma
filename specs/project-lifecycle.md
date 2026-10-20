# SPEC-001: Local project browser and lifecycle

Status: Approved for implementation
Date: 2026-10-20

## Goal and first user experience
Deliver **web UI, CLI, and executable scenarios together**, all using the same Python application interface. The first user action is to self-host a local webpage and **open the source-controlled `projects/rh.sigma/` starter project**. Display its title, research problem, project identity, and recorded events. No agents, strategy generation, scheduler, or sophisticated visualizations.

## Project packages
A project is a directory with a `.sigma` suffix:
```text
projects/rh.sigma/
  config.json
  README.md
  state.db            # generated locally; gitignored
  artifacts/
  scenarios/
```
`config.json` is declarative and human-readable. `state.db` is SQLite, holds mutable state and append-only events, and is not committed. The repository includes a **starter project** with a minimal config but no database. Opening a starter project bootstraps missing local state safely. An existing fully initialized project must never be silently reset.

Do not blanket-ignore `*.sigma/` because the starter project must be source-controlled. The scoped `projects/.gitignore` excludes mutable state and generated artifacts.

## Common application interface
Typed, reusable Python commands/queries, independent of all adapters:
- `project.create(path, title, problem)`: create a complete new project package; reject existing destination.
- `project.open(path)`: open a valid initialized project, or initialize missing state for a valid declarative starter; deterministic close/context manager.
- `project.info(path)`: stable project metadata.
- `project.events(path)`: ordered events.

The shared application layer owns validation, lifecycle, initialization, and persistence. CLI, FastAPI, and scenarios call it directly. No subprocess adapters or business logic in route handlers.

## Starter-project initialization
- `config.json` in a starter requires `schema_version`, nonempty `title`, and nonempty `problem`; optional description and other declarative fields are allowed.
- On first open, if `state.db` is absent, initialize it transactionally with a new UUID, UTC timestamp, matching schema version, and exactly one `project.created` event. Subsequent opens preserve identity and events.
- If `state.db` exists, validate it. Corrupt/incompatible/mismatched DBs must produce clear errors, not be replaced.
- A failure during initial bootstrap must not leave a usable partial database. Never rewrite the source-controlled starter config merely to add runtime identifiers.
- A newly created project includes its config, SQLite database, `artifacts/`, and `scenarios/`. New project creation must not leave a partially usable package on failure.
- Reading project info/events does not add events. Event sequence is monotonic and event timestamps are UTC.

## Local web UI
Use **FastAPI + React + TypeScript + Vite**. The frontend is a separate, minimal adapter over the same application commands/queries. No HTMX/Jinja UI.

Initial page:
- A local project path input prefilled with `projects/rh.sigma` and an **Open project** action.
- Once opened, show title, problem, project UUID, creation time, and a simple chronological event list.
- Show understandable error states for nonexistent, invalid, and incompatible projects.
- A minimal close/switch-project action; no complex styling, tree view, agent stream, or rubric editor yet.

Expose small typed JSON HTTP endpoints for opening and inspecting projects; do not expose arbitrary file writes or secrets. Assume local development only, bind to localhost by default, and document how to run both backend and Vite frontend. No authentication is needed for this local-only first slice.

## CLI
Argparse `sigma` console entry point:
- `sigma init --project=PATH --title=TITLE --problem=TEXT`
- `sigma info --project=PATH`
- `sigma events --project=PATH`
- `sigma scenario run PATH`

First three emit stable JSON. Errors to stderr and nonzero exit code. The CLI must also open the starter project and initialize its local state.

## Scenario-driven verification
A small human-readable, source-controlled scenario runner calls application commands/queries directly. Use YAML steps, variable capture, and targeted assertions, only as necessary for the initial scenarios. Each scenario uses an isolated temporary directory. Verify:
1. The checked-in RH starter opens and bootstraps local DB once; repeated opens preserve UUID and history.
2. Newly created project persists across reopening.
3. Info/events are read-only.
4. Existing destinations are not overwritten.
5. Missing, invalid, corrupt, and incompatible projects fail clearly.
6. Interrupted initialization leaves no usable half-project.
7. Event order is stable.
8. FastAPI endpoint smoke checks exercise the same application layer, and the frontend can open and render the sample project.

Use focused Python tests for fault injection or API tests if a tiny scenario DSL cannot express them. Keep all verification offline.

## Engineering and completion
Python + uv, SQLite, FastAPI/Uvicorn, argparse, Ruff and Pyright. React + TypeScript + Vite with minimal dependencies. Do not introduce agent runtimes or a separate task queue yet.

Codex implements the entire first **UI + CLI + scenario** vertical slice, runs scenario tests, backend/API checks, frontend build/typecheck, and CLI smoke checks, then records exact commands/results in `docs/STATUS.md`, commits, and pushes. No unverified claims.

## Deferred
Agent execution, strategy pool and genealogy, rubric evaluation, scheduler, human controls, SSE, advanced visualization, cloud deployment. See `docs/BRAINSTORM.md`.
