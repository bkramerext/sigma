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

## Current boundaries

No live agents, scheduler, evaluator, generated reports, forks, paid calls, or hosting. Local POSIX storage limitations and migration behavior are in [DECISIONS](DECISIONS.md). Run instructions are in [Getting Started](GETTING-STARTED.md).
