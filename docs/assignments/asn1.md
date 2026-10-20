# ASN-1: Implement SPEC-001 browser-first project lifecycle

Status: Ready for Codex
Specification: [SPEC-001](../../specs/project-lifecycle.md)
Working guidance: [AGENTS.md](../../AGENTS.md)

## Assignment

Implement SPEC-001 from `specs/project-lifecycle.md`, following `AGENTS.md`.

1. **Synchronize first.** Run `git pull --ff-only` to synchronize with GitHub, then read the project documentation and specification.
2. **Own the project representation.** Design the project data model, serialization, directory layout, initialization, and persistence. Keep the implementation simple and explainable. The checked-in `projects/rh.sigma/` is only a seed; do not assume a prescribed internal format.
3. **Deliver a browser-first vertical slice.** Implement a React/TypeScript/Vite frontend, FastAPI backend, CLI, and executable scenarios, all using shared Python application services.
4. **Make the first demonstration work.** I must be able to launch the local webpage, open `projects/rh.sigma`, and inspect the project and its history.
5. **Verify before delivery.** Run the prescribed scenarios, tests, lint/type checks, frontend build, and CLI/API smoke checks. Record actual commands and results in `docs/STATUS.md`.
6. **Commit and push** the tested implementation with a commit message that accurately describes the changes.

Do not implement deferred features. If a major architectural decision or requirement is unclear, ask before proceeding.

## Acceptance

- The locally hosted browser can open the RH seed and display project metadata and event history.
- CLI, browser API, and scenarios call the same application services.
- Reopening preserves project identity and history; errors and initialization failures are handled safely.
- Verification results and local launch instructions are documented.
- Implementation is committed and pushed.

## Scope

This is an implementation assignment, not a request to redesign the project's research objectives. No agents, scheduler, rubric evaluation, advanced visualization, paid APIs, or cloud deployment in this increment.
