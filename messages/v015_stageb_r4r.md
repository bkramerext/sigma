# RED R4R — SIGMA v0.1.5 Stage B readiness

**Ticket:** [#337](https://github.com/bkramerext/sigma/issues/337)

**PR:** separate readiness/correction PR from merged #338; PR URL will be
provided in the R4R notice after opening.

**Branch:** `red/v015-stageb-readiness`

**Base:** `main` at `bc275cb214d1fbec0fd40334593d50d82263c07e` (#338 merge).

**Release source SHA:** `2026f1e5b167ec76289ba2335d369603e4f377ee` (ancestor of
the base). It is the exact v0.1.5 candidate build input; do not substitute the
merge SHA for the release source SHA.

**Scope:** correction of stale #328/#329 Chrome assertions and Stage B
readiness evidence/runbook. This is ready for independent review. It is not a
production deployment request. Do not self-merge.

## Release-gate matrix

| Gate | Result | Evidence / condition |
| --- | --- | --- |
| Post-merge CI on exact `bc275cb…` | **MET** | GitHub Actions `verify` check run succeeded: [run 41000271025](https://github.com/bkramerext/sigma/actions/runs/41000271025/job/123882806127). |
| Exact v0.1.5 source identity | **MET** | `2026f1e5b167ec76289ba2335d369603e4f377ee`, ancestor of merge SHA. |
| Focused Chrome #328 and #329 | **MET** | Both scripts passed on fresh isolated temporary state with deterministic fixture API/provider replies; no local SIGMA server or paid provider call. |
| `./sigma test` on readiness branch | **MET** | All configured steps passed, including paper/release/deploy checks, Ruff, formatting, Pyright, frontend typecheck and build. Optional graph-present test skipped because local sandbox image is unavailable. |
| Active production v0.1.4 SHA | **MET** | Read-only host checkout, protected pin, runtime version and backend/frontend tags and OCI revision labels agree on `6fa626bdfc1f07cb873103dfed2323864d4fb280`. |
| Explanation of prior `2761c0e…` record | **MET** | Record timestamp 06:09:49Z preceded active `6fa626b…` record at 06:12:04Z; previous docs retained the earlier record as current. |
| Existing production data compatibility | **UNVERIFIED** | Source review found no destructive auth/workspace migration and v0.1.5 reads project schema 1–9, but production project/paper/artifact/accounting contents were not inspected. |
| v0.1.4 binary rollback after schema 10 writes | **UNMET** | Exact v0.1.4 parser was imported in an isolated temp package and rejected schema 10 (`expected 1 through 9`). No compatibility bridge exists or has been tested. Prefer forward-fix; treat restoring the earlier snapshot as a separate data-loss incident. |
| Fresh application-consistent snapshot and restore drill | **UNMET** | Existing `sigma-state-v014-20261029-0606` is READY but predates v0.1.4 and was not restore-tested. No new snapshot/config/IAM/infra operation was performed. |
| Target-host Docker build/preflight | **UNVERIFIED** | No target-host build or preflight was run. Requirements are prepared in the Status/Runbook. |
| Release tag absent | **MET** | `git ls-remote` found no `v0.1.5` tag; no tag was created. |
| Production cutover | **UNMET** | Not authorized. No deploy command, snapshot, host/config change, or cutover was performed. |

## Production evidence and discrepancy

Read-only GCE evidence identifies production as v0.1.4 at
`6fa626bdfc1f07cb873103dfed2323864d4fb280`; host checkout, protected
`SIGMA_RELEASE`, Python version, image tags and OCI revision labels agree. The
older `2761c0e12190807bafabe58445d6beac479140c4` file is an earlier release
record, timestamped 06:09:49Z. The active `6fa626b…` record followed at
06:12:04Z. Earlier docs incorrectly retained that earlier record as the
current deployed SHA and called the active commit a merge-only SHA. No user
identity, workspace, project or accounting contents were inspected.

The ext4 state disk is mounted with UUID
`28ef67cb-4da8-46e7-9a8b-dce0470153a5` and restrictive mount options. The only
observed recovery point is READY snapshot `sigma-state-v014-20261029-0606`,
created before v0.1.4 and not restore-tested. The daily timer and persistent
backup environment file were absent. It is not a current recovery guarantee.

## Schema 10 rollback boundary

v0.1.4 accepts schemas 1–9. v0.1.5 accepts 1–10 and can write schema 10 for
strategy inference provenance containing `inference_request_id`. The isolated
v0.1.4 parser rejection was executed directly against `projects.py` from the
exact active SHA. Therefore a code rollback to v0.1.4 is unsafe after any
schema 10 project write. `--schema-compatible` is an assertion gate, not a
test. No bridge has been implemented or validated. Default recovery after a
schema 10 write is a forward fix; if data restore is chosen, stop writers,
preserve the post-cutover disk, use an isolated restore-verified pre-cutover
snapshot only after explicit owner approval, and declare the lost interval.

## Snapshot and isolated restore plan

The runbook now calls for an operator-reviewed one-shot consistent snapshot
after auditing effective IAM, metadata credential isolation, billing, quota
and cost ceiling. Backup service stops SIGMA writers, confirms Compose has
stopped, syncs the mounted disk, waits for snapshot READY before pruning, then
restarts the service. Downtime lasts through snapshot completion and restart;
duration is unknown until measured. Required Compute permissions cover source
disk get, snapshot create/get/list and managed snapshot delete; restore also
needs approved disk create/attach/detach and isolated host access. Do not grant
runtime credentials as a shortcut.

Restore from the exact fresh snapshot to a separately named clone and a
temporary no-public-IP/no-production-service-account host with no secrets or
ingress. Mount read-only with `ro,noload,nosuid,nodev,noexec`, run the packaged
offline verifier with operator-approved aggregate thresholds, preserve the
snapshot and sanitized evidence, then obtain separate authorization for cleanup.
Snapshot storage, changed-block storage, clone disk, temporary compute and
logging may incur cost; current billing/rates/spend are unknown. No action has
been taken.

## Exact candidate build and host preflight

The reviewed release build input is the full lowercase SHA
`2026f1e5b167ec76289ba2335d369603e4f377ee`. The target builder must resolve
that exact commit, use `git archive` as the source, and build backend/frontend
for `linux/amd64`, each tagged with the full SHA and labeled
`org.opencontainers.image.revision=<SHA>`. Verify both labels and immutable
image IDs. Require a clean `/opt/sigma/current` checkout whose HEAD equals the
protected current release pin, successful exact-SHA fetch, available Docker
daemon/disk/network/dependencies, GCE preflight PASS, the mounted state-disk
identity, and the actual rootless sandbox daemon health via
`python -m sigma.cloud_runtime_check`. Confirm sandbox image inputs unchanged.
Systemd then starts Compose with `--no-build` and the host records running
container IDs and immutable image IDs. These host actions remain unverified.

No release tag was made. The guarded deployment helper and any flags were not
run. Stage B remains blocked on the rollback and restore gates and requires
separate operator authorization. No worker coordination was performed.
