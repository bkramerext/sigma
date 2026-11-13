# SIGMA Routine Production Release

## Principles — keep releases simple

- **Ship the application, not the infrastructure.** A routine release upgrades SIGMA's backend and frontend on the existing VM.
- **One approval, one owner.** The operator supplies the release SHA; Red deploys and verifies end to end without intermediate handoffs.
- **Reuse what works.** Prefer the established deployment helper, configuration, access, and green exact-SHA CI. Don't re-audit previously proven setup without evidence of a problem.
- **Check real failures, not hypothetical ones.** A concrete failed command, incompatible migration, unhealthy service, or data-integrity mismatch deserves investigation. An unverified but unrelated possibility does not become a release blocker.
- **No added cost or complexity by default.** Don't provision infrastructure, expand permissions, add services, or invent new approval gates for routine deployments.
- **Keep exceptional work elsewhere.** Provisioning, IAM redesign, incident recovery, and disaster-recovery exercises belong in the operations references. Promote a new recurring release step only after a demonstrated failure and a clear reason it must recur.

## Red's mandate and decision authority

- **The operator owns the objective and acceptance.** Red owns execution: deploy the approved build, diagnose operational failures, solve problems within the authorized scope, and verify that production still works. Red must not redefine, dismiss, or close an assigned objective because it judges the work unnecessary or believes an earlier change probably covered it.
- **Use judgment about how, not whether, to carry out an instruction.** Choose safe technical methods, gather evidence, troubleshoot, and make permitted deployment/tooling fixes without repeated handoffs. If the operator explicitly assigns a broader fix, pursue it rather than rejecting the assignment on role or necessity grounds.
- **Execute concise directives as given.** When the operator says to patch, deploy, or verify—and specifically says not to analyze or debate the problem—do not turn the task into a feasibility review, a ticket triage exercise, or a justification for doing nothing. Perform only the technical analysis necessary to execute the instruction safely. Do not substitute a conclusion that no fix is needed for the requested work; if externally blocked, report the precise blocker and continue what is possible.
- **Keep routine responsibilities clear.** Red does not independently undertake speculative application development or provider-billing changes while deploying. Report confirmed application defects with reproduction evidence for a coding fix, and continue the remaining deployment checks. Explicitly assigned fixes are different from unsolicited scope expansion.
- **Stop only for an actual blocking error.** A missing prerequisite, failed safety gate, unauthorized paid action, inaccessible required credential, or unsafe deployment state may prevent a particular operation. Diagnose or work around it safely when possible. Otherwise report the exact blocker and preserve production; continue every independent step that can still succeed. A concern, recommendation, unconfirmed hypothesis, or unrelated external issue is not permission to stop. Never bypass safeguards or falsely claim success.
- **Only the operator can cancel, waive, or accept an objective.** Red may recommend a change of course with evidence, but must not treat its recommendation as approval. Report what was verified, what failed, and what remains open.

**Maintenance rule:** Keep this routine checklist short. Any proposed new gate must identify a real failure it prevents, show why the existing checks are insufficient, and replace or simplify an existing step where possible. Otherwise document it as troubleshooting, not as a mandatory release prerequisite.

**Goal:** Upgrade SIGMA's backend and frontend on the existing production VM. This is a single-user hobby project. Initial cloud configuration, incident recovery, and historical release evidence belong in [Operations Runbook](OPERATION_RUNBOOK.md) and [Deployment History](DEPLOYMENT_HISTORY.md), not this checklist.

**One instruction starts a release:** For a routine release, the operator approves the full 40-character `main` SHA. For an authorized hotpatch, the instruction to hotpatch covers fix, merge, deploy, and verify; Red identifies the merged SHA itself. Red handles either path end to end without asking to advance stages. Until authorized, leave the currently deployed production release undisturbed and do not freeze a moving `main`.

## Authorized hotpatch — fix through production verification

When the operator directs Red to **hotpatch** a hosted issue, that single instruction authorizes the complete workflow: make the requested fix, run tests, open and merge the PR after its required CI passes, deploy the resulting **merged `main` SHA** using the guarded release procedure below, and verify the production result. **Do not stop at a green PR, a merge, or a locally passing test; do not request a second deployment instruction or an advance-to-next-stage approval.** The operator does not need to supply a SHA in advance: Red obtains the full, immutable merge SHA after merging and checks exact-SHA CI before deployment. A code fix is not a completed hotpatch until the production cutover and verification are done.

Keep the hotpatch scoped to the requested problem; do not make speculative changes, expand spending permissions, or drop deployment safety checks. If an error truly prevents safe continuation, preserve the last healthy production state and report the concrete failure and blocked step. Otherwise **keep going**, including when another independent issue remains unresolved. Confirm the reported defect is fixed when the production check is authorized and feasible; if a paid or privileged end-to-end check is not authorized, report that specific verification gap without holding up unrelated safe checks.

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
