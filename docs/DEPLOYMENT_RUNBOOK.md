# SIGMA Routine Production Release

**Goal:** Upgrade SIGMA's backend and frontend on the existing production VM. This is a single-user hobby project. Initial cloud configuration, incident recovery, and historical release evidence belong in [Operations Runbook](OPERATION_RUNBOOK.md) and [Deployment History](DEPLOYMENT_HISTORY.md), not this checklist.

**One instruction starts a release:** The operator says `main` is ready and supplies the approved full 40-character SHA. Red handles the routine release end to end, without asking to advance stages. Until then, leave production running on v0.2.2 and do not freeze a moving `main`.

## Release checklist

1. **Check the build.** Confirm that the selected SHA is merged, versioned correctly, and has passing Ruff, SIGMA verification, and Browser verification results. Reuse those results; don't rerun `main` or reopen previously resolved IAM issues.
2. **Check the existing VM.** Connect to `sigma-gce-01` using the established keyless IAP/OS Login identity. Confirm the service, backend/frontend/edge containers, persistent state mount, release pin, and available space. Don't re-audit cloud setup or billing unless something is actually failing.
3. **Copy current data.** Briefly stop SIGMA writers, copy the complete state tree to a root-only directory on the *separate, already-provisioned boot disk*, preserve file ownership/metadata, and verify the copy and SQLite integrity with SIGMA's existing read-only verifier. Restore normal service after the copy. This is protection against a bad software upgrade, not VM/zone disaster recovery.
4. **Deploy the approved SHA.** Confirm the new code is compatible with the saved state, then use the existing guarded helper on the production VM, with truthful backup/schema flags:

   ```sh
   sudo python3 /opt/sigma/current/deploy/deploy-gce-release.py FULL_40_CHARACTER_SHA \
     --backup-verified --schema-compatible
   ```

5. **Check the result.** Confirm the version/build SHA, healthy backend/frontend/edge, HTTPS/auth readiness, persistent projects/papers/accounting, and maintenance OFF. Keep the existing boot-disk copy temporarily for software rollback and report the deployed SHA, health, and any actual problem.

**Operating boundaries:** No new recovery VM, disk, cloud snapshot, paid backup service, or additional storage. No paid inference. Do not use personal Owner credentials for deployment. If an actual health, data-integrity, access, or schema check fails, preserve the last safe state and diagnose that **specific failure**—do not bypass the helper's safety checks.

**Completion:** Report `SIGMA | DEPLOYMENT SUCCEEDED` with the production SHA or `SIGMA | DEPLOYMENT FAILED` with the concrete blocker and the last healthy production SHA. No new approvals or policy debates for routine steps.

## Initial setup and nonroutine recovery

Host provisioning, IAM policy design, firewall inventories, billing configuration, disaster recovery drills, detailed troubleshooting, and historical snapshot/VM procedures are documented in [Operations Runbook](OPERATION_RUNBOOK.md) and [Deployment History](DEPLOYMENT_HISTORY.md). They are **not routine release gates**. Revisit them only when a real deployment failure or requested infrastructure change makes them relevant.
