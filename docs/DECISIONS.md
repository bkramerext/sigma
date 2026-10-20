# SIGMA architectural decisions
Date: 2026-10-20

1. **Project:** A `.sigma` directory. `projects/rh.sigma/` is a source-controlled seed. Codex designs internal files, data model, serialization, and initialization in SPEC-001.
2. **Common application interface:** CLI, web API, and executable scenarios are peers over typed Python services.
3. **UI stack:** React + TypeScript + Vite with FastAPI. Browser-visible interaction is required in the first increment.
4. **Research:** Strategies are evolving investigations with parent-linked forks and generations; evaluations assess their promise using qualitative rubrics and adversarial tests.
5. **Governance:** Independent evaluation, deterministic constrained scheduling, auditable human controls and priorities.
6. **Verification:** Human-readable executable scenarios test common application services, with UI and CLI developed in tandem.
7. **Scope:** SPEC-001 covers project lifecycle and local browser only. Agent execution and advanced features are deferred.

## SPEC-001 implementation: minimal versioned document

A project directory contains `project.json` with schema version 1, UUID identity,
nonempty title and problem, and an ordered list of typed events. Its first and
currently only event is `project.initialized`, sequence 1, with a UTC timestamp.
Open, inspect and close are observations, so they do not append history. Reads
validate the complete document, including event sequence and timestamp timezone.
Unknown versions and corrupt documents fail without modification.

One JSON document keeps metadata and history consistent without a database or
cross-file transaction for this small slice. It is portable and inspectable, but
rewrites and validation will become costly for large histories. Future event
mutation should introduce a versioned migration and transactional storage (likely
SQLite); do not add unsynchronized parallel writers to this format.

Initialization writes and fsyncs a temporary file in the target directory, then
publishes through an atomic hard link that fails if `project.json` already exists.
This requires a local filesystem with hard-link support. Exceptions remove the
staged file, and an empty directory created by that attempt is removed. Existing
research and existing state are never replaced. Process termination can leave a
staging file; it blocks subsequent initialization for manual inspection rather
than silently discarding evidence. This is atomic publication, not a guarantee
against every filesystem/power-loss failure (directory entries are not fsynced).

The checked-in `.gitkeep` is the stable RH seed input; RH metadata defaults live in
the shared service. Only that canonical repository directory initializes on open.
Generated `.sigma` contents are ignored by Git. Each local initialization receives
a fresh identity; all reopens of that local package retain it. Copy the entire
package, including project.json, to move an existing project's identity/history.
No secrets belong in the project document.

FastAPI, argparse, and scenarios call the same frozen typed service results. The
browser holds its own active view; the API holds no session or project handles.
Host and browser-origin checks restrict access to the documented localhost flow.
The API is for trusted local use, with filesystem permissions of the launching user.
