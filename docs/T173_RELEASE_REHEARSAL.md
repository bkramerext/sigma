# T173 release smoke rehearsal (2026-10-26)

## Assessment

**Local release mechanics: PASS with the changes in this branch. Production
release readiness: BLOCKED.** The prior flow used a full Git SHA in the image
tag and environment pin, but Compose also declared build contexts; a missing
tag could therefore build from the currently staged checkout. The new
`build-release-images.sh` requires exact clean `HEAD`, builds both tagged images
under staging tags before promoting both final tags, records the revision
label, and `start-gce.sh` uses
`--no-build`. Backend/frontend build inputs use digest-pinned base images and
locked dependencies. The resulting OCI images are not asserted bit-for-bit
reproducible across builders.

The rollback helper is guarded by root, mode-0600 deployment env, mounted
state-disk, inactive backup, full target SHA, local prior images, explicit
backup/schema assertions, and preflight. It changes only the release setting,
restarts through systemd, waits up to two minutes for app health, and restores
the prior pin and attempts restart if the candidate fails. It does not mutate
the state disk or rewind SQLite/provider ledgers. This is code inspection and
existing unit coverage; the real host helper was not executed in this local
fixture rehearsal.

## Reproducible local rehearsal

Command: `uv run --locked --no-sync python tests/release_rehearsal.py`

The test creates a temporary Git checkout, a fake Docker executable, and fake
image-build outcomes. The backend build is accepted and the frontend build
returns exit 17. Result: **PASS**; the builder exits nonzero with an explicit
instruction not to change `SIGMA_RELEASE`, and no successful candidate pair is
reported. A second run with an untracked file is refused before Docker is
called. No Docker daemon, GCE, DNS, public endpoint, production credential, or
paid provider was contacted. This is deterministic orchestration evidence,
not a real container build.

Packaged application command: `bash deploy/validate-local.sh`. Result:
**PASS** using real Docker Compose and Chrome against disposable packaged
backend/frontend/edge containers and temporary state volumes. Project/strategy
edits, 5 saved sessions, Outcome, report downloads, Tectonic/PDF hashes,
backend recreation and fresh-volume backup restore passed; workspace isolation
survived restore. OAuth and provider inference were explicitly skipped. The
script cleaned its containers/network/volumes at completion. This validates
packaged application and fixture restore behavior, not the GCE unit, host
rollback helper, actual GCE snapshot API, persistent-disk mount or public TLS.

Full `./sigma test` was rerun after updating the startup fixture. Storage and
the new release rehearsal passed. It exits 1 on three pre-existing assertions
in `tests/deployment_package.py`, `tests/gce_host.py`, and `tests/host_monitor.py`
that still require the old explicit escaped systemd mount dependency, whereas
current `main` uses `RequiresMountsFor=/srv/sigma-state`. T163 coordinator
integration owns reconciliation of those expectations; they were not changed
here. Ruff check, Ruff format, Pyright (0 diagnostics) and frontend typecheck
passed. The runner skipped frontend production build after test failures;
`npm --prefix frontend run build` passed separately (with the existing large
chunk advisory). Focused `tests/storage.py` passed. The earlier independent
focused run of `tests/gce_host.py` and `tests/host_monitor.py` confirmed the
same mount expectation as their only failure; `tests/state_backup.py` passed.

Existing state backup/restore checks use temporary fixture roots and read-only
verification; existing rollback tests verify required guards and that volume
deletion commands are absent. Those checks were run as part of the validation
listed in STATUS. No actual state is copied from a user project.

## Evidence-based gates

| Area | Result | Evidence and limit |
|---|---|---|
| Release SHA/source match | PASS locally | Builder checks clean checkout and exact full SHA before invoking Docker. |
| Build failure | PASS fixture | Simulated frontend failure after backend success exits nonzero before activation; production config is not touched by builder. |
| Startup image behavior | PASS by config/test | Compose startup uses `--no-build`; missing candidate images fail rather than building another source tree. |
| Startup health failure | PASS by helper inspection; live BLOCKED | Rollback helper waits for backend/frontend healthy and edge running, restores old env and retries old service on timeout. No VM daemon/service was run. |
| Code rollback | BLOCKED live | Guarded logic and prior-image checks exist; no VM, Docker release images or host state were available locally. |
| Persistent data | PASS by design/test; live BLOCKED | Release build/start/rollback do not remove volumes or rewrite SQLite; state remains `/srv/sigma-state/auth`. Live before/after record comparison and restore drill pending. |
| Backup / restore | BLOCKED live | Scheduled snapshot and read-only verifier exist; no snapshot, GCE API, separate disk, or recovery host was used. Local fixture verifier does not prove snapshot recoverability. |
| DNS / HTTPS | BLOCKED live | Public endpoint checker exists; no DNS, public host, Caddy certificate issuance, or outside-network probe was run. |

## First production deployment checklist

1. Record owner-approved project, VM, reserved IP, disk UUID, current release
   SHA, candidate SHA, reviewed PR, migration notes, and maintenance window.
2. Verify live `/srv/sigma-state` mount identity and restrictive permissions;
   confirm it is not boot-disk fallback. Confirm current users/projects/sessions/
   paper artifacts and usage/reservation records have a sanitized baseline.
3. Confirm latest backup is `READY`; verify it came from the expected state
   disk. Complete an isolated separate-disk restore and compare known
   identities, workspaces, projects, SQLite integrity, artifacts and ledger
   before declaring production recovery ready.
4. Keep prior checkout, deploy env, and both prior image tags. Stage candidate
   at exact clean SHA. Run `build-release-images.sh SHA`; verify both image
   tags exist and OCI revision labels match. If either build fails, stop and
   preserve the active release pin.
5. Confirm DNS A record matches owner-verified static IPv4; only TCP 80/443 are
   public; 8000/5173/2375/2376 are closed. Complete OAuth origins/callback and
   protected secret files without exposing values. Require the DNS and HTTPS
   probe prerequisites before public cutover.
6. Announce downtime and quiesce writers for any consistent snapshot. Change
   only `SIGMA_RELEASE`, run host preflight, then start via systemd. Verify all
   three container health states, mounted data path, hosted API readiness,
   redirect, trusted HTTPS certificate and SPA/API routes from outside VM.
7. Use authorized test identities to verify sign-in, isolation, saved project,
   research history, export, usage totals and reservation state. Compare with
   baseline and record candidate SHA, time, downtime, logs and results.
8. Any failed build, preflight, unhealthy startup, timeout, DNS/TLS/API failure,
   wrong release revision, mount mismatch, or changed/missing persistent record
   is STOP. For a healthy known-compatible schema, run guarded rollback with
   verified-backup/schema assertions. Recheck public endpoint and persistent
   records; code rollback never recovers or rewinds data.

## Still requires the live VM

Provisioned host identity and mount UUID proof; approved secrets and rootless
sandbox; actual Docker image builds on the target architecture; target-host
preflight/startup and health behavior; an intentionally failed startup against
the disposable host stack; real prior-image rollback; before/after auth,
workspace, project, artifact and ledger comparison; snapshot IAM and metadata
credential isolation; `READY` backup and separate-disk restore; public DNS,
firewall, trusted Caddy TLS, external endpoint checks; and owner/cross-ticket
hosted application acceptance. No item here is implied PASS by the local run.
