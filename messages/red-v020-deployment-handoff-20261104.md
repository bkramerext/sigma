# Red handoff — SIGMA v0.2.0 production deployment

**Target:** `9d938907ffd02fb89c9d10545e8df61484310cbd` (`main`)

**Recovery point:** `sigma-state-v020-pre-20261104-1736` (READY, restore-verified,
retained)

**Production:** Deployed using the documented guarded helper. The release
record, protected release pin, checkout and running image IDs match the target.
The service and all containers are healthy; persistent state mount is present;
maintenance is off; public HTTPS returns 200. About in Chrome shows
`Version 0.2.0 · Build 9d93890`.

**Exact-SHA CI:** SIGMA tests run 41977490940, browser acceptance run
41977490915, and Ruff run 41977490887 passed.

**Restore verification:** Three SQLite checks passed; 3 identities/workspaces,
14 projects, 33 artifacts, terminal job history, and 19 accounting rows were
verified read-only. Zero saved PDF/TeX pairs were present. Temporary recovery
VM and clone disk were removed and verified absent.

**Smoke status:** Anonymous production browser loaded the app and About; OAuth
redirected to Google without credential entry; public sample research/history
display succeeded without starting a research session or making a provider
call. Positive authenticated login, project import/export, actual email
delivery, bounded research execution, and saved-paper viewing remain
unverified because no authenticated production session was available. No
research/provider call was made. Deployment is live and healthy; full smoke
acceptance is incomplete.

See `docs/STATUS.md`, `docs/OPERATION_RUNBOOK.md`, and
`docs/DEPLOYMENT_RUNBOOK.md` for detailed evidence and remaining checks.
