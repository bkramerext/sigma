# Blue Increment 18 R4R — hosted research/export integration

- **Branch:** `blue/increment-18-hosted-research`
- **Starting base:** `origin/main` at `ade23f8` (Round 2 ticket detail merge)
- **Latest integration:** merged `origin/main` at `f76d834` after the remote advanced during the assignment; no conflicts in the test or handoff files.
- **Head:** PR head commit; final full-suite verification was run after integrating `f76d834`.
- **Scope:** one extension to `tests/cloud_research_sponsored_api.py` that follows an authenticated deterministic hosted research run through the owner-facing project export, saved Outcome verification wording, text report response, and fresh FastAPI process recovery from the same durable workspace.

## Win

The existing hosted sponsored-inference fixture already exercised production
FastAPI routes and workspace boundaries, server-only credential selection,
budgeting, session idempotency, failure accounting and cross-owner denial. The
new check connects the saved research result to the actual project/report export
surface and confirms the project, completed session, Outcome and report remain
readable after a separate application process opens the workspace. No session
engine behavior defect was found by inspection or this check, so no product
behavior was altered.

## Verification actually run

- `./sigma setup` — passed; installed locked Python and frontend dependencies.
- `uv run --locked --no-sync python tests/cloud_research_sponsored_api.py` — passed after the change. It uses a test-only verified-principal adapter and deterministic `httpx.MockTransport`; no external model request occurs.
- `env -u SIGMA_CLOUD_BOOTSTRAP_ADMIN_EMAIL ./sigma test` — passed all scenarios, Ruff check/format, Pyright, frontend typecheck and production build. First full-suite attempt stopped at Ruff format for this test file; formatted it and reran the full suite successfully.
- `git diff --check` — passed before documentation updates.
- Packaged Compose/Chrome attempt: **not completed**. `./deploy/validate-local.sh` first reported that the Docker Compose CLI plugin was missing. A temporary `/tmp` shim routed the command to installed Docker Compose v2. Both images built, but the preflight runner could not start because the ARM64 engine lacked Buildx and the image built for ARM64 while Compose requested `linux/amd64`. Retrying with `DOCKER_DEFAULT_PLATFORM=linux/amd64` produced the same mismatch. No browser acceptance result is claimed. The script's disposable secrets and volumes were cleaned up.

## Expectations and remaining issues

| Increment 18 criterion | Evidence / state |
|---|---|
| Authenticated hosted research with sponsor and budget safeguards | PASS in deterministic production-route integration scenario. |
| Project, saved session, Outcome and export survive app process restart | PASS in fixture-backed fresh-process API acceptance; this is not a live GCE restart. |
| Browser-driven hosted E2E | UNVERIFIED; local Compose run blocked before app startup by host architecture/tooling mismatch. |
| Real Google OIDC and Cloud owner #98/#99 host gates | UNVERIFIED; Red owns these deployment checks. |
| Real hosted Python/Sage availability under rootless GCE isolation | UNVERIFIED; Red host acceptance required. |
| Live provider quality/cost | Not exercised; no production secret, real provider call, paid usage, or GCP resource used. |

This increment is **partially verified**, not complete. The coordinator owns
whether the unverified Cloud/browser checks can be accepted, reordered or
assigned after Red's host run. I did not change scope or lower acceptance.

## Handoff

Elapsed worker time was approximately 40 minutes from assignment start through
PR-ready work. No Cloud-owned implementation was changed. See `docs/STATUS.md`
for the retained project status entry and final head/PR link.
