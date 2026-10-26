# Green handoff — T173 R4R

- **PR:** [#177](https://github.com/bkramerext/sigma/pull/177), targets `main`; do not merge.
- **Branch:** `green/t173-release-smoke`
- **Base:** current `main` at `a335f3f782f12128dd4ca65ab4e0e504b35960cb` after rebase.
- **Head:** `cb5c420a21949751f06b2e5266ae000c067a4e1f`
- **Elapsed:** approximately 40 minutes from isolated worktree setup through PR creation.

Reviewed T129, T130, T135 and T136. The local rehearsal and evidence-backed
assessment are in [`docs/T173_RELEASE_REHEARSAL.md`](../docs/T173_RELEASE_REHEARSAL.md).
The critical finding was that a release-tagged Compose image with a build
context can build from the current checkout when the tag is absent. The new
builder checks exact clean SHA, builds both staging tags, promotes final tags
only when both builds succeed, and labels image revision. Production startup
uses `--no-build`. Runbook documents first deployment, backup/restore, DNS/TLS,
go/no-go and rollback criteria.

## Verification actually run

- `uv run --locked --no-sync python tests/release_rehearsal.py` — PASS. A fake
  Docker command fails the frontend build after backend staging; no promotion
  occurs. Wrong SHA and dirty source are rejected before Docker.
- `uv run --locked --no-sync python tests/storage.py` — PASS, including
  persistent-disk backend restart, two-subject isolation and full-root fixture
  restore.
- `bash deploy/validate-local.sh` — PASS. Real Docker Compose and Chrome tested
  project/strategy edit and reopen, five sessions, Outcome, report downloads,
  Tectonic/PDF, backend recreation, fresh-volume restore and workspace
  isolation. Temporary Compose resources were cleaned. OAuth/inference skipped.
- `npm --prefix frontend run build` — PASS separately; existing bundle-size
  advisory.
- Final `./sigma test` — FAIL on the three existing mount-contract expectations
  in `tests/deployment_package.py`, `tests/gce_host.py` and
  `tests/host_monitor.py`. Current main uses `RequiresMountsFor=/srv/sigma-state`;
  these expect the old escaped explicit mount dependency. Per assignment,
  coordinator-owned T163 integration remains untouched. Storage and release
  rehearsal passed within the run; Ruff check/format, Pyright (0 diagnostics),
  frontend typecheck passed. Frontend build was skipped by the runner and then
  passed separately.
- `git diff --check` — PASS.

**Assessment:** Local packaged smoke, failure gating and fixture data
preservation PASS. Production release readiness BLOCKED pending VM image build,
health-failure/startup rollback, live data comparison, actual GCE snapshot and
separate-disk restore, and public DNS/HTTPS. No GCE, live DNS, production
credentials, public endpoint or paid provider calls were used. Browser workflow
used deterministic identities; no OAuth exchange or inference occurred.
