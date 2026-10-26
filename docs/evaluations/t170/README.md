# T170 pre-deployment research workflow acceptance

## Assessment

This is **simulated acceptance**, not production deployment acceptance. The
existing services and browser workflow passed local checks, including real
Python/Sage containers and a real Chrome session against packaged Compose.
Production OAuth, the GCE persistent disk, rootless sandbox daemon, hosted
provider workflows, and the live T137 launch decision remain unverified or
blocked. No provider calls, paid usage, or GCE operations occurred.

| Workflow | Result | Evidence and boundary |
| --- | --- | --- |
| Project creation and research-session lifecycle | **PASS (simulated)** | `./sigma test`: lifecycle, `tests/project_creation.py`, `tests/research_sessions.py`; T91 packaged Chrome created a sample copy, edited project/strategy, reopened it, and reviewed saved sessions. Session work is deterministic fixture data. |
| Persistent evidence and continuity across sessions | **PASS (simulated)** | `tests/epistemic_continuity.py`, `tests/continuations.py`, `tests/research_feedback.py`, `tests/computational_evidence.py`, `tests/cloud_workspaces.py`, and `tests/storage.py` passed within the suite. T91 Chrome verified saved IDs, Outcome, artifacts, TeX/PDF and report through backend recreation and fresh-volume restore. GCE disk/systemd recovery is not tested. |
| Isolated Python and SageMath execution | **PASS (local Colima simulation); BLOCKED (production rootless daemon)** | `uv run --locked --no-sync python -m sigma.cloud_runtime_check --allow-nonrootless-dev` passed both runtimes. They ran as UID 65532; host sentinel, state directory, network, and Docker socket were blocked; captured artifacts round-tripped. The observed daemon was Colima with `daemon_rootless: false`. The acceptance option explicitly permits local development and is not production rootless evidence. |
| Outcome generation and research reports | **PASS (simulated)** | `tests/research_sessions.py`, `tests/project_reports.py`, `tests/increment13_integrity.py`, `tests/papers.py`, and `tests/text_views.py` passed. Chrome rendered the saved Outcome in both views and downloaded the audit, text, and HTML reports. The session/Outcome is fixture-authored; no live model generation was run. |
| Markdown, LaTeX, and PDF exports | **PASS (local packaged application)** | Chrome downloaded the Project Audit JSON, text and HTML reports, compiled fixture TeX with Tectonic, downloaded and parsed the PDF, and checked persistence/recovery hashes. `tests/project_reports.py`, `tests/papers.py`, and `tests/text_views.py` passed. Provider-authored paper generation remains unverified. |
| Hosted production acceptance / T137 go-no-go | **BLOCKED** | No approved live host/release, real OAuth test identities, production persistent-disk recovery, rootless target-host proof, or separately authorized hosted provider window was available. T132 and T133 both explicitly defer hosted acceptance; T137 remains pending. |

## Existing coverage review and gap

T99.1 already exercises production FastAPI routes over a deterministic fake
provider for sponsored credential selection, missing credentials, limits,
concurrency, uncertain outcomes, restart recovery, and workspace artifacts.
T132 already records research and Python/Sage offline scenarios plus the
target-host and hosted procedures. T133/T91 already cover packaged Chrome,
Outcome rendering, reports, TeX/PDF, restart/restore, and isolation. T137
requires real deployment evidence and a signed go/no-go. These existing checks
were reused; no product workflow defect or missing deterministic behavior
regression was found that justified adding a new product test.

One evidence gap was concrete: the existing T91 browser check deleted the
downloaded exports with its temporary directory, so the coordinator could not
inspect the bytes from a completed acceptance run. Its optional
`SIGMA_T91_EVIDENCE_DIR` now retains the original app-downloaded JSON/TXT/HTML,
the fixture TeX/PDF, and a manifest with source project/session/paper IDs,
activity, limits, and hashes. With the variable unset, existing behavior is
unchanged. This only improves evidence capture; it does not change product
behavior or turn fixture-backed checks into production acceptance.

The packaged acceptance artifacts are in [exports](exports/). Source project
ID `1d33446e-8148-4fe0-8308-68631f2aeaed`, session ID
`1a9a0c44-48ae-49e7-8bea-0e8d47297f9d`, and paper ID
`4d0f00caff7c2bcb53d2b3b8ef0896ec` are from this real browser run. The project
is a copy of the Nonconsecutive Subset Sums stock sample. The saved session is
stock deterministic research; the paper is a deterministic fixture-authored
TeX document, not provider-generated research. The browser used two simulated
Google subjects. No secrets or live user data are retained.

## Test evidence

- `./sigma test`: **FAIL**, with three deployment assertions in
  `tests/deployment_package.py`, `tests/gce_host.py`, and
  `tests/host_monitor.py`. Each expects the old escaped systemd mount-unit
  dependency `srv-sigma\\x2dstate.mount`; current `main` uses
  `RequiresMountsFor=/srv/sigma-state`. This is a real full-suite failure and
  remains an integration/release blocker. The suite continued through Ruff
  (pass), Pyright (0 errors/warnings), and frontend typecheck (pass), then
  skipped the frontend production build after the earlier failures.
- Relevant project, research, continuity, execution-contract, reports, papers,
  sponsored API, workspace, and storage scenarios listed above all passed as
  steps within that run.
- `uv run --locked --no-sync python -m sigma.cloud_runtime_check --allow-nonrootless-dev`:
  **PASS**, with local Colima limitations stated above.
- `bash deploy/validate-local.sh`: **PASS**. Real Chrome against packaged
  frontend/API/edge; local backend restart and restore; no OAuth/provider call.
- `SIGMA_T91_EVIDENCE_DIR="$PWD/docs/evaluations/t170/exports" bash deploy/validate-local.sh`:
  **PASS**, same matrix with source exports retained. All five export file
  hashes and sizes are recorded in `exports/MANIFEST.json`.
- `ruff check` and `ruff format --check` for the modified browser check:
  **PASS** after formatting.

No paid calls, provider calls, GCE operations, or production instance access
occurred. Production deployment is **BLOCKED** pending the T127/T129/T131
readiness prerequisites, operator-approved host/release and backup window,
real authorized identities, target-host rootless sandbox proof, separately
authorized provider limits for any live generation, and coordinator/owner T137
review. See [T132](../../../tickets/t132.md), [T133](../../../tickets/t133.md),
and [T137](../../../tickets/t137.md).

## Current-main follow-up (2026-10-26)

On current `main` `8e8d979`, the earlier three full-suite failures were traced
to stale test expectations for the removed explicit
`srv-sigma\\x2dstate.mount` dependency. The service unit uses
`RequiresMountsFor=/srv/sigma-state`, which supplies the mount dependency and
ordering. Updated only those deterministic assertions in
`tests/deployment_package.py`, `tests/gce_host.py`, and
`tests/host_monitor.py`; no deployment unit or runtime behavior changed.
`./sigma test` then passed all scenarios, Ruff, formatting, Pyright (0
diagnostics), frontend typecheck and production build.

Re-ran `uv run --locked --no-sync python -m sigma.cloud_runtime_check
--allow-nonrootless-dev`: Python and SageMath both passed in local Colima
containers as UID 65532 with host secret/state, network and Docker socket
blocked; evidence artifacts persisted. The daemon again reported
`daemon_rootless: false`. This confirms local isolated execution only, not the
production rootless host requirement. Real Chrome packaged Compose acceptance
also passed again; see [T173 smoke and rollback assessment](../t173/README.md).
