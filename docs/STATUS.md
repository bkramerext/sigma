# SIGMA status
Updated: 2026-10-20

## Active specification
[SPEC-001: Browser-first project lifecycle](../specs/project-lifecycle.md), ready for Codex implementation. No implementation or test results yet.

## Starter
`projects/rh.sigma/` contains only a source-controlled placeholder. Codex chooses its internal data model, serialization, and initialization behavior.

## First demonstration
Self-host the local FastAPI + React/Vite application; open `projects/rh.sigma` and inspect its metadata and events. CLI and scenarios use the same application services.

## Checklist
- [ ] Design and document minimal project representation.
- [ ] Browser opens RH seed and shows project data/history.
- [ ] CLI creates/opens/inspects projects.
- [ ] Executable scenarios verify persistence, invalid inputs and safe failure.
- [ ] Frontend build, backend checks, API/CLI smoke checks pass.
- [ ] Record actual commands/results, commit and push.

Agent execution, rubrics, scheduler, and advanced visualizations remain deferred.
