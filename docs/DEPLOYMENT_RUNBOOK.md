# SIGMA Deployment Runbook

This runbook records who authorized the SIGMA v0.1.5 release work and the
checks required before the guarded GCE cutover. It supplements
[OPERATION_RUNBOOK.md](OPERATION_RUNBOOK.md), which contains the detailed host,
backup, restore, deployment, and rollback commands. A recorded authorization is
not evidence that a release gate passed or that an operation was executed.

## Authorization record — SIGMA v0.1.5 / issue #337

| Authorization | Record | Scope |
| --- | --- | --- |
| Stage A release preparation | The operator approved Stage A; PR [#338](https://github.com/bkramerext/sigma/pull/338) was merged at `bc275cb214d1fbec0fd40334593d50d82263c07e`. | Prepare the v0.1.5 release candidate and its handoff. The release tag was not authorized by that approval. |
| Self-review and self-merge | The operator explicitly authorized the agent to self-review and merge its own PRs. PRs [#340](https://github.com/bkramerext/sigma/pull/340) and [#341](https://github.com/bkramerext/sigma/pull/341) were reviewed against their diffs and verification evidence, then merged at `f4ff07a1b1a5e82915990adee8dea9466702d5bd` and `aa23f4b393f4ef657471705f467f9beecbb0689a`. | Repository PR review and merge only. Each PR still requires a clean diff, exact-head CI success, and merge against the expected head SHA. |
| Stage B production release | After initially withholding cutover authorization, the operator directed “you need to deploy” and then explicitly confirmed “yes, i authorize.” | Authorizes proceeding with the v0.1.5 production release process, subject to the preservation, recovery, exact-SHA, health, and no-paid-provider constraints below. It does not make an unverified rollback assertion true. |

The release authorization does not approve unrelated infrastructure changes,
recurring backup configuration, IAM broadening, deletion of production data or
recovery points, or paid provider inference. It includes cleanup of temporary
VMs and clone disks created solely for the authorized restore drill, while
retaining the approved recovery snapshot. Keep the operator's constraints:
preserve identities, projects, research, papers, and spending records; do not
access the operator's local SIGMA server; do not coordinate directly with
other Codex workers.

The operator also directed that issues exposed by release work be fixed within
scope, and that work may be aborted when a failure becomes catastrophic or
disproportionate. Fix a bounded defect found during preflight or deployment,
verify the fix, and record the new exact SHA. If the next action risks data
loss, identity/accounting corruption, credential exposure, unbounded cost, or
requires an unreviewed destructive migration, stop writers when needed, preserve
the current disk and evidence, do not bypass a gate, and report the blocker and
smallest safe recovery path. Resume only after the owner reviews any new scope.

## Release controls

1. Select one full lowercase 40-character release commit SHA. Run CI on that
   exact SHA and record its successful result. Build from that SHA using
   `deploy/release_image.py`; verify both `linux/amd64` image revision labels
   and immutable image IDs. The release builder also passes the full commit as
   the frontend Docker build argument `SIGMA_BUILD_COMMIT`; Vite displays its
   seven-character prefix in About. Do not substitute a tag or a moving branch
   name. Verify the built frontend bundle contains the expected seven-character
   prefix before deployment.
2. Before stopping production, verify the actual host checkout, protected
   `SIGMA_RELEASE`, running image tags/labels, mounted state disk, service
   health, and the last recovery point. Record observed values and resolve
   disagreements from host state and timestamped release records.
3. Use a fresh application-consistent state-disk snapshot and verify it by
   restoring a clone on an isolated host with no public ingress and no
   production service account or credentials. Establish the recovery
   verifier's aggregate thresholds before the drill. Red records the selected
   maintenance window, required IAM, project quota/billing review, $25 maximum
   incremental cost, recovery owner, and temporary-resource cleanup plan before
   creating resources. A production deployment assignment authorizes these
   routine, bounded release steps without another human approval. Use no public
   ingress or production service account for recovery resources; retain the
   recovery snapshot. If billing, quota, IAM, or the $25 ceiling cannot be
   verified, stop and report the specific gate.
4. Run the documented host preflight with the explicit repository argument:
   `sudo /usr/local/libexec/sigma/gce_preflight.py --json --repository /opt/sigma/current`.
   Run the sandbox runtime check only as an approved exercise because it starts
   a sandbox execution and writes evidence.
5. Deploy only through the guarded GCE helper, with the exact selected SHA and
   required recovery/schema assertions. The guarded command's Boolean
   assertions are operator attestations, not compatibility tests. Start with
   `--no-build`, then verify service/container health, image IDs and labels,
   public HTTPS, authentication, and persistence without paid provider calls.
6. Record the actual cutover SHA, image IDs, downtime, health evidence, recovery
   point, and operator outcome in `OPERATION_RUNBOOK.md` and `STATUS.md`.

## Routine-release autonomy

An explicit assignment to deploy the current `main` authorizes the ordinary
steps in this runbook. Red owns the maintenance window, exact-SHA CI and image
checks, isolated restore drill, guarded deployment, smoke tests, temporary
recovery VM/disk cleanup, and release records. Do not pause for an additional
human approval when all gates pass. For each recovery drill, use the existing
READY snapshot where possible, retain it, and keep incremental GCP resource
costs at or below $25. Verify live billing, required quota, and least-privilege
access before creating temporary resources. If a gate fails, a resource would
exceed the ceiling, or a destructive/data-changing action is needed, keep
production untouched and report the blocker. This standing routine-release
authorization does not include unrelated infrastructure or IAM changes,
recurring backup setup, paid inference, or production data restoration.

## Schema 10 recovery rule

The exact v0.1.4 project parser accepts schemas 1–9 and rejects schema 10.
SIGMA v0.1.5 can write schema 10 when saving strategy provenance. No
older-binary compatibility bridge has been implemented or demonstrated.
Therefore:

- Before a schema 10 write, code rollback is allowed only after compatibility
  is demonstrated for the exact older binary and state.
- After a schema 10 write, do not restart v0.1.4 against the changed state.
  Stop writers, preserve the post-release disk and logs, and forward-fix on
  schema-10-capable code.
- If pre-release data recovery is necessary, treat it as a separate,
  explicitly authorized restore incident. Preserve the post-release disk,
  use the verified pre-release recovery point, and record the data-loss
  interval. A code rollback is not a data rollback.

## Current evidence

At the time of this record, production was observed on v0.1.4 at
`6fa626bdfc1f07cb873103dfed2323864d4fb280`. The existing snapshot was stale
and not restore-tested; the recurring backup timer was inactive. After the
operator authorized deployment, a fresh application-consistent snapshot
`sigma-state-v015-pre-20261030-0506` reached `READY` at
2026-10-29 22:06:32 PDT from source disk `sigma-state`. The service was stopped,
Compose writers were confirmed stopped, and the mounted disk was synced before
snapshot creation. SIGMA was restarted; systemd then reported no pending unit
reload, and the service was active with backend/frontend healthy and edge
running. The isolated restore drill and target-host image build remain
incomplete.

The v0.1.5 version-bump source commit is
`2026f1e5b167ec76289ba2335d369603e4f377ee`. For deployment, select the exact
post-release operational commit
`aa23f4b393f4ef657471705f467f9beecbb0689a`, which contains the v0.1.5 source
and rollback-preflight correction; its post-merge `verify` check succeeded
[in CI run 41006080748](https://github.com/bkramerext/sigma/actions/runs/41006080748/job/123901170598).
Build and label the target images from that full SHA. No `v0.1.5` tag has been
created.

The isolated restore check then completed on a clone of the snapshot, attached
READ_ONLY to a recovery VM with no public IP and no service account and mounted
`ro,nosuid,nodev,noexec,norecovery`. The offline verifier passed three SQLite
integrity checks, 3 identities/mappings, 12 projects, 30 research artifacts,
zero paper pairs, and 17 accounting call rows, including five reserved or
unknown outcomes. It also preserved ten terminal historical job rows across
two removed workspaces; no active jobs or accounting calls referenced those
workspaces. The verifier change for this history case is under review in
[PR #343](https://github.com/bkramerext/sigma/pull/343); exact-head CI and merge
must pass before the updated verifier becomes the maintained procedure. The
temporary VM and clone disk remain until evidence is recorded and cleanup is
verified. Preserve the snapshot.

The clone contained 12 saved project records: eleven at schema 8 and one at
schema 9, with no missing or invalid schema values. These versions are within
v0.1.4's supported 1–9 range and v0.1.5's 1–10 range. This confirms the
pre-cutover state is readable by either version; it does not establish that
v0.1.4 can read a later schema 10 write.

## 2026-10-30 About build SHA spot correction

PR [#344](https://github.com/bkramerext/sigma/pull/344) fixed frontend build
provenance by passing the full requested commit as `SIGMA_BUILD_COMMIT`; Vite
embeds its seven-character prefix. PR
[#345](https://github.com/bkramerext/sigma/pull/345) changed the guarded helper
to check out and validate candidate tooling before image construction. Both
PRs were self-reviewed under the operator's standing authorization and passed
exact-head CI. The final deployed merge commit is
`83c89f20e19ea87c4a3b4934942d0a78c2019973`.

Production deployment used the candidate helper extracted from that exact
commit because the previously installed helper did not yet include the
candidate-tooling ordering fix. The guarded command fetched and verified the
full SHA, checked out candidate tooling, passed host preflight, built both
images from the candidate archive, then stopped/restarted the service and
verified health. The active checkout and protected pin now match the deployed
SHA. Both release image labels/IDs verified; all three containers are healthy;
systemd is active with no pending unit reload; `/srv/sigma-state` is mounted.
Public root and bundle returned HTTP 200, and the bundle contains `83c89f2`.
The unauthenticated health API returned expected HTTP 401.

This was a build-metadata correction with no backend application-code or state
schema change. The existing READY snapshot
`sigma-state-v015-pre-20261030-0506` was retained; no new snapshot or restore
drill was done. No paid provider call or local SIGMA server request occurred.
The `v0.1.5` tag was not created.

## Authorization record — SIGMA v0.1.6 release

On 2026-10-30, the operator assigned Red ownership of release preparation,
local validation, release PR review and merge, GCP deployment, and production
smoke testing from the latest `main`. The operator explicitly authorized Red to
review and merge its own release PR. GitHub Actions is unavailable through
October 31 because of account billing/budget restrictions; the release gate for
this deployment is one clean `./sigma test` on the exact release candidate,
release-specific validation, and production deployment/smoke testing. Do not
modify Actions configuration or wait for Actions. Preserve production identity,
configuration, persistent projects, research, and accounting; avoid paid AI
calls, paper-quality work, Round 11, and unrelated product changes.

The release version is v0.1.6, following the deployed v0.1.5. Release source
must be the tested merged candidate SHA. The existing snapshot
`sigma-state-v015-pre-20261030-0506` predates the v0.1.5 deployment, so it is
not by itself a current recovery point for this release. The remaining release
record must include the fresh recovery point and restore evidence, exact image
labels/IDs, deployment result, and smoke-test outcome. No v0.1.6 tag is
authorized by this record.

## Authorization record — SIGMA v0.1.7 regular production deployment

On 2026-10-30, the operator authorized Red to deploy the latest merged `main`,
including the domain-authorization fix in PR #389 and the maintenance-page
implementation in PR #385. PR #385 merged at
`31ba6c4aba1ed59d2d7e092f589b882d7f134b30`; its exact-head CI passed, and CI on
the merge commit passed in [run 41176581580](https://github.com/bkramerext/sigma/actions/runs/41176581580)
before preparing the v0.1.7 candidate. The product version must be bumped to
v0.1.7 in the Python project, uv lock, frontend
package, and npm lock. Red may review and merge the version-bump PR after its
required CI succeeds. Deploy from the tested merged `main` SHA. No separate
release tag is part of this deployment.

The operator authorized the routine deployment, maintenance cutover, isolated
restore drill, and temporary-resource cleanup without further human approval.
Red owns the recovery and maintenance windows. Verify live billing, quota, and
least-privilege access; cap incremental recovery-drill resources at $25; retain
the READY snapshot and remove only the temporary recovery VM and clone disk.
Preserve identities, projects, research history, papers and accounting. Do not
make unrelated infrastructure/IAM changes, enable recurring backups, or make
paid provider calls. Keep production untouched if a required recovery, exact-SHA
CI, host-preflight, or smoke-test gate fails.

## v0.1.7 pre-deployment restore drill — 2026-10-30

Snapshot `sigma-state-v016-pre-20261030-1122` was READY from source disk
`sigma-state` (created 2026-10-30 11:22:22 PDT). The production host was on
`0e51d20341ea5656f971e075b466694393e25d97` when inspected. A temporary
`e2-standard-2` recovery VM had no external IP and no service account. Its
30 GB clone disk `sigma-state-restore-red-20261030`, filesystem UUID
`28ef67cb-4da8-46e7-9a8b-dce0470153a5`, was attached read-only and mounted with
`ro,nosuid,nodev,noexec,norecovery`.

The offline verifier from the candidate checkout passed with the prior verified
aggregate thresholds:

```sh
sudo python3 /tmp/verify-state-restore.py /mnt/sigma-restore \
  --min-workspaces 3 --min-projects 12 --min-artifacts 30 --min-papers 0
```

Observed: three SQLite integrity checks passed; 3 identities/workspaces map to
3 distinct directories; 12 projects; 30 research artifacts; zero saved paper
pairs; 10 terminal historical job rows across two unmapped workspaces; and 17
accounting call rows with five reserved or unknown outcomes preserved. The
verifier returned `PASS: all restore checks completed read-only`. The recovery
snapshot remains retained. Temporary VM/disk cleanup and removal of temporary
SSH metadata completed 2026-10-30 23:30 PDT. The recovery VM and clone disk are
absent; only the production VM and its two disks remain. The pre-existing
project SSH key entry was preserved and the temporary `ubuntu` mapping removed.
The SSH troubleshooting command briefly enabled
`networkmanagement.googleapis.com`; it was disabled immediately and verified
disabled. This deviation made no persistent API or SSH-access change.

The active host Caddy is version 2.6.2. Its `caddy validate` check passed on the
candidate maintenance Caddyfile after using the version-compatible unqualified
`handle_errors` form. Validation warned that the maintenance import glob has no
matching files while the host snippet directory is still absent; installation
will create that directory and final validation will be repeated before reload.
