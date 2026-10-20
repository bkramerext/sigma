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

## Current boundaries

No live agents, scheduler, evaluator, generated reports, forks, paid calls, or hosting. Local POSIX storage limitations and migration behavior are in [DECISIONS](DECISIONS.md). Run instructions are in [Getting Started](GETTING-STARTED.md).
