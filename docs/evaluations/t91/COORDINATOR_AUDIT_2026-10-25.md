# T91 Coordinator pre-cloud integration audit — 2026-10-25

**Decision: NOT YET ACCEPTED.** This is an audit of actual current-main repository evidence, performed by the coordinator, not a worker assignment or a new launch acceptance. No live OAuth, hosted GCP session, provider call, root/installer action, or clean-room local browser execution was performed in this audit.

**Current main examined:** `f76d834cf5a437651799e4163a3e683618f1f77e` (PR #108). The latest main `SIGMA verification` and `Research Outcome browser acceptance` workflows succeeded. Existing local packaged acceptance was previously recorded under `docs/evaluations/t91/README.md` and `docs/evaluations/t91.2/README.md`.

| T91 gate | Status | Evidence / remaining action |
| --- | --- | --- |
| Research 13–17 integration | PASS (engineering) | PR #112 is merged; the research-superiority claim remains unverified, as acknowledged in STATUS. |
| Packaged local project → strategy/session → Outcome → HTML export | PASS (previous executed evidence) | T91 packaged Compose real-Chrome run tested sample copy/edit, persisted five saved sessions and Mixed Outcome, report download, restart and cross-user 404 isolation. Not re-executed here. |
| Saved TeX → actual PDF, restart, backup/restore, isolation | PASS (previous executed evidence) | T91.2 production-packaged Compose acceptance tested real Tectonic, PDF byte checks, malformed TeX failure, restore hashes and cross-user isolation. Not a real GCE or OAuth test. |
| Full integrated tests | PASS (CI at main head); local rerun pending | Both main-head workflows passed after PR #108; this coordinator environment has no checked-out SIGMA worktree or Docker/Chrome acceptance environment, so `env -u SIGMA_CLOUD_BOOTSTRAP_ADMIN_EMAIL ./sigma test` and a *fresh* clean README onboarding run have **not** been executed by this audit. |
| README / WOLF (#86) | BLOCKED: owner acceptance | Both files exist and contain substantive explanations; README local Markdown relative paths referenced at main all resolve. Explicit T91 requirement remains: two approved screenshots, verified clean onboarding instructions, and owner-approved final WOLF application response. README currently has no embedded Home/RH screenshots. Do not silently waive. |
| About expanded (#87) | BLOCKED: owner acceptance / merge | PR #108 merged project About refinements, but #87 remains OPEN; review against its dedicated multi-agent expanded specification and secure explicit owner visual approval before disposition. |
| Stock sample catalog (#89, PR #74) | PARTIAL | PRs #115 and #120 landed audit/curation; PR #74 remains OPEN. Compare content against current catalog, explicitly dispose PR #74, and secure required owner approval for substantive sample changes. |
| Assets (#79, PR #83) | PENDING MERGE | PR #83 remains OPEN. Reconcile/merge and then close #79 only after confirming current asset references still work. |
| Research integrity contract (#71) | PARTIAL | The T91/T91.2 fixtures verified persisted research and truthful Mixed status; the separate T71 scope remains open. No scientific superiority assertion is made. |
| Broader repo / packaging / secrets audit | PARTIAL | Checked README repo-relative Markdown links against main tree (all resolved). Not a substitute for running Chrome 404 diagnostics, packaged bootstrap from a clean machine, or an automated secrets audit. |
| Cloud transition decision | PENDING | T91 explicitly requires owner approval of transition after reviewing material blockers. This coordinator audit does not grant it. |

## Newly observed integration issue outside T91 acceptance

Gray PR #124 broadens lint scope to `browser_checks`. Its final-commit Ubuntu workflow #445 failed Ruff on **two pre-existing browser fixture style findings** now included in the check: `browser_checks/project_create_contract.py` SIM114 duplicate branches and `browser_checks/t47_conclusion.py` I001 import order. Earlier workflow #443 passed, but #445's failure must be corrected or explicitly dispositioned before #124 can merge. This is not an installer regression; host-focused checks ran before the failing full-suite stage.

## Coordinator action order

1. Review/merge or explicitly disposition #83; finish acceptance of #87 and reconcile already merged #108.
2. Reconcile #74 with merged #115/#120; verify catalog, require owner approval where scope states it.
3. Finish/secure owner sign-off on #86 WOLF and README screenshots; verify fresh documented onboarding.
4. Run exact-main local acceptance, browser 404/asset/links, relevant auth/project/Sample/Outcome/export checks, and reread current STATUS for honest claims. Existing T91 and T91.2 evidence reduces duplication, but must not be passed off as newly run.
5. Record all specific owner decisions; then ask for final T91 gate acceptance. Keep #91 open until every required gate is met or explicitly changed by the owner.

**Scope discipline:** This is a bounded evidence audit. Do not create another polish sprint or duplicate Red's cloud testing. The separate production OAuth / hosted persistent disk / cloud authorization work belongs to the Cloud stream.
