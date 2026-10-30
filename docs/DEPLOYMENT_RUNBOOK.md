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
recurring backup configuration, IAM broadening, destructive cleanup, or paid
provider inference. Keep the operator's constraints: preserve identities,
projects, research, papers, and spending records; do not access the operator's
local SIGMA server; do not coordinate directly with other Codex workers.

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
   and immutable image IDs. Do not substitute a tag or a moving branch name.
2. Before stopping production, verify the actual host checkout, protected
   `SIGMA_RELEASE`, running image tags/labels, mounted state disk, service
   health, and the last recovery point. Record observed values and resolve
   disagreements from host state and timestamped release records.
3. Use a fresh application-consistent state-disk snapshot and verify it by
   restoring a clone on an isolated host with no public ingress and no
   production service account or credentials. Establish the recovery
   verifier's aggregate thresholds before the drill. Record the approved
   maintenance window, required IAM, project quota/billing review, cost ceiling,
   recovery owner, and cleanup approval before creating temporary resources.
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
