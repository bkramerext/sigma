# SIGMA status

## 2026-11-08 — SIGMA v0.2.2 production deployment complete

Production now runs SIGMA v0.2.2 from merged `main` SHA
`469c955dfadb5a7bd17b72fc069a3365b4f20ba7` (tree
`0c8513bae7be8decc27101e2e05147bbac162c8d`). The guarded helper built and
started the backend and frontend from that exact SHA. Backend image
`sha256:1673bf9eedbdf81aa9f9d9944eb3a8708bc1cd10b77d0add1b64afea83f0096c`
and frontend image
`sha256:94721b300106d117b09330092b62797432a3f0d7abf57a195331a00ca65af911`
carry the matching source revision and are recorded in the host release
record. Exact-SHA Ruff, SIGMA verification, and frontend build passed. The
merged-SHA browser acceptance steps passed on attempt 1; the workflow failed
only during `setup-uv` post-job cache pruning after a 300-second lock wait.
Attempt 2 was cancelled during Project Types. The complete browser run for PR
SHA `e5de6f05ef8a8976fffec4a1b6cc54aa9078f205` passed on the identical source
tree. No full tests or moving-`main` checks were rerun.

Before cutover, snapshot `sigma-state-v021-pre-20261108-1546`, ID
`6224195028464248741`, reached READY from `sigma-state` and remains retained.
The service was stopped and the state filesystem synced at 15:46:10 UTC, then
restarted at 15:46:45 UTC. The isolated VM had no public IP or service account;
the 30 GB clone was attached read-only and mounted with
`ro,nosuid,nodev,noexec,norecovery`. The exact-SHA verifier passed all three
SQLite integrity checks, 3 identities/workspaces, 17 projects, 42 artifacts,
one TeX/PDF pair with matching hash and size, 10 terminal historical job rows,
and 46 accounting rows ($5.938237 recorded/reserved, including 15 reserved or
unknown outcomes). The recovery VM, boot disk, clone disk, and temporary
OS Login keys were removed; the snapshot remains.

The guarded release helper ran at 16:01:31 UTC and completed at 16:03:35 UTC.
The public maintenance window was 30 seconds (16:03:05–16:03:35 UTC). The
production persistent state UUID remains
`28ef67cb-4da8-46e7-9a8b-dce0470153a5`. Systemd and all three containers are
healthy, maintenance is off, the production verifier still reports the same
aggregate data/accounting baseline, public HTTPS and the endpoint probe pass,
hosted auth status is 200/ready, and anonymous `/api/health` returns the
expected 401. The served frontend About label contains `Version 0.2.2 · Build
469c955`. No paid inference was run, and no user, project, research, paper,
authorization, or accounting records were reset or deleted.

The two keyless identities passed effective access checks: `sigma-release-ssh`
described `sigma-gce-01` and used IAP/OS Login with `sudo -n true`; the recovery
identity described the temporary VM and used IAP/OS Login with noninteractive
sudo. Snapshot and temporary resource lifecycle checks succeeded without an
Owner fallback or broad IAM grant. The recovery identity lacks
`compute.globalOperations.get`, so synchronous `gcloud` operation polling
returned 403 after accepted operations. Resource state was verified directly
through the same impersonated identity, and no operation was retried or
resource recreated. The initial recovery VM also needed the existing
`sigma-iap-ssh` network tag for the project's IAP-only firewall; the tag was
added, and the canonical runbook command is being corrected.

Live billing totals remain unavailable because `cloudbilling.googleapis.com`
is disabled for the project. The recovery drill was bounded to one 30 GB
snapshot, one 30 GB clone, and one 10 GB boot disk on an `e2-standard-2` VM;
the snapshot stores 35,513,600 bytes and temporary compute ran for less than
12 minutes. Published-rate estimate is well below the $25 incremental ceiling;
the exact billed amount was not independently queried. Full authenticated
Google login, import/export, email, research execution, and saved-paper viewing
were not exercised. A code rollback does not roll back data; preserve new
writes and validate old-binary schema compatibility before any rollback.

## 2026-11-06 — SIGMA v0.2.1 production deployment complete

Production now runs v0.2.1 from the exact approved commit
`5435e14eeea159ab207ad50016577b9a9542ae59`. The guarded helper built the
backend and frontend from that SHA and recorded the immutable images; no
excluded PRs or later `main` changes were included. Exact-SHA Ruff, SIGMA
verification, and browser CI were already green before cutover.

The fresh application-consistent recovery snapshot
`sigma-state-v021-pre-20261107-0658` is READY and retained. A no-public-IP,
no-service-account recovery VM mounted a clone read-only with
`ro,noload,nosuid,nodev,noexec,norecovery`; the read-only verifier passed three
SQLite integrity checks, three identity/workspace mappings, 17 project
records, 42 research artifacts, one TeX/PDF paper pair with matching hash and
size, ten terminal job-history rows, and 46 accounting rows ($5.938237
recorded/reserved, including 15 reserved or unknown outcomes). The verifier
was narrowly corrected to recognize and integrity-check the known hidden
publication-compilation cache rather than misclassify it as a paper record.
The temporary recovery VM and clone disk were removed; the snapshot remains.

The release helper completed at 2026-11-07 07:09 UTC. Backend image
`sha256:1ab6ae4c60f8c320bb69c1cc0135a60b994084befa7dc0c440701a8fa2cd3a88` and
frontend image
`sha256:4615bc091f737620956a5da1bedc3f96ced3a38c4d155e513a126b670f1f09e5`
both carry the approved source SHA. Production systemd and all three
containers are healthy; the edge image remains
`sha256:cf1bd22f2415bc99b785ece1df2c49d32985ac4ac42d84df335be17350593693`.
The persistent state UUID and mount options are unchanged. Maintenance is off.
The observed maintenance/cutover window was approximately 20 seconds
(07:08:49–07:09:09 UTC); public HTTPS returned 200 after cutover, hosted
cloud-auth status returned 200/ready, and unauthenticated `/api/health`
returned the expected 401. Headless Chrome reported
`Version 0.2.1 · Build 5435e14`, with no page errors or write requests. No
paid inference was run. Full authenticated login, import/export, email, and
research workflows were not exercised. Exact billed recovery-drill spend was
not independently queried; the bounded resource plan stayed within the
documented $25 incremental ceiling.

The role-separated release identity could not fetch instance metadata needed
by `gcloud compute ssh`, and direct SSH timed out; the already-authorized
project admin used IAP to run the guarded helper. The release IAM identities
were not broadened. See the operations and deployment runbooks for detailed
evidence and rollback notes.

PR [#589](https://github.com/bkramerext/sigma/pull/589) fixed the local scored
sample migration test path and merged as
`994f714f299cb380e92f27753c4da8516e319d10`. Exact-merge Actions passed
[SIGMA verification](https://github.com/bkramerext/sigma/actions/runs/42242564357),
[browser verification](https://github.com/bkramerext/sigma/actions/runs/42242564360),
and [Ruff](https://github.com/bkramerext/sigma/actions/runs/42242564407).

Issue #590 established keyless, separate `sigma-release-operator` and
`sigma-release-ssh` identities. Effective permissions and least-privilege
role boundaries are documented in the
[operations runbook](OPERATION_RUNBOOK.md#sigma-keyless-release-identities-2026-11-06-issue-590).

## SIGMA v0.2.0 production deployment (2026-11-04 PDT)

PR [#589](https://github.com/bkramerext/sigma/pull/589) fixed the local scored
sample migration test path and merged as
`994f714f299cb380e92f27753c4da8516e319d10`. Exact-merge Actions passed
[SIGMA verification](https://github.com/bkramerext/sigma/actions/runs/42242564357),
[browser verification](https://github.com/bkramerext/sigma/actions/runs/42242564360),
and [Ruff](https://github.com/bkramerext/sigma/actions/runs/42242564407).
`./sigma test` passed all configured steps on that SHA.

Issue #590 established keyless, separate `sigma-release-operator` and
`sigma-release-ssh` identities. The owner's project Owner grant was preserved;
neither release identity has Owner/Editor or user-managed keys. The recovery
identity is scoped to snapshots from `sigma-state`, release-prefixed temporary
recovery resources, and OS Login on recovery VMs. The host-only identity has
IAP/OS Login access to `sigma-gce-01` and `roles/iam.serviceAccountUser` on
`sigma-runtime` only; it has no Compute creation, deletion, attachment, or
service-account-change permission. Both use short-lived impersonation. Effective
permission checks and a five-minute-SSH-key IAP/OS Login session passed. Full
role boundaries and observed checks are in
[Operations Runbook](OPERATION_RUNBOOK.md#sigma-keyless-release-identities-2026-11-06-issue-590).

**Deployment is held at the operator's direction.** No production preflight,
recovery snapshot, isolated restore resources, or cutover was run. The
recovery-creation conditional permissions are configured but have not yet been
exercised with temporary resources. Select and freeze the release SHA only
after the owner updates the branch intended for deployment; then complete the
usual fresh snapshot/restore and exact-SHA release gates.

## SIGMA v0.2.0 production deployment (2026-11-04 PDT)

Production is running the approved `main` release at
`9d938907ffd02fb89c9d10545e8df61484310cbd` (v0.2.0). The exact merged commit
passed SIGMA test shards, Ruff, and browser acceptance in [SIGMA tests run
41977490940](https://github.com/bkramerext/sigma/actions/runs/41977490940),
[browser acceptance run
41977490915](https://github.com/bkramerext/sigma/actions/runs/41977490915), and
[Ruff run 41977490887](https://github.com/bkramerext/sigma/actions/runs/41977490887).
The documented guarded release helper completed successfully. The release
record, running image IDs, checkout, and protected release pin agree on this
commit. Backend and frontend image IDs are
`sha256:65572961183f12569854e5c0ee4c63744441dd616f1b37ed72caaa0490b7c750`
and `sha256:f2cb44d69a8a2b82d0596eca59b5a8880f360840adb964b4812981ef96093a4e`.

Before cutover, production was quiesced and the application-consistent recovery
snapshot `sigma-state-v020-pre-20261104-1736` was created and reached READY.
An isolated read-only restore drill passed three SQLite integrity checks,
three identity/workspace mappings, 14 projects, 33 artifacts, and preserved
job/accounting history; it found zero saved PDF/TeX pairs. The temporary clone
disk and recovery VM were removed and verified absent. No production data,
secrets, or configuration were changed, and no research/provider call was
initiated.

Production service and all three containers are healthy; the state disk is
mounted, maintenance is off, public HTTPS returns HTTP 200, and unauthenticated
API health returns the expected HTTP 401. Headless Chrome rendered the
production app and read About as `Version 0.2.0 · Build 9d93890`. OAuth login
redirected to Google without credentials being submitted. A public sample
research project/history view loaded without starting research or calling a
provider.

**Deployment is live and healthy; full production smoke acceptance remains
incomplete.** Positive authenticated login, project import/export, actual email
delivery, bounded research execution, and viewing a saved paper were not
verified because no authenticated production session was available. No research
was run in order to honor the no-provider-call constraint. These checks remain
outstanding and must not be reported as passed. Detailed evidence is in the
[operations runbook](OPERATION_RUNBOOK.md#sigma-v020-deployment-outcome-2026-11-04-pdt)
and [deployment runbook](DEPLOYMENT_RUNBOOK.md#v020-production-deployment-outcome--2026-11-04).

## Issue #458 — legacy Recent Projects pin migration (2026-11-01)

Reproduced the Saved Projects failure against this Mac account's existing
`~/.local/state/sigma` index without changing it. The state directory was owned
by the current user and mode `0700`; `recents.lock` and `recents.json` were
owned by the current user and mode `0600`. The 49,033-byte index was valid
schema v1 with 154 entries, each carrying the historical boolean `pinned`
field (two entries pinned). `_validate` raised `ValueError` because its exact
entry-key check allowed only the newer shape. Commit `4dc4f921` repaired modes
but did not account for this older entry schema, so `d4ab7d0` still returned
the generic unavailable response. A read-only preflight verified both saved
pins against their project IDs and found no family conflict.

Schema-v1 validation now accepts the legacy `pinned` boolean. Migration checks
each pinned entry against the project at its saved path and derives its pin
family from the verified project title before writing schema v2. A missing or
identity-mismatched project rejects migration and leaves the original index
bytes unchanged. The unavailable message no longer falsely diagnoses only
permissions. No repair was applied to the user's actual index during this
assignment; opening Saved Projects with the updated app performs the safe
one-time migration.

Verification: `uv run --locked --no-sync python tests/recents.py` passed,
including legacy pin preservation across a fresh process and rejection without
writing when project identity differs. Real Chrome on the local app rendered a
fixture Saved project and its pin indicator in Projects → Saved; authentication
and the Recent Projects response were deterministic browser fixtures, while
the migration service itself was exercised by the focused test. `./sigma test`
passed, including Ruff, formatting, Pyright (0 diagnostics), frontend typecheck,
and production build. The existing large JavaScript chunk advisory remains; the
optional graph-present Python sandbox scenario was skipped because its image is
not installed. No provider calls were made. Existing real-user Saved list
acceptance after applying the migration remains the user's confirmation gate.
