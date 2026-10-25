# BLUE IN 18 — Increment 18 R4R: hosted research/export integration

**From:** Blue  
**To:** ChatGPT coordinator  
**Assignment:** Round 2, Increment 18  
**Branch / PR:** `blue/increment-18-hosted-research` / [PR #130](https://github.com/bkramerext/sigma/pull/130)  
**PR head:** `6ea36ede71d8e3a88e271c384247120e2efd694e`  
**Integrated base:** `main` through `b331edb16f8755d4910ab2e6ac1b3432d88cc770`  
**State:** R4R, open, unmerged; Increment 18 is partially verified, not complete.

## Win

Extended the deterministic authenticated hosted research API scenario through
saved Outcome, project JSON export, text report download and reading the same
project/session/result/report from a fresh FastAPI process using the persistent
workspace. Retained the exact route response bytes in
`docs/evaluations/increment_18/exports/`; its manifest records project
`e3bddcf6-d78f-40c0-ac17-f7aebff13ec6`, session
`f694137f-9576-4fff-ab8a-db866cd89930`, capture/app commit `adb3205`, artifact
publishing commit `ab35f2f`, actions and omissions. The final PR head is
`6ea36ed`.

Inspection and the joined deterministic scenario found no Blue-owned research
engine behavior defect. Existing coverage already exercised sponsor-only
credential selection, spending controls, idempotency, failure accounting and
workspace isolation; it ended before the user-facing Outcome/export and
process-restart boundary. No product behavior was changed.

## Verification and limits

- `env -u SIGMA_CLOUD_BOOTSTRAP_ADMIN_EMAIL ./sigma test` passed on code head
  `adb3205` after main integration at `f76d834`: all scenarios, Ruff check and
  format, Pyright, frontend typecheck and production build.
- The focused authenticated sponsored-session API fixture passed and retained
  real project/report export response bytes. It uses a test-only principal
  adapter and deterministic `httpx.MockTransport`; no live provider call,
  production secret, OAuth exchange or cloud resource was used.
- Packaged Compose/Chrome acceptance is UNVERIFIED. The host has standalone
  Compose v2 but no `docker compose` plugin. A temporary shim routed the
  packaged validation to that binary; service startup then failed before the
  app ran because the ARM64 Docker engine lacked Buildx and generated ARM64
  images where the package requests amd64. No real-browser result is claimed.
- Real Google OIDC, hosted browser research, GCE rootless Python/Sage
  isolation, restart on the actual host and Red-owned #98/#99 gates remain
  UNVERIFIED. Red owns the host/deployment acceptance. No actual hosted
  provider usage was attempted or authorized.
- Assignment elapsed time was approximately 40 minutes through handoff.

Detailed evidence: `messages/i18_blue_r4r.md`, `docs/STATUS.md`, and
`docs/evaluations/increment_18/exports/manifest.json` on PR #130.

The coordinator retains acceptance, prioritization, and any decision about the
remaining Cloud/browser dependencies. No scope or acceptance criterion was
lowered. Blue did not merge the PR.
