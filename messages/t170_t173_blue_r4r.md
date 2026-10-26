# Blue R4R — T170/T173 private deployment readiness

- **Tickets:** T170 and T173
- **Base:** `main` at `8e8d979`
- **Assessment:** BLOCKED for first private production deployment; deterministic/local acceptance passes
- **Change:** Corrected three stale systemd mount assertions to `RequiresMountsFor=/srv/sigma-state`; added the T173 acceptance report and reproducible disposable rollback fixture. No product/runtime or cloud configuration changed.

## Verification performed

- `./sigma test` — PASS, including deployment package, GCE host, backup, monitoring and rollback contract checks; Ruff, format, Pyright (0 diagnostics), frontend typecheck and production build.
- `bash deploy/validate-local.sh` — PASS. Pinned amd64 images, real Chrome against packaged Compose, saved project/session/outcome/evidence/report/export workflow, backend restart and container recreation, fresh-volume restore and simulated-account isolation. No OAuth or inference calls.
- `uv run --locked --no-sync python -m sigma.cloud_runtime_check --allow-nonrootless-dev` — PASS for Python and SageMath isolation probes (UID 65532; host secret/state, network and Docker socket blocked). Local Colima daemon is not rootless.
- `bash docs/evaluations/t173/rollback-fixture.sh` — PASS for failed-health restoration and successful prior-release selection; state sentinel preserved in both branches.
- `git diff --check` — PASS.

No paid provider calls, live OAuth, GCP operations, deployment, production credentials or user data were used. Existing T170 exported app artifacts remain fixture-authored and preserved in `docs/evaluations/t170/exports/`; no genuine provider-backed research was represented as executed.

## Remaining acceptance

Failed candidate-build injection; target-host rootless Python/Sage proof; production OAuth and real authorized/denied identities; hosted workspace privacy; GCE disk/backup/restore/reboot; actual public app smoke; compatible rollback on production persistent state; provider-backed research under separate authorization; and T137 owner/coordinator go-no-go.
