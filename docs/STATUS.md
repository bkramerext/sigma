# SIGMA status

Updated: 2026-10-20

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
- New `scenarios/project_creation.py` verifies both modes on disk and reopen,
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
- `scenarios/strategy_tracking.py`: v1–v4 no-write reads/defaults, exact backups,
  active-only order, removed history, stable IDs/timestamps, no-ops, failed saves,
  stale order, competing reorder/stage/edit writes, corruption and API/CLI checks.
- `scenarios/proposals.py`: exact official Responses endpoint/payload, strict
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
- `uv run ruff check src scenarios browser_checks` and format checks passed.
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
- `scenarios/project_settings.py`: explicit model/High creation, v1–v5 no-write
  defaults, no-op, exact backups, both mode directions, stable identity/location/
  archived research/order, failed writes, stale editor races, independent strategy
  changes, strict corrupt audit rejection, and API/CLI update/conflict checks.
  Empty/unknown models and unsupported efforts are rejected without creating files.
- `scenarios/model_connection.py`: valid curated discovery (unreviewed models do
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
- `uv run ruff check src scenarios browser_checks` and corresponding format check
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
- `scenarios/local_config.py`: missing file, quoted export/single/plain/empty
  values, comments, explicit environment precedence (including disabled AI),
  literal shell/variable syntax without execution/expansion, no key output,
  atomic malformed-file rejection, UTF-8 and unreadable-file safe diagnostics.
- `scenarios/instance_ownership.py`: canonical alias and changing symlink target,
  different checkout IDs, directory permissions/symlink refusal, non-socket state
  preservation, refused stale-socket recovery, live wrong-identity refusal without
  sending shutdown or removing its endpoint, and no-follow lock protection.
- `uv run --with playwright python scenarios/ui_lifecycle.py` passed against
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
