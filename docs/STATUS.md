# SIGMA status

## T93 Conclusion Markdown and math rendering (2026-10-25)

Markdown-rendered Conclusions now show a neutral loading message while the lazy
renderer loads instead of briefly presenting raw Markdown as if it were the
rendered result. Explicit legacy LaTeX `\(...\)` and `\[...\]` delimiters are
translated for `remark-math`; empty math blocks are omitted from rendered mode,
compact standalone legacy formula lines and unambiguous inline powers are typeset
conservatively. Outcomes
with recognizable math open in rendered mode by default; ordinary prose keeps
its existing mode. The source toggle continues to show the original saved text
unchanged. A real-Chrome regression covers the live RH-style `### Preliminary
finding` heading, display and inline equations, an un-delimited zeta formula, an
inline exponent in prose, an empty math block, and both rendered/source modes at
desktop and 375/320 px widths. `./sigma test` passed
with `SIGMA_CLOUD_BOOTSTRAP_ADMIN_EMAIL` unset (the first run with it set failed
an existing UI lifecycle cleanup assertion); focused Chrome check
`uv run --with playwright python browser_checks/t47_conclusion.py`, frontend
typecheck, and `git diff --check` passed. No provider calls or cloud changes.

Follow-up: the Conclusion Markdown toggle had been missed by the earlier
Outcome-heading styling because it renders in `.outcome-conclusion-actions`.
That left it inheriting the generic workspace button padding/border, while its
SVG had no size rule and rendered at 0×0: Chrome showed a 42×50 empty outlined
box. The Conclusion action now uses the same 28×28 borderless control and 24×20
glyph as the Outcome heading. The focused Chrome regression asserts those
dimensions and transparent hover surface while continuing to verify rendered
Markdown/TeX and raw-source modes. Focused Chrome passed at 1440/375/320 px; the
full `env -u SIGMA_CLOUD_BOOTSTRAP_ADMIN_EMAIL ./sigma test` passed. No provider
calls or cloud changes.

The next Chrome inspection exposed a separate issue: the pressed copper icon
could accompany raw formula characters because the Conclusion was only passed
through the local Markdown/KaTeX parser. It now uses the same AI formatting
endpoint and preservation instructions as project text, with an explicit
user click. The source digest is checked before and after conversion; formatted
Markdown stays in the view state and the saved session archive is never edited.
The button stays gray in plain mode even under hover and turns copper when the
formatted result is displayed. An offline API regression checks display-math
and layout instructions plus byte-identical saved history. Real Chrome with a
mocked conversion checked the RH-style source, formatted line breaks and three
display equations at 1440, 375 and 320 px; screenshots are in `/tmp/sigma-conclusion-ai-desktop.png`,
`/tmp/sigma-conclusion-ai-375.png` and `/tmp/sigma-conclusion-ai-320.png`. No
provider calls or cloud changes.
## T91.2 packaged PDF and disaster-recovery acceptance (2026-10-25)

Started on fresh branch `gray/t91.2-packaged-pdf-recovery` from current `main`
`5fa536b`. Extended the packaged Compose / real-Chrome check with real Tectonic
0.15.0 compilation from a saved TeX source inside the backend image, strict PDF
parsing and extracted-content checks, authenticated API download/hash comparison,
malformed-TeX failure/no-publication checks, backend container recreation, and
full auth/workspace-volume backup to a new disposable Docker volume. The restore
check compares owner project/strategy/session/paper identities, TeX and PDF
hashes, session outcomes/evidence, and deterministic HTML report hash. A second
simulated user remains denied after restore. Invalid tar extraction returns
nonzero and cannot mark the restore accepted.

**Acceptance matrix for the five requested criteria: PASS 5, FAIL 0, BLOCKED 0.** The packaged
workflow also reports PASS for its existing UI/report/persistence checks; three
cloud/provider checks are explicitly SKIPPED. Details, hashes and exact commands: [T91.2 evidence](evaluations/t91.2/README.md).
The packaged run's PDF was 4,782 bytes, SHA-256
`8e4604f8e35a87f0592ca802170aa86d0398364617e146bb2b1f3d421e28a5c9`; the
restored HTML report SHA-256 was
`284295274a8c1fd2e678b1983c0ea3256638f5f3971e9d6d864cc9f26d9dbcfa`.
No paid inference, Google OAuth exchange, GCP resource, or rootless host
acceptance was used. GCE disk attachment, Red-owned bootstrap/mount/systemd,
public TLS/OAuth, and persistent-disk-on-GCE remain cloud-only limitations.

Validation passed: `DOCKER_CONFIG=/tmp/sigma-t91-2-docker-config
./deploy/validate-local.sh` (fresh amd64 backend/frontend builds and packaged
Chrome matrix); `env -u SIGMA_CLOUD_BOOTSTRAP_ADMIN_EMAIL ./sigma test` (all
scenarios, Ruff, formatting, Pyright, frontend typecheck and production build);
Ruff check/format for the browser acceptance script; `python3 -m py_compile
browser_checks/t91_packaged_compose.py`; and `git diff --check`. Assignment elapsed time was approximately 16 minutes (08:57–09:13 PDT,
2026-10-25). Implementation commit `5c519ba0be92604e4507cd29ae90497c1924b7ab`;
[PR #113](https://github.com/bkramerext/sigma/pull/113).

Post-merge verification after Red PR #111: fetched `origin/main` at
`37637153c4daf0aa652b63a40cef5bf1f5b642ec` and merged it into T91.2. The only
conflict was `docs/STATUS.md`; both acceptance entries were preserved, with no
code conflicts. `DOCKER_CONFIG=/tmp/sigma-t91-2-docker-config
./deploy/validate-local.sh` passed again, including packaged Chrome, real
Tectonic, malformed TeX, backend recreation, fresh-volume restore and isolation.
The rerun PDF SHA-256 was
`057c293aade96f34d9990e1697257da0f6da406990bb0b47e8397fb8451bd06c`; report
SHA-256 was `fb08945053785e85e8f882517aaa98e2a0f582013f625f041dc9988b77f2ce29`.
The requested bare `./sigma test` stopped at existing `tests/tooling.py` cleanup
because `SIGMA_CLOUD_BOOTSTRAP_ADMIN_EMAIL` is set in this shell;
`env -u SIGMA_CLOUD_BOOTSTRAP_ADMIN_EMAIL ./sigma test` passed all scenarios,
including merged `tests/gce_host.py`, Ruff, formatting, Pyright, frontend
typecheck and production build. No provider calls, OAuth, or GCP resources were
used.
## T98 production host readiness pre-cloud (2026-10-25)

Added a pinned Ubuntu 24.04 amd64 host installer for Docker Engine/Compose v2
and the dedicated rootless `sigma-sandbox` daemon, a rootless-only runner image
builder, systemd startup ordering/restart units, and a read-only `PASS`/`FAIL`/
`BLOCKED` production host preflight. The preflight validates the protected
non-secret environment file, secret-file metadata without reading values, disk
mount/ownership and sandbox denial, daemon/socket mode, runner images, Compose
health dependencies, and guarded startup configuration. The runtime proof now
checks that Python and Sage runners cannot access host state or the daemon
socket, in addition to host secrets and network. Production rootless checks
remain mandatory; no Docker Desktop override was used for production acceptance.

The full `env -u SIGMA_CLOUD_BOOTSTRAP_ADMIN_EMAIL ./sigma test` suite passed,
including host, deployment, cloud, sponsored inference, storage, user-isolation,
backup/restore, and Recent relocation coverage. Ruff check/format, Pyright,
frontend typecheck/build, and `git diff --check` passed. On this macOS
workstation the preflight reported `BLOCKED` for Ubuntu/Linux-only checks, the
installer exited `2` before package changes, and `python -m
sigma.cloud_runtime_check` without the dev override refused the selected
non-rootless daemon. Ubuntu 24.04 installation, `systemd-analyze`, actual
rootless daemon/socket permissions, image builds, disk mount, and runtime escape
probes still require an Ubuntu 24.04 amd64 Linux host. No GCP resources, DNS,
OAuth, Secret Manager, credentials, or paid inference were used. See
`messages/t98_red_host_readiness.txt` for rerun commands and commit details.
## T41 — Sponsored cloud inference verification (2026-10-23)

Added deterministic sponsored-inference API coverage through the production
FastAPI routes and a fake OpenAI HTTP transport. The check exercises cloud-only
credential selection, model discovery, successful Responses usage settlement,
idempotency, authenticated workspace isolation, explicit unconfigured behavior,
provider HTTP failure and timeout handling, uncertain-charge holds without
replay, and allowance exhaustion before provider dispatch. No live provider,
cloud resources, UI changes, or product implementation changes were needed.

The T41-specific test lives in `tests/cloud_research_sponsored_api.py` and is
registered in `./sigma test`. Current-main `tests/cloud_research_api.py` remains
intact with T99 budgeted-inference parity coverage, including its own API
failures, timeout, quota and cross-owner checks. The T41 scenario uniquely
exercises the production sponsored credential and Responses transport for
research-session dispatch; shared cloud-ledger tests cover contention and
restart/recovery.
## T100 persistent-disk storage (2026-10-25)

Implemented opt-in `SIGMA_STORAGE_BACKEND=persistent_disk` with a validated
private `SIGMA_STORAGE_ROOT`, while preserving `local` as the default. The
authenticated workspace services now cover projects, strategies, sessions,
evidence/artifacts, Recents, paper files, and research accounting. GCE Compose
settings and a host mount guard are included. No GCP resources, OAuth exchange,
or paid inference were used.

Validation passed: `env -u SIGMA_CLOUD_BOOTSTRAP_ADMIN_EMAIL ./sigma test`,
focused persistent workspace/research tests, Ruff, Pyright, and
`git diff --check`. Real Chrome exercised sample copy, project and strategy
edits, save/reload/reopen, backend restart, Recent identity, cross-subject
denial, and stock-sample immutability; screenshot and transcripts are in
[T100 evidence](evaluations/t100/README.md). A disposable local Docker volume
and backend image retained auth data through restart and container recreation.
Negative root, symlink, permissions, traversal, corrupt mapping, and missing
mount checks passed. The local Docker installation lacks Compose v2, so merged
Compose configuration and a real GCE disk mount are unverified; YAML parsing
and the guard's missing-mount check passed. Production startup now uses the
guarded host script from the deployment runbook, with `/etc/sigma/deploy.env` as
its default env file; the exact env-file handoff and refusal to invoke Docker on
a missing mount are covered in `tests/storage.py`. See
`messages/t100_red_r4r.txt` for the complete handoff and commit details.
## T86 README validation (2026-10-25)

Rewrote the newcomer README with a local quick start, optional AI/API-key
configuration, a separate optional local Google administrator bootstrap, and
links to the main product and engineering guides. The owner deferred Home and
RH screenshots until after cloud launch; README contains no screenshot
placeholders or substitute images.
Setup and bootstrap details were checked against `./sigma setup`,
`src/sigma/ui.py`, `src/sigma/local_config.py`, and the local Google sign-in
section of `CLOUD_DEPLOYMENT.md`.

`./sigma setup` passed. `env -u SIGMA_CLOUD_BOOTSTRAP_ADMIN_EMAIL ./sigma test`
passed all scenarios, Ruff, formatting, Pyright, frontend typecheck, and
production build. An actual local `./sigma start` reached ready state; frontend
and API health URLs returned HTTP 200, and `./sigma shutdown` completed. The
checkout contained Google OAuth client settings but no bootstrap email in that
launch environment, so the observed run stayed in local single-user mode and
printed its existing configuration warning. Credentialed Google sign-in was
not exercised. The updated T86 assigns WOLF drafting to ChatGPT after Brian
approves its outline; Gray's work on this branch is limited to the README.
## T99 Blue: Python/SageMath and TeX/PDF runtime increment (2026-10-25)

Pinned Tectonic 0.15.0 into the backend image using the official x86_64 Linux
musl release asset and a SHA-256 checked download. Paper versions now retain the
exact TeX source used for compilation beside the frozen evidence snapshot and
the existing hash-checked PDF in the project's paper archive. No cloud storage
adapter or sponsored-inference accounting code changed.

Added `python -m sigma.cloud_runtime_check`, an opt-in smoke proof that checks
the selected Docker daemon reports rootless mode, executes real Python and
SageMath through the existing bounded executor, verifies non-root/no-network/
no-host-secret access, retrieves preserved execution artifacts, compiles actual
TeX to PDF, and verifies source/evidence/PDF round trips. The local command in
`CLOUD_DEPLOYMENT.md` explicitly permits Docker Desktop/Colima for development;
the GCE command omits that override and requires the dedicated rootless daemon.

Observed locally on Colima: both images completed against their resolved image
IDs; both reported UID 65532, blocked the disposable host-secret probe and
network probe, and round-tripped `runtime-evidence.json`. TeX compiled to a
5,747-byte PDF; the paper archive returned byte-identical TeX, evidence
snapshot, and PDF. The smoke computes the SHA-256 from the real saved-project
snapshot using the paper service's canonical JSON encoding, then recomputes it
from the reloaded snapshot and compares it with the stored digest. Separately,
the built cloud backend image reported Tectonic
0.15.0 and compiled a real 4,160-byte PDF under the backend's non-root/read-only
container settings. Local Docker reported `daemon_rootless: false`; actual
rootless daemon execution and host-boundary attacks remain **UNVERIFIED** until
Red reruns the documented command on GCE. No Google Cloud resources or inference
provider calls were used.

Validation: `env -u SIGMA_CLOUD_BOOTSTRAP_ADMIN_EMAIL ./sigma test` and focused
paper tests passed. The first bare `./sigma test` attempt failed in the
pre-existing UI tooling scenario because this shell has a bootstrap-admin
environment setting. A later attempt also showed the fresh worktree lacked
frontend dependencies; after `./sigma setup`, the environment-adjusted full
suite passed, including Ruff, formatting, Pyright, frontend typecheck, and
production build. Backend Docker image build and in-image Tectonic compilation
passed. The runtime smoke script was exercised on actual Docker containers.
The GCE command and real rootless execution remain a required Red follow-up;
hosted AI paper generation, identity authorization, restart persistence, and
sponsored budget operations are outside this Blue runtime increment.
## T99 Blue: sponsored inference outside sessions (2026-10-25)

Started from current `main` at `d4ca2194b68314336855823970b4b97f55c1256a` on
the isolated `t99-cloud-inference-parity` branch. Reused the existing durable
cloud call ledger for standalone proposal calls, agentic proposal steps, text
conversion, and one-shot paper generation. Each provider attempt now reserves a
per-user/global spend amount, token ceiling and concurrent slot before dispatch,
then reconciles reported usage using the reviewed model prices. Provider failures
and interruptions after dispatch retain the reservation as an unknown charge.
Cloud inference accepts only the server-side sponsored API credential. Existing
project ownership checks, cancellation paths and LOCAL credential selection
remain in place.

Removed the cloud 403 gates from the four operation routes after adding ledger
admission at each provider-call site, including every long-form paper stage.
Paper preflight and checkpoint restart are available to authenticated owners as
well. Cloud provider quality, live OIDC, hosted persistence, cloud browser
behavior, and TeX compilation on the hosted VM were not exercised; no paid calls
or cloud resources were used.

`docs/CLOUD_DEPLOYMENT.md` still describes these routes as disabled; that
Red-owned deployment document was left untouched for its owner to reconcile.
## T99.1 Blue: pre-cloud sponsored inference acceptance (2026-10-25)

Extended the existing `tests/cloud_research_api.py` scenario rather than adding
a test harness. It uses the production FastAPI app, a test-only verified
principal adapter, temporary but persistent authenticated workspaces and
SQLite ledger, the real hosted `auth_context`/configuration path, and an
offline `httpx.MockTransport` provider fixture. A personal API key is present
as a decoy; all Responses calls carry only the sponsor credential. No real
provider calls, GCP resources, or paid usage occurred.

**Acceptance matrix tally: PASS 7, FAIL 0, BLOCKED 0.**

| Acceptance item | Result | Evidence |
|---|---|---|
| Proposal, agentic proposal, Markdown conversion, one-shot and long-form paper endpoints | PASS | Existing production-route scenario; Responses fixture returns schema-valid payloads and each operation reconciles ledger calls. |
| Sponsored key precedence and absent-key rejection | PASS | Real auth adapter reports `cloud_service_api_key`; server key is used with a personal key configured; removing the server key leaves provider dispatch count unchanged. |
| Per-user and global spending ceilings; concurrent admission; quota preflight | PASS | Full global pool blocks a second authenticated user before dispatch; a raised global ceiling with the second user's allowance exhausted blocks that user's next dispatch; same-user simultaneous operation is rejected while the first provider call is held. |
| Timeout, malformed response, cancellation, uncertain charge | PASS | HTTP 429, read timeout, completed response with missing usage/malformed output, and explicit cancellation each retain an unknown reservation; cancellation returns HTTP 499. |
| Durable recovery and cross-user isolation | PASS | A fresh Uvicorn/FastAPI process reads the same persistent ledger after the test workload; owner A retains four unknown attempts and zero remaining, while owner B retains zero unknown attempts and its full $1 allowance. |
| Authenticated workspace evidence and artifacts | PASS | Research and paper paths resolve under the private workspace root; one-shot and long-form paper metadata and PDF files are readable through the owning API identity; cross-owner project reads remain denied. |

Cancellation testing exposed an API route defect: an explicitly cancelled
proposal task previously let `CancelledError` escape and produced no HTTP
response. `src/sigma/api.py` now returns the bounded `499` response already
used for client disconnect cancellation. Focused checks and the full
`env -u SIGMA_CLOUD_BOOTSTRAP_ADMIN_EMAIL ./sigma test` passed, including Ruff,
formatting, Pyright, frontend typecheck and production build. The requested
bare `./sigma test` also ran, but stopped at the pre-existing
`tests/tooling.py` UI cleanup assertion because the invoking shell exported
`SIGMA_CLOUD_BOOTSTRAP_ADMIN_EMAIL`; the environment-clean rerun passed that
same test. Test output uses a deterministic provider fixture, the PDF compiler
is stubbed, and identity is provided by the test-only shim rather than live
OIDC. Those are deliberate no-cost local test boundaries; no provider-quality,
browser, Google OAuth, or GCP claim is made. No paid provider calls or cloud
resources were used.

Deterministic API coverage exercises successful strategy and agentic proposals,
text conversion, one-shot and forced long-form paper generation, TeX/PDF archival
with the sponsored bearer, and checks their reconciled ledger rows. Provider 429
and a request-timeout fixture both retain unknown reservations; exhaustion blocks
dispatch and cross-user project access is denied. Existing local proposal,
agentic, paper and text conversion regression scenarios also passed.
Focused commands `uv run --locked --no-sync python tests/cloud_research_api.py`,
`tests/proposals.py`, `tests/agentic.py`, `tests/papers.py` and
`tests/text_views.py` passed. The first bare `./sigma test` run stopped at the
existing `tests/tooling.py` UI cleanup assertion while
`SIGMA_CLOUD_BOOTSTRAP_ADMIN_EMAIL` was set. After `./sigma setup`,
`env -u SIGMA_CLOUD_BOOTSTRAP_ADMIN_EMAIL ./sigma test` passed all scenarios,
Ruff, formatting, Pyright, frontend typecheck and production build. The
environment override matches the repository's existing UI test workaround.

Adversarial review of PR #107 found that the write-ahead estimate counted only
request-specific dynamic input. The reservation now uses the UTF-8 JSON size of
the full billable `instructions`, `input`, and structured-output `text` payload,
then adds maximum output tokens. A deterministic API regression leaves enough
budget for dynamic input alone but not for the complete request; the provider is
not dispatched. `env -u SIGMA_CLOUD_BOOTSTRAP_ADMIN_EMAIL ./sigma test` passed
again after the correction, including Ruff, formatting, Pyright, frontend
typecheck, and production build. No paid inference or cloud resources were used.

Follow-up: the Conclusion Markdown toggle had been missed by the earlier
Outcome-heading styling because it renders in `.outcome-conclusion-actions`.
That left it inheriting the generic workspace button padding/border, while its
SVG had no size rule and rendered at 0×0: Chrome showed a 42×50 empty outlined
box. The Conclusion action now uses the same 28×28 borderless control and 24×20
glyph as the Outcome heading. The focused Chrome regression asserts those
dimensions and transparent hover surface while continuing to verify rendered
Markdown/TeX and raw-source modes. Focused Chrome passed at 1440/375/320 px; the
full `env -u SIGMA_CLOUD_BOOTSTRAP_ADMIN_EMAIL ./sigma test` passed. No provider
calls or cloud changes.
## Project header About pill placement (2026-10-25)

The project header uses the labeled About pill in the left column beside Google
and ChatGPT. On narrow screens About and Google share a row, with Model beside
ChatGPT below; Thinking remains in the left column. The Home header orders its
About/Admin group left of the Google/ChatGPT connection pills. Removing mobile
offsets keeps Admin in its aligned second row instead of over the project list.
Real Chrome `browser_checks/header.py` passed at 1280, 1100, 700, 390 and 320 px,
including Home placement and no horizontal overflow. Screenshots:
`/tmp/sigma-a13-header-1280.png`, `/tmp/sigma-a13-header-390.png`,
`/tmp/sigma-home-header-admin-desktop.png` and
`/tmp/sigma-home-header-admin-mobile.png`. `env -u
SIGMA_CLOUD_BOOTSTRAP_ADMIN_EMAIL ./sigma test` passed all scenarios, Ruff,
formatting, Pyright, frontend typecheck and production build. No live provider
calls or cloud changes.
## T84 detailed command-specific CLI help (2026-10-25)

Extended the existing `argparse` command tree with a shared detailed-help format.
`sigma -h COMMAND`, `sigma COMMAND -h`, and `sigma COMMAND --help` use the same
parser help, including purpose, required arguments, options/defaults, examples,
relevant configuration notes, and common input/runtime errors. Root `sigma -h`
remains concise. This changes presentation only; command dispatch and services
are unchanged.

Regression coverage exercises both requested help forms, top-level help, and the
common example/notes structure for every registered command. Validation:
`env -u SIGMA_CLOUD_BOOTSTRAP_ADMIN_EMAIL uv run python tests/tooling.py` passed;
`env -u SIGMA_CLOUD_BOOTSTRAP_ADMIN_EMAIL ./sigma test` passed all scenarios,
Ruff, formatting, Pyright, frontend typecheck, and production build. The
environment variable is unset because this local checkout's launch-time Google
configuration otherwise makes an existing UI lifecycle mock fail before its
cleanup assertion.
## Blue Increment 7: saved reasoning and adversarial continuity (2026-10-25)

On cumulative PR #80, the Skeptic guidance now reviews the current claim against actually supplied prior steps rather than demanding a complete proof rewrite each cycle. Bounded prior-session extracts include saved reasoning arguments and reviews, with truncation and retraction signals. A Skeptic cannot mark an obligation addressed solely by a retracted, reasoning-truncated or absent older source. This checks source availability, not mathematical truth.

Offline scripted roles exercised real session dispatch/persistence across a two-cycle parity derivation, later same-strategy reuse, an unrelated-source rejection, retracted and truncated isolated copies, and paired graph computation-present/withheld controls. The graph path includes a real failed Docker Python attempt, a real completed three-vertex counterexample, a later same-strategy session and a researcher-approved fork carrying the exact negative witness. The failed run is an operational failure; the completed result refutes only the immediate-reverse-edge guard. Twenty-one captured role request bodies totaled 674,575 wire bytes; scripted response bodies totaled 34,358 bytes. No live provider calls or charges occurred; stored usage fields are fixture values. The corrected Skeptic guidance is 287 UTF-8 bytes longer than the static baseline, so no token or cost saving is claimed.

The withheld control remains an explicit research communication failure: authored Conclusion and Simple lead imply computational support even though the typed Outcome is Incomplete, current understanding is unverified and the report states zero executions. No fragile semantic filter or immutable-Conclusion rewrite was added. No UI or report code changed, so no new browser check was required. The first Increment 7 CI attempt exposed that its runner lacks the local Python Docker image; the test now explicitly skips only that real execution control when the image is absent, while export mode requires the image and refuses to fabricate results. Full audits, current-understanding exports, native TXT/HTML/TeX reports, exact request bodies, manifests, command transcripts, CI failure excerpt, no-sandbox control, and MET/UNMET/UNVERIFIED assessment are in [Increment 7 research continuity](evaluations/increment_7/RESEARCH_CONTINUITY.md). Autonomous reasoning quality and actual cost benefit remain unverified pending a separately authorized blind provider gate.
## Blue Increment 6: main release audit and evidence anchor (2026-10-24/25)

Verified merged main `4e25bd3fcb4a80a6b0f204f6726ec57c289d9f2c` after PR #77: post-merge GitHub Actions run 40159404783 succeeded, local `env -u SIGMA_CLOUD_BOOTSTRAP_ADMIN_EMAIL ./sigma test` passed, and focused continuation, feedback, session and settings scripts passed. A second full suite passed after a one-line candidate fix `fd87685` for Current Understanding's exact-artifact anchor. Main then advanced to `afebf33`; its CI run 40163068467 succeeded, and the merged candidate `06cb8c4` passed another full suite and Chrome run. No live provider calls or new research sessions occurred.

Real Chrome 156 on isolated copies of the saved subset and graph projects checked Home/open, project preferences, Simple and Advanced Outcomes, historical Conclusions, approved and unapproved evidence, execution JSON against API, Markdown rendering and 1440/390/320 widths. Twelve viewport checks had no overflow or page errors; all copied session objects were unchanged after preference inspection. Main's “Inspect finding” opened only the owning session; the candidate fix focuses the cited artifact. The fix awaits coordinator review/merge. Full actual `.txt` command transcripts, screenshots, machine observations, new preference-state Project Audit JSON, native reports and the explicit research-quality boundaries are in [Increment 6 release audit](evaluations/increment_6/RELEASE_AUDIT.md). The missing Increment 5 `.log` files were not reconstructed. A frozen blind gate is proposed, not executed; it requires explicit human provider/model/budget authorization.
## PR #76 integration with main (2026-10-24)

Merged `origin/main` at `81384dd` into `green/outcome-hierarchy` without
rebasing. Preserved Blue's read-only Current Understanding section, typed
research-state API/service, evidence navigation, report epistemics and tests,
alongside the project-level Simple/Advanced Outcome preference and Research
settings. Preserved Red's Markdown icon color/visibility rules. Historical
sessions still expose an absent saved Conclusion as `null`; their saved summary
remains visible and is not reattributed as an agent-authored Conclusion.

Validation after reconciliation: `env -u SIGMA_CLOUD_BOOTSTRAP_ADMIN_EMAIL
./sigma test` passed all scenarios, Ruff, format, Pyright, frontend typecheck and
production build. Real Chrome 156 passed `browser_checks/outcome_hierarchy.py`
against fresh copies of the five-session Nonconsecutive Subset Sums project and
historical Maximum Regions project: Simple/Advanced presentation, Conclusion
distinction, preference save/reload/isolation, Reasoning Markdown, computational
source/output access, and desktop/mobile settings at 390px and 320px. No page
errors. Test copies were isolated under `/private/tmp/sigma-outcome-reconcile`;
original saved projects were read only. Provider calls: 0.
## Blue Increment 2: read-only current understanding (2026-10-24)

Implemented on `blue_session` under `messages/blue_out_2.md` plus the standing
export supplement `blue_out_3.md`. The permanent human instruction is recorded
in [Blue operating protocol](BLUE_OPERATING_PROTOCOL.md); after each reported
iteration Blue polls the clean branch every 30 seconds with fast-forward-only
synchronization. No live/provider work or self-merge is authorized.

Added a typed current-understanding service/API and one foldable section before
session history. It shows latest saved reviews by strategy, recorded changes and
resolutions, open/unreconciled work and qualified next questions. Current does
not mean semantically proven or project solved. Source controls expand and focus
the exact owning session/artifact; header controls were not expanded. Existing
Conclusion logic, T48, fork prefill and deterministic report content are unchanged.

Dispositions require exact scoped obligation IDs, a rationale and available
unambiguous evidence; missing/foreign/future sources do not resolve work. Step
sources additionally require completed same-session timestamped provenance.
Legacy narrative notices remain unreconciled rather than silently becoming
proof or a mandatory rerun. Old mistakes, failed branches and raw records remain
intact. Unmatched source IDs are counted as uncertainty. The standalone state
read never invokes worker recovery, provider dispatch or session-file writes.

The unaltered Maximum Regions archive actually contains ten structured
obligation reviews. Four map to identified declarations with usable evidence;
they are reported as resolved/unverified. Its final separate stale completion
note remains unreconciled and is not proposed as another required run.
Nonconsecutive preserves the guessed-rule counterexample, later explanation
repair and still-open recurrence/density work; all five sessions remain clearly
deterministic archived evidence, not new live research.

Actual exports were pushed immediately in commit `322cf55`, under
[Increment 2 exports](evaluations/increment_2/exports/README.md): three complete
Project Audits and actual text/HTML/TeX reports. Final browser audit downloads
and actual current-state API responses are also retained. Audit content matches
the baseline; original source bytes stayed unchanged. No native Markdown report
export exists, so none was fabricated or relabeled. Markdown-valued Conclusions
remain inside complete JSON exports.

Actual validation: focused state scenarios, standalone Pyright/typecheck, and
`env -u SIGMA_CLOUD_BOOTSTRAP_ADMIN_EMAIL ./sigma test` passed all scenarios,
Ruff, format, Pyright, frontend typecheck and production build. Real Chrome
156.0.8078.47 exercised both continuity projects and the session-free stock copy,
exact source navigation, stable reload/IDs, actual audit downloads and 1440px,
390px and 320px document fit. No page errors, inference requests or source-byte
changes. [Evidence and complete logs](evaluations/increment_2/README.md) distinguish
original provider archives, deterministic history and synthetic schema regressions.
Provider calls/charges: 0/$0. Live research, agent uptake, independent correctness
and AI paper quality remain N/O. Next product work waits for the coordinator's
next numbered assignment after the review response.
## Blue Increment 1: confidence and argument-state integrity (2026-10-24)

Implemented on `blue_session` under `messages/blue_out_1.md`; initiative record:
[Researcher-centered SIGMA](RESEARCHER_CENTERED_SIGMA.md). Shared typed Python
presentation now supplies faithful verification labels to Outcome, UI source and
rendered modes, Status, Metrics, detailed review, new Conclusions and deterministic
text/HTML/TeX reports. `incomplete` is never mapped to convincing; legacy `verified`
is explicitly a report, not independent checking by SIGMA. Unknown/missing values
remain unknown/not recorded. Positive structured candidates require the recorded
agent-reviewed `convincing_unverified` state. Raw machine codes and saved text stay
intact; reports distinguish the saved code from the current presentation and do
not trust stale cached metric labels.

Historical Maximum Regions retains its original unstructured argument and is
shown as mixed/unassessed with saved narrative available, rather than saying no
substantive argument was captured. No proof steps or historical answer were
fabricated. A stored Conclusion remains intact; its current verification label
is shown alongside it. No T48 logic, obligation reconciliation or broader UX
redesign is included.

Actual validation: focused status/archive and report regressions passed, standalone
frontend typecheck and Pyright passed, and `env -u
SIGMA_CLOUD_BOOTSTRAP_ADMIN_EMAIL ./sigma test` passed all scenarios, lint,
formatting, Pyright, typecheck and production build. Real Chrome 156.0.8078.47
checked original historical Maximum Regions, explicit verification-declaration
variants and all five deterministic Nonconsecutive sessions at 1440px and 390px,
including Conclusion/Outcome source and rendered modes, details and Metrics.
No overflow, JavaScript errors or inference requests; original source and copied
archive record hashes remained unchanged. Durable screenshots, observation ledger,
reproduction and test outputs: [Increment 1 evidence](evaluations/INCREMENT_1/README.md).
No paid/live provider calls, fresh sandbox experiment or independent checker ran.
Live research and AI-authored paper quality remain unverified. Waiting for the
coordinator's next numbered outgoing message after review.
## T46 Home and Project About dialog (2026-10-24)

Added one shared About action and modal dialog to both Home and Project headers.
The copper-outlined `?` action has the same accessible name and tooltip on each
page. The dialog uses the established project-settings header/body styling, puts
Close immediately after its heading, and uses native modal semantics. Escape,
Close, and backdrop dismissal return focus to the trigger; opening About makes no
API or model request and does not change the Home tab or Project route. The
mobile Home header now lays out its existing Google and connection controls with
the About action without overlap. On narrow Project pages, the About hit area is
44×44px and shares the top header-controls row with Difficulty; a 30px copper
pill remains visible. Copy follows the approved four-part message
and states the limits of model-generated reasoning without claiming independent
proof verification.

Verification on 2026-10-24: `env -u SIGMA_CLOUD_BOOTSTRAP_ADMIN_EMAIL ./sigma
test` passed all scenarios, Ruff, formatting, Pyright, frontend typecheck and
production build. `uv run --with playwright python browser_checks/about.py`
passed in real Chrome at desktop (1440px) and narrow mobile (390px) widths from
both Home and Project, including native modal semantics, tooltip/accessibility,
focus restoration, unchanged navigation/tab state, no API requests on open, and
viewport fit. Visual screenshots are `/tmp/sigma-t46-about-home-desktop.png`,
`/tmp/sigma-t46-about-home-mobile.png`,
`/tmp/sigma-t46-about-project-desktop.png`, and
`/tmp/sigma-t46-about-project-mobile.png`; the mobile Project check also verifies
the hit area and opens via its outer edge. The header arrangement is captured in
`/tmp/sigma-t46-about-project-header-mobile.png`. The browser check used the local
deterministic provider fixture; no live provider calls were made.
## Outcome presentation and Project Settings (2026-10-24)

Added project-scoped `show_advanced_outcome_details`, defaulting off. Simple mode
shows the saved conclusion or an explicitly labeled historical summary, outcome
status, verification, supporting artifacts, and qualifications without Outcome
accordions. Advanced mode preserves the same primary finding in the expanded
Conclusion section and keeps reasoning, evidence/obligations, metrics, and other
records in the existing collapsible sections. Reasoning / proof has its own
Markdown render toggle that preserves the complete saved reasoning content. Historical
session projection no longer inserts a placeholder Conclusion; it preserves the
record's saved summary.

Project Settings now has a Preferences tab with “Show advanced Outcome details”.
The Research tab's Model and Thinking level controls share a two-column desktop
layout and stack on narrow screens; the model label is “Model”. Existing control
IDs and save semantics are retained. `./sigma test` and focused Project,
research-session, text-view, and strategy regressions passed. Real Chrome checks
passed for the five saved Nonconsecutive Subset Sums sessions and historical
Maximum Regions session at desktop and 390px/320px widths, including preference
default, save/reload and project isolation, advanced section order, Reasoning / proof Markdown rendering, execution
source/output access, and Project Settings control alignment. Screenshots:
`/tmp/sigma-outcome-advanced-390.png`,
`/tmp/sigma-outcome-advanced-320.png`,
`/tmp/sigma-settings-model-390.png`, and
`/tmp/sigma-settings-model-320.png`.


ontext, lazy, Suspense, useCallback, useContext, useEffect, useLayoutEffect, useMemo, useRef, useState, type FormEvent, type MouseEvent, type PointerEvent as ReactPointerEvent, type Ref, type ReactNode } from 'react';
import { createPortal } from 'react-dom';
import { createRoot } from 'react-dom/client';
import './style.css';
import './workspace.css';
import './project-entry.css';
import './strategies.css';
import './project-settings.css';
import './recents.css';
import './copper-controls.css';
import './text-views.css';
import { AIProvider, ConnectionStatus, ManageUsage, PlanWelcome, beginProviderRequest, watchResearchProviderActivity, useAI } from './ai-connection';
import { installRequestErrorToasts, reportRequestFailure, RequestErrorToasts } from './request-toast';
const RenderedMarkdown = lazy(() => import('./RenderedMarkdown'));

// Prospective navigation rail; keep implementation available for later activation.
const ENABLE_WORKSPACE_SIDEBAR = false;
const SHOW_PROJECT_DETAILS_AND_HISTORY = false;
const MAX_STRATEGY_APPROACH = 50000;

type Stage = 'draft' | 'ready' | 'exploring' | 'hold';
const stageLabels: Record<Stage, string> = { draft: 'Draft', ready: 'Ready to explore', exploring: 'Exploring', hold: 'On hold' };
type ResearchMode = 'biology' | 'chemistry' | 'computer_science' | 'economics' | 'engineering' | 'law' | 'mathematical' | 'military' | 'philosophy' | 'physics' | 'religion' | 'default';
type ProjectDifficulty = 'easy' | 'medium' | 'hard';
const difficultyLabels: Record<ProjectDifficulty, string> = { easy: 'Easy', medium: 'Medium', hard: 'Hard' };
const difficultyLabel = (value: ProjectDifficulty | null): string => value ? difficultyLabels[value] : 'Not set';
const difficultyDescription = (value: ProjectDifficulty | null): string => value ? `${difficultyLabels[value]} difficulty` : 'Difficulty not set';
const researchTypes: { value: ResearchMode; label: string }[] = [
  { value: 'biology', label: 'Biology' },
  { value: 'chemistry', label: 'Chemistry' },
  { value: 'computer_science', label: 'Computer Science' },
  { value: 'economics', label: 'Economics' },
  { value: 'engineering', label: 'Engineering' },
  { value: 'law', label: 'Law' },
  { value: 'mathematical', label: 'Mathematics' },
  { value: 'military', label: 'Military' },
  { value: 'philosophy', label: 'Philosophy' },
  { value: 'physics', label: 'Physics' },
  { value: 'religion', label: 'Religion' },
  { value: 'default', label: 'Other' },
];
const researchTypeLabels = Object.fromEntries(researchTypes.map(item => [item.value, item.label])) as Record<ResearchMode, string>;
const researchTypeLabel = (value: string | null | undefined) => value && value in researchTypeLabels ? researchTypeLabels[value as ResearchMode] : 'Unavailable';
type Strategy = {
  id: string;
  title: string;
  approach: string;
  stage: Stage;
  summary: string;
  provenance: { provider: string; model: string; reasoning_effort?: string | null } | null;
  author_kind: 'human';
  enabled: boolean;
  created_at: string;
  removed_at?: string | null;
};
type ProjectView = {
  path: string;
  project: {
    id: string;
    title: string;
    problem: string;
    schema_version: number;
    ai_model: string;
    reasoning_effort: string;
    difficulty: ProjectDifficulty | null;
    investigation_type: ResearchMode;
    events: { sequence: number; kind: string; timestamp: string; strategy_id?: string | null;
      project_change?: { previous: Settings; current: Settings } | null;
      order?: string[] | null; stage_change?: { previous: Stage; stage: Stage } | null;
      change?: { previous_title: string; previous_approach: string; title: string; approach: string } | null }[];
    strategies: Strategy[];
    active_order: string[];
  };
};

type ResearchArtifact = { id: string; session_id?: string; strategy_id?: string; strategy_cycle?: number; sequence: number; claim_or_question: string; method: string; assumptions: string[]; evidence_status: string; skeptic_response: string; objections: string[]; open_obligations: string[]; coordinator_decision: string; next_question: string; note: string; investigator_output: Record<string, unknown>; skeptic_output: Record<string, unknown> };
type ResearchEvent = { sequence: number; timestamp: string; kind: string; role?: string | null; message: string };
type ContextManifest = { policy_version?: string; byte_limit?: number; assembled_context_bytes?: number; selected_count?: number; omitted_count?: number; note?: string; obligation_disposition_counts?: Record<string, number>; omitted_obligations?: { count: number; obligation_ids: string[]; reason: string }; omitted_peer_evidence?: { count: number; artifact_ids: string[]; reason: string }; omitted_project_strategies?: { count: number; strategy_ids: string[]; reason: string }; sources?: { source_ids?: string[]; category?: string; reason?: string; representation?: string; status?: string }[]; omitted_prior_session_findings?: { count: number; source_ids: string[]; reason: string }; omitted_prior_failures?: { count: number; attempt_ids: string[]; reason: string } };
type ResearchStep = { id: string; strategy_id?: string | null; cycle: number; role: string; status: string; started_at: string; finished_at?: string; call_number: number; failure_kind?: string | null; provider_http_status?: number | null; interruption_reason?: string | null; context_artifact_ids?: string[]; prior_session_artifact_ids?: string[]; peer_strategy_artifact_ids?: string[]; peer_handoff_artifact_ids?: string[]; peer_handoff_ids?: string[]; human_intervention_ids?: string[]; context_manifest?: ContextManifest; provider_input_audit?: { kind: string; status: string; headers_included: boolean; request_body: Record<string, unknown> }; potential_truncation_fields?: string[]; token_usage_status?: string; output?: Record<string, unknown> };
type InterventionDelivery = { strategy_id: string; role: 'investigator' | 'skeptic'; status: string; target_cycle?: number | 'next_eligible'; acknowledged_at?: string; uptake?: string; rationale?: string; attempts: { step_id: string; cycle?: number; status: string; delivered_at: string; acknowledged_at?: string; uptake?: string; rationale?: string }[] };
type ResearchIntervention = { id: string; kind: 'objection' | 'evidence' | 'priority'; text: string; status: string; submitted_at: string; target_strategy_ids: string[]; target_roles: ('investigator' | 'skeptic')[]; rejection_reason?: string; superseded_by?: string; deliveries: InterventionDelivery[] };
type PriorSessionFinding = { id: string; sequence: number; claim_or_question: string; method: string; assumptions?: string[]; evidence_status: string; objections: string[]; open_obligations: string[]; coordinator_decision: string; next_question: string; session_id: string; session_number: number; strategy_id: string; strategy_title: string; obligation_reviews?: { obligation_id: string; status: string; basis_artifact_ids: string[]; basis_step_ids: string[]; rationale: string; epistemic_status: string }[] };
type ResearchStrategyRun = { strategy_id: string; strategy_title: string; status: string; current_action: string; current_question: string; cycle: number; calls_used: number; artifacts: string[]; reason?: string | null };
type PortfolioStrategyAction = { strategy_id: string; strategy_title: string; action: string; rationale: string; basis_artifact_ids: string[]; next_question: string };
type PortfolioCombination = { strategy_ids: string[]; basis_artifact_ids: string[]; rationales: string[]; status: string };
type PortfolioRelation = { source_strategy_id: string; source_artifact_id: string; target_strategy_id: string; target_artifact_id: string; relation: string; rationale: string };
type PortfolioDecision = { status?: string; strategy_actions?: PortfolioStrategyAction[]; combination_candidates?: PortfolioCombination[]; conflict_candidates?: PortfolioRelation[]; overlap_warnings?: PortfolioRelation[]; limitations?: string[] };
type OutcomeMetric = { label: string; value: string; detail?: string };
type ResearchOutcomeMetrics = { operational: OutcomeMetric[]; research_quality: OutcomeMetric[]; sources: { session_id: string | null; step_ids: string[]; artifact_ids: string[]; execution_ids: string[]; strategy_ids: string[] } };
type OutcomeArgumentStep = { number: number; title: string; argument: string; epistemic_status: string; basis_artifact_ids: string[]; research_artifact_id?: string; review?: { disposition: string; rationale: string; objection?: string; basis_artifact_ids: string[] } };
type StrategyFinding = { strategy_id: string; strategy_title: string; status: string; execution_status?: string; failure_reason?: string; claim: string; research_artifact_id: string; research_artifact_ids?: string[]; reasoning_steps: OutcomeArgumentStep[]; skeptic_response: string; objections: string[]; open_obligations: string[] };
type ResearchOutcome = { assessment: 'pending' | 'positive' | 'mixed' | 'negative'; label: string; summary?: string; conclusion?: string; caveats?: string[]; basis_artifact_ids?: string[]; provisional: boolean; metrics?: ResearchOutcomeMetrics; solution_review?: { status: string; claim?: string; claim_scope?: 'conditional' | 'unconditional' | 'disputed'; argument_summary?: string; skeptic_response?: string; skeptic_objections?: string[]; open_obligations?: string[]; argument_steps?: OutcomeArgumentStep[]; strategy_findings?: StrategyFinding[]; assumptions?: string[]; proof_obligations?: string[]; verification_status?: string; unresolved_objections?: string[]; resolved_objections?: string[]; basis_artifact_ids?: string[] } | null };
type StrategyAssessment = { strategy_id: string | null; strategy_title: string; assessment: 'contributed_to_solution' | 'productive' | 'unproductive' | 'not_used' | 'disabled' | 'unknown'; rationale: string; basis_artifact_ids: string[] };
type ResearchSession = { id: string; project_id?: string; problem?: string; session_number: number; strategy_id: string; strategy_title: string; strategy_text?: string; strategy_ids?: string[]; strategy_snapshot?: Record<string, unknown>; strategy_runs?: ResearchStrategyRun[]; portfolio_decision?: PortfolioDecision | null; peer_handoffs_prompted?: unknown[]; interventions?: ResearchIntervention[]; status: 'queued' | 'running' | 'paused' | 'stopped' | 'completed' | 'ended' | 'failed'; model: string; reasoning_effort: string; mode: string; calls_used: number; call_limit: number; cycle: number; cycle_limit?: number; current_question: string; current_action: string; message: string; artifacts: ResearchArtifact[]; prior_session_findings?: PriorSessionFinding[]; strategy_assessments?: StrategyAssessment[]; steps: ResearchStep[]; events: ResearchEvent[]; created_at: string; updated_at: string; started_at?: string; elapsed_seconds?: number; output_token_limit?: number; tokens_used?: number | null; token_usage_status?: string; estimated_cost_usd?: number | null; cost_status?: string; outcome: ResearchOutcome };
type ResearchLimits = { research_rounds: number; model_calls: number; session_duration_minutes: number; output_tokens_per_call: number; maximum_estimated_cost_usd: number | null };
type DurationUnit = 'minutes' | 'hours' | 'days';
type ResearchLimitsDraft = { research_rounds: string; model_calls: string; session_duration_value: string; session_duration_unit: DurationUnit; output_tokens_per_call: string; maximum_estimated_cost_usd: string };
function outcomeArtifactReferences(ids: string[] | undefined, session: ResearchSession): string {
  return ids?.map(id => `Artifact ${session.artifacts.find(artifact => artifact.id === id)?.sequence ?? '?'}`).join(', ') || 'No artifact references';
}

function researchOutcomeMarkdown(session: ResearchSession): string {
  const outcome = session.outcome;
  const lines = [outcome.summary || 'No outcome summary was recorded.'];
  if (outcome.basis_artifact_ids?.length) lines.push('', `**Outcome evidence:** ${outcomeArtifactReferences(outcome.basis_artifact_ids, session)}`);
  const review = outcome.solution_review;
  if (review) {
    lines.push('', '### Solution review', '', `**Investigated:** ${session.problem || 'Project objective unavailable in this historical record.'}`, '', `**Bounded strategy:** ${session.strategy_text || session.strategy_title || 'Strategy details unavailable.'}`, '', `**Solution claim:** ${review.claim || 'No solution claim recorded.'}`, '', `**Argument:** ${review.argument_summary || 'No argument summary recorded.'}`, '', `**Skeptic response:** ${review.skeptic_response || 'No substantive Skeptic response recorded.'}`, '', `**Assumptions:** ${review.assumptions?.join(' · ') || 'None recorded'}`, '', `**Proof obligations considered:** ${review.proof_obligations?.join(' · ') || 'None recorded'}`, '', `**Still open:** ${review.open_obligations?.join(' · ') || 'None recorded'}`, '', `**Evidence:** ${outcomeArtifactReferences(review.basis_artifact_ids, session)}`);
    if (review.argument_steps?.length) lines.push('', '### Reviewed reasoning', '', ...review.argument_steps.flatMap(step => [`#### ${step.number}. ${step.title}`, '', `**Kind:** ${step.epistemic_status}`, '', step.argument, '', `**Skeptic review:** ${step.review?.disposition || 'Not recorded'} — ${step.review?.rationale || 'No rationale recorded'}`, ...(step.review?.objection ? ['', `**Objection:** ${step.review.objection}`] : []), '', `**Sources:** ${outcomeArtifactReferences([...(step.basis_artifact_ids || []), ...(step.research_artifact_id ? [step.research_artifact_id] : [])], session)}`, '']));
    else lines.push('', '### Reviewed reasoning', '', 'No step-by-step argument was preserved in this session outcome.');
    if ((review.strategy_findings?.length ?? 0) > 0) lines.push('', '### Findings by strategy', '', ...review.strategy_findings!.flatMap(item => [`#### ${item.strategy_title} · ${item.status}`, '', item.claim, ...(item.execution_status ? ['', `**Execution status:** ${item.execution_status}`] : []), ...(item.failure_reason ? [`**Failure detail:** ${item.failure_reason}`] : []), '', ...item.reasoning_steps.flatMap(step => [`**${step.number}. ${step.title} (${step.epistemic_status}):** ${step.argument}`, `**Review:** ${step.review?.disposition || 'Not recorded'} — ${step.review?.rationale || item.skeptic_response}`, '']), ...(item.objections.length ? [`**Objections:** ${item.objections.join(' · ')}`] : []), ...(item.open_obligations.length ? [`**Open obligations:** ${item.open_obligations.join(' · ')}`] : []), `**Sources:** ${outcomeArtifactReferences(item.research_artifact_ids?.length ? item.research_artifact_ids : (item.research_artifact_id ? [item.research_artifact_id] : []), session)}`, '']));
    if (review.unresolved_objections?.length) lines.push('', '### Unresolved objections', '', ...review.unresolved_objections.map(item => `- ${item}`));
    if (review.resolved_objections?.length) lines.push('', '### Objections addressed', '', ...review.resolved_objections.map(item => `- ${item}`));
    if (review.resolved_objections?.length) lines.push('', `**Resolved review notes:** ${review.resolved_objections.join(' · ')}`);
    if (review.unresolved_objections?.length) lines.push('', `**Unresolved objections:** ${review.unresolved_objections.join(' · ')}`);
    if (review.verification_status && review.verification_status !== 'unknown') lines.push('', `**Verification:** ${review.verification_status === 'verified' ? 'Verified' : 'Convincing but unverified'}`);
  }
  if (outcome.caveats?.length) lines.push('', '### Caveats', '', ...outcome.caveats.map(caveat => `- ${caveat}`));
  return lines.join('\n');
}

function researchConclusionMarkdown(session: ResearchSession): string {
  return session.outcome.conclusion || '### Historical session\n\nNo Conclusion was saved for this session. Its existing outcome summary and detailed evidence remain available below.';
}

function researchArtifactMarkdown(artifact: ResearchArtifact): string {
  const lines = [
    `# Cycle ${artifact.sequence}: ${artifact.claim_or_question}`,
    '',
    `**Evidence status:** ${artifact.evidence_status}`,
    '',
    '## Method',
    '',
    artifact.method,
    '',
    '## Assumptions',
    '',
    ...(artifact.assumptions.length ? artifact.assumptions.map(item => `- ${item}`) : ['None stated']),
    '',
    '## Skeptic response',
    '',
    artifact.skeptic_response,
    '',
    '## Objections',
    '',
    ...(artifact.objections.length ? artifact.objections.map(item => `- ${item}`) : ['No concrete objection recorded']),
    '',
    '## Open obligations',
    '',
    ...(artifact.open_obligations.length ? artifact.open_obligations.map(item => `- ${item}`) : ['None recorded']),
    '',
    '## Coordinator decision',
    '',
    artifact.coordinator_decision,
    '',
    '## Next question',
    '',
    artifact.next_question || 'No further question; the session ended.',
    '',
    '## Full validated role outputs',
    '',
    '### Investigator',
    '',
    ...Object.entries(artifact.investigator_output).map(([key, value]) => `- **${key.replaceAll('_', ' ')}:** ${Array.isArray(value) ? value.join(' · ') : String(value)}`),
    '',
    '### Skeptic',
    '',
    ...Object.entries(artifact.skeptic_output).map(([key, value]) => `- **${key.replaceAll('_', ' ')}:** ${Array.isArray(value) ? value.join(' · ') : String(value)}`),
    '',
    `**Note:** ${artifact.note}`,
  ];
  return lines.join('\n');
}
const MAX_SESSION_DURATION_MINUTES = 7 * 24 * 60;
const durationUnitMinutes: Record<DurationUnit, number> = { minutes: 1, hours: 60, days: 1440 };
const limitBounds = {
  research_rounds: [1, 5], model_calls: [2, 30], output_tokens_per_call: [256, 16384],
} as const;
function draftLimits(value: ResearchLimits): ResearchLimitsDraft {
  const unit: DurationUnit = value.session_duration_minutes >= 1440 && value.session_duration_minutes % 1440 === 0 ? 'days' : value.session_duration_minutes >= 60 && value.session_duration_minutes % 60 === 0 ? 'hours' : 'minutes';
  const duration = value.session_duration_minutes / durationUnitMinutes[unit];
  return { research_rounds: String(value.research_rounds), model_calls: String(value.model_calls), session_duration_value: String(duration), session_duration_unit: unit, output_tokens_per_call: String(value.output_tokens_per_call), maximum_estimated_cost_usd: value.maximum_estimated_cost_usd === null ? '' : String(value.maximum_estimated_cost_usd) };
}
function validateLimitDraft(draft: ResearchLimitsDraft): { value: ResearchLimits | null; errors: Partial<Record<keyof ResearchLimitsDraft, string>> } {
  const errors: Partial<Record<keyof ResearchLimitsDraft, string>> = {};
  const value = {} as ResearchLimits;
  for (const key of Object.keys(limitBounds) as Array<keyof typeof limitBounds>) {
    const input = draft[key];
    const [minimum, maximum] = limitBounds[key];
    if (!/^\d+$/.test(input)) { errors[key] = 'Enter a whole number.'; continue; }
    const number = Number(input);
    if (!Number.isSafeInteger(number) || number < minimum || number > maximum) {
      errors[key] = `Enter a whole number from ${minimum} to ${maximum}.`; continue;
    }
    value[key] = number;
  }
  if (!/^\d+$/.test(draft.session_duration_value)) {
    errors.session_duration_value = 'Enter a whole number.';
  } else {
    const enteredDuration = Number(draft.session_duration_value);
    const durationMinutes = enteredDuration * durationUnitMinutes[draft.session_duration_unit];
    if (!Number.isSafeInteger(enteredDuration) || !Number.isSafeInteger(durationMinutes) || durationMinutes < 1 || durationMinutes > MAX_SESSION_DURATION_MINUTES) {
      errors.session_duration_value = 'Enter a duration from 1 minute to 7 days.';
    } else value.session_duration_minutes = durationMinutes;
  }
  if (draft.maximum_estimated_cost_usd === '') value.maximum_estimated_cost_usd = null;
  else if (!/^(?:\d+(?:\.\d{1,2})?|\.\d{1,2})$/.test(draft.maximum_estimated_cost_usd)) {
    errors.maximum_estimated_cost_usd = 'Enter a USD amount from $0.01 to $100.00, or leave blank for unlimited.';
  } else {
    const cost = Number(draft.maximum_estimated_cost_usd);
    if (!Number.isFinite(cost) || cost < 0.01 || cost > 100) errors.maximum_estimated_cost_usd = 'Enter a USD amount from $0.01 to $100.00, or leave blank for unlimited.';
    else value.maximum_estimated_cost_usd = Math.round(cost * 100) / 100;
  }
  if (!errors.research_rounds && !errors.model_calls && value.model_calls < 2 * value.research_rounds) {
    errors.model_calls = 'Allow at least two model calls per round so each round can include Investigator and Skeptic.';
  }
  return { value: Object.keys(errors).length ? null : value, errors };
}

function displayStrategyTitle(strategy: Strategy | undefined): string {
  if (!strategy) return 'Strategy';
  if (typeof strategy.title === 'string' && strategy.title.trim()) return strategy.title;
  const firstLine = typeof strategy.approach === 'string' ? strategy.approach.split(/\r?\n/, 1)[0].trim() : '';
  return firstLine ? `${firstLine.slice(0, 72)}${firstLine.length > 72 ? '…' : ''}` : 'Untitled strategy';
}

type ProcessControls = { play: () => void; stop: () => void; playDisabled: boolean; stopDisabled: boolean; playLabel: string; confirming?: boolean; start?: () => void; cancel?: () => void; nextSessionNumber?: number };

function DisclosureChevron({ expanded }: { expanded: boolean }) {
  return <svg aria-hidden="true" className={`disclosure-chevron${expanded ? ' is-expanded' : ''}`} viewBox="0 0 12 12"><path d="m4 2 4 4-4 4"/></svg>;
}

function ContextManifestNotes({ manifest }: { manifest: ContextManifest }) {
  const notes = [
    manifest.omitted_peer_evidence?.count ? {
      key: 'peer',
      text: `${manifest.omitted_peer_evidence.count} peer artifacts omitted; source IDs: ${manifest.omitted_peer_evidence.artifact_ids.join(', ') || 'bounded pointer list unavailable'}. ${manifest.omitted_peer_evidence.reason}`,
    } : null,
    manifest.omitted_project_strategies?.count ? {
      key: 'strategies',
      text: `${manifest.omitted_project_strategies.count} project strategies omitted; source IDs: ${manifest.omitted_project_strategies.strategy_ids.join(', ') || 'bounded pointer list unavailable'}. ${manifest.omitted_project_strategies.reason}`,
    } : null,
    manifest.omitted_obligations?.count ? {
      key: 'obligations',
      text: `${manifest.omitted_obligations.count} lower-priority obligation details omitted; IDs: ${manifest.omitted_obligations.obligation_ids.join(', ') || 'bounded pointer list unavailable'}. ${manifest.omitted_obligations.reason}`,
    } : null,
  ].filter((item): item is { key: string; text: string } => item !== null);
  if (!notes.length) return null;
  return <ul className="context-omission-notes">{notes.map(item => <li key={item.key}>{item.text}</li>)}</ul>;
}

function ResearchSessionContents({ path, session, expanded, busy, onViewStrategy, onViewPriorSession, onForkFromFindings, onInterventionSaved }: {
  path: string;
  session: ResearchSession; expanded: boolean; busy: boolean;
  onViewStrategy: (id: string) => void;
  onViewPriorSession: (id: string) => void;
  onForkFromFindings: (session: ResearchSession) => void;
  onInterventionSaved: (sessionId: string) => Promise<void>;
}) {
  const [outcomeMarkdown, setOutcomeMarkdown] = useState(false);
  const [conclusionMarkdown, setConclusionMarkdown] = useState(false);
  const [artifactsMarkdown, setArtifactsMarkdown] = useState(false);
  const [activityExpanded, setActivityExpanded] = useState(session.status === 'queued' || session.status === 'running');
  const [interventionKind, setInterventionKind] = useState<ResearchIntervention['kind']>('priority');
  const [interventionText, setInterventionText] = useState('');
  const [interventionStrategy, setInterventionStrategy] = useState('*');
  const [targetAgentRole, setTargetAgentRole] = useState<'investigator' | 'skeptic'>('investigator');
  const [interventionBusy, setInterventionBusy] = useState(false);
  const [interventionError, setInterventionError] = useState('');
  useEffect(() => {
    setActivityExpanded(session.status === 'queued' || session.status === 'running');
  }, [session.status]);
  const lastActivity = session.events.at(-1);
  const lastStep = session.steps.at(-1);
  const review = session.outcome.solution_review;
  const hasEvidence = !!review || session.artifacts.length > 0;
  const metricSources = session.outcome.metrics?.sources;
  const artifactNumber = (id: string) => session.artifacts.find(artifact => artifact.id === id)?.sequence;
  const idList = (ids: string[] | undefined) => ids?.length ? ids.map(id => `Artifact ${artifactNumber(id) ?? '?'} · ${id}`).join(', ') : 'None recorded';
  const targetStrategies = session.strategy_runs ?? [{ strategy_id: session.strategy_id, strategy_title: session.strategy_title }];
  const supportsIntervention = !!session.strategy_runs?.length;
  const interventionCount = session.interventions ?? [];
  const interventionWindowOpen = ['queued', 'running', 'paused', 'stopped'].includes(session.status);
  const canIntervene = supportsIntervention && interventionWindowOpen
    && interventionCount.filter(item => item.status !== 'rejected').length < 24
    && interventionCount.length < 32;
  const interventionHelp = session.status === 'paused' || session.status === 'stopped'
    ? 'Applies after resume; no call starts now.'
    : 'Applies on a later call; no call starts now.';
  async function submitIntervention(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const agentRoles = [targetAgentRole];
    if (!interventionText.trim()) return;
    setInterventionBusy(true); setInterventionError('');
    try {
      await post<ResearchSession>(`research-sessions/${session.id}/interventions`, {
        path,
        kind: interventionKind,
        text: interventionText,
        strategy_ids: interventionStrategy === '*' ? targetStrategies.map(item => item.strategy_id) : [interventionStrategy],
        agent_roles: agentRoles,
      });
      setInterventionText('');
      await onInterventionSaved(session.id);
    } catch (cause) {
      setInterventionError(errorMessage(cause));
      reportRequestFailure(errorMessage(cause));
    } finally { setInterventionBusy(false); }
  }
  const outcomeFormatToggle = <button type="button" className="sigma-render-toggle" aria-label={outcomeMarkdown ? 'Show plain outcome text' : 'Render outcome as Markdown'} aria-pressed={outcomeMarkdown} data-tooltip={outcomeMarkdown ? 'Show plain outcome text' : 'Render outcome as Markdown'} title={outcomeMarkdown ? 'Show plain outcome text' : 'Render outcome as Markdown'} onClick={() => setOutcomeMarkdown(value => !value)}><svg aria-hidden="true" className="markdown-logo" viewBox="20 25 160 78" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M20 92V30h20l20 25 20-25h20v62H80V59L60 84 40 59v33H20Z" fill="currentColor"/><path d="M120 30v38h-18l28 28 28-28h-18V30h-20Z" fill="currentColor"/></svg></button>;
  const conclusionFormatToggle = <button type="button" className="sigma-render-toggle" aria-label={conclusionMarkdown ? 'Show Conclusion Markdown source' : 'Render Conclusion as Markdown'} aria-pressed={conclusionMarkdown} data-tooltip={conclusionMarkdown ? 'Show Conclusion Markdown source' : 'Render Conclusion as Markdown'} title={conclusionMarkdown ? 'Show Conclusion Markdown source' : 'Render Conclusion as Markdown'} onClick={() => setConclusionMarkdown(value => !value)}><svg aria-hidden="true" className="markdown-logo" viewBox="20 25 160 78" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M20 92V30h20l20 25 20-25h20v62H80V59L60 84 40 59v33H20Z" fill="currentColor"/><path d="M120 30v38h-18l28 28 28-28h-18V30h-20Z" fill="currentColor"/></svg></button>;
  const renderMetricGroup = (title: string, items: OutcomeMetric[] | undefined) => <div className="outcome-metric-group">
    <h5>{title}</h5>
    {items?.length ? <dl>{items.map((item, index) => <div className="outcome-label-value" key={`${item.label}:${index}`}><dt>{item.label}</dt><dd><span>{item.value}</span>{item.detail && <small>{item.detail}</small>}</dd></div>)}</dl> : <p className="outcome-unavailable">No {title.toLowerCase()} metrics are available for this session.</p>}
  </div>;
  return <div id={`session-content-${session.id}`} className="session-row-content" hidden={!expanded}>
    <section className={`session-outcome outcome-${session.outcome.assessment}`} aria-label="Research outcome">
      <div className="outcome-heading"><div className="outcome-heading-title"><h3>Outcome</h3>{outcomeFormatToggle}<span className={`outcome-label outcome-${session.outcome.assessment}`}>{session.outcome.label}{session.outcome.provisional ? ' · provisional' : ''}</span></div></div>
      <details className="outcome-subsection outcome-conclusion" open>
        <summary><DisclosureChevron expanded={false}/>Conclusion</summary>
        <div className="outcome-subsection-content outcome-conclusion-content">
          <div className="outcome-conclusion-actions">{conclusionFormatToggle}</div>
          {conclusionMarkdown
            ? <div className="outcome-markdown"><Suspense fallback={<p>{session.outcome.conclusion || 'No Conclusion was saved for this historical session.'}</p>}><RenderedMarkdown body={researchConclusionMarkdown(session)}/></Suspense></div>
            : <div className="outcome-conclusion-source">{researchConclusionMarkdown(session)}</div>}
        </div>
      </details>
      {outcomeMarkdown ? <div className="outcome-markdown"><Suspense fallback={<p>{session.outcome.summary || 'No outcome summary was recorded.'}</p>}><RenderedMarkdown body={researchOutcomeMarkdown(session)}/></Suspense></div> : <div className="outcome-general"><div className="outcome-summary-text"><p>{session.outcome.summary || 'No outcome summary was recorded.'}</p>{!!session.outcome.basis_artifact_ids?.length && <p><strong>Outcome evidence:</strong> {outcomeArtifactReferences(session.outcome.basis_artifact_ids, session)}</p>}</div>{review && <div className="solution-review"><h4>Reasoning / proof</h4><p><strong>Investigated:</strong> {session.problem || 'Project objective unavailable in this historical record.'}</p><p><strong>Bounded strategy:</strong> {session.strategy_text || session.strategy_title || 'Strategy details unavailable.'}</p><p><strong>Claim:</strong> {review.claim || 'No claim recorded.'}</p><p><strong>Skeptic response:</strong> {review.skeptic_response || 'No substantive Skeptic response recorded.'}</p>{!!review.skeptic_objections?.length && <p><strong>Skeptic objections:</strong> {review.skeptic_objections.join(' · ')}</p>}{review.argument_steps?.length ? <ol>{review.argument_steps.map(step => <li key={`${step.research_artifact_id ?? ''}:${step.number}`}><strong>{step.title}</strong> <span>({step.epistemic_status})</span><p>{step.argument}</p><p><strong>Skeptic review:</strong> {step.review?.disposition || 'Not recorded'} — {step.review?.rationale || 'No rationale recorded'}</p>{!!step.review?.objection && <p><strong>Objection:</strong> {step.review.objection}</p>}<p><strong>Sources:</strong> {outcomeArtifactReferences([...(step.basis_artifact_ids || []), ...(step.research_artifact_id ? [step.research_artifact_id] : [])], session)}</p></li>)}</ol> : <p>No step-by-step argument was preserved. See the saved research artifacts before relying on this claim.</p>}{(review.strategy_findings?.length ?? 0) > 0 && <div><h4>Findings by strategy</h4>{review.strategy_findings!.map(item => <section key={item.strategy_id}><h5>{item.strategy_title} · {item.status}</h5><p>{item.claim}</p>{!!item.execution_status && <p><strong>Execution status:</strong> {item.execution_status}</p>}{!!item.failure_reason && <p><strong>Failure detail:</strong> {item.failure_reason}</p>}{item.reasoning_steps.length ? <ol>{item.reasoning_steps.map(step => <li key={step.number}><strong>{step.title}</strong> ({step.epistemic_status})<p>{step.argument}</p><p><strong>Review:</strong> {step.review?.disposition || 'Not recorded'} — {step.review?.rationale || item.skeptic_response}</p>{!!step.review?.objection && <p><strong>Objection:</strong> {step.review.objection}</p>}</li>)}</ol> : <p>No structured reasoning steps were preserved for this finding.</p>}{!!item.objections.length && <p><strong>Objections:</strong> {item.objections.join(' · ')}</p>}{!!item.open_obligations.length && <p><strong>Open obligations:</strong> {item.open_obligations.join(' · ')}</p>}<p><strong>Sources:</strong> {outcomeArtifactReferences(item.research_artifact_ids?.length ? item.research_artifact_ids : (item.research_artifact_id ? [item.research_artifact_id] : []), session)}</p></section>)}</div>}<p><strong>Assumptions:</strong> {review.assumptions?.join(' · ') || 'None recorded'}</p><p><strong>Proof obligations considered:</strong> {review.proof_obligations?.join(' · ') || 'None recorded'}</p><p><strong>Still open:</strong> {review.open_obligations?.join(' · ') || 'None recorded'}</p>{!!review.unresolved_objections?.length && <p><strong>Unresolved objections:</strong> {review.unresolved_objections.join(' · ')}</p>}{!!review.resolved_objections?.length && <p><strong>Objections addressed:</strong> {review.resolved_objections.join(' · ')}</p>}</div>}{!!session.outcome.caveats?.length && <div className="outcome-caveats"><strong>Caveats:</strong><ul>{session.outcome.caveats.map((caveat, index) => <li key={index}>{caveat}</li>)}</ul></div>}</div>}

      {(canIntervene || !!session.interventions?.length || (interventionWindowOpen && !supportsIntervention)) && <details className="human-interventions outcome-subsection" aria-label="Human research feedback" open>
        <summary><DisclosureChevron expanded={false}/>Human feedback</summary>
        <div className="human-interventions-content">
        {!supportsIntervention && <p className="human-intervention-note">Feedback is unavailable for this legacy session because it has no strategy-bound execution steps.</p>}
        {supportsIntervention && interventionWindowOpen && interventionCount.filter(item => item.status !== 'rejected').length >= 24 && <p className="human-intervention-note">This session reached its 24-feedback limit.</p>}
        {canIntervene && <form className="human-intervention-form" onSubmit={submitIntervention}>
          <fieldset className="human-intervention-type" aria-label="Feedback type"><label><input type="radio" name={`feedback-type-${session.id}`} value="priority" checked={interventionKind === 'priority'} onChange={() => setInterventionKind('priority')}/> Priority</label><label><input type="radio" name={`feedback-type-${session.id}`} value="objection" checked={interventionKind === 'objection'} onChange={() => setInterventionKind('objection')}/> Objection</label><label><input type="radio" name={`feedback-type-${session.id}`} value="evidence" checked={interventionKind === 'evidence'} onChange={() => setInterventionKind('evidence')}/> New Evidence</label></fieldset>
          <fieldset className="human-intervention-target" aria-label="Feedback recipient"><label><input type="radio" name={`feedback-target-${session.id}`} value="investigator" checked={targetAgentRole === 'investigator'} onChange={() => setTargetAgentRole('investigator')}/> For investigator</label><label><input type="radio" name={`feedback-target-${session.id}`} value="skeptic" checked={targetAgentRole === 'skeptic'} onChange={() => setTargetAgentRole('skeptic')}/> For skeptic</label></fieldset>
          <label className="human-intervention-strategy"><span className="sr-only">Strategy</span><select aria-label="Strategy" value={interventionStrategy} onChange={event => setInterventionStrategy(event.target.value)}><option value="*">All strategies</option>{targetStrategies.map(item => <option key={item.strategy_id} value={item.strategy_id}>{item.strategy_title}</option>)}</select></label>
          <label className="human-intervention-text">Feedback<textarea value={interventionText} maxLength={1200} rows={3} onChange={event => setInterventionText(event.target.value)} placeholder="Add a research instruction or evidence note."/></label>
          <div className="human-intervention-submit"><button type="submit" className="text-view-link" aria-describedby={`human-feedback-help-${session.id}`} disabled={interventionBusy || busy || !interventionText.trim()}>{interventionBusy ? 'Adding…' : 'Add'}</button><small id={`human-feedback-help-${session.id}`}>{interventionText.length}/1,200 · {interventionHelp}</small></div>
          {interventionError && <p className="error" role="alert">{interventionError}</p>}
        </form>}
        {!!session.interventions?.length && <ol className="human-intervention-history">{session.interventions.slice(-8).reverse().map(item => <li key={item.id}>
          <div><strong>{item.kind.replaceAll('_', ' ')}</strong>{item.status !== 'queued' && <span>{item.status.replaceAll('_', ' ')}</span>}</div>
          <p>{item.text}</p>
          {item.rejection_reason && <small>{item.rejection_reason}</small>}
          {!!item.deliveries.length && <ul>{item.deliveries.map((delivery, index) => <li key={`${delivery.strategy_id}:${delivery.role}:${index}`}><span>{targetStrategies.find(strategy => strategy.strategy_id === delivery.strategy_id)?.strategy_title ?? 'Strategy'} · {delivery.role}{delivery.target_cycle ? ` · cycle ${delivery.target_cycle === 'next_eligible' ? 'pending' : delivery.target_cycle}` : ''}</span>{delivery.status !== 'queued' && <span>{delivery.status}{delivery.uptake ? ` · ${delivery.uptake}` : ''}</span>}{delivery.rationale && <small>{delivery.rationale}</small>}{delivery.attempts.length > 1 && <small>{delivery.attempts.length} delivery attempts; interrupted attempts remain in the audit.</small>}</li>)}</ul>}
        </li>)}</ol>}
        </div>
      </details>}

      <div className="outcome-subsections">
        <details className="outcome-subsection">
          <summary><DisclosureChevron expanded={false}/>Status</summary>
          <div className="outcome-subsection-content">
            <div className="outcome-label-value"><dt>Session lifecycle</dt><dd>{session.status}</dd></div><div className="outcome-label-value"><dt>Token usage</dt><dd>{session.tokens_used == null ? `Unavailable (${session.token_usage_status ?? 'not reported'})` : `${session.tokens_used.toLocaleString()} tokens · ${session.token_usage_status ?? 'reported'}`}</dd></div>
            <div className="outcome-label-value"><dt>Research result</dt><dd>{session.outcome.label}{session.outcome.provisional ? ' · provisional' : ''}</dd></div>
            <div className="outcome-label-value"><dt>Verification</dt><dd>{review?.verification_status && review.verification_status !== 'unknown' ? review.verification_status === 'verified' ? 'Verified (session record)' : 'Convincing but unverified' : 'Not independently verified'}</dd></div>
            <p className="outcome-integrity-note">A completed session or successful computation does not establish a mathematical proof.</p>
            {!!session.message && <p className="research-session-message">{session.message}</p>}
            {!!session.strategy_runs && session.strategy_runs.length > 1 && <section className="research-strategy-activity" aria-label="Strategy activity"><h4>Strategy activity</h4><ul>{session.strategy_runs.map(branch => <li key={branch.strategy_id} className={`strategy-run-${branch.status}`}><p><strong>{branch.strategy_title}</strong> · {branch.status} · {branch.current_action}</p><p>Cycle {branch.cycle} · {branch.calls_used} calls · {branch.artifacts.length} saved findings</p>{!!branch.current_question && <p><strong>Current question:</strong> {branch.current_question}</p>}{!!branch.reason && <p><strong>Coordinator rationale:</strong> {branch.reason}</p>}</li>)}</ul></section>}
            {!!session.steps.filter(step => ['failed', 'interrupted', 'running'].includes(step.status)).length && <section className="outcome-provider-attempts" aria-label="Incomplete provider attempts"><h4>Incomplete or failed attempts</h4><ul>{session.steps.filter(step => ['failed', 'interrupted', 'running'].includes(step.status)).map(step => <li key={step.id}><strong>{step.status} · {step.role}</strong><span>Cycle {step.cycle}, call {step.call_number}{step.provider_http_status ? ` · HTTP ${step.provider_http_status}` : ''}{step.failure_kind ? ` · ${step.failure_kind}` : ''}</span>{step.interruption_reason && <p>{step.interruption_reason}</p>}{step.status === 'interrupted' && <p>The provider may have completed or charged usage; SIGMA did not repeat this ambiguous attempt automatically.</p>}</li>)}</ul></section>}
            {lastStep && ['running', 'interrupted', 'failed'].includes(lastStep.status) && !session.steps.some(step => ['failed', 'interrupted', 'running'].includes(step.status)) && <section className="research-incomplete-step" aria-label="Current or incomplete step"><strong>{lastStep.status === 'running' ? 'In progress' : 'Incomplete step'} · {lastStep.role}</strong><p>Cycle {lastStep.cycle}, call {lastStep.call_number}. This attempt is not a completed research artifact.</p></section>}
            {!!session.current_question && <p><strong>Current focus:</strong> {session.current_question}</p>}
            <div className="research-session-actions"><a className="text-view-link" title={`View strategy: ${session.strategy_title}`} href={`#strategy-${session.strategy_id}`} onClick={event => { event.preventDefault(); onViewStrategy(session.strategy_id); }}>Go to strategy: {session.strategy_title}</a>{!!session.artifacts.length && <button type="button" className="text-view-link" onClick={() => onForkFromFindings(session)}>Fork strategy from findings</button>}</div>
          </div>
        </details>

        <details className="outcome-subsection">
          <summary><DisclosureChevron expanded={false}/>Strategy Assessments</summary>
          <div className="outcome-subsection-content">
            <p className="outcome-subsection-intro">Each assessment records a strategy’s contribution to the project objective in this session.</p>
            {session.strategy_assessments?.length ? <div className="outcome-assessment-list">{session.strategy_assessments.map((item, index) => {
              const label: Record<StrategyAssessment['assessment'], string> = { contributed_to_solution: 'Contributed to solution', productive: 'Productive', unproductive: 'Unproductive', not_used: 'Not used', disabled: 'Disabled', unknown: 'Unknown' };
              return <article className="outcome-assessment" key={item.strategy_id ?? index}><h4>{item.strategy_title}</h4><div className="outcome-label-value"><dt>Disposition</dt><dd>{label[item.assessment] ?? 'Unknown'}</dd></div><div className="outcome-label-value"><dt>Rationale</dt><dd>{item.rationale || 'No rationale recorded'}</dd></div><div className="outcome-label-value"><dt>Cited evidence</dt><dd>{idList(item.basis_artifact_ids)}</dd></div></article>;
            })}</div> : <p className="outcome-unavailable">No strategy assessments were recorded for this session.</p>}
            {session.portfolio_decision?.strategy_actions?.length ? <section className="coordinator-portfolio-review" aria-label="Coordinator portfolio recommendations"><h4>Coordinator recommendations</h4><p>Evidence-linked recommendations are model-reported and unverified. Saved strategies are never changed automatically.</p><ul>{session.portfolio_decision.strategy_actions.map(item => <li key={item.strategy_id}><p><strong>{item.strategy_title}:</strong> {item.action.replaceAll('_', ' ')}</p><p>{item.rationale}{item.basis_artifact_ids.length > 0 && <> · Evidence: {idList(item.basis_artifact_ids)}</>}</p>{!!item.next_question && <p><strong>Next question:</strong> {item.next_question}</p>}</li>)}</ul>
              {!!session.portfolio_decision.combination_candidates?.length && <div className="coordinator-combinations"><strong>Combination candidates for human review</strong><ul>{session.portfolio_decision.combination_candidates.map((item, index) => { const titles = item.strategy_ids.map(id => session.strategy_runs?.find(branch => branch.strategy_id === id)?.strategy_title ?? 'Strategy'); return <li key={`${item.strategy_ids.join(':')}-${index}`}><p>{titles.join(' + ')} · {idList(item.basis_artifact_ids)}</p>{item.rationales.map((rationale, rationaleIndex) => <p key={rationaleIndex}>{rationale}</p>)}</li>; })}</ul></div>}
              {!!session.portfolio_decision.conflict_candidates?.length && <div className="coordinator-conflicts"><strong>Cross-strategy contradictions to resolve</strong><ul>{session.portfolio_decision.conflict_candidates.map((item, index) => <li key={`${item.source_artifact_id}-${item.target_artifact_id}-${index}`}><p>{item.relation.replaceAll('_', ' ')} · {idList([item.source_artifact_id, item.target_artifact_id])}</p><p>{item.rationale}</p></li>)}</ul></div>}
              {!!session.portfolio_decision.overlap_warnings?.length && <div className="coordinator-overlaps"><strong>Potentially overlapping approaches</strong><ul>{session.portfolio_decision.overlap_warnings.map((item, index) => <li key={`${item.source_artifact_id}-${item.target_artifact_id}-${index}`}><p>{idList([item.source_artifact_id, item.target_artifact_id])} · {item.rationale}</p></li>)}</ul></div>}
              {!!session.portfolio_decision.limitations?.length && <p className="coordinator-review-limit">{session.portfolio_decision.limitations.join(' ')}</p>}
            </section> : null}
          </div>
        </details>

        <details className="outcome-subsection">
          <summary><DisclosureChevron expanded={false}/>Metrics</summary>
          <div className="outcome-subsection-content">
            {session.outcome.metrics ? <div className="outcome-metrics-groups">{renderMetricGroup('Operational', session.outcome.metrics.operational)}{renderMetricGroup('Research quality', session.outcome.metrics.research_quality)}</div> : <p className="outcome-unavailable">Metrics are not available for this historical session.</p>}
          </div>
        </details>

        <details className="outcome-subsection">
          <summary><DisclosureChevron expanded={false}/>Provenance</summary>
          <div className="outcome-subsection-content">
            <div className="outcome-provenance-group"><h4>Session and configuration</h4><div className="outcome-label-value"><dt>Session ID</dt><dd>{session.id}</dd></div>{session.project_id && <div className="outcome-label-value"><dt>Project ID</dt><dd>{session.project_id}</dd></div>}<div className="outcome-label-value"><dt>Selected strategy</dt><dd>{session.strategy_title || 'Strategy'} · {session.strategy_ids?.length ? session.strategy_ids.join(', ') : session.strategy_id || 'ID unavailable'}</dd></div>{session.strategy_snapshot && <div className="outcome-label-value"><dt>Strategy snapshot</dt><dd>{String(session.strategy_snapshot.title ?? session.strategy_title)}{typeof session.strategy_snapshot.approach === 'string' ? ` · ${session.strategy_snapshot.approach}` : ''}</dd></div>}<div className="outcome-label-value"><dt>Model and thinking</dt><dd>{session.model || 'Unavailable'} · {thinkingLabels[session.reasoning_effort] ?? session.reasoning_effort ?? 'Unavailable'} · configured at session level, not an independent provider receipt</dd></div><div className="outcome-label-value"><dt>Billing mode</dt><dd>{session.mode === 'api_key' ? 'API key billing' : session.mode === 'chatgpt' ? 'ChatGPT plan allowance; actual allowance consumption unavailable' : session.mode || 'Unavailable'}</dd></div><div className="outcome-label-value"><dt>Started / updated</dt><dd>{session.started_at ? dateLabel(session.started_at) : 'Start time unavailable'} · {session.updated_at ? dateLabel(session.updated_at) : 'Update time unavailable'}</dd></div></div>
            {metricSources && <div className="outcome-provenance-group"><h4>Metric source inventory</h4><p className="outcome-subsection-intro">These session-scoped IDs identify records used by the metrics projection; they are not a per-measurement source map.</p>{([['Steps', metricSources.step_ids], ['Artifacts', metricSources.artifact_ids], ['Computation executions', metricSources.execution_ids], ['Strategies', metricSources.strategy_ids]] as [string, string[]][]).map(([label, ids]) => <div className="outcome-label-value" key={label}><dt>{label}</dt><dd>{ids.length ? ids.join(', ') : 'None recorded'}</dd></div>)}</div>}
            {session.steps.length > 0 && <div className="outcome-provenance-group"><h4>Model call attempts</h4><ol className="outcome-provenance-list">{session.steps.map(step => <li key={step.id}><div className="outcome-label-value"><dt>{step.role} · {step.status}</dt><dd>Step {step.id} · Cycle {step.cycle} · Call {step.call_number}{step.strategy_id ? ` · Strategy ${step.strategy_id}` : ''}</dd></div><p>{step.started_at ? dateLabel(step.started_at) : 'Start time unavailable'}{step.finished_at ? ` · ${dateLabel(step.finished_at)}` : ' · no finish time recorded'}{step.provider_http_status ? ` · HTTP ${step.provider_http_status}` : ''}{step.failure_kind ? ` · ${step.failure_kind}` : ''}{step.interruption_reason ? ` · ${step.interruption_reason}` : ''}</p>{!!(step.context_artifact_ids?.length || step.prior_session_artifact_ids?.length || step.peer_strategy_artifact_ids?.length || step.peer_handoff_artifact_ids?.length) && <p><strong>Context artifacts:</strong> {idList([...(step.context_artifact_ids ?? []), ...(step.prior_session_artifact_ids ?? []), ...(step.peer_strategy_artifact_ids ?? []), ...(step.peer_handoff_artifact_ids ?? [])])}</p>}{!!step.peer_handoff_ids?.length && <p><strong>Peer handoffs:</strong> {step.peer_handoff_ids.join(', ')}</p>}{step.context_manifest && <details className="context-used-disclosure"><summary>Context used · {step.context_manifest.selected_count ?? step.context_manifest.sources?.filter(source => source.status === 'selected').length ?? 0} current artifacts selected · {step.context_manifest.omitted_count ?? 0} omitted</summary><p>{step.context_manifest.note ?? 'Deterministic extracts from saved records; originals remain in session history.'}</p>{typeof step.context_manifest.assembled_context_bytes === 'number' && <p>Serialized context: {step.context_manifest.assembled_context_bytes.toLocaleString()} bytes of {step.context_manifest.byte_limit?.toLocaleString() ?? 'bounded'} UTF-8 input</p>}{step.context_manifest.sources?.length ? <ul>{step.context_manifest.sources.slice(0, 32).map((source, index) => <li key={`${source.source_ids?.[0] ?? 'source'}-${index}`}><strong>{source.category?.replaceAll('_', ' ') ?? 'Source'} · {source.status ?? 'recorded'}:</strong> {source.source_ids?.join(', ') ?? 'ID unavailable'} — {source.reason ?? source.representation ?? 'See saved source'}</li>)}</ul> : <p>No source-level manifest was recorded for this historical step.</p>}{(step.context_manifest.sources?.length ?? 0) > 32 && <p>{(step.context_manifest.sources?.length ?? 0) - 32} additional manifest entries omitted from this view.</p>}{step.context_manifest.omitted_prior_session_findings?.count ? <p>{step.context_manifest.omitted_prior_session_findings.count} older session findings omitted; source IDs: {step.context_manifest.omitted_prior_session_findings.source_ids.join(', ') || 'bounded pointer list unavailable'}.</p> : null}{step.context_manifest.omitted_prior_failures?.count ? <p>{step.context_manifest.omitted_prior_failures.count} older operational failures omitted; attempt IDs: {step.context_manifest.omitted_prior_failures.attempt_ids.join(', ') || 'bounded pointer list unavailable'}.</p> : null}<ContextManifestNotes manifest={step.context_manifest}/></details>}{step.potential_truncation_fields?.length ? <p className="research-output-warning" role="status"><strong>Potentially truncated output:</strong> {step.potential_truncation_fields.join(', ')} reached a structured output field limit. Review the saved source text before relying on it.</p> : null}{step.provider_input_audit && <details className="context-used-disclosure"><summary>Exact provider input · {step.provider_input_audit.status}</summary><p>Saved request body before dispatch; authorization headers and credentials are excluded.</p><h5>Role instructions</h5><pre>{String(step.provider_input_audit.request_body.instructions ?? '')}</pre><h5>Submitted input</h5><pre>{JSON.stringify(step.provider_input_audit.request_body.input, null, 2)}</pre></details>}</li>)}</ol></div>}
            {session.artifacts.length > 0 && <div className="outcome-provenance-group"><h4>Saved artifact origins</h4><ul className="outcome-provenance-list">{session.artifacts.map(artifact => <li key={artifact.id}><div className="outcome-label-value"><dt>Artifact {artifact.sequence}</dt><dd>{artifact.id}</dd></div><p>{artifact.session_id ? `Session ${artifact.session_id}` : 'Source session unavailable'} · {artifact.strategy_id ? `Strategy ${artifact.strategy_id}` : 'Strategy unavailable'} · {typeof artifact.strategy_cycle === 'number' ? `Cycle ${artifact.strategy_cycle}` : 'Cycle unavailable'}</p></li>)}</ul></div>}
            {!!session.prior_session_findings?.length && <div className="outcome-provenance-group"><h4>Prior session sources</h4><ul className="outcome-provenance-list">{session.prior_session_findings.map(finding => <li key={`${finding.session_id}:${finding.id}`}><p><button type="button" className="text-view-link" onClick={() => onViewPriorSession(finding.session_id)}>Session #{finding.session_number} · {finding.strategy_title} · Artifact {finding.sequence}</button></p><p>{finding.id} · {finding.claim_or_question}</p><p><strong>Method:</strong> {finding.method}</p>{!!finding.assumptions?.length && <p><strong>Assumption/domain scope:</strong> {finding.assumptions.join(' · ')}</p>}<p><strong>Evidence status:</strong> {finding.evidence_status} · <strong>Coordinator:</strong> {finding.coordinator_decision}</p>{!!finding.objections.length && <p><strong>Objections:</strong> {finding.objections.join(' · ')}</p>}{!!finding.open_obligations.length && <p><strong>Open obligations:</strong> {finding.open_obligations.join(' · ')}</p>}{!!finding.obligation_reviews?.length && <ul>{finding.obligation_reviews.map(review => <li key={review.obligation_id}><strong>Prior obligation disposition ({review.status}, {review.epistemic_status}):</strong> {review.rationale} · Basis artifacts: {review.basis_artifact_ids.join(', ') || 'none recorded'}</li>)}</ul>}{!!finding.next_question && <p><strong>Next question:</strong> {finding.next_question}</p>}</li>)}</ul></div>}
            {!!session.peer_handoffs_prompted?.length && <div className="outcome-provenance-group"><h4>Peer handoffs prompted</h4><ul className="outcome-provenance-list">{session.peer_handoffs_prompted.map((handoff, index) => <li key={index}><pre>{JSON.stringify(handoff, null, 2)}</pre></li>)}</ul></div>}
            <div className="outcome-provenance-group"><h4>Session facts</h4><div className="outcome-label-value"><dt>Elapsed wall time</dt><dd>{typeof session.elapsed_seconds === 'number' ? formatDuration(session.elapsed_seconds) : 'Unavailable'}</dd></div><div className="outcome-label-value"><dt>Output limit</dt><dd>{typeof session.output_token_limit === 'number' ? `${session.output_token_limit} tokens per call` : 'Unavailable'}</dd></div><div className="outcome-label-value"><dt>Current action</dt><dd>{session.current_action || 'Unavailable'}</dd></div>{lastActivity && <div className="outcome-label-value"><dt>Last activity</dt><dd><time dateTime={lastActivity.timestamp}>{dateLabel(lastActivity.timestamp)}</time> · {lastActivity.message}</dd></div>}</div>
            {!!session.events.length && <section className="research-activity" aria-label="Recent session activity"><h4><button type="button" title={`${activityExpanded ? 'Collapse' : 'Expand'} recent activity`} aria-expanded={activityExpanded} aria-controls={`session-activity-${session.id}`} onClick={() => setActivityExpanded(value => !value)}><DisclosureChevron expanded={activityExpanded}/>Recent activity</button></h4><ol id={`session-activity-${session.id}`} hidden={!activityExpanded}>{session.events.slice(-8).map(event => <li key={event.sequence}><time dateTime={event.timestamp}>{dateLabel(event.timestamp)}</time><span>{event.message}</span></li>)}</ol></section>}
          </div>
        </details>

        {hasEvidence && <details className="outcome-subsection outcome-evidence-subsection">
          <summary><DisclosureChevron expanded={false}/>Citations, Evidence &amp; Obligations</summary>
          <div className="outcome-subsection-content">
            {review && !outcomeMarkdown && <div className="solution-review"><h4>Solution review</h4><p><strong>Solution claim:</strong> {review.claim || 'No solution claim recorded.'}</p><p><strong>Argument:</strong> {review.argument_summary || 'No argument summary recorded.'}</p><p><strong>Assumptions:</strong> {review.assumptions?.join(' · ') || 'None recorded'}</p><p><strong>Proof obligations:</strong> {review.proof_obligations?.join(' · ') || 'None recorded'}</p><p><strong>Evidence:</strong> {outcomeArtifactReferences(review.basis_artifact_ids, session)}</p>{!!review.resolved_objections?.length && <p><strong>Resolved review notes:</strong> {review.resolved_objections.join(' · ')}</p>}{!!review.unresolved_objections?.length && <p><strong>Unresolved objections:</strong> {review.unresolved_objections.join(' · ')}</p>}{review.verification_status && review.verification_status !== 'unknown' && <p><strong>Verification:</strong> {review.verification_status === 'verified' ? 'Verified (session record)' : 'Convincing but unverified'}</p>}</div>}
            {!!session.artifacts.length && <section className="research-artifacts" aria-label="Research artifacts"><div className="research-artifacts-heading"><h4>Research artifacts</h4><button type="button" className="sigma-render-toggle" aria-label={artifactsMarkdown ? 'Show plain research artifacts' : 'Render research artifacts as Markdown'} aria-pressed={artifactsMarkdown} data-tooltip={artifactsMarkdown ? 'Show plain research artifacts' : 'Render research artifacts as Markdown'} title={artifactsMarkdown ? 'Show plain research artifacts' : 'Render research artifacts as Markdown'} onClick={() => setArtifactsMarkdown(value => !value)}><svg aria-hidden="true" className="markdown-logo" viewBox="20 25 160 78" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M20 92V30h20l20 25 20-25h20v62H80V59L60 84 40 59v33H20Z" fill="currentColor"/><path d="M120 30v38h-18l28 28 28-28h-18V30h-20Z" fill="currentColor"/></svg></button></div><ol>{session.artifacts.map(artifact => {
              const sage = !!artifact.investigator_output.sage_execution;
              const executionField = sage ? 'sage_execution' : 'python_execution';
              const toolName = sage ? 'SageMath' : 'Python';
              const execution = artifact.investigator_output[executionField] && typeof artifact.investigator_output[executionField] === 'object' ? artifact.investigator_output[executionField] as Record<string, unknown> : null;
              const captured = execution && Array.isArray(execution.artifacts) ? execution.artifacts as Record<string, unknown>[] : [];
              const reused = artifact.investigator_output[executionField + '_reuse_reason'];
              return <li key={artifact.id}>{artifactsMarkdown ? <div className="research-artifact-content research-artifact-markdown"><Suspense fallback={<p>{artifact.method}</p>}><RenderedMarkdown body={researchArtifactMarkdown(artifact)}/></Suspense></div> : <details>
                <summary>Cycle {artifact.strategy_cycle ?? artifact.sequence} · {artifact.claim_or_question} <span>{artifact.evidence_status}</span></summary>
                <div className="research-artifact-content"><p><strong>Method:</strong> {artifact.method}</p><p><strong>Assumptions:</strong> {artifact.assumptions.join(' · ') || 'None stated'}</p><p><strong>Evidence status:</strong> {artifact.evidence_status}</p><p><strong>Skeptic response:</strong> {artifact.skeptic_response}</p><p><strong>Objections:</strong> {artifact.objections.join(' · ') || 'No concrete objection recorded'}</p><p><strong>Open obligations:</strong> {artifact.open_obligations.join(' · ') || 'None recorded'}</p>{Array.isArray(artifact.skeptic_output.obligation_reviews) && artifact.skeptic_output.obligation_reviews.length > 0 && <p><strong>Obligation dispositions:</strong> {(artifact.skeptic_output.obligation_reviews as Record<string, unknown>[]).map(review => `${String(review.status ?? 'unknown')} · ${String(review.rationale ?? '')} [${Array.isArray(review.basis_artifact_ids) ? review.basis_artifact_ids.join(', ') : 'no artifact source'}]`).join(' · ')}. Model-reported and unverified.</p>}<p><strong>Coordinator decision:</strong> {artifact.coordinator_decision}</p><p><strong>Next question:</strong> {artifact.next_question || 'No further question; the session ended.'}</p>
                  {execution && <section className="outcome-python-evidence"><h5>{toolName} execution · {String(execution.status ?? 'status unavailable')}</h5><details className="research-execution-record"><summary>Execution source and output</summary><pre>{JSON.stringify(execution, null, 2)}</pre></details><p><strong>Execution ID:</strong> {String(execution.id ?? 'Unavailable')}</p>{typeof execution.exit_code === 'number' && <p><strong>Exit code:</strong> {execution.exit_code}</p>}{typeof reused === 'string' && <p><strong>Reuse:</strong> {reused}</p>}<p>{typeof execution.source === 'string' ? 'Exact source is retained in the execution record.' : 'Source unavailable in this record.'} Computation status is not proof of a mathematical claim.</p>{!!captured.length && <div><strong>Captured files</strong><ul>{captured.map((file, index) => <li key={index}>{String(file.filename ?? 'Unnamed file')} · {typeof file.size_bytes === 'number' ? `${file.size_bytes} bytes` : 'size unavailable'} · SHA-256 {String(file.sha256 ?? 'unavailable')}</li>)}</ul></div>}</section>}
                  <details><summary>Full validated role outputs</summary><h5>Investigator</h5>{Object.entries(artifact.investigator_output).filter(([key]) => !['python_execution', 'sage_execution'].includes(key)).map(([key, value]) => <p key={key}><strong>{key.replaceAll('_', ' ')}:</strong> {Array.isArray(value) ? value.join(' · ') : typeof value === 'object' && value !== null ? JSON.stringify(value) : String(value)}</p>)}<h5>Skeptic</h5>{Object.entries(artifact.skeptic_output).map(([key, value]) => <p key={key}><strong>{key.replaceAll('_', ' ')}:</strong> {Array.isArray(value) ? value.join(' · ') : typeof value === 'object' && value !== null ? JSON.stringify(value) : String(value)}</p>)}</details><small>{artifact.note}</small>
                </div></details>}</li>;
            })}</ol></section>}
          </div>
        </details>}
      </div>
    </section>
  </div>;
}

function ResearchWorkspace({ path, projectId, strategies, onViewStrategy, onForkFromFindings, onControlsChange }: { path: string; projectId: string; strategies: Strategy[]; onViewStrategy: (id: string) => void; onForkFromFindings: (session: ResearchSession) => void; onControlsChange: (controls: ProcessControls) => void }) {
  const eligible = useMemo(() => strategies.filter(strategy => !strategy.removed_at && strategy.enabled), [strategies]);
  const [sessions, setSessions] = useState<ResearchSession[]>([]);
  const selectedSessionId = useRef('');
  const sessionsLoaded = useRef(false);
  const [pendingStrategyIds, setPendingStrategyIds] = useState<string[]>([]);
  const [config, setConfig] = useState<{ available: boolean; model: string; reasoning_effort: string; mode: string; binding: string; message: string } | null>(null);
  const [limits, setLimits] = useState<ResearchLimits | null>(null);
  const [confirmStart, setConfirmStart] = useState(false);
  const [confirmRemoveId, setConfirmRemoveId] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [readError, setReadError] = useState('');
  const [announcement, setAnnouncement] = useState('');
  const [expanded, setExpanded] = useState(() => window.localStorage.getItem(`sigma.sessionsPane:${path}`) !== 'false');
  const [expandedSessionIds, setExpandedSessionIds] = useState<Set<string>>(() => new Set());
  const readErrorReported = useRef(false);
  const lastAnnouncement = useRef('');
  const idempotencyKey = useRef<string | null>(null);
  const submittingStart = useRef(false);
  const activeSession = sessions.find(item => item.status === 'queued' || item.status === 'running');

  const load = useCallback(async (preferredId?: string, signal?: AbortSignal) => {
    const query = new URLSearchParams({ path });
    const response = await fetch(`/api/projects/research-sessions?${query}`, { signal });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error ?? 'Could not read research sessions');
    const nextSessions = data.sessions as ResearchSession[];
    setSessions(nextSessions);
    readErrorReported.current = false;
    setReadError('');
    const requestedId = preferredId ?? selectedSessionId.current;
    const firstLoad = !sessionsLoaded.current;
    const chosen = (requestedId ? nextSessions.find(item => item.id === requestedId) : null)
      ?? (!sessionsLoaded.current && !selectedSessionId.current
        ? nextSessions.find(item => item.status === 'queued' || item.status === 'running' || item.status === 'paused') ?? nextSessions[0] ?? null
        : null);
    sessionsLoaded.current = true;
    selectedSessionId.current = chosen?.id ?? '';
    if (firstLoad && chosen) setExpandedSessionIds(current => current.size ? current : new Set([chosen.id]));
    if (chosen) {
      const transition = `${chosen.id}:${chosen.status}:${chosen.current_action}`;
      if (chosen.status === 'failed' && lastAnnouncement.current.startsWith(`${chosen.id}:`) && /:(queued|running):/.test(lastAnnouncement.current)) {
        setError(chosen.message);
        reportRequestFailure(chosen.message);
      }
      if (lastAnnouncement.current && transition !== lastAnnouncement.current) {
        setAnnouncement(`Research session ${chosen.session_number}: ${chosen.status}. ${chosen.current_action}.`);
      }
      lastAnnouncement.current = transition;
    }
    return chosen;
  }, [path]);

  const reportReadFailure = useCallback((cause: unknown) => {
    const message = errorMessage(cause);
    setReadError(message);
    if (!readErrorReported.current) reportRequestFailure(message);
    readErrorReported.current = true;
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void load(undefined, controller.signal).catch(cause => { if (!controller.signal.aborted) reportReadFailure(cause); });
    return () => controller.abort();
  }, [load, reportReadFailure]);

  useEffect(() => {
    if (!activeSession) return;
    const stopWatching = watchResearchProviderActivity(path, projectId);
    const poll = () => {
      if (document.visibilityState === 'visible') void load().catch(reportReadFailure);
    };
    const timer = window.setInterval(poll, 2000);
    document.addEventListener('visibilitychange', poll);
    return () => { window.clearInterval(timer); document.removeEventListener('visibilitychange', poll); stopWatching(); };
  }, [activeSession?.id, activeSession?.status, load, path, projectId, reportReadFailure]);

  async function begin() {
    setBusy(true); setError('');
    try {
      const response = await fetch(`/api/projects/proposals/config?${new URLSearchParams({ path })}`);
      const current = await response.json();
      if (!response.ok) throw new Error(current.error ?? 'Could not read AI configuration');
      const limitResponse = await fetch(`/api/projects/research-limits?${new URLSearchParams({ path })}`);
      const currentLimits = await limitResponse.json();
      if (!limitResponse.ok) throw new Error(currentLimits.error ?? 'Could not read research limits');
      if (!validateLimitDraft(draftLimits(currentLimits)).value) {
        throw new Error('Saved research limits need attention. Update them in Project Settings → Limits before starting a session.');
      }
      if (!current.available) throw new Error(current.message ?? 'Connect the selected AI account before investigating');
      if (eligible.length > 12) {
        throw new Error('A session can include at most 12 enabled strategies. Disable strategies before starting.');
      }
      if (eligible.length * 2 > currentLimits.model_calls) {
        throw new Error(
          `The ${eligible.length} enabled strategies need at least ${eligible.length * 2} model calls for their Investigator/Skeptic pairs, but the budget allows ${currentLimits.model_calls}. Disable strategies or increase the model-call limit in Project Settings.`,
        );
      }
      setPendingStrategyIds(eligible.map(strategy => strategy.id));
      setConfig(current); setLimits(currentLimits);
      setConfirmStart(true);
    } catch (cause) { setError(errorMessage(cause)); reportRequestFailure(errorMessage(cause)); }
    finally { setBusy(false); }
  }

  async function start() {
    if (submittingStart.current || !config || !pendingStrategyIds.length) return;
    submittingStart.current = true;
    setBusy(true); setError('');
    try {
      idempotencyKey.current ??= crypto.randomUUID();
      selectedSessionId.current = '';
      const next = await post<ResearchSession>('research-sessions/start', { path, strategy_id: pendingStrategyIds[0], strategy_ids: pendingStrategyIds, expected_project_id: projectId, expected_binding: config.binding, expected_limits: limits, idempotency_key: idempotencyKey.current });
      idempotencyKey.current = null;
      setConfirmStart(false); selectedSessionId.current = next.id;
      lastAnnouncement.current = `${next.id}:${next.status}:${next.current_action}`;
      await load(next.id);
      revealSession(next.id);
    } catch (cause) { await load().catch(() => {}); setError(errorMessage(cause)); reportRequestFailure(errorMessage(cause)); }
    finally { submittingStart.current = false; setBusy(false); }
  }

  async function control(action: 'pause' | 'resume' | 'stop', target: ResearchSession | null = null) {
    if (!target) return;
    setBusy(true); setError('');
    try { await post<ResearchSession>(`research-sessions/${target.id}/control`, { path, action }); await load(target.id); }
    catch (cause) { await load(target.id).catch(() => {}); setError(errorMessage(cause)); reportRequestFailure(errorMessage(cause)); }
    finally { setBusy(false); }
  }

  const interventionSaved = useCallback(async (sessionId: string) => {
    await load(sessionId);
    setAnnouncement('Human feedback added for a later agent step. No provider call was made.');
  }, [load]);

  function requestResume(target: ResearchSession) {
    revealSession(target.id);
    void control('resume', target);
  }

  function revealSession(id: string) {
    setExpanded(true);
    window.localStorage.setItem(`sigma.sessionsPane:${path}`, 'true');
    setExpandedSessionIds(current => new Set(current).add(id));
    requestAnimationFrame(() => requestAnimationFrame(() => {
      const row = document.querySelector<HTMLElement>(`[data-session-id="${CSS.escape(id)}"]`);
      row?.scrollIntoView({ block: 'center', behavior: 'smooth' });
    }));
  }

  async function removeSession(target: ResearchSession) {
    setBusy(true); setError('');
    try {
      const response = await fetch(`/api/projects/research-sessions/${encodeURIComponent(target.id)}`, {
        method: 'DELETE', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path, expected_updated_at: target.updated_at }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error ?? 'Session removal failed');
      setConfirmRemoveId('');
      setExpandedSessionIds(current => { const next = new Set(current); next.delete(target.id); return next; });
      if (selectedSessionId.current === target.id) selectedSessionId.current = '';
      await load();
      setAnnouncement(`Session #${result.session_number} removed. Strategy and other sessions were kept.`);
    } catch (cause) { setError(errorMessage(cause)); reportRequestFailure(errorMessage(cause)); }
    finally { setBusy(false); }
  }

  const playLabel = 'Start a new research session';
  const play = useCallback(() => {
    if (busy || readError) return;
    setExpanded(true); window.localStorage.setItem(`sigma.sessionsPane:${path}`, 'true');
    if (activeSession || !eligible.length) return;
    setConfirmStart(false);
    void begin();
  }, [activeSession, busy, eligible, readError, path]);
  const stop = useCallback(() => {
    if (activeSession?.status === 'running' && !busy && !readError) void control('stop', activeSession);
  }, [activeSession, busy, readError]);
  useEffect(() => {
    onControlsChange({
      play, stop, confirming: confirmStart, start: () => void start(), cancel: () => setConfirmStart(false), nextSessionNumber: Math.max(0, ...sessions.map(item => item.session_number)) + 1,
      playDisabled: busy || !!readError || confirmStart || (activeSession
        ? true
        : !eligible.length),
      stopDisabled: busy || !!readError || activeSession?.status !== 'running',
      playLabel,
    });
  }, [activeSession, busy, confirmStart, eligible.length, onControlsChange, stop, play, playLabel, readError, sessions]);

  const orderedSessions = [...sessions].sort((left, right) => left.session_number - right.session_number);

  const runningCount = sessions.filter(item => item.status === 'running' || item.status === 'queued').length;
  return <section className={`sessions-pane workspace-pane${expanded ? '' : ' is-collapsed'}`} aria-labelledby="sessions-heading">
    <header className="workspace-pane-heading sessions-pane-heading">
      <h2 id="sessions-heading" tabIndex={-1}><button type="button" className="workspace-section-disclosure" title={`${expanded ? 'Collapse' : 'Expand'} Sessions section`} aria-expanded={expanded} aria-controls="sessions-pane-content" onClick={() => setExpanded(value => { window.localStorage.setItem(`sigma.sessionsPane:${path}`, String(!value)); return !value; })}><DisclosureChevron expanded={expanded}/>Sessions</button></h2>
      <p className="section-count">{sessions.length} {sessions.length === 1 ? 'session' : 'sessions'}, {runningCount} running</p>
    </header>

    <div id="sessions-pane-content" hidden={!expanded}>
    <div className="session-table">
      {sessions.length ? <ol className="session-list" aria-label="Research sessions">
        {orderedSessions.map(item => {
          const currentAction = readError && activeSession?.id === item.id ? `State unknown · ${item.current_action}` : item.current_action;
          const sessionExpanded = expandedSessionIds.has(item.id);
          return <li className="session-row" key={item.id} data-session-id={item.id}>
            <div className="session-row-heading">
              <div className="session-summary">
                <div className="session-title-line"><button type="button" className="session-row-disclosure" title={`${sessionExpanded ? 'Collapse' : 'Expand'} Session ${item.session_number} details`} aria-expanded={sessionExpanded} aria-controls={`session-content-${item.id}`} onClick={() => setExpandedSessionIds(current => { const next = new Set(current); if (next.has(item.id)) next.delete(item.id); else next.add(item.id); return next; })}><DisclosureChevron expanded={sessionExpanded}/><span className="session-row-title">Session #{item.session_number}</span></button>
                <div className="session-heading-actions" aria-label={`Session ${item.session_number} actions`}>
                  {(item.status === 'stopped' || item.status === 'paused') && <button type="button" className="text-view-link session-remove-link" title={`Resume Session ${item.session_number}`} data-tooltip={`Resume Session ${item.session_number}`} disabled={busy || !!readError || (!!activeSession && activeSession.id !== item.id)} onClick={() => requestResume(item)}>Resume</button>}
                  {['queued', 'running', 'paused'].includes(item.status) && <button type="button" className="text-view-link session-remove-link" title={`Stop Session ${item.session_number}; it can be resumed later`} disabled={busy} onClick={() => void control('stop', item)}>Stop</button>}
                  {['completed', 'ended', 'stopped', 'failed'].includes(item.status) && <button type="button" className="text-view-link destructive-action session-remove-link" title={`Remove Session ${item.session_number} and its saved research`} disabled={busy} onClick={() => setConfirmRemoveId(item.id)}>Remove</button>}
                  {['completed', 'ended', 'stopped', 'failed'].includes(item.status) && confirmRemoveId === item.id && <div className="session-remove-actions"><div className="research-stop-confirm" role="group" aria-label={`Confirm remove Session ${item.session_number}`}><p>Remove Session #{item.session_number} and its saved research record and artifacts? The strategy and other sessions will remain.</p><div className="session-remove-confirm-actions"><button type="button" className="text-view-link destructive-action" title={`Confirm removal of Session ${item.session_number}`} disabled={busy} onClick={() => void removeSession(item)}>Confirm</button><button type="button" className="text-view-link" title={`Keep Session ${item.session_number}`} disabled={busy} onClick={() => setConfirmRemoveId('')}>Cancel</button></div></div></div>}
                </div></div>
                <span className={`session-status session-${item.status}`} aria-label={`Lifecycle status: ${item.status}`}><i aria-hidden="true"/>{item.status}</span>
                <small className={`session-strategy-name session-outcome-inline outcome-${item.outcome.assessment}`}><span>{item.outcome.label}{item.outcome.provisional ? ' · provisional' : ''}</span></small>
                <small className="session-progress-inline">Cycle {item.cycle} of {item.cycle_limit ?? 3} · {item.calls_used}/{item.call_limit} calls</small>
              </div>
            </div>
            <ResearchSessionContents path={path} session={{ ...item, current_action: currentAction }} expanded={sessionExpanded} busy={busy} onViewStrategy={onViewStrategy} onViewPriorSession={revealSession} onForkFromFindings={onForkFromFindings} onInterventionSaved={interventionSaved}/>
          </li>;
        })}
      </ol> : !confirmStart && <p className="sessions-empty">No sessions yet. Use Play in Strategies to start one.</p>}
    </div>
    {readError && <p className="error" role="alert">Unable to confirm session state. Last confirmed information is shown: {readError}</p>}
    {error && <p className="error" role="alert">{error}</p>}
    </div>
    <p className="sr-only" role="status" aria-live="polite">{announcement}</p>
  </section>;
}

type TextFormat = 'plain' | 'markdown';
type TextDisplay = 'plain' | 'rendered';
type TextVersion = { body: string; kind: 'authored' | 'ai_derived'; current: boolean; source_digest: string; source_format: TextFormat; created_at: string; provenance: { provider: string; model: string; reasoning_effort: string | null } | null; warnings: string[] };
type TextRepresentations = { source_format: TextFormat; source_digest: string; plain: TextVersion | null; markdown: TextVersion | null };

async function post<T>(route: string, body: object = {}, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`/api/projects/${route}`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body), signal,
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error ?? JSON.stringify(data.detail) ?? 'Request failed');
  return data;
}
const errorMessage = (error: unknown) => error instanceof Error ? error.message : String(error);
const projectUrl = (path: string) => `/project?${new URLSearchParams({ path })}`;
const dateLabel = (value: string) => new Date(value).toLocaleString();
function formatDuration(totalSeconds: number) {
  const seconds = Math.max(0, Math.floor(totalSeconds));
  return `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
}

function useDocumentScrollLock(enabled = true) {
  useEffect(() => {
    if (!enabled) return;
    const root = document.documentElement;
    const body = document.body;
    const previous = {
      rootOverflow: root.style.overflow,
      rootOverscroll: root.style.overscrollBehavior,
      bodyOverflow: body.style.overflow,
      bodyOverscroll: body.style.overscrollBehavior,
    };
    root.style.overflow = 'hidden';
    root.style.overscrollBehavior = 'none';
    body.style.overflow = 'hidden';
    body.style.overscrollBehavior = 'none';
    return () => {
      root.style.overflow = previous.rootOverflow;
      root.style.overscrollBehavior = previous.rootOverscroll;
      body.style.overflow = previous.bodyOverflow;
      body.style.overscrollBehavior = previous.bodyOverscroll;
    };
  }, [enabled]);
}

function ProjectExportDialog({ path, title, onCancel, open = true, demo = false }: { path: string; title: string; onCancel: () => void; open?: boolean; demo?: boolean }) {
  useDocumentScrollLock(open);
  const dialog = useRef<HTMLDialogElement>(null);
  const input = useRef<HTMLInputElement>(null);
  const submitting = useRef(false);
  const defaultStem = `sigma-${(title || 'project').replace(/[^a-z0-9_-]+/gi, '-').replace(/^-|-$/g, '') || 'project'}`;
  const [exportType, setExportType] = useState<'audit' | 'text' | 'html'>('audit');
  const isReport = exportType !== 'audit';
  const reportFormat = exportType === 'text' ? 'txt' : 'html';
  const [filename, setFilename] = useState(defaultStem);
  const [openInTab, setOpenInTab] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  useEffect(() => {
    if (!dialog.current) return;
    if (open && !dialog.current.open) {
      dialog.current.showModal();
      input.current?.focus();
      input.current?.select();
    } else if (!open && dialog.current.open) dialog.current.close();
  }, [open]);
  function cancel() { if (!submitting.current) onCancel(); }
  async function exportFile(event: FormEvent) {
    event.preventDefault();
    if (submitting.current) return;
    const chosen = filename.trim();
    const stem = chosen.replace(/\.(json|txt|html|tex|pdf)$/i, '');
    if (!stem || stem === '.' || stem === '..' || /[\/\\<>:"|?*\x00-\x1f]/.test(stem)) {
      setError('Enter a filename stem without path separators or reserved characters.');
      return;
    }
    const extension = exportType === 'audit' ? 'json' : reportFormat;
    const downloadName = `${stem}.${extension}`;
    const opened = openInTab ? window.open('about:blank', '_blank') : null;
    if (opened) opened.opener = null;
    submitting.current = true; setBusy(true); setError('');
    try {
      const route = demo ? (exportType === 'audit' ? '/api/cloud-demo/' : '/api/cloud-demo/report') : (exportType === 'audit' ? '/api/projects/export' : '/api/projects/export/report');
      const query = new URLSearchParams({ ...(!demo ? { path } : {}), ...(isReport ? { format: reportFormat } : {}) });
      const suffix = query.toString();
      const response = await fetch(`${route}${suffix ? `?${suffix}` : ''}`, { cache: 'no-store' });
      if (!response.ok) {
        const detail = await response.json().catch(() => null);
        throw new Error(detail?.error ?? detail?.detail ?? 'Project export failed');
      }
      let content: string;
      if (exportType === 'audit') {
        const result = await response.json() as { export_version: number; project: { title: string }; agentic_runs: unknown[]; research_sessions: ResearchSession[] };
        if (result.export_version !== 2 || !result.project || !Array.isArray(result.agentic_runs) || !Array.isArray(result.research_sessions)) throw new Error('Invalid project export response');
        content = `${JSON.stringify(result, null, 2)}\n`;
      } else content = await response.text();
      if (opened && !opened.closed) {
        if (exportType === 'html') opened.document.open(), opened.document.write(content), opened.document.close();
        else {
          opened.document.title = `${title} — ${exportType === 'audit' ? 'Project Audit' : 'Research Report'}`;
          const pre = opened.document.createElement('pre');
          pre.style.cssText = 'white-space:pre-wrap;overflow-wrap:anywhere;font:14px/1.6 ui-monospace,monospace;padding:1rem';
          pre.textContent = content;
          opened.document.body.replaceChildren(pre);
        }
      }
      const mimeType = exportType === 'audit' ? 'application/json;charset=utf-8' : exportType === 'html' ? 'text/html;charset=utf-8' : 'text/plain;charset=utf-8';
      const url = URL.createObjectURL(new Blob([content], { type: mimeType }));
      const link = document.createElement('a');
      link.href = url; link.download = downloadName;
      document.body.appendChild(link); link.click(); link.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
      if (openInTab && (!opened || opened.closed)) {
        setError('The browser blocked or closed the new tab. The file was still downloaded.');
      } else onCancel();
    } catch (cause) { if (opened && !opened.closed) opened.close(); setError(errorMessage(cause)); }
    finally { submitting.current = false; setBusy(false); }
  }
  return <dialog ref={dialog} className="project-settings-dialog export-project-dialog" aria-labelledby="export-project-heading"
    onCancel={event => { event.preventDefault(); cancel(); }}>
    <form onSubmit={exportFile}>
      <header className="settings-header">
        <h2 id="export-project-heading">{demo ? 'Export Demo Project' : 'Export Project'}</h2>
        <div className="settings-actions">
          <button type="button" className="settings-cancel" title="Close without downloading" disabled={busy} onClick={() => cancel()}>Cancel</button>
        </div>
      </header>
      <div className="settings-body">
        <fieldset className="export-type-options" disabled={busy}>
          <legend>Report type</legend>
          <label><input type="radio" name="export-type" value="audit" checked={exportType === 'audit'} onChange={() => setExportType('audit')}/> Project Audit</label>
          <label><input type="radio" name="export-type" value="text" checked={exportType === 'text'} onChange={() => setExportType('text')}/> Text file</label>
          <label><input type="radio" name="export-type" value="html" checked={exportType === 'html'} onChange={() => setExportType('html')}/> HTML report</label>
        </fieldset>
        <label htmlFor="export-project-filename">Filename</label>
        <div className="export-filename-field"><input ref={input} id="export-project-filename" value={filename} maxLength={260} disabled={busy} spellCheck={false}
          onChange={event => { setFilename(event.target.value.replace(/[\/\\<>:"|?*\x00-\x1f]/g, '-').replace(/\.(json|txt|html|tex|pdf)$/i, '')); setError(''); }}/>
          <span aria-hidden="true">.{exportType === 'audit' ? 'json' : reportFormat}</span></div>
        <label className="export-open-tab"><input type="checkbox" checked={openInTab} disabled={busy} onChange={event => setOpenInTab(event.target.checked)}/> Open in browser tab</label>
        {error && <p className="error" role="alert">{error}</p>}
      </div>
      <footer className="export-footer">
        <button type="submit" className="settings-submit" title="Download the selected project export" disabled={busy}>{busy ? 'Downloading…' : 'Download'}</button>
      </footer>
    </form>
  </dialog>;
}

type PaperSummary = { paper_id: string; title: string; created_at: string; snapshot_sha256: string; validation_warnings: string[]; author_review_warnings?: string[]; pdf_available?: boolean; generation: { mode: string; model: string; reasoning_effort: string; call_limit: number; provider_calls_attempted?: number; provider_calls_prior_runs?: number; provider_calls_lifetime_total?: number; long_form?: boolean; evidence_batch_count?: number; evidence_fields_omitted?: number; omitted_evidence?: { field_ref: string; source_ref: string; field: string; reason: string }[]; evidence_note_compaction_events?: number; reduction_source_refs_omitted?: string[]; evidence_conflict_note_count?: number; evidence_conflicts?: { statement: string; evidence_refs: string[] }[] } };
type PaperRecord = PaperSummary & { draft: { title: string; abstract: string; abstract_claim_ids: string[]; problem_framing: string[]; problem_framing_claim_ids: string[]; methods: string[]; methods_claim_ids: string[]; claims: { id: string; statement: string; status: string; evidence_refs: string[]; reasoning: string }[]; sections: { heading: string; paragraphs: string[]; claim_ids: string[] }[]; limitations: string[]; open_obligations: string[]; conclusions: string[]; conclusion_claim_ids: string[] }; obligation_reconciliation?: { text: string; source_refs: string[]; status: string }[]; snapshot: { sources: { id: string; kind: string }[] } };

function AIPaperDialog({ path, projectId, downloadFilename, openInTab, onCancel }: { path: string; projectId: string; downloadFilename: string; openInTab: boolean; onCancel: () => void }) {
  const ai = useAI();
  const dialog = useRef<HTMLDialogElement>(null);
  const request = useRef<AbortController | null>(null);
  const [papers, setPapers] = useState<PaperSummary[]>([]);
  const [selected, setSelected] = useState<PaperRecord | null>(null);
  const [binding, setBinding] = useState('');
  const [model, setModel] = useState('');
  const [mode, setMode] = useState('');
  const [effort, setEffort] = useState('');
  const [checkpoint, setCheckpoint] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const [longForm, setLongForm] = useState(false);
  const [phase, setPhase] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  useEffect(() => { dialog.current?.showModal(); void refresh(); return () => request.current?.abort(); }, []);
  async function refresh(keepId?: string) {
    setLoading(true);
    try {
      const query = new URLSearchParams({ path });
      const [listResponse, configResponse] = await Promise.all([
        fetch(`/api/projects/papers?${query}`, { cache: 'no-store' }),
        fetch(`/api/projects/proposals/config?${query}`, { cache: 'no-store' }),
      ]);
      const list = await listResponse.json(); const config = await configResponse.json();
      if (!listResponse.ok) throw new Error(list.error ?? 'Could not load saved AI papers.');
      setPapers(list.papers as PaperSummary[]);
      if (!configResponse.ok || !config.available) { setBinding(''); setModel(config.model ?? ''); setMode(config.mode ?? ''); setEffort(config.reasoning_effort ?? ''); setCheckpoint(null); }
      else {
        setBinding(config.binding); setModel(config.model); setMode(config.mode); setEffort(config.reasoning_effort);
        const params = new URLSearchParams({
          path, long_form: String(longForm), expected_project_id: projectId, expected_binding: config.binding,
          mode: config.mode, model: config.model, reasoning_effort: config.reasoning_effort,
        });
        const preflightResponse = await fetch(`/api/projects/papers/preflight?${params}`, { cache: 'no-store' });
        const preflight = await preflightResponse.json();
        if (preflightResponse.ok) setCheckpoint(preflight);
      }
      const nextId = keepId ?? selected?.paper_id ?? list.papers?.[0]?.paper_id;
      if (nextId) {
        const response = await fetch(`/api/projects/papers/${encodeURIComponent(nextId)}?${query}`, { cache: 'no-store' });
        const record = await response.json(); if (!response.ok) throw new Error(record.error ?? 'Could not open this paper version.');
        setSelected(record as PaperRecord);
      } else setSelected(null);
      setError(!configResponse.ok || !config.available ? (config.message ?? 'Connect an eligible AI provider to author a paper.') : '');
    } catch (cause) { setError(errorMessage(cause)); }
    finally { setLoading(false); }
  }
  async function openPaper(id: string) {
    try {
      const response = await fetch(`/api/projects/papers/${encodeURIComponent(id)}?${new URLSearchParams({ path })}`, { cache: 'no-store' });
      const record = await response.json(); if (!response.ok) throw new Error(record.error ?? 'Could not open this paper version.');
      setSelected(record as PaperRecord); setError('');
    } catch (cause) { setError(errorMessage(cause)); }
  }
  async function restartCheckpoint() {
    if (busy || !checkpoint?.checkpoint_can_restart || !binding) return;
    const prior = Number(checkpoint.provider_calls_previous_runs ?? 0) + Number(checkpoint.provider_calls_attempted ?? 0);
    const restartCostCeiling = mode === 'api_key'
      ? ' At 12,000 requested output tokens per call, a fresh run may request up to ' + Number(checkpoint.maximum_fresh_run_requested_output_tokens).toLocaleString() + ' output tokens; this is a ceiling, not expected consumption or a dollar quote.'
      : ' The new run is subject to your ChatGPT-plan allowance.';
    if (!window.confirm(
      `Restart long-form authoring from the beginning? This discards the current checkpointed work and can repeat up to ${Number(checkpoint.maximum_provider_calls).toLocaleString()} provider calls. The ${prior.toLocaleString()} calls already attempted will remain recorded. ${restartCostCeiling} ${mode === 'api_key' ? 'Additional calls can incur API-key charges.' : ''}`
    )) return;
    setBusy(true); setError(''); setPhase('Resetting the long-form checkpoint…');
    try {
      const response = await fetch('/api/projects/papers/restart', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          path, expected_project_id: projectId, expected_binding: binding,
          expected_snapshot_sha256: checkpoint.snapshot_sha256, confirm_restart: true,
        }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error ?? 'Could not reset the long-form checkpoint.');
      setPhase(`Checkpoint reset. ${Number(result.provider_calls_previous_runs).toLocaleString()} previous provider call attempts remain recorded.`);
      await refresh(selected?.paper_id);
    } catch (cause) { setError(errorMessage(cause)); }
    finally { setBusy(false); }
  }
  async function generatePaper() {
    if (busy || !binding) return;
    const controller = new AbortController(); request.current = controller;
    setBusy(true); setPhase('Checking the frozen evidence size…'); setError('');
    let finishProvider = () => {};
    let timer = 0;
    try {
      const preflightParams = new URLSearchParams({
        path, long_form: String(longForm), expected_project_id: projectId, expected_binding: binding,
        mode, model, reasoning_effort: effort,
      });
      const preflightResponse = await fetch(`/api/projects/papers/preflight?${preflightParams}`, { cache: 'no-store', signal: controller.signal });
      const preflight = await preflightResponse.json();
      if (!preflightResponse.ok) throw new Error(preflight.error ?? 'Could not size the evidence snapshot.');
      if (preflight.checkpoint_exists && !preflight.resume_available) {
        throw new Error('A checkpoint exists for different project or provider settings. Use Restart checkpoint to preserve its attempt history before generating.');
      }
      const resumeDisclosure = preflight.resume_available
        ? ' This resumes after ' + Number(preflight.completed_batches).toLocaleString() + ' completed evidence batches, ' + Number(preflight.reduction_groups_completed).toLocaleString() + ' index-reduction groups' + (preflight.outline_complete ? ', with the outline saved' : '') + ', and ' + Number(preflight.completed_sections).toLocaleString() + ' sections. ' + Number(preflight.provider_calls_attempted).toLocaleString() + ' calls were already attempted in this run; ' + Number(preflight.provider_calls_previous_runs).toLocaleString() + ' in prior runs. Up to ' + Number(preflight.provider_calls_remaining).toLocaleString() + ' more calls may be made.'
        : '';
      const callBreakdown = preflight.long_form
        ? ' Call ceiling by stage: ' + preflight.maximum_evidence_calls + ' evidence, up to ' + preflight.maximum_index_reduction_calls + ' index reduction, 1 outline, and up to ' + preflight.maximum_section_calls + ' sections.'
        : ' This uses one provider call.';
      const tokenCeiling = ' Structured stage-input limits total up to ' + (Number(preflight.maximum_structured_input_bytes) / 1_000_000).toFixed(1) + ' MB.' + (mode === 'api_key'
        ? ' At 12,000 requested output tokens per API-key call, the run could request up to ' + Number(preflight.maximum_requested_output_tokens).toLocaleString() + ' output tokens; this is a ceiling, not expected consumption or a dollar estimate.'
        : ' ChatGPT-plan use is subject to provider allowance; this client cannot convert it to a dollar estimate.');
      if (preflight.long_form && !window.confirm(
        'This frozen snapshot is ' + Number(preflight.snapshot_bytes).toLocaleString() + ' bytes across ' + Number(preflight.source_count).toLocaleString() + ' saved sources. Long-form authoring will use ' + Number(preflight.evidence_batches).toLocaleString() + ' evidence batches, then a plan and separate section calls. The run may use up to ' + Number(preflight.maximum_provider_calls).toLocaleString() + ' calls.' + callBreakdown + tokenCeiling + resumeDisclosure + ' ' + (mode === 'api_key' ? 'API-key mode can incur separate usage charges.' : 'ChatGPT-plan usage is subject to provider allowance.') + ' Continue?'
      )) {
        setPhase('Large paper generation was not started; no provider calls were made.');
        return;
      }
      finishProvider = beginProviderRequest('ai-paper');
      setPhase(preflight.long_form
        ? `Indexing ${Number(preflight.evidence_batches).toLocaleString()} evidence batches, then authoring the planned sections…`
        : 'Authoring and validating the paper, then compiling the PDF…');
      timer = window.setTimeout(() => setPhase(preflight.long_form
        ? 'Long-form evidence indexing and section authoring are in progress…'
        : 'Authoring, validating evidence references, and compiling PDF…'), 350);
      const response = await fetch('/api/projects/papers', { method: 'POST', headers: { 'Content-Type': 'application/json' }, signal: controller.signal,
        body: JSON.stringify({ path, expected_project_id: projectId, expected_binding: binding, expected_snapshot_sha256: preflight.snapshot_sha256, long_form: longForm }) });
      if (!response.ok) {
        const failure = await response.json().catch(() => null);
        throw new Error(failure?.error ?? `Paper generation failed (${response.status}); no version was published.`);
      }
      if (!response.headers.get('content-type')?.includes('text/event-stream') || !response.body)
        throw new Error(`Paper generation failed with an invalid server response (${response.status}). No version was published.`);
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let result: { paper_id: string } | null = null;
      while (true) {
        const { done, value } = await reader.read();
        buffer += decoder.decode(value, { stream: !done });
        const frames = buffer.split('\n\n'); buffer = frames.pop() ?? '';
        for (const frame of frames) {
          const line = frame.split('\n').find(item => item.startsWith('data: '));
          if (!line) continue;
          const event = JSON.parse(line.slice(6));
          if (event.type === 'error') throw new Error(event.error ?? 'Paper generation failed.');
          if (event.type === 'complete') result = event.result as { paper_id: string };
          if (event.type === 'progress') {
            const stage = event.stage === 'snapshot' ? 'Frozen the complete evidence snapshot'
              : event.stage === 'evidence' ? `Indexing evidence batch ${event.completed} of ${event.total}`
              : event.stage === 'index' ? 'Consolidating the source-linked evidence index'
              : event.stage === 'outline' ? 'Planning the complete paper outline'
              : event.stage === 'compile' ? 'Compiling the complete TeX document and validating the PDF'
              : `Authoring paper section ${event.completed} of ${event.total}`;
            setPhase(`${stage}…`);
          }
        }
        if (done) break;
      }
      if (!result) throw new Error('Paper generation ended without a completed version. No version was published.');
      setPhase('Saved a new immutable paper version.');
      await refresh(result.paper_id);
    } catch (cause) {
      if (controller.signal.aborted) setPhase('Generation cancelled. No new version was published.');
      else { setError(errorMessage(cause)); reportRequestFailure(errorMessage(cause)); }
      await refresh(selected?.paper_id);
    } finally { if (timer) window.clearTimeout(timer); finishProvider(); request.current = null; setBusy(false); }
  }
  const pdfUrl = selected ? `/api/projects/papers/${encodeURIComponent(selected.paper_id)}/pdf?${new URLSearchParams({ path })}` : '';
  return <dialog ref={dialog} className="project-settings-dialog ai-paper-dialog" aria-labelledby="ai-paper-heading" onCancel={event => { event.preventDefault(); if (!busy) onCancel(); }}>
    <header className="settings-header"><h2 id="ai-paper-heading">Academic paper using LaTeX</h2><div className="settings-actions"><button type="button" className="settings-cancel" disabled={busy} onClick={onCancel}>Close</button></div></header>
    <div className="settings-body ai-paper-body">
      <p className="settings-hint">This is a bounded AI authoring operation, separate from Project Audit and deterministic Research Reports. It uses the complete current evidence snapshot and creates a new saved version. {mode === 'api_key' ? 'API-key mode may incur separate usage charges.' : 'ChatGPT plan usage is subject to provider allowance.'}</p>
      <p className="settings-hint">Selected model: <strong>{model || 'Loading…'}</strong>. No research session will be started.</p>
      <p className="settings-hint"><strong>Generation bounds:</strong> the complete snapshot is archived up to 20 MB. Snapshots above 100,000 bytes use 48 KB evidence batches, an outline, and one call per section, with at most 512 batches, 48 sections, and 593 provider calls. Each call has a 120-second deadline; API-key calls request up to 12,000 output tokens with a 1 MB response cap, while ChatGPT-plan responses are capped at 4 MB per stream. TeX compilation allows 50 MB and 300 seconds, with PDFs up to 80 MB. Each saved version is capped at 100 MB.</p>
      <label className="ai-paper-long-form"><input type="checkbox" checked={longForm} disabled={busy} onChange={event => setLongForm(event.target.checked)}/> Use expanded multi-section authoring for a more detailed paper</label>
      {checkpoint?.checkpoint_can_restart && <p className="settings-hint" role="status">
        {checkpoint.resume_available
          ? `Checkpoint: ${checkpoint.completed_batches} evidence batches, ${checkpoint.reduction_groups_completed} reduction groups, ${checkpoint.completed_sections} sections complete; ${checkpoint.provider_calls_attempted} calls attempted in this run, ${checkpoint.provider_calls_previous_runs} in prior runs. ${checkpoint.provider_calls_remaining} remain in this run's call ceiling.`
          : `A checkpoint exists but does not match current settings. It records ${checkpoint.provider_calls_attempted} calls in its current run and ${checkpoint.provider_calls_previous_runs} in earlier runs; restart to keep this accounting before authoring.`}
      </p>}
      <div className="ai-paper-controls"><button type="button" className="settings-submit" disabled={busy || loading || !binding} onClick={() => void generatePaper()}>{busy ? 'Authoring…' : papers.length ? 'Generate new version' : 'Generate paper'}</button>{checkpoint?.checkpoint_can_restart && <button type="button" className="settings-cancel" disabled={busy || loading || !binding} onClick={() => void restartCheckpoint()}>Restart checkpoint</button>}{busy && <button type="button" className="settings-cancel" onClick={() => request.current?.abort()}>Cancel generation</button>}</div>
      {(busy || phase.startsWith('Generation cancelled.')) && <p role="status" aria-live="polite">{phase}</p>}
      {error && <p role="alert" className="error">{error}</p>}
      {loading && <p>Loading saved versions…</p>}
      {!loading && papers.length > 0 && <label htmlFor="ai-paper-version">Saved versions</label>}
      {!loading && papers.length > 0 && <select id="ai-paper-version" value={selected?.paper_id ?? ''} disabled={busy} onChange={event => void openPaper(event.target.value)}>{papers.map(item => <option key={item.paper_id} value={item.paper_id}>{item.title} · {dateLabel(item.created_at)}</option>)}</select>}
      {selected && <article className="ai-paper-preview">
        <h3>{selected.draft.title}</h3>
        <p><strong>Abstract.</strong> {selected.draft.abstract}</p>
        <p className="settings-hint">Abstract claim links: {selected.draft.abstract_claim_ids.join(', ') || 'None'}</p>
        <h4>Problem framing</h4>{selected.draft.problem_framing.map((text, index) => <p key={`framing-${index}`}>{text}</p>)}
        <p className="settings-hint">Claim links: {selected.draft.problem_framing_claim_ids.join(', ') || 'None'}</p>
        <h4>Methods and evidence</h4>{selected.draft.methods.map((text, index) => <p key={`method-${index}`}>{text}</p>)}
        <p className="settings-hint">Claim links: {selected.draft.methods_claim_ids.join(', ') || 'None'}</p>
        <p><strong>Snapshot.</strong> SHA-256 {selected.snapshot_sha256} · {selected.snapshot.sources.length} stable evidence sources</p>
        <p><strong>Generated.</strong> {selected.generation.model} ({selected.generation.mode}) · {dateLabel(selected.created_at)}{selected.generation.long_form ? ` · ${selected.generation.evidence_batch_count} evidence batches · ${selected.generation.provider_calls_attempted} calls this run · ${selected.generation.provider_calls_prior_runs} prior-run calls · ${selected.generation.provider_calls_lifetime_total} lifetime calls` : ''}</p>
        {!!selected.generation.omitted_evidence?.length && <details><summary>Evidence fields omitted from the generated index ({selected.generation.evidence_fields_omitted})</summary>{selected.generation.omitted_evidence.map(item => <p className="ai-paper-warning" key={item.field_ref}><code>{item.source_ref}{item.field}</code>: {item.reason}</p>)}</details>}
        {!!selected.generation.reduction_source_refs_omitted?.length && <details><summary>Sources omitted during index reduction ({selected.generation.reduction_source_refs_omitted.length})</summary>{selected.generation.reduction_source_refs_omitted.map(source => <p className="ai-paper-warning" key={source}><code>{source}</code></p>)}<p className="settings-hint">The complete original source records remain in the archived snapshot.</p></details>}
        {!!selected.generation.evidence_conflicts?.length && <details><summary>Potential conflicts and gaps identified by the evidence index ({selected.generation.evidence_conflict_note_count})</summary>{selected.generation.evidence_conflicts.map((conflict, index) => <p className="ai-paper-warning" key={`conflict-${index}`}>{conflict.statement} <strong>Sources:</strong> {conflict.evidence_refs.map(source => <code key={source}>{source} </code>)}</p>)}</details>}
        {selected.validation_warnings.map((warning, index) => <p className="ai-paper-warning" key={`system-${index}`}>Evidence validation: {warning}</p>)}
        {(selected.author_review_warnings ?? []).map((warning, index) => <p className="ai-paper-warning" key={`author-${index}`}>Author self-review (not independent): {warning}</p>)}
        {selected.draft.sections.map(section => <section key={section.heading}><h4>{section.heading}</h4>{section.paragraphs.map((paragraph, index) => <p key={index}>{paragraph}</p>)}<p className="settings-hint">Claim links: {section.claim_ids.join(', ') || 'None'}</p></section>)}
        <h4>Claim register</h4>{selected.draft.claims.map(claim => <section key={claim.id}><p><strong>{claim.id} · {claim.status}:</strong> {claim.statement}</p><p>{claim.reasoning}</p><p className="settings-hint">Evidence: {claim.evidence_refs.join(', ') || 'No source reference'}</p></section>)}
        <h4>Limitations</h4><ul>{selected.draft.limitations.map((item, index) => <li key={index}>{item}</li>)}</ul>
        {selected.draft.open_obligations.length > 0 && <><h4>Open obligations</h4><ul>{selected.draft.open_obligations.map((item, index) => <li key={index}>{item}</li>)}</ul></>}
        {!!selected.obligation_reconciliation?.length && <><h4>Frozen obligation reconciliation</h4><p className="settings-hint">Unlisted evidence obligations are not presumed resolved. References point to the saved evidence source and field.</p><ul>{selected.obligation_reconciliation.map((item, index) => <li key={index}><strong>{item.status}.</strong> {item.text}<br/><span className="settings-hint">{item.source_refs.join(', ') || 'No exact frozen-record match'}</span></li>)}</ul></>}
        <h4>Conclusions</h4>{selected.draft.conclusions.map((item, index) => <p key={`conclusion-${index}`}>{item}</p>)}
        <p className="settings-hint">Conclusion claim links: {selected.draft.conclusion_claim_ids.join(', ') || 'None'}</p>
        {selected.pdf_available && (openInTab
          ? <a className="text-view-link" href={pdfUrl} target="_blank" rel="noopener noreferrer">Open compiled PDF in new tab</a>
          : <a className="text-view-link" href={pdfUrl} download={downloadFilename}>Download compiled PDF</a>)}
        {!selected.pdf_available && <p role="status">The paper record is saved, but its compiled PDF is unavailable. Regenerate to create a new version with a PDF.</p>}
      </article>}
    </div>
  </dialog>;
}

function FloatingTooltip() {
  const [active, setActive] = useState<{ element: HTMLElement; text: string } | null>(null);
  const tooltip = useRef<HTMLDivElement>(null);
  const activeRef = useRef<HTMLElement | null>(null);
  const suppressedAfterClick = useRef(new WeakSet<HTMLElement>());
  const previousDescriptions = useRef(new WeakMap<HTMLElement, string | null>());
  const hoverTimer = useRef<number | null>(null);
  const clearHoverTimer = () => {
    if (hoverTimer.current !== null) window.clearTimeout(hoverTimer.current);
    hoverTimer.current = null;
  };
  const position = useCallback(() => {
    const element = activeRef.current;
    const hint = tooltip.current;
    if (!element?.isConnected || !hint) return;
    const anchor = element.getBoundingClientRect();
    const box = hint.getBoundingClientRect();
    const left = Math.max(8, Math.min(window.innerWidth - box.width - 8, anchor.left + anchor.width / 2 - box.width / 2));
    const below = anchor.bottom + 8;
    const top = below + box.height <= window.innerHeight - 8
      ? below
      : Math.max(8, anchor.top - box.height - 8);
    hint.style.left = `${left}px`;
    hint.style.top = `${top}px`;
  }, []);
  const hide = useCallback((element?: HTMLElement | null) => {
    const current = activeRef.current;
    if (!current || element && element !== current) return;
    const previous = previousDescriptions.current.get(current);
    if (previous === undefined || previous === null) current.removeAttribute('aria-describedby');
    else current.setAttribute('aria-describedby', previous);
    previousDescriptions.current.delete(current);
    activeRef.current = null;
    setActive(null);
  }, []);
  const show = useCallback((element: HTMLElement | null) => {
    if (document.querySelector('.project-model-confirm-popover')) { hide(); return; }
    const text = element?.dataset.tooltip?.trim() || element?.getAttribute('aria-label')?.trim();
    if (!element || !text) return;
    if (activeRef.current === element) { setActive({ element, text }); return; }
    const previous = element.getAttribute('aria-describedby');
    previousDescriptions.current.set(element, previous);
    element.setAttribute('aria-describedby', [previous, 'sigma-ui-tooltip'].filter(Boolean).join(' '));
    activeRef.current = element;
    setActive({ element, text });
  }, [hide]);
  useEffect(() => {
    const targetFor = (target: EventTarget | null) => target instanceof Element
      ? target.closest<HTMLElement>('[data-tooltip]:not([data-tooltip-disabled]), button[aria-label]:not([data-tooltip-disabled])')
      : null;
    const onPointerOver = (event: PointerEvent) => {
      const element = targetFor(event.target);
      if (document.querySelector('.project-model-confirm-popover')) { clearHoverTimer(); hide(); return; }
      if (element && suppressedAfterClick.current.has(element)) return;
      if (element && element !== activeRef.current) {
        clearHoverTimer();
        hide();
        hoverTimer.current = window.setTimeout(() => {
          hoverTimer.current = null;
          if (element.matches(':hover') && !suppressedAfterClick.current.has(element)) show(element);
        }, 400);
      }
    };
    const onPointerOut = (event: PointerEvent) => {
      const element = targetFor(event.target);
      const related = targetFor(event.relatedTarget);
      if (element && related !== element) clearHoverTimer();
      if (element && related !== element) suppressedAfterClick.current.delete(element);
      if (element && element === activeRef.current && related !== element && !element.matches(':focus-visible')) hide(element);
    };
    const onClick = (event: Event) => {
      const element = targetFor(event.target);
      if (!element) return;
      clearHoverTimer();
      suppressedAfterClick.current.add(element);
      hide(element);
    };
    const onFocusIn = (event: FocusEvent) => { clearHoverTimer(); show(targetFor(event.target)); };
    const onFocusOut = (event: FocusEvent) => {
      const element = targetFor(event.target);
      if (element && !element.matches(':hover') && !element.contains(event.relatedTarget as Node | null)) hide(element);
    };
    const onMove = () => position();
    document.addEventListener('pointerover', onPointerOver, true);
    document.addEventListener('pointerout', onPointerOut, true);
    document.addEventListener('click', onClick, true);
    document.addEventListener('focusin', onFocusIn, true);
    document.addEventListener('focusout', onFocusOut, true);
    window.addEventListener('scroll', onMove, true);
    window.addEventListener('resize', onMove);
    return () => {
      clearHoverTimer();
      document.removeEventListener('pointerover', onPointerOver, true);
      document.removeEventListener('pointerout', onPointerOut, true);
      document.removeEventListener('click', onClick, true);
      document.removeEventListener('focusin', onFocusIn, true);
      document.removeEventListener('focusout', onFocusOut, true);
      window.removeEventListener('scroll', onMove, true);
      window.removeEventListener('resize', onMove);
      hide();
    };
  }, [hide, position, show]);
  useEffect(() => {
    if (!active) return;
    const observer = new MutationObserver(() => {
      const text = active.element.dataset.tooltip?.trim() || active.element.getAttribute('aria-label')?.trim();
      if (text) setActive(previous => previous?.element === active.element ? { element: active.element, text } : previous);
    });
    observer.observe(active.element, { attributes: true, attributeFilter: ['data-tooltip', 'aria-label'] });
    return () => observer.disconnect();
  }, [active]);
  useEffect(() => {
    if (!active) return;
    const observer = new MutationObserver(() => {
      if (!active.element.isConnected) hide(active.element);
    });
    observer.observe(document.body, { childList: true, subtree: true });
    return () => observer.disconnect();
  }, [active, hide]);
  useLayoutEffect(() => { if (active) position(); }, [active, position]);
  if (!active) return null;
  return createPortal(<div ref={tooltip} id="sigma-ui-tooltip" role="tooltip" className="sigma-ui-tooltip">{active.text}</div>, document.body);
}

function SettingsGearIcon() {
  return <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><path d="M12.22 2h-.44a2 2 0 0 0-2 1.72l-.08.54a2 2 0 0 1-1 1.44l-.47.27a2 2 0 0 1-1.74 0l-.44-.22a2 2 0 0 0-2.72.73l-.22.38a2 2 0 0 0 .73 2.73l.44.25a2 2 0 0 1 1 1.73v.54a2 2 0 0 1-1 1.73l-.44.25a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.72.73l.44-.22a2 2 0 0 1 1.74 0l.47.27a2 2 0 0 1 1 1.44l.08.54a2 2 0 0 0 2 1.72h.44a2 2 0 0 0 2-1.72l.08-.54a2 2 0 0 1 1-1.44l.47-.27a2 2 0 0 1 1.74 0l.44.22a2 2 0 0 0 2.72-.73l.22-.38a2 2 0 0 0-.73-2.73l-.44-.25a2 2 0 0 1-1-1.73v-.54a2 2 0 0 1 1-1.73l.44-.25a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.72-.73l-.44.22a2 2 0 0 1-1.74 0l-.47-.27a2 2 0 0 1-1-1.44l-.08-.54A2 2 0 0 0 12.22 2z"/><circle cx="12" cy="12" r="3"/></svg>;
}

function TextViews({ path, scope, strategyId, source, projectTitle, contentClass, onSaved, mathematical, onSettings, settingsDisabled, settingsButtonRef, hideProjectHeading, hideProjectActions = false, hideEditAction = false, modeDisabled = false, combinedEditMode = false, editSignal = 0, markdownSlotId, onCombinedDraftChange, onEnterMode, onExitMode }: {
  path: string; scope: 'project' | 'strategy'; strategyId?: string; source: string; projectTitle?: string;
  contentClass: string; onSaved: (view: ProjectView) => void; mathematical: boolean; onSettings?: () => void; settingsDisabled?: boolean; settingsButtonRef?: React.RefObject<HTMLButtonElement | null>; hideProjectHeading?: boolean; hideProjectActions?: boolean; hideEditAction?: boolean; modeDisabled?: boolean; combinedEditMode?: boolean; editSignal?: number; markdownSlotId?: string; onCombinedDraftChange?: (draft: string) => void; onEnterMode?: () => boolean; onExitMode?: () => void;
}) {
  const [data, setData] = useState<TextRepresentations | null>(null);
  const preferenceKey = `sigma.markdownView:${path}:${scope}:${strategyId ?? ''}`;
  const [storedSelected, setSelected] = useState<TextDisplay>(() => window.localStorage.getItem(preferenceKey) === 'rendered' ? 'rendered' : 'plain');
  const selected: TextDisplay = storedSelected;
  const [rendering, setRendering] = useState(false);
  const [editing, setEditing] = useState(false);
  const [editingFromRendered, setEditingFromRendered] = useState(false);
  const [draft, setDraft] = useState('');
  const [busy, setBusy] = useState(false);
  const [exportOpen, setExportOpen] = useState(false);
  const exportTrigger = useRef<HTMLButtonElement>(null);
  const [error, setError] = useState('');
  const abort = useRef<AbortController | null>(null);
  const bodyTrigger = useRef<HTMLElement>(null);
  const editorForm = useRef<HTMLFormElement>(null);
  const editorArea = useRef<HTMLDivElement>(null);
  const [markdownPortalTarget, setMarkdownPortalTarget] = useState<HTMLElement | null>(null);
  const handledEditSignal = useRef(0);
  useLayoutEffect(() => {
    setMarkdownPortalTarget(markdownSlotId ? document.getElementById(markdownSlotId) : null);
  }, [markdownSlotId, modeDisabled, combinedEditMode, editSignal]);
  useEffect(() => {
    const controller = new AbortController();
    setData(null); setError(''); setEditing(false);
    const query = new URLSearchParams({ path, scope, ...(strategyId ? { strategy_id: strategyId } : {}) });
    fetch(`/api/projects/text?${query}`, { signal: controller.signal }).then(async response => {
      const result = await response.json();
      if (!response.ok) throw new Error(result.error ?? 'Could not read text views');
      return result as TextRepresentations;
    }).then(result => { setData(result); if (!result.markdown?.current) setSelected('plain'); setDraft(result.markdown?.current ? result.markdown.body : result.plain?.body ?? ''); })
      .catch(cause => { if (!controller.signal.aborted) setError(errorMessage(cause)); });
    return () => { controller.abort(); abort.current?.abort(); };
  }, [path, scope, strategyId, source]);
  const format: TextFormat = selected === 'plain' ? 'plain' : 'markdown';
  function chooseView(view: TextDisplay) {
    setSelected(view);
    window.localStorage.setItem(preferenceKey, view);
  }
  const version = data?.[format];
  const current = version?.current ?? false;
  function beginBodyEdit(fromRendered = false, alreadyInMode = false) {
    if (!version?.current || busy || (modeDisabled && !alreadyInMode) || (!alreadyInMode && onEnterMode && !onEnterMode())) return;
    setDraft(version.body); onCombinedDraftChange?.(version.body); setEditingFromRendered(fromRendered);
    if (fromRendered) chooseView('rendered');
    setEditing(true); setError('');
  }
  useEffect(() => {
    if (!editSignal || handledEditSignal.current === editSignal || !version?.current) return;
    handledEditSignal.current = editSignal;
    beginBodyEdit(selected === 'rendered', combinedEditMode);
  }, [editSignal, version?.current, combinedEditMode]);
  const wasCombinedEditMode = useRef(false);
  useEffect(() => {
    if (wasCombinedEditMode.current && !combinedEditMode) setEditing(false);
    wasCombinedEditMode.current = combinedEditMode;
  }, [combinedEditMode]);
  function cancelBodyEdit(restoreFocus = true) {
    setEditing(false);
    onExitMode?.();
    if (editingFromRendered) chooseView('rendered');
    if (restoreFocus) requestAnimationFrame(() => bodyTrigger.current?.focus());
  }
  async function convert(targetFormat: TextFormat = format) {
    if (!data || busy) return;
    const controller = new AbortController(); abort.current = controller; setBusy(true); setRendering(true); setError('');
    let finishProviderRequest = () => {};
    try {
      const settingsResponse = await fetch(`/api/projects/proposals/config?${new URLSearchParams({ path })}`, { signal: controller.signal });
      const settings = await settingsResponse.json();
      if (!settingsResponse.ok || !settings.available) { if (settingsResponse.ok) reportRequestFailure(settings.message ?? settings.error ?? 'Connect AI in the header, then retry.'); throw new Error(settings.message ?? settings.error ?? 'Connect AI in the header, then retry.'); }
      finishProviderRequest = beginProviderRequest('text-conversion');
      const response = await fetch('/api/projects/text/convert', { method: 'POST', headers: { 'Content-Type': 'application/json' }, signal: controller.signal,
        body: JSON.stringify({ path, scope, strategy_id: strategyId, target: targetFormat, expected_digest: data.source_digest, expected_binding: settings.binding }) });
      const next = await response.json();
      if (!response.ok) throw new Error(next.error ?? 'Conversion failed; source text was kept.');
      setData(next as TextRepresentations); setDraft(next[targetFormat]?.body ?? ''); chooseView(targetFormat === 'markdown' ? 'rendered' : 'plain');
    } catch (cause) { if (!controller.signal.aborted) { chooseView('plain'); setError(errorMessage(cause)); reportRequestFailure(errorMessage(cause)); } }
    finally { finishProviderRequest(); if (abort.current === controller) { abort.current = null; setBusy(false); setRendering(false); } }
  }
  async function save(event: FormEvent) {
    event.preventDefault(); if (!data || busy) return;
    setBusy(true); setError('');
    try {
      const next = await post<ProjectView>('text/source', { path, scope, strategy_id: strategyId, body: draft, format, expected_digest: data.source_digest });
      setEditing(false); onExitMode?.(); onSaved(next);
    } catch (cause) { setError(errorMessage(cause)); }
    finally { setBusy(false); }
  }
  const name = scope === 'project' ? 'research problem' : 'strategy approach';
  const plainRecovery = data?.source_format === 'markdown' && !data.plain?.current;
  const renderTooltip = rendering ? (plainRecovery ? 'Converting to Plain' : 'Converting to markdown') : selected === 'rendered' ? 'Show plain text' : plainRecovery ? 'Convert to Plain' : 'Convert to markdown';
  function closeExport() {
    setExportOpen(false);
    requestAnimationFrame(() => exportTrigger.current?.focus());
  }
  const markdownToggle = <button type="button" className={`sigma-render-toggle${markdownSlotId ? '' : ' workspace-icon-button'}${selected === 'rendered' || rendering ? ' sigma-render-active' : ''}${rendering ? ' sigma-render-pending' : ''}`}
      aria-label={selected === 'rendered' ? `Show plain ${name}` : plainRecovery ? `Convert ${name} to Plain` : `Render ${name} as Markdown`}
      aria-pressed={selected === 'rendered' || rendering} data-tooltip={renderTooltip}
      aria-hidden={combinedEditMode || undefined} style={combinedEditMode ? { visibility: 'hidden' } : undefined}
      disabled={editing || busy || combinedEditMode} onClick={() => {
        if (selected === 'rendered') { chooseView('plain'); setError(''); }
        else if (data?.markdown?.current) { chooseView('rendered'); setError(''); }
        else { void convert(plainRecovery ? 'plain' : 'markdown'); }
      }} title={renderTooltip}>{rendering ? <span aria-hidden="true">⌛</span> : <svg aria-hidden="true" className="markdown-logo" viewBox="20 25 160 78" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M20 92V30h20l20 25 20-25h20v62H80V59L60 84 40 59v33H20Z" fill="currentColor"/><path d="M120 30v38h-18l28 28 28-28h-18V30h-20Z" fill="currentColor"/></svg>}</button>;
  const viewActions = <>
    {!markdownSlotId && markdownToggle}

    {editing ? combinedEditMode ? null : <>
      <button type="submit" form={`text-form-${scope}-${strategyId ?? 'project'}`} className="text-view-link" title={`Save ${name}`} disabled={busy || !draft.trim()}>Save</button>
      <button type="button" className="text-view-link" title={`Cancel editing ${name}`} disabled={busy} onClick={() => cancelBodyEdit()}>Cancel</button>
      </> : data && version && !hideEditAction && <button type="button" className="text-view-link text-view-icon workspace-icon-button" aria-label={`Edit ${name}`} title={`Edit ${name}`} data-tooltip={`Edit ${name}`} disabled={modeDisabled} onClick={() => beginBodyEdit(selected === 'rendered')}><svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><path d="m15 5 4 4M4 20l4.5-1 11-11a2.83 2.83 0 0 0-4-4l-11 11L4 20Z"/></svg></button>}

    {!hideProjectActions && scope === 'project' && !editing && <button ref={exportTrigger} type="button" className="copper-button project-export-trigger workspace-icon-button" aria-label="Export project" title="Export project" data-tooltip="Export project" onClick={() => setExportOpen(true)}><svg aria-hidden="true" viewBox="0 0 20 20" fill="none"><path d="M10 2.5v9m0 0 3.5-3.5M10 11.5 6.5 8M3.5 13v3.5h13V13" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"/></svg></button>}
    {!hideProjectActions && onSettings && !editing && <button ref={settingsButtonRef} type="button" className="text-view-link text-view-icon workspace-icon-button" aria-label="Project settings" title="Project settings" data-tooltip="Project settings" disabled={settingsDisabled} onClick={onSettings}><SettingsGearIcon /></button>}
  </>;
  return <div ref={editorArea} className={`text-views${scope === 'project' ? ' project-text-views' : ''}${mathematical ? ' math-text-views' : ''}`}>
    {markdownPortalTarget && createPortal(markdownToggle, markdownPortalTarget)}
    {scope === 'project' && exportOpen && <ProjectExportDialog path={path} title={projectTitle ?? 'project'} onCancel={closeExport}/>}
    <div className="text-view-controls">
      {scope === 'project' && !hideProjectHeading && <h2 className="investigation-heading">Project</h2>}
      {scope === 'project' ? <div className="project-text-actions">{viewActions}</div> : viewActions}
    </div>
    {editing ? <form ref={editorForm} id={`text-form-${scope}-${strategyId ?? 'project'}`} className="text-view-editor" onSubmit={save}>
      <textarea id={`text-editor-${scope}-${strategyId ?? 'project'}`} autoFocus value={draft} maxLength={scope === 'project' ? 20000 : MAX_STRATEGY_APPROACH} rows={8} required disabled={busy} onChange={event => { setDraft(event.target.value); onCombinedDraftChange?.(event.target.value); }} onKeyDown={event => { if (event.key === 'Escape') { event.preventDefault(); cancelBodyEdit(); } }}/>
    </form> : current && version ? selected === 'rendered'
      ? <div className={`${contentClass} rendered-text`} aria-label={`Rendered ${name}`}><Suspense fallback={<p>Preparing preview…</p>}><RenderedMarkdown body={version.body}/></Suspense></div>
      : <p className={contentClass}>{version.body}</p>
      : !data ? <p className={contentClass}>{source}</p> : <div className="text-view-missing">
        <p>{version ? 'The previous conversion is out of date with the current source.' : `No ${format === 'markdown' ? 'Markdown' : 'Plain'} representation is stored yet.`}</p>
        {mathematical && plainRecovery && format === 'plain' && <button type="button" className="text-view-link" disabled={busy || modeDisabled} onClick={() => void convert('plain')}>Convert to Plain</button>}
        {version && <details><summary>Inspect previous {format === 'markdown' ? 'Markdown' : 'Plain'} text</summary><pre>{version.body}</pre></details>}
      </div>}
    {busy && !editing && <span className="sr-only" role="status">Converting to Markdown…</span>}
    {error && <p role="alert" className="error">{error}</p>}
  </div>;
}

function ProjectPaneTitle({ view, onSaved, disabled, modeDisabled, descriptionDraft, onEnterMode, onExitMode, onEditDescription }: { view: ProjectView; onSaved: (view: ProjectView) => void; disabled: boolean; modeDisabled: boolean; descriptionDraft: string; onEnterMode: () => boolean; onExitMode: () => void; onEditDescription: () => void }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(view.project.title);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const trigger = useRef<HTMLButtonElement>(null);
  const input = useRef<HTMLInputElement>(null);
  const form = useRef<HTMLFormElement>(null);
  useEffect(() => { if (!editing) setDraft(view.project.title); }, [view.project.title, editing]);
  useEffect(() => { if (editing) { input.current?.focus(); input.current?.select(); } }, [editing]);
  function cancel(restoreFocus = true) { setDraft(view.project.title); setError(''); setEditing(false); onExitMode(); if (restoreFocus) requestAnimationFrame(() => trigger.current?.focus()); }
  async function save(event: FormEvent) {
    event.preventDefault();
    if (busy) return;
    if (!draft.trim()) { setError('Enter a project title.'); input.current?.focus(); return; }
    setBusy(true); setError('');
    try {
      const current = settingsOf(view);
      const next = await post<ProjectView>('update', { path: view.path, ...current, title: draft, problem: descriptionDraft, expected: current });
      setEditing(false); onExitMode(); onSaved(next); requestAnimationFrame(() => trigger.current?.focus());
    } catch (cause) { setError(errorMessage(cause)); reportRequestFailure(errorMessage(cause)); }
    finally { setBusy(false); }
  }
  return <div className={`project-pane-title-line${editing ? ' is-renaming' : ''}`}>
    {editing ? <form ref={form} className="project-title-edit-form" onSubmit={save}>
      <label className="sr-only" htmlFor="project-pane-title-input">Project title</label>
      <input ref={input} id="project-pane-title-input" aria-label="Project title" value={draft} size={Math.max(8, Math.min(50, draft.length + 1))} maxLength={200} required disabled={busy} onChange={event => { setDraft(event.target.value); setError(''); }} onKeyDown={event => { if (event.key === 'Escape' && !busy) { event.preventDefault(); cancel(); } }}/>
      <button type="submit" className="text-view-link" title="Save project title" disabled={busy}>Save</button><button type="button" className="text-view-link" title="Cancel editing the project title" disabled={busy} onClick={() => cancel()}>Cancel</button>
      {error && <p role="alert" className="project-title-error">{error}</p>}
    </form> : <><h3 className="current-project">{view.project.title}</h3>
      <span id="project-markdown-slot" className="project-markdown-slot"/><button type="button" ref={trigger} className="text-view-link text-view-icon workspace-icon-button project-title-pencil" aria-label={`Edit project title and description: ${view.project.title}`} data-tooltip-disabled disabled={disabled || modeDisabled} onClick={() => { if (onEnterMode()) { setEditing(true); onEditDescription(); } }}>
        <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><path d="m15 5 4 4M4 20l4.5-1 11-11a2.83 2.83 0 0 0-4-4l-11 11L4 20Z"/></svg>
      </button> </>}
  </div>;
}

function Header({ goHome, close, projectTitle, projectType, projectDifficulty, projectView, onProjectUpdated, projectArtwork = false, connectionDisabled = false }: { goHome: (event: MouseEvent<HTMLAnchorElement>) => void;
  close?: { action: () => void; busy: boolean }; projectTitle?: string; projectType?: ResearchMode; projectDifficulty?: ProjectDifficulty | null; projectView?: ProjectView; onProjectUpdated?: (view: ProjectView) => void; projectArtwork?: boolean; connectionDisabled?: boolean }) {
  const cloud = useCloudIdentity();
  return <header className={projectArtwork ? 'site-header project-art-header' : 'site-header'}>
    <div className="brand-block">
      <a href="/" className={projectArtwork ? 'brand project-header-art' : 'brand'} onClick={goHome} aria-label="SIGMA home"><img src={projectArtwork ? '/sigma-project-header.png' : '/sigma-workspace-logo.png'} alt="SIGMA" /></a>
      {projectArtwork && close && <div className="project-back-row project-art-back-row">
        <button className="project-back" type="button" onClick={close.action} disabled={close.busy} aria-label="Back to home" data-tooltip-disabled><svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="m14 5-7 7 7 7M7 12h13"/></svg></button>
        <button className="project-back-label" type="button" onClick={close.action} disabled={close.busy} aria-label="Back to home caption" data-tooltip-disabled>Back to home</button>
      </div>}
      {projectArtwork ? close && <div className="project-title-line">{projectTitle && <div className="project-header-title-row">{projectType && <ResearchTypeIcon type={projectType}/>}<span className="project-header-title" title={projectTitle}>{projectTitle}</span></div>}</div>
        : <p className="expansion">Strategy Investigation, Generation, Measurement &amp; Assessment</p>}
    </div>
    <div className="header-controls">
    {!close && <span className="local">● Local workspace</span>}
    {close && projectView && onProjectUpdated ? <>
      <ProjectHeaderControls view={projectView} onSaved={onProjectUpdated} disabled={connectionDisabled || close.busy}/>
      <GoogleIdentityPill compact/>
      <ConnectionStatus disabled={connectionDisabled} projectHeader cloudFunding={cloudFundingFor(cloud)}/>
    </> : <ConnectionStatus disabled={connectionDisabled}/>}
    </div>
  </header>;
}

function WorkspaceIcon({ name }: { name: string }) {
  const paths: Record<string, string> = {
    Strategies: 'M3 3h6v6H3z M15 3h6v6h-6z M3 15h6v6H3z M15 15h6v6h-6z',
    Renders: 'M5 3h10l4 4v14H5z M14 3v5h5 M8 12h8 M8 16h6',
    Analysis: 'M4 20h17 M6 16v-5 M11 16V4 M16 16V8 M21 16v-3',
    References: 'M12 5c-3-2-6-2-10-1v16c4-1 7-1 10 1 3-2 6-2 10-1V4c-4-1-7-1-10 1v16',
    Notes: 'M5 3h14v18H5z M8 8h8 M8 12h8 M8 16h5',
    Settings: 'M12 2.5v2.3 M12 19.2v2.3 M2.5 12h2.3 M19.2 12h2.3 M5.28 5.28l1.63 1.63 M17.09 17.09l1.63 1.63 M5.28 18.72l1.63-1.63 M17.09 6.91l1.63-1.63 M16.5 12a4.5 4.5 0 1 1-9 0 4.5 4.5 0 0 1 9 0',
  };
  return <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor"
    strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={paths[name]}/></svg>;
}

function focusWorkspace(id: string) {
  const target = document.getElementById(id) ?? document.getElementById('workspace-content');
  target?.focus(); target?.scrollIntoView({ block: 'start' });
}

function WorkspaceFrame({ children, goHome, close, projectTitle, projectType, projectView, onProjectUpdated, connectionDisabled = false }: {
  children: React.ReactNode; goHome: (event: MouseEvent<HTMLAnchorElement>) => void;
  close?: { action: () => void; busy: boolean }; projectTitle?: string; projectType?: ResearchMode; projectView?: ProjectView; onProjectUpdated?: (view: ProjectView) => void; connectionDisabled?: boolean;
}) {
  const [collapsed, setCollapsed] = useState(() => window.localStorage.getItem('sigma.sidebarCollapsed') === 'true');
  function toggleSidebar() {
    setCollapsed(value => {
      window.localStorage.setItem('sigma.sidebarCollapsed', String(!value));
      return !value;
    });
  }
  return <>
    <a className="workspace-skip" href="#workspace-content" onClick={event => {
      event.preventDefault(); focusWorkspace('workspace-content');
    }}>Skip to project content</a>
    <Header goHome={goHome} close={close} projectTitle={projectTitle} projectType={projectType} projectView={projectView} onProjectUpdated={onProjectUpdated} projectArtwork connectionDisabled={connectionDisabled}/>
    <div className={`workspace-layout${!ENABLE_WORKSPACE_SIDEBAR ? ' sidebar-disabled' : collapsed ? ' nav-collapsed' : ''}`}>
      {ENABLE_WORKSPACE_SIDEBAR && <nav className="workspace-nav" aria-label="Project navigation">
        <button className="nav-collapse" type="button" aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'} aria-expanded={!collapsed} title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'} data-tooltip={collapsed ? 'Expand sidebar' : 'Collapse sidebar'} onClick={toggleSidebar}><svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={collapsed ? 'm9 6 6 6-6 6' : 'm15 6-6 6 6 6'}/></svg></button>
        <a href="#project-pane-heading" aria-label="Project" title={collapsed ? 'Project' : undefined} onClick={event => { event.preventDefault(); focusWorkspace('project-pane-heading'); }}><WorkspaceIcon name="Settings"/><span>Project</span></a>
        <a href="#sessions-heading" aria-label="Sessions" title={collapsed ? 'Sessions' : undefined} onClick={event => { event.preventDefault(); focusWorkspace('sessions-heading'); }}><WorkspaceIcon name="Analysis"/><span>Sessions</span></a>
        <a href="#pool-heading" aria-current="page" aria-label="Strategies" title={collapsed ? 'Strategies' : undefined} onClick={event => {
          event.preventDefault(); focusWorkspace('pool-heading');
        }}><WorkspaceIcon name="Strategies"/><span>Strategies</span></a>
        {['Renders', 'Analysis', 'References', 'Notes', 'Settings'].map(name =>
          <button key={name} disabled title={collapsed ? `${name} · later` : 'Not available yet'} aria-label={name} aria-describedby="workspace-nav-help">
            <WorkspaceIcon name={name}/><span>{name}</span><small>Later</small>
          </button>)}
        <p id="workspace-nav-help">Other destinations are not available yet.</p>
      </nav>}
      <div id="workspace-content" className="workspace-content" tabIndex={-1}>{children}</div>
    </div>
  </>;
}

type Destination = { root: string; path: string | null; exists: boolean };

function ProjectEntryDialog({ initialPath, onOpen, onCancel }: {
  initialPath: string; onOpen: (view: ProjectView) => void; onCancel: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const first = useRef<HTMLInputElement>(null);
  const submitting = useRef(false);
  const [path, setPath] = useState(initialPath);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  useEffect(() => { dialog.current?.showModal(); first.current?.focus(); }, []);
  async function save(event: FormEvent) {
    event.preventDefault(); if (submitting.current) return; submitting.current = true; setBusy(true); setError('');
    try { onOpen(await post<ProjectView>('open', { path })); }
    catch (error) { setError(errorMessage(error)); }
    finally { submitting.current = false; setBusy(false); }
  }
  return <dialog ref={dialog} className="project-entry-dialog" aria-labelledby="project-entry-heading" onCancel={event => { event.preventDefault(); if (!busy) onCancel(); }}>
    <header className="entry-dialog-header"><h2 id="project-entry-heading">Open Project</h2><button type="button" className="entry-cancel" disabled={busy} onClick={onCancel}>Cancel</button></header><p className="entry-help">Choose an existing local project by its directory path.</p>
    <form onSubmit={save}><fieldset disabled={busy}><label htmlFor="open-project-path">Project directory</label><input ref={first} id="open-project-path" required value={path} onChange={event => setPath(event.target.value)} aria-describedby="project-path-help"/><p id="project-path-help" className="entry-hint">Try <code>projects/rh.sigma</code>, or an absolute path such as <code>/Users/you/projects/question.sigma</code>. Paths refer to this local server.</p>
    {error && <p className="error" role="alert">{error}</p>}<div className="entry-dialog-actions"><button type="submit">{busy ? 'Opening…' : 'Open Project'}</button></div></fieldset></form>
  </dialog>;
}

type Settings = { title: string; problem: string; investigation_type: ResearchMode; ai_model: string; reasoning_effort: string; difficulty: ProjectDifficulty | null };
type CatalogChoice = { id: string; label: string; description: string; efforts: string[]; relative_cost: '$' | '$$' | '$$$'; availability: 'available' | 'unavailable' | 'unverified' };
const thinkingLabels: Record<string, string> = { low: 'Low', medium: 'Medium', high: 'High', xhigh: 'Extra high' };
const settingsOf = (view: ProjectView): Settings => ({ title: view.project.title, problem: view.project.problem, investigation_type: view.project.investigation_type, ai_model: view.project.ai_model, reasoning_effort: view.project.reasoning_effort, difficulty: view.project.difficulty });

function ProjectHeaderControls({ view, onSaved, disabled }: { view: ProjectView; onSaved: (view: ProjectView) => void; disabled: boolean }) {
  const ai = useAI();
  const [models, setModels] = useState<CatalogChoice[]>([]);
  const [catalogReady, setCatalogReady] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const [pendingModel, setPendingModel] = useState<CatalogChoice | null>(null);
  const [confirmationPosition, setConfirmationPosition] = useState<{ left: number; top: number } | null>(null);
  const saving = useRef(false);
  const modelButton = useRef<HTMLButtonElement>(null);
  const confirmButton = useRef<HTMLButtonElement>(null);
  const confirmationPopover = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (pendingModel) {
      const place = () => {
        const anchor = modelButton.current?.getBoundingClientRect();
        const popover = confirmationPopover.current?.getBoundingClientRect();
        if (!anchor) return;
        const width = popover?.width ?? Math.min(320, window.innerWidth - 16);
        const height = popover?.height ?? 110;
        const left = Math.max(8, Math.min(anchor.left, window.innerWidth - width - 8));
        const below = anchor.bottom + height + 8 <= window.innerHeight - 8;
        setConfirmationPosition({ left, top: below ? anchor.bottom + 8 : Math.max(8, anchor.top - height - 8) });
      };
      const frame = requestAnimationFrame(() => {
        place();
        confirmButton.current?.focus();
      });
      const escape = (event: KeyboardEvent) => {
        if (event.key === 'Escape') {
          event.preventDefault();
          setPendingModel(null);
        }
      };
      window.addEventListener('resize', place);
      window.addEventListener('scroll', place, true);
      document.addEventListener('keydown', escape, true);
      return () => {
        cancelAnimationFrame(frame);
        window.removeEventListener('resize', place);
        window.removeEventListener('scroll', place, true);
        document.removeEventListener('keydown', escape, true);
      };
    } else {
      setConfirmationPosition(null);
      modelButton.current?.focus();
    }
  }, [pendingModel]);

  useEffect(() => {
    const controller = new AbortController();
    setCatalogReady(false);
    fetch('/api/ai/models', { signal: controller.signal }).then(async response => {
      if (!response.ok) throw new Error('Model availability could not be checked.');
      return response.json();
    }).then(data => {
      if (!controller.signal.aborted) setModels(Array.isArray(data.models) ? data.models : []);
    }).catch(() => {
      if (!controller.signal.aborted) setMessage('Model availability could not be verified. Saved settings are unchanged.');
    }).finally(() => { if (!controller.signal.aborted) setCatalogReady(true); });
    return () => controller.abort();
  }, [ai.info?.mode, ai.info?.active_account, ai.info?.status]);

  const current = models.find(model => model.id === view.project.ai_model);
  const costOrder: Record<CatalogChoice['relative_cost'], number> = { '$': 1, '$$': 2, '$$$': 3 };
  const available = models.filter(model => model.availability === 'available').sort((a, b) => costOrder[b.relative_cost] - costOrder[a.relative_cost] || a.label.localeCompare(b.label));
  const currentAvailableIndex = available.findIndex(model => model.id === view.project.ai_model);
  const nextModel = available.length > 1
    ? available[(currentAvailableIndex + 1 + available.length) % available.length]
    : available.length === 1 && currentAvailableIndex < 0 ? available[0] : undefined;
  const efforts = current?.availability === 'available' ? current.efforts : [];
  const currentEffortIndex = efforts.indexOf(view.project.reasoning_effort);
  const nextEffort = efforts.length > 1
    ? efforts[(currentEffortIndex + 1 + efforts.length) % efforts.length]
    : undefined;
  const effortOrder = ['low', 'medium', 'high', 'xhigh'];
  const reconciledEffort = (model: CatalogChoice | undefined) => {
    if (!model?.efforts.length) return undefined;
    if (model.efforts.includes(view.project.reasoning_effort)) return view.project.reasoning_effort;
    const oldIndex = effortOrder.indexOf(view.project.reasoning_effort);
    return [...model.efforts].sort((a, b) => {
      const distance = Math.abs(effortOrder.indexOf(a) - oldIndex) - Math.abs(effortOrder.indexOf(b) - oldIndex);
      return distance || effortOrder.indexOf(a) - effortOrder.indexOf(b);
    })[0];
  };
  const nextModelEffort = reconciledEffort(nextModel);
  const effortWillChange = Boolean(nextModel && nextModelEffort !== view.project.reasoning_effort);
  const nextModelCostsMore = Boolean(current && nextModel && costOrder[nextModel.relative_cost] > costOrder[current.relative_cost]);
  const difficultyOrder: ProjectDifficulty[] = ['easy', 'medium', 'hard'];
  const currentDifficultyIndex = view.project.difficulty ? difficultyOrder.indexOf(view.project.difficulty) : -1;
  const nextDifficulty = difficultyOrder[(currentDifficultyIndex + 1) % difficultyOrder.length];
  const difficultyText = view.project.difficulty ? difficultyLabels[view.project.difficulty].toLowerCase() : 'not set';
  const costHelpId = `project-model-cost-help-${view.project.id}`;

  async function update(changes: Partial<Settings>) {
    if (saving.current || disabled || busy) return;
    saving.current = true; setBusy(true); setMessage('');
    const expected = settingsOf(view);
    try {
      const saved = await post<ProjectView>('update', {
        path: view.path, ...expected, ...changes, expected,
      });
      onSaved(saved);
    } catch (error) {
      setMessage(errorMessage(error));
    } finally {
      saving.current = false; setBusy(false);
    }
  }

  const modelLabel = current ? `${current.label.split(' · ')[0]} ${current.relative_cost}` : view.project.ai_model;
  const modelDisabled = !catalogReady || busy || disabled || !nextModel || !nextModelEffort;
  const thinkingDisabled = !catalogReady || busy || disabled || !nextEffort;
  const statusMessage = message || !catalogReady
    ? message || 'Checking model availability…'
    : current?.availability !== 'available'
      ? 'Saved model access is not verified; settings were preserved.'
      : '';
  const nextEffortNotice = effortWillChange
    ? ` Switching to ${nextModel?.label.split(' · ')[0]} will also change Thinking from ${thinkingLabels[view.project.reasoning_effort] ?? view.project.reasoning_effort} to ${thinkingLabels[nextModelEffort!]}.`
    : '';
  const visibleEffortNotice = effortWillChange ? `Next model uses ${thinkingLabels[nextModelEffort!]}.` : '';
  const pendingModelName = pendingModel?.label.split(' · ')[0] ?? 'this model';
  function requestModelChange() {
    if (!nextModel || !nextModelEffort) return;
    if (nextModelCostsMore) setPendingModel(nextModel);
    else void update({ ai_model: nextModel.id, reasoning_effort: nextModelEffort });
  }
  function confirmModelChange() {
    if (!pendingModel) return;
    const confirmed = pendingModel;
    setPendingModel(null);
    const effort = reconciledEffort(confirmed);
    if (effort) void update({ ai_model: confirmed.id, reasoning_effort: effort });
  }
  function cycleDifficulty() {
    void update({ difficulty: nextDifficulty });
  }
  return <div className="project-header-controls" aria-label="Project model, thinking, and difficulty controls">
    <button type="button" className={`project-control-pill project-difficulty-badge difficulty-${view.project.difficulty ?? 'unset'}`} aria-label={`Project difficulty ${view.project.difficulty ? difficultyLabels[view.project.difficulty] : 'not set'}`} title={`This project is considered ${difficultyText}. Click to cycle through easy, medium, and hard.`} data-tooltip={`This project is considered ${difficultyText}. Click to cycle through easy, medium, and hard.`} disabled={disabled || busy || !!pendingModel} onClick={cycleDifficulty}>Difficulty · {view.project.difficulty ? difficultyLabels[view.project.difficulty] : 'Not set'}</button>
    <button ref={modelButton} type="button" className="project-control-pill project-model-pill" aria-label={`Model ${modelLabel}. Relative published API token cost ${current?.relative_cost ?? 'unknown'}.${nextEffortNotice}`} aria-describedby={costHelpId} title={`The selected model is ${modelLabel}. Its relative published API token cost is ${current?.relative_cost ?? 'unknown'}. Click to cycle through available models.${nextEffortNotice}`} data-tooltip={`The selected model is ${modelLabel}. Its relative published API token cost is ${current?.relative_cost ?? 'unknown'}. Click to cycle through available models.${nextEffortNotice}`} disabled={modelDisabled || !!pendingModel} onClick={requestModelChange}><span>Model · </span>{modelLabel}</button>
    <button type="button" className="project-control-pill project-thinking-pill" aria-label={`Thinking level ${thinkingLabels[view.project.reasoning_effort] ?? view.project.reasoning_effort}`} title={`The thinking level is set to ${(thinkingLabels[view.project.reasoning_effort] ?? view.project.reasoning_effort).toLowerCase()}. Click to cycle through levels supported by this model.`} data-tooltip={`The thinking level is set to ${(thinkingLabels[view.project.reasoning_effort] ?? view.project.reasoning_effort).toLowerCase()}. Click to cycle through levels supported by this model.`} disabled={thinkingDisabled || !!pendingModel} onClick={() => nextEffort && void update({ ai_model: view.project.ai_model, reasoning_effort: nextEffort })}>Thinking · {thinkingLabels[view.project.reasoning_effort] ?? view.project.reasoning_effort}</button>
    <span id={costHelpId} className="sr-only">Dollar signs show relative published API token price tiers. They are not actual research session charges.</span>
    {visibleEffortNotice && <span className="project-controls-message" role="status">{visibleEffortNotice}</span>}
    {statusMessage && <span className="project-controls-message" role="status">{statusMessage}</span>}
    {pendingModel && createPortal(<div ref={confirmationPopover} className="project-model-confirm-popover" role="group" aria-label={`Confirm switch to ${pendingModelName}`} style={confirmationPosition ? { left: confirmationPosition.left, top: confirmationPosition.top } : { left: -10000, top: -10000 }}>
      <p><strong>Switch to {pendingModelName}?</strong> {pendingModelName} has a higher relative published API token cost tier ({pendingModel.relative_cost} versus {current?.relative_cost}). Continue to save this model?</p>
      <div className="project-model-confirm-actions session-remove-confirm-actions"><button ref={confirmButton} type="button" onClick={confirmModelChange}>Confirm</button><button type="button" onClick={() => setPendingModel(null)}>Cancel</button></div>
    </div>, document.body)}
  </div>;
}

function ResearchTypeIcon({ type }: { type: ResearchMode }) {
  const common = { fill: 'none', stroke: 'currentColor', strokeWidth: 1.6, strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const };
  return <svg className={`research-type-icon research-type-icon-${type}`} viewBox="0 0 24 24" aria-hidden="true">
    {type === 'mathematical' ? <text x="12" y="18" textAnchor="middle" fill="currentColor" fontFamily="Georgia,serif" fontSize="21">Σ</text>
      : type === 'religion' ? <path {...common} d="M12 3v18M7 8h10M9 21h6M12 3 9.5 6M12 3l2.5 3"/>
        : type === 'law' ? <path {...common} d="M12 4v15M7 20h10M5 7h14M12 7 7 15m0 0H3l2-4 2 4Zm5-8 5 8m0 0h-4l2-4 2 4Z"/>
          : type === 'chemistry' ? <path {...common} d="M9 3h6M10 3v6l-5 9a2 2 0 0 0 2 3h10a2 2 0 0 0 2-3l-5-9V3M7 16h10M9 13h6"/>
            : type === 'biology' ? <g {...common}>
              <path d="M5 2C5 7 19 7 19 12s-14 5-14 10"/>
              <path d="M19 2c0 5-14 5-14 10s14 5 14 10"/>
              <path d="M7 4.5h10M6 12h12M7 19.5h10"/>
            </g>
              : type === 'computer_science' ? <path {...common} d="m8 7-5 5 5 5m8-10 5 5-5 5m-1-14-6 18"/>
                : type === 'economics' ? <text x="12" y="19" textAnchor="middle" fill="currentColor" fontFamily="Georgia,serif" fontSize="20">$</text>
                  : type === 'engineering' ? <><circle {...common} cx="12" cy="12" r="6.7"/><circle {...common} cx="12" cy="12" r="3.1"/><path {...common} d="M12 1.8v3.5m0 13.4v3.5M1.8 12h3.5m13.4 0h3.5M4.8 4.8l2.5 2.5m9.4 9.4 2.5 2.5m0-14.4-2.5 2.5m-9.4 9.4-2.5 2.5"/></>
            : type === 'physics' ? <><ellipse {...common} cx="12" cy="12" rx="9" ry="3.8"/><ellipse {...common} cx="12" cy="12" rx="9" ry="3.8" transform="rotate(60 12 12)"/><ellipse {...common} cx="12" cy="12" rx="9" ry="3.8" transform="rotate(120 12 12)"/><circle cx="12" cy="12" r="1.5" fill="currentColor"/></>
              : type === 'military' ? <><path {...common} d="M12 3 20 6v5c0 5-3.3 8-8 10-4.7-2-8-5-8-10V6l8-3Z"/><path {...common} d="m8 13 4-4 4 4M12 9v6"/></>
                : type === 'philosophy' ? <><path {...common} d="M4 6c3-1 5 0 8 2 3-2 5-3 8-2v12c-3-1-5 0-8 2-3-2-5-3-8-2V6Z"/><path {...common} d="M12 8v12M8 10h1M15 10h1"/></>
                  : <><circle {...common} cx="12" cy="12" r="8.5"/><circle cx="7" cy="8" r="1.5" fill="currentColor"/><circle cx="16.5" cy="7" r="1.5" fill="currentColor"/><circle cx="9" cy="16.5" r="1.5" fill="currentColor"/><path {...common} d="m8.5 9 6.5-1m-6 7 1-5m1 6 4-7"/></>}
  </svg>;
}

function ResearchTypePicker({ value, onChange, fieldLabel = 'Research type' }: { value: ResearchMode; onChange: (value: ResearchMode) => void; fieldLabel?: string }) {
  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(Math.max(0, researchTypes.findIndex(type => type.value === value)));
  const root = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const options = useRef<Array<HTMLButtonElement | null>>([]);
  const selectedIndex = Math.max(0, researchTypes.findIndex(type => type.value === value));
  useEffect(() => {
    if (open) options.current[activeIndex]?.focus();
  }, [activeIndex, open]);
  useEffect(() => {
    if (!open) return;
    const closeOutside = (event: PointerEvent) => {
      if (!root.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener('pointerdown', closeOutside);
    return () => document.removeEventListener('pointerdown', closeOutside);
  }, [open]);
  function choose(next: ResearchMode) {
    onChange(next);
    setOpen(false);
    requestAnimationFrame(() => trigger.current?.focus());
  }
  function move(index: number) {
    setActiveIndex((index + researchTypes.length) % researchTypes.length);
  }
  const selected = researchTypes[selectedIndex];
  return <div className="research-type-picker" ref={root}>
    <button ref={trigger} id="project-mode" type="button" role="combobox" aria-labelledby="project-mode-label project-mode-value" aria-haspopup="listbox" aria-expanded={open} aria-controls="project-mode-options" onClick={() => { setActiveIndex(selectedIndex); setOpen(current => !current); }} onKeyDown={event => {
      if (event.key === 'ArrowDown') { event.preventDefault(); setActiveIndex(selectedIndex); setOpen(true); }
      else if (event.key === 'ArrowUp') { event.preventDefault(); setActiveIndex(researchTypes.length - 1); setOpen(true); }
    }}>
      <ResearchTypeIcon type={selected.value}/><span id="project-mode-value">{selected.label}</span><svg className="research-type-chevron" viewBox="0 0 12 12" aria-hidden="true"><path d="m2 4 4 4 4-4"/></svg>
    </button>
    {open && <div className="research-type-options" id="project-mode-options" role="listbox" aria-label={fieldLabel}>
      {researchTypes.map((type, index) => <button ref={element => { options.current[index] = element; }} id={`project-mode-option-${type.value}`} key={type.value} type="button" role="option" aria-selected={value === type.value} tabIndex={activeIndex === index ? 0 : -1} onFocus={() => setActiveIndex(index)} onClick={() => choose(type.value)} onKeyDown={event => {
        if (event.key === 'ArrowDown') { event.preventDefault(); move(index + 1); }
        else if (event.key === 'ArrowUp') { event.preventDefault(); move(index - 1); }
        else if (event.key === 'Home') { event.preventDefault(); move(0); }
        else if (event.key === 'End') { event.preventDefault(); move(researchTypes.length - 1); }
        else if (event.key === 'Escape') { event.preventDefault(); setOpen(false); trigger.current?.focus(); }
        else if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); choose(type.value); }
      }}><ResearchTypeIcon type={type.value}/><span>{type.label}</span></button>)}
    </div>}
  </div>;
}

function ProjectSettingsDialog({ initial, onSaved, onCancel }: { initial?: ProjectView; onSaved: (view: ProjectView) => void; onCancel: () => void }) {
  useDocumentScrollLock();
  const ai = useAI();
  const cloud = useCloudIdentity();
  const dialog = useRef<HTMLDialogElement>(null);
  const first = useRef<HTMLInputElement>(null);
  const submitting = useRef(false);
  const [values, setValues] = useState<Settings>(() => initial ? settingsOf(initial) : { title: '', problem: '', investigation_type: 'default', ai_model: '', reasoning_effort: 'high', difficulty: 'medium' });
  const [catalog, setCatalog] = useState<CatalogChoice[]>([]);
  const [catalogMessage, setCatalogMessage] = useState('Checking model availability…');
  const [destination, setDestination] = useState<Destination | null>(null);
  const [locationError, setLocationError] = useState('');
  const [previewBusy, setPreviewBusy] = useState(!initial);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [activeTab, setActiveTab] = useState<'main' | 'limits'>('main');
  const [limitDraft, setLimitDraft] = useState<ResearchLimitsDraft>(() => draftLimits({ research_rounds: 3, model_calls: 30, session_duration_minutes: 60, output_tokens_per_call: 12000, maximum_estimated_cost_usd: null }));
  const [limitsLoaded, setLimitsLoaded] = useState(!initial);
  const limitValidation = validateLimitDraft(limitDraft);
  useEffect(() => { dialog.current?.showModal(); first.current?.focus(); }, []);
  useEffect(() => {
    if (!initial) return;
    const controller = new AbortController();
    fetch(`/api/projects/research-limits?${new URLSearchParams({ path: initial.path })}`, { signal: controller.signal }).then(async response => {
      const data = await response.json(); if (!response.ok) throw new Error(data.error ?? 'Research limits could not be read');
      setLimitDraft(draftLimits(data)); setLimitsLoaded(true);
    }).catch(cause => { if (!controller.signal.aborted) setError(errorMessage(cause)); });
    return () => controller.abort();
  }, [initial?.path]);
  useEffect(() => {
    const controller = new AbortController();
    fetch('/api/ai/models', { signal: controller.signal }).then(async response => { if (!response.ok) throw new Error('Model catalog unavailable. Check the local server; existing settings are retained.'); return response.json(); }).then(data => {
      setCatalog(data.models); setCatalogMessage(data.message);
      if (!initial) setValues(previous => previous.ai_model ? previous : { ...previous, ai_model: data.default_model, reasoning_effort: data.default_effort });
    }).catch(error => { if (!controller.signal.aborted) setCatalogMessage(errorMessage(error)); });
    return () => controller.abort();
  }, [ai.info?.mode, ai.info?.active_account]);
  useEffect(() => {
    if (initial) return;
    const controller = new AbortController(); setPreviewBusy(true); setDestination(null); setLocationError('');
    const timer = window.setTimeout(async () => {
      try {
        const response = await fetch(`/api/projects/destination?${new URLSearchParams({ title: values.title })}`, { signal: controller.signal });
        const data = await response.json(); if (!response.ok) throw new Error(data.error ?? 'Project location unavailable');
        setDestination(data);
      } catch (error) { if (!controller.signal.aborted) setLocationError(errorMessage(error)); }
      finally { if (!controller.signal.aborted) setPreviewBusy(false); }
    }, values.title ? 180 : 0);
    return () => { clearTimeout(timer); controller.abort(); };
  }, [values.title]);
  function change<K extends keyof Settings,>(key: K, value: Settings[K]) { setValues(previous => ({ ...previous, [key]: value })); }
  const selected = catalog.find(model => model.id === values.ai_model);
  const costOrder: Record<CatalogChoice['relative_cost'], number> = { '$': 1, '$$': 2, '$$$': 3 };
  const orderedCatalog = [...catalog].sort((a, b) => costOrder[a.relative_cost] - costOrder[b.relative_cost] || a.label.localeCompare(b.label));
  const samePair = !!initial && values.ai_model === initial.project.ai_model && values.reasoning_effort === initial.project.reasoning_effort;
  const compatible = selected?.efforts.includes(values.reasoning_effort) || samePair;
  const pairError = selected && !selected.efforts.includes(values.reasoning_effort) && !samePair ? 'This model does not support the selected Thinking level. Choose a supported level explicitly.' : '';
  async function save(event: FormEvent) {
    event.preventDefault(); if (submitting.current || !compatible || (initial && !limitValidation.value) || (!initial && (!destination?.path || destination.exists || previewBusy))) return;
    submitting.current = true; setBusy(true); setError('');
    try {
      const next = await post<ProjectView>(initial ? 'update' : 'create', initial ? { path: initial.path, ...values, expected: settingsOf(initial) } : values);
      if (initial) {
        const response = await fetch('/api/projects/research-limits', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ path: initial.path, ...limitValidation.value }) });
        const result = await response.json(); if (!response.ok) throw new Error(result.error ?? 'Research limits were not saved');
        setLimitDraft(draftLimits(result));
      }
      onSaved(next);
    }
    catch (error) { setError(errorMessage(error)); }
    finally { submitting.current = false; setBusy(false); }
  }
  return <dialog ref={dialog} className={`project-settings-dialog ${initial ? 'edit-project-dialog' : 'new-project-dialog'}`} aria-labelledby="project-settings-heading" aria-describedby="project-settings-help" onCancel={event => { event.preventDefault(); if (!submitting.current) onCancel(); }}>
    <form onSubmit={save}>
      <header className="settings-header"><h2 id="project-settings-heading">{initial ? 'Settings' : 'New Project'}</h2><div className="settings-actions">{initial ? <><button type="submit" disabled={busy || !values.ai_model || !compatible || !!pairError || !limitsLoaded || !limitValidation.value}>{busy ? 'Saving…' : 'Save'}</button><button className="settings-cancel" type="button" disabled={busy} onClick={() => { if (!submitting.current) onCancel(); }}>Cancel</button></> : <><button type="submit" disabled={busy || !values.ai_model || !compatible || !!pairError || !values.problem.trim() || previewBusy || !destination?.path || destination.exists}>{busy ? 'Creating…' : 'Create'}</button><button className="settings-cancel" type="button" disabled={busy} onClick={() => { if (!submitting.current) onCancel(); }}>Cancel</button></>}</div></header>
      {initial && <div role="tablist" aria-label="Project settings" className="settings-tabs" onKeyDown={event => { if (['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) { event.preventDefault(); const next = event.key === 'Home' ? 'main' : event.key === 'End' ? 'limits' : activeTab === 'main' ? 'limits' : 'main'; setActiveTab(next); dialog.current?.querySelector<HTMLButtonElement>(`[data-settings-tab="${next}"]`)?.focus(); } }}>
        <button type="button" role="tab" data-settings-tab="main" id="settings-tab-main" aria-selected={activeTab === 'main'} aria-controls="settings-panel-main" tabIndex={activeTab === 'main' ? 0 : -1} onClick={() => setActiveTab('main')}>Main</button>
        <button type="button" role="tab" data-settings-tab="limits" id="settings-tab-limits" aria-selected={activeTab === 'limits'} aria-controls="settings-panel-limits" tabIndex={activeTab === 'limits' ? 0 : -1} onClick={() => setActiveTab('limits')}>Limits</button>
      </div>}
      <div className="settings-body" id={initial ? 'settings-panel-main' : undefined} role={initial ? 'tabpanel' : undefined} aria-labelledby={initial ? 'settings-tab-main' : undefined} hidden={!!initial && activeTab !== 'main'}><p id="project-settings-help">{initial ? 'Choose this project’s research type and AI settings. Edit its title and description directly on the project page.' : 'Name a project and choose its research category.'}</p>
      <fieldset disabled={busy}>
      {!initial && <><label htmlFor="project-name">Project name</label><input ref={first} id="project-name" required maxLength={200} value={values.title} onChange={event => change('title', event.target.value)}/>
      <label htmlFor="project-problem">Research problem</label><textarea id="project-problem" required maxLength={20000} rows={4} value={values.problem} onChange={event => change('problem', event.target.value)}/></>}
      <div className="settings-classification-row"><div><label id="project-mode-label">{initial ? 'Research type' : 'Research category'}</label><ResearchTypePicker fieldLabel={initial ? 'Research type' : 'Research category'} value={values.investigation_type} onChange={value => change('investigation_type', value)}/></div>
      <div><label htmlFor="project-difficulty">Difficulty</label><select id="project-difficulty" value={values.difficulty ?? ''} onChange={event => change('difficulty', (event.target.value || null) as ProjectDifficulty | null)}>{values.difficulty === null && <option value="">Not set</option>}<option value="easy">Easy</option><option value="medium">Medium</option><option value="hard">Hard</option></select></div></div>
      <label htmlFor="project-model">LLM Model</label><select id="project-model" required value={values.ai_model} onChange={event => change('ai_model', event.target.value)} aria-describedby="project-model-help">
        {!values.ai_model && <option value="" disabled>Loading reviewed choices…</option>}
        {values.ai_model && !selected && <option value={values.ai_model}>{values.ai_model} · unavailable/unreviewed</option>}
        {orderedCatalog.map(model => <option key={model.id} value={model.id}>{model.label.replace(/\s*\([^)]*\)$/, '').trim()} · {model.relative_cost}{model.availability === 'available' ? '' : model.availability === 'unavailable' ? ' · unavailable' : ' · access unverified'}</option>)}
      </select>
      <p id="project-model-help" className="settings-hint">{ai.info?.mode === 'api_key' ? 'OpenAI API · billed separately. ' : 'ChatGPT plan allowance or credits · connection required for generation. '}{selected?.description} {catalogMessage}{selected?.availability === 'unavailable' ? ' Your selected model is unavailable; it will not be replaced automatically.' : ''}</p>
      <label htmlFor="project-thinking">Thinking level</label><select id="project-thinking" value={values.reasoning_effort} onChange={event => change('reasoning_effort', event.target.value)}>
        {!selected?.efforts.includes(values.reasoning_effort) && <option value={values.reasoning_effort}>{thinkingLabels[values.reasoning_effort] ?? values.reasoning_effort} · {selected ? 'unsupported' : 'preserved'}</option>}
        {(selected?.efforts ?? []).map(effort => <option key={effort} value={effort}>{thinkingLabels[effort] ?? effort}</option>)}
      </select>
      <p className="settings-hint">Applies to future AI proposals. Higher thinking can take longer and consume more usage. API cost tiers are relative; <a href="https://developers.openai.com/api/docs/pricing" target="_blank" rel="noreferrer">current token prices</a>. Earlier strategy provenance stays unchanged.</p>
      {pairError && <p className="error" role="alert">{pairError}</p>}
      <p className="project-destination"><span>Project location</span><code>{initial ? initial.path : previewBusy ? 'Checking location…' : destination?.path ?? destination?.root ?? 'Location unavailable'}</code><small>{initial ? 'Editing the display name never renames or moves this directory.' : 'The project name determines its directory; existing files are never overwritten.'}</small></p>
      {locationError && <p className="error" role="alert">{locationError}</p>}
      {destination?.exists && <p className="error" role="alert">That name is already used by another project, or the location is occupied. Choose another name.</p>}
      {error && <p className="error" role="alert">{error}</p>}
    </fieldset></div>
    {initial && <section id="settings-panel-limits" className="settings-body research-limits-panel" role="tabpanel" aria-labelledby="settings-tab-limits" hidden={activeTab !== 'limits'}>
      <p>Research limits apply to future sessions. For local strategy generation, the model-call limit also sets the call budget. Existing sessions keep the limits captured when they started.</p>
      {cloud?.enabled && <p className="settings-hint">Cloud research is capped at six calls, 15 minutes, and $0.25 estimated cost per session. Values above these limits are saved at the cloud cap.</p>}
      <fieldset disabled={busy || !limitsLoaded}>
        <label htmlFor="research-rounds">Skeptic iterations</label><input id="research-rounds" type="number" min={1} max={5} step={1} value={limitDraft.research_rounds} aria-invalid={!!limitValidation.errors.research_rounds} aria-describedby="research-rounds-help research-rounds-error" onChange={event => setLimitDraft(value => ({ ...value, research_rounds: event.target.value }))}/><p id="research-rounds-help" className="settings-hint">Investigator/Skeptic iterations, from 1 to 5.</p>{limitValidation.errors.research_rounds && <p id="research-rounds-error" className="limit-error" role="alert">{limitValidation.errors.research_rounds}</p>}
        <label htmlFor="research-calls">Maximum agent calls</label><input id="research-calls" type="number" min={2} max={30} step={1} value={limitDraft.model_calls} aria-invalid={!!limitValidation.errors.model_calls} aria-describedby="research-calls-help research-calls-error" onChange={event => setLimitDraft(value => ({ ...value, model_calls: event.target.value }))}/><p id="research-calls-help" className="settings-hint">Provider request allowance, 2 to 30. At least two calls per iteration are required for Investigator and Skeptic; local strategy generation uses this as its call ceiling.</p>{limitValidation.errors.model_calls && <p id="research-calls-error" className="limit-error" role="alert">{limitValidation.errors.model_calls}</p>}
        <label htmlFor="research-duration-value">Maximum session duration</label><div className="research-duration-controls"><input id="research-duration-value" type="number" min={1} max={Math.floor(MAX_SESSION_DURATION_MINUTES / durationUnitMinutes[limitDraft.session_duration_unit])} step={1} value={limitDraft.session_duration_value} aria-invalid={!!limitValidation.errors.session_duration_value} aria-describedby="research-duration-help research-duration-error" onChange={event => setLimitDraft(value => ({ ...value, session_duration_value: event.target.value }))}/><select id="research-duration-unit" aria-label="Maximum session duration unit" value={limitDraft.session_duration_unit} onChange={event => setLimitDraft(value => ({ ...value, session_duration_unit: event.target.value as DurationUnit }))}><option value="minutes">Minutes</option><option value="hours">Hours</option><option value="days">Days</option></select></div><p id="research-duration-help" className="settings-hint">Elapsed wall time from start, 1 minute to 7 days. Time spent paused counts.</p>{limitValidation.errors.session_duration_value && <p id="research-duration-error" className="limit-error" role="alert">{limitValidation.errors.session_duration_value}</p>}
        <label htmlFor="research-output-tokens">Maximum output tokens per call</label><input id="research-output-tokens" type="number" min={256} max={16384} step={1} value={limitDraft.output_tokens_per_call} aria-invalid={!!limitValidation.errors.output_tokens_per_call} aria-describedby="research-output-help research-output-error" onChange={event => setLimitDraft(value => ({ ...value, output_tokens_per_call: event.target.value }))}/><p id="research-output-help" className="settings-hint">256 to 16,384 tokens. SIGMA sends this limit where supported and enforces it against reported output usage or a conservative response-size bound.</p>{limitValidation.errors.output_tokens_per_call && <p id="research-output-error" className="limit-error" role="alert">{limitValidation.errors.output_tokens_per_call}</p>}
        <label htmlFor="research-cost-limit">Maximum estimated session cost (USD)</label><input id="research-cost-limit" type="text" inputMode="decimal" placeholder="Unlimited" value={limitDraft.maximum_estimated_cost_usd} aria-invalid={!!limitValidation.errors.maximum_estimated_cost_usd} aria-describedby="research-cost-help research-cost-error" onChange={event => setLimitDraft(value => ({ ...value, maximum_estimated_cost_usd: event.target.value }))}/><p id="research-cost-help" className="settings-hint">API-key billing only: $0.01 to $100.00, or blank for unlimited. ChatGPT subscription usage is not converted to dollars. Estimates use published prices and reported tokens; unknown prices or missing usage pause further calls when a cap is set.</p>{limitValidation.errors.maximum_estimated_cost_usd && <p id="research-cost-error" className="limit-error" role="alert">{limitValidation.errors.maximum_estimated_cost_usd}</p>}
      </fieldset>
      {!limitsLoaded && <p role="status">Loading saved research limits…</p>}{error && <p role="alert" className="error">{error} <button type="button" className="text-view-link" onClick={async () => { setError(''); try { const response = await fetch(`/api/projects/research-limits?${new URLSearchParams({ path: initial.path })}`); const data = await response.json(); if (!response.ok) throw new Error(data.error ?? 'Research limits could not be read'); setLimitDraft(draftLimits(data)); setLimitsLoaded(true); } catch (cause) { setError(errorMessage(cause)); } }}>Retry</button></p>}
    </section>}
    </form>
  </dialog>;
}

type RecentProject = { id: string; path: string; title: string; investigation_type: string | null; strategy_count: number | null; difficulty: ProjectDifficulty | null; available: boolean; error: string | null };
type SampleProject = { id: string; title: string; problem: string; investigation_type: ResearchMode; difficulty: ProjectDifficulty | null; strategy_count: number };
const strategyCount = (count: number) => `${count} ${count === 1 ? 'strategy' : 'strategies'}`;
function RecentProjects({ onOpen }: { onOpen: (view: ProjectView) => void }) {
  const [projects, setProjects] = useState<RecentProject[]>([]);
  const [loading, setLoading] = useState(true);
  const [opening, setOpening] = useState('');
  const [confirmRemoveId, setConfirmRemoveId] = useState('');
  const [error, setError] = useState('');
  const pending = useRef(false);
  const load = useCallback(async (signal?: AbortSignal) => {
    const response = await fetch('/api/projects/recent', { signal });
    const data = await response.json(); if (!response.ok) throw new Error(data.error ?? 'Recent Projects unavailable. Open Project still works.');
    setProjects(data.projects); setLoading(false);
  }, []);
  useEffect(() => { const controller = new AbortController(); void load(controller.signal).catch(error => { if (!controller.signal.aborted) { setError(errorMessage(error)); setLoading(false); } }); return () => controller.abort(); }, [load]);
  async function open(entry: RecentProject) {
    if (pending.current) return; pending.current = true; setOpening(entry.id); setError('');
    try { onOpen(await post<ProjectView>('open', { path: entry.path })); }
    catch (error) { setError(errorMessage(error)); }
    finally { pending.current = false; setOpening(''); }
  }
  async function forget(entry: RecentProject) {
    if (pending.current) return; pending.current = true; setOpening(entry.id); setError('');
    try { await post('recent/forget', { project_id: entry.id }); setConfirmRemoveId(''); await load(); }
    catch (error) { setError(errorMessage(error)); }
    finally { pending.current = false; setOpening(''); }
  }
  const recentGroups = projects.reduce<Array<{ type: ResearchMode; projects: RecentProject[] }>>((groups, project) => {
    const type: ResearchMode = project.investigation_type && Object.hasOwn(researchTypeLabels, project.investigation_type)
      ? project.investigation_type as ResearchMode
      : 'default';
    const group = groups.find(item => item.type === type);
    if (group) group.projects.push(project);
    else groups.push({ type, projects: [project] });
    return groups;
  }, []).sort((a, b) => researchTypeLabel(a.type).localeCompare(researchTypeLabel(b.type)));
  return <div className="empty home-empty home-recents">
    {loading ? <p role="status">Loading recent projects…</p> : !projects.length && <p>No recent projects yet. Open a project or begin a new project.</p>}
    {recentGroups.map(group => <details className="recent-type-group" key={group.type ?? 'other'} open={group.projects.some(entry => entry.path === window.localStorage.getItem('sigma.currentProject'))}>
      <summary>{group.type && group.type in researchTypeLabels && <ResearchTypeIcon type={group.type as ResearchMode}/>}<span>{researchTypeLabel(group.type)}</span><small>{group.projects.length} {group.projects.length === 1 ? 'project' : 'projects'}</small></summary>
      <ul>{group.projects.map((entry, index) => <li key={entry.id}>
        <div className="recent-entry">
          <div className="recent-title-row">
            <button className="recent-open" disabled={!entry.available || !!opening} onClick={() => void open(entry)}>{index === 0 || entry.path === window.localStorage.getItem('sigma.currentProject') ? <strong className={`${index === 0 ? 'is-most-recent-project' : ''} ${entry.path === window.localStorage.getItem('sigma.currentProject') ? 'is-current-project' : ''}`.trim()}>{entry.title}</strong> : entry.title}</button>
          </div>
          <div className="recent-meta-row"><small><span>{entry.strategy_count === null ? difficultyDescription(entry.difficulty) : `${strategyCount(entry.strategy_count)} · ${difficultyDescription(entry.difficulty)}`}</span></small><button className="recent-forget" disabled={!!opening} aria-label={`Remove ${entry.title} from Recent Projects`} aria-expanded={confirmRemoveId === entry.id} title="Remove from Recent Projects; keep all research" onClick={() => setConfirmRemoveId(current => current === entry.id ? '' : entry.id)}>Remove</button></div>
          <span title={entry.path}>{entry.path}</span>
          {confirmRemoveId === entry.id && <div className="recent-remove-actions"><div className="recent-remove-confirm" role="group" aria-label={`Confirm remove ${entry.title}`}><p>Remove “{entry.title}” from Recent Projects? The project and its research will be kept in storage.</p><div className="recent-remove-confirm-actions"><button type="button" className="destructive-action" disabled={!!opening} onClick={() => void forget(entry)}>Confirm</button><button type="button" disabled={!!opening} onClick={() => setConfirmRemoveId('')}>Cancel</button></div></div></div>}
        </div>
        {entry.error && <p className="recent-unavailable">{entry.error}</p>}
      </li>)}</ul>
    </details>)}
    {error && <p role="alert" className="error">{error}</p>}
  </div>;
}

function SampleProjects({ onOpen }: { onOpen: (view: ProjectView) => void }) {
  const [projects, setProjects] = useState<SampleProject[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [opening, setOpening] = useState('');
  const pending = useRef(false);
  useEffect(() => {
    const controller = new AbortController();
    void fetch('/api/projects/samples', { signal: controller.signal }).then(async response => {
      const data = await response.json();
      if (!response.ok) throw new Error(data.error ?? 'Samples unavailable.');
      setProjects([...data.projects].sort((a: SampleProject, b: SampleProject) => {
        const typeOrder = researchTypeLabel(a.investigation_type).localeCompare(researchTypeLabel(b.investigation_type), 'en', { sensitivity: 'base' });
        return typeOrder || a.title.localeCompare(b.title, 'en', { sensitivity: 'base' });
      })); setLoading(false);
    }).catch(error => { if (!controller.signal.aborted) { setError(errorMessage(error)); setLoading(false); } });
    return () => controller.abort();
  }, []);
  async function open(sample: SampleProject) {
    if (pending.current) return; pending.current = true; setOpening(sample.id); setError('');
    try {
      const copy = await post<ProjectView>('samples/open', { sample_id: sample.id });
      // A Sample opens as a saved working copy, which now belongs in Recent.
      window.localStorage.setItem('sigma.homeCatalogTab', 'recent');
      onOpen(copy);
    }
    catch (error) { setError(errorMessage(error)); }
    finally { pending.current = false; setOpening(''); }
  }
  const groups = projects.reduce<Array<{ type: ResearchMode; samples: SampleProject[] }>>((result, sample) => {
    const group = result.find(item => item.type === sample.investigation_type);
    if (group) group.samples.push(sample);
    else result.push({ type: sample.investigation_type, samples: [sample] });
    return result;
  }, []);
  return <div className="empty home-empty home-samples">
    {loading ? <p role="status">Loading sample projects…</p> : !projects.length && !error && <p>No sample projects are available.</p>}
    {groups.map(group => <details className="sample-type-group" key={group.type} open>
      <summary><ResearchTypeIcon type={group.type}/><span>{researchTypeLabel(group.type)}</span><small>{group.samples.length} {group.samples.length === 1 ? 'sample' : 'samples'}</small></summary>
      <ul>{group.samples.map(sample => <li key={sample.id}><button className="sample-open" disabled={!!opening} onClick={() => void open(sample)} aria-label={`Open ${sample.title}`}><strong>{sample.title}</strong><small><span>{strategyCount(sample.strategy_count)} · {difficultyDescription(sample.difficulty)}</span></small></button></li>)}</ul>
    </details>)}
    {error && <p role="alert" className="error">{error}</p>}
  </div>;
}

function HomeCatalog({ onOpen }: { onOpen: (view: ProjectView) => void }) {
  const [tab, setTab] = useState<'recent' | 'samples'>(() =>
    window.localStorage.getItem('sigma.homeCatalogTab') === 'recent' ? 'recent' : 'samples');
  useEffect(() => { window.localStorage.setItem('sigma.homeCatalogTab', tab); }, [tab]);
  const recent = useRef<HTMLButtonElement>(null);
  const samples = useRef<HTMLButtonElement>(null);
  const recentPanel = useRef<HTMLDivElement>(null);
  const samplesPanel = useRef<HTMLDivElement>(null);
  function switchTab(next: 'recent' | 'samples') {
    if (next === tab) {
      const panel = next === 'samples' ? samplesPanel.current : recentPanel.current;
      if (panel) {
        const selector = next === 'samples' ? '.sample-type-group' : '.recent-type-group';
        const groups = Array.from(panel.querySelectorAll<HTMLDetailsElement>(selector));
        const expandAll = groups.length > 0 && groups.every(group => !group.open);
        groups.forEach(group => { group.open = expandAll; });
      }
      return;
    }
    setTab(next); (next === 'recent' ? recent : samples).current?.focus();
  }
  return <div className="home-catalog"><div className="catalog-tabs" role="tablist" aria-label="Project lists" onKeyDown={event => {
    if (event.key === 'ArrowRight' || event.key === 'ArrowLeft') { event.preventDefault(); switchTab(tab === 'samples' ? 'recent' : 'samples'); }
    if (event.key === 'Home') { event.preventDefault(); switchTab('samples'); }
    if (event.key === 'End') { event.preventDefault(); switchTab('recent'); }
  }}>
    <button ref={samples} id="samples-tab" role="tab" aria-controls="samples-panel" aria-selected={tab === 'samples'} tabIndex={tab === 'samples' ? 0 : -1} data-tooltip="Show sample projects. Click again to collapse or expand all." onClick={() => switchTab('samples')}>Samples</button>
    <button ref={recent} id="recent-tab" role="tab" aria-controls="recent-panel" aria-selected={tab === 'recent'} tabIndex={tab === 'recent' ? 0 : -1} data-tooltip="Show recent projects. Click again to collapse or expand all." onClick={() => switchTab('recent')}>Recent</button>
  </div>
    <div ref={recentPanel} id="recent-panel" role="tabpanel" aria-labelledby="recent-tab" hidden={tab !== 'recent'}><RecentProjects onOpen={onOpen}/></div>
    <div ref={samplesPanel} id="samples-panel" role="tabpanel" aria-labelledby="samples-tab" hidden={tab !== 'samples'}><SampleProjects onOpen={onOpen}/></div>
  </div>;
}

type CloudResearchBudget = {
  allowance_usd: number;
  estimated_usage_usd: number;
  held_usd: number;
  reserved_and_estimated_usd: number;
  remaining_usd: number;
  unknown_provider_attempts: number;
};

function Home({ initialPath, onOpen }: {
  initialPath: string; onOpen: (view: ProjectView) => void;
}) {
  const cloud = useCloudIdentity();
  const [entry, setEntry] = useState<'open' | 'new' | null>(null);
  const heading = useRef<HTMLHeadingElement>(null);
  const openButton = useRef<HTMLButtonElement>(null);
  const newButton = useRef<HTMLButtonElement>(null);
  const shell = useRef<HTMLDivElement>(null);
  const nextCreditStreak = useRef(0);
  const nextCreditPlunk = useRef(0);
  const turbulenceAnimation = useRef<SVGAnimateElement>(null);
  const displacementAnimation = useRef<SVGAnimateElement>(null);
  const [creditStreaks, setCreditStreaks] = useState<Array<{ id: number; line: 'name' | 'models' }>>([]);
  const [creditPlunk, setCreditPlunk] = useState<number | null>(null);
  useEffect(() => { document.title = 'SIGMA · Research workspace'; heading.current?.focus(); }, []);
  useEffect(() => {
    // CSS background-size: cover scales the source image by the larger of
    // viewport-width/image-width and viewport-height/image-height. Apply
    // that exact same factor to the beam overlay, anchored at image top/center.
    const background = new Image();
    const updateScale = () => {
      if (!background.naturalWidth || !background.naturalHeight) return;
      const scale = Math.max(
        window.innerWidth / background.naturalWidth,
        window.innerHeight / background.naturalHeight,
      );
      shell.current?.style.setProperty('--home-art-scale', String(scale));
    };
    background.addEventListener('load', updateScale);
    window.addEventListener('resize', updateScale);
    background.src = '/sigma-home-background-copper.png';
    if (background.complete) updateScale();
    return () => {
      background.removeEventListener('load', updateScale);
      window.removeEventListener('resize', updateScale);
    };
  }, []);
  function cancel() {
    const trigger = entry === 'open' ? openButton : newButton;
    setEntry(null); requestAnimationFrame(() => trigger.current?.focus());
  }
  function launchCreditStreak() {
    const nameId = ++nextCreditStreak.current;
    const modelsId = ++nextCreditStreak.current;
    setCreditStreaks(current => [...current, { id: nameId, line: 'name' }, { id: modelsId, line: 'models' }]);
  }
  function removeCreditStreak(id: number) {
    setCreditStreaks(current => current.filter(streak => streak.id !== id));
  }
  function launchCreditPlunk() {
    const id = ++nextCreditPlunk.current;
    setCreditPlunk(id);
    requestAnimationFrame(() => {
      turbulenceAnimation.current?.beginElement();
      displacementAnimation.current?.beginElement();
    });
  }
  function finishCreditPlunk(id: number) {
    setCreditPlunk(current => current === id ? null : current);
  }
  return <div ref={shell} className={`home-shell${creditPlunk !== null ? ' home-credit-plunk-active' : ''}`}>
    <svg className="home-effect-definitions" aria-hidden="true" width="0" height="0" focusable="false"><defs><filter id="home-rubber-sheet-filter" x="-12%" y="-12%" width="124%" height="124%"><feTurbulence type="fractalNoise" baseFrequency="0.004 0.008" numOctaves="2" seed="4" result="rubber-wave"><animate ref={turbulenceAnimation} attributeName="baseFrequency" values="0.004 0.008;0.014 0.024;0.006 0.012" dur="900ms" begin="indefinite" fill="freeze"/></feTurbulence><feDisplacementMap in="SourceGraphic" in2="rubber-wave" scale="0" xChannelSelector="R" yChannelSelector="G"><animate ref={displacementAnimation} attributeName="scale" values="0;26;13;0" keyTimes="0;0.2;0.62;1" dur="900ms" begin="indefinite" fill="freeze"/></feDisplacementMap></filter></defs></svg>
    <div className="home-atmosphere" aria-hidden="true"/>
    <div className="home-content">
      {cloud?.user?.role === 'admin' && <a href="#administrator-settings" className="administrator-settings-link" onClick={event => { event.preventDefault(); cloud.openAccessManagement(); }}>Administrator Settings</a>}
      <div className="home-topline"><GoogleIdentityPill/><ConnectionStatus projectHeader cloudFunding={cloudFundingFor(cloud)}/></div>
      {cloud?.enabled && !cloud.authenticated && cloud.deniedEmail && <AccessNotGranted email={cloud.deniedEmail} contactEmail={cloud.admin_contact_email}/>}
      {cloud?.enabled && !cloud.authenticated && !cloud.deniedEmail && <section className="home-cloud-prompt"><h1>Sign in with approved Gmail account to access projects.</h1></section>}
      {(!cloud?.enabled || cloud.authenticated) && <section className="home-projects" aria-labelledby="home-projects-heading">
        <div className="home-projects-heading">
          <h1 id="home-projects-heading" ref={heading} tabIndex={-1}>Projects</h1>
          <button type="button" ref={newButton} className="home-project-action" data-tooltip="Create a project" onClick={() => setEntry('new')}>New</button>
          <button type="button" ref={openButton} className="home-project-action" data-tooltip="Open an existing project" onClick={() => setEntry('open')}>Open</button>
        </div>
        <HomeCatalog onOpen={onOpen}/>
      </section>}
      <img className="home-slogan" src="/sigma-slogan-copper-approved.png" alt="Strategy · Investigation · Generation · Measurement · Assessment"/>
      <footer className="home-art-credit" aria-label="Artwork credit" onPointerEnter={event => { if (!(event.relatedTarget instanceof Node) || !event.currentTarget.contains(event.relatedTarget)) launchCreditStreak(); }} onClick={launchCreditPlunk}><span>Brian Kramer</span><span>&amp; OpenAI Models</span>{creditStreaks.map(({ id, line }) => <span key={id} className={`home-credit-streak home-credit-streak--${line}`} aria-hidden="true" onAnimationEnd={() => removeCreditStreak(id)}/>)}{creditPlunk !== null && <span key={creditPlunk} className="home-credit-plunk" aria-hidden="true" onAnimationEnd={() => finishCreditPlunk(creditPlunk)}/>}</footer>
      {entry === 'open' && <ProjectEntryDialog initialPath={initialPath} onOpen={onOpen} onCancel={cancel}/>}
      {entry === 'new' && <ProjectSettingsDialog onSaved={onOpen} onCancel={cancel}/>}
    </div>
  </div>;
}

function StrategyTitleEditor({ strategy, path, onSaved, modeDisabled, descriptionDraft, onEnterMode, onExitMode, onEditDescription, expanded, onToggle, commands }: {
  strategy: Strategy; path: string; onSaved: (view: ProjectView) => void; modeDisabled: boolean; descriptionDraft: string; onEnterMode: () => boolean; onExitMode: () => void;
  onEditDescription: () => void; expanded: boolean; onToggle: () => void; commands: ReactNode;
}) {
  const [editing, setEditing] = useState(false);
  const shownTitle = displayStrategyTitle(strategy);
  const [draft, setDraft] = useState(shownTitle);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const input = useRef<HTMLInputElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const form = useRef<HTMLFormElement>(null);
  useEffect(() => { if (!editing) setDraft(shownTitle); }, [shownTitle, editing]);
  useEffect(() => { if (editing) { input.current?.focus(); input.current?.select(); } }, [editing]);
  function cancel(restoreFocus = true) {
    setEditing(false); onExitMode(); setDraft(shownTitle); setError('');
    if (restoreFocus) requestAnimationFrame(() => trigger.current?.focus());
  }
  async function save(event: FormEvent) {
    event.preventDefault(); event.stopPropagation();
    if (busy) return;
    if (!draft.trim()) { setError('Enter a strategy title.'); input.current?.focus(); return; }
    setBusy(true); setError('');
    try {
      const next = await post<ProjectView>('strategies/edit', {
        path, strategy_id: strategy.id, title: draft, approach: descriptionDraft,
      });
      setEditing(false); onExitMode(); onSaved(next);
      requestAnimationFrame(() => trigger.current?.focus());
    } catch (cause) { setError(errorMessage(cause)); reportRequestFailure(errorMessage(cause)); }
    finally { setBusy(false); }
  }
  return <div className={`strategy-title-editor${editing ? ' is-renaming' : ''}`}>
    {editing ? <form ref={form} onSubmit={save} className="strategy-rename-form">
      <label className="sr-only" htmlFor={`strategy-title-${strategy.id}`}>Strategy title</label>
      <input ref={input} id={`strategy-title-${strategy.id}`} aria-label="Strategy title" value={draft} size={Math.max(8, Math.min(50, draft.length + 1))} maxLength={200} disabled={busy}
        required onChange={event => { setDraft(event.target.value); setError(''); }} onKeyDown={event => { if (event.key === 'Escape' && !busy) { event.preventDefault(); cancel(); } }}/>
      <button type="submit" className="text-view-link" title="Save strategy title" disabled={busy}>Save</button>
      <button type="button" className="text-view-link" title="Cancel editing the strategy title" disabled={busy} onClick={() => cancel()}>Cancel</button>
    </form> : <div className="strategy-title-line">
      <button type="button" id={`strategy-${strategy.id}`} className={`strategy-row-disclosure${strategy.enabled ? '' : ' is-disabled'}`} title={`${expanded ? 'Collapse' : 'Expand'} strategy: ${shownTitle}`} aria-expanded={expanded} aria-controls={`strategy-content-${strategy.id}`} onClick={onToggle}><DisclosureChevron expanded={expanded}/><h3>{shownTitle}</h3></button>
      <span id={`strategy-markdown-slot-${strategy.id}`} className="strategy-markdown-slot"/><button type="button" ref={trigger} className="text-view-link text-view-icon workspace-icon-button strategy-title-pencil" aria-label={`Edit strategy title and description: ${shownTitle}`} data-tooltip-disabled disabled={modeDisabled}
        onClick={() => { if (onEnterMode()) { setEditing(true); onEditDescription(); } }}><svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><path d="m15 5 4 4M4 20l4.5-1 11-11a2.83 2.83 0 0 0-4-4l-11 11L4 20Z"/></svg></button>
      {commands}
    </div>}
    {error && <p className="error" role="alert">{error}</p>}
  </div>;
}

function StrategyCommands({ strategy, onCommand, disabled = false }: {
  strategy: Strategy; onCommand: (mode: 'remove' | 'fork' | 'toggle', strategy: Strategy) => void; disabled?: boolean;
}) {
  const [confirmingRemove, setConfirmingRemove] = useState(false);
  return <span className="strategy-inline-commands">
    <button type="button" className="text-view-link" disabled={disabled}
      title={`${strategy.enabled ? 'Disable' : 'Enable'} strategy`} onClick={() => onCommand('toggle', strategy)}>{strategy.enabled ? 'Disable' : 'Enable'}</button>
    <button type="button" className="text-view-link" disabled={disabled}
      title="Fork strategy" onClick={() => onCommand('fork', strategy)}>Fork</button>
    <span className="strategy-remove-anchor">
      <button type="button" id={`commands-${strategy.id}`} className="text-view-link" disabled={disabled}
        title="Remove strategy" onClick={() => setConfirmingRemove(true)}>Remove</button>
      {confirmingRemove && <div className="strategy-remove-popover"><div className="research-stop-confirm" role="group" aria-label={`Confirm remove strategy ${strategy.title}`}>
        <p>Remove “{strategy.title}” from Strategies? Its research and history will be kept in the project.</p>
        <div className="session-remove-confirm-actions">
          <button type="button" className="text-view-link destructive-action" disabled={disabled} onClick={() => { setConfirmingRemove(false); onCommand('remove', strategy); }}>Confirm</button>
          <button type="button" className="text-view-link" disabled={disabled} onClick={() => setConfirmingRemove(false)}>Cancel</button>
        </div>
      </div></div>}
    </span>
  </span>;
}

function NewStrategy({ path, onSaved, onCancel, initialDraft }: {
  path: string; initialDraft?: { title: string; approach: string; summary?: string }; onSaved: (view: ProjectView) => void; onCancel: () => void;
}) {
  const submitting = useRef(false);
  const [title, setTitle] = useState(initialDraft?.title ?? '');
  const [approach, setApproach] = useState(initialDraft?.approach ?? '');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const titleInput = useRef<HTMLInputElement>(null);
  useEffect(() => { titleInput.current?.focus(); }, []);
  async function save(event: FormEvent) {
    event.preventDefault(); if (submitting.current) return; submitting.current = true; setBusy(true); setError('');
    try { onSaved(await post<ProjectView>('strategies', { path, title, approach, summary: initialDraft?.summary ?? '' })); }
    catch (error) { setError(errorMessage(error)); }
    finally { submitting.current = false; setBusy(false); }
  }
  return <form className="strategy-form" aria-labelledby="new-strategy-heading" onSubmit={save}
    onKeyDown={event => { if (event.key === 'Escape' && !busy) { event.preventDefault(); onCancel(); } }}>
    <div className="new-strategy-heading-row"><h3 id="new-strategy-heading">{initialDraft ? "Forked strategy" : "New strategy"}</h3><div className="new-strategy-heading-actions"><button type="submit" className="text-view-link" disabled={busy}>{busy ? "Saving…" : "Save"}</button><button type="button" className="text-view-link" disabled={busy} onClick={onCancel}>Cancel</button></div></div>
    <p className="hint">Capture an idea and the approach you want to investigate.</p>
    <fieldset disabled={busy}>
      <label htmlFor="strategy-title">Title</label>
      <input ref={titleInput} id="strategy-title" value={title} maxLength={200} required
        onChange={event => setTitle(event.target.value)} />
      <label htmlFor="strategy-approach">Hypothesis / approach</label>
      <textarea id="strategy-approach" value={approach} maxLength={MAX_STRATEGY_APPROACH} required rows={5}
        onChange={event => setApproach(event.target.value)} />
      {error && <p role="alert" className="error">{error}</p>}
    </fieldset>
  </form>;
}

function StrategyCreationActions({ buttonRef, disabled, hideNew = false, onManual, onAI }: {
  buttonRef: React.RefObject<HTMLButtonElement | null>; disabled: boolean; hideNew?: boolean; onManual: () => void; onAI: () => void;
}) {
  return <div className="strategy-heading-actions">
    {!hideNew && <button type="button" className="text-view-link" ref={buttonRef} title="Create a new strategy" disabled={disabled} onClick={onManual}>New</button>}
    <button type="button" className="text-view-link" title="Generate a strategy with AI" disabled={disabled} onClick={onAI}>Generate</button>
  </div>;
}

function ProcessControlsView({ controls, disabled }: { controls: ProcessControls; disabled: boolean }) {
  return <span className="strategy-process-controls" aria-label="Research process controls">
      {controls.confirming ? <>
        <button type="button" className="text-view-link session-start-link" title={`Confirm start new Session ${controls.nextSessionNumber}`} disabled={disabled} onClick={controls.start}>Start new session #{controls.nextSessionNumber}</button>
        <button type="button" className="text-view-link session-start-link" title="Cancel starting a research session" disabled={disabled} onClick={controls.cancel}>Cancel</button>
      </> : <>
      <button type="button" className="text-view-link text-view-icon workspace-icon-button process-control" aria-label={controls.playLabel} title={controls.playLabel} data-tooltip={controls.playLabel} disabled={controls.playDisabled || disabled} onClick={controls.play}>
        <svg viewBox="0 0 20 20" aria-hidden="true"><path d="M6 3.8v12.4L16 10 6 3.8Z"/></svg>
      </button>
      <button type="button" className="text-view-link text-view-icon workspace-icon-button process-control" aria-label="Stop research session" title="Stop research session" data-tooltip="Stop research session" disabled={controls.stopDisabled || disabled} onClick={controls.stop}>
        <svg viewBox="0 0 20 20" aria-hidden="true"><path d="M5 5h10v10H5z"/></svg>
      </button>
      </>}
  </span>;
}

type ProposalResult = { draft: { title: string; summary: string; approach: string; first_tests: string; assumptions: string; failure_modes: string }; provenance: { provider: string; model: string; reasoning_effort?: string | null }; receipt: string };
type AgenticEvent = { type: string; sequence: number; run_id: string; kind?: 'explore' | 'challenge' | 'revise' | null; attempt?: number | null; summary?: string | null; outcome?: 'revise' | 'retry' | 'present' | 'stop' | null; max_calls?: number | null; draft?: ProposalResult['draft'] | null; provenance?: ProposalResult['provenance'] | null; receipt?: string | null; assessment?: 'distinct' | 'overlapping' | 'unconvincing' | null; objections?: string[] | null; missing_obligations?: string | null; mechanism_comparison?: string | null };
const activityLabels = { explore: 'Exploring a candidate', challenge: 'Independent challenge', revise: 'Targeted revision' } as const;
async function readAgenticStream(response: Response, onEvent: (event: AgenticEvent) => void): Promise<AgenticEvent> {
  if (!response.ok) { let detail = `HTTP ${response.status}`; try { const body = await response.json(); detail = body.error ?? body.detail ?? detail; } catch {} throw new Error(String(detail)); }
  if (!response.body) throw new Error('The server returned no progress stream. Nothing was saved.');
  const reader = response.body.getReader(); const decoder = new TextDecoder(); let buffer = ''; let sequence = 0; let runId = ''; let terminal: AgenticEvent | null = null;
  const consume = (chunk: string) => {
    buffer += chunk; const records = buffer.split(/\r?\n\r?\n/); buffer = records.pop() ?? '';
    for (const record of records) {
      const data = record.split(/\r?\n/).filter(line => line.startsWith('data:')).map(line => line.slice(5).trimStart()).join('\n');
      if (!data) continue;
      let event: AgenticEvent; try { event = JSON.parse(data) as AgenticEvent; } catch { throw new Error('The server sent malformed progress data. You can retry; nothing was saved.'); }
      if (!['run.started', 'activity.started', 'activity.completed', 'decision', 'run.completed', 'run.stopped', 'run.failed'].includes(event?.type)) throw new Error('The server sent an unknown progress event. You can retry; nothing was saved.');
      if (!event || typeof event.type !== 'string' || !Number.isInteger(event.sequence) || event.sequence !== sequence + 1 || typeof event.run_id !== 'string' || !/^[0-9a-f]{32}$/.test(event.run_id)) throw new Error('The progress stream was incomplete or out of order. You can retry; nothing was saved.');
      if (runId && event.run_id !== runId) throw new Error('The progress stream changed run identity. You can retry; nothing was saved.');
      if (terminal) throw new Error('The server sent progress after its terminal event. You can retry; nothing was saved.');
      sequence = event.sequence; runId = event.run_id;
      const activityKind = event.kind === 'explore' || event.kind === 'challenge' || event.kind === 'revise';
      if (event.type === 'run.started' && (!Number.isInteger(event.max_calls) || (event.max_calls ?? 0) < 2 || (event.max_calls ?? 0) > 30)) throw new Error('The server sent an invalid run limit. You can retry; nothing was saved.');
      if (event.type.startsWith('activity.') && (!activityKind || !Number.isInteger(event.attempt) || (event.attempt ?? 0) < 1 || (event.attempt ?? 0) > 15)) throw new Error('The server sent an invalid activity event. You can retry; nothing was saved.');
      if (event.type === 'activity.completed' && typeof event.summary !== 'string') throw new Error('The server sent an incomplete activity result. You can retry; nothing was saved.');
      if (event.type === 'activity.completed' && event.kind === 'challenge' && (!event.assessment || !Array.isArray(event.objections) || typeof event.missing_obligations !== 'string' || typeof event.mechanism_comparison !== 'string')) throw new Error('The server sent an incomplete reviewer summary. You can retry; nothing was saved.');
      if (event.type === 'decision' && (!['revise', 'retry', 'present', 'stop'].includes(event.outcome ?? '') || typeof event.summary !== 'string')) throw new Error('The server sent an invalid coordinator decision. You can retry; nothing was saved.');
      if (['run.stopped', 'run.failed'].includes(event.type) && typeof event.summary !== 'string') throw new Error('The server sent an incomplete terminal result. You can retry; nothing was saved.');
      if (event.type === 'run.completed') {
        const fields = ['title', 'summary', 'approach', 'first_tests', 'assumptions', 'failure_modes'];
        if (!event.draft || typeof event.receipt !== 'string' || !event.receipt || !event.provenance || typeof event.provenance.provider !== 'string' || typeof event.provenance.model !== 'string' || fields.some(key => typeof event.draft?.[key as keyof ProposalResult['draft']] !== 'string')) throw new Error('The completed stream did not include a complete draft and receipt. You can retry; nothing was saved.');
      }
      if (['run.completed', 'run.stopped', 'run.failed'].includes(event.type)) terminal = event;
      onEvent(event);
    }
  };
  try { while (true) { const { done, value } = await reader.read(); if (done) break; consume(decoder.decode(value, { stream: true })); } consume(decoder.decode()); }
  catch (error) { await reader.cancel().catch(() => {}); throw error; }
  if (buffer.trim()) consume('\n\n');
  if (!terminal) throw new Error('The progress stream ended without a final result. You can retry; nothing was saved.');
  return terminal;
}
function GenerateStrategy({ path, projectId, sourceGuard, onSaved, onCancel }: {
  path: string; projectId: string; sourceGuard: string; onSaved: (view: ProjectView) => void; onCancel: () => void;
}) {
  const composer = useRef<HTMLDivElement>(null);
  const request = useRef<AbortController | null>(null);
  const submitting = useRef(false);
  const [config, setConfig] = useState<{ available: boolean; provider: string; mode: string; binding: string; project_id: string; model: string; reasoning_effort: string; message: string } | null>(null);
  const [seed, setSeed] = useState('');
  const ai = useAI();
  const lifetime = useRef(new AbortController());
  const runGuard = useRef('');
  const [result, setResult] = useState<ProposalResult | null>(null);
  const [title, setTitle] = useState('');
  const [summary, setSummary] = useState('');
  const [approach, setApproach] = useState('');
  const [busy, setBusy] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [activities, setActivities] = useState<string[]>([]);
  const [currentActivity, setCurrentActivity] = useState('');
  const [review, setReview] = useState<AgenticEvent | null>(null);
  useEffect(() => {
    composer.current?.querySelector('textarea')?.focus();
    const controller = new AbortController();
    fetch(`/api/projects/proposals/config?${new URLSearchParams({ path })}`, { signal: controller.signal }).then(async response => { if (!response.ok) throw new Error('Could not read AI configuration'); return response.json(); }).then(setConfig).catch(error => { if (!controller.signal.aborted) setError(errorMessage(error)); });
    return () => { controller.abort(); lifetime.current.abort(); request.current?.abort(); };
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    fetch(`/api/projects/proposals/config?${new URLSearchParams({ path })}`, { signal: controller.signal }).then(response => response.json()).then(setConfig).catch(() => {});
    return () => controller.abort();
  }, [ai.info?.mode, ai.info?.active_account, ai.info?.status]);
  const needsConnection = ai.info?.mode !== 'api_key' && ['disconnected', 'reauth_required', 'unauthorized', 'plan_not_permitted'].includes(ai.info?.status ?? 'disconnected');
  async function cancel() {
    if (saving || cancelling) return;
    if (busy) {
      setCancelling(true);
      if (ai.connecting) ai.cancelSignIn();
      request.current?.abort();
      return;
    }
    lifetime.current.abort(); onCancel();
  }
  async function generate() {
    if (submitting.current) return; submitting.current = true;
    runGuard.current = sourceGuard;
    const controller = new AbortController(); request.current = controller; setBusy(true); setError(''); setActivities([]); setCurrentActivity('Preparing run'); setReview(null);
    let finishProviderRequest = () => {};
    try {
      if (needsConnection) {
        const connected = await ai.signIn({ accountId: ai.info?.active_account, enablePlan: ai.info?.status === 'plan_not_permitted', signal: lifetime.current.signal });
        if (!connected || lifetime.current.signal.aborted) return;
      }
      const response = await fetch(`/api/projects/proposals/config?${new URLSearchParams({ path })}`, { signal: controller.signal });
      if (!response.ok) throw new Error('Could not read current AI settings. Retry explicitly.');
      const latest = await response.json(); setConfig(latest);
      if (latest.project_id !== projectId) throw new Error('Project identity changed during sign-in. Reopen it before generating; your text is retained.');
      if (!latest.available) throw new Error(latest.message);
      if (lifetime.current.signal.aborted) return;
      finishProviderRequest = beginProviderRequest('strategy-generation');
      const stream = await fetch('/api/projects/proposals/agentic', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ path, seed, expected_binding: latest.binding, expected_project_id: projectId }), signal: controller.signal });
      const terminal = await readAgenticStream(stream, event => {
        if (event.type === 'activity.started' && event.kind) setCurrentActivity(`${activityLabels[event.kind]}${event.attempt ? ` · attempt ${event.attempt}` : ''}`);
        if (event.type === 'activity.completed' && event.kind) {
          setActivities(previous => [...previous, `${activityLabels[event.kind!]}${event.attempt ? ` · attempt ${event.attempt}` : ''}: ${event.summary ?? 'completed'}`]);
          if (event.kind === 'challenge') setReview(event);
          setCurrentActivity('');
        }
        if (event.type === 'decision') { setActivities(previous => [...previous, `Decision · ${event.outcome}: ${event.summary}`]); setCurrentActivity(''); }
        if (event.type === 'run.started') setCurrentActivity(`Starting bounded run · up to ${event.max_calls ?? 'configured'} model calls`);
      });
      if (terminal.type === 'run.completed' && terminal.draft && terminal.receipt && terminal.provenance) {
        const next: ProposalResult = { draft: terminal.draft, receipt: terminal.receipt, provenance: terminal.provenance };
        setResult(next); setTitle(next.draft.title); setSummary(next.draft.summary); setApproach(next.draft.approach); setCurrentActivity('Ready for your review');
        requestAnimationFrame(() => document.getElementById('proposal-title')?.focus());
      } else if (terminal.type === 'run.stopped') { setCurrentActivity('Run stopped'); setError(`${terminal.summary ?? 'No viable candidate was found.'} Nothing was saved. You can retry with different guidance.`); }
      else { setCurrentActivity('Run failed'); throw new Error(terminal.summary ?? 'The run failed. No strategy was saved.'); }
    } catch (error) {
      if (controller.signal.aborted) { setCurrentActivity('Run cancelled'); setError('Run cancelled. Nothing was saved. If generation had started, its evidence will be retained in project export. You can retry.'); }
      else { const message = errorMessage(error); setCurrentActivity('Run could not be completed'); setError(message); reportRequestFailure(message); }
    }
    finally { finishProviderRequest(); if (request.current === controller) {
      request.current = null;
      submitting.current = false; setBusy(false); setCancelling(false);
    } }
  }
  async function save(event: FormEvent) {
    event.preventDefault(); if (submitting.current || !result) return; submitting.current = true; setSaving(true); setError('');
    try {
      if (runGuard.current !== sourceGuard) throw new Error('Project research inputs changed while this strategy was generating. Regenerate against the current project before accepting; this draft is still available for reference.');
      onSaved(await post<ProjectView>('strategies', { path, title, approach, summary, receipt: result.receipt }));
    }
    catch (error) { setError(errorMessage(error)); }
    finally { submitting.current = false; setSaving(false); }
  }
  return <div ref={composer} className="strategy-form proposal-dialog inline-proposal" role="region" aria-labelledby="proposal-heading" aria-describedby="proposal-help" onKeyDown={event => { if (event.key === "Escape") { event.preventDefault(); cancel(); } }}>
    <div className="proposal-heading-row"><h2 id="proposal-heading">Generate a strategy</h2><button type="button" className="text-view-link proposal-heading-generate" disabled={(!config?.available && !needsConnection) || busy || saving || ai.connecting} onClick={() => void generate()}>{busy ? cancelling ? 'Cancelling…' : ai.connecting ? 'Connecting…' : 'Generating…' : result ? 'Regenerate' : 'Generate'}</button>{result && <button type="submit" form="proposal-save-form" className="text-view-link proposal-heading-save" disabled={busy || saving}>{saving ? 'Accepting…' : 'Accept'}</button>}<button type="button" className="text-view-link proposal-heading-cancel" disabled={saving || cancelling} onClick={() => void cancel()}>{busy ? cancelling ? 'Cancelling…' : "Cancel request" : "Cancel"}</button></div>
    {!busy && <p id="proposal-help" className="hint">Explore and independently challenge a candidate, then review the editable, unsaved draft before accepting.</p>}
    <p className="provider-context">{config ? `${config.mode === 'api_key' ? 'OpenAI API · billed separately' : 'Using ChatGPT plan'} · ${config.model} · ${thinkingLabels[config.reasoning_effort] ?? config.reasoning_effort}` : 'Reading AI settings…'} · call limit from this project’s settings{config?.mode === 'chatgpt' && <ManageUsage/>}</p>
    {config && !config.available && <p role="status" className="hint">{config.message}</p>}
    <details className="proposal-context" open={!result}><summary>Generation context &amp; starting point (optional)</summary>
    <label htmlFor="proposal-seed" className="sr-only">Starting point (optional)</label>
    <textarea id="proposal-seed" rows={3} maxLength={4000} value={seed} disabled={busy || saving} onChange={event => setSeed(event.target.value)} aria-describedby="seed-help"/>
    <p id="seed-help" className="hint">An optional idea or mechanism to investigate, not an assumption to accept uncritically. Leave empty for an independent research direction.</p>
    <p className="hint">Generation sends this problem, mode, all strategy titles/approaches (including removed ones), and the starting point to OpenAI. Cancelling disconnects the active run; provider usage may already count toward the selected plan or billing mode.</p>
    </details>
    {(busy || activities.length > 0 || currentActivity) && <section className="agentic-activity" aria-label="Generation progress" aria-live="polite">
      {busy && <span className="agentic-filament" aria-hidden="true"/>}
      {currentActivity && <p className="agentic-current">{currentActivity}</p>}
      {activities.length > 0 && <ol>{activities.map((item, index) => <li key={`${index}-${item}`}>{item}</li>)}</ol>}
    </section>}
    {review && <section className="agentic-review" aria-label="Independent review"><strong>Independent review · {review.assessment}</strong><p>{review.summary}</p><p>{review.mechanism_comparison}</p><ul>{review.objections?.map((objection, index) => <li key={index}>{objection}</li>)}</ul><p><strong>Still to establish:</strong> {review.missing_obligations}</p></section>}
    <p className="sr-only" role="status" aria-live="polite">{busy ? currentActivity || 'Generating strategy…' : ''}</p>
    <PlanWelcome/>
    {ai.connecting && <button type="button" onClick={ai.cancelSignIn}>Cancel sign-in</button>}
    {ai.handoff && <a href={ai.handoff} target="_blank" rel="noreferrer">Open sign-in browser</a>}
    {ai.error && <p role="alert" className="error">{ai.error}</p>}
    {error && <p role="alert" className="error">{error}</p>}
    <form id="proposal-save-form" onSubmit={save}>
      {result && <fieldset disabled={busy || saving} className="proposal-review">
        <legend>Unsaved draft · Review before accepting</legend>
        <label htmlFor="proposal-title">Title</label><input id="proposal-title" required maxLength={200} value={title} onChange={event => setTitle(event.target.value)}/>
        <label htmlFor="proposal-summary">Description</label><input id="proposal-summary" required maxLength={300} value={summary} onChange={event => setSummary(event.target.value)}/>
        <label htmlFor="proposal-approach">Plan</label><textarea id="proposal-approach" required maxLength={MAX_STRATEGY_APPROACH} rows={12} value={approach} onChange={event => setApproach(event.target.value)}/>
        <p className="hint">AI-assisted suggestion · {result.provenance.provider} / {result.provenance.model}{result.provenance.reasoning_effort ? ` · ${thinkingLabels[result.provenance.reasoning_effort] ?? result.provenance.reasoning_effort} thinking` : ''}. Accepting saves your edits and records your acceptance; reviewer obligations remain open as shown above.</p>
      </fieldset>}
    </form>
  </div>;
}

function ProjectScreen({ path, initialView, onClose, goHome }: {
  path: string; initialView?: ProjectView; onClose: () => void;
  goHome: (event: MouseEvent<HTMLAnchorElement>) => void;
}) {
  const [view, setView] = useState<ProjectView | null>(initialView ?? null);
  const [error, setError] = useState('');
  const [closing, setClosing] = useState(false);
  const [editing, setEditing] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [manualDraft, setManualDraft] = useState<{ title: string; approach: string; summary?: string }>();
  const [projectEditing, setProjectEditing] = useState(false);
  const [exportOpen, setExportOpen] = useState(false);
  const [paperOpen, setPaperOpen] = useState(false);
  const modeOwner = useRef<string | null>(null);
  const [activeMode, setActiveMode] = useState<string | null>(null);
  const enterMode = useCallback((owner: string) => {
    if (modeOwner.current !== null) return false;
    modeOwner.current = owner; setActiveMode(owner); return true;
  }, []);
  const exitMode = useCallback((owner: string) => {
    if (modeOwner.current !== owner) return;
    modeOwner.current = null; setActiveMode(null);
  }, []);
  const editProjectButton = useRef<HTMLButtonElement>(null);
  const [ordering, setOrdering] = useState(false);
  const [previewOrder, setPreviewOrder] = useState<string[] | null>(null);
  const [dragId, setDragId] = useState<string | null>(null);
  const drag = useRef<{ id: string; order: string[]; pointer: number | null } | null>(null);
  const [announcement, setAnnouncement] = useState('');
  const [focusStrategy, setFocusStrategy] = useState('');
  const [strategiesExpanded, setStrategiesExpanded] = useState(() => window.localStorage.getItem(`sigma.strategiesPane:${path}`) !== 'false');
  const [collapsedStrategies, setCollapsedStrategies] = useState<Set<string>>(() => new Set());
  const [textEditSignals, setTextEditSignals] = useState<Record<string, number>>({});
  const [combinedTextDrafts, setCombinedTextDrafts] = useState<Record<string, string>>({});
  const requestTextEdit = (key: string) => setTextEditSignals(current => ({ ...current, [key]: (current[key] ?? 0) + 1 }));
  const updateCombinedTextDraft = (key: string, draft: string) => setCombinedTextDrafts(current => ({ ...current, [key]: draft }));
  const [projectExpanded, setProjectExpanded] = useState(() => window.localStorage.getItem(`sigma.projectPane:${path}`) !== 'false');
  const [processControls, setProcessControls] = useState<ProcessControls>({ play: () => {}, stop: () => {}, playDisabled: true, stopDisabled: true, playLabel: 'Start a new research session' });
  const heading = useRef<HTMLHeadingElement>(null);
  const newButton = useRef<HTMLButtonElement>(null);
  const introPane = useRef<HTMLDivElement>(null);
  const resizeStart = useRef<{ pointer: number; y: number; height: number } | null>(null);
  const [introHeight, setIntroHeight] = useState<number | null>(null);
  useEffect(() => {
    setIntroHeight(null);
    const frame = requestAnimationFrame(() => { if (introPane.current) setIntroHeight(Math.round(introPane.current.getBoundingClientRect().height)); });
    return () => cancelAnimationFrame(frame);
  }, [view?.project.id, view?.project.title, view?.project.problem]);
  useEffect(() => {
    if (initialView) return;
    const controller = new AbortController();
    post<ProjectView>('open', { path }, controller.signal).then(setView).catch(error => {
      if (!controller.signal.aborted) setError(errorMessage(error));
    });
    return () => controller.abort();
  }, [path]);
  useEffect(() => {
    if (view) document.title = `${view.project.title} · SIGMA`;
    else if (error) document.title = 'Project unavailable · SIGMA';
    heading.current?.focus();
  }, [view?.project.id, !!error]);
  useEffect(() => {
    if (!focusStrategy || !strategiesExpanded) return;
    const target = document.getElementById(`strategy-${focusStrategy}`);
    requestAnimationFrame(() => { target?.scrollIntoView({ block: 'center', behavior: 'smooth' }); target?.focus(); });
  }, [focusStrategy, strategiesExpanded]);
  useEffect(() => {
    if (!dragId) return;
    function pointerMove(event: PointerEvent) {
      if (drag.current?.pointer !== event.pointerId) return;
      event.preventDefault();
      const activeId = drag.current.id;
      const rows = Array.from(document.querySelectorAll<HTMLElement>('.strategy-row'))
        .filter(row => row.dataset.strategyId !== activeId);
      const before = rows.find(row => {
        const rect = row.getBoundingClientRect();
        return event.clientY < rect.top + rect.height / 2;
      });
      moveBefore(before?.dataset.strategyId ?? null);
      if (event.clientY > window.innerHeight - 60) window.scrollBy(0, 16);
      if (event.clientY < 60) window.scrollBy(0, -16);
    }
    function pointerUp(event: PointerEvent) { if (drag.current?.pointer === event.pointerId) void drop(); }
    function pointerCancel(event: PointerEvent) { if (drag.current?.pointer === event.pointerId) cancelDrag(); }
    function escape(event: KeyboardEvent) { if (event.key === 'Escape') { event.preventDefault(); const id = drag.current?.id; cancelDrag(); if (id) document.getElementById(`grip-${id}`)?.focus(); } }
    // Document listeners survive DOM relocation of the captured grip during touch sorting.
    document.addEventListener('pointermove', pointerMove, { passive: false });
    document.addEventListener('pointerup', pointerUp);
    document.addEventListener('pointercancel', pointerCancel);
    document.addEventListener('keydown', escape);
    return () => { document.removeEventListener('pointermove', pointerMove); document.removeEventListener('pointerup', pointerUp); document.removeEventListener('pointercancel', pointerCancel); document.removeEventListener('keydown', escape); };
  }, [dragId, view]);
  async function close() {
    setClosing(true); setError('');
    try { await post('close'); onClose(); }
    catch (error) { setError(errorMessage(error)); setClosing(false); }
  }
  const frame = { goHome, close: { action: close, busy: closing }, connectionDisabled: activeMode !== null };
  function toggleStrategiesPane() {
    setStrategiesExpanded(open => { window.localStorage.setItem(`sigma.strategiesPane:${path}`, String(!open)); return !open; });
  }
  function showStrategy(id: string) {
    setCollapsedStrategies(current => { const next = new Set(current); next.delete(id); return next; });
    if (!strategiesExpanded) {
      setStrategiesExpanded(true);
      window.localStorage.setItem(`sigma.strategiesPane:${path}`, 'true');
    }
    if (id) setFocusStrategy(id);
  }
  function cancel() { setEditing(false); exitMode('new-strategy'); requestAnimationFrame(() => newButton.current?.focus()); }
  function expandStrategies() { setStrategiesExpanded(true); window.localStorage.setItem(`sigma.strategiesPane:${path}`, 'true'); }
  function startNewStrategy() {
    if (!enterMode('new-strategy')) return;
    expandStrategies(); setManualDraft(undefined); setEditing(true);
    requestAnimationFrame(() => document.getElementById('strategy-title')?.focus());
  }
  function startGeneration() {
    if (modeOwner.current !== null || generating) return;
    expandStrategies(); setGenerating(true);
    requestAnimationFrame(() => document.getElementById('proposal-seed')?.focus());
  }
  if (!view) return <WorkspaceFrame {...frame}><div className="workspace-state" aria-live="polite">{error ? <>
    <h1 ref={heading} tabIndex={-1}>Project unavailable</h1><p role="alert" className="error">{error}</p>
    <p>Close this project to choose another directory.</p>
  </> : <p className="intro">Opening project…</p>}</div></WorkspaceFrame>;
  const project = view.project;
  const introMaximum = Math.max(160, Math.min(Math.round(window.innerHeight * .75), 800));
  const clampIntro = (height: number) => Math.max(120, Math.min(introMaximum, Math.round(height)));
  const byId = new Map(project.strategies.map(strategy => [strategy.id, strategy]));
  const strategies = (previewOrder ?? project.active_order).map(id => byId.get(id)!);
  function forkFromFindings(session: ResearchSession) {
    if (!enterMode('new-strategy')) return;
    const parent = byId.get(session.strategy_id);
    const parentApproach = session.strategy_text ?? parent?.approach ?? '';
    const evidence = session.artifacts.slice(-3).map(artifact => [
      `Artifact ${artifact.sequence}: ${artifact.claim_or_question}`,
      `Skeptic objections: ${artifact.objections.join(' · ') || 'None recorded'}`,
      `Open obligations: ${artifact.open_obligations.join(' · ') || 'None recorded'}`,
      `Coordinator decision: ${artifact.coordinator_decision}`,
      `Next question: ${artifact.next_question || 'None recorded'}`,
    ].join('\n')).join('\n\n');
    const prefix = [
      `Fork rationale: derived from strategy “${session.strategy_title}” (ID ${session.strategy_id}) after Research Session #${session.session_number}.`,
      'Use the saved findings below to revise the approach. Preserve unresolved obligations as open work; treat model notes as unverified.',
      evidence ? `\nSaved findings and criticism:\n${evidence}` : '',
      '\nParent approach follows:',
    ].filter(Boolean).join('\n');
    const available = Math.max(0, MAX_STRATEGY_APPROACH - prefix.length - 120);
    const clippedParent = parentApproach.slice(0, available);
    const approach = `${prefix}\n${clippedParent}${parentApproach.length > clippedParent.length ? '\n[Parent approach shortened to fit; see the source session for the complete saved strategy.]' : ''}`.slice(0, MAX_STRATEGY_APPROACH);
    setManualDraft({
      title: `${session.strategy_title} (Session ${session.session_number} fork)`.slice(0, 200),
      summary: `Fork of ${session.strategy_title} informed by Session #${session.session_number}`.slice(0, 300),
      approach,
    });
    expandStrategies(); setEditing(true);
    requestAnimationFrame(() => document.getElementById('strategy-title')?.focus());
  }
  function pickup(id: string, pointer: number | null) {
    if (ordering || drag.current) return;
    drag.current = { id, order: [...project.active_order], pointer }; setDragId(id);
    setPreviewOrder([...project.active_order]);
    setAnnouncement(`Picked up ${byId.get(id)!.title}. Arrow keys move, Enter drops, Escape cancels.`);
  }
  function moveTo(index: number) {
    const active = drag.current; if (!active) return;
    const order = [...active.order]; const old = order.indexOf(active.id);
    const target = Math.max(0, Math.min(order.length - 1, index));
    order.splice(old, 1); order.splice(target, 0, active.id);
    if (order.every((id, position) => id === active.order[position])) return;
    active.order = order; setPreviewOrder(order);
    setAnnouncement(`Position ${target + 1} of ${order.length}.`);
  }
  function moveBefore(targetId: string | null) {
    const active = drag.current; if (!active) return;
    const order = active.order.filter(id => id !== active.id);
    const target = targetId ? order.indexOf(targetId) : order.length;
    order.splice(Math.max(0, target), 0, active.id);
    if (order.every((id, position) => id === active.order[position])) return;
    active.order = order; setPreviewOrder(order);
    setAnnouncement(`Position ${order.indexOf(active.id) + 1} of ${order.length}.`);
  }
  function cancelDrag() {
    drag.current = null; setDragId(null); setPreviewOrder(null); setAnnouncement('Reorder cancelled.');
  }
  async function drop() {
    const active = drag.current; if (!active) return;
    drag.current = null; setDragId(null);
    if (active.order.join() === project.active_order.join()) { setPreviewOrder(null); setAnnouncement('Order unchanged.'); return; }
    setOrdering(true); setError('');
    try {
      setView(await post<ProjectView>('strategies/reorder', { path: view!.path, order: active.order, expected_order: project.active_order }));
      setAnnouncement('Strategy order saved.');
    } catch (error) { setError(errorMessage(error)); setAnnouncement('Order save failed. Previous order restored.'); }
    finally { setOrdering(false); setPreviewOrder(null); requestAnimationFrame(() => document.getElementById(`grip-${active.id}`)?.focus()); }
  }
  return <WorkspaceFrame {...frame} projectTitle={project.title} projectType={project.investigation_type} projectView={view!} onProjectUpdated={setView}>
    <section className="workspace-pane project-pane" aria-labelledby="project-pane-heading">
      <header className="workspace-pane-heading project-pane-heading">
        <h2 id="project-pane-heading" ref={heading} tabIndex={-1}>
          <button type="button" className="workspace-section-disclosure" aria-expanded={projectExpanded} aria-controls="project-pane-content" title={`${projectExpanded ? 'Collapse' : 'Expand'} Project section`} onClick={() => setProjectExpanded(value => { window.localStorage.setItem(`sigma.projectPane:${path}`, String(!value)); return !value; })}>
            <DisclosureChevron expanded={projectExpanded}/>Project
          </button>
        </h2>
        <div className="project-pane-actions">
          <button type="button" className="text-view-link text-view-icon project-latex-button" aria-label="LaTeX research paper" title="Generate a LaTeX research paper" data-tooltip="Generate a LaTeX research paper" disabled={closing || ordering || !!dragId || activeMode !== null} onClick={() => setPaperOpen(true)}>
            <span className="latex-wordmark" aria-hidden="true">T<span className="latex-lowered-e">E</span>X</span>
          </button>
          {project.investigation_type === 'mathematical' && <button type="button" className="text-view-link text-view-icon project-lean-button" aria-label="Generate Lean proof (coming soon)" title="Generate Lean proof (coming soon)" data-tooltip="Generate Lean proof (coming soon)" disabled>
            <img src="/lean-logo.svg" alt="" aria-hidden="true"/>
          </button>}
          <button type="button" className="text-view-link text-view-icon" aria-label="Export project" title="Export project" data-tooltip="Export project" disabled={closing || ordering || !!dragId} onClick={() => setExportOpen(true)}>
            <svg aria-hidden="true" viewBox="0 0 20 20" fill="none"><path d="M10 2.5v9m0 0 3.5-3.5M10 11.5 6.5 8M3.5 13v3.5h13V13" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"/></svg>
          </button>
          <button ref={editProjectButton} type="button" className="text-view-link text-view-icon" aria-label="Project settings" title="Settings" disabled={closing || ordering || !!dragId || activeMode !== null} onClick={() => { if (enterMode('project-settings')) setProjectEditing(true); }}>
            <SettingsGearIcon />
          </button>
        </div>
      </header>
      <div id="project-pane-content" hidden={!projectExpanded}>
      <ProjectPaneTitle view={view} onSaved={setView} disabled={closing || ordering || !!dragId} modeDisabled={activeMode !== null && activeMode !== 'project-title'} descriptionDraft={combinedTextDrafts.project ?? project.problem} onEnterMode={() => enterMode('project-title')} onExitMode={() => exitMode('project-title')} onEditDescription={() => requestTextEdit('project')}/>
      <div className="project-pane-content">
        <div className="project-intro" id="project-intro-pane" ref={introPane} style={introHeight === null ? undefined : { height: introHeight, maxHeight: 'min(75dvh, 800px)' }}>
          <TextViews mathematical={project.investigation_type === 'mathematical'} path={view.path} scope="project" source={project.problem} projectTitle={project.title} contentClass="objective" onSaved={setView} hideProjectActions hideProjectHeading hideEditAction markdownSlotId="project-markdown-slot" editSignal={textEditSignals.project ?? 0} combinedEditMode={activeMode === 'project-title'} onCombinedDraftChange={draft => updateCombinedTextDraft('project', draft)} modeDisabled={activeMode !== null && activeMode !== 'text-project' && activeMode !== 'project-title'} onEnterMode={() => enterMode('text-project')} onExitMode={() => exitMode('text-project')}/>
        </div>
        <div className="project-pane-resizer" role="separator" tabIndex={0} aria-label="Resize project description" aria-controls="project-intro-pane" aria-orientation="horizontal" aria-valuemin={120} aria-valuemax={introMaximum} aria-valuenow={introHeight ?? undefined} title="Drag or use arrow keys to resize the project description"
      onPointerDown={event => { if (event.button !== 0) return; const height = introPane.current?.getBoundingClientRect().height ?? 120; resizeStart.current = { pointer: event.pointerId, y: event.clientY, height }; event.currentTarget.setPointerCapture(event.pointerId); event.preventDefault(); }}
      onPointerMove={event => { const start = resizeStart.current; if (start?.pointer === event.pointerId) setIntroHeight(clampIntro(start.height + event.clientY - start.y)); }}
      onPointerUp={event => { if (resizeStart.current?.pointer === event.pointerId) resizeStart.current = null; }}
      onPointerCancel={event => { if (resizeStart.current?.pointer === event.pointerId) resizeStart.current = null; }}
      onKeyDown={event => { const current = introPane.current?.getBoundingClientRect().height ?? 120; if (event.key === 'ArrowUp' || event.key === 'ArrowDown') { event.preventDefault(); setIntroHeight(clampIntro(current + (event.key === 'ArrowDown' ? 24 : -24))); } else if (event.key === 'Home' || event.key === 'End') { event.preventDefault(); setIntroHeight(event.key === 'Home' ? 120 : introMaximum); } }}><span aria-hidden="true"/></div>
      </div>
      </div>
    </section>
    {error && <p role="alert" className="error">{error}</p>}
    <section className={`pool workspace-pane strategies-pane${strategiesExpanded ? '' : ' is-collapsed'}`} aria-labelledby="pool-heading">
      <header className="pool-heading workspace-pane-heading strategies-pane-heading">
        <h2 id="pool-heading" tabIndex={-1}><button type="button" className="workspace-section-disclosure" title={`${strategiesExpanded ? 'Collapse' : 'Expand'} Strategies section`} aria-expanded={strategiesExpanded} aria-controls="strategies-pane-content" onClick={toggleStrategiesPane}><DisclosureChevron expanded={strategiesExpanded}/>Strategies</button></h2>
        <div className="strategies-heading-right">
          <StrategyCreationActions buttonRef={newButton} hideNew={generating} disabled={activeMode !== null || generating || closing || ordering || !!dragId || !!processControls.confirming} onManual={startNewStrategy} onAI={startGeneration}/>
          <p className="section-count">{strategies.length} strateg{strategies.length === 1 ? 'y' : 'ies'}</p>
          <ProcessControlsView controls={processControls} disabled={activeMode !== null || closing || ordering || !!dragId}/>
        </div>
      </header>
      <div id="strategies-pane-content" hidden={!strategiesExpanded}>
      <p className="sr-only" role="status">{announcement}</p>
      <div id="strategy-composer">{editing && <NewStrategy initialDraft={manualDraft} path={view.path} onCancel={cancel} onSaved={next => {
        const strategy = next.project.strategies[next.project.strategies.length - 1];
        setView(next); setEditing(false); exitMode('new-strategy'); setAnnouncement(`Strategy saved: ${strategy.title}`);
        setFocusStrategy(strategy.id);
      }}/>}
      {generating && <GenerateStrategy path={view.path} projectId={view.project.id} sourceGuard={JSON.stringify({ project_id: project.id, problem: project.problem, strategies: project.strategies.map(item => [item.id, item.title, item.approach, item.removed_at]) })} onCancel={() => { setGenerating(false); requestAnimationFrame(() => newButton.current?.focus()); }} onSaved={next => {
        const strategy = next.project.strategies.at(-1)!; setView(next); setGenerating(false); setFocusStrategy(strategy.id); setAnnouncement('AI-assisted strategy accepted and saved.');
      }}/>}</div>
      {strategies.length ? <div className="strategies-table">
        <div className="strategy-columns" aria-hidden="true"><span>Strategy</span></div>
        <ol className="strategy-list" aria-label="Strategies" aria-busy={ordering}>
        {strategies.map(strategy => <li className={`strategy-row${strategies.length === 1 ? ' is-only-strategy' : ''}${!strategy.enabled ? ' is-disabled' : ''}${dragId === strategy.id ? ' is-lifted' : ''}`} key={strategy.id} data-strategy-id={strategy.id}>
          <div className="strategy-row-main">
            <StrategyTitleEditor strategy={strategy} path={view.path} onSaved={setView} modeDisabled={activeMode !== null && activeMode !== `strategy-title-${strategy.id}`} descriptionDraft={combinedTextDrafts[`strategy:${strategy.id}`] ?? strategy.approach} onEnterMode={() => enterMode(`strategy-title-${strategy.id}`)} onExitMode={() => exitMode(`strategy-title-${strategy.id}`)} onEditDescription={() => requestTextEdit(`strategy:${strategy.id}`)} expanded={!collapsedStrategies.has(strategy.id)} onToggle={() => setCollapsedStrategies(current => { const next = new Set(current); if (next.has(strategy.id)) next.delete(strategy.id); else next.add(strategy.id); return next; })} commands={<StrategyCommands strategy={strategy} disabled={activeMode !== null || processControls.confirming} onCommand={(mode, strategy) => {
              if (ordering || dragId || activeMode !== null || processControls.confirming) return;
              if (mode === 'toggle') {
                const owner = `strategy-toggle-${strategy.id}`;
                if (!enterMode(owner)) return;
                void post<ProjectView>('strategies/enabled', { path: view.path, strategy_id: strategy.id, enabled: !strategy.enabled })
                  .then(next => { setView(next); setAnnouncement(`${strategy.title} ${strategy.enabled ? 'disabled' : 'enabled'}.`); })
                  .catch(cause => { setError(errorMessage(cause)); reportRequestFailure(errorMessage(cause)); })
                  .finally(() => exitMode(owner));
                return;
              }
              if (mode === 'fork') {
                if (!enterMode('new-strategy')) return;
                expandStrategies(); setManualDraft({ title: `${strategy.title} (forked)`, approach: strategy.approach, summary: strategy.summary }); setEditing(true);
                requestAnimationFrame(() => document.getElementById('strategy-composer')?.scrollIntoView({ block: 'nearest' }));
                return;
              }
              const owner = `strategy-remove-${strategy.id}`;
              if (!enterMode(owner)) return;
              void post<ProjectView>('strategies/remove', { path: view.path, strategy_id: strategy.id })
                .then(next => {
                  setView(next); setAnnouncement(`Removed ${strategy.title} from Strategies. History retained.`);
                  requestAnimationFrame(() => document.getElementById('pool-heading')?.focus());
                })
                .catch(cause => { setError(errorMessage(cause)); reportRequestFailure(errorMessage(cause)); })
                .finally(() => exitMode(owner));
            }}/>} />
            <div id={`strategy-content-${strategy.id}`} className="strategy-expanded" hidden={collapsedStrategies.has(strategy.id)}><TextViews mathematical={project.investigation_type === 'mathematical'} path={view.path} scope="strategy" strategyId={strategy.id} source={strategy.approach} contentClass="strategy-approach" onSaved={setView} hideEditAction markdownSlotId={`strategy-markdown-slot-${strategy.id}`} editSignal={textEditSignals[`strategy:${strategy.id}`] ?? 0} combinedEditMode={activeMode === `strategy-title-${strategy.id}`} onCombinedDraftChange={draft => updateCombinedTextDraft(`strategy:${strategy.id}`, draft)} modeDisabled={activeMode !== null && activeMode !== `text-strategy-${strategy.id}` && activeMode !== `strategy-title-${strategy.id}`} onEnterMode={() => enterMode(`text-strategy-${strategy.id}`)} onExitMode={() => exitMode(`text-strategy-${strategy.id}`)}/></div>
          </div>
          {strategies.length > 1 && <button id={`grip-${strategy.id}`} className="drag-grip" disabled={ordering || closing}
            aria-label={`Reorder ${strategy.title}`} title={`Drag to reorder ${strategy.title}`} aria-describedby="reorder-help" aria-pressed={dragId === strategy.id}
            onPointerDown={event => { if (event.button !== 0) return; event.preventDefault(); event.currentTarget.focus(); pickup(strategy.id, event.pointerId); event.currentTarget.setPointerCapture(event.pointerId); }}
            onKeyDown={event => { if (event.key === 'Escape' && drag.current) { event.preventDefault(); cancelDrag(); }
              else if (event.key === ' ' && !drag.current) { event.preventDefault(); pickup(strategy.id, null); }
              else if (drag.current?.id === strategy.id && ['ArrowUp', 'ArrowDown', 'Enter', ' '].includes(event.key)) { event.preventDefault();
                if (event.key === 'ArrowUp' || event.key === 'ArrowDown') moveTo(drag.current.order.indexOf(strategy.id) + (event.key === 'ArrowUp' ? -1 : 1)); else void drop();
              } }}><svg width="12" height="16" viewBox="0 0 12 16" fill="currentColor" aria-hidden="true">{[3,7,11].flatMap(y => [3,7].map(x => <circle key={`${x}-${y}`} cx={x} cy={y} r="1"/>))}</svg></button>}
        </li>)}
      </ol></div> : !editing && <p className="pool-empty">No strategies yet.</p>}
      {(dragId || ordering) && <p className="reorder-feedback">{ordering ? 'Saving order…' : 'Moving strategy · Release or press Enter to save · Escape cancels'}</p>}
      <p id="reorder-help" className="sr-only">Drag only the corner grip to reorder. Keyboard: Space picks up, arrows move, Enter drops, Escape cancels. Changes save on drop.</p>
      </div>
    </section>
    <ResearchWorkspace path={view.path} projectId={project.id} strategies={strategies} onViewStrategy={showStrategy} onForkFromFindings={forkFromFindings} onControlsChange={setProcessControls}/>
    {projectEditing && <ProjectSettingsDialog initial={view} onCancel={() => { setProjectEditing(false); exitMode('project-settings'); requestAnimationFrame(() => editProjectButton.current?.focus()); }} onSaved={next => { setView(next); setProjectEditing(false); exitMode('project-settings'); setAnnouncement('Project settings saved.'); requestAnimationFrame(() => editProjectButton.current?.focus()); }}/>}
    <ProjectExportDialog open={exportOpen} path={view.path} title={project.title} onCancel={() => { setExportOpen(false); requestAnimationFrame(() => document.querySelector<HTMLButtonElement>('.project-pane-actions [aria-label="Export project"]')?.focus()); }}/>
    {paperOpen && (
      <AIPaperDialog path={view.path} projectId={project.id} downloadFilename="sigma-paper.pdf" openInTab={false} onCancel={() => {
        setPaperOpen(false);
        requestAnimationFrame(() => document.querySelector<HTMLButtonElement>('.project-latex-button')?.focus());
      }} />
    )}
    {SHOW_PROJECT_DETAILS_AND_HISTORY && <details className="project-details">
      <summary>Project details &amp; history</summary>
      <dl><dt>Identity</dt><dd>{project.id}</dd><dt>Directory</dt><dd>{view.path}</dd><dt>Format version</dt><dd>{project.schema_version}</dd><dt>Research type</dt><dd>{researchTypeLabel(project.investigation_type)}</dd>{project.difficulty && <><dt>Difficulty</dt><dd>{difficultyLabels[project.difficulty]}</dd></>}<dt>AI model</dt><dd>{project.ai_model}</dd><dt>Thinking level</dt><dd>{thinkingLabels[project.reasoning_effort] ?? project.reasoning_effort}</dd></dl>
      <h3>Event history</h3>
      <ol className="event-list">{project.events.map(event => <li key={event.sequence}>
        <span className="sequence">{String(event.sequence).padStart(2, '0')}</span>
        <div><span>{event.kind}</span><time dateTime={event.timestamp}>{dateLabel(event.timestamp)}</time>
          {event.project_change && <details className="edit-history"><summary>View project changes</summary><dl>{(Object.keys(event.project_change.current) as (keyof Settings)[]).filter(key => event.project_change!.previous[key] !== event.project_change!.current[key]).map(key => <div key={key}><dt>{({ title: 'Project name', problem: 'Research problem', investigation_type: 'Research type', ai_model: 'AI model', reasoning_effort: 'Thinking level', difficulty: 'Difficulty' })[key]}</dt><dd>Before: {key === 'investigation_type' ? researchTypeLabel(String(event.project_change!.previous[key])) : key === 'difficulty' ? difficultyLabel(event.project_change!.previous[key] as ProjectDifficulty | null) : event.project_change!.previous[key]}<br/>After: {key === 'investigation_type' ? researchTypeLabel(String(event.project_change!.current[key])) : key === 'difficulty' ? difficultyLabel(event.project_change!.current[key] as ProjectDifficulty | null) : event.project_change!.current[key]}</dd></div>)}</dl></details>}
          {event.stage_change && <p>Manually tracked: {stageLabels[event.stage_change.previous]} → {stageLabels[event.stage_change.stage]}</p>}
          {event.order && <details><summary>Saved order</summary><ol>{event.order.map(id => <li key={id}>{byId.get(id)?.title ?? id}</li>)}</ol></details>}
          {event.change && <details className="edit-history"><summary>View changes</summary>
            <dl><dt>Name before</dt><dd>{event.change.previous_title}</dd>
              <dt>Name after</dt><dd>{event.change.title}</dd>
              <dt>Description before</dt><dd>{event.change.previous_approach}</dd>
              <dt>Description after</dt><dd>{event.change.approach}</dd></dl>
          </details>}
        </div>
      </li>)}</ol>
      <p className="hint">Opening and inspecting a project leave its history unchanged.</p>
    </details>}
  </WorkspaceFrame>;
}

function App() {
  const [openedView, setOpenedView] = useState<ProjectView | null>(null);
  const [location, setLocation] = useState(() => window.location.pathname + window.location.search);
  const [lastPath, setLastPath] = useState(() =>
    new URLSearchParams(window.location.search).get('path') || 'projects/rh.sigma');
  useEffect(() => {
    const pop = () => { setOpenedView(null); setLocation(window.location.pathname + window.location.search); };
    window.addEventListener('popstate', pop);
    return () => window.removeEventListener('popstate', pop);
  }, []);
  const navigate = useCallback((url: string) => {
    window.history.pushState(null, '', url); setLocation(url); window.scrollTo(0, 0);
  }, []);
  const closeProject = useCallback(() => {
    setOpenedView(null);
    const path = new URLSearchParams(window.location.search).get('path');
    if (path) { setLastPath(path); window.localStorage.setItem('sigma.currentProject', path); }
    navigate('/');
  }, [navigate]);
  function goHome(event: MouseEvent<HTMLAnchorElement>) {
    if (event.button === 0 && !event.metaKey && !event.ctrlKey && !event.shiftKey && !event.altKey) {
      event.preventDefault(); setOpenedView(null); navigate('/');
    }
  }
  const url = new URL(location, window.location.origin);
  return <><main className={url.pathname === '/' ? 'home-page' : 'workspace-page'}>
    {url.pathname === '/' ? <Home initialPath={lastPath} onOpen={view => {
      setOpenedView(view); setLastPath(view.path); window.localStorage.setItem('sigma.currentProject', view.path); navigate(projectUrl(view.path));
    }}/> : url.pathname === '/project' ? <ProjectScreen key={location}
      initialView={openedView?.path === url.searchParams.get('path') ? openedView : undefined} path={url.searchParams.get('path') ?? ''} onClose={closeProject} goHome={goHome}/>
      : <><Header goHome={goHome}/><h1>Page not found</h1><a href="/" onClick={goHome}>Return Home</a></>}
  </main><FloatingTooltip/></>;
}

type CloudStatus = { target?: 'local' | 'hosted'; enabled: boolean; ready: boolean; authenticated: boolean; user: { email: string; role: string } | null; admin_contact_email: string | null; local_setup_missing?: string[] };
type CloudGrant = { kind: string; value: string; role: string; active: number; allowance_usd: number | null; effective_allowance_usd: number | null };
type CloudAccountSession = { email: string; role: string; authorized: boolean; status: string; expires_at: number | null; allowance_usd: number | null; spending?: { estimated_usage_usd: number; held_usd: number; reserved_and_estimated_usd: number; remaining_usd: number | null } };
type CloudFunding = { target: 'local' | 'hosted'; budget: CloudResearchBudget | null; loading: boolean; error: string | null; authorized: boolean };
type CloudIdentityState = CloudStatus & { deniedEmail: string | null; funding: CloudFunding; openAccessManagement: () => void };
const CloudIdentityContext = createContext<CloudIdentityState | null>(null);
function useCloudIdentity() { return useContext(CloudIdentityContext); }
function cloudFundingFor(cloud: CloudIdentityState | null): CloudFunding | undefined {
  return cloud?.funding;
}

type CloudDemoAudit = { export_version: 2; project: ProjectView['project']; agentic_runs: Record<string, any>[]; research_sessions: Record<string, any>[] };
function CloudDemoExperience({ deniedEmail, authenticated, user }: { deniedEmail: string | null; authenticated: boolean; user: CloudStatus['user'] }) {
  const [audit, setAudit] = useState<CloudDemoAudit | null>(null);
  const [error, setError] = useState('');
  const [exportOpen, setExportOpen] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    fetch('/api/cloud-demo/', { cache: 'no-store', signal: controller.signal }).then(async response => {
      if (!response.ok) throw new Error('The curated Demo is temporarily unavailable.');
      const value = await response.json() as CloudDemoAudit;
      if (value.export_version !== 2 || !value.project || !Array.isArray(value.agentic_runs) || !Array.isArray(value.research_sessions)) throw new Error('The curated Demo data could not be verified.');
      setAudit(value);
    }).catch(cause => { if (!controller.signal.aborted) setError(errorMessage(cause)); });
    return () => controller.abort();
  }, []);
  const project = audit?.project;
  return <main className="cloud-demo-page">
    <header className="cloud-demo-header"><a className="cloud-demo-brand" href="/">SIGMA</a><nav aria-label="Demo navigation"><a href={deniedEmail ? '/?access=denied' : '/'}>{deniedEmail ? 'Invitation request' : 'Home'}</a>{authenticated ? <><span>{user?.email}</span><button onClick={async () => { await fetch('/api/cloud-auth/logout', { method: 'POST', credentials: 'same-origin' }); window.location.assign('/demo'); }}>Sign out</button></> : <a className="cloud-demo-signin" href="/api/cloud-auth/login">Sign in with Google</a>}</nav></header>
    <section className="cloud-demo-intro"><p className="cloud-auth-kicker">Public read-only preview</p><h1>Explore a SIGMA research project</h1><p>Inspect a curated saved project, its strategies, research sessions, outcomes, computational evidence and report exports. This shared Demo does not create a workspace or run agents.</p></section>
    {error && <section className="cloud-demo-state" role="alert"><h2>Demo unavailable</h2><p>{error}</p></section>}
    {!audit && !error && <p className="cloud-demo-state" role="status">Loading saved Demo data…</p>}
    {audit && project && <>
      <section className="cloud-demo-project"><div><p className="cloud-auth-kicker">{researchTypeLabel(project.investigation_type)} · {difficultyLabel(project.difficulty)}</p><h2>{project.title}</h2><div className="cloud-demo-markdown"><RenderedMarkdown body={project.problem}/></div></div><button className="cloud-demo-export" onClick={() => setExportOpen(true)}>Export project</button></section>
      <section className="cloud-demo-section"><h2>Strategies <span>{project.strategies.length}</span></h2><div className="cloud-demo-grid">{project.strategies.map(strategy => <details className="cloud-demo-card" key={strategy.id} open><summary><span>{strategy.title}</span><small>{strategy.stage} · {strategy.author_kind}</small></summary><p>{strategy.summary}</p><div className="cloud-demo-markdown"><RenderedMarkdown body={strategy.approach}/></div></details>)}</div></section>
      <section className="cloud-demo-section"><h2>Research sessions <span>{audit.research_sessions.length}</span></h2>{audit.research_sessions.map(session => <details className="cloud-demo-card cloud-demo-session" key={session.id}><summary><span>Session #{session.session_number}: {session.strategy_title}</span><small>{session.status} · {session.started_at?.slice(0, 10)}</small></summary><div className="cloud-demo-columns"><div><h3>Outcome</h3><p>{session.outcome?.solution_review?.claim}</p><p>{session.outcome?.solution_review?.argument_summary}</p><h3>Strategy assessment</h3>{session.strategy_assessments?.map((item: any) => <p key={item.strategy_id}>{item.assessment}: {item.rationale}</p>)}</div><div><h3>Saved research artifacts</h3>{session.artifacts?.map((artifact: any) => <article className="cloud-demo-evidence" key={artifact.id}><strong>{artifact.claim}</strong><p>{artifact.method}</p><small>Evidence status: {artifact.evidence_status}</small><p>{artifact.skeptic_response}</p>{artifact.computational_evidence && <details><summary>Inspect saved computation</summary><p>{artifact.computational_evidence.interpretation}</p><pre>{artifact.computational_evidence.source}{'\n'}{artifact.computational_evidence.stdout}</pre>{artifact.computational_evidence.files?.map((file: any) => <details key={file.filename}><summary>Captured artifact: {file.filename}</summary><pre>{file.content}</pre><small>SHA-256: {file.sha256}</small></details>)}</details>}</article>)}</div></div></details>)}</section>
      <section className="cloud-demo-section"><h2>Saved analysis <span>{audit.agentic_runs.length}</span></h2>{audit.agentic_runs.map(run => <details className="cloud-demo-card" key={run.run_id}><summary><span>Research run · {run.status}</span><small>{run.started_at?.slice(0, 10)}</small></summary><p>{run.timeline?.map((entry: any) => entry.message).join(' ')}</p>{run.steps?.map((step: any, index: number) => <article className="cloud-demo-evidence" key={index}><strong>{step.output?.title}</strong><p>{step.output?.approach}</p><small>{step.output?.evidence_boundary}</small></article>)}</details>)}</section>
      <footer className="cloud-demo-footer"><p>Read-only curated data · exports are generated from this saved snapshot</p><button className="cloud-demo-export" onClick={() => setExportOpen(true)}>Export Project Audit or Research Report</button></footer>
      {exportOpen && <ProjectExportDialog demo path="" title={project.title} onCancel={() => setExportOpen(false)}/>}
    </>}
  </main>;
}


function GoogleIdentityPill({ compact = false }: { compact?: boolean }) {
  const cloud = useCloudIdentity();
  const [open, setOpen] = useState(false);
  const disclosure = useRef<HTMLButtonElement>(null);
  const panel = useRef<HTMLDivElement>(null);
  const [position, setPosition] = useState<{ top: number; right: number } | null>(null);
  const [error, setError] = useState('');
  useEffect(() => {
    if (!open) return;
    const place = () => {
      const rect = disclosure.current?.getBoundingClientRect();
      if (!rect || !panel.current) return;
      const panelRect = panel.current.getBoundingClientRect();
      const below = rect.bottom + 8 + panelRect.height <= window.innerHeight - 8;
      const right = Math.min(Math.max(8, window.innerWidth - rect.right), Math.max(8, window.innerWidth - panelRect.width - 8));
      setPosition({ top: below ? rect.bottom + 8 : Math.max(8, rect.top - panelRect.height - 8), right });
    };
    const frame = requestAnimationFrame(() => {
      place();
      panel.current?.querySelector<HTMLElement>('button:not(:disabled), a[href]')?.focus();
    });
    const escape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') { event.preventDefault(); setOpen(false); requestAnimationFrame(() => disclosure.current?.focus()); }
      if (event.key !== 'Tab' || !panel.current) return;
      const items = Array.from(panel.current.querySelectorAll<HTMLElement>('button:not(:disabled), a[href]')).filter(item => item.offsetParent !== null);
      if (!items.length) { event.preventDefault(); panel.current.focus(); return; }
      const first = items[0]; const last = items.at(-1)!;
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    };
    window.addEventListener('resize', place); window.addEventListener('scroll', place, true); document.addEventListener('keydown', escape);
    return () => { cancelAnimationFrame(frame); window.removeEventListener('resize', place); window.removeEventListener('scroll', place, true); document.removeEventListener('keydown', escape); };
  }, [open]);
  function close() { setOpen(false); requestAnimationFrame(() => disclosure.current?.focus()); }
  function dismissBackdrop(event: ReactPointerEvent<HTMLDivElement>) { if (event.target === event.currentTarget) close(); }
  async function signOut() {
    setError('');
    try {
      const response = await fetch('/api/cloud-auth/logout', { method: 'POST', credentials: 'same-origin' });
      if (!response.ok) throw new Error('Google sign-out could not be completed.');
      window.location.assign('/');
    } catch (cause) { setError(errorMessage(cause)); }
  }
  const canSignIn = !!cloud?.enabled && cloud.ready;
  const setupMissing = cloud?.local_setup_missing ?? [];
  const description = cloud?.authenticated ? 'Google account connected; open account settings' : canSignIn ? 'Sign in with Google' : 'Google sign-in setup required';
  return <>
    <button ref={disclosure} type="button" className={`project-google-signin${compact ? ' compact' : ''}`} aria-haspopup="dialog" aria-expanded={open} aria-label={description} data-tooltip-disabled="" onClick={() => { setError(''); setPosition(null); setOpen(true); }}>
      <span className={`connection-dot${cloud?.authenticated ? ' connection-connected' : ' connection-disconnected'}`} aria-hidden="true"/><span>{cloud?.authenticated ? 'Google account connected' : canSignIn ? 'Sign in with Google' : 'Google sign-in setup required'}</span>
    </button>
    {open && createPortal(<>
      <div className="connection-backdrop" onPointerDown={dismissBackdrop}/>
      <div ref={panel} className="connection-details google-connection-details" role="dialog" aria-modal="true" aria-labelledby={cloud?.authenticated ? undefined : 'google-account-title'} aria-label={cloud?.authenticated ? 'Google account' : undefined} tabIndex={-1} style={{ top: position?.top ?? 8, right: position?.right ?? 8 }}>
      {!cloud ? <>
        <h2 id="google-account-title">Checking Google sign-in</h2>
        <p>SIGMA is checking the local Google authentication configuration.</p>
      </> : !canSignIn && !cloud.authenticated ? <>
        <h2 id="google-account-title">Google sign-in setup required</h2>
        <p>Local Google sign-in is unavailable because the current SIGMA launch is missing required configuration.</p>
        {setupMissing.length > 0 && <p className="google-setup-missing">Missing: {setupMissing.map(name => <code key={name}>{name}</code>)}</p>}
        {setupMissing.length === 0 && <p>Local Google authentication is not enabled for this server process. Restart using <code>./sigma start --nav</code> after exporting the required settings.</p>}
        <p>Set the missing values in the environment used to start SIGMA. Put the Google OAuth client ID and secret in this checkout’s <code>.env</code>. Set <code>SIGMA_CLOUD_BOOTSTRAP_ADMIN_EMAIL</code> to the operator’s actual Gmail address. If that value is in <code>~/.bashrc</code>, run <code>source ~/.bashrc</code> in the launching shell, then restart with <code>./sigma start --nav</code>.</p>
        <p>Google verifies the account and SIGMA checks its email and persistent Google subject before granting access.</p>
      </> : <>
        {!cloud?.authenticated && <h2 id="google-account-title">Connect your Google account</h2>}
        {cloud?.authenticated && <p className="google-account-email">{cloud.user?.email}</p>}
        {cloud?.deniedEmail && <p className="google-account-denied" role="status">Access is not granted for {cloud.deniedEmail}.</p>}
        {!cloud?.authenticated && canSignIn && <a className="cloud-auth-button" href="/api/cloud-auth/login">Sign in with Google</a>}
        {cloud?.authenticated && <button type="button" className="google-text-action" onClick={() => void signOut()}>Sign out</button>}
      </>}
      {error && <p role="alert">{error}</p>}
      </div>
    </>, document.body)}
  </>;
}
function allowanceInput(value: number | null) { return value === null ? '' : value.toFixed(2); }
function AccessManagementDialog({ bootstrapAdmin, grants, sessions, error, busy, onClose, onAdd, onSave, onRevoke }: {
  bootstrapAdmin: string; grants: CloudGrant[]; sessions: CloudAccountSession[];
  error: string; busy: boolean; onClose: () => void;
  onAdd: (entry: { kind: 'email' | 'domain'; value: string; role: 'member' | 'admin'; allowance_usd: number | null }) => Promise<void>;
  onSave: (updates: { kind: 'email' | 'domain'; value: string; role: 'member' | 'admin'; allowance_usd: number | null }[]) => Promise<void>;
  onRevoke: (grant: CloudGrant) => Promise<void>;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [drafts, setDrafts] = useState<Record<string, { role: string; allowance: string }>>({});
  const [addOpen, setAddOpen] = useState(false);
  const [newKind, setNewKind] = useState<'email' | 'domain'>('email');
  const [newValue, setNewValue] = useState('');
  const [newRole, setNewRole] = useState<'member' | 'admin'>('member');
  const [newAllowance, setNewAllowance] = useState('');
  const addButton = useRef<HTMLButtonElement>(null);
  const newEntryPanel = useRef<HTMLDivElement>(null);
  const [newEntryPosition, setNewEntryPosition] = useState<{ left: number; top: number; maxHeight: number } | null>(null);
  const [confirmRemoveKey, setConfirmRemoveKey] = useState('');
  const [removeConfirmationPosition, setRemoveConfirmationPosition] = useState<{ left: number; top: number } | null>(null);
  const removeButtons = useRef(new Map<string, HTMLButtonElement>());
  const removeConfirmation = useRef<HTMLDivElement>(null);
  const removeConfirmButton = useRef<HTMLButtonElement>(null);
  const [message, setMessage] = useState('');
  const [activeTab, setActiveTab] = useState<'access' | 'usage'>('access');
  useEffect(() => {
    setDrafts(Object.fromEntries(grants.map(grant => [`${grant.kind}:${grant.value}`, { role: grant.role, allowance: allowanceInput(grant.allowance_usd) }])));
  }, [grants]);
  useEffect(() => { if (!dialog.current?.open) dialog.current?.showModal(); }, []);
  useEffect(() => {
    if (!addOpen) {
      setNewEntryPosition(null);
      return;
    }
    const place = () => {
      const panel = newEntryPanel.current?.getBoundingClientRect();
      const parent = dialog.current?.getBoundingClientRect();
      if (!parent) return;
      const width = panel?.width ?? Math.min(340, parent.width - 24);
      const height = panel?.height ?? 300;
      const maxHeight = Math.max(140, Math.min(window.innerHeight - 16, parent.height - 24));
      const left = parent.left + (parent.width - width) / 2;
      const top = parent.top + (parent.height - Math.min(height, maxHeight)) / 2;
      setNewEntryPosition({ left, top, maxHeight });
    };
    const frame = requestAnimationFrame(() => {
      place();
      newEntryPanel.current?.querySelector<HTMLInputElement>('input')?.focus();
    });
    const escape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        cancelAdd();
      }
    };
    window.addEventListener('resize', place);
    window.addEventListener('scroll', place, true);
    document.addEventListener('keydown', escape, true);
    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener('resize', place);
      window.removeEventListener('scroll', place, true);
      document.removeEventListener('keydown', escape, true);
    };
  }, [addOpen]);
  useEffect(() => {
    if (!confirmRemoveKey) {
      setRemoveConfirmationPosition(null);
      return;
    }
    const place = () => {
      const anchor = removeButtons.current.get(confirmRemoveKey)?.getBoundingClientRect();
      const popover = removeConfirmation.current?.getBoundingClientRect();
      const parent = dialog.current?.getBoundingClientRect();
      if (!anchor || !parent) return;
      const width = popover?.width ?? Math.min(280, window.innerWidth - 24);
      const height = popover?.height ?? 100;
      const left = Math.max(parent.left + 12, Math.min(anchor.right - width, parent.right - width - 12));
      const belowSpace = Math.max(0, parent.bottom - anchor.bottom - 8);
      const aboveSpace = Math.max(0, anchor.top - parent.top - 8);
      const below = height <= belowSpace || belowSpace >= aboveSpace;
      const top = below ? Math.min(anchor.bottom + 8, parent.bottom - height - 8) : Math.max(parent.top + 8, anchor.top - height - 8);
      setRemoveConfirmationPosition({ left, top });
    };
    const frame = requestAnimationFrame(() => {
      place();
      removeConfirmButton.current?.focus();
    });
    const escape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        setConfirmRemoveKey('');
      }
    };
    window.addEventListener('resize', place);
    window.addEventListener('scroll', place, true);
    document.addEventListener('keydown', escape, true);
    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener('resize', place);
      window.removeEventListener('scroll', place, true);
      document.removeEventListener('keydown', escape, true);
      requestAnimationFrame(() => removeButtons.current.get(confirmRemoveKey)?.focus());
    };
  }, [confirmRemoveKey]);
  const ordered = grants.filter(grant => grant.active === 1).sort((a, b) => a.value.localeCompare(b.value, undefined, { sensitivity: 'base' }) || a.kind.localeCompare(b.kind));
  const changed = ordered.filter(grant => {
    const key = `${grant.kind}:${grant.value}`; const draft = drafts[key];
    return grant.active === 1 && draft && (draft.role !== grant.role || draft.allowance.trim() !== allowanceInput(grant.allowance_usd));
  });
  const validation = (value: string) => value.trim() === '' || /^\d+(?:\.\d{1,2})?$/.test(value.trim()) && Number(value) >= 0.01 && Number(value) <= 15;
  const draftsValid = changed.every(grant => validation(drafts[`${grant.kind}:${grant.value}`]?.allowance ?? ''));
  const hasDrafts = changed.length > 0;
  function requestClose() {
    if (hasDrafts && !window.confirm('Discard only the unsaved role or allowance edits? Completed Add, Remove, and Save actions remain in effect.')) return;
    dialog.current?.close(); onClose();
  }
  async function addEntry() {
    const value = newValue.trim();
    if (!value || !validation(newAllowance) || value.includes('@') !== (newKind === 'email')) return;
    try {
      await onAdd({ kind: newKind, value, role: newKind === 'domain' ? 'member' : newRole, allowance_usd: newAllowance.trim() ? Number(newAllowance) : null });
      setNewValue(''); setNewAllowance(''); setAddOpen(false); setMessage('');
      requestAnimationFrame(() => addButton.current?.focus());
    } catch (cause) { setMessage(cause instanceof Error ? cause.message : 'Authorization could not be added.'); }
  }
  function cancelAdd() {
    setNewValue(''); setNewAllowance(''); setNewKind('email'); setNewRole('member'); setAddOpen(false);
    requestAnimationFrame(() => addButton.current?.focus());
  }
  async function saveUpdates() {
    if (!hasDrafts || !draftsValid) return;
    const updates = changed.map(grant => {
      const draft = drafts[`${grant.kind}:${grant.value}`];
      return { kind: grant.kind as 'email' | 'domain', value: grant.value, role: draft.role as 'member' | 'admin', allowance_usd: draft.allowance.trim() ? Number(draft.allowance) : null };
    });
    try { await onSave(updates); setMessage(`Saved ${updates.length} authorization ${updates.length === 1 ? 'update' : 'updates'}.`); }
    catch (cause) { setMessage(cause instanceof Error ? cause.message : 'Updates could not be saved.'); }
  }
  async function revoke(grant: CloudGrant) {
    try { await onRevoke(grant); setConfirmRemoveKey(''); setMessage(''); }
    catch (cause) { setMessage(cause instanceof Error ? cause.message : 'Authorization could not be revoked.'); }
  }
  const currency = (value: number | null | undefined) => value === null || value === undefined ? '—' : `$${value.toFixed(2)}`;
  return <dialog ref={dialog} className="cloud-access-dialog" aria-labelledby="cloud-access-title" onCancel={event => { event.preventDefault(); requestClose(); }}>
    <div className="admin-dialog-heading"><h2 id="cloud-access-title">Administrator Settings</h2><button type="button" className="admin-text-action" onClick={requestClose}>Close</button></div>
    <div className="admin-tabs" role="tablist" aria-label="Administrator settings" onKeyDown={event => {
      if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
      event.preventDefault();
      const next = event.key === 'Home' ? 'access' : event.key === 'End' ? 'usage' : event.key === 'ArrowRight' ? (activeTab === 'access' ? 'usage' : 'access') : (activeTab === 'usage' ? 'access' : 'usage');
      setActiveTab(next); requestAnimationFrame(() => document.getElementById(next === 'access' ? 'access-management-tab' : 'account-usage-tab')?.focus());
    }}>
      <button type="button" role="tab" id="access-management-tab" aria-controls="access-management-panel" aria-selected={activeTab === 'access'} tabIndex={activeTab === 'access' ? 0 : -1} onClick={() => setActiveTab('access')}>Access Management</button>
      <button type="button" role="tab" id="account-usage-tab" aria-controls="account-usage-panel" aria-selected={activeTab === 'usage'} tabIndex={activeTab === 'usage' ? 0 : -1} onClick={() => setActiveTab('usage')}>Account usage</button>
    </div>
    <section id="access-management-panel" role="tabpanel" tabIndex={0} aria-labelledby="access-management-tab" className="admin-access-panel" hidden={activeTab !== 'access'}>
      <p className="admin-access-note">Authorized email and domain rules. Domain allowances apply separately to each person; email rules take precedence.</p>
      <p className="cloud-access-bootstrap">Built-in administrator: {bootstrapAdmin || 'not configured'}</p>
      <div className="admin-table-heading"><h3>Authorized users</h3></div>
      <div className="admin-table-scroll"><table className="admin-grants-table"><colgroup><col style={{ width: '35%' }}/><col style={{ width: '14%' }}/><col style={{ width: '32%' }}/><col style={{ width: '19%' }}/></colgroup><thead><tr><th scope="col">Email / Domain</th><th scope="col">Role</th><th scope="col">ChatGPT Allowance</th><th scope="col">Actions</th></tr></thead><tbody>
        {ordered.map(grant => {
          const key = `${grant.kind}:${grant.value}`; const draft = drafts[key] ?? { role: grant.role, allowance: allowanceInput(grant.allowance_usd) };
          const isBootstrap = grant.kind === 'email' && grant.value.toLowerCase() === bootstrapAdmin.toLowerCase();
          return <tr key={key} className={grant.active ? '' : 'is-revoked'}>
            <th scope="row"><span className="admin-entry-value">{grant.value}</span><small>{grant.kind === 'email' ? 'Email' : 'Domain'}{grant.active ? '' : ' · Removed'}</small></th>
            <td>{grant.kind === 'domain' ? <span>Member</span> : <select aria-label={`Role for ${grant.value}`} value={draft.role} disabled={!grant.active || isBootstrap || busy} onChange={event => setDrafts(value => ({ ...value, [key]: { ...draft, role: event.target.value } }))}><option value="member">Member</option><option value="admin">Admin</option></select>}</td>
            <td><label className="admin-allowance-input"><span className="sr-only">ChatGPT allowance for {grant.value}</span><span aria-hidden="true">$</span><input type="text" inputMode="decimal" value={draft.allowance} disabled={!grant.active || busy} aria-invalid={!validation(draft.allowance)} aria-describedby={`allowance-${grant.kind}-${grant.value}`} onChange={event => setDrafts(value => ({ ...value, [key]: { ...draft, allowance: event.target.value } }))}/></label><small id={`allowance-${grant.kind}-${grant.value}`}>{validation(draft.allowance) ? `Effective ${currency(grant.effective_allowance_usd)}` : 'Enter $0.01 to $15.00'}</small></td>
            <td>{grant.active === 1 && !isBootstrap && <button ref={element => { if (element) removeButtons.current.set(key, element); else removeButtons.current.delete(key); }} type="button" className="admin-text-action admin-remove" aria-expanded={confirmRemoveKey === key} disabled={busy} onClick={() => setConfirmRemoveKey(current => current === key ? '' : key)}>Remove</button>}{isBootstrap && <span className="admin-protected-entry">Protected</span>}</td>
          </tr>;
        })}
        {!ordered.length && <tr><td colSpan={4} className="admin-empty-row">No authorization entries yet.</td></tr>}
        <tr className="admin-add-row"><td/><td/><td/><td><button ref={addButton} type="button" className="admin-text-action" aria-expanded={addOpen} onClick={() => setAddOpen(true)}>New</button></td></tr>
      </tbody></table></div>
      {hasDrafts && <div className="admin-save-row"><p>{draftsValid ? `${changed.length} unsaved change${changed.length === 1 ? '' : 's'}.` : 'Correct invalid allowance values before saving.'}</p><button type="button" className="admin-text-action" disabled={busy || !draftsValid} onClick={() => void saveUpdates()}>Save Updates</button></div>}
      {(message || error) && <p role={error || message.includes('could not') ? 'alert' : 'status'} className="admin-feedback">{error || message}</p>}
    </section>
    <section id="account-usage-panel" role="tabpanel" tabIndex={0} aria-labelledby="account-usage-tab" className="admin-usage-panel" hidden={activeTab !== 'usage'}>
      <h3>Account usage</h3>
      {sessions.length ? <div className="admin-table-scroll"><table className="admin-usage-table"><thead><tr><th scope="col">Email</th><th scope="col">Access</th><th scope="col">Allowance</th><th scope="col">Estimated</th><th scope="col">Held</th><th scope="col">Remaining</th></tr></thead><tbody>{sessions.map(session => <tr key={session.email}><th scope="row">{session.email}</th><td>{session.status} · {session.role}</td><td>{currency(session.allowance_usd)}</td><td>{currency(session.spending?.estimated_usage_usd)}</td><td>{currency(session.spending?.held_usd)}</td><td>{currency(session.spending?.remaining_usd)}</td></tr>)}</tbody></table></div> : <p className="cloud-access-bootstrap">No account usage has been recorded.</p>}
    </section>
    {addOpen && createPortal(<div ref={newEntryPanel} className="admin-new-entry-panel" role="group" aria-label="Add authorized user" style={newEntryPosition ? { left: newEntryPosition.left, top: newEntryPosition.top, maxHeight: newEntryPosition.maxHeight } : { left: -10000, top: -10000 }}>
      <h3>New Email or Domain</h3>
      <div className="admin-new-entry-classification"><label>Entry type<select value={newKind} onChange={event => setNewKind(event.target.value as 'email' | 'domain')}><option value="email">Email</option><option value="domain">Domain</option></select></label>{newKind === 'email' && <label>Role<select aria-label="New authorization role" value={newRole} onChange={event => setNewRole(event.target.value as 'member' | 'admin')}><option value="member">Member</option><option value="admin">Admin</option></select></label>}</div>
      <label>{newKind === 'email' ? 'Email address' : 'Domain'}<input aria-label={newKind === 'email' ? 'New email address' : 'New domain'} value={newValue} placeholder={newKind === 'email' ? 'person@example.org' : 'example.org'} onChange={event => setNewValue(event.target.value)} onKeyDown={event => { if (event.key === 'Enter') { event.preventDefault(); void addEntry(); } }}/></label>
      <label>ChatGPT allowance<span className="admin-allowance-input"><span aria-hidden="true">$</span><input aria-label="New ChatGPT allowance" type="text" inputMode="decimal" value={newAllowance} placeholder="Default" aria-invalid={!validation(newAllowance)} onChange={event => setNewAllowance(event.target.value)}/></span><small>Blank uses the configured default</small></label>
      <div className="admin-new-entry-actions"><button type="button" className="admin-text-action" disabled={busy || !newValue.trim() || !validation(newAllowance) || newValue.includes('@') !== (newKind === 'email')} onClick={() => void addEntry()}>Add</button><button type="button" className="admin-text-action" disabled={busy} onClick={cancelAdd}>Cancel</button></div>
    </div>, dialog.current ?? document.body)}
    {confirmRemoveKey && createPortal(<div ref={removeConfirmation} className="admin-remove-confirm" role="group" aria-label={`Confirm remove access for ${confirmRemoveKey.slice(confirmRemoveKey.indexOf(':') + 1)}`} style={removeConfirmationPosition ? { left: removeConfirmationPosition.left, top: removeConfirmationPosition.top } : { left: -10000, top: -10000 }}>
      <p>Remove access for {confirmRemoveKey.slice(confirmRemoveKey.indexOf(':') + 1)}? Recorded usage will be retained.</p>
      <div className="admin-remove-confirm-actions"><button ref={removeConfirmButton} type="button" className="admin-text-action admin-remove" disabled={busy} onClick={() => { const grant = grants.find(item => `${item.kind}:${item.value}` === confirmRemoveKey); if (grant) void revoke(grant); }}>Confirm</button><button type="button" className="admin-text-action" disabled={busy} onClick={() => setConfirmRemoveKey('')}>Cancel</button></div>
    </div>, dialog.current ?? document.body)}
  </dialog>;
}

async function cloudFailure(response: Response, fallback: string) {
  let body: { error?: string; detail?: string } = {};
  try { body = await response.json() as typeof body; } catch { /* use a stable generic error */ }
  return new Error(body.error || (typeof body.detail === 'string' ? body.detail : fallback));
}

function CloudAuthGate() {
  const [status, setStatus] = useState<CloudStatus | null>(null);
  const [failure, setFailure] = useState('');
  const [accessOpen, setAccessOpen] = useState(false);
  const [grants, setGrants] = useState<CloudGrant[]>([]);
  const [accountSessions, setAccountSessions] = useState<CloudAccountSession[]>([]);
  const [bootstrapAdmin, setBootstrapAdmin] = useState('');
  const [busy, setBusy] = useState(false);
  const [deniedEmail, setDeniedEmail] = useState<string | null>(null);
  const [budget, setBudget] = useState<CloudResearchBudget | null>(null);
  const [budgetLoading, setBudgetLoading] = useState(false);
  const [budgetError, setBudgetError] = useState<string | null>(null);
  const refresh = useCallback(async () => {
    try {
      const response = await fetch('/api/cloud-auth/status', { credentials: 'same-origin', cache: 'no-store' });
      if (!response.ok) throw new Error('Google sign-in could not be checked.');
      const current = await response.json() as CloudStatus;
      if (current.enabled && !current.authenticated && new URLSearchParams(window.location.search).get('access') === 'denied') {
        const denied = await fetch('/api/cloud-auth/denied', { credentials: 'same-origin', cache: 'no-store' });
        if (denied.ok) setDeniedEmail((await denied.json() as { email: string }).email);
        else { setDeniedEmail(null); window.history.replaceState(null, '', '/'); }
      } else setDeniedEmail(null);
      setStatus(current); setFailure(current.ready ? '' : 'Google sign-in is not configured correctly.');
    } catch { setFailure('SIGMA could not check Google sign-in. Refresh this page or contact the administrator.'); }
  }, []);
  useEffect(() => { void refresh(); }, [refresh]);
  const loadGrants = useCallback(async () => {
    const response = await fetch('/api/cloud-auth/admin/grants', { credentials: 'same-origin', cache: 'no-store' });
    if (!response.ok) throw await cloudFailure(response, 'Access rules could not be loaded.');
    const result = await response.json() as { grants: CloudGrant[]; sessions: CloudAccountSession[]; bootstrap_admin: string };
    setGrants(result.grants); setAccountSessions(result.sessions); setBootstrapAdmin(result.bootstrap_admin);
  }, []);
  useEffect(() => {
    const target = status?.target ?? 'hosted';
    if (!status?.enabled || !status.authenticated || target !== 'hosted') {
      setBudget(null); setBudgetLoading(false); setBudgetError(null); return;
    }
    let active = true;
    const fetchBudget = async () => {
      setBudgetLoading(true);
      try {
        const response = await fetch('/api/cloud-research/budget', { credentials: 'same-origin', cache: 'no-store' });
        if (!response.ok) throw await cloudFailure(response, 'ChatGPT allowance is unavailable.');
        const result = await response.json() as CloudResearchBudget;
        if (active) { setBudget(result); setBudgetError(null); }
      } catch (cause) { if (active) setBudgetError(cause instanceof Error ? cause.message : 'ChatGPT allowance is unavailable.'); }
      finally { if (active) setBudgetLoading(false); }
    };
    void fetchBudget();
    const interval = window.setInterval(fetchBudget, 30_000);
    window.addEventListener('focus', fetchBudget);
    return () => { active = false; window.clearInterval(interval); window.removeEventListener('focus', fetchBudget); };
  }, [status?.enabled, status?.authenticated, status?.target]);
  async function addGrant(entry: { kind: 'email' | 'domain'; value: string; role: 'member' | 'admin'; allowance_usd: number | null }) {
    setBusy(true);
    try {
      const response = await fetch('/api/cloud-auth/admin/grants', { method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(entry) });
      if (!response.ok) throw await cloudFailure(response, 'Authorization could not be added.');
      await loadGrants();
    } finally { setBusy(false); }
  }
  async function saveGrants(updates: { kind: 'email' | 'domain'; value: string; role: 'member' | 'admin'; allowance_usd: number | null }[]) {
    setBusy(true);
    try {
      const response = await fetch('/api/cloud-auth/admin/grants/updates', { method: 'PUT', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ updates }) });
      if (!response.ok) throw await cloudFailure(response, 'Updates could not be saved.');
      await loadGrants();
    } finally { setBusy(false); }
  }
  async function revokeGrant(grant: CloudGrant) {
    setBusy(true);
    try {
      const response = await fetch(`/api/cloud-auth/admin/grants/${grant.kind}/${encodeURIComponent(grant.value)}`, { method: 'DELETE', credentials: 'same-origin' });
      if (!response.ok) throw await cloudFailure(response, 'Authorization could not be revoked.');
      await loadGrants();
    } finally { setBusy(false); }
  }
  const funding: CloudFunding = { target: status?.target ?? 'local', budget, loading: budgetLoading, error: budgetError, authorized: !!status?.authenticated };
  const context: CloudIdentityState | null = status ? { ...status, deniedEmail, funding, openAccessManagement: () => { setAccessOpen(true); setFailure(''); void loadGrants().catch(error => setFailure(error instanceof Error ? error.message : 'Access rules could not be loaded.')); } } : null;
  if (!status) return <main className="cloud-auth-shell"><p role="status">Checking access…</p></main>;
  if (!status.enabled) return <CloudIdentityContext.Provider value={context}><AIProvider><App/></AIProvider></CloudIdentityContext.Provider>;
  if (!status.ready) return <main className="cloud-auth-shell"><section className="cloud-auth-card"><h1>SIGMA is not ready</h1><p>{failure}</p></section></main>;
  if (window.location.pathname === '/demo') return <CloudDemoExperience deniedEmail={deniedEmail} authenticated={status.authenticated} user={status.user}/>;
  return <CloudIdentityContext.Provider value={context}><AIProvider>{status.authenticated ? <App/> : <main className="home-page"><Home initialPath="" onOpen={() => {}}/></main>}</AIProvider>{accessOpen && status.authenticated && status.user?.role === 'admin' && <AccessManagementDialog bootstrapAdmin={bootstrapAdmin} grants={grants} sessions={accountSessions} error={failure} busy={busy} onClose={() => setAccessOpen(false)} onAdd={addGrant} onSave={saveGrants} onRevoke={revokeGrant}/>}</CloudIdentityContext.Provider>;
}

function AccessNotGranted({ email, contactEmail }: { email: string; contactEmail: string | null }) {
  const subject = 'SIGMA invitation request';
  const body = `Hello,\n\nI signed in to SIGMA with my Google account (${email}), but access has not yet been granted. Please consider inviting me.\n\nThank you.`;
  const requestHref = contactEmail
    ? `mailto:${contactEmail}?${new URLSearchParams({ subject, body })}`
    : undefined;
  return <section className="home-cloud-denied"><p className="cloud-auth-kicker">Google sign-in verified</p><h1>Access not yet granted</h1><p>Your Google account is valid, but it has not been invited to SIGMA.</p><p className="home-cloud-denied-email">Verified account: <strong>{email}</strong></p><div className="cloud-denied-actions">{requestHref ? <a className="cloud-secondary-button" href={requestHref}>Request Invitation</a> : <button className="cloud-secondary-button" disabled title="Administrator contact is not configured">Request Invitation</button>}<a className="cloud-text-button" href="/api/cloud-auth/login">Use Another Account</a></div></section>;
}

installRequestErrorToasts();
createRoot(document.getElementById('root')!).render(<><CloudAuthGate/><RequestErrorToasts/></>);
## Blue Increment 3 — approved causal research continuation (2026-10-24)

Coordinator assignment: `messages/blue_out_4.md`; implementation app revision
`373f564ab957a2f13db298c4190e2e29893328b9`, on `blue_session`, not merged.
Researchers can inspect a saved open duty or write a bounded follow-up, select
cross-strategy sources, reject transfers with reasons and explicitly approve a
new durable strategy. Immutable companion packets preserve parent/source IDs,
source snapshots and uncertainty. New sessions freeze them into actual role
contexts, exact call audits and coordinator decisions. Uptake is explicitly
model-reported, with negative-constraint treatment required for saved local
counterexamples; no proof obligation is automatically closed. New Outcomes expose
inherited sources and reported changes. Original history remains unchanged.

Actual validation: focused continuation/role-contract and research-state tests,
research-session suite and full `./sigma test` passed. Actual installed Chrome
exercised approval, explicit session start, source inspection and reload; saved
source navigation passed at 1440/390/320px without page errors or horizontal
overflow. Reader fixed to exclude `sequence.json` allocation metadata from
unavailable-session counts, found after the first actual new session. Full-run
lint/import failures were fixed before final passing checks.

Controlled actual orchestration: six new sessions, 21 offline scripted HTTP
attempts (20 completed role steps, one interrupted), ten new artifacts. Evidence
ON changes the second dispatched Investigator question relative to OFF. A fresh
RH-SYM injected candidate retains its explicit objection and separate approved
follow-up; the first Investigator context excludes the evaluator answer key.
Negative-transfer rejection and stop/API-process-restart/resume are retained.
All 21 exported call inputs match actual transport bodies/hashes; five original
subset session exports compare equal before/after. Independent exact oracles
check the short-rule counterexample, `a_12=128`, finite Gaussian normalization
and RH logical-countermodel scope. These are not novel agent discoveries.

Evidence and actual before/after Project Audit JSON/native TXT/HTML/TeX reports:
`docs/evaluations/increment_3/`. Zero live provider calls and zero charges; token
accounting in scripted responses is synthetic. Native Markdown reports, PDF,
AI-authored paper quality and unscripted agent research quality are not claimed.
Companion approval-bearing audit-to-sample conversion is explicitly refused
rather than dropping lineage. Dense/repetitive reading surfaces and relevance
selection remain product weaknesses documented in the assessment. No stock
sample or historical source project was changed. Permanent clean-tree mailbox
polling resumes after the report is pushed; no self-merge.
## Blue Increment 4 — real computational research feedback (2026-10-24)

Assignment: `messages/blue_out_5.md`; engine implementation `d9b1b19`, annotation-only
static-check correction `fb919af`; on `blue_session`, not merged. Added optional
strict computational feedback bound to supplied execution ID/status/output hash,
citation and the actual next question. Failed/missing computation, stderr, or
missing/invalid citation/hash cannot support a structured counterexample/result.
Legacy/unstructured claims remain unverified. New continuation contexts pool exact
repeated text losslessly; new Conclusions aggregate repeated uptake prose. Full
approved sources/history remain unchanged. No frontend changes this increment.

Actual SIGMA orchestration with offline HTTP provider transport ran Python and
Sage in the existing local Docker images: nine sessions, 28 captured role requests,
ten execution-attempt records (seven completed, one failed, one actual 15-second
timeout, one uncertain interrupted reservation). Explicit changed-source retry
follows backend death/recovery; incorrect output hash fails closed. Separate
withheld controls have no computations/citations. Source-hashed actual subset
DP disproves an evaluator-authored six-step candidate at `n=0` (`a6=8`, prediction
9); actual graph enumeration refutes an immediate-reverse-edge cycle guard with
a three-vertex cycle. Next dispatched questions contain observed witnesses and
lead to actual discriminating computations. Independent mask/topological-order
oracles validate finite outputs; Sage exact polynomial counts match Python.
Global recurrence/limit and general dynamic-algorithm proofs/bounds remain open.

All 28 exported call inputs match captured actual HTTP bodies/hashes. Existing
nine subset sessions compare equal before/after. Actual API audits/native TXT,
HTML, TeX reports, execution JSON and downloaded observation artifacts are in
`docs/evaluations/increment_4/exports/`. Earlier Sage serialization failure is
retained separately as a failed computation, not disproof. No live provider calls
or charges; provider accounting inputs are synthetic. Exact-text expansion
preserves all selected source coverage while saving 14.6% in the paired context
serialization comparison; main subset Conclusion falls from a deterministic
legacy-render baseline of 7,416 to 2,904 characters. Neither comparison is a new
provider run or an archive rewrite.

Focused feedback/continuation/session checks and final `./sigma test` pass.
Real installed Chrome inspected existing execution source/output navigation and
reload at 1440/390/320px for six cases: 18 checks, no page errors or horizontal
overflow. No Sage installation, cloud provisioning, live research, worker
coordination or self-merge. Unscripted reasoning, general proof/discovery quality,
PDF/AI papers and native Markdown reports are not claimed. Return to permanent
clean-tree 30-second fetch/fast-forward-only polling after pushing `blue_in_4`.
## Blue Increment 5 — integrated research Outcome and provenance gate (2026-10-24)

Coordinator assignment: `messages/blue_out_6.md`. The isolated PR #77 integration
branch merged current `main` (Green's Simple/Advanced Outcome hierarchy and
previously merged UI work) into Increments 3–4 without rewriting any historical
research export. Simple displays a bounded opening excerpt of the saved
Conclusion first when present, with its three leading substantive qualifications,
or a clearly named historical summary when absent; the full text remains in
Advanced and exports. Researcher-approved inherited
sources are collapsed in Advanced, with direct source links and frozen detail;
ordinary available history is labeled separately and duplicate inherited rows
are suppressed in the other-prior-sources list. Settings and older sessions
remain intact. An approved continuation branch filters cross-strategy historical
findings to explicitly approved sources plus its own prior work, preventing an
unselected parent artifact from entering via a multi-strategy session index.

New Python execution reservations now carry the validated saved Investigator
step ID, role, model and thinking level, matching Sage; old records remain
unchanged. An interrupted reservation may retain known proposal attribution,
but its execution result remains unknown. New role calls dispatch full literal
approved continuation text by default. The exact-text pool is retained behind
an internal false-by-default experimental constant; deterministic opt-in tests
confirm round-trip, source coverage and corrupt-alias refusal. In the new actual
smoke run, 20 literal contexts totaled 1,139,058 bytes; a paired deterministic
pooled alternative totaled 972,678 bytes (14.61% fewer bytes), **not** a live
token/cost or comprehension result.

`env -u SIGMA_CLOUD_BOOTSTRAP_ADMIN_EMAIL ./sigma test` passed all steps after
formatter correction; focused continuation, computational-feedback,
research-session and project-settings tests passed. Real SIGMA API orchestration
with offline scripted provider transport generated nine new sessions and 28
captured role calls across isolated subset and algorithm projects, with ten
Docker execution attempts: seven complete, one failed, one timed out and one
interrupted. Existing nine subset sessions compare exactly before/after.
Exact output/hash/citations and next-dispatched questions passed independent
subset and graph oracles, including 543 four-vertex DAGs and 4,500 insertions.
All ten execution records carry the correct saved Investigator provenance; no
live inference or charges occurred. The script's deterministic next-test choice
does not establish autonomous model comprehension.

Installed Chrome covered Simple→Advanced Preference, per-project isolation,
historical summary, inherited source navigation, Markdown icon visibility and
saved execution source/output at 1440/390/320px for six cases (18 evidence
viewport checks, plus six Simple, two mobile Preferences and three Research
Model/Thinking settings screenshots).
No page errors, request-error overlays or horizontal overflow; final browser-state audits show
Preferences changed while every research session object remained equal. An
explicitly synthetic adversarial report test shows a correctly hashed but
meaningless `theorem_proved=true` stdout is only an observation: a conservative
review stays incomplete, while an optimistic role review can still become a
**positive unverified candidate**, never an independently verified proof. This
is a product trust limit, not a solved inference problem. Audit JSON, native
TXT/HTML/TeX reports, execution JSON, downloaded evidence, browser screenshots,
test logs, synthetic-test diagnostics and provenance are in
`docs/evaluations/increment_5/`. The blind unscripted quality gate is proposed
there but awaits explicit paid-provider authorization. No PDF/AI-paper quality,
unprompted reasoning advantage or general mathematical proof is claimed.
## T91 — production-shaped local Compose smoke (2026-10-25)

Ran `./deploy/validate-local.sh` against the tree at
`579a2069090bd972232c88ec8b5515485d81b0b2` (whose code base is current `main`
`f3bae10af63eeb781b549bd610100ba75f6a3633`). Docker Engine 29.5.2 on the
Colima Linux VM and Compose 5.6.1 built the locked backend and frontend images,
started the local Compose stack, served the SPA and API through its edge,
reported hosted auth enabled/ready, and confirmed auth SQLite persistence after
backend restart and container recreation. The script exited 0 with
`Local deployment smoke passed`. It removed its temporary stack, volumes, and
dummy secret files. No Google or provider endpoints were called. Compose was
installed through Homebrew; Docker plugin discovery used a temporary CLI
config, leaving the existing Docker config unchanged.

This verifies the local production-shaped package and its basic persistence
path. It is not a clean-machine README onboarding/browser acceptance run, live
Google OAuth, sponsored inference, GCE startup, rootless-daemon isolation,
public HTTPS, backup restore, or cloud deployment approval. Those remain
separate acceptance items in T91 and the cloud runbook.
## T91 — packaged Chrome workflow increment (2026-10-25)

From `main` at `f0dd5c63dd88cdd79190231856119dbfb317522d` and reconciled with
current `main` (`903a356230267390aa7fdcc20d774eda56195c48`), expanded the
local Compose check to drive installed Chrome against the packaged Caddy,
Nginx, and FastAPI services. The backend image now includes the stock `samples/`
catalog, which the packaged sample endpoint requires. See the explicit
acceptance matrix and run instructions in `docs/evaluations/t91/README.md`.

**PASS:** sample creation; project and strategy edits; save, reload and reopen;
five saved sessions and outcomes; HTML report download; User B denied User A's
project, report, and session evidence; the same session and edited project
survived backend container recreation; packaged Compose health and auth SQLite
survived restart and full container recreation. **SKIPPED:** real Google OAuth
(the workflow seeds two ephemeral local sessions), PDF download (no saved PDF
fixture), and the T100 persistent-disk configuration (this run uses Compose's
default local storage). T99 inference is also skipped; no provider calls were
made. This is local acceptance, not live OAuth or cloud-deployment evidence.
