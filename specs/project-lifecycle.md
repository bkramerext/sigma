# SPEC-001: Browser-first investigation lifecycle

Status: Implemented

## Goal

Open the source-controlled `investigations/rh.sigma/` seed in a local browser, showing investigation identity, problem, and history. Preserve identity on reopen.

## Contract

- An investigation is a `.sigma/` directory. Codex chooses safe storage and initialization; never overwrite existing research.
- Typed shared Python services support init, open, inspect, close, and event listing. Browser, FastAPI, CLI, and scenarios are peer adapters.
- Reject invalid/corrupt/incompatible investigations without modifying them. Initialization must avoid partial publication.
- Browser supports path selection, open, close/switch, details/history, and visible errors.
- CLI provides machine-readable investigation commands.
- Executable scenarios verify initialization, persistence, immutable reads, failures, and event ordering.

## Verification

Run scenarios, API/CLI checks, frontend typecheck/build, Ruff, and Pyright. Record actual results in `docs/STATUS.md`.

## Scope

No agents, scheduler, rubric engine, paid APIs, or remote hosting in SPEC-001. Later assignments extend the foundation.
