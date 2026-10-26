# Blue T98 repository Codex launcher — R4R

**Base:** `main` at `dd23fec65683cea72b39f95f952377cc41a84346` when work began.
**Scope:** Repository-local Codex launcher, shared environment/preflight,
deterministic regression coverage, and worker protocol/status updates.

## Delivered

- `./scripts/codex [arguments...]` resolves its repository independent of cwd,
  sources `scripts/codex-env.sh`, prevents recursive dispatch, and `exec`s the
  real CLI to preserve argument boundaries, exit codes, and signals.
- `scripts/codex-env.sh` exports the observed GCP project, zone, VM, and public
  hostname; adds common executable directories without duplicating PATH entries.
  It does not change gcloud configuration, copy credentials, or assume Docker.
- `scripts/codex-check.sh` checks required tools, active gcloud auth, expected
  project/zone, and read-only IAP SSH. It withholds identity and raw diagnostics.
- `./sigma test` now includes `tests/codex_launcher.py`. Worker startup guidance
  points future SIGMA worker launches to the repository wrapper and documents
  its process inheritance boundary.

## Verification

- `python3 tests/codex_launcher.py -v`: **6 passed** (argument forwarding,
  cwd-independent root, missing CLI, recursion guard, environment/idempotency,
  exit status, and signal propagation).
- `./scripts/codex --version`: `codex-cli 0.164.0`.
- `bash -n scripts/codex scripts/codex-env.sh scripts/codex-check.sh`: passed.
- `./sigma test`: all steps passed; Ruff check/format, Pyright, frontend
  typecheck, and frontend production build passed. Build emitted the existing
  large-chunk advisory. The full suite began before the sixth signal case was
  added and ran five launcher tests; the final six-case script passed directly.
- `./scripts/codex-check.sh`: active GCP auth, configured project/zone, and
  read-only VM connectivity passed. Overall status was **FAIL** because `gh`
  is missing on this host.
- Direct read-only IAP check:
  `gcloud compute ssh sigma-gce-01 --project=sigma-research-prod --zone=us-west1-b --tunnel-through-iap --command=true --quiet`
  exited 0.

## Environment boundary and limits

This Codex run used the authenticated local macOS arm64 host. That proves
read-only GCE access only from this run's context. The four persistent worker
sessions were not observed being launched through this wrapper; their process
environment and GCE access remain **UNVERIFIED**. The wrapper supplies exported
settings to the Codex CLI and its children only when that CLI is launched
through it. No credentials were copied/displayed; no global gcloud, IAM,
firewall, or service state changed; no provider calls or costs occurred. A
real-browser check does not apply to this launcher change.
