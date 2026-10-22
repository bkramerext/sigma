# SIGMA status

Updated: 2026-10-21

## A14.2 ChatGPT-plan Markdown conversion recovery

Reproduced the reported case against the connected ChatGPT-plan transport using
a disposable copy of the empty-pool Mathematical sample example. The provider
returned HTTP 200 without a `Content-Type`; the previous conversion code tried
to parse the untyped body only as JSON, replaced the parse failure with `{}`,
then described that placeholder as a ChatGPT `other-object` rejection. The
local conversion endpoint returned HTTP 400, and the source and companion store
were unchanged. With the repair, an untyped but correctly framed SSE response
is passed to the shared strict Responses stream validator. Bounded JSON remains
supported, recognized provider errors keep their actionable diagnosis, and
malformed/unknown envelopes are reported as malformed output rather than as a
provider rejection. No API-key fallback or model change occurs.

The Σ control switches to rendered Markdown only after the conversion has been
validated and stored; on failure it remains on the plain source, with one
dismissible request toast and an explicit retry by selecting Σ again. Its hover
title is “Convert to markdown.”

Actual verification: one post-fix live ChatGPT-plan request to the disposable
copy returned provider HTTP 200 with no content type and local API HTTP 200;
the Markdown representation was current and nonempty, while the copied
`project.json` stayed byte-for-byte unchanged. Two earlier diagnostic requests
in the same investigation reproduced the failure and may count against plan/app
usage; all temporary project copies were removed. No live requests are used by
automated tests. `tests/text_views.py`
passed untyped SSE, completed JSON, provider rejection, malformed/partial SSE,
missing `output_text`, structured-output validation, timeout, cancellation,
source/account binding and API error preservation. Real Chrome
`browser_checks/a142.py` passed the one-toast failure, retained source/no saved
artifact, exact tooltip and explicit successful retry using a mock provider.
`./sigma test`, Ruff, Pyright, frontend typecheck/build also passed. The
existing Starlette TestClient/httpx deprecation notice remains non-failing.

## Sample project test stabilization

Updated the sample catalog scenario to cover the current behavior: each open
creates an independent copy with a distinct identity, copied projects enter
Recents, existing research is preserved, and shipped examples remain unchanged.
Added the dedicated sample-copy unit tests to `./sigma test` and updated the
agentic sample scenario to check the same copy semantics. Corrected Ruff import
ordering and formatting issues exposed by the complete run.

Verification on 2026-10-21: `./sigma test` passed all scenarios and unit tests,
Ruff, Pyright, frontend typecheck, and production build. Starlette emitted its
existing non-failing TestClient/httpx deprecation notice.

## Test suite directory migration

Renamed the source-controlled executable checks from `scenarios/` to `tests/`.
Updated `./sigma test`, Ruff and Pyright scopes, the browser-check fixture import,
test run instructions, and documented file paths. Test behavior is unchanged;
the checks remain workflow-oriented and use temporary projects and controlled
providers.

Verification on 2026-10-21: `./sigma test` passed all scenarios, Ruff, Pyright,
frontend typecheck and production build after the rename.

## Text conversion response stabilization

The ChatGPT plan conversion path now accepts either a bounded completed JSON
response or the existing validated event stream. When a plan route returns a
JSON error with HTTP 200, SIGMA reports its sanitized provider diagnostic
instead of surfacing an internal `plan_stream:content_type` parsing failure;
the source remains unchanged. The conversion scenario covers JSON success,
sanitized JSON error, and the explicit SSE content type.

Verification on 2026-10-21: `./sigma test` passed all scenarios, Ruff, Pyright
(zero errors), frontend typecheck, and production build. Several scenarios were
updated to match the current `investigation_type` serialization and six-entry
Recent Projects limit; these were stale test expectations, not runtime changes.

## Large strategy Markdown conversions

The conversion service had incorrectly reused Generate Strategy's 128 KB
provider-response limit. A complete conversion can have a larger response
envelope, especially when a ChatGPT-plan bridge omits `Content-Type` and the
client must buffer a valid SSE stream before classifying it. Text conversions
now have a separate explicit 1 MB response cap, matching the shared SSE parser;
payloads above it are still rejected without truncation or a saved conversion.
The selected model, billing path, source bounds, and validated converted-body
limits are unchanged.

Verification: `tests/text_views.py` converts an approximately 8 KB generated
strategy description from both a >128 KB API JSON envelope and >128 KB untyped
ChatGPT-plan SSE, verifies the full derived result and unchanged authored
approach, and confirms the 1 MB cap rejects oversized responses without writing
a representation. `browser_checks/a142.py` passed the failure-toast/source
retention and explicit-retry UI flow in real Chrome. `./sigma test` passed all
scenarios, Ruff, Pyright, frontend typecheck and production build; no paid API
calls were made.

## Implemented

- **ASN-1 / SPEC-001:** Local project lifecycle with persistent identity/history; shared Python services for UI, API, CLI, and scenarios. RH seed initializes once.
- **Tooling:** `./sigma setup`, `./sigma test`, and `./sigma ui`. UI launches local FastAPI and Vite servers and cleans up on exit.
- **ASN-2:** Refined branding and landing-page copy.
- **ASN-3:** Separate Home and Project screens; persistent manual strategies; keyboard-accessible contextual command hierarchy. Future commands are disabled with explanations.

## Verification

All checks below passed on 2026-10-20:

- `./sigma test`: lifecycle/strategy/API/CLI and launcher scenarios, Ruff, Pyright, frontend typecheck/build.
- Real Chrome/Playwright: open/close, browser navigation, strategy save/reload/reopen, errors, focus, action disclosures, 320px/390px layouts.
- Migration tests: v1 compatibility, exact backup, concurrent writes, corrupt data, failed saves, and external-edit detection.

Tests used temporary projects; RH data was preserved. Existing non-failing Starlette TestClient deprecation notice remains.

## ASN-3.1 verification

Verified on 2026-10-20 after pulling `38f48c4`. ASN-3 already puts the single Fork
control inside Actions, alongside Schedule and Report artifact; no UI code change
was needed.

- `uv run --with playwright python /tmp/sigma-asn31-browser.py`: real Chrome check
  passed. Fork is hidden while Actions is closed, disabled when opened, and linked
  to “Forking is not available yet.” No duplicate exists. Keyboard Enter/Escape
  and focus restoration work; 320px/390px layouts have no horizontal overflow.
- `./sigma test`: all scenarios, Ruff, Pyright, frontend typecheck/build passed.
- Temporary-project bytes and RH data were unchanged by menu interactions.
  Desktop/mobile screenshots: `/tmp/sigma-asn31-desktop.png` and
  `/tmp/sigma-asn31-mobile-320.png`; mobile screenshot visually inspected.

## Command group and button refinement

Schedule and Report artifact now form an exclusive native accordion. Only one
strategy Actions menu can also remain open, including when opened by keyboard.
Command buttons and disclosure triggers share New strategy's outlined styling,
spacing, typography, hover/pressed states and focus treatment; unavailable
commands retain their disabled state and explanation.

Verified on 2026-10-20:

- `./sigma test`: all scenarios, lint/types, frontend typecheck/build passed.
- `uv run --with playwright python /tmp/sigma-accordion-browser.py`: real Chrome
  verified mouse/keyboard exclusivity, matching computed button styles and hover,
  disabled commands, Escape focus restoration, and 320px/390px layouts. Temporary
  project data stayed unchanged; no JavaScript errors. Visually inspected
  `/tmp/sigma-accordion-320.png`.

## Corrected strategy command hierarchy

The strategy-name chevron now reveals three sibling groups: Scheduling, Artifact,
and Actions. There is no visible top-level label. Fork appears only under Actions,
with its disabled state and explanation preserved. Group/menu exclusivity and the
shared outlined control styling remain in place.

Verified on 2026-10-20: `./sigma test` passed. Real Chrome check
`uv run --with playwright python /tmp/sigma-command-hierarchy.py` passed for the
three-group hierarchy, Fork containment, one-at-a-time expansion, keyboard and
Escape focus, and desktop/390px/320px layouts. No JavaScript errors or data
changes; `/tmp/sigma-command-hierarchy-320.png` visually inspected.

## Strategy Edit and Remove

Actions now contains working Edit and Remove commands alongside unavailable Fork;
Remove is no longer in Scheduling. Edit opens a prefilled name/description dialog.
Remove confirms the named strategy and removes it from the active pool, retaining
its full research record and history. Cancel/Escape restores chevron focus; errors
retain dialog text. Edit history exposes before-and-after values under View changes.

The shared services, API and CLI support both operations. First edit/removal of a
v2 project atomically publishes v3 after preserving an exact `project.v2.json`
backup. Identity/authorship/creation time remain unchanged. Removed records remain
in inspection; active-list queries exclude them. Unchanged edits append no event.

Verified on 2026-10-20:

- `./sigma test`: all lifecycle/strategy/edit-removal/API/CLI/launcher scenarios,
  Ruff (twelve Python files), Pyright, frontend types/build passed. Scenarios cover
  backup migration, audit chains, no-op edits, rejection of invalid/removed IDs,
  failed writes, retry, concurrency and corrupt edit/removal histories.
- `uv run --with playwright python /tmp/sigma-edit-remove-browser.py`: real Chrome
  passed prefilled edit, cancellation/Escape/focus, injected failures with retained
  text and retry, persistence after reload/reopen, history before/after values,
  and confirmed removal returning the empty pool. 320px/390px dialogs fit without
  horizontal overflow; no JavaScript errors. Test projects were temporary; RH was
  byte-identical afterward.
- Visually inspected `/tmp/sigma-edit-dialog-320.png` and
  `/tmp/sigma-remove-dialog-320.png`. UI server restarted for the new API.

## ASN-5: approved Strategy Pool workspace

Implemented the supplied workspace identity with a compact transparent metallic
header logo, dark navigation rail, quiet navy canvas, copper/gold New strategy
control, bordered strategy list, and matching forms/dialogs/history. All workspace
rules are isolated in `frontend/src/workspace.css` under `.workspace-page`; older
conflicting workspace header rules were removed. Home JSX and Home-specific CSS
were unchanged. Backend routes, data models and persistence were unchanged.

Asset gate passed: supplied reference is a valid 1705×922 RGB PNG; logo is a
385×96 RGBA PNG with real alpha (range 0–255, transparent corners). Originals are
retained under `assets/`; the public logo copy is byte-identical. No artwork was
regenerated, and the reference screenshot is never served as a UI background.

Actual verification on 2026-10-20:

- Merged `origin/main` through `dc98916` while preserving the local artwork commit
  and pre-existing Home asset modifications. Those Home changes remain unstaged.
- `./sigma test`: all lifecycle/strategy/change/API/CLI/launcher scenarios, Ruff,
  Pyright, and frontend typecheck/build passed. Corrected a pre-existing Ruff
  formatting failure in the CLI smoke test's final print statement; no behavior
  changed. Existing non-failing TestClient warning remains.
- `npm --prefix frontend run build`: final workspace build/typecheck passed.
- `uv run --with playwright python /tmp/sigma-asn5-browser.py`: real Chrome passed
  Home/project/close/back/forward, actual RH opening, temporary strategy creation,
  full descriptions, edit/retry/reload, removal/cancel/reopen, retained history,
  keyboard accordion/focus, skip navigation, loading and error states, disabled
  future controls, and reduced motion. No JavaScript errors; RH file unchanged.
- `uv run --with playwright python /tmp/sigma-asn5-home.py before` and `after`:
  Home screenshots were byte-identical at 1705×922, 1440×1200, 768×1024, 390×844,
  and 320×844. Home source and the pre-existing Home asset hashes also matched.
- Workspace screenshots at those five sizes have no page-level horizontal
  overflow. Inspected `/tmp/sigma-asn5-workspace-1705.png`, `-768.png`, `-320.png`,
  `/tmp/sigma-asn5-edit-mobile.png`, and `/tmp/sigma-asn5-commands-mobile.png`;
  compared the desktop composition with `assets/sigma-workspace-reference.png`.
  Mobile rail scrolls within its own row; the command panel stays within the
  viewport and scrolls when necessary.

Intentional differences from the concept: no title-area Sigma/waves, search or
status filters, invented statuses/IDs/dates, View actions, settings/theme tools,
or nonfunctional project selector. The real title/problem, full approaches,
author/creation metadata, commands and history are preserved. Future destinations
are disabled and marked Later. These are the assignment's prescribed deviations;
no required interactions or visual checks remain blocked.

## ASN-6: Home project commands and research modes

Implemented matched Open Project / New Project dialogs and a resting Home command
pair, stacked on mobile with no path input. Open retains truthful local-path
entry; New previews its server-derived destination and asks only for name,
multiline problem and mode. Both dialogs support keyboard focus, Cancel/Escape,
retained inputs on failure and duplicate/busy protection. Created projects open
the real workspace. Research mode appears in collapsed Project details.

Shared services, API and CLI support managed creation under the checkout's
`projects/` root or an explicit existing owned `SIGMA_PROJECTS_ROOT`. Exclusive
name reservation and staged publication reject existing directories/files,
including symlinks, and preserve concurrent research during rollback. New schema
v4 persists Default/Mathematical; legacy v1–v3 reads default without rewriting,
retaining existing migration/backup and history semantics. See
[design](asn6-design.md) and [decisions](DECISIONS.md) for limits.

Actual verification on 2026-10-20:

- `./sigma test`: lifecycle, managed project creation, strategies, edit/removal,
  API, CLI and launcher scenarios all passed; Ruff check/format (13 Python files),
  Pyright (0 errors), frontend typecheck and production build passed. Existing
  non-failing Starlette TestClient deprecation warning remains.
- New `tests/project_creation.py` verifies both modes on disk and reopen,
  legacy v1/v2/v3 no-write reads, preserved strategy/history semantics, invalid
  modes/fields/names, Unicode naming, collisions, missing/foreign/symlink roots,
  injected publication failures, concurrent files and eight competing creators.
- `uv run --with playwright python /tmp/sigma-asn6-browser.py /private/tmp/sigma-asn6.15KfaQ`:
  real Chrome passed both Home commands, keyboard opening/cancel/focus restoration,
  bad-path and injected-create error recovery with retained text, both persisted
  modes, reload/reopen/back/forward, readonly destination/collision validation,
  two synchronous submissions yielding one request, disabled busy controls/Escape,
  arbitrary existing paths, strategy create/edit/remove and audit history. No JS
  errors; RH state unchanged. Browser-navigation assertions wait for Home to settle
  before traversing history.
- Resting Home and creation dialogs checked at 1705, 768, 390 and 320px; no page or
  dialog horizontal overflow. Visually inspected desktop/320px Home and New
  screenshots, plus 320px Open. Screenshots are `/tmp/sigma-asn6-home-*.png`,
  `/tmp/sigma-asn6-new-*.png` and `/tmp/sigma-asn6-open-320.png`.
- `/tmp/sigma-asn6-workspace.py before` / `after`: full-page workspace screenshots
  byte-identical at 1705×922, 768×1024, 390×844 and 320×844. ASN-5 styles unchanged.
- Accepted pre-existing canonical Home art was preserved and committed as-is;
  SHA-256 `eeb16d623f1723d98e8c9a157603d923c2ca8cfc728483804e20b96da5cd9529`
  matches canonical, generated runtime and browser-served bytes. Deleted the
  generated runtime copy and rebuilt successfully to verify automatic restoration
  from `assets/`. No artwork regeneration or ASN-4.1 animation.
- Browser creation tests used a temporary root; launcher restored to the default
  `/Users/admin/sigma/projects` and destination endpoint verified. A project named
  “My basic project” created during that session was copied without overwriting to
  the default root with identical document bytes; original retained.

Limitations remain local POSIX storage and path-based Open (no native picker).
Crash leftovers and ambiguous lost responses are documented; artifact engines,
recent-project indexing and agent functionality remain deferred.

## A7: Strategies workspace and human-reviewed AI proposals

Implemented the approved compact Strategies workspace with two-level rows,
full-approach disclosure, vertical three-dot commands and upper-right grips.
New Strategy is a single warm split action: primary Write manually, dropdown
Write manually / Generate with AI. Stage rings include text and are explicitly
manually tracked: Draft, Ready to explore, Exploring, On hold. No automatic
research activity or evaluation is claimed. Existing edit/remove/history and
Open/Close remain functional; removed research stays in the project.

Order is durable and active-only, with pointer, Chrome touch, and keyboard
pick-up/move/drop/cancel. Previews do not save; errors revert; stale concurrent
order/active-list changes are rejected. Schema v5 validates order/stage audit
replay and adds optional summary/provenance. V1–v4 reads remain unchanged with
creation-order/Draft defaults and exact backups on actual v5 updates. Existing
manual-only lazy migrations remain compatible.

OpenAI Responses integration is opt-in and server-configured (`SIGMA_AI_ENABLED`,
`OPENAI_API_KEY`, optional `SIGMA_AI_MODEL`, default `gpt-4.1`). Generate returns
one strictly validated, unsaved draft. Context disclosure/consent, optional seed,
editable review, explicit regeneration, human acceptance and provider/model
provenance are implemented. Server timeout/concurrency/context/output bounds,
lexical duplicate rejection and request cancellation are enforced. No keys or
prompt dumps are stored in projects or browser bundles. No paid calls were made.

Actual verification on 2026-10-20:

- Asset gate: exact supplied `assets/sigma-strategies-reference.png` inspected,
  1672×941 PNG, SHA-256
  `9cf973b6552f755061b8f45aecbfdd17275a1e6b50bd84a4ce0536da13e49858`.
  Retained as reference only. Original Home PNG and workspace logo hashes match
  the A6 baseline. Obsolete unused SVG logos removed after checking references;
  Home/atmosphere assets retained.
- `./sigma test`: all lifecycle/project-create/strategy/change/tracking/proposal/
  API/CLI/launcher scenarios passed, plus Ruff check/format (16 files), Pyright
  (0 errors), frontend typecheck and production build. The existing non-failing
  Starlette TestClient deprecation warning remains.
- `tests/strategy_tracking.py`: v1–v4 no-write reads/defaults, exact backups,
  active-only order, removed history, stable IDs/timestamps, no-ops, failed saves,
  stale order, competing reorder/stage/edit writes, corruption and API/CLI checks.
- `tests/proposals.py`: exact official Responses endpoint/payload, strict
  schema/full context, empty/seeded generation, no mutation until human-edited
  acceptance, signed provenance, unavailable/invalid config, bad/refused/
  incomplete output, rate errors, lexical duplicate, timeout, concurrent requests,
  oversized context and cancellation. ASGI middleware/endpoint disconnect replay
  confirms cancellation joins the adapter and releases its request slot.
- `uv run --with playwright python browser_checks/strategies.py`: real installed
  Chrome passed desktop/manual/stage/menu/detail flows, keyboard reorder/cancel,
  save rollback, reload, desktop pointer drag, actual CDP touch drag/drop/cancel,
  narrow layouts, AI fixture error/retry/review/edited acceptance and cancellation,
  and reduced motion. No JavaScript errors. These are browser touch-emulation
  checks, not physical-device testing. Provider is an explicitly identified
  HTTP fixture on a separate API port, forwarded only in the test browser.
- `uv run python browser_checks/http_cancel.py`: real HTTP disconnect against the
  fixture cancels an in-flight request, permits an immediate next request, and
  leaves project bytes identical. This caught/fixed receive-channel polling that
  missed disconnect events behind middleware. No claim of live provider billing
  cancellation: OpenAI may already have processed a sent request.
- `uv run ruff check src tests browser_checks` and format checks passed.
  Browser fixture/checks are source-controlled and documented separately from
  `sigma test`; they require installed Chrome and Playwright.
- Compared actual workspace at 1672×941 with the approved reference; inspected
  screenshots for split menu, clamped Actions menu, expanded approach, lifted
  touch row, 768/390/320px layouts and desktop/mobile draft review. Artifacts are
  `/tmp/sigma-a7-workspace-*.png`, `-split-1672.png`, `-actions-1672.png`,
  `-detail-1672.png`, `-touch-lift-390.png`, and `-ai-review-*.png`.
- Home before/after screenshots byte-identical at 1672×941, 768×1024, 390×844 and
  320×844 against the A6 implementation. Actual default server checked for
  unavailable-provider messaging, disabled Generate, Escape/focus restoration,
  RH Open/Close and browser back/forward. RH document, Home art and logo bytes
  remain unchanged. Tests used temporary projects only.

Intentional differences from the mock: omit invented S-IDs/sample data; full UUID
and real creation metadata live in expanded details. Stages reflect human work
rather than fictitious automated evaluation. Unimplemented rail destinations
remain disabled/Later; retain actual project title and Close instead of fake
selector/theme/settings controls. Small +/− detail affordances expose full text;
manual writing retains its working inline composer. On mobile the rail scrolls,
rows stack stage labels, and menus/dialogs fit the viewport. Draft review collapses
context after generation. No Home changes or A4.1 animation.

Live OpenAI account access, billing and mathematical proposal quality were not
verified: controlled HTTP fixtures exercised the real adapter and no paid calls
were authorized. Set the documented server environment and make an explicit user
request to use live generation. Semantic novelty/proof validity still require
human judgment; no runner, evaluator, branch lineage or artifact engine is added.
The UI is running normally with default project location; the test fixture server
is stopped after verification. See Getting Started for setup/limits and Decisions
for schema/concurrency/receipt tradeoffs.

## A8: shared project settings, curated models and real API status

Implemented one Create/Edit project dialog (exact headers/actions), the small
44px pencil beside the project heading, and transactional name/problem/mode/model/
Thinking level updates. Creation retains its readonly managed destination; Edit
never moves it. No-op, Cancel/Escape and Close do not save. Successful edits update
the workspace in place and return focus; failed/stale saves retain entered values.
All new init/create operations persist schema v6. Legacy v1–v5 reads stay unchanged;
first settings updates make an exact version backup and retain UUID, strategies,
stages, active order, archived records and prior events. Strict `project.updated`
before/after chains and expected-settings conflict checks protect concurrent edits.

Reviewed Sol/Luna/Astra choices use four compatible efforts (High default), with
relative $/$$/$$$ cost tiers and official pricing link. Official model pages were
opened/verified on 2026-10-20 for text, Responses, strict JSON and reasoning support;
references are in Getting Started and `model_catalog.py`. No token prices are
inferred from `/v1/models`. Fresh account discovery intersects known IDs only;
unavailable/unverified choices are qualified and stored selections are retained.
Sol/High is preferred when verified accessible; alternate initial defaults and
provisional offline Sol/High are explicit. Unreviewed bootstrap overrides are
called out; saved project settings win. Requests never substitute another model
or drop/lower effort. Proposal receipts and new provenance bind requested effort
and actual returned model to the immutable request snapshot.

The upper-right dot/text now verifies actual API authentication with bounded
GET /v1/models. Checking/missing/auth/permission/rate/network/invalid/stale states
are distinct; green means only fresh valid HTTP 200 authentication/reachability,
not selected-model generation, credits, quota or billing. Requests coalesce/cache
for 60 seconds (3-second Retry cooldown), with 8-second deadline and response bounds.
The browser checks once on app load, reuses state across routes, and expires green
without polling. No credential/raw provider error/catalog is exposed to React.
Workspace status space is reserved; Home uses existing header/sky space.

Actual verification on 2026-10-20:

- Final `./sigma test`: all lifecycle/create/settings/model-connection/tracking/
  proposal/strategy/edit/remove/API/CLI/launcher scenarios passed. Ruff check/format
  (20 files), Pyright (0 errors), frontend typecheck and production build passed.
  Existing non-failing Starlette TestClient deprecation notice remains.
- `tests/project_settings.py`: explicit model/High creation, v1–v5 no-write
  defaults, no-op, exact backups, both mode directions, stable identity/location/
  archived research/order, failed writes, stale editor races, independent strategy
  changes, strict corrupt audit rejection, and API/CLI update/conflict checks.
  Empty/unknown models and unsupported efforts are rejected without creating files.
- `tests/model_connection.py`: valid curated discovery (unreviewed models do
  not escape), coalescing eight calls into one, cache/TTL/Retry, zero accessible
  choices, missing setup, 401, 403, 429, 500, redirect, malformed/oversized responses,
  network failure and timeout. Controlled Responses fixture verifies saved model
  plus real `reasoning.effort` (including High and Extra high across scenarios),
  strict schema, 25,000-token bound, no pre-acceptance mutation, concurrent settings
  snapshot/provenance, unavailable model/no fallback and offline metadata edits.
- `uv run --with playwright python browser_checks/settings.py`: real Chrome passed
  shared field order/Create/Edit headers, Sol/High, pencil keyboard opening and
  return focus, no-op/cancel, failed create/update retry, duplicate synchronous
  submits/busy/Escape guard, both mode/model/effort changes, reload, UUID/path/audit
  retention, stale edits preserving unsaved text, explicit unsupported-effort
  correction, unavailable-model retention and actual offline metadata save.
  Status checks cover initial Checking/no green, authenticated fixture green,
  key/permission/rate/offline/unconfigured alternatives, stale success, safe details
  and Retry access. No JavaScript errors. Screenshots at 1672/768/390/320px are
  `/tmp/sigma-a8-create-*.png`, `-edit-*.png`, and `-status-*-320.png`.
- Real 320px Chrome stress check: unbroken 200-character title, long visible problem
  and 20,000-character form problem fit without horizontal overflow; Escape keeps
  document bytes and returns focus. Screenshot: `/tmp/sigma-a8-long-edit-320.png`.
- `uv run --with playwright python browser_checks/strategies.py` and
  `uv run python browser_checks/http_cancel.py`: A7 manual/edit/remove, stage,
  keyboard/mouse/CDP touch reorder/drop/cancel, rollback/reload, AI draft review/
  human acceptance/cancellation and actual HTTP disconnect/slot release all pass.
  Tests use explicitly identified no-network provider fixtures and temporary
  projects, not physical-device or live API-account claims.
- `uv run ruff check src tests browser_checks` and corresponding format check
  passed (24 files). Browser fixture and A8 checks are source-controlled and
  documented separately from the standard suite.
- Compared current UI with a temporary checkout of actual A7 `2a8f90b`, serving the
  same approved PNG. `/tmp/sigma-a8-compare.py` with Playwright/Pillow confirmed Home
  pixels outside the requested header/sky status area identical at 1672×941,
  768×1024, 390×844 and 320×844. The initial baseline captured before Vite served its
  generated public image was rejected; comparisons awaited decoded art and visible
  UI. Strategy list at desktop is pixel-identical; tablet/mobile lists have the
  same dimensions/composition (up to one screenshot crop pixel), visually reviewed.
  Header height changes alter gradient/capture phase, not row styling. Artifacts:
  `/tmp/sigma-a8-home-reference-*.png`, `-home-current-*.png`, and
  `-strategies-reference/current-*.png`. Temporary reference server/worktree removed.
- Fresh dev startup test removed only the generated public Home copy and restarted
  `./sigma ui`: new config-evaluation copy served HTTP 200 `image/png` on first
  launch with exact canonical bytes. Fixes the older late buildStart copy, which
  could miss Vite's initial public-file scan. Human copying is not required.
- RH document, canonical Home PNG and workspace logo hashes match the pre-A8
  baseline; existing untracked `models.json` also stayed byte-identical and is not
  committed or used as authentication proof. No image generation or A4.1 animation.
  Test API fixture server is stopped; normal UI runs with default project root.

Limits: no live OpenAI generation/billing/quality check was performed; all provider
integration uses controlled HTTP fixtures. Normal server currently reports Not
configured, never fake green. Configure server API enablement/key and restart to
check real authentication; an explicit user request is needed for billable
proposals. Higher thinking may hit the unchanged 60-second deadline or 25,000-token
budget; failures never downgrade or retry automatically. API/catalog changes need
deliberate review. Past missing effort remains unknown. No cost accounting,
per-strategy settings, agent work or Close-time save/confirmation is introduced.

## Current boundaries

No live agents, scheduler, evaluator, generated reports, forks, paid calls, or hosting. Local POSIX storage limitations and migration behavior are in [DECISIONS](DECISIONS.md). Run instructions are in [Getting Started](GETTING-STARTED.md).

## Project dialog terminology correction

Per user request, the creation dialog heading and submit button now say “New Project” to match Home. Edit Project / Save Changes are unchanged. Updated browser-check expectations. Validation: `./sigma test` passed (scenarios, API/CLI, Ruff, Pyright, frontend typecheck/build); real Chrome confirmed both dialog labels.


## A8.1 — automatic local configuration and safe UI replacement

Implemented the one-command startup/restart fix independently of A9. `./sigma ui`
loads checkout-root `.env` with pinned python-dotenv 1.2.1 before spawning the API;
quoted `export` assignments work without sourcing. Environment values win. The
whole file is validated before mutation; absent is normal, malformed/unreadable
files get safe actionable diagnostics without raw contents. CLI project commands
and the standalone backend factory share the loader. Setup/test avoid loading it.
AI enablement and explicit billed-generation consent are preserved.

A private owned 0700 state directory, no-follow launch lock and canonical
path/device/inode identity handshake coordinate same-checkout replacement.
Shutdown is requested through a private Unix socket; the old supervisor confirms
both server guardians have exited before the replacement starts. Pipe guardians
own the actual child groups and clean up after supervisor crashes as well as
normal stops. No recorded PID or occupied port authorizes a signal. Stale refused
owned sockets recover automatically. Unverified state, other checkouts and unrelated
listeners cause a named safe conflict. Ports remain fixed at 8000/5173; no dynamic
fallback or relaxed host/origin checks. Readiness verifies the per-launch public
instance ID at the API and through Vite before announcing the URL. No project/UI
artwork or Close behavior changed. README, Getting Started, decisions and a
placeholder-only `.env.example` document the behavior.

Actual verification:

- `./sigma test` passed: all existing research lifecycle/settings/strategy/provider
  scenarios, API/CLI checks, launcher failure/interrupt checks, new dotenv and
  ownership scenarios, Ruff check/format (27 files), Pyright (zero errors),
  frontend TypeScript check and production build. Existing non-failing Starlette
  TestClient deprecation notice remains.
- `tests/local_config.py`: missing file, quoted export/single/plain/empty
  values, comments, explicit environment precedence (including disabled AI),
  literal shell/variable syntax without execution/expansion, no key output,
  atomic malformed-file rejection, UTF-8 and unreadable-file safe diagnostics.
- `tests/instance_ownership.py`: canonical alias and changing symlink target,
  different checkout IDs, directory permissions/symlink refusal, non-socket state
  preservation, refused stale-socket recovery, live wrong-identity refusal without
  sending shutdown or removing its endpoint, and no-follow lock protection.
- `uv run --with playwright python tests/ui_lifecycle.py` passed against
  disposable real checkouts and explicit no-network provider fixtures. Started
  actual `./sigma ui` from another working directory; a fresh second invocation
  loaded updated `.env`, verified the new model availability, and let the old
  supervisor exit zero with both old child trees gone. API and frontend proxy,
  allowed/forbidden origins, Chrome's authenticated-fixture connection status
  and New Project dialog passed. Ctrl+C and SIGTERM cleaned up; actual supervisor
  SIGKILL left a stale socket and pipe guardians recovered automatically. Rapid
  concurrent launches serialized to one working owner. A different checkout and
  unrelated listeners on each default port survived safe refusal. Fixture logs
  contained no key; provider transport allowed only GET /v1/models. Source project
  file hashes and temporary research sentinel stayed unchanged.
- Also exercised actual normal-checkout `./sigma ui` followed by `./sigma ui`:
  the second invocation printed the restart message and became ready while the
  old command exited cleanly. Normal launcher is left running after verification.

Limits: real-process/Chrome checks were run on macOS, not Linux or a physical
browser device. The opt-in lifecycle check requires free default ports and Chrome
at its documented macOS location. An older launcher without the ownership protocol
cannot be safely replaced automatically; its own controls must stop it once.
Same-user malicious processes are outside the private-directory trust boundary.
No paid generation or live provider billing/quality verification was performed.
Existing untracked `models.json`, local `.env`, project research and artwork are
not committed or rewritten by this change.

## A8.2 — ChatGPT connection and explicit billing modes

Implemented documented local OSS Sign in with ChatGPT. The repository's public
visibility and Apache license were checked, and current official SIWC discovery,
registration, session, token, model/inference, preview and UI documentation was
read before implementation. Exact sources and security decisions are in
[asn8.2-security.md](asn8.2-security.md).

Home/workspace reuse the small top-right account control: Connect AI, official
Continue with ChatGPT button, connected/account/usage/reconnect states, account
switch/add, disconnect, and explicit advanced API-key billing. Manual work needs
no connection, key, .env or enable flag. A present key never selects billing;
SIGMA_AI_ENABLED no longer gates runtime behavior. Plan failures never use a key.

Backend-owned PKCE/state/nonce and real loopback callback validate signed RS256
OIDC identity, issued client/account binding, scopes and expiration. Stable host
and separate registrations persist in private owner-only application storage,
never projects, Git, Vite or React. Refresh rotation serializes across processes;
terminal errors retain registration for reconnect. Invalid-grant code retries
retain the issued client transiently. Disconnect reports unconfirmed revocation
honestly. Account storage failures keep manual model defaults available.

On-demand sign-in retains seed/draft and resumes one initiating generation,
checking project/account bindings and cancellation. Header sign-in does not
generate. Plan requests use the required bounded SSE Responses contract and
preview-compatible body; API-key requests keep their existing contract. Both
retain strict proposal validation, returned-model/effort receipts, explicit human
Save Strategy and schema v6. No recurring consent checkbox or automatic saving.
One-time welcome is informational. Existing SIGMA artwork is unchanged; the
sign-in mark is the unmodified official asset. A9 remains separate.

Actual verification:

- `./sigma test` passed all scenarios, API/CLI checks, Ruff, Pyright (zero errors),
  frontend typecheck and production build. Existing non-failing TestClient
  deprecation notice remains. Final frontend build and Ruff check/format over
  `src`, `tests`, and `browser_checks` passed (39 Python files); final Pyright passed.
- `tests/chatgpt.py`: real loopback callback and generated RSA-signed OIDC
  fixtures verify PKCE/exact code exchange, stable host/issued client, nonce,
  state, issuer/audience/signature/expiry/subject/client rejection, missing tokens,
  duplicate callback race, cancellation/decline, discovery endpoint validation,
  scope denial/enablement, distinct same-email registrations, both catalog shapes,
  strict completed SSE and malformed/out-of-order/incomplete/failed/oversized
  errors, explicit API mode without flag, no billing fallback or sign-in writes,
  project/account binding, terminal refresh and confirmed/unconfirmed revoke.
  Added invalid-grant retry and unreadable-store/manual-default checks passed.
- `tests/chatgpt_restart.py`: two fresh real processes contending for an
  expired rotating session performed exactly one refresh, retained host/account/
  client identity, and atomically stored the replacement with 0600 permissions.
- Real Chrome `browser_checks/chatgpt.py` passed manual project/strategy creation
  while disconnected, cancelled/declined login preserving a nonempty seed, signed
  simulated authorization resuming exactly one SSE generation, no pre-acceptance
  project write, one explicit human save, actual returned-model provenance,
  welcome once/reload without generation, account menu/switch, explicit API billing,
  expiry/offline/permission/usage-limit states, keyboard focus and no JS errors.
  Responsive screenshots at 1280x720, 1440x900, 390x844 and 320x844 are under
  `/tmp/sigma-a82-*.png`; desktop and mobile menu captures were visually inspected.
- Existing `browser_checks/settings.py`, `browser_checks/strategies.py`, and
  `browser_checks/http_cancel.py` passed with explicit no-network API-key fixtures.
  Settings CRUD/conflicts/offline preservation, manual strategy CRUD/stages,
  mouse/keyboard/touch ordering, draft review/acceptance and actual HTTP
  disconnection/cancellation all remain working. Fixture startup now explicitly
  selects dummy key billing; production never does so automatically.
- `tests/ui_lifecycle.py` passed real fresh-shell restart with updated .env,
  explicit persisted key-mode selection, proxy/origin routing, old owner/children
  gone, Ctrl+C/SIGTERM, hard-crash pipe cleanup/stale recovery, rapid launches,
  different checkout and unrelated listener refusal, and unchanged research.
- Normal launcher was restarted; real Chrome confirmed Home/account control and
  official sign-in asset without starting live OAuth or generation.

Limits: all OAuth and inference verification uses controlled fixtures. Live
sign-in, account/workspace eligibility, structured-output admission, plan capacity
and billing/quality have not been verified or consumed. Live testing requires an
explicit user request. Private files protect against other OS accounts, not code
already running as this account; a crash between remote token rotation and local
publication can require reconnect. Tested on macOS/Chrome, not physical devices
or Linux. A9's Recent Projects and dialog-header correction are not implemented
here. Local .env, existing research, canonical artwork and untracked models.json
are not committed or rewritten.

## A9 — four recents, included exercise and visible dialog controls

Implemented a private application-level four-item LRU keyed by existing project
UUID. Successful create/open services and explicit API/CLI init record canonical
path and actual access time; inspect, edits and Close do not reorder or write the
index. Home reads fresh titles/minimal metadata, opens actual projects, disables
unavailable entries and can forget a pointer without deleting research. Creation/
recent navigation passes its already-loaded view into the workspace, avoiding an
incidental second Open write. Index state uses an owned 0700 XDG/per-user directory,
0600 no-follow index/lock, multiprocess serialization and atomic fsynced writes.
Index failure warns separately from an already successful research operation.

The supplied Mathematical template is installed byte-for-byte with validated v5
schema/UUID/history and exclusive no-replace publication. Existing same-UUID
research is preserved; other occupants/symlinks report a conflict. Per-root
bootstrap facts prevent reinstatement after deletion/forgetting/eviction and do
not displace four real accesses. Initial inclusion says Included example and has
no invented last-opened time. Opening shows the three real Draft strategies;
normal edits evolve the copy independently of the unchanged Git template.

New/Edit Project now use a title/action header (Create or Save Changes, Cancel)
and one scrolling body in one native form. The header remains visible at laptop
and mobile sizes; busy buttons/Escape, native validation, duplicate guards,
errors/retry and focus restoration remain operational. No artwork redesign or
provider behavior change. Future Markdown/LaTeX transcript rendering is documented
in agent-output-design.md, without implementing execution or hidden reasoning.
Independent mathematical verification is outside the active project template.

Actual verification:

- `./sigma test` passed all existing and new scenarios, API/CLI checks, Ruff,
  Pyright (zero errors), frontend typecheck and production build. Existing
  non-failing TestClient deprecation notice remains. Final targeted recents
  scenarios, Ruff check/format over `src`, `tests`, and `browser_checks` (43 files) and
  Pyright passed after the state-path guard and extra failure cases.
- `tests/recents.py`: exact first/second bootstrap, strict seed/event/strategy
  identity, five creates/four-entry eviction, actual API/CLI accesses, repeated
  opens, Close/inspect/title-refresh byte immutability, renamed/moved/corrupt
  projects, forget/no reseed, concurrent real processes/threads and parallel
  bootstrap. Full genuine lists survive inclusion; bad templates, publication
  failure, edited existing seed, other-project collisions, symlinks, root switches,
  corrupt index and failed index replacement preserve research. State permissions
  and refusal of checkout/project-package state locations are checked. The two
  expected index-failure warnings demonstrate secondary-error handling.
- `tests/example_math.py`: independent residue/adjacency DP cross-checked by
  exhaustive enumeration through n=12 gives a_12=128; recurrence checked through
  n=120. Exact arithmetic in Z[omega] verifies three-step traces, determinant and
  Cayley–Hamilton identities in all phases. The analytic root-of-unity recurrence
  and density proof is in docs/example-math-verification.md; no proof/answer was
  inserted into the unproved seed and no agent/Lean activity is claimed.
- Real Chrome `browser_checks/recents.py` passed actual example opening with three
  Draft strategies, first inclusion versus actual access, five UI creations,
  eviction, Open/recent click UUID deduplication, corrupt/unavailable/forget flow,
  unchanged template and zero JavaScript errors. Measured header button bounds
  at 1280x720, 1440x900, 390x844 and 320x700 for Create and Edit before/after body
  scroll, long problem/help/localized labels, save spinner, Escape/duplicate guard,
  failure with retained text and successful retry. Confirmed no second post-create
  Open request. Home also checked at 768x1024. Captures: /tmp/sigma-a9-*.png;
  desktop Home and 320px Edit were visually inspected.
- Existing real Chrome `browser_checks/settings.py` passed shared form defaults,
  field/pair validation, offline retention, create/edit/no-op/conflict/error/retry,
  UUID/history preservation, keyboard/focus, responsive and connection-state
  checks. Fixtures use isolated app/credential/project roots and no live provider.
- Normal `./sigma ui` safely replaced its prior instance and became ready, with
  the included example installed in the configured root. Canonical artwork and
  source example bytes remain unchanged; no tracked live research was added.

Limits: local cooperative POSIX locking and same-OS-account trust boundary remain.
Research publication and secondary-index updates are not one cross-file atomic
transaction; a failed index update can be retried by a later explicit Open without
resubmitting creation. A hard crash can leave an empty reserved example directory;
existing directories are inspected, never silently reset. Up to four full project
files are validated server-side to refresh metadata, while the browser receives
only the small index view. Chrome checks used macOS emulation, not physical
phones or Linux. No paid calls, autonomous agents or transcript renderer. Existing
untracked models.json and local .env remain unmodified and uncommitted.

## A8.2.1 — quiet, current connection status

AI connection health now refreshes centrally in `AIProvider`, once per app rather
than once per header. For the current 60-second check TTL, a visible connected
ChatGPT or API-key account is checked at 48 seconds. Hidden tabs pause scheduled
requests and resume with one due check. Background checks leave the header label
steady; manual Retry shows progress only in the account popover. Repeated network
or provider-unavailable failures show a neutral actionable warning after a
transport failure, retain a known provider-specific unavailable label, and retry
with visible-only 30/60/120-second backoff capped at five minutes. A successful
check or deliberate account/mode change resets backoff. No-account states are not
polled. Old in-flight results are discarded after sign-in, account/mode changes
or Disconnect. The A8.2 one-time welcome acknowledgment remains unchanged.

Actual verification:

- `./sigma test` passed all scenarios, API/CLI checks, Ruff, Pyright (zero errors),
  frontend typecheck and production build. The existing non-failing Starlette
  TestClient deprecation notice remains.
- Real Chrome `browser_checks/connection_refresh.py` passed with a controlled
  clock and mocked browser fetches: repeated 48-second refresh cycles, no header
  flash while background/manual checks are held open, hidden-tab pause and one refresh on
  return after expiry, transient failure warning and 30-second retry, manual
  recovery, stale successful response rejected after Disconnect, and welcome
  acknowledgment only once across multiple checks and reload. No provider calls.
- Real Chrome `browser_checks/chatgpt.py` passed against the signed local OAuth
  fixture: disconnected manual work, cancelled/declined and successful sign-in,
  one explicit strategy save, account controls, separately billed API mode,
  outage/limit/permission/reconnect states, and responsive 1280/1440/390/320px
  layouts. No live sign-in or billable inference. Final frontend build/typecheck,
  Ruff check/format (45 Python files), and Pyright all passed after changes.

Limits: the verified status remains a bounded non-generating model-catalog
authentication/reachability check; it does not establish inference entitlement,
credits, quota or billing. Browser refresh behavior was controlled-clock tested;
no live provider state or physical mobile device was used.

## Home copper artwork update

Home now uses the approved copper background and static slogan artwork. Vite
copies both source PNGs byte-for-byte from `assets/` into `frontend/public/`;
the originals remain unchanged. The slogan is blended with `screen` and feathered
at its edges so its dark canvas does not form a hard rectangle. Home actions stay
below the raised Σ/SIGMA mark, and the connection control remains in the upper
right. The responsive crop keeps the background image's aspect ratio.

Actual verification:

- Real Chrome screenshots at 1440x900, 390x844 and 320x700 were visually
  inspected (`/tmp/sigma-verified-*.png`). The connection control clears the
  slogan and Σ at each size, the actions remain below the artwork, and no
  horizontal overflow was measured. This was browser emulation, not physical
  mobile hardware.
- `npm run build` passed TypeScript checking and the Vite production build.
- `./sigma test` passed lifecycle and project creation scenarios, then stopped
  in `tests/recents.py:204`. Its bad-template check patches
  `sigma.recents.TEMPLATE`, but `bootstrap_example()` calls `_install(root)` whose
  default `template=TEMPLATE` was bound when the function was defined, so the
  fixture patch is not observed and its assertion fails. This failure occurs in
  existing scenario/application code, unrelated to the Home artwork change; the
  later checks in that command did not run.

## A11 — copper Home controls and sample catalog

Home now offers Samples and Recent Projects tabs, with Samples selected on
entry per the later UI request. The catalog discovers every valid shipped
investigation and places the Jesus example last. Selecting a Sample row opens the
project directly with no dialog, creating an independent working copy with its
own identity and a distinct path. The original source remains byte-for-byte
unchanged, and opened copies appear in Recents. Existing automatic sample recent
entries are removed from the index on read; project directories and research
files are left untouched. The Home buttons use matching navy/copper
resting styles, and both hover with the selected tab's copper gradient. Dialogs,
lists, connection status and Close Project use coordinated copper styling.

Actual verification:

- `./sigma test` passed all scenarios and API/CLI checks, Ruff check/format,
  Pyright (zero errors), frontend typecheck, and production build. The existing
  non-failing Starlette TestClient deprecation notice remains.
- Real Chrome `browser_checks/recents.py` passed tab keyboard navigation, exact
  button rest/hover style comparisons, stable direct sample opens, Recent/Forget and
  unavailable path behavior, source immutability, no page errors, and 1280px,
  390px and 320px responsive layout checks. The 1280px Home screenshot was
  visually inspected; the controls do not cover the approved artwork. The New
  Project dialog had no internal vertical scroll at 1280x800. Screenshots are
  under `/tmp/sigma-a11-*.png`.

Limits: browser sizes were Chrome emulation, not physical devices. The first
selection creates one managed installation because the checked-in catalog paths
are not `.sigma` packages; this is a stable project, not a new copy on each open.

Follow-up: the "Open a Project" heading retained a gold color from the older Home
stylesheet. It now uses the exact resting copper text color of Open/New Project.
Real Chrome checked the heading against both buttons' computed colors and the
desktop screenshot was visually inspected. `./sigma test` and the full A11 Chrome
check passed again after the change.

The direct-open correction removed the working-copy dialog and endpoint. Real
Chrome verified immediate opens, the same project path on repeat selections,
retained edits, exclusion from Recents, source-file immutability, and desktop and
mobile layouts. `./sigma test` passed the updated scenarios, API/CLI, Ruff,
Pyright, frontend typecheck and production build after the correction.

## Project header artwork

The project-page header now uses the approved `assets/sigma-project-header.png`
through an identical copy in `frontend/public/`. It is displayed as a full image
with proportional sizing at desktop and narrow widths. The Home page and its
artwork are unchanged.

Actual verification: `npm --prefix frontend run build` passed TypeScript and the
Vite production build. Byte comparisons confirmed the source, public and built
PNG files are identical. Real Chrome `browser_checks/recents.py` passed, and its
1280px and 390px project-page screenshots were visually inspected; the logo and
copper/blue wire effects are visible without cropping or horizontal overflow.

## A13 — project header and shared copper controls

The workspace header now places the complete project name immediately to the
right of the approved SIGMA artwork, replacing only the redundant workspace
tagline. It wraps instead of clipping or hiding below 1100px. The unchanged
`ConnectionStatus` component now uses one shared pill style on Home and in the
workspace; Open/New Project and Close project use one shared copper button style
with matching resting, hover, disabled and focus states. Home artwork, workspace
navigation and project content remain unchanged.

Actual verification:

- `./sigma test` passed all scenarios and API/CLI checks, Ruff check/format,
  Pyright (zero errors), frontend typecheck and production build. The existing
  non-failing Starlette TestClient deprecation notice remains.
- Real Chrome `browser_checks/header.py` passed full long-name display and no
  overflow at 1280, 1100, 700, 390 and 320px; checked artwork dimensions,
  workspace-only tagline removal, identical Home/Close button and connection
  pill styles, live status/dot, disclosure, keyboard focus and Close. Its five
  screenshots under `/tmp/sigma-a13-header-*.png` were inspected at desktop,
  1100px, 700px and mobile widths.
- Real Chrome `browser_checks/recents.py` passed Home and sample/recent regressions
  after the shared CSS change. The 390px Home and project screenshots were
  inspected, with the approved Home artwork and project navigation intact.

## Project header placement follow-up

The approved project artwork now begins at the viewport's top-left corner. Its
unused dark lower area no longer reserves extra vertical space above the project
workspace. The project title, header controls and workspace navigation are
layered above the artwork so they remain legible and clickable. The image file
and its aspect ratio are unchanged.

Actual verification: `./sigma test` passed all scenarios, API/CLI checks, Ruff,
Pyright, frontend typecheck and production build. Real Chrome
`browser_checks/header.py` passed at 1280, 1100, 700, 390 and 320px, including
artwork top-left placement, aspect ratio, control interactions and no horizontal
overflow. Desktop, tablet and mobile screenshots were visually inspected.

The header display now clips only the blank bottom quarter of the artwork. The
top 75%, including the complete SIGMA lettering and copper/blue wires, remains
visible. The source/public image files are untouched, and the clipped display
ends above workspace navigation. `./sigma test` and real Chrome header checks
passed again at all five viewport widths; desktop and mobile screenshots were
visually inspected.

## Project introduction and Strategies controls follow-up

The upper project pane gives the title and description the full available width.
It scrolls vertically when the description grows beyond the pane's bounded
height. New Strategy now sits to the right of the Strategies heading below the
divider and matches the Home action's 50px button height and padding. Strategy
expand/collapse and the split action use standard chevrons instead of text
symbols. The New Strategy action no longer has a leading plus.

Actual verification: `./sigma test` passed scenarios, API/CLI checks, Ruff,
Pyright, frontend typecheck and production build. Real Chrome
`browser_checks/strategies.py` passed creation, edit/remove, reordering and AI
flows after checking button placement, long-description scrolling and no
horizontal overflow at desktop and 390px. Desktop/mobile screenshots were
visually inspected. `browser_checks/header.py` passed at five widths.

## UI browser launch follow-up

`./sigma ui` now opens `http://127.0.0.1:5173` in the default browser after
both the API and Vite frontend report ready. If the browser cannot open, the
servers continue running and the terminal repeats the URL for manual use.
The browser is not opened during failed startup. The tooling scenario checks
the one-time launch and failure paths. Actual verification: `./sigma test`
passed scenarios, API/CLI checks, Ruff, Pyright, frontend typecheck and build.
The ready message also names the FastAPI API server at `127.0.0.1:8000` and
the Vite UI server at `127.0.0.1:5173`; the tooling scenario asserts both lines.

Home's content wrapper now has no left padding, so approved artwork starts at
the viewport edge. The Open Project heading, action buttons and sample/recent
catalog share a deliberate left inset. Real Chrome checks at 1280px and 390px
confirmed their positions and no horizontal overflow; screenshots were inspected.

## A14 — bounded agentic Generate Strategy (2026-10-21)

Generate with AI now uses a streamed, role-isolated Explore → Challenge → Decide
coordinator. A skeptical review can trigger targeted revision, a second
mechanism, or a no-viable-strategy stop. Each run is limited to six model calls,
two candidate attempts and 120 seconds; each provider call has a 35-second
deadline. The selected project model, thinking level and connected billing mode
remain bound throughout. Full active and removed strategy approaches are sent;
oversized context stops the run rather than truncating it. Progress events are
typed, sequential public summaries, and the browser rejects malformed or
unterminated streams. The draft stays editable and unsaved until Save strategy
records human acceptance and signed model provenance. No research tools or
literature searches run in this slice.

The project sidebar now collapses to an accessible icon rail on desktop. The
description/Strategies divider can be dragged or adjusted by keyboard, and its
default position sits close below the description. The project description
retains bounded vertical scrolling for long text; narrow layouts retain the
horizontal navigation row. Home and approved raster artwork were unchanged.

Actual verification on 2026-10-21:

- `./sigma test` passed all scenarios, API/CLI checks, Ruff, Pyright (zero
  errors), frontend typecheck and production build. `tests/agentic.py`
  covers sample zero-pool generation, explicit acceptance/reopen, later-strategy
  context, duplicate retry, skeptical revision, no-proposal and six-call stops,
  malformed/refused output, binding changes, timeouts, duplicate-run guard,
  cancellation, ChatGPT-plan streaming and ASGI disconnect, all with mocked
  transport and no paid calls.
- Real Chrome `browser_checks/agentic.py` passed against a fresh isolated
  provider fixture: zero strategy rows, chronological progress and critique,
  unsaved cancellation, explicit save/reopen, a second distinct mechanism,
  in-flight cancellation and source immutability. Desktop and 390px review
  screenshots were visually inspected; the dialog fits and scrolls.
- Real Chrome `browser_checks/strategies.py` passed sidebar collapse/expand,
  divider placement and drag/keyboard resizing, long-description scrolling,
  320px/390px layouts and strategy create/edit/remove/reorder/AI regressions.
  The collapsed desktop screenshot was visually inspected; no JavaScript errors
  or page-level horizontal overflow occurred.

The browser fixture's provider output is deterministic and does not demonstrate
live-model research quality, entitlement or account usage. Playwright's API
proxy can outlive a locally aborted request briefly; the direct ASGI disconnect
scenario verifies server-side cancellation and run-gate release.

## A15 — basic Generate Strategy path (2026-10-21)

The active A15 scope is the single-request Generate Strategy assignment. The
first broken integration was in the visible UI: it called the A14 streamed
agentic endpoint, while the already-supported bounded proposal service was
exposed separately and had its own request, validation, receipt and save tests.
The UI now calls that existing service directly. It presents one editable,
unsaved proposal; Save remains the only persistence action. Pending and cancel
states are visible, and the copy no longer promises independent review. A14's
agentic service and tests remain intact for the deferred A16 extension; the
original A15 text-representations work remains separately implemented.

Generation rejects an in-flight result if the connected account or billing
mode, project identity, selected model/thinking effort, or full research and
strategy context changed while the provider request was running. The existing
API-key and ChatGPT-plan response adapters, strict structured validation,
response/context limits, concurrency guard, and signed project/model provenance
remain in use. Failed requests and local cancellation leave research untouched
and keep the draft composer recoverable.

Actual verification on 2026-10-21:

- `./sigma test`: all executable scenarios and API/CLI checks passed; Ruff check
  and format passed; Pyright reported zero errors; frontend typecheck and Vite
  production build passed. Provider and agent tests use deterministic mocked
  transports; no paid provider call was made.
- `uv run --with playwright python browser_checks/a15_generate.py`: real Chrome
  passed the empty counting-project/empty-seed flow, exactly one bounded request
  per generation, substantive editable unsaved draft, cancel without mutation,
  simulated HTTP 500 with one dismissible request toast and inline recovery,
  in-flight cancellation without mutation, explicit edited save/reopen, and a
  different proposal with existing strategy context. The source fixture stayed
  byte-identical. Screenshots at 1440×900 and 390×844 were inspected; neither
  has horizontal overflow. These checks use the isolated mock provider on port
  8002, not live OpenAI.
- `tests/proposals.py` now also exercises the proposals API endpoint and verifies
  that an account change during a provider request discards the result without
  changing project state. `tests/model_connection.py` verifies changed-model
  rejection during the request.

## Project header spacing follow-up (2026-10-21)

The project header now displays the upper 64% of its unchanged artwork, retaining
the complete raised SIGMA lettering and visible copper/blue wires while removing
the remaining dark area beneath them. Its bottom padding is zero, so the project
workspace begins at about 125px on desktop instead of about 166px. Header
controls and the project title stay above the content without overlap.

Actual verification: `./sigma test` passed all scenarios, API/CLI checks,
Ruff, Pyright and frontend typecheck/build. Real Chrome `browser_checks/header.py`
passed at 1280, 1100, 700, 390 and 320px, and `browser_checks/strategies.py`
passed the project layout and strategy regressions. Desktop and 390px project
screenshots were visually inspected; no horizontal overflow or JavaScript errors
were observed. The public PNG and source artwork were not changed.

## A15 — Plain, Markdown and Rendered project text (2026-10-21)

The research problem and expanded strategy approaches now have a three-view
control. Plain and Markdown are separate durable bodies; Rendered is a local
read-only Markdown/KaTeX preview. Selecting a missing or stale view now starts
its conversion automatically per the later user request; failures retain the
source and offer Retry. The UI reports AI attribution, working/cancellation,
conversion errors and stale copies. A direct in-place description or title
edit requires Save; Escape cancels without writing. The project View selector
sits at the lower-right of the description pane above its draggable divider.
The project title appears once in the header, beside a back arrow; clicking it
edits the title in place. Other options remain in Project Settings. Home shows
a Current Project shortcut above “Switch to a new project,” validated through
the read-only inspect endpoint. The sidebar's collapse preference survives
leaving and reopening a project. Sample source fixtures and approved artwork
remain unchanged.

A versioned portable `text-representations.json` companion stores format history
and source-digest keyed conversions without rewriting legacy project documents
on read or conversion. Both conversion directions use the selected account,
model and Thinking settings through one bounded, cancellable service. The
current source is checked again under the project lock before publishing a
result. Strategy generation receives the current authoritative text and its
format. No live paid conversion was made for verification.

Actual verification: `./sigma test` passed all scenarios, API/CLI checks, Ruff,
Pyright (zero errors), frontend typecheck and production build. The A15 offline
scenario passed mock-provider conversion in both directions, v1–v6 read-only
migration, sample immutability, cache reuse, stale edits/conflicts, cancellation,
ASGI disconnect, malformed/truncated output, account/model availability and
ChatGPT-plan streaming. Real Chrome `browser_checks/text_views.py` passed
literal and rendered inline/display math, working/error/stale states,
in-place title/description editing and safe rendering, zero provider requests on cached switches,
Current Project reopen and desktop/390px layouts. Real Chrome
`browser_checks/header.py` passed the back-arrow header at five widths;
`browser_checks/strategies.py` passed layout, divider, strategy CRUD and AI
regressions and sidebar persistence. Real Chrome `browser_checks/settings.py`
passed in-place title/description editing, separate project settings, retained
model selection and conflict/error handling; `browser_checks/recents.py`
passed sample/recent Home navigation. Desktop/mobile screenshots were visually inspected and no
horizontal viewport overflow or page errors occurred. The renderer can display
an AI conversion faithfully but cannot verify mathematical equivalence; users
must review derived text before relying on it.


## UI recovery and explicit shutdown (2026-10-21, awaiting local verification)

The `./sigma ui` launcher now records the exact owner PID, process birth time,
user, command and checkout identity in a private owner file. Restart recognizes a
verified suspended launcher, sends SIGCONT so it can serve its control endpoint,
and requests a clean shutdown. If a verified owner remains suspended while
holding the startup lock, the launcher escalates after a bounded wait. An
unresponsive authenticated owner can receive SIGTERM then SIGKILL after a
bounded grace period. Unrelated port listeners, changed PIDs and unverifiable
control records are never signalled. Startup reports its stages rather than
waiting silently.

The new `./sigma shutdown` command uses the same checkout-specific control
mechanism without starting servers. Offline ownership and CLI-shutdown scenarios
and opt-in real-process suspended-launcher/shutdown lifecycle checks were added.
These changes were committed via GitHub and **have not been locally executed or
verified yet**; run `./sigma test` and the opt-in `tests/ui_lifecycle.py`
before treating the behavior as verified.

## Legacy suspended UI startup recovery (2026-10-21, pending local verification)

A launch or `shutdown` previously could block behind an older suspended SIGMA
launcher that predated owner registration. When a startup lock is held without
an owner record, the replacement path now queries the OS for the actual lock
holder and checks the exact checkout CLI path, user identity and process birth
before resuming it. If the same verified process retains the lock after a grace
period, termination escalates with identity rechecks. It never kills a process
merely for using ports 8000/5173. An offline regression covers legacy lock
inspection, suspension recovery and rejection of unrelated processes. The
change is committed but awaits macOS startup/restart/shutdown testing.

## Multiple suspended launchers (2026-10-21, pending macOS verification)

An initial legacy recovery attempt rejected multiple processes with open file
descriptors for the checkout's startup lock as "ambiguous", blocking both `ui`
and `shutdown`. Recovery now enumerates and verifies all reported holders
for the same checkout and OS user, resumes all verified suspended SIGMA UI
launchers, and escalates only against verified process identities still holding
the lock after the grace period. If any holder is unverified, no signals are sent.
The offline test now includes multiple holders and an unrelated-process negative
control. This is committed, but it has not been exercised on the user's Mac.

## Verified orphan-server cleanup (2026-10-21, awaiting macOS confirmation)

After suspended-launcher recovery, the UI can still be blocked by an orphaned
FastAPI or Vite listener on ports 8000/5173. The new `sigma.ui_orphans`
service examines a listening PID's OS user, process birth/command, working
directory, expected SIGMA server arguments, and (for FastAPI) its nonempty
`/api/ui-instance` identity. Only a matching same-checkout listener can be
stopped, first with SIGTERM and then (after a bounded grace period and
identity re-verification) SIGKILL. Unknown or unrelated listeners are untouched.

Both `./sigma shutdown` and `./sigma ui` now invoke that cleanup after
serializing through the private instance lock. The mock-provider-free offline
`tests/ui_orphans.py` regression covers owned servers, unrelated
listeners, changed process identity and SIGKILL escalation, and runs in
`./sigma test`. The isolated tests passed in the assistant's Python
environment, but end-to-end behavior on the user's macOS machine is not yet
verified.

## Samples terminology and source directory rename (2026-10-21)

The Home catalog now calls the shipped examples **Samples**. Samples is the
first tab and remains selected by default; Recent follows it. The Python
catalog module and public handlers were renamed to `sigma.samples` and
`/api/projects/samples`, including the open route and request field. The Home
component, CSS classes, browser checks, scenario filenames and documentation
use the same terminology. The checked-in project JSON and identities remain
unchanged; their containing directory moved from `examples/` to `samples/`.
Runtime discovery now reads `samples/` through the `SAMPLES` path constant.

Actual verification: `./sigma test` passed all scenarios, API/CLI checks, Ruff,
Pyright, frontend typecheck and production build. Real Chrome
`browser_checks/recents.py`, `browser_checks/a15_generate.py` and
`browser_checks/a142.py` passed, including real Chrome checks after the
directory move. `browser_checks/text_views.py` reached the
opened sample project, then stopped at a stale `.project-eyebrow` selector;
the current project page uses the “Project description” heading. It needs a
separate refresh of its project-page assertions.

## Markdown conversion tooltip (2026-10-21)

The gray Σ control now shows a visible hover and keyboard-focus tooltip reading
“Convert to markdown”; while the hourglass is active, it reads “Converting to
markdown”; after a successful conversion, it reads “Show plain text”. The
A14.2 real-Chrome regression checks all three states.

Actual verification: `uv run --with playwright python
browser_checks/a142.py` passed in real Chrome, including the initial gray state,
in-progress state, conversion failure and retry, and the rendered-state
tooltip. `./sigma test` passed all scenarios, API/CLI checks, Ruff, Pyright,
frontend typecheck and production build.

## Generate Strategy controls and manual fallback removal (2026-10-21)

Removed “Continue manually” from the Generate Strategy flow. Its starting point
and generated draft remain in that dialog through cancellation, sign-in decline,
and generation errors; users can still separately choose New to create a manual
strategy or fork an existing strategy. Moved Generate/Regenerate into the
dialog heading as an underlined action immediately before Cancel, and updated
authentication and provider guidance to point to retry or explicit billing
settings instead of a manual-continuation path.

Actual verification: `./sigma test` passed all scenarios, API/CLI checks, Ruff
check and format, Pyright, frontend typecheck and production build.

## Immediate retry after cancelling generation (2026-10-21)

The Generate dialog now sends a request ID and explicitly asks the API to cancel
the server-side generation task when the user cancels. This releases SIGMA's
single-request slot without waiting for the provider's normal completion; the
provider may still process or bill a request already received. The dialog keeps
Generate disabled until cancellation is confirmed, then allows an immediate
new intentional request. A short-lived cancellation tombstone handles a cancel
that reaches the API just before its proposal POST.

Actual verification: `./sigma test` passed all scenarios, Ruff, Pyright,
frontend typecheck and production build. Real Chrome
`uv run --with playwright python browser_checks/a15_generate.py` passed with an
immediate Generate retry after cancelling a deliberately delayed mock request;
no live provider call was made.

## Project and Strategies heading controls (2026-10-21)

The project heading is simply **Project**. Its text and Settings controls share
the heading row, with controls immediately after the heading. New and Generate
are beside Strategies on its heading row. Project description editing shows
Save and Cancel without Settings. Project action buttons use the same 16px
spacing as the Strategies action buttons. During strategy generation, the
button itself carries the visible loading label; the duplicate visible status
line is removed while a screen-reader-only live status remains.

Actual verification: `./sigma test` passed all scenarios, API/CLI checks, Ruff
check and format, Pyright, frontend typecheck and production build.
`uv run --with playwright python browser_checks/a15_generate.py` passed in real
Chrome against the isolated mock provider, including generation, failure,
cancellation, save/reopen, and mobile overflow checks. No live provider call was
made.

## Project description edit actions (2026-10-21)

While the project description is being edited, its text action row now shows
Save and Cancel without Settings. Settings returns after the edit is saved or
cancelled.

Actual verification: `./sigma test` passed all scenarios, API/CLI checks, Ruff
check and format, Pyright, frontend typecheck and production build.
