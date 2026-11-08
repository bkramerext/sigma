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

**Default paid-infrastructure path:** freeze SHA and reuse CI → verify access,
schema and quota → take and restore-verify an application-consistent snapshot
using isolated recovery resources → guarded cutover → verify and record.
**The v0.3.0 no-new-resource override below supersedes the paid snapshot path.**

See [Operations Runbook](OPERATION_RUNBOOK.md) for host/incident procedures and
[Deployment History](DEPLOYMENT_HISTORY.md) for previous release authorizations,
old compatibility notes, and historical outcomes. Archived procedures are not
an alternate routine-release checklist.

## SIGMA v0.3.0 — routine Red-owned release (current)

**Current state:** Production is healthy on v0.2.2, SHA
`469c955dfadb5a7bd17b72fc069a3365b4f20ba7`.
The earlier IAM operation-polling permissions were repaired and
successfully retested with the keyless recovery identity. See
[Operations Runbook](OPERATION_RUNBOOK.md) for that evidence.

**Only remaining operator handoff:** Development is ongoing. When the
operator says **main is ready** and provides the frozen full release SHA,
Red owns the deployment end to end. Do not request additional
routine stage approvals, recovery-policy questionnaires, fresh IAM
privileges, or billing-budget evidence merely to perform the release.
Reuse the selected SHA's passing CI. Do not freeze a moving `main`.

**No added deployment-protection spending:** Do not provision a new
recovery VM, disk, snapshot, bucket, service or additional paid storage;
the older cloud recovery drill in the reference procedure below is
**not** the v0.3.0 path. No paid inference or Owner-account fallback.
Keep existing snapshots and production infrastructure unchanged.

**v0.3.0 release sequence on already-provisioned infrastructure:**

1. **Preflight:** Verify production health, release pin, mount UUID,
   remaining space on the *existing* boot disk, maintenance state,
   keyless IAP/sudo and final source/schema compatibility. Reuse the
   already-established IAM results unless a new effective denial occurs.
2. **Current-data safety:** Stop SIGMA writers cleanly; take a full
   consistent copy of `/srv/sigma-state` onto a separate root-only
   directory on the **existing boot disk**, preserving ownership and
   metadata. Confirm source and destination really are separate disks.
   Compare a complete manifest/hashes and run the frozen release's
   read-only `deploy/verify-state-restore.py` against the copy, with
   fresh project, paper, identity and accounting baseline thresholds.
   Do not claim `--backup-verified` if this verification fails.
3. **Deploy:** Once backup verification and actual schema compatibility
   both pass, run the already-established guarded exact-SHA helper,
   using its truthful `--backup-verified --schema-compatible` flags.
   Do not introduce alternative cutover methods or override a failure.
4. **Accept:** Verify the release pin, immutable image SHAs,
   backend/frontend/edge health, stored data/accounting, public
   HTTPS/auth/About and maintenance off. Keep the protected copy for
   short-term rollback; record its path and storage impact.
   No destructive automatic data restore if an upgrade fails.

A same-host copy addresses many **software-update** failures, but
does **not** protect against losing the entire VM, boot disk or zone.
That limitation is recorded here; it is **not** a separate approval
question or another release-stage handoff. An actual failed copy,
broken integrity check, incompatible migration, or failed health check
is a genuine technical blocker: keep the last safe state and report
the precise issue. Do not manufacture additional hypothetical gates.

**Before main is ready:** Red may validate the procedure with synthetic
data or review existing infrastructure read-only. No live writer stop,
live backup, cutover, deployment SHA or new resources until the operator
declares the release ready.

## Routine keyless GCE release — canonical ordered path (issue #667)

**For v0.3.0, use the short release sequence above.** Steps 3–6
below document the historical cloud snapshot/recovery-VM procedure
and are **not authorized** for this release. Keep technical checks
honest and do not allocate additional infrastructure.

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
   `compute.globalOperations.get`, `compute.zoneOperations.get`, and
   `compute.zoneOperations.list` when an existing zonal operation ID must
   be discovered (and regional operation permissions only if that path is
   used). A successful resource `describe` does **not** prove
   permission to poll its operation. Grant only the missing, narrowly scoped
   operation-read permissions under #590/#667 and retest with the **same
   impersonated identity**; never grant Owner/Editor or use human Owner
   access. If there is no valid existing operation to test, mark the gate
   **unverified**, not passed, and resolve it before downtime. Do not
   repeatedly stop production to discover missing permissions.

   **Confirmed v0.3.0 IAM repair:** all three operation-read permissions
   have now been proven through the impersonated recovery identity on
   existing global/zonal operations (details above). Keep the
   effective-access test as a future regression gate. A fresh
   application-consistent backup remains required at cutover, using
   the existing boot-disk copy described above.
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

**Default paid-infrastructure evidence checklist** (not approved for
v0.3.0 under the zero-new-resources restriction; record observed values,
not assumptions):
`release ticket + SHA + exact-SHA CI URLs`;
`effective SSH/recovery connections + global/zonal operation-read permissions + IAM denials`;
`preflight + quota/billing + <=$25 estimate`;
`snapshot name/ID/source/READY/UTC`;
`clone/VM flags + read-only mount + verifier results/counts`;
`VM/disk deletion and snapshot retention`;
`helper command + image IDs/labels + cutover times`;
`HTTPS/auth/About + maintenance off + data/accounting preservation`;
`no paid inference + limitations`.

**v0.3.0 existing-infrastructure evidence checklist:**
`frozen SHA + exact-SHA CI`;
`verified state/boot disk identities, free space and root-only backup path`;
`all writers stopped + complete copy + manifest hashes/metadata`;
`selected release verifier run on copied tree + baseline/ledger integrity`;
`schema and write-gate compatibility + guarded cutover command`;
`running image SHA/IDs + production counts/HTTPS/About + maintenance off`;
`retained boot-disk backup path and limited recovery/retention caveats`;
`no new cloud resources, no paid inference, no destructive auto-restore`.

The v0.3.0 IAM operation-read denials were resolved and tested; do not
reopen them without a new effective failure. The only remaining
operator handoff is the declaration that the final application SHA
is ready. Red should work end-to-end once that SHA is supplied, stopping
only for a concrete technical failure or unauthorized spending.

Historical authorizations, release controls, schema-specific rollback notes
and past cutover records are retained in
[DEPLOYMENT_HISTORY.md](DEPLOYMENT_HISTORY.md), **not** as additional steps
for the next release.
