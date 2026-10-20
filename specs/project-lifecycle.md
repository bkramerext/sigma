# SPEC-001: Project lifecycle

Status: Approved for implementation
Scope: First milestone, project persistence and CLI lifecycle
Date: 2026-10-20

## Goal
Create, open, inspect, close and reopen a SIGMA project stored in one portable SQLite-backed `.sigma` file. This is a **small vertical slice**. Do not implement LLM agents, strategy generation, scheduling or the browser UI in this spec.

## Terminology
A project is a persistent research workspace. Opening a project establishes a usable application-level handle; closing releases resources. A CLI process may implicitly close on exit. A project database is not a Git repository and should not be automatically committed.

## CLI contract
Provide a console entry point named `sigma` using `argparse` with:
- `sigma init --project=PATH --title=TITLE --problem=TEXT`: create a new project; reject an existing path without overwriting.
- `sigma info --project=PATH`: open an existing project, validate schema, print stable machine-readable JSON with project id, title, problem, schema version and creation timestamp; then close.
- `sigma events --project=PATH`: list recorded events in sequence order as JSON (empty array permitted). 

Keep commands and options explicit; do not introduce hidden interactive prompts. `sigma generate --project=rh.sigma` is a later spec, not this one.

## Data and invariants
- A `.sigma` file is a valid SQLite database with a schema version, immutable project UUID, title, problem statement, creation timestamp in UTC and an append-only event table.
- Exactly one project identity exists per database. Project id, creation timestamp and initial problem/title survive reopen unchanged.
- Event sequence numbers are monotonically increasing; events include timestamp, actor, event type and JSON payload. The initial `project.created` event is recorded in the same transaction as initialization.
- Successful mutations commit atomically. A failure must not leave a partially initialized usable project.
- Opening a project for inspection does not mutate its logical history. `info` and `events` do not append events.
- Reject missing files, directories, invalid SQLite content and unsupported schema versions with a nonzero exit status and understandable stderr; never silently create a project during `info` or `events`.
- Refuse to overwrite existing project paths. No automatic migrations in this slice.
- Project database connections close deterministically, including on errors.
- Avoid storing secrets or absolute machine-specific paths in the database.

## Implementation boundaries
Put domain model definitions in `models/project.py` and `models/event.py`. Persistence and project lifecycle operations should live in shared services, not directly inside CLI handlers. Keep web integration possible without building it now. Use `uv`, `pyproject.toml`, `pytest`, Ruff and Pyright as specified in project docs. Standard tests run without network access or API credentials.

## Acceptance tests
1. Initializing a project creates a readable SQLite `.sigma` file with one identity and one creation event.
2. Reopening via a new process/service instance yields the same id, title, problem, timestamp and events.
3. Calling `info` or `events` repeatedly does not add events or change stored values.
4. Initialization against an existing path fails without changing its bytes or contents.
5. Missing, corrupt and incompatible-schema paths fail clearly and are not overwritten.
6. Simulated exception during initialization leaves no valid half-created project.
7. Event ordering is stable and monotonic.
8. All tests are offline; CLI tests exercise actual command behavior.

## Completion
Codex documents exact test/lint/type-check commands and results, updates docs/STATUS.md, and commits/pushes this increment. Any contract change requires an explicit spec update with rationale before code is considered complete.

## Out of scope
Strategy pool, agents, rubrics, scheduler, browser, artifacts, migration machinery, collaboration, cloud storage, authentication and full event replay.
