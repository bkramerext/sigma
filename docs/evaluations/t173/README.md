# T173 pre-deployment smoke and rollback readiness

## Assessment

**BLOCKED for first private production deployment.** This assignment performed
no cloud changes. The application is not deployed; the HTTPS host currently
serves the temporary readiness page (per assignment context). Local packaged
acceptance gives useful release evidence, but it cannot establish target-host
rootless execution, production identity behavior, persistent-disk recovery,
or public application rollback.

| Gate | Result | Evidence and boundary |
| --- | --- | --- |
| Research workflow, T170 | **PASS (simulated/local)** | See [T170 evidence](../t170/README.md): sample project creation/edit/reopen; saved session lifecycle and restart/restore; evidence and Outcome preservation; reports; Markdown, TeX and PDF export; isolated Python and SageMath in local Colima. Session/provider content is deterministic fixture data. |
| Packaged release build and smoke | **PASS (local)** | `bash deploy/validate-local.sh` built pinned amd64 backend/frontend images and ran real Chrome against packaged Compose/Nginx/Caddy, not Vite. Five saved sessions, Outcome/artifact reads, downloaded audit/text/HTML, Tectonic PDF, backend restart, container recreation, fresh-volume restore and second-user isolation passed. OAuth/inference were skipped. |
| Persistent data across app restart/recreation | **PASS (local fixture)** | Project/strategy/session IDs, Outcome/evidence, TeX/PDF and report hashes survived backend recreation and fresh-volume restore in T91. This does not prove the GCE state disk, backup inventory, or host reboot path. |
| Rollback helper gates | **PASS (offline contract)** | `tests/host_monitor.py` verifies explicit verified-backup/schema-compatible flags, local image checks, prior-env restoration paths, and no volume deletion. `./sigma test` passes after correcting the stale systemd mount assertions. |
| Rollback helper health outcomes | **PASS (disposable Linux fixture)** | [`rollback-fixture.sh`](rollback-fixture.sh) runs the actual helper in a throwaway container with stubbed host commands. Unhealthy backend/frontend health returned failure, restored the original release SHA and preserved a state sentinel; healthy checks switched to the prior SHA and also preserved the sentinel. This is a fixture, not a GCE/systemd rehearsal. |
| Failed candidate build | **BLOCKED (not injected)** | The local smoke build passed. No release-publishing wrapper owns both image build and `SIGMA_RELEASE` mutation, so no automated failed-build rollback path was verified. Operationally, a failed build must stop before changing the release pin. |
| Live target host / public app rollback | **BLOCKED** | No deployed SIGMA stack, GCE access, approved backup point, production images, production identities, or target-host rootless daemon was available. The temporary HTTPS readiness page is not an app smoke. No live rollback or data compatibility check occurred. |

## Operator gate

Before any first private deployment, require the owner-approved release SHA and
images, an independently verified recent state-disk recovery point, target-host
preflight and rootless Python/Sage proof, approved identity matrix, and a
maintenance/rollback window. Follow the exact release, restart, rollback, and
post-rollback checks in [`OPERATION_RUNBOOK.md`](../../OPERATION_RUNBOOK.md)
and the cloud release checks in [`CLOUD_DEPLOYMENT.md`](../../CLOUD_DEPLOYMENT.md).
The rollback helper requires the full prior SHA plus
`--backup-verified --schema-compatible`; after it returns, the operator must
verify HTTPS/API, identity and workspace boundaries, existing projects and
artifacts, usage totals, and pending/unknown reservations. A code rollback does
not restore database state or reverse provider charges.

## Test evidence

- `./sigma test`: **PASS** on current source after correcting the three stale
  `srv-sigma\\x2dstate.mount` test assertions to match
  `RequiresMountsFor=/srv/sigma-state`; includes deployment package, host
  preflight, backup, monitor and rollback-contract scenarios, Ruff, formatting,
  Pyright, frontend typecheck and production build.
- `bash deploy/validate-local.sh`: **PASS**, including real Chrome, packaged
  Compose lifecycle/recovery and fresh-volume artifact/hash verification.
- `bash docs/evaluations/t173/rollback-fixture.sh`: **PASS** for both failed-
  health restoration and successful prior-release selection in the disposable
  container described above.
- `uv run --locked --no-sync python -m sigma.cloud_runtime_check
  --allow-nonrootless-dev`: **PASS** for Python and SageMath isolation probes;
  local Colima reports `daemon_rootless: false`, so hosted runtime remains
  unverified.

No paid provider calls, Google OAuth, GCP operations, production secrets,
production data, or live release actions were used. The full-suite correction
changed test expectations only; no cloud host configuration or product
runtime changed.
