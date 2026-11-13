# Red — SIGMA v0.4.2 authorized production hotpatch request

**Request date:** November 13, 2026
**Repository:** `bkramerext/sigma`
**Production baseline documented:** v0.4.1 at `03781befac94ef1235fd5630e2f061abcd4fd9c8`.
**Intended source-content cutoff:** `91ca6f391ffafd77aba9e7570b81b390b3f0c6fb` (merged PR #845).
**Release notes:** `docs/RELEASE_NOTES.md`, Version 0.4.2.
**Authority:** [Merged PR #834](https://github.com/bkramerext/sigma/pull/834) at `925c7ee9bf42cf90f7b571e65377a40b2accb8e4` and [`docs/DEPLOYMENT_RUNBOOK.md`](../docs/DEPLOYMENT_RUNBOOK.md) (“Red's mandate and decision authority,” “Authorized hotpatch — fix through production verification,” “Release checklist”). For deployed baseline and incident-only references, see [`docs/DEPLOYMENT_HISTORY.md`](../docs/DEPLOYMENT_HISTORY.md) and [`docs/OPERATION_RUNBOOK.md`](../docs/OPERATION_RUNBOOK.md).

## Directive

**Red: hotpatch the currently hosted SIGMA application to v0.4.2, end to end.** This instruction authorizes release preparation, any necessary narrowly scoped release fix, CI, PR merge, guarded production deployment, and production verification under the already merged hotpatch runbook. **Do not stop at a PR or ask for another deployment approval.** Only a concrete safety, authorization, integrity, or health blocker may prevent the affected step; preserve production and continue independent safe checks.

## Execute

1. **Release source.** Confirm the 0.4.2 release notes have merged, and verify that the intended fixes through PR #845 are present. Do not silently sweep in unrelated unreviewed work beyond the stated source cutoff.
2. **Version bump and PR.** Set `pyproject.toml`, `uv.lock`, `frontend/package.json`, and `frontend/package-lock.json` consistently to **0.4.2**. Open the minimal release PR, fix CI findings in batches, and merge after its required checks pass. No tag unless explicitly requested.
3. **Exact build identity.** Find the full 40-character merged `main` SHA after the version bump. Confirm Ruff, SIGMA verification (including all shards and real PDF gate), Browser verification, and other required release checks are green for that exact SHA. A source cutoff or PR head is *not* a deployable release SHA.
4. **Preflight and safety copy.** Use established keyless IAP/OS Login to inspect the existing `sigma-gce-01` VM, service/containers, persistent mount, pin, disk space, and schema compatibility. Briefly stop writers to make and verify a root-only, metadata-preserving complete state copy on the separate existing boot disk; run the existing read-only verifier. Do not create new infrastructure or pay for unrelated recovery exercises.
5. **Guarded deployment.** Only after the copy and schema checks are truthful, run the existing production helper using the final merged **full** SHA:
   ```sh
   sudo python3 /opt/sigma/current/deploy/deploy-gce-release.py FULL_40_CHARACTER_SHA \
     --backup-verified --schema-compatible
   ```
6. **Production verification.** Confirm About says `Version 0.4.2` with the expected build prefix; pin/checkout/images match, backend/frontend/edge are healthy, public HTTPS/hosted auth and guest/read-only pages work, saved projects/papers/identity/accounting are preserved, and maintenance is OFF. Pay special attention to provider selection UI and research startup/Resume safety. Do not initiate unauthorized paid AI calls; record any paid end-to-end verification gap honestly.
7. **Close the loop.** Update release notes to deployed status and append real release SHA/verification evidence to `docs/DEPLOYMENT_HISTORY.md` and relevant Operations Runbook inventory. Report **`SIGMA | DEPLOYMENT SUCCEEDED`** with observed checks and SHA, or **`SIGMA | DEPLOYMENT FAILED`** with the actual blocker and last healthy production SHA.

## Boundaries

Preserve user work and payment provenance. No unauthorized inference, billing-limit changes, credential copying, IAM expansion, new VM/snapshot/disk/service, or unsafe bypasses. The merged runbook says to solve concrete execution problems within scope rather than debating whether a requested hotpatch is necessary. Production deployment, not PR merge, is the completion criterion.
