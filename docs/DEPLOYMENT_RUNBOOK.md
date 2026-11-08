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

## SIGMA v0.3.0 — Red-owned deployment and current IAM blocker

**Status (2026-11-08): HELD for current billing evidence and a new release
source SHA.** Production remains v0.2.2 at
`469c955dfadb5a7bd17b72fc069a3365b4f20ba7`. The original recovery
identity operation-status IAM denial has been repaired and retested
successfully (details below). No writers have been stopped, no snapshot or
recovery VM/clone created, and no deployment has occurred. A one-time
explicitly approved **IAM-only** use of the existing Owner account
completed; this authorization does **not** extend to billing inspection
or release execution.

**Owner and authority.** Red owns the complete routine deployment after
preflight is repaired and a new release SHA is approved: evidence, recovery
drill, guarded cutover, production acceptance, cleanup, and records. Red
should work through ordinary recoverable problems without Coordinator
stage handoffs, and end with an explicit `DEPLOYMENT SUCCEEDED` or
`DEPLOYMENT FAILED` report. A real safety gate stops work; Red must not
waive that gate, use project Owner/Editor as a fallback, or infer a passed
permission check from a prior deployment. A completed docs PR is not a
completed release.

**Release freeze is on hold while new UI/features are being merged.** The
earlier v0.3.0 cutoff `ef463bd0fb06dcd9f437651d6dff803bd206b545`,
version-bump SHA `063d980f31161792068c8957beb134ca81caa10b`,
and candidate `a53e50cd9ba076a8e4996acf8ebe590159fbdf08` are
**historical release candidates, not current deployment authorization**.
When the operator declares `main` ready again, freeze a new **full** SHA
from merged `main`; verify v0.3.0 version, review delta/release notes,
and reuse passing CI tied to that exact SHA. Do not begin writer downtime
or cutover with a previous candidate merely because its CI was green.

### Pre-freeze readiness: finish everything independent of the next SHA

The source is still changing. **Red owns this preparation and should
continue without Coordinator turn-taking.** This work may run now, before
a new `main` SHA is selected, provided it does not modify production.
Do not start recovery snapshots/VMs, stop writers, invoke the guarded
deploy helper, enable maintenance, or claim v0.3.0 was deployed.

1. **Access and IAM — PASSED:** The authorized one-time IAM repair was
   completed and the recovery identity described one real global and one
   real zonal `DONE` operation. Preserve the existing binding; retest
   it after any future IAM change. No Owner account for deployment.
2. **Host and topology:** Reconfirm IAP/OS Login, noninteractive
   `sudo -n true`, systemd/Compose and all three containers, release
   pin, disk UUID/mount flags, quotas, and available recovery instance
   and disk types. Do not alter anything to produce a green check.
3. **Billing — BLOCKED:** An authorized **billing-account viewer** must
   confirm via Cloud Console (or a pre-existing legitimate read-only
   API path) that project `sigma-research-prod` is still linked to an
   active billing account, its relevant budget and alert thresholds are
   present, and current costs/spend are visible or honestly unavailable.
   The Cloud Billing API is disabled; **do not enable it**, widen billing
   IAM or use the personal Owner account for billing under the separate
   IAM-only authorization. The previous October budget/credit evidence
   is historical. Budget alerts are **not** hard spend caps. The latest
   modeled recovery cost is **$16.11**, or **$21.11 including $5
   contingency**, versus a mandatory $25 incremental ceiling. This is
   modeled, not billed. Do not create recovery resources before current
   billing association and budget evidence is supplied.
4. **Maintenance and baseline:** Inspect the existing maintenance
   switch state and confirm the public site is serving normally.
   Prepare the read-only identity, project, paper, job and accounting
   queries, baseline thresholds, and the restore-verifier invocation.
   Capture a *fresh* baseline close to the actual snapshot, not from
   old v0.2.2 numbers. Do not run paid inference.
5. **Readiness proof:** Record the checked environment, impersonated
   identities, commands, statuses, quotas/costs, and remaining
   limitations in one concise readiness report. If all source-independent
   gates pass, mark **READY FOR SHA**; otherwise name the actual blocked
   gate and the smallest administrative corrective action. Do not
   convert `UNVERIFIED` into `PASS`.

Only when the operator says development is finished does Red select the
new approved merged SHA. Then verify backend/frontend 0.3.0, update
release notes, reuse exact-SHA green CI, perform final schema-compatibility
review against the *actual selected commit*, and recapture the live
data/accounting baseline. Proceed with the existing snapshot/restore,
guarded cutover, acceptance, cleanup, and merged deployment record
without routine intermediary approval requests. Stop only on a genuine
safety gate or a task requiring new privileges/scope.

**Expired operation IDs:** Operations are retained for a limited time.
An expired or unavailable ID is `UNVERIFIED`, not IAM denial. Do not
create cloud resources merely to prove `.get` before the release.
Gather known operation IDs from the previous release evidence and
prove existing `.list` where applicable. If no IDs remain, record
the verified grant, absence of operations, and the remaining actual-get
test as a gate to resolve before writer downtime; do not invent a
success or repeat the same blocked request.

### IAM readiness — completed after explicit one-time authorization

The operator **explicitly authorized** a one-time use of the existing
personal Owner account for **only** the minimum operation-read IAM
bootstrap. Red created custom project role `sigmaOperationMetadataReaderV1`
containing exactly:

- `compute.globalOperations.get`
- `compute.zoneOperations.list`
- `compute.zoneOperations.get`

The role was bound **without a resource-name condition** to **only**
`sigma-release-operator@sigma-research-prod.iam.gserviceaccount.com`.
Other IAM bindings, the original Owner grant, and the existing
recovery-discovery role were preserved. Owner use ended after the IAM
repair; no broader IAM or service-account keys were created.

**Effective permission test: PASS.** With the existing short-lived
impersonated recovery account (not Owner), Red listed existing zonal
operations and successfully described:

- Zonal `operation-1794153415633-65fc5e502e935-d1ec7554-4d9d3a8e`
  — `DONE`.
- Global `operation-1794152778212-65fc5bf04a54f-24773804-b221c4f8`
  — `DONE`.

Those existing operation names are historical evidence, not guaranteed
to remain available; retest after IAM changes. The denied
`getIamPolicy` permission is unnecessary for routine release polling.
**No further Owner access is authorized**, including for billing or
cutover.

### Host, storage, network, and recovery readiness

**Source-independent checks completed by Red (2026-11-08):**

- Production is v0.2.2, full SHA
  `469c955dfadb5a7bd17b72fc069a3365b4f20ba7`,
  checkout and release pin agree; systemd is active and backend,
  frontend, and edge containers are healthy.
- IAP/OS Login and `sudo -n true` passed via the host-only
  `sigma-release-ssh` identity.
- `/srv/sigma-state` is mounted ext4 from `/dev/sdb`, UUID
  `28ef67cb-4da8-46e7-9a8b-dce0470153a5`;
  `auth` is owned by 10001:10001 and mode 0700.
- Maintenance is **OFF** (`/etc/caddy/sigma-maintenance/active.caddy`
  absent); Caddy configuration validates. Public DNS/TLS,
  redirect, root, SPA deep-link, private-port exposure, and
  hosted API probes passed. The anonymous health endpoint
  appropriately returned HTTP 401.
- Quotas: CPUs 4/100, instances 1/24, persistent disk 100/2458 GiB,
  SSD disk 30/300 GiB, snapshots 12/1000. The recovery subnet is
  readable; `e2-standard-2` is available in `us-west1-b`.
- Read-only **live baseline** from the installed v0.2.2 restore
  verifier: 3 identities/workspaces, 17 projects, 42 artifacts,
  one saved TeX/PDF pair verified by SHA-256 and size, 10 terminal
  jobs in two unmapped historical workspaces, 46 accounting calls
  recording $5.938237, including 15 reserved/unknown outcomes;
  all three SQLite integrity checks passed. This is **not** an
  isolated snapshot restore and does **not** prove new-release schema
  compatibility. Re-run the frozen release verifier against the
  eventual restored clone, with fresh live baselines and careful
  preservation of all unmapped historical data.
- Both keyless identities were denied `compute.firewalls.list`.
  Production IAP SSH succeeds using the existing `sigma-iap-ssh`
  tag; the read-only inventory of firewall rules remains unavailable.
  A *future* recovery VM IAP connection cannot be demonstrated until
  that VM exists. Test the recovery identity and IAP after the
  carefully bounded VM is created in the **authorized restore drill**;
  do not broaden firewall visibility or create a VM merely for this
  early check. If actual recovery IAP fails, stop and remediate
  before accepting the restore.

**Remaining billing gate (no authorization to change billing):**
The Cloud Billing API is disabled, and the recovery identity cannot
view the account's budgets. Historical documentation of a $300 budget
and 50/75/90/100% alerts does not prove those controls are current.
A person **already authorized on the billing account** can provide
read-only Cloud Console evidence without granting Red any billing
permissions: project-to-account link, linked account active status,
current budget/thresholds and alert notification settings, and
available current spend/cost report. Google Cloud Billing Account
Viewer on the **billing account** is a documented read-only option
when an authorized billing administrator chooses to delegate;
this is not a request to grant it now. Record the date and redacted
evidence. If no authorized billing viewer can furnish it,
report **READINESS BLOCKED — BILLING_EVIDENCE**, not READY FOR SHA.

**Cost bound:** The incremental recovery scenario is modeled as
$16.11, or $21.11 with contingency, including an e2-standard-2 VM
for at most 24h, up to 100-GiB boot and 30-GiB clone disks,
and a 30-GiB standard snapshot retained up to 30 days. No
external IP or cross-region traffic; no paid inference.
Costs are estimates, not actual spend. Observe and clean up
temporary resources promptly, retain only the verified snapshot,
and stop when the $25 incremental ceiling cannot be supported.

**Stage A execution environment:** use the current maintained runbook
from `origin/main` and the approved keyless GCP operator runtime.
Confirm `gcloud` is available (`command -v gcloud` or previously used
`/Users/admin/google-cloud-sdk/bin/gcloud`) before testing access.
`sigma-release-ssh` and `sigma-release-operator` name **service accounts**,
not SSH hosts. The production destination is `sigma-gce-01`, through
`gcloud compute ssh ... --tunnel-through-iap --impersonate-service-account`.
An absent SDK is `ENVIRONMENT_UNAVAILABLE`, not GCP permission denial.

Proceed through the eight routine gates **below** only after these
preflight issues are resolved, the operator approves the new frozen SHA,
and appropriate exact-SHA CI is green. Preserve all existing recovery,
least-privilege, cost, state, and rollback safeguards.
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
   effective-access test as a future regression gate. The remaining
   source-independent blocker is current billing evidence.
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

A documented dry-run is **not** live-credential acceptance. The v0.2.2
release demonstrated keyless host access, but the v0.3.0 preflight confirmed
operation-read denials. The next release remains on hold until a separately
authorized IAM remediation is **effectively retested**, the selected v0.3.0
SHA is refreshed after ongoing feature work, and all safety gates pass.

Historical authorizations, release controls, schema-specific rollback notes
and past cutover records are retained in
[DEPLOYMENT_HISTORY.md](DEPLOYMENT_HISTORY.md), **not** as additional steps
for the next release.
