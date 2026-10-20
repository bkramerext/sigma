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

## Direct checkout launcher

Added executable `./sigma` for use without environment activation; it delegates to
uv with the checkout's absolute project path and forwards all arguments. The name
avoids shadowing the `sigma` Python package (a root `sigma.py` broke module imports
in CLI smoke verification and was replaced before delivery). Plain `sigma` remains
available after `source .venv/bin/activate`. README now leads with the direct launcher.

Verification on 2026-10-20: `./sigma --help`, `./sigma setup`, `./sigma test`, and
`uv run pyright sigma` all passed. The test command includes launcher lint and
format checks (nine Python files). Missing uv produces an actionable error and
exit status 2. Existing non-failing dependency notices are unchanged.

## One-command UI launch

Added `./sigma ui` (also `sigma ui` in an activated environment). It launches
FastAPI on 127.0.0.1:8000 and Vite on 127.0.0.1:5173 from the checkout, waits for
both HTTP endpoints, and prints the browser URL. Ctrl+C or SIGTERM stops both
process groups, including npm's Vite child. A server exit, launch error or startup
timeout also cleans up both servers. Missing frontend dependencies point to
`./sigma setup`; occupied ports fail without terminating existing listeners.
Ports remain fixed to match the local proxy and browser-origin policy.

Verification on 2026-10-20:

- `./sigma test`: passed lifecycle/API and CLI checks, maintenance/UI supervision
  scenarios, Ruff lint/format (ten files), Pyright, frontend types and build.
- UI supervision scenarios cover missing dependencies, occupied ports, partial
  startup failure, unexpected server exit, interrupt cleanup, and forced cleanup
  after a graceful shutdown timeout.
- `./sigma ui` with the earlier review servers running: correctly rejected the
  occupied port. Those earlier servers were then stopped for the live smoke test.
- `.venv/bin/python /tmp/sigma-ui-smoke.py`: passed live launcher startup from
  `/tmp`, readiness output, frontend HTTP and proxied project inspection, Ctrl+C,
  and checks that neither port retained a listener after shutdown. Repeated twice
  consecutively to verify immediate restart. The restart check caught a transient
  socket-state issue; port preflight now uses SO_REUSEADDR, matching server reuse.

README now launches the UI with `./sigma setup` followed by `./sigma ui`. The UI
command stays in the foreground; open the printed URL in a browser. Setup remains
the dependency installer and UI does not install npm packages implicitly.

## ASN-2: project browser copy and header

Updated the hero, description, project helper, and empty-state copy to the assigned
wording. The full SIGMA expansion now appears once, directly beneath the header
logo; removed the partial hero eyebrow and duplicate footer. Kept the muted green
palette, typography, whitespace, project controls, and opened-project details.
The header stacks on narrow screens so its expansion remains readable.

Verification on 2026-10-20:

- `git pull --ff-only`: retrieved ASN-2 at `07e06e7`.
- `./sigma test`: passed lifecycle/API scenarios, CLI smoke checks, maintenance/UI
  supervision checks, Ruff lint/format, Pyright (zero errors/warnings), frontend
  typecheck, and production build. Existing non-failing TestClient notice remains.
- `uv run --with playwright python /tmp/sigma-asn2-browser.py`: passed in headless
  Google Chrome against the already-running local UI/API. Verified every assigned
  text replacement, a single full expansion inside the header positioned beneath
  the logo, and absence of the former partial eyebrow and footer. Exercised empty,
  opened, close/reopen, and switching to a temporary project and back. RH identity,
  directory, format version, initialization event, and the finite-experiments
  qualification remained visible; the RH project file was byte-identical afterward.
- Browser checks passed at 320px and 390px widths without horizontal overflow and
  with no JavaScript page errors. Screenshots saved to `/tmp/sigma-asn2-empty.png`,
  `/tmp/sigma-asn2-open.png`, and `/tmp/sigma-asn2-mobile.png`; desktop empty and
  mobile opened screenshots visually inspected.

Only frontend copy/presentation and delivery documentation changed; project
services, storage, and CLI behavior are unchanged.

## ASN-3: project workspace and persistent manual strategies

Implemented Home `/` and a distinct `/project?path=...` research workspace. Opening
navigates to the project; title/problem lead the page, followed by an initially
empty strategy pool. Close returns Home. Reload, direct project URLs, and browser
back/forward reopen the correct data; Home remembers the last project path after
close, including after a project-page reload. Project details/history remain in a
secondary disclosure. The initial interaction/visual decisions were recorded in
[asn3-design.md](asn3-design.md) before implementation.

New strategy opens an inline form with focused title input, title/approach fields,
Save and Cancel. A successful save focuses the new strategy and announces success;
errors retain both fields. Cancel/Escape restores focus to New strategy. Strategy
rows show full approach and human authorship. Keyboard-accessible native Actions
and nested Schedule/Report artifact disclosures expose the assigned hierarchy.
Generate strategy, Promote, Demote, Pause/Resume, Remove, Audit, other artifact
types and Fork remain explicitly unavailable with explanations. No scheduling,
agent work, reports or forks are simulated; no artifact types were invented.

Shared typed services now create/list strategies via API, CLI and executable
scenarios. Each record has a stable UUID, human author kind, title, approach and
creation timestamp, with a linked contiguous event. New projects use JSON schema
v2. v1 opens without rewriting; first strategy save preserves an exact v1 backup
and atomically publishes v2 with old identity/history intact. Cooperative writers
serialize through a stable advisory lock. See [DECISIONS](DECISIONS.md) for backup,
POSIX/local-filesystem, external-edit, lost-response and crash limitations.

Actual verification on 2026-10-20:

- `git pull --ff-only`: retrieved ASN-3 at `3459102`.
- `./sigma test`: all lifecycle and strategy scenario groups, CLI smoke checks,
  maintenance/UI supervision checks, Ruff lint/format (eleven Python files),
  Pyright (zero errors/warnings), frontend typecheck and production build passed.
  The existing non-failing Starlette TestClient deprecation notice remains.
- Strategy scenarios cover v1 read-only compatibility, exact backup/migration,
  stable identity and history, save/reopen, validation limits, failed file
  flush/replacement/backup link, migration retry and backup conflicts, detected
  external edits, unsafe lock symlinks, missing projects, concurrent writers,
  corrupt strategy/event records, and real API create/list/error responses.
- CLI smoke checks cover `new-strategy`, `strategies`, reopen persistence, JSON
  output, validation errors and unchanged state on rejection, alongside lifecycle.
- `npm --prefix frontend run build`: passed during UI implementation and after
  navigation/focus fixes; final typecheck/build also passed through `./sigma test`.
- `./sigma ui`: restarted the local servers to load the new API, verified readiness;
  left the final implementation running at http://127.0.0.1:5173 for review.
- `uv run --with playwright python /tmp/sigma-asn3-browser.py`: passed on the final
  running implementation in real headless Google Chrome. Verified Home → open RH
  → project → close → Home, back/forward, heading focus, disabled generation with
  explanation, direct reload, form input focus and Escape, injected save failure
  with retained text and successful retry, saved-strategy focus/announcement,
  persistence and stable IDs after reload/close/reopen, and first-save v1 backup.
  Exercised Schedule and Report artifact with keyboard, confirmed every future
  action disabled/explained, and checked Escape restores Actions focus.
- Browser checks used a temporary project for writes. RH remained byte-identical
  with its real objective and empty pool; no test strategies were added to it.
  Checked 390px/320px widths, including the expanded action hierarchy and mobile
  creation form, without horizontal overflow. Invalid project URLs displayed an
  error and recovered through Close. No JavaScript page errors occurred.
- Screenshots inspected: `/tmp/sigma-asn3-rh.png`, `/tmp/sigma-asn3-saved.png`,
  `/tmp/sigma-asn3-mobile-320.png`, and `/tmp/sigma-asn3-mobile-form.png`. A desktop
  expanded-menu capture is also at `/tmp/sigma-asn3-menu.png`.

All required ASN-3 interactions are implemented. Future commands listed above are
intentionally unavailable under the assignment boundary. No agents, scheduler,
evaluator, audits, autonomous forks, paid calls or cloud services were added.
