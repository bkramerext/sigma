# Green handoff — T173 R4R

- **PR:** [#177](https://github.com/bkramerext/sigma/pull/177), targets `main`; do not merge.
- **Branch:** `green/t173-release-smoke`
- **Base:** current `main` at `a335f3f782f12128dd4ca65ab4e0e504b35960cb` after rebase.
- **T173 head:** pending this handoff commit; record final SHA from `git rev-parse HEAD` after push.
- **T129 code exercised:** PR #161 head `c19e1d654f27be6f736f1aea382033e9d79080da` in detached worktree `/Users/admin/sigma_t129_review`.
- **Elapsed:** approximately 25 minutes from isolated worktree setup through this handoff; additional polling follows.

Reviewed T129/T130/T135/T136. T129's exact-SHA image build, protected release
pin and automatic startup rollback are already implemented in coordinator-owned
PR #161. T173 does not duplicate or modify that implementation. The assessment
and first-production checklist are in
[`docs/T173_RELEASE_REHEARSAL.md`](../docs/T173_RELEASE_REHEARSAL.md).

## Verification actually run

- In T129 isolated worktree:
  `uv run --locked --no-sync python tests/deployment_automation.py` — PASS
  for same-release idempotency, missing configuration, simulated candidate
  startup failure, prior checkout/pin restoration, sanitized diagnostics and
  fixture state preservation.
- In T173 worktree:
  `uv run --locked --no-sync python docs/evaluations/t173/build_failure_rehearsal.py --deployment-script /Users/admin/sigma_t129_review/deploy/deploy-gce-release.py`
  — PASS. Compose build exit 17 occurred before service stop or checkout/pin
  changes; deployment env bytes and the temporary state marker stayed equal.
- `bash deploy/validate-local.sh` — PASS. Real Docker Compose and Chrome
  validated packaged app workflows, five saved sessions, reports, Tectonic/PDF,
  backend recreation, fresh-volume fixture restore and user isolation. Temporary
  Compose resources were cleaned. OAuth/inference skipped.
- `uv run --locked --no-sync python tests/storage.py` — PASS.
- `npm --prefix frontend run build` — PASS separately, existing bundle advisory.
- `./sigma test` — three failures in existing systemd mount expectations in
  `tests/deployment_package.py`, `tests/gce_host.py`, `tests/host_monitor.py`;
  current `main` uses `RequiresMountsFor=/srv/sigma-state`, while those tests
  expect the old explicit escaped dependency. Coordinator T163 integration owns
  them; T173 leaves them untouched. Ruff, format, Pyright, frontend typecheck
  and standalone frontend build passed.
- No GCE, live DNS, production credentials, public endpoint, or paid provider
  call occurred.

**Assessment:** The local packaged smoke, T129 failed-build gate, simulated
startup rollback and fixture data preservation PASS. Source-to-image SHA
pinning **FAILS** in T129 PR #161: an isolated fixture observes Compose build
with the previous checkout while `SIGMA_RELEASE` is the candidate SHA, then a
checkout happens afterward. Require the coordinator's T129 integration to fix
and test this before GO. Production release readiness is BLOCKED pending this
correction plus live host build/start/health failure/rollback, live data
comparison, actual GCE snapshot/separate-disk restore, and public DNS/TLS.
