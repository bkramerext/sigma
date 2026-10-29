# PR #325 documentation accuracy — Red R4R

**PR:** #325, `chat/readme-technical-accuracy` against `main`  
**Implementation commit:** `163b77e4295936e3157e6b7dd6ae15909a111d08`  
**R4R:** Ready for independent review. Do not merge.

## Files in the PR

The coordinator's earlier commits changed `README.md`,
`docs/CLOUD_DEPLOYMENT.md`, and added `docs/LOCAL_MOCK_AUTH.md`. This follow-up
changes:

- `README.md` — describes the actual locked setup steps, records isolated
  checkout verification without calling it a clean-machine test, and clarifies
  persistent administrator/contact semantics.
- `docs/CLOUD_DEPLOYMENT.md` — replaces stale duplicated provisioning recipes
  with an evidence-based current deployment inventory, runtime/security
  boundaries, exact release SHA, backup/rollback state, administrator binding,
  historical sizing/cost context, and explicit acceptance gaps. Operational
  commands point to the runbook.
- `docs/OPERATION_RUNBOOK.md` — corrects its current release, recovery, billing
  and cloud-doc link records, and labels new-host provisioning as inapplicable
  to the existing production VM.
- `docs/STATUS.md` — records the checks performed and remaining unknowns.
- `messages/pr325_red_documentation_accuracy_r4r.md` — this handoff.

## Verification performed

- `./sigma setup` passed in a fresh detached Git worktree at the implementation
  commit on the existing macOS 14.6 Apple Silicon host. It used CPython 3.14.7,
  Node 24.21.0, npm 11.19.0, `uv sync --locked --group dev`, and `npm ci`.
- `./sigma start` served the frontend (HTTP 200) and local API. The API's
  `/api/cloud-auth/status` reported local readiness. I stopped the process with
  Ctrl+C. This was not a clean-machine test and did not test Google OAuth.
- `uv run --with playwright --no-sync python browser_checks/guest_samples.py`
  passed in real Chrome using temporary fixture storage; no OAuth or provider
  calls.
- `./sigma test` passed all scenarios, Ruff, formatting, Pyright (0 diagnostics),
  frontend typecheck, and production build. Its optional graph-present Python
  sandbox case was skipped because the local sandbox image is unavailable.
- A local Markdown target/anchor check passed for README, Status, Cloud
  Deployment, Operations Runbook, and Local Mock Authentication. `git diff
  --check` passed.
- Source review of `cloud_auth.py`, `gce_preflight.py`, Compose, and
  `tests/cloud_auth.py` confirms first subject binding, retained bootstrap admin
  privileges, later contact subject binding, persistence across contact
  changes, and rejection of `SIGMA_CLOUD_BOOTSTRAP_ADMIN_EMAIL`.

No GCP resources, production settings, credentials, or real accounts were
accessed. No deployment, OAuth exchange, paid inference, or provider call was
performed.

## Remaining unknowns and unvalidated claims

- Production Google OAuth, real authorized/denied identities, administrator
  operations, invitation email delivery, and identity-based workspace
  separation remain unverified.
- No production research session or inference was started; provider quality,
  hosted research workflow, and actual billing behavior were not tested.
- The one-off `sigma-state-v014-20261029-0606` snapshot was not itself restored.
  The daily backup timer and `/etc/sigma/backup.env` are absent; restore and
  rollback on deployed data remain unverified.
- A fresh production reboot, target-host rootless runner isolation, and external
  operational alert delivery remain unverified.
- Current GCP trial eligibility/expiry, project billing association, available
  credit, alert delivery, current spend, and current pricing have not been
  verified. Historical estimates are not current cost claims.
- README setup was exercised on one existing macOS host through an isolated
  worktree, not on a clean machine or a Linux host. The minimum Python version
  and other supported OS versions were not tested here.
- The About view's build SHA is still `unknown` even though host checkout and
  image labels independently identify the deployed source commit; see
  `docs/STATUS.md`.

The implementation commit SHA above is the verified code head. This handoff is
committed immediately afterward; the final PR branch head is the handoff commit
that contains this file.
