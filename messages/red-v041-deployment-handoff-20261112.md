# Red — SIGMA v0.4.1 routine production deployment handoff

**Status:** Release preparation and deployment instructions. **Not deployed.**
**Repository:** `bkramerext/sigma`
**Source-content cutoff:** `9faa3e667766b35d75ae3113ba5db22405c55802` (merged main through PR #829).
**Release notes:** `docs/RELEASE_NOTES.md`, section “Version 0.4.1”.
**Authoritative routine release procedure:** `docs/DEPLOYMENT_RUNBOOK.md`.

## Objective

Release the merged v0.4.1 application changes using the existing production VM and guarded deployment helper. The key user-visible changes are paper Play/Stop/Resume reliability, truthful step restarts, faster paper/home metadata loading with **no PDF/TeX reads outside explicit view/download**, best-paper star navigation, and the new Medical project type/sample.

The source cutoff above **is not** an approved final release SHA. Use the full SHA of the final merged version bump after exact-SHA CI, and follow the operator's release approval procedure. Do not deploy a moving branch, a pull-request head, or the cutoff by mistake.

## Do in order

1. **Release preparation.** Ensure the v0.4.1 notes have merged. Make the minimum release-only version changes: `pyproject.toml`, `uv.lock`, `frontend/package.json`, `frontend/package-lock.json` must all consistently report **0.4.1**. Do not pull in unrelated development changes. Do not create a Git tag unless the operator asks.
2. **Prove the exact release source.** Run the repository's `./sigma test`, frontend build, Ruff check and format, and confirm the required GitHub **SIGMA verification** and **Browser verification** workflows are green for the final release commit. Preserve the mandatory real two-creator PDF compilation gate. Reuse passed checks; do not launch paid AI-provider work. Batch and resolve any CI findings before another push.
3. **Freeze the release SHA.** Once the release PR is merged, identify the **full 40-character merged `main` SHA** and verify its identity and green checks. Confirm this is the SHA authorized for deployment. The release notes' source cutoff is an inclusion boundary, not a substitute.
4. **Inspect the existing production host.** Use the established keyless IAP/OS Login path to `sigma-gce-01` in `sigma-research-prod` / `us-west1-b`. Confirm the currently deployed version/SHA and healthy backend/frontend/edge, attached persistent state disk at `/srv/sigma-state`, free disk space, and normal service status. Resolve discrepancies against **live host state**, not stale historical docs.
5. **Make and verify the routine local safety copy.** Follow `docs/DEPLOYMENT_RUNBOOK.md`: briefly stop writers; copy all persistent state, retaining ownership and metadata, to a **root-only directory on the already-provisioned separate boot disk**; check completeness and SQLite integrity using the existing verifier; return service to normal. Do not create a GCE VM, cloud snapshot, additional disk, backup service, or other infrastructure for a routine software update.
6. **Guarded cutover only.** After confirming schema compatibility and verified safety copy, run on the production VM, substituting the **approved final release SHA**:

   ```sh
   sudo python3 /opt/sigma/current/deploy/deploy-gce-release.py FULL_40_CHARACTER_SHA \
     --backup-verified --schema-compatible
   ```

   Never assert `--backup-verified` or `--schema-compatible` without checking them. Do not bypass the guarded helper or replace it with manual Compose commands.
7. **Verify production.** Confirm About reports **Version 0.4.1** and the expected seven-character build prefix; release pin, image labels/IDs, backend/frontend/edge health, HTTPS and hosted-auth readiness, persistent projects/papers/identities/accounting, and maintenance OFF. Use the existing public endpoint probe. Inspect read-only UI paths for home/project listing and guest access if practical; do not initiate paid research/paper calls just to smoke-test.
8. **Record outcome.** Append a concise dated entry to `docs/DEPLOYMENT_HISTORY.md` and update the v0.4.1 release-note status only **after** verified cutover. Report `SIGMA | DEPLOYMENT SUCCEEDED` with the **full production SHA** and the observed checks, or `SIGMA | DEPLOYMENT FAILED` with the specific blocker and last healthy production SHA.

## Operating boundaries

Routine release only: **no paid inference, new resources, IAM changes, credentials in logs, local user server access, destructive data migration, or unrequested tag**. Do not turn speculative infrastructure concerns into new gates. If a real integrity, authorization, schema or health check fails, preserve the last safe state, stop, and report the concrete blocker. Consult `docs/OPERATION_RUNBOOK.md` only for targeted diagnosis/nonroutine recovery.

**Release-specific acceptance focus:** a project with around ten or more papers should open without reading PDF/TeX bytes; paper Stop must not continue into later workflow stages; activity and paper counts must remain truthful, and existing data and attribution must survive the cutover. Production testing is read-only unless an explicit safe, non-paid test is available.
