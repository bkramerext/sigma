# T173 release smoke rehearsal (2026-10-26)

## Readiness assessment

**Local release failure/recovery mechanics: PASS against the T129 candidate.
Production release readiness: FAIL / NO-GO.** T129 implementation remains in
the coordinator-owned, unmerged [PR #161](https://github.com/bkramerext/sigma/pull/161).
T173 adds only a fixture rehearsal and release-readiness record; it does not
reimplement T129 deployment behavior or alter T129/T163-owned files.

The T129 release command selects a full lowercase 40-character Git SHA, checks
for a clean checkout, fetches that commit, and runs the backend/frontend
Compose build before stopping the active service or changing the protected
release pin. The application Dockerfiles pin base images by digest and package
inputs by lockfiles. This provides controlled build inputs and SHA-tagged
images; no byte-for-byte image digest comparison across builders is claimed.
No manifest/artifact attestation currently binds the pushed source SHA to a
registry digest; target-host build and image identity checks remain required.

Build or preflight failure occurs before service stop/pin change. Candidate
startup or health failure restores the old checkout and release pin, attempts
to restart the old service, and verifies its health. The fixture test confirms
the pin/config bytes and a persistent-state marker survive failure. This is
not actual GCE rollback evidence. Code rollback never restores data or undoes
schema migrations/provider charges.

| Gate | Result | Evidence limit |
|---|---|---|
| Full SHA source → image tag | **FAIL** | Isolated fixture shows previous checkout SHA during candidate build and candidate SHA in `SIGMA_RELEASE`; requires T129 correction. |
| Pinned build inputs | **PASS, constrained** | Digest-pinned Docker bases and lockfiles are present. Byte-identical images or registry digest provenance are not claimed. |
| Failed-build behavior | **PASS** | Candidate Compose build exit 17 leaves service, env pin, checkout and fixture data unchanged. |
| Startup/health failure recovery | **PASS, fixture only** | Existing T129 test exercises candidate start failure and prior service restart; no real GCE service was run. |
| Persistent data across restart/restore | **PASS locally; BLOCKED live** | Packaged local Compose restart and fresh-volume restore preserve fixture IDs/hashes; no GCE disk/snapshot was used. |
| GCE backup and separate-disk restore | **BLOCKED** | Fixture restore is not a GCE `READY` snapshot or restored disk. |
| Public DNS and HTTPS | **BLOCKED** | Deterministic endpoint tests pass; no live DNS, public firewall, cert issuance or outside-VM probe was performed. |

## Reproducible local rehearsals

T129 PR head: `c19e1d654f27be6f736f1aea382033e9d79080da`, detached isolated
worktree `/Users/admin/sigma_t129_review`.

1. Run existing T129 fixture coverage:

   ```sh
   cd /Users/admin/sigma_t129_review
   uv run --locked --no-sync python tests/deployment_automation.py
   ```

   **PASS:** idempotent already-active release, missing configuration,
   simulated startup failure, release/config restoration, prior release
   restart, sanitized diagnostics, and unchanged state fixture.

2. Rehearse candidate image build failure against T129 code with isolated files:

   ```sh
   cd /Users/admin/sigma_t173
   uv run --locked --no-sync python docs/evaluations/t173/build_failure_rehearsal.py \
     --deployment-script /Users/admin/sigma_t129_review/deploy/deploy-gce-release.py
   ```

   **PASS:** fake Compose build returns exit 17. The helper exits before
   `systemctl stop`, checkout, or release-pin write; exact `deploy.env` bytes
   and temporary persistent-state marker remain unchanged. No Docker daemon,
   GCE, DNS, production credential, public endpoint or paid provider is used.

3. Check source SHA against the candidate image tag:

   ```sh
   cd /Users/admin/sigma_t173
   uv run --locked --no-sync python docs/evaluations/t173/build_source_sha_rehearsal.py \
     --deployment-script /Users/admin/sigma_t129_review/deploy/deploy-gce-release.py
   ```

   **FAIL (reproduced):** command exits 1 and records
   `selected_image_sha=bbbb…bbbb`, `build_context_checkout_sha=aaaa…aaaa`,
   `post-build_checkout_sha=bbbb…bbbb`. The T129 command fetches the target
   commit but does not check it out or create a target worktree before Compose
   builds from `--repository` (`/opt/sigma/current`). Only after the build and
   service stop does it check out the candidate. Thus the old source can be
   built under the new SHA tag. Existing T129 tests do not catch this. Require
   T129 integration to build from an isolated worktree/archive of the target
   SHA and add a regression proving build-context revision equals the image
   tag before considering release SHA pinning PASS.

4. Run packaged browser and storage smoke:

   ```sh
   cd /Users/admin/sigma_t173
   bash deploy/validate-local.sh
   ```

   **PASS:** real Docker Compose and Chrome against disposable packaged
   backend/frontend/edge containers. Project/strategy edits, 5 saved sessions,
   Outcome and report downloads, Tectonic/PDF hashes, backend recreation,
   fresh-volume restore and workspace isolation passed. OAuth and inference
   were skipped. The script cleaned its temporary Compose resources. This
   validates local app packaging and fixture restore behavior, not GCE service
   units, a persistent-disk mount, GCE snapshot API, public DNS/TLS or T129
   helper execution on the VM.

Other checks recorded during this work: `uv run --locked --no-sync python
tests/storage.py` passed; `npm --prefix frontend run build` passed separately
with the existing large-chunk advisory. `./sigma test` fails three existing
systemd mount-contract assertions in `tests/deployment_package.py`,
`tests/gce_host.py`, and `tests/host_monitor.py`: they expect the former
explicit escaped mount dependency while current systemd uses
`RequiresMountsFor=/srv/sigma-state`. T163 coordinator integration owns those
expectations; T173 does not change them. Ruff check/format, Pyright (0
diagnostics), and frontend typecheck passed in the full run; runner skipped
the frontend build after test failures, then the standalone build passed.

## First production deployment checklist

Use the T129 operator command only after its PR is reviewed/merged and current
main contains its runbook/script. Before that, production deployment is STOP.

1. Record owner-approved project, VM, reserved IP, disk UUID, chosen release
   SHA, reviewed PR, migration notes, current `SIGMA_RELEASE`, and downtime
   window. Preserve the previous checkout, protected env file and image tags.
2. Verify live `/srv/sigma-state` mount identity and permissions; prove it is
   the attached state disk, never a boot/container fallback. Capture a
   sanitized baseline for users, workspaces, projects, sessions, paper files,
   usage and reserved/unknown ledger entries.
3. Confirm a recent `READY` snapshot sourced from the expected disk. Complete
   T135's isolated separate-disk restore and verify identities, SQLite
   integrity, projects/artifacts, papers and ledger against the baseline.
   Snapshot existence alone is not a recovery pass.
4. Confirm a clean checkout and run host read-only preflight. For the first
   application start, set `SIGMA_RELEASE` to the exact full SHA in
   `/etc/sigma/deploy.env`, then use:

   ```sh
   sudo python3 /opt/sigma/current/deploy/deploy-gce-release.py FULL_40_CHAR_SHA --initial
   ```

   For subsequent upgrades, announce downtime, verify the latest recovery
   point and schema compatibility, then use:

   ```sh
   sudo python3 /opt/sigma/current/deploy/deploy-gce-release.py FULL_40_CHAR_SHA \
     --backup-verified --schema-compatible
   ```

   Those flags are operator assertions; the command does not make a backup or
   determine schema compatibility for you. The command fetches/builds the exact
   SHA before stopping the existing service, updates only the release pin,
   checks preflight, and starts through systemd.
5. Require backend/frontend/edge health, correct app image tags and checkout
   SHA, active systemd service, mounted state path, and API readiness. From
   outside the VM run `python3 deploy/verify_public_endpoint.py
   --expected-ip OWNER_VERIFIED_STATIC_IPV4`; require DNS A match, only TCP
   80/443 open, HTTP→HTTPS redirect, trusted certificate, SPA deep route and
   hosted API ready. OAuth origins/callback and protected secrets must be
   reviewed without printing values.
6. With authorized test identities, compare project/session/artifact and
   accounting records to baseline; test identity isolation, report/export and
   browser reload. Record UTC, deployed SHA, outage, probes and sanitized logs.

## Stop/go and rollback triggers

**GO** only if the release is reviewed and image source is proven to match the
full SHA tag, exact build succeeds,
host preflight passes, verified recovery point and schema compatibility are
established, all local service/health and public DNS/HTTPS checks pass, and
saved state matches the baseline.

**STOP / rollback trigger:** source SHA/image tag mismatch; candidate build or preflight failure; startup
failure/health timeout; image/check-out SHA mismatch; absent or wrong disk
mount; DNS mismatch, invalid HTTPS, unready public API; missing project,
artifact or accounting record; or unknown migration compatibility. For a
verified, compatible schema, let the T129 command restore the prior code/pin
and verify service health. If automatic recovery fails, keep ingress closed,
preserve both releases, env records, logs and state disk, and escalate. If data
integrity is uncertain or migration is incompatible, stop writes and follow
the separate-disk restore/cutover procedure; code rollback is not data restore.

## Live VM evidence still required

Owner-approved host and rootless sandbox readiness; target architecture image
build; real preflight/start/healthcheck; induced candidate health failure and
prior-release recovery; live pre/post persistent-data comparison; approved
snapshot IAM and metadata credential isolation; successful `READY` GCE backup
and isolated separate-disk restore; public DNS, firewall, Caddy certificate
and external endpoint checks; and owner-authorized hosted OAuth/workspace/
research acceptance. None is implied by these local fixture results.
