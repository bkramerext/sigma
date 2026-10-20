# SPEC-001: Project lifecycle

Status: Approved for implementation
Date: 2026-10-20

## Goal
Implement the smallest offline, testable vertical slice: create, open, inspect, close, and reopen a SIGMA project. A project is a **directory** with a `.sigma` suffix, not a SQLite file. No agents, scheduler, strategies, or browser in this slice.

## Project package
```text
research.sigma/
  config.json
  state.db
  artifacts/
  scenarios/
```
`config.json` contains declarative, human-readable, non-secret project metadata and configuration. `state.db` is SQLite for identity and immutable events. `artifacts/` and `scenarios/` start empty. A user can ignore generated projects with `*.sigma/`.

## Shared application interface
Implement typed application commands/queries in a reusable Python module, independent of CLI and scenario runner. Required operations:
- `project.create(path, title, problem)` returns project information.
- `project.info(path)` returns immutable project information.
- `project.events(path)` returns ordered events.
- `project.open(path)` offers an application-level context manager or handle that closes resources deterministically.

Use clear typed results and domain-specific exceptions. Do not implement CLI logic in services or invoke CLI subprocesses from scenarios. This interface will also serve the future web UI.

## CLI contract
Use argparse and a `sigma` console entry point:
- `sigma init --project=PATH --title=TITLE --problem=TEXT`
- `sigma info --project=PATH`
- `sigma events --project=PATH`
- `sigma scenario run PATH` (one YAML scenario file or a directory of them)

Print stable JSON on stdout for the first three commands. Errors go to stderr with nonzero status. CLI commands may open and close a project within one invocation. No interactive prompts.

## Persistence and invariants
- A project path must end in `.sigma`; it is a directory containing the expected package structure. Reject existing paths without modifying them.
- `config.json` stores schema version, immutable project UUID, title, problem, and UTC creation timestamp. `state.db` stores the same immutable identity and schema version for consistency validation, plus append-only events.
- Create one `project.created` event atomically with initial DB state. Events have increasing sequence numbers, UTC timestamp, actor, type, and JSON payload.
- Validate configuration structure, database integrity, schema compatibility, and agreement of identity metadata on open. Never silently initialize or migrate an existing path.
- `info` and `events` do not alter logical history. Closing releases DB connections.
- A failed initialization must not leave a partially usable `.sigma` directory: build in a temporary sibling directory and publish only when complete. Avoid overwriting an existing destination, including in failure paths.
- No secrets or machine-specific absolute paths in committed project configuration.

## Scenario-driven acceptance
Implement a **minimal** source-controlled scenario runner that calls the shared application interface directly. YAML scenarios support a name, description, and ordered steps invoking `project.create`, `project.info`, `project.events`, with variable capture and assertions on selected fields. Support only the operations and assertion features required by these scenarios; no general-purpose DSL. A scenario runs inside an isolated temporary directory and reports precise assertion failures. Use deterministic expectations, avoiding fixed UUIDs and timestamps.

Create readable scenarios demonstrating:
1. Create, inspect, reopen, and preserve project identity and event history.
2. Read-only inspection does not append events.
3. Existing destination is rejected without modification.
4. Missing, corrupt, and unsupported-schema packages fail clearly.
5. Failed initialization leaves no usable half-project.
6. Event ordering is stable.

If some fault-injection checks cannot be expressed cleanly in the tiny scenario format, use focused Python tests for those mechanics. The scenario runner is the primary acceptance mechanism, not pytest. All verification is offline.

## Engineering boundaries
Python with uv, pyproject.toml, argparse, SQLite, and a small YAML dependency if needed. Domain models under `models/`. Shared commands/queries under `application/`. Adapters under `interfaces/cli/` and `scenarios/` (or comparably clear package structure). Ruff and Pyright; pytest permitted for targeted low-level checks. Keep dependency count small.

## Completion
Run the source-controlled scenarios, CLI smoke checks, Ruff, and Pyright (and any focused tests). Record exact commands and outcomes in `docs/STATUS.md`. Commit and push a coherent implementation increment. Do not claim success until the commands actually pass.

## Deferred
Strategy pool, genealogy, rubric evaluation, human priority controls, agent execution, scheduler, web UI, artifact generation, migrations, and cloud features. See `docs/BRAINSTORM.md` for ideas not yet promoted to specifications.
