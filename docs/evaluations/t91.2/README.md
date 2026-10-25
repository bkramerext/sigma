# T91.2 packaged PDF and disaster-recovery acceptance

## Result

Acceptance executed against freshly built amd64 production-packaged backend and
frontend images using the local Compose edge, a disposable Docker volume, and
real Chrome 156. The backend image contains its pinned Tectonic 0.15.0 binary.
All test data was synthetic/deterministic and used simulated authenticated
sessions. No Google OAuth exchange, inference call, paid service, or GCP resource
was used.

### PASS / FAIL / BLOCKED matrix

| Acceptance item | Result | Evidence |
| --- | --- | --- |
| Actual packaged Tectonic compiles saved TeX | PASS | `tectonic` in the packaged backend compiled the saved source; strict `pypdf` parsing read one page and extracted “T91 packaged recovery acceptance”. |
| Authenticated API PDF download | PASS | Owner got `application/pdf` attachment; API bytes matched saved SHA-256 `8e4604f8e35a87f0592ca802170aa86d0398364617e146bb2b1f3d421e28a5c9` (4,782 bytes). |
| Malformed TeX failure/no partial PDF | PASS | Undefined TeX control sequence returned the explicit Tectonic compilation failure; paper archive entries were identical before and after. |
| Container recreation preserves TeX/PDF/report/session evidence | PASS | Forced backend recreation retained project, strategy and session identities, session outcome/artifacts, TeX source, PDF digest, and deterministic HTML report digest `284295274a8c1fd2e678b1983c0ea3256638f5f3971e9d6d864cc9f26d9dbcfa`. |
| Backup/restore into fresh storage | PASS | Stopped backend, tar-backed the complete auth/workspace volume, restored into a new named volume, then checked owner project, session and paper IDs and report/PDF hashes through the packaged API. |
| Cross-user isolation after restore | PASS | Simulated user B received 404 for owner's project, paper/PDF, report, and session evidence. |
| Failed restore is not called success | PASS | Invalid archive extraction returned nonzero; restore PASS was assigned only after valid restore plus owner/content/hash assertions. |
| Real Google OAuth / GCP / mounted persistent disk | BLOCKED (cloud-only) | No OAuth exchange, GCP host, Red-owned mount/bootstrap/systemd, or T100 persistent-disk run was attempted. |
| Paid/live inference | BLOCKED (excluded) | Deterministic session/archive fixtures; no inference was requested. |

## Commands and environment

- `DOCKER_CONFIG=/tmp/sigma-t91-2-docker-config ./deploy/validate-local.sh` —
  PASS, packaged images built and full Chrome acceptance completed. The temporary
  Docker CLI configuration exposed installed standalone Compose and Buildx
  plugins while preserving the local Colima context; no repository Docker config
  was changed.
- `env -u SIGMA_CLOUD_BOOTSTRAP_ADMIN_EMAIL ./sigma test` — full suite, result
  PASS: all scenarios, Ruff, formatting, Pyright, frontend typecheck and
  production build.
- `python3 -m py_compile browser_checks/t91_packaged_compose.py` — PASS.
- `git diff --check` — PASS.

The packaged workflow uses Docker's local Compose volume backend, not a mounted
GCE disk or `SIGMA_STORAGE_BACKEND=persistent_disk`. PDF compiler, download,
restart, and backup/restore acceptance are real local packaged runs, but do not
prove GCE disk attachment, production rootless daemon operation, actual OAuth,
public TLS, cloud backup policy, or recovery objectives.

Full suite passed all scenarios, Ruff, format, Pyright, frontend typecheck, and
production build. Total assignment elapsed time was approximately 16 minutes
(about 08:57–09:13 PDT, 2026-10-25). Commit and PR identifiers are reported in
[PR #113](https://github.com/bkramerext/sigma/pull/113), commit
`5c519ba0be92604e4507cd29ae90497c1924b7ab`, and the final response.

## Post-merge verification after Red PR #111

Fetched `origin/main` at `37637153c4daf0aa652b63a40cef5bf1f5b642ec` and merged it
into the T91.2 branch. `docs/STATUS.md` was the only conflict; both the T91.2
acceptance record and Red's T98 host-readiness record were retained. No code
conflicts occurred.

- `DOCKER_CONFIG=/tmp/sigma-t91-2-docker-config ./deploy/validate-local.sh` —
  PASS after merge, including packaged Chrome, real Tectonic, malformed TeX,
  backend recreation, fresh-volume restore, and post-restore isolation. The
  rerun PDF SHA-256 was
  `057c293aade96f34d9990e1697257da0f6da406990bb0b47e8397fb8451bd06c`; restored
  report SHA-256 was
  `fb08945053785e85e8f882517aaa98e2a0f582013f625f041dc9988b77f2ce29`.
- Bare `./sigma test` stopped at the pre-existing UI cleanup mock in
  `tests/tooling.py`, because this shell has `SIGMA_CLOUD_BOOTSTRAP_ADMIN_EMAIL`
  set. `env -u SIGMA_CLOUD_BOOTSTRAP_ADMIN_EMAIL ./sigma test` then passed all
  scenarios, including the newly merged `tests/gce_host.py`, Ruff, formatting,
  Pyright, frontend typecheck and production build.
- No paid calls, OAuth exchange, or cloud resources were used.
