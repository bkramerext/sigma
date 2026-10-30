# RED R4R — v0.1.5 About build SHA correction

Production About previously displayed `Version 0.1.5 · Build unknown`.

## Cause and correction

Release images are built from a Git archive without `.git`, so Vite could not
discover the source SHA. PR [#344](https://github.com/bkramerext/sigma/pull/344)
passes the full requested SHA as `SIGMA_BUILD_COMMIT` to the frontend Docker
build; Vite displays its seven-character prefix. Review also found the active
host helper would call its old builder before selecting candidate code. PR
[#345](https://github.com/bkramerext/sigma/pull/345) checks out and validates
candidate tooling before image construction, and restores the prior checkout
on a candidate build/preflight failure without stopping the service or
changing the release pin.

Both PRs were reviewed and merged under the operator's standing
self-review/self-merge authorization. #344 head
`0750cbefbdb4dc6d0db3cea8ed104f109d6856fd` passed CI run 41009812640. #345
final head `2765872e9c8b85f362d5bc6656ed42126db9187b` passed CI run 41010839265.
Focused local checks passed: release-image tests (3), deployment-package
checks, GCE deployment automation, T173 failed-build recovery rehearsal, Ruff
format, and `git diff --check`. A local production frontend build with the
release SHA confirmed the seven-character value was embedded. The local full
`./sigma test` was stopped after the operator requested a spot fix; exact-head
CI completed the repository verification successfully.

## Production result

Under the operator's quick-patch deployment authorization, the guarded helper
deployed exact merged SHA
`83c89f20e19ea87c4a3b4934942d0a78c2019973` to `sigma-gce-01` on 2026-10-30.
The helper ran from the selected commit so candidate build tooling was used.
Host checkout and `SIGMA_RELEASE` match this SHA. Release-image verification
passed; backend, frontend, and edge containers are healthy; systemd is active
with no pending reload; and `/srv/sigma-state` remains mounted. The public SPA
root and JavaScript bundle return HTTP 200, and the bundle contains `83c89f2`.
Unauthenticated `/api/health` returns HTTP 401 as expected.

Recovery evidence: the existing pre-v0.1.5 snapshot remains READY and was not
replaced. No new snapshot or restore drill was done for this frontend build
metadata correction. Backend application code and state schema were unchanged.
No paid provider calls, local SIGMA server requests, or new infrastructure
changes occurred. No `v0.1.5` tag was created.
