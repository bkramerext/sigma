# SIGMA architectural decisions
Date: 2026-10-20

1. **Project:** A `.sigma` directory. `projects/rh.sigma/` is a source-controlled seed. Codex designs internal files, data model, serialization, and initialization in SPEC-001.
2. **Common application interface:** CLI, web API, and executable scenarios are peers over typed Python services.
3. **UI stack:** React + TypeScript + Vite with FastAPI. Browser-visible interaction is required in the first increment.
4. **Research:** Strategies are evolving investigations with parent-linked forks and generations; evaluations assess their promise using qualitative rubrics and adversarial tests.
5. **Governance:** Independent evaluation, deterministic constrained scheduling, auditable human controls and priorities.
6. **Verification:** Human-readable executable scenarios test common application services, with UI and CLI developed in tandem.
7. **Scope:** SPEC-001 covers project lifecycle and local browser only. Agent execution and advanced features are deferred.

## SPEC-001 original format: minimal versioned document

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


## ASN-3: manual strategy persistence and migration

New projects use schema v2. Each strategy has a stable UUID, a title (1–200
characters), approach (1–10,000), `author_kind: "human"`, and a timezone-aware
creation timestamp. Creation appends a contiguous `strategy.created` event
referencing that ID and timestamp in the same document. Both the full record and
matching event are validated on read. No genealogy, assessments, scheduling state,
agent authors, or reports are invented. CLI, API and scenarios share the typed
`create_strategy` and `list_strategies` services.

Schema v1 remains readable without migration or writes. The first successful
strategy save upgrades it to v2, preserving project identity, title, objective and
all earlier events, and first publishes an exact `project.v1.json` backup through
a no-replace link. Conflicting or symlink backups stop the save. A failed migration
may leave a complete backup; retries accept it only if it matches the current
legacy bytes. The backup is not updated on later saves. Older releases reject v2;
restoring a v1 backup would discard later strategies, so recovery is a deliberate
manual operation, not an automatic downgrade.

Writers hold an advisory `flock` on a stable `.write.lock` inode and re-read under
that lock. The lock file remains in the package; OS locks release on exit/crash.
Do not remove it during an active save. The whole next document is staged and
fsynced, then atomically replaces project.json. Readers observe complete old/new
documents. Cooperative concurrent writes serialize, preserving every strategy.
An extra byte comparison before replacement rejects external edits detected
during staging. This is not a compare-and-swap guarantee for noncooperating tools:
a manual edit after that comparison can race, so edit the document only while
writers are stopped. Lock/state symlinks are rejected; other project files remain
untouched. Failure tests cover flushing, backup publication, replacement, and
external-edit conflicts.

This implementation targets local POSIX filesystems (macOS/Linux) with advisory
locks, hard links and atomic rename. It does not promise cross-machine filesystem
locking or power-loss durability: directory entries are not fsynced. A hard kill
can leave staging files, which are preserved for manual inspection. Full-document
rewrites and validation remain linear in project size; SQLite remains deferred
until needed. There is no retry/idempotency protocol for an ambiguous lost HTTP
response after a completed save; inspect the pool before submitting again.

The UI uses Home `/` and `/project?path=<directory>` routes, with History API
navigation and reload/back/forward handling. The project page is the research
workspace; technical metadata/history are a secondary disclosure. Native nested
disclosures expose future strategy commands with visible explanations and disabled
controls. They are not ARIA menus with unsupported keyboard contracts. Saving a
manual idea is the sole new research mutation. The pre-implementation interaction
and visual decisions are recorded in [the design note](asn3-design.md).
