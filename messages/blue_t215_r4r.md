# Blue R4R — PR #221 (T215) request-toast expiration

**Branch:** `blue/t215-toast-expiry`

**Base:** `main` at `e821520`

**Implementation commit:** `069b81d91b90be4b4edcdc0487fbd100e19272ec`

**PR:** [PR #221 (T215)](https://github.com/bkramerext/sigma/pull/221), open against `main`, not merged

**Reconciled code head:** `7f89dcb` (merge of current `main` `084e23b`)

## Delivered

- Request error toasts have independent 60-second lifetimes. Expiration and
  manual dismissal enter the same downward-exit phase before DOM removal.
- A grid row and padding collapse animate remaining stack entries into place.
  Toast order and the existing four-toast cap remain unchanged.
- `prefers-reduced-motion: reduce` skips the exit phase and removes the toast
  immediately at expiry. Existing fixed placement and responsive width remain.
- Added an isolated store with injectable timers, seven Node built-in fake-clock
  tests, and a real-Chrome browser check for timing, downward transform, stack
  reflow, manual dismissal, reduced motion, cleanup, and 390px layout. Wired
  the Node test into `./sigma test`.
- Updated the concise status summary and ticket tracker. No provider calls,
  cloud operations, or research project/session changes.

## Verification

- `node --test frontend/src/request-toast-store.test.mjs` — PASS, 7 tests.
- `uv run --locked --with playwright python browser_checks/request_toast_expiry.py`
  — PASS in real Chrome, desktop and 390px viewport.
- Focused Ruff check/format, frontend typecheck, and `git diff --check` — PASS.
- `./sigma test` — PASS all scenarios, Ruff, format, Pyright (0 diagnostics),
  frontend typecheck, and production build. Vite reports the existing large
  chunk advisory.
- `browser_checks/t47_conclusion.py` — PASS in real Chrome after preserving
  coordinator commit `d625216`, which waits for the animated dismissal and
  avoids unstable pointer clicks.
- `browser_checks/request_toast_expiry.py` — PASS in real Chrome after
  reconciliation; independent toast expiry, downward transform, reflow,
  reduced-motion mode and 390px layout verified.

GitHub CI for the reconciled final head is being checked after this branch push;
its result will be recorded before this handoff is considered final.

## Limitations

Browser visual acceptance used Chrome only; no Firefox, Safari, or physical
mobile device was exercised. The fake-clock suite covers simultaneous expiry
and cleanup deterministically. No known functional blockers remain.
