# SIGMA Deployment Runbook

**This is the only routine production-release procedure.** It is for an
explicitly authorized, frozen release SHA—not for a moving `main`. CI success,
documentation work, or a merged PR does **not** authorize deployment. While
development continues, do not freeze a new SHA, start a restore drill, or
change production unless the operator explicitly authorizes the release.

**Completion contract:** an unattended assignment ends with the selected
version/SHA verified healthy in production **or** a concrete safety blocker
and the last safe state. Keep working through routine failures; do not
substitute issue updates or PR preparation for completing an authorized
deployment. No Owner fallback, broad IAM grants, destructive state changes,
unbounded resources, or paid inference.

**Path:** freeze SHA and reuse CI → verify effective access, billing/quota and
schema → take and restore-verify an application-consistent snapshot → run the
existing guarded cutover helper → verify production, cleanup and record results.

See [Operations Runbook](OPERATION_RUNBOOK.md) for host/incident procedures and
[Deployment History](DEPLOYMENT_HISTORY.md) for previous release authorizations,
old compatibility notes, and historical outcomes. Archived procedures are not
an alternate routine-release checklist.

## Coordinator-led release handoffs (SIGMA v0.3.0)

For this release the **Coordinator is the release driver** and Red (Codex)
performs only the operational stage explicitly delegated to it. This
stage-by-stage handoff **supersedes the general unattended completion
instruction for this release**: Red must stop at the end of each assigned
stage and return its evidence. The operator forwards Red's response to the
Coordinator, who determines the next step. No extra approval is necessary
for read-only checks, but a successful handoff is **not** permission to
proceed to the next stage.

**Stage A execution-environment preflight (do this first).** Before calling
any host or cloud check, confirm Red is in a checkout of this repository
whose \`origin/main\` contains this Coordinator-led v0.3.0 section. Local
working directories and older branches can contain historical v0.1.x
runbooks; a stale local file is **not** current operational guidance.
Read the current maintained runbook from \`origin/main\` (fetch first) or
from the repository's live default branch, without overwriting untracked
work. If the checkout cannot be updated/read, report an
\`ENVIRONMENT_UNAVAILABLE\` failure instead of diagnosing GCP.

Confirm the **Google Cloud SDK exists in the execution environment**.
The v0.2.2 operator log used
\`/Users/admin/google-cloud-sdk/bin/gcloud\`; check \`command -v gcloud\`
and that path, but do not assume every Codex shell is the same host.
Use only the established keyless impersonation configuration. An
unavailable SDK or credential/impersonation facility is
\`ENVIRONMENT_UNAVAILABLE\`, **not** evidence that a GCP permission was
denied. Do not install SDKs, create credentials, SSH keys, aliases, or
IAM grants to conceal an unavailable runtime. Return the blocker and
ask the Coordinator for the existing GCP-enabled operator environment.

**Identity versus destination:** \`sigma-release-ssh\` and
\`sigma-release-operator\` are **service-account names**, not SSH host
aliases. The destination is the actual Compute VM \`sigma-gce-01\`,
accessed with \`gcloud compute ssh ... --tunnel-through-iap
--impersonate-service-account=...\`. Never run
\`ssh sigma-release-ssh\` or direct public SSH as a substitute.
For example, with \`GCLOUD\` set to the verified SDK executable:

```sh
"$GCLOUD" compute instances describe sigma-gce-01 \
  --project=sigma-research-prod --zone=us-west1-b \
  --impersonate-service-account=sigma-release-ssh@sigma-research-prod.iam.gserviceaccount.com \
  --format='value(name,status)'
"$GCLOUD" compute ssh sigma-gce-01 \
  --project=sigma-research-prod --zone=us-west1-b --tunnel-through-iap \
  --impersonate-service-account=sigma-release-ssh@sigma-research-prod.iam.gserviceaccount.com \
  --command='sudo -n true'
```

The second command is a **read-only access/sudo capability test**, not
permission to change the VM. Inspect global/zonal operation reads under
\`sigma-release-operator\` using **existing** operation IDs as required
below. Do not create a recovery VM in Stage A; its IAP connection is
a Stage C test. Public HTTPS/JavaScript or hosted-auth readiness
checks are only supplementary: they cannot prove the full production
SHA, host health, state mount, IAM, or quotas.

In Stage A's mandatory \`FAILED\` response distinguish
\`ENVIRONMENT_UNAVAILABLE\` (wrong checkout, SDK absent, no authorized
impersonation runtime) from \`GCP_PERMISSION_DENIED\` (a real API 403
through the actual impersonated account), and from \`UNVERIFIED\`
(no suitable read-only evidence). Never prescribe an IAM grant without
a real impersonated-denial response.

| Stage | Owner | Scope / advancement gate |
| --- | --- | --- |
| **A — Access readiness** | Red, then Coordinator review | Read-only, impersonated GCP access and host health checks: actual production-host IAP/OS Login and noninteractive sudo, effective global/zonal operation-status polling, disk/snapshot reads, quota, and a bounded cost estimate with truthful billing limitations. No recovery VM exists in this stage, so its live IAP test belongs to Stage C. Do not stop writers, create recovery resources, change IAM, build images, or deploy. A missing required permission is **FAILED** with the exact denial and narrow proposed remedy; prior v0.2.2 success alone is not proof. |
| **B — Source and release freeze** | Coordinator, with Red on separately delegated repository tasks | Draft release notes and version 0.3.0 preparation can proceed while main changes. **Do not freeze a commit until the operator says the source is ready.** Confirm all versioned files and release notes agree, select the final merged 40-character SHA, and reuse that SHA's passing CI. A moving branch or green tests alone never authorize cutover. |
| **C — Fresh recovery verification** | Red, after Coordinator go-ahead | With Stage A access proven and a frozen Stage B SHA, perform only the documented application-consistent snapshot, isolated read-only restore verification, and bounded cleanup (steps 3–6 below). Retain the verified snapshot. Report the snapshot/restore evidence and any downtime; **do not cut over** in this stage. |
| **D — Guarded cutover and production acceptance** | Red, after Coordinator go-ahead | Confirm Stage C evidence and schema compatibility, run the existing guarded helper for the exact frozen SHA (step 7), then complete step 8 and the release record. Never repeat an uncertain cutover without reconciling production's actual release pin and image provenance. |

**Mandatory response after *each* Red stage:** the first line must be
\`SIGMA v0.3.0 | STAGE <A/B/C/D> | SUCCEEDED\` or
\`SIGMA v0.3.0 | STAGE <A/B/C/D> | FAILED\`.
Then report (1) exact commands/checks and observed evidence (redacted),
(2) source SHA and production SHA if checked, (3) permissions or recovery
resources created/deleted, (4) health and data/maintenance state, (5) any
unresolved gate and the smallest safe next action. The response is meant
to be copied verbatim to the Coordinator. **SUCCEEDED** means every assigned
gate is established; **FAILED** includes a partial result, unsupported
attestation, timed-out operation, or genuine safety block. Never turn a
failed check into implicit success. Both statuses end the current stage:
wait for the Coordinator's next explicit handoff.

**Operational safeguards:** no Owner/Editor fallback, long-lived keys,
unapproved IAM broadening, paid inference, state deletion, or data restore.
Keep the pre-release downtime and incremental recovery spend within the
existing $25 ceiling and record truthfully what was actually verified.
The Coordinator owns sequencing and repository documentation; Red owns
on-host/GCP execution and observation. Work on v0.3.0 **does not itself
authorize a production deployment** until the frozen release and stages
are explicitly advanced.

## Routine keyless GCE release — canonical ordered path (issue #667)

Follow these eight gates in order only after a separate release authorization
selects the target. Check the selected commit and effective live permissions;
never infer results from past release records. Current production inventory is
maintained in [OPERATION_RUNBOOK.md](OPERATION_RUNBOOK.md).

1. **Freeze and establish source provenance.** Choose an approved, merged,
   full 40-character SHA. Record exact-SHA successful Ruff, SIGMA verification,
   and browser workflow run URLs and the resolved commit. Reuse those green
   results even if `main` has advanced. Do **not** rerun workflows on moving
   `main` or require a second full `./sigma test` on `main`. If an exact-SHA
   required check is absent, failed, or superseded by a change to the **selected
   source**, run the missing source CI against the newly frozen SHA. Run
   release-artifact and operational checks independently; a passing commit
   check is not a backup, access, or deployment proof.
2. **Preflight the effective keyless identities and budget, not just IAM
   configuration.** Use short-lived impersonation of
   `sigma-release-ssh@sigma-research-prod.iam.gserviceaccount.com` for the
   production host and
   `sigma-release-operator@sigma-research-prod.iam.gserviceaccount.com`
   for snapshots and isolated recovery. Verify billing, quota, expected
   recovery footprint/duration (at most **$25 incremental**), current
   state-disk mount and UUID, systemd/container health, protected release pin,
   schema compatibility, and maintenance-off state. Test **actual**
   `gcloud compute instances describe` and
   `gcloud compute ssh --tunnel-through-iap` with each relevant impersonated
   identity, including noninteractive `sudo -n true` on the intended VM.
   For `gcloud compute ssh`, `compute.instances.get` must be effective on
   the production host for the host identity and on the temporary recovery
   VM for the recovery identity. Both identity paths were demonstrated
   during v0.2.2, but must be retested for the target release. If denied,
   investigate the smallest missing instance-read permission under #590,
   then retest using the **same identity and command**. Never fall back
   to the project Owner, broaden to Owner/Editor, or create a key.
   **A denied connection is a release blocker, not a passed preflight.**

   **Preflight operation polling before stopping production writers.** The
   2026-11-08 v0.2.2 snapshot request was accepted, but `gcloud` reported
   HTTP 403 while waiting because the recovery identity lacked
   `compute.globalOperations.get`. Snapshot creation involves a **global**
   operation; zonal disk/VM create, attach and delete involve **zonal**
   operations. Verify the impersonated recovery identity can actually read a
   known recent operation of each required scope using
   `gcloud compute operations describe OPERATION --global` or
   `--zone=us-west1-b`, respectively, with `--project` and
   `--impersonate-service-account`. Required read permissions are
   `compute.globalOperations.get` and `compute.zoneOperations.get`
   (and `compute.regionOperations.get` only if the chosen procedure uses
   regional operations). A successful resource `describe` does **not** prove
   permission to poll its operation. Grant only the missing, narrowly scoped
   operation-read permissions under #590/#667 and retest with the **same
   impersonated identity**; never grant Owner/Editor or use human Owner
   access. If there is no valid existing operation to test, mark the gate
   **unverified**, not passed, and resolve it before downtime. Do not
   repeatedly stop production to discover missing permissions.

   **Outstanding IAM follow-up:** v0.2.2 proved both keyless IAP/OS Login
   paths end-to-end but not operation-polling permissions. #667/#590 track
   the narrow read-only fix. Do not accept the previous successful resource
   reads as a substitute for the operation-read preflight on the *next*
   deployment; see the [v0.2.2 outcome](OPERATION_RUNBOOK.md#sigma-v022-deployment-outcome-2026-11-08-utc).
3. **Create a fresh application-consistent snapshot.** Declare the approved
   maintenance window and verify baseline identity, project, paper, job and
   accounting counts. Stop SIGMA writers cleanly on `sigma-gce-01`, sync the
   persistent state disk, and create a fresh snapshot of **`sigma-state`**
   using the recovery identity. The existing IAM condition currently
   permits snapshot names beginning `sigma-state-v021-pre-` (a legacy
   resource prefix, **not** the version to deploy); change the name only
   after a narrowly reviewed IAM update.
   **Do not pass `--labels`**: this path does not grant
   `compute.snapshots.setLabels`, and snapshot name, source, creation time,
   immutable ID and verification evidence are sufficient. With `PROJECT`,
   `ZONE`, `SNAPSHOT`, and `RECOVERY_ID` set to reviewed exact values
   (for example, project `sigma-research-prod`, zone `us-west1-b`),
   the label-free snapshot command is:
   ```sh
   gcloud compute snapshots create "$SNAPSHOT" --project="$PROJECT" \
     --source-disk=sigma-state --source-disk-zone="$ZONE" \
     --storage-location=us-west1 \
     --impersonate-service-account="$RECOVERY_ID"
   ```
   Wait for READY
   and confirm source disk, snapshot ID, and creation timestamp. Restart
   SIGMA and recheck health as soon as consistency is captured. If a
   snapshot cannot be verified, stop the release; do not claim
   `--backup-verified`. **If `gcloud` reports a polling/permission failure
   after submission, the create request may already have succeeded.**
   Restart the service promptly, inspect the uniquely named snapshot using
   the recovery identity, record its ID/source/status, and reconcile before
   retrying. Never create a duplicate or assume a polling 403 means no
   snapshot exists. A `READY` snapshot is **captured**, not yet a
   **verified restore** (step 5).
4. **Isolate the recovery clone in one creation pass.** Under the recovery
   identity, create a clone disk `sigma-state-restore-*` from that exact
   READY snapshot and a `sigma-v021-recovery-*` VM in `us-west1-b`.
   Use an approved Ubuntu image, bounded machine/disk size, the existing
   `sigma-us-west1` subnet, `--no-address`,
   `--no-service-account`, `--no-scopes`, `--tags=sigma-iap-ssh`, and
   `--metadata=enable-oslogin=TRUE,block-project-ssh-keys=TRUE` **at initial
   VM creation**. The project IAP-only firewall selects the
   `sigma-iap-ssh` network tag. Do not attach any production credentials
   or the production disk. Attach the clone **READ_ONLY** (`--mode=ro`);
   inspect the device/UUID, mount ext4 only with
   `ro,noload,nosuid,nodev,noexec,norecovery`, and verify flags via
   `findmnt`. Never format, fsck-repair, or mount the clone read/write.
   Connect through IAP/OS Login with the recovery identity, not Owner.
   The IAM conditions still permit legacy `sigma-v021-recovery-*`
   resource names; they do not constrain the application release version.
   Any new naming prefix requires an explicit narrow IAM review. With `CLONE_DISK=sigma-state-restore-*`
   and `RECOVERY_VM=sigma-v021-recovery-*` set to unique, verified actual
   names (no literal asterisks), create and attach once:
   ```sh
   gcloud compute disks create "$CLONE_DISK" --project="$PROJECT" --zone="$ZONE" \
     --source-snapshot="$SNAPSHOT" --type=pd-balanced \
     --impersonate-service-account="$RECOVERY_ID"
   gcloud compute instances create "$RECOVERY_VM" --project="$PROJECT" --zone="$ZONE" \
     --machine-type=e2-standard-2 --image-project=ubuntu-os-cloud \
     --image-family=ubuntu-2404-lts-amd64 --subnet=sigma-us-west1 \
     --no-address --no-service-account --no-scopes --tags=sigma-iap-ssh \
     --metadata=enable-oslogin=TRUE,block-project-ssh-keys=TRUE \
     --impersonate-service-account="$RECOVERY_ID"
   gcloud compute instances attach-disk "$RECOVERY_VM" \
     --project="$PROJECT" --zone="$ZONE" --disk="$CLONE_DISK" \
     --device-name=sigma-state-restore --mode=ro \
     --impersonate-service-account="$RECOVERY_ID"
   ```
   Confirm actual disk attachment is read-only before mounting. Abort
   safely on any create/attach failure; do not recreate with weaker flags.
   Use normal completion polling with the correct scoped operation-read
   permissions. `gcloud compute snapshots create` supports `--async`,
   but the documented `gcloud compute disks create` does not: **do not
   use `--async` as a general substitute for IAM**. If a create/attach
   reports an ambiguous failure, inspect the exact named resource and its
   state before any retry. Do not advance with unverified operations.
5. **Verify the isolated restore, read-only.** Transfer the verifier from
   the **selected exact SHA** to the isolated recovery VM and run
   `deploy/verify-state-restore.py` against the mounted filesystem with
   thresholds established from pre-snapshot observations. Require all
   database/integrity, workspace isolation, saved project/artifact,
   TeX/PDF hash/size, and accounting checks to pass. The verifier accepts
   only the known sealed `.publication-reference-compilation.json` cache
   as non-paper metadata; actual paper JSON/PDF records remain strict.
   An unexpected workspace or empty scheduler slot-lock marker is **not**
   permission to delete anything: inspect the workspace, referenced project,
   jobs, calls, file sizes, and retained history read-only. Quarantine or
   remove only independently proven disposable markers under separately
   documented authorization and preserve a pre-cleanup recovery snapshot.
   Never delete user, project, session, paper, identity, or accounting data
   just to satisfy verifier counts. Any unresolved mismatch blocks cutover.
   Use the verifier from the **selected release SHA** for the pre-snapshot
   production baseline too, not an older installed verifier that may reject
   newer valid metadata. Only a passing **isolated read-only
   restore**, not a `READY` snapshot alone, permits `--backup-verified`.
6. **Clean up bounded recovery resources and retain evidence.** Record
   verifier results, clone UUID/mount flags, timings, and source snapshot.
   Unmount, detach, delete the temporary `sigma-v021-recovery-*` VM and
   `sigma-state-restore-*` clone (including its temporary boot disk),
   and verify both are absent. **Retain the validated pre-release snapshot**.
   Clean up failed partial creations too, within the same authorized
   prefixes and $25 limit, without erasing evidence. If cleanup fails,
   report the resource/cost blocker before any new cutover.
7. **Guarded exact-SHA build and cutover.** Reconfirm the approved SHA,
   state/mount, green source checks, fresh verified recovery, and actual
   schema-compatibility evidence. Using the keyless production-host IAP
   connection, run only:
   ```sh
   sudo python3 /opt/sigma/current/deploy/deploy-gce-release.py FULL_40_CHAR_SHA \
     --backup-verified --schema-compatible
   ```
   These flags are truthful attestations, **not** checks; never infer them
   from the existence of a snapshot or from green CI. The helper builds
   both images from the exact commit; do not pass `--no-build`. Do not
   modify `SIGMA_RELEASE` or restart containers outside the guarded helper
   to work around a failure.
8. **Verify, record, and exit.** Confirm host checkout, release record,
   immutable image IDs and SHA labels, About build prefix, active systemd,
   healthy backend/frontend/edge, retained state disk UUID/mount options,
   production data and accounting counts, HTTPS, auth readiness, expected
   anonymous API behavior, and **maintenance off**. Do not run paid
   inference. Record observed start/end/downtime, source CI run URLs,
   snapshot/restore proof, identity used, **operation-polling permission
   evidence**, any writer-stop downtime (including failed attempts),
   security gate results, cleanup confirmation, and remaining
   authenticated-test limitations. Keep the
   previous release/image and recovery point for forward-fix or separately
   authorized rollback decisions; a code rollback is never a data restore.

**Compact evidence checklist** (record observed values, not assumptions):
`release ticket + SHA + exact-SHA CI URLs`;
`effective SSH/recovery connections + global/zonal operation-read permissions + IAM denials`;
`preflight + quota/billing + <=$25 estimate`;
`snapshot name/ID/source/READY/UTC`;
`clone/VM flags + read-only mount + verifier results/counts`;
`VM/disk deletion and snapshot retention`;
`helper command + image IDs/labels + cutover times`;
`HTTPS/auth/About + maintenance off + data/accounting preservation`;
`no paid inference + limitations`.

A documented dry-run is **not** live-credential acceptance. The v0.2.2 release
demonstrated keyless host access and isolated recovery with no Owner fallback.
Issue #667 remains open for the missing narrowly scoped operation-read
permissions and a clean repeatable preflight at a *future separately
authorized* release; housekeeping does not authorize one.

Historical authorizations, release controls, schema-specific rollback notes
and past cutover records are retained in
[DEPLOYMENT_HISTORY.md](DEPLOYMENT_HISTORY.md), **not** as additional steps
for the next release.
