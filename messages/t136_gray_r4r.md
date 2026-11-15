# T136 — Gray handoff

**To:** ChatGPT coordinator
**From:** Gray
**Status:** R4R for offline preparation; hosted acceptance is unverified
**Branch:** `gray/t136-cloud-ops-recovery`
**Base:** current `main` at `690fff6`
**PR:** [#144](https://github.com/bkramerext/sigma/pull/144) (open, unmerged)

## Delivered

- `deploy/host-monitor.py` and a separate 15-minute systemd timer/service and
  installer. The monitor fails closed unless `/srv/sigma-state` is an exact
  mountpoint and its device or partition parent resolves to
  `/dev/disk/by-id/google-sigma-state`; it never measures boot-disk capacity as
  a substitute. It reports disk bytes/free percentage and inodes, app/rootless
  and Docker unit state, Compose health, T135 success/failure markers, a
  last-success snapshot still present as READY, and at least 14 labeled READY
  snapshots from that disk. Check output excludes captured command output,
  secrets, request bodies and user data. Failures are journaled locally; no
  remote alert path is set up.
- `deploy/rollback-gce-release.sh` requires explicit operator assertions for a
  verified recent backup and schema compatibility, a mounted state disk,
  locally present prior backend/frontend images, and passing host preflight.
  It atomically changes only `SIGMA_RELEASE`, saves the protected previous env,
  restarts through systemd, waits for backend/frontend health and running edge,
  and attempts to restore/restart the former release on failure. It does not
  alter state, volumes, databases, images or provider accounting.
- Runbook, deployment guide, ticket checklist and STATUS document the
  procedures, failure actions, limitations and unverified live acceptance.

## Verification performed

- `./sigma test` — passed all offline scenarios, Ruff, format, Pyright (0
  diagnostics), frontend typecheck and production build. This full run included
  eight monitor cases.
- Final `uv run --locked --no-sync python tests/host_monitor.py` — 9 tests
  passed, including exact-mount/source identity, wrong-disk and absent-mount
  guards, capacity/inode thresholds, retention/freshness/READY membership,
  failure-marker diagnostics and rollback safety gates.
- `uv run --locked --no-sync ruff check deploy/host-monitor.py
  tests/host_monitor.py src/sigma/tooling.py tests/tooling.py` — passed.
- `uv run --locked --no-sync ruff format --check ...` — passed during full test
  run; final focused format check passed for monitor files.
- `bash -n deploy/install-host-monitor.sh deploy/rollback-gce-release.sh` and
  `git diff --check` — passed. Focused Pyright for `src/sigma/tooling.py` — 0
  diagnostics.
- No GCP calls/resources, snapshots, credentials, provider calls, production
  data changes or browser checks. `systemd-analyze` is unavailable on this
  macOS host.

## Dependencies and remaining acceptance

- Red owns T128/T129 host, systemd application service, Compose healthchecks and
  deployed health/API behavior. This PR intentionally does not edit those
  units. Please route to Red through the coordinator for a Linux/GCE check that
  the separate monitor installer coexists with their final host layout and
  that Compose emits the expected `backend`, `frontend`, and `edge` health
  fields. No direct worker-to-worker coordination was used.
- T135 host scheduler/IAM and the `/etc/sigma/backup.env` project/disk settings
  must be installed and approved. The VM identity needs snapshot listing,
  metadata credential isolation remains required, and at least 14 daily READY
  points take two weeks to accrue.
- Live T136 acceptance still requires real restart and reboot recovery, disk
  identity/capacity checks, daily timer and failure observation, external alert
  routing approval, public HTTPS/API validation, persistence of known test
  identities/workspaces/artifacts/accounting and unknown reservations, and an
  approved compatible code rollback against actually tagged images. Local
  tests are not production acceptance.

**Elapsed implementation time at final handoff:** record in final response from
the measured start/finish timestamps. No real host or release SHA was
available.
