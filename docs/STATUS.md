# SIGMA status

## Two-agent chat UI (2026-11-13)

Added `./sigma chat`, an ephemeral Human / AI #1 / AI #2 interface that uses
the selected SIGMA ChatGPT or API-key connection and alternates AI turns until
the user stops or intervenes. AI replies and transcript entries render Markdown
and LaTeX; AI reply panels are read-only. Each chat opens a private, timestamped
Markdown transcript under SIGMA state, displays its full path in the chat window,
and appends Human, AI #1, and AI #2 messages. Chat Model and Thinking pills cycle
only through account-verified models and supported reasoning levels; each turn
uses the selected pair. A new chat starts with the verified default model and
Low thinking.

Verification on the follow-up branch: `tests/chat.py` passes configuration,
model/Thinking validation, transcript mode/append/symlink checks, and API turns.
`browser_checks/chat.py` passes in real Chrome against deterministic fixtures,
including the visible full transcript path, timestamp format, all three transcript speakers,
Markdown/LaTeX display, model/Thinking selection, human intervention, and no AI
reply editors. Frontend typecheck and production build pass. Ruff check and
format checks pass. No provider inference was made. The full `./sigma test`
completed with two pre-existing failures outside this chat change:
`tests/project_collaboration.py` (four symlink-guard errors) and
`tests/research_qa.py` (`Collaboration is not available for this project`).
Because of those failures, the suite skipped its later production build; the
build passed separately. Pyright passed with zero diagnostics. The app was
launched with `./sigma chat` on the earlier implementation branch.

GitHub Issue #458 was separately fixed by merged PR #459. Its root cause was a
valid schema-v1 Recent Projects index with legacy `pinned` fields rejected by
the v2 exact-key validator; the earlier permissions repair did not address
that schema mismatch. `tests/recents.py` passes on current `main`.

## 2026-11-14 — issue #854 sponsored ChatGPT hotpatch in progress

Read-only production inspection confirmed runtime pin
`2cc08b5eae6acd661d485878f4ce84ca962786f8`, explicit
`SIGMA_CLOUD_INFERENCE_PROVIDER=api_key`, the intended sponsor email, and an
empty designated ChatGPT registration in the persistent sponsor store. The
saved Maximum Regions session shows optional reference compilation fell back
after `project_spend_limit_exceeded`; two Investigator calls were then rejected
with the same hard cap. The UI's compiler-only terminal explanation was
incorrect. No failed call was retried by this inspection, no spend-limit
configuration was changed, and no production data or accounting rows were
modified.

OpenAI's current OSS SIWC guide requires the exact `127.0.0.1` loopback
redirect through token exchange; the production HTTPS callback is unsupported.
Its VM guide requires local sign-in and protected transfer to the VM while
retaining the VM host ID. The hosted sponsor button now explains this path and
does not start the invalid HTTPS OAuth flow. Hard provider spending-limit
errors from either compiler or research agents are classified as nontransient
provider limits, with safe error guidance and no automatic hard-cap retry.
Hosted provider labels distinguish Sponsored OpenAI API key billing from
ChatGPT sponsorship, and the SIGMA allowance pill says “No SIGMA cap.”

The operator completed local ChatGPT connection in a dedicated private
`SIGMA_AUTH_HOME`; a `0600` registration file was found under its opaque
per-user subdirectory. Its contents were not read or exposed. The local SIGMA
process was stopped to prevent a refresh race. It has not yet been transferred
or imported on the VM. Production remains on `api_key`; the requested live
three-minute Session has not run.

Focused regressions for project hard-cap classification, no retry, hosted
authorization blocking, provider guidance, and the hosted connection browser
flow passed. Ruff, Ruff format, Pyright, frontend typecheck/build, and the
provider-guidance tests passed. `./sigma test` completed with two unrelated
macOS/Python 3.14 collaboration-fixture failures (`project_collaboration.py`
and `research_qa.py`), which are outside this patch's changed files; the
remaining safe checks passed. The focused hosted browser workflow passed. No
paid inference was dispatched. Merge, guarded deployment,
protected transfer/import, production readiness, and the one authorized live
three-minute start/Stop remain outstanding.

## 2026-11-14 — second SIGMA v0.4.2 deployment complete

The second v0.4.2 cutover deployed exact merged `main` SHA
`2cc08b5eae6acd661d485878f4ce84ca962786f8` (PRs #850 and #851); no version
bump was made. The protected release pin, checkout, release record, and
backend/frontend image labels match this SHA. All three containers and
systemd are healthy, state UUID is unchanged, and maintenance is off.

GitHub checks ran on the exact target SHA and passed: Ruff, frontend build,
eight SIGMA shards, two-creator real PDF acceptance, and three Browser
acceptance jobs including Project Types. The PR #851 head tree differed from
the merged target tree, so PR-head CI was not reused as proof for this SHA.

A fresh root-only complete state copy was made on the existing boot disk at
`/var/backups/sigma-state-v042-second-pre-2cc08b5e-20261114T002323Z/state`
(196 files). Full-tree checksum/metadata comparison and the read-only restore
verifier view passed. Post-deploy checks found 3 identities/workspaces, 21
projects, 49 research assets, one verified TeX/PDF pair, 10 terminal job
rows, and 53 accounting rows ($5.938237 recorded/reserved, including 15
reserved/unknown outcomes). The full copy retains the three zero-byte
`provider-slots` lock files; only the verifier view excludes their directory.

Public HTTPS/auth readiness, anonymous API behavior, and real Chrome acceptance
passed. About shows `Version 0.4.2 · Build 2cc08b5`; 26 guest samples loaded.
The About legal actions showed transparent underlined styling, the Terms quote
was italic, and the Home invitation retry remained available after a mocked
503. The failed invite was intercepted in the browser and did not modify
production. Exact-target browser CI covered guest sign-in/sign-out navigation;
no real account was authenticated. No paid inference ran. Detailed evidence is
in `DEPLOYMENT_HISTORY.md`; the first v0.4.2 deployment record is unchanged.

## 2026-11-13 — SIGMA v0.4.2 production deployment complete

PR #846 merged the release notes/handoff, and version-only PR #848 passed
Ruff, frontend build, all eight SIGMA test shards, the real two-creator PDF
gate, Browser verification, and Project Types browser acceptance. Its checked
head `454b930a602b52bf659de0eedab466d565833b2c` and merged production SHA
`0201c706d0ad63d3909016c9c4cc35e6f9ecb074` have the same Git tree. The guarded
helper deployed the merged SHA. The pin, checkout, backend/frontend image
labels and release record match; systemd and all three containers are healthy.

All 23 host preflight checks passed. A complete root-only, metadata-preserving
state copy was made on the existing boot disk at
`/var/backups/sigma-state-v042-pre-454b930a-20261113T231812Z/state` (178 files);
its rsync checksum/metadata comparison was clean. The full copy includes an
unmapped `provider-slots` directory containing three zero-byte lock files, so
the restore verifier reports that directory as unmapped. The full copy was
preserved; a separate verification view omitting only that lock-only directory
passed all read-only checks both before and after deployment. The persistent
state disk UUID remained `28ef67cb-4da8-46e7-9a8b-dce0470153a5`.

After deployment the read-only verifier found 3 identities/workspaces, 20
projects, 47 research assets, one TeX/PDF pair, 10 terminal historical job
rows, and 50 accounting rows ($5.938237 recorded/reserved; 15 reserved or
unknown outcomes). Backend and frontend image IDs are recorded in
`DEPLOYMENT_HISTORY.md`; edge health passed and maintenance is off. Public DNS,
HTTPS/TLS, redirect, private-port, SPA, and same-origin API checks passed.
Hosted Google auth reported `ready=true`; the login endpoint issued an HTTP
302 to Google. Real Chrome loaded 26 guest samples, About displayed
`Version 0.4.2 · Build 0201c70`, the OAuth start link redirected correctly,
and there were no page errors. No authenticated account flow or paid inference
was run.

Production is deliberately still configured for `api_key`;
`SIGMA_CLOUD_SPONSOR_EMAIL` is set to `zetacontinuation@gmail.com`, but the
dedicated persistent sponsor credentials are absent. The OpenAI API project
hard spending limit remains an external blocker for research. Do not change
provider routing until the authorized sponsor completes ChatGPT OAuth and the
connection becomes healthy. No billing limit, credentials, or research records
were changed.

Local `./sigma test` ran on macOS/Python 3.14 but failed in
`project_collaboration.py` and `research_qa.py` with filesystem path/symlink
behavior; the exact release tree's Linux CI passed all required shards.

## 2026-11-13 — hosted production issue remediation

Started from current `main` at `216d47a9b6507992cd8f66bf23852ad7bdd7efe9`
(merged PR #833). Deployment inspection found that `deploy/compose.yaml`
already gates the public edge on healthy frontend and backend containers, and
the backend health check validates hosted authentication configuration. The
first sign-in failure was reproducible in the callback's cold OIDC path: it
consumed the single-use flow and Google authorization code before fetching
discovery/JWKS metadata. The callback now retries safe metadata GETs, caches
validated signing keys for one hour, refreshes once for a rotated key, and
keeps the flow/code available if metadata remains unavailable. Regression
tests cover a transient first metadata failure and a full outage followed by
retrying the same callback.

`project_spend_limit_exceeded` identifies an exhausted enforced hard limit on
the OpenAI API project associated with the hosted service key. SIGMA's local
user/global spending limits cannot override it, and paid calls/retries remain
blocked. Existing non-retry handling is regression-tested across provider
billing/quota error codes; the stopped-session guidance now names the OpenAI
Project → Limits settings and next actions. An OpenAI project/organization
owner must review the project's **Monthly spend limit** and **Enforce a hard
limit**, then raise/disable the hard limit if authorized or wait for monthly
reset. Organization spend limit and prepaid credit may also apply. No provider
setting, key, or spending authorization was changed. See
[`hosted_prod_fixes_r4r.md`](../messages/hosted_prod_fixes_r4r.md).

Verification: canonical-temp `./sigma test` passed all steps, including Ruff,
formatting, Pyright (0 diagnostics), frontend typecheck/build, cloud auth and
reference compiler tests. Frontend production build passed independently.
Real-Chrome checks `browser_checks/t23_1_google_signin.py` and
`browser_checks/t257_mock_auth.py` were attempted but their stale selectors
expect `.api-connection > summary`; the current UI exposes a direct Google
sign-in link and may show a first-visit welcome dialog. The focused callback
regression runs against the real FastAPI callback with deterministic Google
transport fixtures; it is not a live Google account or production round trip.
No provider inference was run. OpenAI project configuration and a live hosted
Google OAuth round trip remain external/unverified.

## 2026-11-13 — SIGMA v0.4.1 production deployment complete

Production runs v0.4.1 from merged `main` SHA
`03781befac94ef1235fd5630e2f061abcd4fd9c8`. All 14 exact-merge checks
passed: eight SIGMA test shards, three Browser acceptance jobs, real
two-creator PDF acceptance, frontend typecheck/build, and Ruff. The guarded
deployment helper completed successfully. The local `./sigma test` run on
macOS/Python 3.14 reported failures in `project_collaboration.py` and
`research_qa.py`; exact merged-SHA CI passed all required suites. The
standalone frontend production build passed.

Before cutover, production was healthy on v0.4.0 at
`02cd31299deb9581bf31de60aafcfe057012733a`; all 23 host preflight checks
passed. Production schemas 8, 9, 11, and 13 were supported by both versions.
A root-owned mode-0700 state copy was saved on the existing boot disk at
`/var/backups/sigma-state-v041-pre-03781bef-20261113T022329Z/state`. Its
149-file checksum/metadata comparison had no differences. The read-only
verifier passed before and after deployment with the same baseline: 3
identities/workspaces, 19 projects, 43 research artifacts, one matching
TeX/PDF pair, 10 terminal historical job rows, and 46 accounting rows
($5.938237 recorded/reserved, including 15 reserved or unknown outcomes).

The release pin, host checkout, release record, and backend/frontend image
labels match `03781befac94ef1235fd5630e2f061abcd4fd9c8`. Backend and frontend
are healthy with immutable image IDs recorded in `DEPLOYMENT_HISTORY.md`; the
edge is healthy and retains its existing image. Maintenance is off. The
persistent disk UUID and mount are unchanged. Public DNS, HTTPS, redirect,
private-port, SPA, hosted-auth, and same-origin API checks passed; hosted auth
reported ready and anonymous `/api/health` returned the expected 401. Real
Chrome loaded all 26 guest samples, including Medical, and About showed
`Version 0.4.1 · Build 03781be`; the page requested no PDF/TeX assets and
reported no page errors. The first-visit invitation overlay remained open, so
no sample was opened or copied. No paid inference ran. Authenticated member
workflows were not exercised. See `DEPLOYMENT_HISTORY.md` for the full record.

## 2026-11-12 — SIGMA v0.4.0 production deployment complete

Production runs v0.4.0 from merged release SHA
`02cd31299deb9581bf31de60aafcfe057012733a`, whose parent is the approved
source cutoff `dae6de2690fa47e79bd53fb98ace565ad5789210`. Exact-SHA Ruff,
frontend build, SIGMA verification, and browser verification workflows all
passed. The guarded deployment helper started the release at 00:08:36 UTC and
reported success at 00:10:43 UTC on November 12.

Before cutover, the existing service and persistent state mount were verified.
A root-owned mode-0700 local backup was created on the existing boot disk at
`/var/backups/sigma-state-v040-pre-02cd31299deb9581-20261112T0007Z/state` and
verified with checksum/metadata comparison and the read-only restore verifier.
The production state disk remains mounted read-write at `/srv/sigma-state`
from `/dev/sdb` (ext4, UUID
`28ef67cb-4da8-46e7-9a8b-dce0470153a5`). The post-deployment verifier passed
three SQLite integrity checks and found 3 identities/workspaces, 19 project
records, 43 research artifacts, one TeX/PDF pair, 10 terminal historical job
rows, and 46 accounting rows ($5.938237 recorded/reserved, including 15
reserved or unknown outcomes).

Backend and frontend containers are healthy and built from the release SHA;
the edge container is healthy. Public HTTPS, HTTP redirect, TLS, SPA deep link,
hosted Google-auth readiness, and same-origin API checks passed. Anonymous
health correctly returns 401; Guest Mode sample browsing passed in real
Chrome. About displays `Version 0.4.0 · Build 02cd312`. Maintenance is off.
No paid inference was run. Existing project/session/paper/Q&A records were
preserved; authenticated member access and provider-backed Resume were not
exercised during production acceptance. The separately pending live
two-real-account collaboration smoke test remains outstanding. See
`DEPLOYMENT_HISTORY.md` for detailed results and image IDs.

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
