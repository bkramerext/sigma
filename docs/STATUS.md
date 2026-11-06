# SIGMA status

## 2026-11-06 — Issue #590 release IAM setup; v0.2.1 deployment held

PR [#589](https://github.com/bkramerext/sigma/pull/589) fixed the local scored
sample migration test path and merged as
`994f714f299cb380e92f27753c4da8516e319d10`. Exact-merge Actions passed
[SIGMA verification](https://github.com/bkramerext/sigma/actions/runs/42242564357),
[browser verification](https://github.com/bkramerext/sigma/actions/runs/42242564360),
and [Ruff](https://github.com/bkramerext/sigma/actions/runs/42242564407).
`./sigma test` passed all configured steps on that SHA.

Issue #590 established keyless, separate `sigma-release-operator` and
`sigma-release-ssh` identities. The owner's project Owner grant was preserved;
neither release identity has Owner/Editor or user-managed keys. The recovery
identity is scoped to snapshots from `sigma-state`, release-prefixed temporary
recovery resources, and OS Login on recovery VMs. The host-only identity has
IAP/OS Login access to `sigma-gce-01` and `roles/iam.serviceAccountUser` on
`sigma-runtime` only; it has no Compute creation, deletion, attachment, or
service-account-change permission. Both use short-lived impersonation. Effective
permission checks and a five-minute-SSH-key IAP/OS Login session passed. Full
role boundaries and observed checks are in
[Operations Runbook](OPERATION_RUNBOOK.md#sigma-keyless-release-identities-2026-11-06-issue-590).

**Deployment is held at the operator's direction.** No production preflight,
recovery snapshot, isolated restore resources, or cutover was run. The
recovery-creation conditional permissions are configured but have not yet been
exercised with temporary resources. Select and freeze the release SHA only
after the owner updates the branch intended for deployment; then complete the
usual fresh snapshot/restore and exact-SHA release gates.

## SIGMA v0.2.0 production deployment (2026-11-04 PDT)

Production is running the approved `main` release at
`9d938907ffd02fb89c9d10545e8df61484310cbd` (v0.2.0). The exact merged commit
passed SIGMA test shards, Ruff, and browser acceptance in [SIGMA tests run
41977490940](https://github.com/bkramerext/sigma/actions/runs/41977490940),
[browser acceptance run
41977490915](https://github.com/bkramerext/sigma/actions/runs/41977490915), and
[Ruff run 41977490887](https://github.com/bkramerext/sigma/actions/runs/41977490887).
The documented guarded release helper completed successfully. The release
record, running image IDs, checkout, and protected release pin agree on this
commit. Backend and frontend image IDs are
`sha256:65572961183f12569854e5c0ee4c63744441dd616f1b37ed72caaa0490b7c750`
and `sha256:f2cb44d69a8a2b82d0596eca59b5a8880f360840adb964b4812981ef96093a4e`.

Before cutover, production was quiesced and the application-consistent recovery
snapshot `sigma-state-v020-pre-20261104-1736` was created and reached READY.
An isolated read-only restore drill passed three SQLite integrity checks,
three identity/workspace mappings, 14 projects, 33 artifacts, and preserved
job/accounting history; it found zero saved PDF/TeX pairs. The temporary clone
disk and recovery VM were removed and verified absent. No production data,
secrets, or configuration were changed, and no research/provider call was
initiated.

Production service and all three containers are healthy; the state disk is
mounted, maintenance is off, public HTTPS returns HTTP 200, and unauthenticated
API health returns the expected HTTP 401. Headless Chrome rendered the
production app and read About as `Version 0.2.0 · Build 9d93890`. OAuth login
redirected to Google without credentials being submitted. A public sample
research project/history view loaded without starting research or calling a
provider.

**Deployment is live and healthy; full production smoke acceptance remains
incomplete.** Positive authenticated login, project import/export, actual email
delivery, bounded research execution, and viewing a saved paper were not
verified because no authenticated production session was available. No research
was run in order to honor the no-provider-call constraint. These checks remain
outstanding and must not be reported as passed. Detailed evidence is in the
[operations runbook](OPERATION_RUNBOOK.md#sigma-v020-deployment-outcome-2026-11-04-pdt)
and [deployment runbook](DEPLOYMENT_RUNBOOK.md#v020-production-deployment-outcome--2026-11-04).

## Issue #458 — legacy Recent Projects pin migration (2026-11-01)

Reproduced the Saved Projects failure against this Mac account's existing
`~/.local/state/sigma` index without changing it. The state directory was owned
by the current user and mode `0700`; `recents.lock` and `recents.json` were
owned by the current user and mode `0600`. The 49,033-byte index was valid
schema v1 with 154 entries, each carrying the historical boolean `pinned`
field (two entries pinned). `_validate` raised `ValueError` because its exact
entry-key check allowed only the newer shape. Commit `4dc4f921` repaired modes
but did not account for this older entry schema, so `d4ab7d0` still returned
the generic unavailable response. A read-only preflight verified both saved
pins against their project IDs and found no family conflict.

Schema-v1 validation now accepts the legacy `pinned` boolean. Migration checks
each pinned entry against the project at its saved path and derives its pin
family from the verified project title before writing schema v2. A missing or
identity-mismatched project rejects migration and leaves the original index
bytes unchanged. The unavailable message no longer falsely diagnoses only
permissions. No repair was applied to the user's actual index during this
assignment; opening Saved Projects with the updated app performs the safe
one-time migration.

Verification: `uv run --locked --no-sync python tests/recents.py` passed,
including legacy pin preservation across a fresh process and rejection without
writing when project identity differs. Real Chrome on the local app rendered a
fixture Saved project and its pin indicator in Projects → Saved; authentication
and the Recent Projects response were deterministic browser fixtures, while
the migration service itself was exercised by the focused test. `./sigma test`
passed, including Ruff, formatting, Pyright (0 diagnostics), frontend typecheck,
and production build. The existing large JavaScript chunk advisory remains; the
optional graph-present Python sandbox scenario was skipped because its image is
not installed. No provider calls were made. Existing real-user Saved list
acceptance after applying the migration remains the user's confirmation gate.
