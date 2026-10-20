# SIGMA status
Updated: 2026-10-20

## Active specification
**[SPEC-001: Project lifecycle](../specs/project-lifecycle.md)** is approved and ready for Codex implementation. No implementation or verification has yet been reported.

## Acceptance checklist
- [ ] Scaffold Python/uv package and `sigma` argparse CLI.
- [ ] Implement `.sigma/` package creation, validation, opening and deterministic closing.
- [ ] Store `config.json`, `state.db`, empty `artifacts/` and `scenarios/`.
- [ ] Record exactly one atomic `project.created` event and expose read-only info/events.
- [ ] Implement a small source-controlled scenario runner using the common application interface.
- [ ] Exercise persistence, read-only operations, overwrite refusal, corruption, schema mismatch, atomic failure, and event ordering.
- [ ] Run scenarios, CLI smoke checks, Ruff and Pyright; record actual results.
- [ ] Commit and push implementation.

## Not active
Strategy genealogy, rubric evaluation, scheduler, human controls, agent runtime, and web UI. See `docs/BRAINSTORM.md`.

## Coordination
Codex implements the active spec, tests, updates this file with commands/results, and commits/pushes. ChatGPT reviews against the specification. GitHub is the shared source of truth.

## Open dependency
Runtime agent authentication and API billing are not settled. SPEC-001 must run fully offline.
