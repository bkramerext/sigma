# Gray R4R — PR #224 (T86)

**Branch:** `gray/t86-readme-integration` → `main`  
**Head:** `ad860499666ac9574dd129a248145ab75dbf0e67`

## Summary

Recovered the README work from the T86 branch and reviewed the already merged
PR #104. Reconciled the README against current `main` and the T86 review notes:
distinct owner-screenshot placements for SIGMA Home and a Riemann Hypothesis
investigation; a focused product description with explicit limits; corrected
local Google administrator bootstrap guidance; documentation links that
resolve; and a short About Development paragraph linking to WOLF. `WOLF.md` is
unchanged. The existing Product Rationale remains linked from the README; no
duplicate rationale file was added. Verification is recorded in `docs/STATUS.md`.

## Verification performed

- `./sigma setup` — passed (locked Python sync and frontend `npm ci`).
- `./sigma start` with `SIGMA_CLOUD_ADMIN_CONTACT_EMAIL` unset — reached ready
  state; frontend `http://127.0.0.1:5173/` returned HTTP 200; API
  `http://127.0.0.1:8000/api/ui-instance` returned HTTP 200; `./sigma shutdown`
  completed.
- README Markdown link scan — 14 links, no missing local targets.
- `git diff --check` — passed, including the final diff against current `main`.
- `./sigma test` — passed all scenarios, Ruff, Ruff formatting, Pyright
  (0 errors/warnings/information), frontend typecheck, and production build.
  Build emitted the existing advisory about a JavaScript chunk over 500 kB.

No paid provider calls or live/credentialed Google OAuth were performed. The
local bootstrap instructions were checked against `src/sigma/cli.py`,
`src/sigma/ui.py`, `docs/CLOUD_DEPLOYMENT.md`, and `deploy/env.example`; browser
sign-in itself was not exercised.

## Remaining dependency

Brian still owes two actual screenshots: (1) SIGMA Home and (2) a credible,
owner-exercised Riemann Hypothesis investigation. Separate labeled placement
markers are present in README. No screenshots were created, selected, or
substituted. Per the T86 owner decision, screenshot delivery is a documented
follow-up and does not block this README PR.

**R4R:** [PR #224 (T86)](https://github.com/bkramerext/sigma/pull/224). Do not
self-merge.
