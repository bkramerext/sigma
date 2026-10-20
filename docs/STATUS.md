# SIGMA status
Updated: 2026-10-20

## SPEC-001 / ASN-1 implemented and verified

React/TypeScript/Vite browser, FastAPI API, argparse CLI, and executable scenarios
use shared typed Python services. The browser opens `projects/rh.sigma` and shows
its objective, UUID, path, format version and initialization event. Close and
switch are supported, with visible errors and retention of the last valid view
when a switch fails. No agents or paid calls are implemented.

The project format is a versioned `project.json` inside a `.sigma/` directory.
Initialization publishes a complete document atomically without replacing existing
files. Reads validate metadata/history and never change it. The canonical RH seed
initializes once on open; custom directories require explicit initialization.
Generated state is ignored. Storage tradeoffs and crash limitations are documented
in [DECISIONS](DECISIONS.md); setup and launch commands are in [README](../README.md).

## Actual verification results

Performed on macOS with Python 3.14.7, Node 24.21.0 and npm 11.19.0:

- `git pull --ff-only`: synchronized to `07a3c0b`, retrieving ASN-1.
- `uv sync`: passed; Python dependency lockfile created.
- `npm install --fetch-retries=0 --fetch-timeout=15000` in `frontend`: passed;
  npm lockfile created, audit reported zero vulnerabilities.
- `.venv/bin/python scenarios/lifecycle.py`: all six scenario groups passed.
  Covers seed initialization, close/reopen identity and history, repeated immutable
  reads, explicit creation, invalid paths and blank metadata, preservation of
  existing research, injected publication failure/collision cleanup, malformed
  JSON, incompatible schema, invalid metadata/events, and API lifecycle/errors.
  Origin and host boundary checks passed. The seed fixture is a temporary directory.
- `.venv/bin/ruff check src scenarios`: passed.
- `.venv/bin/ruff format --check src scenarios`: passed (five files).
- `.venv/bin/pyright`: passed, zero errors/warnings.
- `npm run build` in `frontend`: passed TypeScript checking and Vite production build.
- `npm run typecheck` in `frontend`: passed.
- `.venv/bin/sigma open projects/rh.sigma`, `inspect`, `events`, `close`: passed;
  actual RH seed initialized and repeated reads retained identity/history.
- A Python subprocess CLI smoke check exercised init/open/inspect/events/close,
  parsed JSON output, verified identity and event sequence, and verified exit 2
  with JSON stderr on overwrite/missing-project errors: passed.
- Started `.venv/bin/uvicorn sigma.api:app --host 127.0.0.1 --port 8000` and
  `npm run dev` in `frontend`: both served on localhost successfully.
- `uv run --with playwright python /tmp/sigma-browser-check.py`: passed with
  installed headless Google Chrome. Actual browser opened RH, displayed its
  metadata/event, closed and reopened with the same identity, and showed a missing
  path error while retaining the prior view. No page JavaScript errors; 390px
  viewport had no horizontal overflow. Screenshot inspected at `/tmp/sigma-open.png`.
  Playwright was a temporary verification dependency, not a project requirement.
- `git check-ignore -v projects/rh.sigma/project.json`: confirms generated seed
  state is excluded; checked-in `.gitkeep` remains the reproducible seed.

Starlette emits a non-failing deprecation warning for its httpx TestClient adapter;
all API assertions pass. Restricted execution initially blocked package access and
localhost binds; the same operations passed with approved access.

## Remaining scope

No SPEC-001 implementation work remains. Agent execution, rubrics, scheduler,
advanced visualizations, database migration and cloud hosting remain deferred.
The UI is served by the local Vite server alongside the local API; frontend `dist/`
is a build artifact, not a bundled server deployment.

## CLI setup and test commands

Added `sigma setup` (locked Python/dev dependency sync and frontend `npm ci`)
and `sigma test` (lifecycle/API scenarios, CLI smoke checks, maintenance failure
checks, Ruff lint/format, Pyright, frontend types and build). Both stream output,
use the source checkout as the working directory, and stop on failure with a
nonzero status. Missing prerequisites and process launch failures have clear
messages. README includes `uv run sigma setup` for bootstrap and activated-venv
usage for bare `sigma setup` / `sigma test` commands.

Verification on 2026-10-20:

- `uv run sigma setup`: passed dependency sync and npm clean install; zero audit
  vulnerabilities. Existing npm install-script notices remain non-failing.
- `uv run sigma test`: passed every step, including API and real CLI process checks.
- `/Users/admin/sigma/.venv/bin/sigma test` launched from `/tmp`: passed every step,
  confirming callers do not need to change into the checkout first. Ruff checked
  eight formatted Python files and Pyright reported zero errors/warnings.
- Maintenance scenarios verify missing tools, launch errors, child exit-code
  propagation and stopping before later checks after a failure.
- `uv run sigma --help`: lists setup and test with descriptions.

These checks use temporary projects and leave the RH seed unchanged. Browser
interaction remains covered by the earlier browser verification, not `sigma test`.
