# SIGMA status
Updated: 2026-10-20

## Active specification
**[SPEC-001: Local project browser and lifecycle](../specs/project-lifecycle.md)**. Approved for implementation; no implementation or test results reported yet.

## Committed starter project
`projects/rh.sigma/config.json` is source-controlled, along with its README and placeholder directories. Mutable `state.db` and generated artifacts are gitignored. The starter is not yet openable until SPEC-001 is implemented.

## First demonstrable user action
Start the local FastAPI server and React/Vite frontend, open `projects/rh.sigma` in the browser, and inspect its metadata and event history. CLI and scenarios must use the same application services.

## Acceptance checklist
- [ ] Scaffold Python/uv app, FastAPI server, React/TypeScript/Vite UI, argparse CLI.
- [ ] Shared typed project creation/open/info/events services.
- [ ] Bootstrap source-controlled starter project state on first open; preserve identity on reopen.
- [ ] Browser opens RH project and shows metadata/events and meaningful errors.
- [ ] CLI creates/opens/inspects projects.
- [ ] Executable scenarios verify lifecycle, persistence, failure handling, and event ordering.
- [ ] Backend/API checks and frontend build/typecheck pass.
- [ ] Document exact setup/run commands and verification results.
- [ ] Commit and push tested implementation.

## Not active
Strategies, rubrics, scheduling, agent runtime, SSE, and advanced visualizations.

## Coordination
Codex implements and tests the approved specification, records actual results, and commits/pushes. ChatGPT reviews the changes against the specification. No secrets or recruiting context in the public repository.
